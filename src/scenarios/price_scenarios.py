from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NGFS_CSV = PROJECT_ROOT / "data" / "raw" / "prices" / "ngfs_price_ita.csv"

MODEL = "Downscaling[REMIND-MAgPIE 3.3-4.8]"
VARIABLE = "Price|Secondary Energy|Electricity"
SCENARIOS = ["Delayed transition", "Nationally Determined Contributions (NDCs)", "Net Zero 2050"]

GJ_PER_MWH = 3.6
USD_PER_EUR_2010 = 1.33

GME_PUN_2024 = 108.52
ANCHOR_YEAR = 2024

with open(PROJECT_ROOT / "config.yaml") as f:
    config = yaml.safe_load(f)

ZONES = list(config["zones"].keys())
START_YEAR = config["weather"]["start_year"]
END_YEAR = config["weather"]["end_year"]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

SOLAR_INSTALLED_CAPACITY_GW = 37.1
WIND_INSTALLED_CAPACITY_GW = 13.0

SOLAR_MERIT_ORDER_COEF = -3.45
WIND_MERIT_ORDER_COEF = -2.86


def load_price_trajectories():
    df = pd.read_csv(NGFS_CSV)
    df = df[(df["Model"] == MODEL) & (df["Variable"] == VARIABLE) & (df["Region"] == "ITA")]
    df = df[df["Scenario"].isin(SCENARIOS)]

    year_cols = [c for c in df.columns if c.isdigit() and int(c) <= 2050]
    trajectories = df.set_index("Scenario")[year_cols]
    trajectories.columns = trajectories.columns.astype(int)

    return trajectories * GJ_PER_MWH / USD_PER_EUR_2010


def full_annual_trajectory(scenario):
    prices = load_price_trajectories().loc[scenario]
    full_range = range(prices.index.min(), prices.index.max() + 1)
    return prices.reindex(full_range).interpolate(method="linear")


def annual_price_trajectory(scenario, start_year, end_year):
    return full_annual_trajectory(scenario).loc[start_year:end_year]


def rescaled_price_trajectory(scenario, start_year, end_year):
    trajectory = full_annual_trajectory(scenario)
    scale = GME_PUN_2024 / trajectory.loc[ANCHOR_YEAR]
    return (trajectory * scale).loc[start_year:end_year]


def national_annual_cf(technology):
    column = f"{technology}_cf"
    by_year = {}
    for year in range(START_YEAR, END_YEAR + 1):
        zone_means = [
            pd.read_csv(PROCESSED_DIR / technology / zone / f"{column}_{year}.csv")[column].mean()
            for zone in ZONES
        ]
        by_year[year] = sum(zone_means) / len(ZONES)
    return by_year


def merit_order_adjustment_by_year():
    solar_output = {y: cf * SOLAR_INSTALLED_CAPACITY_GW for y, cf in national_annual_cf("solar").items()}
    wind_output = {y: cf * WIND_INSTALLED_CAPACITY_GW for y, cf in national_annual_cf("wind").items()}

    solar_baseline = sum(solar_output.values()) / len(solar_output)
    wind_baseline = sum(wind_output.values()) / len(wind_output)

    return {
        y: SOLAR_MERIT_ORDER_COEF * (solar_output[y] - solar_baseline)
           + WIND_MERIT_ORDER_COEF * (wind_output[y] - wind_baseline)
        for y in solar_output
    }
