
from pathlib import Path

import pandas as pd
import xarray as xr
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_WEATHER_DIR = PROJECT_ROOT / "data" / "raw" / "weather"

with open(PROJECT_ROOT / "config.yaml") as f:
    config = yaml.safe_load(f)

ZONES = config["zones"]
START_YEAR = config["weather"]["start_year"]
END_YEAR = config["weather"]["end_year"]
EXPECTED_VARS = {"t2m", "ssrd", "fdir", "sp", "u100", "v100"}


def check(path):
    if not path.exists():
        return "missing"

    ds = xr.open_dataset(path)
    missing_vars = EXPECTED_VARS - set(ds.data_vars)
    if missing_vars:
        return f"missing vars {missing_vars}"

    tmin = pd.Timestamp(ds.valid_time.min().item())
    tmax = pd.Timestamp(ds.valid_time.max().item())
    if tmin.year != START_YEAR or tmax.year != END_YEAR:
        return f"range {tmin.date()} to {tmax.date()}"

    nans = sum(ds[v].isnull().sum().item() for v in ds.data_vars)
    if nans:
        return f"{nans} NaNs"

    ds.close()
    return None


if __name__ == "__main__":
    failures = {}

    for zone, zone_data in ZONES.items():
        for city in zone_data["cities"]:
            path = RAW_WEATHER_DIR / f"era5_{zone}_{city['name']}.nc"
            result = check(path)
            if result:
                failures[f"{zone}/{city['name']}"] = result

    if failures:
        for name, reason in failures.items():
            print(f"FAIL {name}: {reason}")
    else:
        print("All files are OK")