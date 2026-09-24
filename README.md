# PPA Selection Italy

Master's Thesis Project

Risk-aware CVaR portfolio optimization for selecting renewable Power Purchase Agreements (PPAs) for industrial electricity consumers in the Italian market. Given a factory's zone and load profile, recommends a weighted mix of PPA contract types under a user-chosen risk appetite.

## Features

- ERA5 weather data pipeline (Copernicus CDS)
- Solar PV and wind power modelling (pvlib, windpowerlib)
- NGFS-sourced electricity price scenarios, zonal basis risk calibrated against real GME data
- Eligibility screening and per-contract-type cost matrices (Pay-as-Produced, Baseload, Virtual PPA, Sleeved)
- CVaR portfolio optimizer (Pyomo/HiGHS)
- Plain-language explainability layer for the optimizer's recommendations
- Streamlit dashboard

Battery/storage sizing is not implemented yet, still an open scope decision.

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

pytest tests/
```

Running the data pipeline from scratch:

```bash
python src/ingestion/download_era5.py      # needs ~/.cdsapirc, Copernicus CDS credentials
python src/ingestion/validate_era5_downloads.py
python src/preprocessing/weather.py
python src/physics/solar.py
python src/physics/wind.py
python src/ingestion/download_ngfs.py      # guest access, no credentials needed

streamlit run src/dashboard/app.py
```
