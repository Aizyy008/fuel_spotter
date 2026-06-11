import numpy as np
from django.conf import settings

from .geo_utils import cumulative_distances, downsample_route, nearest_route_distance


def _bounding_box(route_points, buffer_miles):
    buffer_degrees = buffer_miles / 45.0
    lons = route_points[:, 0]
    lats = route_points[:, 1]
    return {
        "min_lat": float(lats.min()) - buffer_degrees,
        "max_lat": float(lats.max()) + buffer_degrees,
        "min_lon": float(lons.min()) - buffer_degrees,
        "max_lon": float(lons.max()) + buffer_degrees,
    }


def _find_candidates(route_geometry, total_distance_miles, stations, search_radius):
    route_points = downsample_route(route_geometry)
    cumdist = cumulative_distances(route_points, total_distance_miles)
    bbox = _bounding_box(route_points, search_radius)

    nearby = [
        s for s in stations
        if bbox["min_lat"] <= s.latitude <= bbox["max_lat"]
        and bbox["min_lon"] <= s.longitude <= bbox["max_lon"]
    ]
    if not nearby:
        return []

    station_lats = np.array([s.latitude for s in nearby])
    station_lons = np.array([s.longitude for s in nearby])
    min_dist, position = nearest_route_distance(route_points, cumdist, station_lats, station_lons)

    candidates = [
        {"station": station, "position": float(pos), "price": float(station.retail_price)}
        for station, dist, pos in zip(nearby, min_dist, position)
        if dist <= search_radius
    ]
    candidates.sort(key=lambda c: c["position"])
    return candidates


def _cheapest_cost_path(candidates, total_distance_miles, tank_range, mpg):
    """Dijkstra/DP over candidate stops to find the minimum-cost sequence of
    fuel stops, where consecutive stops (and the start/end of the route) must
    be no more than `tank_range` miles apart.

    Each leg's fuel is "purchased" at the price of the station where that leg
    began (the vehicle always leaves a stop with a full tank). The leg from
    the route's start uses the vehicle's initial, pre-paid full tank (price 0).

    Returns (total_cost, path) where `path` is the list of candidate indices
    chosen as stops, or (None, None) if no valid sequence exists.
    """
    positions = [0.0] + [c["position"] for c in candidates] + [total_distance_miles]
    prices = [0.0] + [c["price"] for c in candidates] + [0.0]
    n = len(positions)

    inf = float("inf")
    best_cost = [inf] * n
    best_cost[0] = 0.0
    came_from = [None] * n

    for i in range(n - 1):
        if best_cost[i] == inf:
            continue
        for j in range(i + 1, n):
            leg_distance = positions[j] - positions[i]
            if leg_distance > tank_range + 1e-6:
                break
            cost = best_cost[i] + (leg_distance / mpg) * prices[i]
            if cost < best_cost[j] - 1e-9:
                best_cost[j] = cost
                came_from[j] = i

    if best_cost[n - 1] == inf:
        return None, None

    path = []
    node = n - 1
    while came_from[node] is not None:
        path.append(node)
        node = came_from[node]
    path.reverse()

    stop_indices = [node - 1 for node in path[:-1]]
    return best_cost[n - 1], stop_indices


def plan_fuel_stops(route_geometry, total_distance_miles, stations):
    """Choose cost-effective fuel stops along a route given the vehicle's range.

    `stations` must be an iterable of objects with `latitude`, `longitude` and
    `retail_price` attributes (only those with known coordinates).

    Returns a dict with `fuel_stops`, `total_fuel_cost`, `total_gallons` and
    `warnings`.
    """
    tank_range = settings.VEHICLE_RANGE_MILES
    mpg = settings.VEHICLE_MPG
    search_radius = settings.FUEL_STATION_SEARCH_RADIUS_MILES

    result = {
        "fuel_stops": [],
        "total_fuel_cost": 0.0,
        "total_gallons": round(total_distance_miles / mpg, 2),
        "warnings": [],
    }

    if total_distance_miles <= tank_range:
        return result

    if not stations:
        result["warnings"].append(
            "No fuel station data is available, so a fuel cost estimate could not be calculated."
        )
        return result

    candidates = _find_candidates(route_geometry, total_distance_miles, stations, search_radius)
    if not candidates:
        result["warnings"].append(
            "No fuel stations were found close to this route; a fuel cost estimate could not be calculated."
        )
        return result

    total_cost, stop_indices = _cheapest_cost_path(candidates, total_distance_miles, tank_range, mpg)
    if stop_indices is None:
        result["warnings"].append(
            f"No combination of nearby fuel stations keeps the vehicle within its "
            f"{tank_range}-mile range for the entire route; fuel cost could not be calculated."
        )
        return result

    fuel_stops = []
    for idx, stop_pos_idx in enumerate(stop_indices):
        stop = candidates[stop_pos_idx]
        next_position = (
            candidates[stop_indices[idx + 1]]["position"]
            if idx + 1 < len(stop_indices)
            else total_distance_miles
        )
        leg_distance = next_position - stop["position"]
        gallons = leg_distance / mpg
        cost = gallons * stop["price"]

        station = stop["station"]
        fuel_stops.append({
            "name": station.name,
            "address": station.address,
            "city": station.city,
            "state": station.state,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "price_per_gallon": stop["price"],
            "distance_from_start_miles": round(stop["position"], 1),
            "gallons_purchased": round(gallons, 2),
            "fuel_cost": round(cost, 2),
        })

    result["fuel_stops"] = fuel_stops
    result["total_fuel_cost"] = round(total_cost, 2)
    return result
