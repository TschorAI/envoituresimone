# OpenRouteService routing on OpenStreetMap: directions (with or without tollways) and a
# one-to-many distance matrix. Needs ORS_API_KEY in .env (free key at openrouteservice.org).
# Free plan: 2000 directions and 500 matrix calls a day, 40 a minute.
# Reads: https://api.openrouteservice.org, .env. Writes: nothing.
from __future__ import annotations

import math
import os
from pathlib import Path

from dotenv import load_dotenv

from ..cost import Leg
from ._http import cached, client, store

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
BASE = "https://api.openrouteservice.org/v2"
DETOUR_FACTOR = 1.3     # road km per crow-fly km, used only without a key
FALLBACK_KMH = 40.0     # town speed, used only without a key


class RoutingError(RuntimeError):
    pass


def has_key() -> bool:
    return bool(os.environ.get("ORS_API_KEY"))


def _headers() -> dict:
    if not has_key():
        raise RoutingError("ORS_API_KEY is missing in .env: routing is off.")
    return {"Authorization": os.environ["ORS_API_KEY"], "Content-Type": "application/json"}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


async def _post(path: str, body: dict) -> dict:
    r = await client().post(f"{BASE}/{path}", json=body, headers=_headers())
    if r.status_code != 200:
        try:
            msg = r.json().get("error", r.text)
            msg = msg.get("message", msg) if isinstance(msg, dict) else msg
        except ValueError:
            msg = r.text
        raise RoutingError(f"OpenRouteService {r.status_code}: {msg}")
    return r.json()


async def route(a: tuple[float, float], b: tuple[float, float], avoid_tolls: bool) -> dict:
    """Route from a to b, points as (lat, lon). Returns
    {geometry: [[lat, lon], ...], legs: [Leg], toll_ranges: [[i, j]], toll_stretches_km: [km]}.
    Leg speeds come from the route's steps; tolled parts from ORS's `tollways` extra."""
    key = f"route:{a}:{b}:{avoid_tolls}"
    if (hit := cached(key, 3600)) is not None:
        return hit
    body = {"coordinates": [[a[1], a[0]], [b[1], b[0]]], "extra_info": ["tollways"],
            "instructions": True, "units": "m"}
    if avoid_tolls:
        body["options"] = {"avoid_features": ["tollways"]}
    feat = (await _post("directions/driving-car/geojson", body))["features"][0]
    coords = feat["geometry"]["coordinates"]
    geometry = [[c[1], c[0]] for c in coords]
    seg_km = [haversine_km(*geometry[i], *geometry[i + 1]) for i in range(len(geometry) - 1)]

    toll_ranges = [[v[0], v[1]] for v in feat["properties"].get("extras", {})
                   .get("tollways", {}).get("values", []) if v[2] == 1]
    tolled_pts = set()
    for i, j in toll_ranges:
        tolled_pts.update(range(i, j))  # segment k goes from point k to point k+1
    # merge touching ranges into stretches
    stretches, cur = [], 0.0
    for k, d in enumerate(seg_km):
        if k in tolled_pts:
            cur += d
        elif cur:
            stretches.append(cur); cur = 0.0
    if cur:
        stretches.append(cur)

    legs = []
    for seg in feat["properties"]["segments"]:
        for st in seg.get("steps", []):
            km, h = st["distance"] / 1000, st["duration"] / 3600
            if km <= 0:
                continue
            i, j = st["way_points"]
            tolled_share = sum(seg_km[k] for k in range(i, j) if k in tolled_pts)
            legs.append(Leg(km, h, tolled=tolled_share > 0.5 * sum(seg_km[i:j] or [0])))
    out = {"geometry": geometry, "legs": legs, "toll_ranges": toll_ranges,
           "toll_stretches_km": stretches}
    return store(key, out)


async def one_to_many(origin: tuple[float, float], dests: list[tuple[float, float]]) -> list[dict]:
    """Road distance and time from origin to each destination: [{km, hours, estimated}].
    Without a key, or if a destination is unreachable, falls back on a crow-fly estimate."""
    def estimate(d):
        km = haversine_km(*origin, *d) * DETOUR_FACTOR
        return {"km": km, "hours": km / FALLBACK_KMH, "estimated": True}

    if not dests:
        return []
    if not has_key():
        return [estimate(d) for d in dests]
    body = {"locations": [[origin[1], origin[0]]] + [[d[1], d[0]] for d in dests],
            "sources": [0], "destinations": list(range(1, len(dests) + 1)),
            "metrics": ["distance", "duration"], "units": "km"}
    res = await _post("matrix/driving-car", body)
    out = []
    for d, km, s in zip(dests, res["distances"][0], res["durations"][0]):
        out.append({"km": km, "hours": s / 3600, "estimated": False} if km is not None and s else estimate(d))
    return out
