# Checks the cost model on hand-computed cases. Reads: nothing. Writes: nothing.
import pytest

from envoituresimone import cost

CURVE = [(50, 6.0), (100, 8.0)]


def test_consumption_interpolates_and_clamps():
    assert cost.consumption(CURVE, 75) == pytest.approx(7.0)
    assert cost.consumption(CURVE, 10) == 6.0
    assert cost.consumption(CURVE, 200) == 8.0


def test_route_cost():
    legs = [cost.Leg(100, 1.0), cost.Leg(50, 1.0)]          # 100 km/h -> 8 L, 50 km/h -> 3 L
    c = cost.route_cost(legs, [80.0, 10.0], CURVE, price_eur_l=2.0, wear_eur_km=0.1, toll_eur_km=0.1)
    assert c.litres == pytest.approx(11.0)
    assert c.fuel_eur == pytest.approx(22.0)
    assert c.wear_eur == pytest.approx(15.0)
    assert c.toll_eur == pytest.approx(9.0)
    assert c.total_eur == pytest.approx(46.0)
    assert len(c.warnings) == 1 and "10.0 km" in c.warnings[0]


def test_wear_off():
    c = cost.route_cost([cost.Leg(100, 1.0)], [], CURVE, 2.0, wear_eur_km=None)
    assert c.wear_eur == 0 and c.warnings == []


def test_refill_cost_round_trip():
    # 5 km each way in 0.1 h -> 10 km at 50 km/h -> 0.6 L
    r = cost.refill_cost("x", 2.0, 40, 5, 0.1, CURVE, wear_eur_km=0.1)
    assert r.fuel_bought_eur == pytest.approx(80.0)
    assert r.detour_litres == pytest.approx(0.6)
    assert r.detour_fuel_eur == pytest.approx(1.2)
    assert r.wear_eur == pytest.approx(1.0)
    assert r.total_eur == pytest.approx(82.2)
    assert r.eur_per_litre_real == pytest.approx(82.2 / 40)
