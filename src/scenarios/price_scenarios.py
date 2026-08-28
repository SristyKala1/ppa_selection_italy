from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NGFS_CSV = PROJECT_ROOT / "data" / "raw" / "prices" / "ngfs_price_ita.csv"

MODEL = "Downscaling[REMIND-MAgPIE 3.3-4.8]"
VARIABLE = "Price|Secondary Energy|Electricity"
SCENARIOS = ["Delayed transition", "Nationally Determined Contributions (NDCs)", "Net Zero 2050"]

GJ_PER_MWH = 3.6
USD_PER_EUR_2010 = 1.33

GME_PUN_2024 = 108.52
ANCHOR_YEAR = 2024


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
