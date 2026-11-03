# The web app: a JSON API over the connectors and the cost model, plus the map page.
# Reads: the connectors (prices, geocoding, routing), static/. Writes: <DATA_DIR>/prices/, through
# the hourly snapshot task (off with PRICE_REFRESH=0).
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import cost, snapshot
from .connectors import geocode, prices, routing

STATIC = Path(__file__).resolve().parent / "static"
# Feature flag: the refill ranking (use case A) is off unless ENABLE_REFILL=1. Off, the public
# site shows only the price map, and the endpoints that spend the OpenRouteService quota answer 404.
REFILL_ON = os.environ.get("ENABLE_REFILL", "0") == "1"
# Visitor counting: GoatCounter (no cookies, no personal data), only if GOATCOUNTER_CODE is set.
GOATCOUNTER_CODE = os.environ.get("GOATCOUNTER_CODE", "").strip()


@asynccontextmanager
async def lifespan(_app):
    """Hourly price snapshot in the background, unless PRICE_REFRESH=0."""
    task = asyncio.create_task(snapshot.refresh_loop()) if os.environ.get("PRICE_REFRESH", "1") != "0" else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="envoituresimone", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=2000)
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


@app.get("/", response_class=HTMLResponse)
def index():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    if GOATCOUNTER_CODE:
        tag = (f'<script data-goatcounter="https://{GOATCOUNTER_CODE}.goatcounter.com/count" '
               'async src="//gc.zgo.at/count.js"></script>')
        html = html.replace("</body>", f"{tag}\n</body>")
    return html


def _refill_on():
    if not REFILL_ON:
        raise HTTPException(404, "Fonction pas encore disponible.")


@app.get("/api/config")
def config():
    return {"fuels": prices.FUELS, "curves": cost.DEFAULT_CURVES,
            "wear_eur_km": cost.DEFAULT_WEAR_EUR_KM, "routing": routing.has_key(),
            "features": {"refill": REFILL_ON}}


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
    _refill_on()
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


@app.get("/api/price-map")
def price_map(fuel: str = "e10", max_price_age_days: float = 7):
    """Use case C: every station's price, for the national map. Columnar to keep it small."""
    _check_fuel(fuel)
    df = prices.all_stations(fuel)
    if df is None:
        raise HTTPException(503, "Le relevé des prix n'est pas encore prêt : réessayez dans une minute.")
    cutoff = datetime.now() - timedelta(days=max_price_age_days)
    fresh = df[df["updated"] >= cutoff]
    q = fresh["price"].quantile([0.05, 0.5, 0.95])
    return {
        "fuel": fuel, "at": df["fetched_at"].iloc[0].isoformat(timespec="minutes"),
        "count": len(fresh), "stale_excluded": len(df) - len(fresh), "max_price_age_days": max_price_age_days,
        "stats": {"min": float(fresh["price"].min()), "p05": float(q[0.05]), "median": float(q[0.5]),
                  "p95": float(q[0.95]), "max": float(fresh["price"].max())},
        "stations": {
            "id": fresh["id"].tolist(), "lat": fresh["lat"].round(5).tolist(), "lon": fresh["lon"].round(5).tolist(),
            "price": fresh["price"].tolist(), "address": fresh["address"].tolist(), "city": fresh["city"].tolist(),
            "updated": fresh["updated"].dt.strftime("%Y-%m-%dT%H:%M").tolist(),
        },
    }


@app.post("/api/leg")
async def leg(q: LegIn):
    """Road geometry between two points (fastest), to draw the way to a station."""
    _refill_on()
    try:
        r = await routing.route(q.a.t(), q.b.t(), avoid_tolls=False)
    except routing.RoutingError as e:
        raise HTTPException(503, str(e))
    return {"geometry": r["geometry"]}
