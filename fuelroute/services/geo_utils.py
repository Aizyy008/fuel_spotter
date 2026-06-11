import numpy as np

EARTH_RADIUS_MILES = 3958.7613


def haversine_miles(lat1, lon1, lat2, lon2):
    """Vectorised great-circle distance (miles) between point(s) using numpy arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def downsample_route(geometry, max_points=1500):
    """Reduce a list of [lon, lat] route coordinates to at most `max_points`.

    Always keeps the first and last point so the route's endpoints are preserved.
    """
    coords = np.asarray(geometry, dtype=float)
    if len(coords) <= max_points:
        return coords

    indices = np.linspace(0, len(coords) - 1, max_points, dtype=int)
    indices = np.unique(indices)
    return coords[indices]


def cumulative_distances(route_points, total_distance_miles=None):
    """Cumulative distance (miles) travelled along an array of [lon, lat] points.

    If `total_distance_miles` is given, the result is rescaled so the final
    value matches it exactly, correcting for the polyline's simplification error.
    """
    lons = route_points[:, 0]
    lats = route_points[:, 1]

    seg_distances = haversine_miles(lats[:-1], lons[:-1], lats[1:], lons[1:])
    cumdist = np.concatenate(([0.0], np.cumsum(seg_distances)))

    if total_distance_miles is not None and cumdist[-1] > 0:
        cumdist *= total_distance_miles / cumdist[-1]

    return cumdist


def nearest_route_distance(route_points, cumdist, station_lats, station_lons):
    """For each station, find its minimum distance to the route and its
    position (in miles from the route start) at the closest route point.

    Returns two arrays: (min_distance_miles, distance_along_route_miles).
    """
    route_lats = route_points[:, 1]
    route_lons = route_points[:, 0]

    # station_lats/lons: shape (N,). route_lats/lons: shape (M,).
    # Broadcast to (N, M) to compute distance from every station to every route point.
    dists = haversine_miles(
        station_lats[:, None], station_lons[:, None],
        route_lats[None, :], route_lons[None, :],
    )

    nearest_idx = np.argmin(dists, axis=1)
    min_dist = dists[np.arange(len(station_lats)), nearest_idx]
    position = cumdist[nearest_idx]

    return min_dist, position
