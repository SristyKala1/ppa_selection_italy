# PPA Selection Italy

A CVaR portfolio optimizer that recommends renewable Power Purchase Agreements (PPAs) for Italian industrial electricity buyers. Given a buyer's zone, industry type, annual consumption, market access and an optional Virtual PPA reference zone, it recommends a mix of contracts, each sized as a share of the buyer's consumption, under a user-chosen tolerance for tail risk, and explains the choice in plain language.

## Who it's for

Energy and procurement managers at Italian industrial companies who are weighing renewable PPAs against staying on the spot market, and analysts or consultants who advise them. Since zonal prices replaced the national PUN for final customers, where a buyer sits matters, and the tool shows how much expected cost and tail risk each contract mix trades off for a given zone, load shape and risk tolerance.

## Built with

- Python 3.13
- Weather and price data: ERA5 via `cdsapi`, NGFS scenarios via `pyam`, `xarray` and `netCDF4`
- Physics: `pvlib` (solar) and `windpowerlib` (wind)
- Data handling: `pandas`, `numpy`, `scipy`
- Optimization: `pyomo` with the HiGHS solver (`highspy`)
- Dashboard and charts: `streamlit`, `plotly`, `matplotlib`
- Tests: `pytest`

## Features

- ERA5 hourly weather pipeline (Copernicus CDS time-series API), 1991–2023, all 7 GME bidding zones
- Solar PV (pvlib, PVWatts chain with Perez transposition) and wind (windpowerlib, one real wind farm per zone) capacity factors
- 4,950 price scenarios per zone: NGFS Phase 5 pathways, year-to-year price shocks calibrated on GME's 2005–2024 PUN history (each zone's shock correlated with the national one at 0.99, fitted on GME zonal prices), a merit-order weather adjustment, and structural zone offsets from GSE zonal day-ahead prices (2021–2025)
- Eligibility screening and cost matrices for pay-as-produced, sleeved, baseload and Virtual PPA (solar and wind) contracts, at six sizes from 10% to 100% of consumption; renewable energy is valued at KYOS capture rates (in the reference zone for Virtual PPAs, in the buyer's own zone for pay-as-produced and sleeved contracts, whose surplus above the load is credited at half that rate); baseload is struck at the expected price less 1%, plus a counterparty spread and a risk premium
- CVaR-constrained linear program (Pyomo/HiGHS): minimise expected cost subject to a CVaR budget set by the tail-risk tolerance
- Plain-language explainability layer and a Streamlit dashboard

Battery storage (BESS) and continuous contract sizing are not in the current model. See [ROADMAP.md](ROADMAP.md) for what is planned next.

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the data pipeline once before the tests or the dashboard; most tests read from `data/processed/`, which is not in the repository:

```bash
python src/ingestion/download_era5.py      # needs ~/.cdsapirc, Copernicus CDS credentials
python src/ingestion/validate_era5_downloads.py
python src/preprocessing/weather.py
python src/physics/solar.py
python src/physics/wind.py
python src/ingestion/download_ngfs.py      # guest access, no credentials needed

pytest tests/
streamlit run src/dashboard/app.py
```

## Sensitivity analyses

`analysis/` holds the scripts behind the benchmark and sensitivity results. They change model settings in memory only and leave `src/` untouched; each writes a CSV next to itself.

```bash
python analysis/benchmark_no_shocks.py   # final model on the 99 scenarios without price shocks
python analysis/size_grid.py             # 5% and coarse contract size grids
python analysis/cvar_settings.py         # CVaR confidence level and limit, budget vs. penalty form
python analysis/shock_volatility.py      # calm shocks (σ = 0.19), Nord and Sicilia with and without VPPA
python analysis/case_studies.py          # all case studies across the full tolerance range
python analysis/sensitivities.py         # one-at-a-time tests: price level, capture rates, seed, strikes, margins, surplus
python analysis/baseload_premium.py      # Baseload risk premium 0, 2.5, 5, 10, 15 €/MWh
python analysis/fit_zone_correlation.py  # correlation of zone price shocks, fitted on GME zonal prices 2005-2024
python analysis/zone_shock_correlation.py # Virtual PPA cases at zone correlations 1.0, 0.999, 0.99, 0.96
```

`python analysis/run_chapter9.py` runs all of the result scripts above in one go, with whatever settings are in `src/`.
