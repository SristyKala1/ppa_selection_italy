import pytest

from scenarios.price_scenarios import (
    ANCHOR_YEAR,
    GME_PUN_2024,
    SCENARIOS,
    ZONE_STRUCTURAL_OFFSET_EUR_PER_MWH,
    build_zonal_price_matrix,
    rescaled_price_trajectory,
    zone_annual_cf,
    zone_merit_order_adjustment,
)


def test_rejects_unknown_zone():
    with pytest.raises(ValueError):
        zone_annual_cf("solar", "atlantis")


def test_known_zone_still_works():
    cf = zone_annual_cf("solar", "nord")
    assert len(cf) > 0
    assert (cf > 0).all()


def test_rescaled_trajectory_is_anchored_to_the_2024_gme_pun():
    for scenario in SCENARIOS:
        traj = rescaled_price_trajectory(scenario, 2020, 2030)
        assert traj.loc[ANCHOR_YEAR] == pytest.approx(GME_PUN_2024)


def test_zone_merit_order_adjustment_centers_on_the_structural_offset():
    # the weather-driven component is zero-mean by construction, but the whole
    # adjustment now carries each zone's fixed historical structural offset on top
    adjustment = zone_merit_order_adjustment("nord")
    assert adjustment.mean() == pytest.approx(ZONE_STRUCTURAL_OFFSET_EUR_PER_MWH["nord"], abs=1e-9)


def test_zonal_price_matrix_shape_and_column_names():
    matrix = build_zonal_price_matrix("nord")
    assert matrix.shape == (15, 99)
    assert matrix.columns.names == ["price_scenario", "weather_year"]
