import hashlib

import requests
from django.conf import settings
from django.core.cache import cache


class GeocodingError(Exception):
    pass


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode_location(query):
    """Resolve a free-form US location string (city/state or full address) to (lat, lon)."""
    digest = hashlib.sha1(query.strip().lower().encode()).hexdigest()
    cache_key = f"geocode:{digest}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    response = requests.get(
        NOMINATIM_URL,
        params={
            "q": query,
            "format": "json",
            "countrycodes": "us",
            "limit": 1,
        },
        headers={"User-Agent": "spotter-fuel-route-api/1.0"},
        timeout=settings.EXTERNAL_API_TIMEOUT,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        raise GeocodingError(f"Could not find a location matching '{query}'")

    result = results[0]
    coordinates = (float(result["lat"]), float(result["lon"]))
    cache.set(cache_key, coordinates, timeout=settings.EXTERNAL_API_CACHE_TTL)
    return coordinates
