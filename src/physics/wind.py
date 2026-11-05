import sys
from pathlib import Path

import yaml
from windpowerlib import WindTurbine, power_output

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preprocessing.weather import process_wind_site, validate_wind_site

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_WEATHER_DIR = PROJECT_ROOT / "data" / "raw" / "weather"
PROCESSED_WIND_DIR = PROJECT_ROOT / "data" / "processed" / "wind"

with open(PROJECT_ROOT / "config.yaml") as f:
    config = yaml.safe_load(f)

START_YEAR = config["weather"]["start_year"]
END_YEAR = config["weather"]["end_year"]

turbine = WindTurbine(turbine_type="E-101/3050", hub_height=100)


def wind_capacity_factor(speed):
    power = power_output.power_curve(
        wind_speed=speed,
        power_curve_wind_speeds=turbine.power_curve["wind_speed"],
        power_curve_values=turbine.power_curve["value"],
    )
    return power / turbine.nominal_power


def main():
    for zone_name, zone_data in config["zones"].items():
        site = zone_data["wind_site"]
        path = RAW_WEATHER_DIR / f"era5_{zone_name}_wind_{site['name']}.nc"

        wind_speed = process_wind_site(path)
        validate_wind_site(wind_speed, f"{zone_name}/wind_{site['name']}", START_YEAR, END_YEAR)
        cf = wind_capacity_factor(wind_speed)

        zone_dir = PROCESSED_WIND_DIR / zone_name
        zone_dir.mkdir(parents=True, exist_ok=True)

        for year, year_cf in cf.groupby(cf.index.year):
            if START_YEAR <= year <= END_YEAR:
                year_cf.to_frame("wind_cf").to_csv(zone_dir / f"wind_cf_{year}.csv")

        print(f"{zone_name} done")


if __name__ == "__main__":
    main()
