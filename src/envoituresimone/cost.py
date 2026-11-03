# The cost model. Pure functions, no network, no files: the same code can run in a Dataiku
# recipe or behind an n8n webhook.
# Reads: nothing. Writes: nothing.
"""Cost of a refill (use case A) and of a route (use case B).

Units: distances in km, durations in hours, speeds in km/h, consumption in L/100 km,
prices in EUR/L, money in EUR.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

# Default consumption-by-speed curves, (speed km/h, L/100 km), for an average compact car.
# Editable in the app. Shape: high in town (stops), lowest around 70-90 km/h, rising with drag.
DEFAULT_CURVES: dict[str, list[tuple[float, float]]] = {
    "e10": [(10, 11.0), (30, 8.0), (50, 6.5), (70, 5.8), (90, 5.6), (110, 6.4), (130, 7.6)],
    "gazole": [(10, 9.0), (30, 6.6), (50, 5.3), (70, 4.8), (90, 4.6), (110, 5.3), (130, 6.3)],
}
DEFAULT_WEAR_EUR_KM = 0.10
DEFAULT_TOLL_EUR_KM = 0.11
SHORT_TOLL_KM = 15.0  # a tolled stretch shorter than this gets a warning (urban tunnels, Duplex A86)


def consumption(curve: list[tuple[float, float]], speed_kmh: float) -> float:
    """L/100 km at a speed, by linear interpolation on the curve, flat beyond its ends."""
    pts = sorted((float(s), float(c)) for s, c in curve)
    if not pts:
        raise ValueError("empty consumption curve")
    if speed_kmh <= pts[0][0]:
        return pts[0][1]
    for (s0, c0), (s1, c1) in zip(pts, pts[1:]):
        if speed_kmh <= s1:
            return c0 + (c1 - c0) * (speed_kmh - s0) / (s1 - s0)
    return pts[-1][1]


@dataclass
class Leg:
    """A piece of road driven at one average speed."""
    km: float
    hours: float
    tolled: bool = False

    @property
    def speed(self) -> float:
        return self.km / self.hours if self.hours > 0 else 0.0


def fuel_litres(legs: list[Leg], curve: list[tuple[float, float]]) -> float:
    return sum(leg.km * consumption(curve, leg.speed) / 100 for leg in legs)


@dataclass
class RouteCost:
    km: float
    hours: float
    litres: float
    fuel_eur: float
    wear_eur: float
    toll_km: float
    toll_eur: float
    total_eur: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def route_cost(
    legs: list[Leg],
    toll_stretches_km: list[float],
    curve: list[tuple[float, float]],
    price_eur_l: float,
    wear_eur_km: float | None = DEFAULT_WEAR_EUR_KM,
    toll_eur_km: float = DEFAULT_TOLL_EUR_KM,
) -> RouteCost:
    """Use case B: cost of driving a route. `toll_stretches_km` lists each tolled stretch's length;
    `wear_eur_km=None` (or 0) turns wear off."""
    km = sum(leg.km for leg in legs)
    hours = sum(leg.hours for leg in legs)
    litres = fuel_litres(legs, curve)
    toll_km = sum(toll_stretches_km)
    wear = km * (wear_eur_km or 0.0)
    toll = toll_km * toll_eur_km
    fuel = litres * price_eur_l
    warnings = []
    short = [s for s in toll_stretches_km if 0 < s < SHORT_TOLL_KM]
    if short:
        warnings.append(
            f"{len(short)} short tolled stretch(es) ({', '.join(f'{s:.1f} km' for s in short)}): "
            f"the {toll_eur_km:.2f} EUR/km estimate can be far off there "
            "(urban tunnels such as the Duplex A86 cost several EUR for about 10 km)."
        )
    return RouteCost(km, hours, litres, fuel, wear, toll_km, toll, fuel + wear + toll, warnings)


@dataclass
class RefillCost:
    station_id: str
    price_eur_l: float
    litres_bought: float
    one_way_km: float
    one_way_hours: float
    fuel_bought_eur: float
    detour_litres: float
    detour_fuel_eur: float
    wear_eur: float
    total_eur: float
    eur_per_litre_real: float  # total paid per litre bought, trip included

    def to_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def refill_cost(
    station_id: str,
    price_eur_l: float,
    litres: float,
    one_way_km: float,
    one_way_hours: float,
    curve: list[tuple[float, float]],
    wear_eur_km: float | None = DEFAULT_WEAR_EUR_KM,
) -> RefillCost:
    """Use case A: fill `litres` at a station, counting the round trip from home.
    The round trip is twice the one-way route. The fuel burnt on the way is priced at the
    station's price, since it is bought back there."""
    trip = [Leg(2 * one_way_km, 2 * one_way_hours)]
    detour_l = fuel_litres(trip, curve)
    bought = litres * price_eur_l
    detour_eur = detour_l * price_eur_l
    wear = 2 * one_way_km * (wear_eur_km or 0.0)
    total = bought + detour_eur + wear
    return RefillCost(station_id, price_eur_l, litres, one_way_km, one_way_hours, bought,
                      detour_l, detour_eur, wear, total, total / litres if litres else 0.0)
