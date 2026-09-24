"""
download_ngfs.py

Fetches the NGFS price scenario data price_scenarios.py needs, via the IIASA
Scenario Explorer API (pyam), instead of the manual website export it started
as. Only pulls the one model/variable/scenario slice actually used, not the
full multi-model NGFS export, both because that's all price_scenarios.py
reads anyway and because the NGFS license restricts redistributing
substantial portions of the dataset.

Guest access, no credentials needed. Platform name confirmed by actually
listing pyam.iiasa.Connection().valid_connections, not just guessed.
"""

from pathlib import Path

import pyam

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "prices" / "ngfs_price_ita.csv"

PLATFORM = "ngfs_phase_5"
MODEL = "Downscaling[REMIND-MAgPIE 3.3-4.8]"
VARIABLE = "Price|Secondary Energy|Electricity"
REGION = "ITA"
SCENARIOS = ["Delayed transition", "Nationally Determined Contributions (NDCs)", "Net Zero 2050"]


def download_ngfs_prices():
    if OUTPUT_PATH.exists():
        print(f"Skipping ({OUTPUT_PATH.name} already downloaded)")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        connection = pyam.iiasa.Connection(PLATFORM)
        result = connection.query(model=MODEL, variable=VARIABLE, region=REGION, scenario=SCENARIOS)
    except Exception as exc:
        raise RuntimeError(f"couldn't reach the IIASA {PLATFORM} platform: {exc}")

    wide = result.timeseries().reset_index()
    wide = wide.rename(columns={c: str(c).capitalize() for c in wide.columns if not isinstance(c, int)})
    wide.to_csv(OUTPUT_PATH, index=False)


if __name__ == "__main__":
    download_ngfs_prices()
    print("Done.")
