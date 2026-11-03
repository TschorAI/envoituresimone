# The web app: a JSON API over the connectors and the cost model, plus the map page.
# Reads: the connectors (live prices, geocoding, routing), static/. Writes: nothing.
from __future__ import annotations

import asyncio
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


class TripIn(Common):
    start: Point
    end: Point
    price_eur_l: float | None = None  # None: median price around the start
    toll_eur_km: float = cost.DEFAULT_TOLL_EUR_KM


class LegIn(BaseModel):
    a: Point
    b: Point


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/config")
def config():
    return {"fuels": prices.FUELS, "curves": cost.DEFAULT_CURVES,
            "wear_eur_km": cost.DEFAULT_WEAR_EUR_KM, "toll_eur_km": cost.DEFAULT_TOLL_EUR_KM,
            "short_toll_km": cost.SHORT_TOLL_KM, "routing": routing.has_key()}


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
            "routing": routing.has_key(), "notes": notes}


@app.post("/api/leg")
async def leg(q: LegIn):
    """Road geometry between two points (fastest), to draw the way to a station."""
    try:
        r = await routing.route(q.a.t(), q.b.t(), avoid_tolls=False)
    except routing.RoutingError as e:
        raise HTTPException(503, str(e))
    return {"geometry": r["geometry"]}


@app.post("/api/trip")
async def trip(q: TripIn):
    """Use case B: fastest route (tolls allowed) against the toll-free route."""
    _check_fuel(q.fuel)
    curve = q.the_curve()
    notes = []
    price = q.price_eur_l
    if price is None:
        price = await prices.median_price(q.start.lat, q.start.lon, q.fuel)
        if price is None:
            raise HTTPException(404, "Aucun prix trouvé autour du départ : saisissez-en un.")
        notes.append(f"Prix du carburant : médiane des stations autour du départ, {price:.3f} €/L.")
    try:
        fast, free = await asyncio.gather(
            routing.route(q.start.t(), q.end.t(), avoid_tolls=False),
            routing.route(q.start.t(), q.end.t(), avoid_tolls=True))
    except routing.RoutingError as e:
        raise HTTPException(503, str(e))

    out = {}
    for name, r in (("fastest", fast), ("toll_free", free)):
        c = cost.route_cost(r["legs"], r["toll_stretches_km"], curve, price, q.wear_eur_km, q.toll_eur_km)
        out[name] = {**c.to_dict(), "geometry": r["geometry"], "toll_ranges": r["toll_ranges"]}
    if out["toll_free"]["toll_km"] > 0:
        notes.append("Aucun itinéraire entièrement sans péage trouvé : l'option « sans péage » en garde une partie.")
    if out["fastest"]["toll_km"] == 0:
        notes.append("Le trajet le plus rapide n'a pas de péage : les deux options sont identiques ou proches.")
    saved = out["fastest"]["total_eur"] - out["toll_free"]["total_eur"]
    lost_h = out["toll_free"]["hours"] - out["fastest"]["hours"]
    return {**out, "price_eur_l": price, "saved_eur": round(saved, 2), "extra_hours": round(lost_h, 3),
            "eur_per_hour_lost": round(saved / lost_h, 2) if lost_h > 0.01 else None, "notes": notes}
