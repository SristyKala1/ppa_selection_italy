"""
download_era5.py

Downloads ERA5 hourly weather timeseries (1991-2023) from the Copernicus
Climate Data Store, using the point-location Timeseries API.

One request per city covers the full 33-year range. Responses always come
back as a zip (confirmed via test request, 2026-08-04 — the API ignores
download_format and defaults to zip regardless), so each city's download
is unzipped and the extracted file renamed to the canonical path.
"""

from pathlib import Path
import tempfile
import time
import zipfile

import cdsapi
import yaml

# Check CDS credentials

cds_key = Path.home() / ".cdsapirc"

if not cds_key.exists():
    raise FileNotFoundError(
        "CDS API credentials not found.\n"
        "Create ~/.cdsapirc before running this script."
    )



# Read configuration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
config_path = PROJECT_ROOT / "config.yaml"

with open(config_path, "r") as file:
    config = yaml.safe_load(file)

ZONES = config["zones"]
START_YEAR = config["weather"]["start_year"]
END_YEAR = config["weather"]["end_year"]
DATE_RANGE = f"{START_YEAR}-01-01/{END_YEAR}-12-31"


# Output folder

RAW_WEATHER_DIR = PROJECT_ROOT / "data" / "raw" / "weather"
RAW_WEATHER_DIR.mkdir(parents=True, exist_ok=True)


# Download function (single city, with retry + unzip)

VARIABLES = [
    "2m_temperature",
    "surface_solar_radiation_downwards",
    "total_sky_direct_solar_radiation_at_surface",
    "surface_pressure",
    "100m_u_component_of_wind",
    "100m_v_component_of_wind",
]

MAX_RETRIES = 3
RETRY_PAUSE_SECONDS = 30


def download_city(client, zone_name, city_name, lat, lon):
    final_output = RAW_WEATHER_DIR / f"era5_{zone_name}_{city_name}.nc"

    if final_output.exists():
        print(f"  Skipping {zone_name}/{city_name} (already downloaded)")
        return True

    zip_path = RAW_WEATHER_DIR / f"_tmp_{zone_name}_{city_name}.zip"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client.retrieve(
                "reanalysis-era5-single-levels-timeseries",
                {
                    "variable": VARIABLES,
                    "location": {"latitude": lat, "longitude": lon},
                    "date": [DATE_RANGE],
                    "data_format": "netcdf",
                },
                str(zip_path),
            )

            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(tmp_dir)

                extracted_nc = next(Path(tmp_dir).glob("*.nc"))
                extracted_nc.rename(final_output)

            zip_path.unlink()
            return True

        except Exception as exc:
            print(f"  Attempt {attempt}/{MAX_RETRIES} failed for "
                  f"{zone_name}/{city_name}: {exc}")
            zip_path.unlink(missing_ok=True)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_PAUSE_SECONDS)

    print(f"  FAILED: {zone_name}/{city_name} after {MAX_RETRIES} attempts")
    return False


# Main

if __name__ == "__main__":

    client = cdsapi.Client()

    total_cities = sum(len(z["cities"]) + 1 for z in ZONES.values())
    counter = 0
    failures = []

    for zone_name, zone_data in ZONES.items():
        for city in zone_data["cities"]:
            counter += 1
            print(f"[{counter}/{total_cities}] {zone_name}/{city['name']}")

            success = download_city(
                client, zone_name, city["name"], city["lat"], city["lon"]
            )
            if not success:
                failures.append(f"{zone_name}/{city['name']}")

        wind_site = zone_data["wind_site"]
        counter += 1
        print(f"[{counter}/{total_cities}] {zone_name}/wind_{wind_site['name']}")

        success = download_city(
            client, zone_name, f"wind_{wind_site['name']}",
            wind_site["lat"], wind_site["lon"],
        )
        if not success:
            failures.append(f"{zone_name}/wind_{wind_site['name']}")

    print(f"\nDone. {total_cities - len(failures)}/{total_cities} succeeded.")
    if failures:
        print("Failed cities:", ", ".join(failures))