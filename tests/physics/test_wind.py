import numpy as np
import pandas as pd
import pytest

from physics.wind import wind_capacity_factor


def test_zero_below_cut_in_speed():
    speed = pd.Series([0.0, 1.0])
    cf = wind_capacity_factor(speed)
    assert (cf == 0).all()


def test_zero_above_cut_out_speed():
    speed = pd.Series([35.0])
    cf = wind_capacity_factor(speed)
    assert cf.iloc[0] == 0.0


def test_flat_out_around_rated_wind_speed():
    speed = pd.Series([12.0, 15.0, 20.0])
    cf = wind_capacity_factor(speed)
    assert np.allclose(cf.to_numpy(), cf.iloc[0])
    assert cf.iloc[0] == pytest.approx(0.984, abs=0.01)


def test_capacity_factor_stays_between_zero_and_one():
    speed = pd.Series(np.linspace(0, 35, 50))
    cf = wind_capacity_factor(speed)
    assert (cf >= 0).all()
    assert (cf <= 1.0).all()
