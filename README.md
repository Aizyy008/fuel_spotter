# Fuel-Optimal Route Planner API

A Django REST API that plans a driving route between two locations in the USA,
finds the most cost-effective fuel stops along the way (given a 500-mile
vehicle range and 10 MPG fuel economy), and returns the total estimated fuel
cost for the trip.

## Tech stack

- **Django 6.0** + **Django REST Framework**
- **SQLite** for storing the ~7,500 US fuel stations from
  `fuel-prices-for-be-assessment.csv` (with geocoded coordinates)
- **NumPy** for fast, vectorised geo-distance calculations
- Free, key-free external APIs:
  - **[OSRM](https://project-osrm.org/)** (`router.project-osrm.org`) for
    driving directions/route geometry — **1 call per request**
  - **[Nominatim](https://nominatim.org/)** (OpenStreetMap) for geocoding the
    start/finish locations — **2 calls per request**

  That's a maximum of **3 external API calls per request**, all of which are
  cached (24h) so repeat requests for the same locations make **0** calls.

## Setup

```bash
source venv/bin/activate          # venv already has Django, DRF, requests, numpy
pip install -r requirements.txt   # no-op if already installed

python manage.py migrate
python manage.py load_fuel_stations   # one-time: loads + geocodes the CSV into SQLite
python manage.py runserver
```

The `load_fuel_stations` command reads
`fuel-prices-for-be-assessment.csv` and attaches latitude/longitude to each
station using a bundled offline lookup table
(`fuelroute/data/city_state_geocode.json`, built from US Census Gazetteer
data + a one-time Nominatim pass). No network access is needed at load time,
and it loads all 8,151 rows (7,531 US stations get coordinates; the
remaining rows are Canadian truck stops, which are out of scope and stored
without coordinates).

## API

### `POST /api/route/`

**Request body**

```json
{
  "start_location": "Chicago, IL",
  "finish_location": "Joplin, MO"
}
```

Locations can be a city/state (`"Chicago, IL"`) or a full street address.

**Response**

```json
{
  "start": {
    "query": "Chicago, IL",
    "latitude": 41.8755616,
    "longitude": -87.6244212
  },
  "finish": {
    "query": "Joplin, MO",
    "latitude": 37.0841838,
    "longitude": -94.5133385
  },
  "distance_miles": 579.6,
  "duration_hours": 10.89,
  "vehicle": {
    "range_miles": 500,
    "mpg": 10,
    "tank_capacity_gallons": 50.0
  },
  "fuel_stops": [
    {
      "name": "One9 #1318",
      "address": "I-44, Exit 88",
      "city": "Strafford",
      "state": "MO",
      "latitude": 37.268882,
      "longitude": -93.118041,
      "price_per_gallon": 2.986,
      "distance_from_start_miles": 498.3,
      "gallons_purchased": 1.03,
      "fuel_cost": 3.08
    },
    {
      "name": "RAPID ROBERTS #123",
      "address": "I-44, EXIT 80",
      "city": "Springfield",
      "state": "MO",
      "latitude": 37.194157,
      "longitude": -93.292642,
      "price_per_gallon": 2.899,
      "distance_from_start_miles": 508.6,
      "gallons_purchased": 7.1,
      "fuel_cost": 20.59
    }
  ],
  "total_fuel_cost": 23.67,
  "total_gallons": 57.96,
  "warnings": [],
  "route_geometry": {
    "type": "LineString",
    "coordinates": [[-87.624351, 41.875563], [-87.626849, 41.874399], "..."]
  }
}
```

`route_geometry` is a GeoJSON `LineString` (downsampled to ~500 points) that
can be dropped straight into Leaflet/Mapbox/Google Maps to draw the route.

### `GET /api/route/map/?start_location=...&finish_location=...`

A small HTML page (Leaflet + OpenStreetMap tiles) that visualises the route,
start/finish points and fuel stops on an interactive map. Useful for demos —
open it directly in a browser.

## Fuel stop algorithm

1. The route's geometry (returned by OSRM) is used to compute the cumulative
   distance travelled at every point along the route.
2. Every fuel station within 5 miles of the route is treated as a candidate
   stop, and assigned its position (in miles from the start) along the route.
3. The vehicle is assumed to start with a full tank (500-mile range, free).
   Choosing the cheapest-cost sequence of stops — where consecutive stops
   (and the start/end of the trip) are never more than 500 miles apart — is a
   shortest-path problem: each candidate stop is a node, an edge connects two
   stops that are within 500 miles of each other, and the edge's cost is the
   fuel consumed for that leg priced at the price of the stop where the leg
   began (the first leg is "free", since it runs on the initial full tank).
   This is solved with an O(N²) DP over the (typically tens to ~100)
   candidate stops near the route — fast and provably minimal-cost given the
   range constraint.
4. `total_fuel_cost` is the sum of each leg's cost; `total_gallons` is simply
   `distance_miles / mpg`.

If the route is 500 miles or shorter, no fuel stop is needed and
`total_fuel_cost` is `0`. If no combination of nearby stations can keep the
vehicle within its range for the whole trip, the `warnings` list explains why
and `fuel_stops` is left empty.

## Performance

- Both geocoding (Nominatim) and routing (OSRM) results are cached for 24h,
  so repeat requests for the same locations are served from cache in
  milliseconds.
- The fuel-station lookup uses a bounding-box pre-filter plus vectorised
  NumPy haversine distance calculations against a downsampled route polyline,
  so scanning ~7,500 stations takes a few milliseconds.
- A first-time (uncached) request typically completes in 2-7 seconds,
  dominated entirely by the two Nominatim calls and the one OSRM call.

## Tests

```bash
python manage.py test fuelroute
```

Covers the geo-distance utilities, the fuel-stop optimizer (including the DP
correctness and edge cases like short routes, unreachable routes, and no
nearby stations), the geocoding/routing service wrappers (mocked HTTP), and
the API endpoints.

## Project layout

```
fuelroute/
  models.py              # FuelStation model
  serializers.py         # request validation
  views.py                # POST /api/route/ and the map demo view
  services/
    geocoding.py          # Nominatim geocoding (cached)
    routing.py             # OSRM routing (cached)
    geo_utils.py           # haversine, downsampling, cumulative distance
    fuel_optimizer.py       # DP-based cheapest fuel-stop selection
    route_planner.py        # orchestrates the above into one API response
  management/commands/
    load_fuel_stations.py  # loads + geocodes the CSV into the DB
  data/
    city_state_geocode.json  # offline city/state -> lat/lon lookup table
  templates/fuelroute/map.html
  tests/
```
