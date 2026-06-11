import csv
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from fuelroute.models import FuelStation

DEFAULT_CSV_PATH = settings.BASE_DIR / "fuel-prices-for-be-assessment.csv"
GEOCODE_LOOKUP_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "city_state_geocode.json"


class Command(BaseCommand):
    help = "Load fuel station prices from the assessment CSV, attaching coordinates from the bundled city/state geocode lookup."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-path",
            default=str(DEFAULT_CSV_PATH),
            help="Path to the fuel prices CSV file.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        with open(GEOCODE_LOOKUP_PATH) as f:
            geocode_lookup = json.load(f)

        stations = []
        skipped = 0
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                city = row["City"].strip()
                state = row["State"].strip()
                coords = geocode_lookup.get(f"{city}|{state}")
                if coords is None:
                    skipped += 1
                    latitude = longitude = None
                else:
                    latitude, longitude = coords

                stations.append(FuelStation(
                    opis_id=int(row["OPIS Truckstop ID"]),
                    name=row["Truckstop Name"].strip(),
                    address=row["Address"].strip(),
                    city=city,
                    state=state,
                    rack_id=int(row["Rack ID"]),
                    retail_price=row["Retail Price"],
                    latitude=latitude,
                    longitude=longitude,
                ))

        FuelStation.objects.all().delete()
        FuelStation.objects.bulk_create(stations, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(stations)} fuel stations ({skipped} without coordinates)."
        ))
