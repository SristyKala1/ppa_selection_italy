import numpy as np
import pandas as pd
import pytest

from physics.solar import config, solar_capacity_factor, zone_coords


def _synthetic_day():
    index = pd.date_range("2020-07-15 00:00", periods=24, freq="h", tz="Europe/Rome")
    hour = index.hour
    daylight = (hour >= 5) & (hour <= 20)
    bump = np.sin(np.pi * np.clip((hour - 5) / 15, 0, 1)) * daylight
    return pd.DataFrame({
        "ghi_wm2": 700.0 * bump,
        "bhi_wm2": 500.0 * bump,
        "temp_c": 25.0,
        "wind_speed_ms": 3.0,
    }, index=index)


def test_zone_coords_is_the_mean_of_the_zone_cities():
    lat, lon = zone_coords("nord")
    cities = config["zones"]["nord"]["cities"]
    assert lat == pytest.approx(np.mean([c["lat"] for c in cities]))
    assert lon == pytest.approx(np.mean([c["lon"] for c in cities]))


def test_capacity_factor_zero_at_night_positive_at_noon():
    lat, lon = zone_coords("centro_sud")
    weather = _synthetic_day()
    cf = solar_capacity_factor(weather, lat, lon)

    assert not cf.isna().any()
    assert (cf[weather.index.hour.isin([0, 1, 2, 3])] == 0).all()
    assert cf[weather.index.hour == 13].iloc[0] > 0.5


def test_capacity_factor_never_exceeds_one():
    lat, lon = zone_coords("centro_sud")
    weather = _synthetic_day()
    cf = solar_capacity_factor(weather, lat, lon)
    assert (cf <= 1.0).all()
