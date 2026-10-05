from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from scenarios.price_scenarios import (
    build_zonal_price_matrix,
    zone_annual_cf,
    START_YEAR,
    END_YEAR,
    PROCESSED_DIR,
)
from scenarios.load_profile import load_profile_for_archetype
from timeseries import read_timeseries_csv

STRIKE_PRICE_SOLAR = 56.83
STRIKE_PRICE_WIND = 72.85
COUNTERPARTY_SPREAD = 5.0
SLEEVING_MARGIN = 3.0
BASELOAD_DISCOUNT = 0.03  # Bonaldo et al. 2021, near-parity Italy baseload futures vs spot
HOURS_PER_YEAR = 8760

# onshore wind capture price / baseload price, KYOS PPA Insights No. 14 (June 2025), 2026-2035 averages
WIND_CAPTURE_RATE = {
    "nord": 1.018, "centro_nord": 1.003, "centro_sud": 0.977, "sud": 0.881,
    "calabria": 0.900, "sicilia": 0.850, "sardegna": 0.808,
}


@lru_cache(maxsize=None)
def hourly_cf(technology, zone, year):
    cf = read_timeseries_csv(PROCESSED_DIR / technology / zone / f"{technology}_cf_{year}.csv")
    return cf[f"{technology}_cf"].resample("h").mean().to_numpy()


def annual_residual_mwh(technology, zone, contracted_mw, load):
    load_mwh = load.to_numpy() / 1000
    by_year = {}
    for year in range(START_YEAR, END_YEAR + 1):
        gen_mwh = hourly_cf(technology, zone, year) * contracted_mw
        n = min(len(load_mwh), len(gen_mwh))
        by_year[year] = np.maximum(load_mwh[:n] - gen_mwh[:n], 0.0).sum()
    return pd.Series(by_year)


def zonal_basis_risk(own_zone, reference_zone):
    return build_zonal_price_matrix(own_zone) - build_zonal_price_matrix(reference_zone)


def _as_matrix(columns):
    matrix = pd.DataFrame(columns)
    matrix.columns.names = ["price_scenario", "weather_year"]
    matrix.index.name = "contract_year"
    return matrix


def _pap_cost_matrix(technology, strike, zone, price_matrix, contracted_mw, load):
    cf = zone_annual_cf(technology, zone)
    payment = (strike + COUNTERPARTY_SPREAD) * cf * HOURS_PER_YEAR * contracted_mw
    residual = annual_residual_mwh(technology, zone, contracted_mw, load)
    return _as_matrix({
        (s, w): payment[w] + residual[w] * price_matrix[(s, w)]
        for s, w in price_matrix.columns
    })


def mw_for_coverage(technology, zone, coverage, annual_load_mwh):
    # nameplate MW whose average yearly output equals `coverage` of the buyer's consumption
    return coverage * annual_load_mwh / (zone_annual_cf(technology, zone).mean() * HOURS_PER_YEAR)


def contract_cost_matrices(zone, archetype, annual_kwh, coverage=1.0, reference_zone=None):
    price_own = build_zonal_price_matrix(zone)
    load = load_profile_for_archetype(archetype, annual_kwh)
    annual_load_mwh = load.sum() / 1000

    solar_mw = mw_for_coverage("solar", zone, coverage, annual_load_mwh)
    wind_mw = mw_for_coverage("wind", zone, coverage, annual_load_mwh)
    matrices = {
        "pap_solar": _pap_cost_matrix("solar", STRIKE_PRICE_SOLAR, zone, price_own, solar_mw, load),
        "pap_wind": _pap_cost_matrix("wind", STRIKE_PRICE_WIND, zone, price_own, wind_mw, load),
    }

    fee = SLEEVING_MARGIN * zone_annual_cf("solar", zone) * HOURS_PER_YEAR * solar_mw
    matrices["sleeved"] = _as_matrix({
        (s, w): matrices["pap_solar"][(s, w)] + fee[w] for s, w in price_own.columns
    })

    baseload_mw = coverage * annual_load_mwh / HOURS_PER_YEAR
    strike_baseload = price_own.mean().mean() * (1 - BASELOAD_DISCOUNT) + COUNTERPARTY_SPREAD
    baseload_payment = strike_baseload * baseload_mw * HOURS_PER_YEAR
    baseload_residual = annual_load_mwh - baseload_mw * HOURS_PER_YEAR
    matrices["baseload"] = _as_matrix({
        (s, w): baseload_payment + baseload_residual * price_own[(s, w)]
        for s, w in price_own.columns
    })

    matrices["spot_only"] = _as_matrix({
        (s, w): annual_load_mwh * price_own[(s, w)] for s, w in price_own.columns
    })

    if reference_zone is not None:
        price_ref = build_zonal_price_matrix(reference_zone)
        wind_cf_ref = zone_annual_cf("wind", reference_zone)
        vppa_mw = mw_for_coverage("wind", reference_zone, coverage, annual_load_mwh)
        capture = WIND_CAPTURE_RATE[reference_zone]
        matrices["vppa"] = _as_matrix({
            (s, w): annual_load_mwh * price_own[(s, w)]
            + (STRIKE_PRICE_WIND + COUNTERPARTY_SPREAD - capture * price_ref[(s, w)])
            * wind_cf_ref[w] * HOURS_PER_YEAR * vppa_mw
            for s, w in price_own.columns
        })

    return matrices
