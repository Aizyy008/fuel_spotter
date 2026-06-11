from django.conf import settings

from fuelroute.models import FuelStation

from .fuel_optimizer import plan_fuel_stops
from .geo_utils import downsample_route
from .geocoding import geocode_location
from .routing import get_route

MAP_GEOMETRY_MAX_POINTS = 500


def plan_route(start_location, finish_location):
    start_lat, start_lon = geocode_location(start_location)
    finish_lat, finish_lon = geocode_location(finish_location)

    route = get_route((start_lat, start_lon), (finish_lat, finish_lon))

    stations = FuelStation.objects.filter(latitude__isnull=False, longitude__isnull=False)
    fuel_plan = plan_fuel_stops(route["geometry"], route["distance_miles"], list(stations))

    map_geometry = downsample_route(route["geometry"], max_points=MAP_GEOMETRY_MAX_POINTS)

    return {
        "start": {
            "query": start_location,
            "latitude": start_lat,
            "longitude": start_lon,
        },
        "finish": {
            "query": finish_location,
            "latitude": finish_lat,
            "longitude": finish_lon,
        },
        "distance_miles": round(route["distance_miles"], 1),
        "duration_hours": round(route["duration_hours"], 2),
        "vehicle": {
            "range_miles": settings.VEHICLE_RANGE_MILES,
            "mpg": settings.VEHICLE_MPG,
            "tank_capacity_gallons": settings.VEHICLE_RANGE_MILES / settings.VEHICLE_MPG,
        },
        "fuel_stops": fuel_plan["fuel_stops"],
        "total_fuel_cost": fuel_plan["total_fuel_cost"],
        "total_gallons": fuel_plan["total_gallons"],
        "warnings": fuel_plan["warnings"],
        "route_geometry": {
            "type": "LineString",
            "coordinates": map_geometry.tolist(),
        },
    }
