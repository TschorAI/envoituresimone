# Live fuel prices of French stations (prix-carburants.gouv.fr, instant flow, via the
# data.economie.gouv.fr API). No key. Cached in memory for 10 minutes.
# Reads: https://data.economie.gouv.fr. Writes: nothing.
from __future__ import annotations

import statistics

from ._http import cached, client, store

URL = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
       "prix-des-carburants-en-france-flux-instantane-v2/records")
FUELS = {"e10": "E10 (SP95-E10)", "gazole": "Diesel (gazole)"}  # app key -> label; key is the dataset prefix
PAGE = 100
MAX_STATIONS = 500


async def stations_near(lat: float, lon: float, radius_km: float, fuel: str) -> list[dict]:
    """Stations within `radius_km` that sell `fuel` now: [{id, lat, lon, address, city, price, updated}]."""
    if fuel not in FUELS:
        raise ValueError(f"unknown fuel {fuel!r}; one of {list(FUELS)}")
    key = f"st:{lat:.4f}:{lon:.4f}:{radius_km}:{fuel}"
    if (hit := cached(key, 600)) is not None:
        return hit
    where = (f"within_distance(geom, geom'POINT({lon} {lat})', {radius_km}km) "
             f"AND {fuel}_prix IS NOT NULL")
    select = f"id,adresse,ville,cp,geom,{fuel}_prix,{fuel}_maj"
    out, offset = [], 0
    while offset < MAX_STATIONS:
        r = await client().get(URL, params={"where": where, "select": select, "limit": PAGE, "offset": offset})
        r.raise_for_status()
        rows = r.json().get("results", [])
        for s in rows:
            if not s.get("geom"):
                continue
            out.append({
                "id": str(s["id"]), "lat": s["geom"]["lat"], "lon": s["geom"]["lon"],
                "address": (s.get("adresse") or "").title(), "city": s.get("ville") or "",
                "postcode": s.get("cp") or "", "price": float(s[f"{fuel}_prix"]),
                "updated": s.get(f"{fuel}_maj"),
            })
        if len(rows) < PAGE:
            break
        offset += PAGE
    return store(key, out)


async def median_price(lat: float, lon: float, fuel: str, radius_km: float = 10) -> float | None:
    """Median price around a point; widens the circle once if nothing is found."""
    for r in (radius_km, radius_km * 3):
        st = await stations_near(lat, lon, r, fuel)
        if st:
            return statistics.median(s["price"] for s in st)
    return None
