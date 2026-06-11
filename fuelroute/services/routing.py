import requests
from django.conf import settings
from django.core.cache import cache


class RoutingError(Exception):
    pass


def get_route(start, finish):
    """Fetch a driving route between two (lat, lon) points from the OSRM routing API.

    Returns a dict with `distance_miles`, `duration_hours` and `geometry`
    (a list of [lon, lat] coordinate pairs describing the route path).
    """
    cache_key = (
        f"osrm-route:{start[0]:.4f},{start[1]:.4f}:{finish[0]:.4f},{finish[1]:.4f}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    coordinates = f"{start[1]},{start[0]};{finish[1]},{finish[0]}"
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{coordinates}"

    response = requests.get(
        url,
        params={"overview": "full", "geometries": "geojson"},
        timeout=settings.EXTERNAL_API_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError(data.get("message", "No route could be found between the given locations"))

    route = data["routes"][0]
    result = {
        "distance_miles": route["distance"] / 1609.344,
        "duration_hours": route["duration"] / 3600,
        "geometry": route["geometry"]["coordinates"],
    }
    cache.set(cache_key, result, timeout=settings.EXTERNAL_API_CACHE_TTL)
    return result
