from unittest.mock import patch

import numpy as np
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from fuelroute.models import FuelStation
from fuelroute.services.geocoding import GeocodingError
from fuelroute.services.routing import RoutingError


def _straight_route_geometry(num_points=1001):
    lats = np.linspace(30.0, 44.47467, num_points)
    return [[-95.0, float(lat)] for lat in lats]


class RoutePlanViewTests(TestCase):
    def setUp(self):
        cache.clear()
        FuelStation.objects.create(
            opis_id=1, name="Cheap Stop", address="Addr", city="Testville", state="TX",
            rack_id=1, retail_price="2.50",
            latitude=30.0 + 400 * (14.47467 / 1000), longitude=-95.0,
        )
        FuelStation.objects.create(
            opis_id=2, name="Pricey Stop", address="Addr", city="Otherville", state="OK",
            rack_id=1, retail_price="3.50",
            latitude=30.0 + 800 * (14.47467 / 1000), longitude=-95.0,
        )

    def _mock_route(self, distance_miles):
        return {
            "distance_miles": distance_miles,
            "duration_hours": distance_miles / 60,
            "geometry": _straight_route_geometry(),
        }

    @patch("fuelroute.services.route_planner.get_route")
    @patch("fuelroute.services.route_planner.geocode_location")
    def test_returns_route_with_fuel_stops(self, mock_geocode, mock_get_route):
        mock_geocode.side_effect = [(30.0, -95.0), (44.47467, -95.0)]
        mock_get_route.return_value = self._mock_route(1000.0)

        response = self.client.post(
            reverse("fuelroute:route-plan"),
            data={"start_location": "A, TX", "finish_location": "B, OK"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["distance_miles"], 1000.0)
        self.assertEqual(data["vehicle"]["range_miles"], 500)
        self.assertEqual(data["vehicle"]["mpg"], 10)
        self.assertEqual(len(data["fuel_stops"]), 2)
        self.assertEqual(data["fuel_stops"][0]["name"], "Cheap Stop")
        self.assertGreater(data["total_fuel_cost"], 0)
        self.assertIn("route_geometry", data)
        self.assertEqual(data["route_geometry"]["type"], "LineString")

    @patch("fuelroute.services.route_planner.get_route")
    @patch("fuelroute.services.route_planner.geocode_location")
    def test_short_route_has_no_fuel_stops(self, mock_geocode, mock_get_route):
        mock_geocode.side_effect = [(30.0, -95.0), (31.0, -95.0)]
        mock_get_route.return_value = self._mock_route(100.0)

        response = self.client.post(
            reverse("fuelroute:route-plan"),
            data={"start_location": "A, TX", "finish_location": "B, TX"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["fuel_stops"], [])
        self.assertEqual(data["total_fuel_cost"], 0.0)

    def test_missing_fields_returns_400(self):
        response = self.client.post(
            reverse("fuelroute:route-plan"),
            data={"start_location": "A, TX"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("fuelroute.services.route_planner.geocode_location")
    def test_geocoding_error_returns_400(self, mock_geocode):
        mock_geocode.side_effect = GeocodingError("Could not find a location matching 'Nowhere'")

        response = self.client.post(
            reverse("fuelroute:route-plan"),
            data={"start_location": "Nowhere", "finish_location": "B, TX"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    @patch("fuelroute.services.route_planner.get_route")
    @patch("fuelroute.services.route_planner.geocode_location")
    def test_routing_error_returns_502(self, mock_geocode, mock_get_route):
        mock_geocode.side_effect = [(30.0, -95.0), (44.47467, -95.0)]
        mock_get_route.side_effect = RoutingError("No route could be found")

        response = self.client.post(
            reverse("fuelroute:route-plan"),
            data={"start_location": "A, TX", "finish_location": "B, OK"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 502)
        self.assertIn("error", response.json())

    def test_get_method_not_allowed(self):
        response = self.client.get(reverse("fuelroute:route-plan"))
        self.assertEqual(response.status_code, 405)


class RouteMapViewTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_renders_form_without_params(self):
        response = self.client.get(reverse("fuelroute:route-map"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plan route")

    @patch("fuelroute.services.route_planner.get_route")
    @patch("fuelroute.services.route_planner.geocode_location")
    def test_renders_map_with_results(self, mock_geocode, mock_get_route):
        mock_geocode.side_effect = [(30.0, -95.0), (44.47467, -95.0)]
        mock_get_route.return_value = {
            "distance_miles": 1000.0,
            "duration_hours": 16.7,
            "geometry": _straight_route_geometry(),
        }

        response = self.client.get(
            reverse("fuelroute:route-map"),
            {"start_location": "A, TX", "finish_location": "B, OK"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "L.polyline")
