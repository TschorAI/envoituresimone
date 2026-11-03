# Fuel prices of French stations (prix-carburants.gouv.fr instant flow). Reads the hourly
# snapshot (see ../snapshot.py, refreshed hourly by the app); if it is missing or older than MAX_AGE, asks the
# live data.economie.gouv.fr API instead (cached 10 min in memory). No key.
# Reads: <DATA_DIR>/prices/latest.parquet, https://data.economie.gouv.fr. Writes: nothing.
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from .. import snapshot
from ._http import cached, client, store

SNAPSHOT = snapshot.LATEST
MAX_AGE = timedelta(hours=3)
URL = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
       "prix-des-carburants-en-france-flux-instantane-v2/records")
FUELS = {"e10": "E10 (SP95-E10)", "gazole": "Diesel (gazole)"}  # app key -> label; key is the dataset prefix
PAGE = 100
MAX_STATIONS = 500

_snap: tuple[float, pd.DataFrame] | None = None  # (file mtime, table)


def _snapshot() -> pd.DataFrame | None:
    """The snapshot table if it exists and is fresh enough, re-read only when the file changes."""
    global _snap
    try:
        mtime = SNAPSHOT.stat().st_mtime
    except FileNotFoundError:
        return None
    if datetime.now() - datetime.fromtimestamp(mtime) > MAX_AGE:
        return None
    if _snap is None or _snap[0] != mtime:
        _snap = (mtime, pd.read_parquet(SNAPSHOT))
    return _snap[1]


def source() -> dict:
    """Where prices come from now: {"kind": "snapshot"|"live", "at": ISO time of the snapshot}."""
    df = _snapshot()
    if df is None:
        return {"kind": "live", "at": None}
    return {"kind": "snapshot", "at": df["fetched_at"].iloc[0].isoformat(timespec="minutes")}


def _from_snapshot(df: pd.DataFrame, lat: float, lon: float, radius_km: float, fuel: str) -> list[dict]:
    sel = df[df[f"{fuel}_price"].notna()]
    p1, p2 = np.radians(lat), np.radians(sel["lat"].to_numpy())
    dl = np.radians(sel["lon"].to_numpy() - lon)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    sel = sel[2 * 6371.0 * np.arcsin(np.sqrt(a)) <= radius_km]
    return [{
        "id": r.id, "lat": r.lat, "lon": r.lon, "address": r.address, "city": r.city,
        "postcode": r.postcode, "price": float(getattr(r, f"{fuel}_price")),
        "updated": getattr(r, f"{fuel}_updated").isoformat() if pd.notna(getattr(r, f"{fuel}_updated")) else None,
    } for r in sel.itertuples()]


async def _live(lat: float, lon: float, radius_km: float, fuel: str) -> list[dict]:
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
                "updated": (s.get(f"{fuel}_maj") or "")[:19] or None,  # local time labelled UTC
            })
        if len(rows) < PAGE:
            break
        offset += PAGE
    return store(key, out)


def all_stations(fuel: str) -> pd.DataFrame | None:
    """Every station selling `fuel` in the snapshot, columns id, lat, lon, address, city, postcode,
    price, updated, fetched_at; None if there is no fresh snapshot (no live fallback: too big)."""
    df = _snapshot()
    if df is None:
        return None
    sel = df[df[f"{fuel}_price"].notna()]
    return sel[["id", "lat", "lon", "address", "city", "postcode", "fetched_at"]].assign(
        price=sel[f"{fuel}_price"], updated=sel[f"{fuel}_updated"])


async def stations_near(lat: float, lon: float, radius_km: float, fuel: str) -> list[dict]:
    """Stations within `radius_km` that sell `fuel`: [{id, lat, lon, address, city, postcode, price, updated}]."""
    if fuel not in FUELS:
        raise ValueError(f"unknown fuel {fuel!r}; one of {list(FUELS)}")
    df = _snapshot()
    if df is not None:
        return _from_snapshot(df, lat, lon, radius_km, fuel)
    return await _live(lat, lon, radius_km, fuel)
