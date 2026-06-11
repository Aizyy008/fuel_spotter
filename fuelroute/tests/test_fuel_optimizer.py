import numpy as np
from django.test import SimpleTestCase

from fuelroute.models import FuelStation
from fuelroute.services.fuel_optimizer import _cheapest_cost_path, plan_fuel_stops

TANK_RANGE = 500
MPG = 10


class CheapestCostPathTests(SimpleTestCase):
    def test_no_stops_needed_within_range(self):
        cost, stops = _cheapest_cost_path([], 400, TANK_RANGE, MPG)
        self.assertEqual(cost, 0.0)
        self.assertEqual(stops, [])

    def test_picks_minimum_cost_combination(self):
        candidates = [
            {"position": 100.0, "price": 3.00},
            {"position": 400.0, "price": 2.50},
            {"position": 600.0, "price": 4.00},
            {"position": 900.0, "price": 2.00},
        ]
        cost, stops = _cheapest_cost_path(candidates, 1000.0, TANK_RANGE, MPG)
        self.assertEqual(stops, [1, 3])
        self.assertAlmostEqual(cost, 145.0)

    def test_unreachable_when_gap_exceeds_range(self):
        candidates = [
            {"position": 100.0, "price": 3.00},
            {"position": 700.0, "price": 2.00},
        ]
        cost, stops = _cheapest_cost_path(candidates, 1200.0, TANK_RANGE, MPG)
        self.assertIsNone(cost)
        self.assertIsNone(stops)


def _station_at(position_miles, price, name):
    lat = 30.0 + position_miles * (14.47467 / 1000)
    return FuelStation(
        opis_id=1,
        name=name,
        address="Test Address",
        city="Testville",
        state="TX",
        rack_id=1,
        retail_price=price,
        latitude=lat,
        longitude=-95.0,
    )


def _straight_route(num_points=1001):
    lats = np.linspace(30.0, 44.47467, num_points)
    return [[-95.0, float(lat)] for lat in lats]


class PlanFuelStopsTests(SimpleTestCase):
    def test_short_route_needs_no_fuel_stops(self):
        geometry = _straight_route()
        result = plan_fuel_stops(geometry, 400.0, [_station_at(100, 3.00, "A")])
        self.assertEqual(result["fuel_stops"], [])
        self.assertEqual(result["total_fuel_cost"], 0.0)
        self.assertEqual(result["total_gallons"], 40.0)

    def test_long_route_picks_cheapest_combination(self):
        geometry = _straight_route()
        stations = [
            _station_at(100, 3.00, "Expensive Early Stop"),
            _station_at(400, 2.50, "Good Mid Stop"),
            _station_at(600, 4.00, "Expensive Late Stop"),
            _station_at(900, 2.00, "Cheap Late Stop"),
        ]

        result = plan_fuel_stops(geometry, 1000.0, stations)

        self.assertEqual(result["warnings"], [])
        self.assertEqual(len(result["fuel_stops"]), 2)
        self.assertEqual(result["fuel_stops"][0]["name"], "Good Mid Stop")
        self.assertEqual(result["fuel_stops"][1]["name"], "Cheap Late Stop")
        self.assertAlmostEqual(result["total_fuel_cost"], 145.0, places=1)
        self.assertAlmostEqual(
            sum(s["fuel_cost"] for s in result["fuel_stops"]),
            result["total_fuel_cost"],
            places=2,
        )
        for stop in result["fuel_stops"]:
            self.assertLessEqual(stop["distance_from_start_miles"], 1000.0)

    def test_no_nearby_stations_returns_warning(self):
        geometry = _straight_route()
        far_station = FuelStation(
            opis_id=1, name="Far Away", address="x", city="x", state="TX",
            rack_id=1, retail_price=3.0, latitude=60.0, longitude=10.0,
        )
        result = plan_fuel_stops(geometry, 1000.0, [far_station])
        self.assertEqual(result["fuel_stops"], [])
        self.assertEqual(result["total_fuel_cost"], 0.0)
        self.assertTrue(result["warnings"])

    def test_gap_larger_than_range_produces_warning(self):
        geometry = _straight_route()
        stations = [
            _station_at(100, 3.00, "A"),
            _station_at(700, 2.00, "B"),
        ]
        result = plan_fuel_stops(geometry, 1200.0, stations)
        self.assertEqual(result["fuel_stops"], [])
        self.assertEqual(result["total_fuel_cost"], 0.0)
        self.assertTrue(result["warnings"])
