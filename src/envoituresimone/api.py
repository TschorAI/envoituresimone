# The web app: a JSON API over the connectors and the cost model, plus the map page.
# Reads: the connectors (live prices, geocoding, routing), static/. Writes: nothing.
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import cost
from .connectors import geocode, prices, routing

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="envoituresimone")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class Point(BaseModel):
    lat: float
    lon: float

    def t(self) -> tuple[float, float]:
        return (self.lat, self.lon)


class Common(BaseModel):
    fuel: str = "e10"
    curve: list[tuple[float, float]] | None = None     # None: the fuel's default curve
    wear_eur_km: float | None = cost.DEFAULT_WEAR_EUR_KM  # None or 0: wear off

    def the_curve(self):
        return self.curve or cost.DEFAULT_CURVES[self.fuel]


class RefillIn(Common):
    home: Point
    litres: float = Field(40, gt=0, le=200)
    radius_km: float = Field(10, gt=0, le=50)
    max_routed: int = Field(25, ge=1, le=50)
    max_price_age_days: float = Field(7, gt=0)  # older prices are left out


class LegIn(BaseModel):
    a: Point
    b: Point


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/config")
def config():
    return {"fuels": prices.FUELS, "curves": cost.DEFAULT_CURVES,
            "wear_eur_km": cost.DEFAULT_WEAR_EUR_KM, "routing": routing.has_key()}


@app.get("/api/complete")
async def complete(q: str):
    return await geocode.complete(q)


@app.get("/api/geocode")
async def geocode_(q: str):
    return await geocode.search(q)


@app.get("/api/reverse")
async def reverse(lat: float, lon: float):
    return {"label": await geocode.reverse(lat, lon)}


def _check_fuel(fuel: str):
    if fuel not in prices.FUELS:
        raise HTTPException(400, f"fuel must be one of {list(prices.FUELS)}")


@app.post("/api/refill")
async def refill(q: RefillIn):
    """Use case A: rank the stations around home by the real cost of the refill."""
    _check_fuel(q.fuel)
    curve = q.the_curve()
    stations = await prices.stations_near(q.home.lat, q.home.lon, q.radius_km, q.fuel)
    cutoff = datetime.now() - timedelta(days=q.max_price_age_days)
    fresh = [s for s in stations if s["updated"] and datetime.fromisoformat(s["updated"]) >= cutoff]
    stale = len(stations) - len(fresh)
    stations = fresh
    if not stations:
        return {"stations": [], "found": 0, "routing": routing.has_key(), "notes": [
            f"Aucune station ne vend du {prices.FUELS[q.fuel]} à moins de {q.radius_km:g} km."]}

    # Pre-rank on a crow-fly estimate, then route only the best candidates (API quota).
    def rough(s):
        km = routing.haversine_km(q.home.lat, q.home.lon, s["lat"], s["lon"]) * routing.DETOUR_FACTOR
        return cost.refill_cost(s["id"], s["price"], q.litres, km, km / routing.FALLBACK_KMH,
                                curve, q.wear_eur_km).total_eur
    candidates = sorted(stations, key=rough)[: q.max_routed]
    notes = []
    if stale:
        notes.append(f"{stale} station(s) écartée(s) : prix non mis à jour depuis plus de "
                     f"{q.max_price_age_days:g} jours.")
    try:
        dist = await routing.one_to_many(q.home.t(), [(s["lat"], s["lon"]) for s in candidates])
    except routing.RoutingError as e:
        notes.append(f"{e} Distances à vol d'oiseau x {routing.DETOUR_FACTOR}.")
        dist = [{"km": routing.haversine_km(q.home.lat, q.home.lon, s["lat"], s["lon"]) * routing.DETOUR_FACTOR,
                 "hours": 0, "estimated": True} for s in candidates]
        for d in dist:
            d["hours"] = d["km"] / routing.FALLBACK_KMH
    if not routing.has_key():
        notes.append(f"Pas de clé ORS_API_KEY : distances à vol d'oiseau x {routing.DETOUR_FACTOR}, "
                     f"à {routing.FALLBACK_KMH:.0f} km/h.")

    ranked = []
    for s, d in zip(candidates, dist):
        c = cost.refill_cost(s["id"], s["price"], q.litres, d["km"], d["hours"], curve, q.wear_eur_km)
        ranked.append({**s, **c.to_dict(), "estimated": d["estimated"]})
    ranked.sort(key=lambda r: r["total_eur"])
    cheapest_pump = min(ranked, key=lambda r: r["price"])
    best = ranked[0]
    if cheapest_pump["id"] != best["id"]:
        notes.append(
            f"La pompe la moins chère ({cheapest_pump['price']:.3f} €/L, {cheapest_pump['city']}) n'est pas "
            f"le plein le moins cher : le trajet coûte plus qu'il ne fait gagner "
            f"({cheapest_pump['total_eur'] - best['total_eur']:.2f} € de plus).")
    return {"stations": ranked, "found": len(stations), "routed": len(candidates),
            "best_id": best["id"], "cheapest_pump_id": cheapest_pump["id"],
            "routing": routing.has_key(), "prices": prices.source(), "notes": notes}


@app.post("/api/leg")
async def leg(q: LegIn):
    """Road geometry between two points (fastest), to draw the way to a station."""
    try:
        r = await routing.route(q.a.t(), q.b.t(), avoid_tolls=False)
    except routing.RoutingError as e:
        raise HTTPException(503, str(e))
    return {"geometry": r["geometry"]}
