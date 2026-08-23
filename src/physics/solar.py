from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_WEATHER_DIR = PROJECT_ROOT / "data" / "processed" / "weather"
PROCESSED_SOLAR_DIR = PROJECT_ROOT / "data" / "processed" / "solar"

with open(PROJECT_ROOT / "config.yaml") as f:
    config = yaml.safe_load(f)

START_YEAR = config["weather"]["start_year"]
END_YEAR = config["weather"]["end_year"]


def zone_coords(zone_name):
    cities = config["zones"][zone_name]["cities"]
    lat = np.mean([c["lat"] for c in cities])
    lon = np.mean([c["lon"] for c in cities])
    return lat, lon


def solar_capacity_factor(weather, lat, lon):
    solpos = pvlib.solarposition.get_solarposition(
        time=weather.index, latitude=lat, longitude=lon
    )
    cos_zenith = np.cos(np.radians(solpos["zenith"]))

    bhi = weather["bhi_wm2"]
    ghi = weather["ghi_wm2"]
    dni = (bhi / cos_zenith).where(solpos["zenith"] < 85, 0.0).clip(upper=1000)
    dhi = (ghi - bhi).clip(lower=0)

    dni_extra = pvlib.irradiance.get_extra_radiation(weather.index)
    airmass = pvlib.atmosphere.get_relative_airmass(solpos["zenith"])

    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=lat,
        surface_azimuth=180,
        solar_zenith=solpos["zenith"],
        solar_azimuth=solpos["azimuth"],
        dni=dni,
        ghi=ghi,
        dhi=dhi,
        dni_extra=dni_extra,
        airmass=airmass,
        model="perez",
    )

    temp_cell = pvlib.temperature.noct_sam(
        poa_global=poa["poa_global"],
        temp_air=weather["temp_c"],
        wind_speed=weather["wind_speed_ms"],
        noct=45,
        module_efficiency=0.19,
    )

    pdc = pvlib.pvsystem.pvwatts_dc(
        effective_irradiance=poa["poa_global"],
        temp_cell=temp_cell,
        pdc0=1,
        gamma_pdc=-0.0047,
    )

    return pvlib.inverter.pvwatts(pdc, pdc0=1, eta_inv_nom=0.96)


def process_zone_year(zone_name, year):
    weather = pd.read_csv(
        PROCESSED_WEATHER_DIR / zone_name / f"weather_{year}.csv",
        index_col=0,
    )
    weather.index = pd.to_datetime(weather.index, utc=True).tz_convert("Europe/Rome")
    lat, lon = zone_coords(zone_name)
    return solar_capacity_factor(weather, lat, lon)


def main():
    for zone_name in config["zones"]:
        zone_dir = PROCESSED_SOLAR_DIR / zone_name
        zone_dir.mkdir(parents=True, exist_ok=True)

        for year in range(START_YEAR, END_YEAR + 1):
            cf = process_zone_year(zone_name, year)
            cf.to_frame("solar_cf").to_csv(zone_dir / f"solar_cf_{year}.csv")

        print(f"{zone_name} done")


if __name__ == "__main__":
    main()
