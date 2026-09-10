from scenarios.price_scenarios import zone_annual_cf

MIN_SOLAR_CF = 0.10
MIN_WIND_CF = 0.10
MIN_BASELOAD_VOLUME_MWH = 10_000


def eligible_contracts(zone, annual_kwh, has_wholesale_market_access=False, reference_zone=None):
    annual_load_mwh = annual_kwh / 1000
    solar_cf = zone_annual_cf("solar", zone).mean()
    wind_cf = zone_annual_cf("wind", zone).mean()

    eligible = set()

    if solar_cf >= MIN_SOLAR_CF:
        eligible.add("pap_solar" if has_wholesale_market_access else "sleeved")

    if has_wholesale_market_access and wind_cf >= MIN_WIND_CF:
        eligible.add("pap_wind")

    if annual_load_mwh >= MIN_BASELOAD_VOLUME_MWH:
        eligible.add("baseload")

    if reference_zone is not None and zone_annual_cf("wind", reference_zone).mean() >= MIN_WIND_CF:
        eligible.add("vppa")

    return eligible
