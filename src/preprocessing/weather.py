from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_WEATHER_DIR = PROJECT_ROOT / "data" / "raw" / "weather"
PROCESSED_WEATHER_DIR = PROJECT_ROOT / "data" / "processed" / "weather"

with open(PROJECT_ROOT / "config.yaml") as f:
    config = yaml.safe_load(f)

START_YEAR = config["weather"]["start_year"]
END_YEAR = config["weather"]["end_year"]


def process_city(path):
    ds = xr.open_dataset(path)
    df = ds.to_dataframe().reset_index()

    time_col = "valid_time" if "valid_time" in df.columns else "time"
    df = df.set_index(time_col)

    conv = pd.DataFrame(index=df.index)
    conv["temp_c"] = df["t2m"] - 273.15
    conv["ghi_wm2"] = (df["ssrd"] / 3600).clip(lower=0)
    conv["bhi_wm2"] = (df["fdir"] / 3600).clip(lower=0)
    conv["pressure_pa"] = df["sp"]
    conv["wind_speed_ms"] = np.sqrt(df["u100"]**2 + df["v100"]**2)

    conv.index = conv.index.tz_localize("UTC").tz_convert("Europe/Rome")
    return conv


def validate_zone_weather(df, zone_name, start_year, end_year):
    if df.isna().any().any():
        raise ValueError(f"{zone_name}: NaN values found in processed weather data")

    if not df["temp_c"].between(-50, 60).all():
        raise ValueError(f"{zone_name}: temperature outside plausible range (-50 to 60 C)")

    if not df["pressure_pa"].between(70_000, 110_000).all():
        raise ValueError(f"{zone_name}: pressure outside plausible range (70,000-110,000 Pa)")

    num_years = end_year - start_year + 1
    num_leap = sum(1 for y in range(start_year, end_year + 1)
                    if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
    expected_rows = (num_years - num_leap) * 8_760 + num_leap * 8_784
    tolerance = 2 * num_years

    if abs(len(df) - expected_rows) > tolerance:
        raise ValueError(
            f"{zone_name}: row count {len(df)} outside tolerance of expected {expected_rows} (±{tolerance})"
        )


def aggregate_zone(city_data, zone_name):
    common_index = city_data[next(iter(city_data))].index
    for df in city_data.values():
        common_index = common_index.intersection(df.index)

    if len(common_index) == 0:
        raise ValueError(
            f"{zone_name}: no overlapping timestamps across cities, check for corrupted/misaligned downloads"
        )

    stacked = pd.concat(city_data.values(), keys=city_data.keys())
    zone_weather = stacked.groupby(level=1).mean()

    validate_zone_weather(zone_weather, zone_name, START_YEAR, END_YEAR)
    return zone_weather


def write_zone_weather(zone_weather, zone_name):
    zone_dir = PROCESSED_WEATHER_DIR / zone_name
    zone_dir.mkdir(parents=True, exist_ok=True)

    in_range = zone_weather[
        (zone_weather.index.year >= START_YEAR) & (zone_weather.index.year <= END_YEAR)
    ]

    for year, year_df in in_range.groupby(in_range.index.year):
        year_df.to_csv(zone_dir / f"weather_{year}.csv")

def main():
    for zone_name, zone_data in config["zones"].items():
        print(f"Processing {zone_name}...")

        city_data = {
            city["name"]: process_city(RAW_WEATHER_DIR / f"era5_{zone_name}_{city['name']}.nc")
            for city in zone_data["cities"]
        }

        zone_weather = aggregate_zone(city_data, zone_name)
        write_zone_weather(zone_weather, zone_name)

    print("Done.")


if __name__ == "__main__":
    main()

