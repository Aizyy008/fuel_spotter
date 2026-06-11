import numpy as np
from django.test import SimpleTestCase

from fuelroute.services.geo_utils import (
    cumulative_distances,
    downsample_route,
    haversine_miles,
)


class HaversineMilesTests(SimpleTestCase):
    def test_zero_distance_for_identical_points(self):
        self.assertAlmostEqual(haversine_miles(40.0, -90.0, 40.0, -90.0), 0.0)

    def test_one_degree_of_longitude_at_equator(self):
        distance = haversine_miles(0.0, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(distance, 69.0954, places=2)

    def test_one_degree_of_latitude(self):
        distance = haversine_miles(30.0, -95.0, 31.0, -95.0)
        self.assertAlmostEqual(distance, 69.0954, places=2)


class DownsampleRouteTests(SimpleTestCase):
    def test_keeps_short_routes_unchanged(self):
        geometry = [[-95.0, 30.0], [-95.0, 31.0], [-95.0, 32.0]]
        result = downsample_route(geometry, max_points=10)
        self.assertEqual(len(result), 3)

    def test_downsamples_long_routes_keeping_endpoints(self):
        geometry = [[-95.0, 30.0 + i * 0.01] for i in range(2000)]
        result = downsample_route(geometry, max_points=500)
        self.assertLessEqual(len(result), 500)
        self.assertTrue(np.array_equal(result[0], geometry[0]))
        self.assertTrue(np.array_equal(result[-1], geometry[-1]))


class CumulativeDistancesTests(SimpleTestCase):
    def test_cumulative_distances_along_meridian(self):
        route_points = np.array([[-95.0, 30.0], [-95.0, 31.0], [-95.0, 32.0]])
        cumdist = cumulative_distances(route_points)
        self.assertAlmostEqual(cumdist[0], 0.0)
        self.assertAlmostEqual(cumdist[1], 69.0954, places=2)
        self.assertAlmostEqual(cumdist[2], 138.1908, places=2)

    def test_rescales_to_match_total_distance(self):
        route_points = np.array([[-95.0, 30.0], [-95.0, 31.0], [-95.0, 32.0]])
        cumdist = cumulative_distances(route_points, total_distance_miles=200.0)
        self.assertAlmostEqual(cumdist[-1], 200.0)
        self.assertAlmostEqual(cumdist[1], 100.0)
