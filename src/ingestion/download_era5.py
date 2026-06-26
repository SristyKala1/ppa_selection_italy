"""
download_era5.py

Downloads hourly ERA5 weather data from the Copernicus Climate Data Store.

Current version:
- Downloads one year only
- Reads coordinates from config.yaml
- Saves raw NetCDF files

Later versions will:
- Loop over all 33 years
- Skip already-downloaded files
- Add retry/error handling
"""

from pathlib import Path

import cdsapi
import yaml


# --------------------------------------------------
# Check CDS credentials
# --------------------------------------------------

cds_key = Path.home() / ".cdsapirc"

if not cds_key.exists():
    raise FileNotFoundError(
        "CDS API credentials not found.\n"
        "Create ~/.cdsapirc before running this script."
    )


# --------------------------------------------------
# Read configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

config_path = PROJECT_ROOT / "config.yaml"

with open(config_path, "r") as file:
    config = yaml.safe_load(file)

LATITUDE = config["site"]["latitude"]
LONGITUDE = config["site"]["longitude"]


# --------------------------------------------------
# Output folder
# --------------------------------------------------

RAW_WEATHER_DIR = PROJECT_ROOT / "data" / "raw" / "weather"

RAW_WEATHER_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Download function
# --------------------------------------------------

def download_era5(year, month):

    print(f"Downloading {year}-{month:02d}...")

    client = cdsapi.Client()

    output_file = RAW_WEATHER_DIR / f"weather_{year}_{month:02d}.nc"

    client.retrieve(
        "reanalysis-era5-single-levels",
        {
            "product_type": "reanalysis",

            "variable": [
                "2m_temperature",
                "surface_solar_radiation_downwards",
                "total_sky_direct_solar_radiation_at_surface",
                "surface_pressure",
                "100m_u_component_of_wind",
                "100m_v_component_of_wind",
            ],

            "year": str(year),

            "month": [f"{month:02d}"],

            "day": [
                "01","02","03","04","05","06","07","08","09","10",
                "11","12","13","14","15","16","17","18","19","20",
                "21","22","23","24","25","26","27","28","29","30","31"
            ],

            "time": [
                "00:00","01:00","02:00","03:00",
                "04:00","05:00","06:00","07:00",
                "08:00","09:00","10:00","11:00",
                "12:00","13:00","14:00","15:00",
                "16:00","17:00","18:00","19:00",
                "20:00","21:00","22:00","23:00"
            ],

            # ERA5 expects: North, West, South, East
            "area": [
                LATITUDE + 0.25,
                LONGITUDE - 0.25,
                LATITUDE - 0.25,
                LONGITUDE + 0.25,
            ],

            "data_format": "netcdf",
            "download_format": "unarchived",
        },

        str(output_file),

    )

    print(f"\nFinished downloading {year}")
    print(output_file)


# --------------------------------------------------
# Main
# --------------------------------------------------

if __name__ == "__main__":

    for month in range(1, 13):
        download_era5(1991, month)