# Géoplateforme (IGN) address lookup: search, autocompletion and reverse lookup. No key.
# Reads: https://data.geopf.fr/geocodage. Writes: nothing.
from __future__ import annotations

from ._http import cached, client, store

BASE = "https://data.geopf.fr/geocodage"


async def search(q: str, limit: int = 5) -> list[dict]:
    """Address -> [{label, lat, lon}], best match first."""
    key = f"geo:{q}:{limit}"
    if (hit := cached(key, 86400)) is not None:
        return hit
    r = await client().get(f"{BASE}/search", params={"q": q, "limit": limit, "index": "address"})
    r.raise_for_status()
    out = [
        {"label": f["properties"]["label"], "lon": f["geometry"]["coordinates"][0],
         "lat": f["geometry"]["coordinates"][1]}
        for f in r.json().get("features", [])
    ]
    return store(key, out)


async def complete(text: str, limit: int = 6) -> list[dict]:
    """Partial address -> suggestions [{label, lat, lon}] for the search box."""
    if len(text.strip()) < 3:
        return []
    key = f"compl:{text}:{limit}"
    if (hit := cached(key, 86400)) is not None:
        return hit
    r = await client().get(f"{BASE}/completion/", params={
        "text": text, "maximumResponses": limit, "type": "StreetAddress,PositionOfInterest"})
    if r.status_code != 200:
        return []
    out = [{"label": x["fulltext"], "lon": x["x"], "lat": x["y"]} for x in r.json().get("results", [])]
    return store(key, out)


async def reverse(lat: float, lon: float) -> str | None:
    """Point -> nearest address label, or None."""
    r = await client().get(f"{BASE}/reverse", params={"lat": lat, "lon": lon, "limit": 1, "index": "address"})
    if r.status_code != 200:
        return None
    feats = r.json().get("features", [])
    return feats[0]["properties"]["label"] if feats else None
