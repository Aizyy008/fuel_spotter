from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import TestCase

from fuelroute.services.geocoding import GeocodingError, geocode_location
from fuelroute.services.routing import RoutingError, get_route


class GeocodeLocationTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("fuelroute.services.geocoding.requests.get")
    def test_returns_coordinates_from_first_result(self, mock_get):
        mock_get.return_value.json.return_value = [{"lat": "41.8781", "lon": "-87.6298"}]
        mock_get.return_value.raise_for_status.return_value = None

        result = geocode_location("Chicago, IL")

        self.assertEqual(result, (41.8781, -87.6298))
        mock_get.assert_called_once()

    @patch("fuelroute.services.geocoding.requests.get")
    def test_caches_results(self, mock_get):
        mock_get.return_value.json.return_value = [{"lat": "41.8781", "lon": "-87.6298"}]
        mock_get.return_value.raise_for_status.return_value = None

        geocode_location("Chicago, IL")
        geocode_location("Chicago, IL")

        self.assertEqual(mock_get.call_count, 1)

    @patch("fuelroute.services.geocoding.requests.get")
    def test_raises_when_no_results(self, mock_get):
        mock_get.return_value.json.return_value = []
        mock_get.return_value.raise_for_status.return_value = None

        with self.assertRaises(GeocodingError):
            geocode_location("Nowhereville, ZZ")


class GetRouteTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("fuelroute.services.routing.requests.get")
    def test_returns_distance_duration_and_geometry(self, mock_get):
        mock_get.return_value.json.return_value = {
            "code": "Ok",
            "routes": [{
                "distance": 1609.344,
                "duration": 3600,
                "geometry": {"coordinates": [[-87.6, 41.8], [-87.5, 41.9]]},
            }],
        }
        mock_get.return_value.raise_for_status.return_value = None

        result = get_route((41.8, -87.6), (41.9, -87.5))

        self.assertAlmostEqual(result["distance_miles"], 1.0)
        self.assertAlmostEqual(result["duration_hours"], 1.0)
        self.assertEqual(result["geometry"], [[-87.6, 41.8], [-87.5, 41.9]])

    @patch("fuelroute.services.routing.requests.get")
    def test_caches_results(self, mock_get):
        mock_get.return_value.json.return_value = {
            "code": "Ok",
            "routes": [{
                "distance": 1609.344,
                "duration": 3600,
                "geometry": {"coordinates": [[-87.6, 41.8], [-87.5, 41.9]]},
            }],
        }
        mock_get.return_value.raise_for_status.return_value = None

        get_route((41.8, -87.6), (41.9, -87.5))
        get_route((41.8, -87.6), (41.9, -87.5))

        self.assertEqual(mock_get.call_count, 1)

    @patch("fuelroute.services.routing.requests.get")
    def test_raises_routing_error_when_no_route_found(self, mock_get):
        mock_get.return_value.json.return_value = {"code": "NoRoute", "message": "Could not route"}
        mock_get.return_value.raise_for_status.return_value = None

        with self.assertRaises(RoutingError):
            get_route((0.0, 0.0), (50.0, 50.0))
