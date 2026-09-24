import numpy as np
import pandas as pd
import pytest

from preprocessing.weather import aggregate_zone, validate_zone_weather


def _clean_year_df():
    index = pd.date_range("2021-01-01", periods=35_040, freq="15min")
    return pd.DataFrame({
        "temp_c": 15.0,
        "ghi_wm2": 100.0,
        "bhi_wm2": 80.0,
        "pressure_pa": 101_000.0,
        "wind_speed_ms": 3.0,
    }, index=index)


def test_passes_on_clean_data():
    validate_zone_weather(_clean_year_df(), "test_zone", 2021, 2021)


def test_raises_on_nan():
    df = _clean_year_df()
    df.iloc[0, 0] = np.nan
    with pytest.raises(ValueError):
        validate_zone_weather(df, "test_zone", 2021, 2021)


def test_raises_on_temperature_out_of_range():
    df = _clean_year_df()
    df.loc[df.index[0], "temp_c"] = 200.0
    with pytest.raises(ValueError):
        validate_zone_weather(df, "test_zone", 2021, 2021)


def test_raises_on_pressure_out_of_range():
    df = _clean_year_df()
    df.loc[df.index[0], "pressure_pa"] = 1000.0
    with pytest.raises(ValueError):
        validate_zone_weather(df, "test_zone", 2021, 2021)


def test_raises_on_row_count_way_off():
    df = _clean_year_df().iloc[:1000]
    with pytest.raises(ValueError):
        validate_zone_weather(df, "test_zone", 2021, 2021)


def test_aggregate_zone_raises_on_no_overlapping_timestamps():
    city_a = pd.DataFrame({"temp_c": [10.0]}, index=pd.date_range("2021-01-01", periods=1, freq="h"))
    city_b = pd.DataFrame({"temp_c": [12.0]}, index=pd.date_range("2022-01-01", periods=1, freq="h"))
    with pytest.raises(ValueError):
        aggregate_zone({"city_a": city_a, "city_b": city_b}, "test_zone")
