import pandas as pd
import pytest

from optimization.portfolio import (
    _cvar, candidate_npvs, optimize_portfolio, recommend, recommend_from_npvs, scenario_npv,
)


def test_recommend_rejects_unknown_zone():
    with pytest.raises(ValueError):
        recommend("atlantis", "chemicals", 20_000_000, tail_tolerance=0.5)


def test_recommend_rejects_unknown_reference_zone():
    with pytest.raises(ValueError):
        recommend("nord", "chemicals", 20_000_000, tail_tolerance=0.5, reference_zone="atlantis")


def test_recommend_rejects_unknown_archetype():
    with pytest.raises(ValueError):
        recommend("nord", "spaceship_yard", 20_000_000, tail_tolerance=0.5)


def test_recommend_rejects_non_positive_annual_kwh():
    with pytest.raises(ValueError):
        recommend("nord", "chemicals", 0, tail_tolerance=0.5)


def test_optimize_portfolio_rejects_negative_rho():
    with pytest.raises(ValueError):
        optimize_portfolio({"spot_only": None}, rho=-5)


@pytest.fixture(scope="module")
def nord_sud_npvs():
    # nord buying, sud as the VPPA reference zone
    _, npvs = candidate_npvs("nord", "chemicals", 20_000_000, reference_zone="sud",
                             has_wholesale_market_access=True)
    return npvs


def test_recommend_rejects_tail_tolerance_outside_0_to_1(nord_sud_npvs):
    with pytest.raises(ValueError):
        recommend_from_npvs(nord_sud_npvs, 1.5)


def test_mid_tolerance_blends_solar_and_vppa(nord_sud_npvs):
    result = recommend_from_npvs(nord_sud_npvs, 0.6)
    weights = result["weights"]
    assert weights["pap_solar_30%"] > 0.3
    assert weights["vppa_wind_100%"] > 0.3
    assert sum(weights.values()) == pytest.approx(1.0)


def test_lower_tolerance_costs_more_and_cuts_the_tail(nord_sud_npvs):
    loose = recommend_from_npvs(nord_sud_npvs, 1.0)
    tight = recommend_from_npvs(nord_sud_npvs, 0.0)
    assert tight["expected_cost"] > loose["expected_cost"]
    assert tight["cvar"] < loose["cvar"]


def test_cvar_budget_is_respected(nord_sud_npvs):
    result = optimize_portfolio(nord_sud_npvs, cvar_budget=20_000_000)
    assert result["cvar"] <= 20_000_000 + 1


def test_recommend_tiny_consumer_gets_a_small_sleeved_contract():
    result = recommend("nord", "office_services", 100_000, tail_tolerance=0.5, has_wholesale_market_access=False)
    top = max(result["weights"], key=result["weights"].get)
    assert top.startswith("sleeved_")


def test_scenario_npv_with_zero_discount_is_a_plain_sum():
    cost_matrix = pd.DataFrame({"a": [100, 100, 100]}, index=[2026, 2027, 2028])
    npv = scenario_npv(cost_matrix, discount_rate=0.0)
    assert npv["a"] == pytest.approx(300.0)


def test_scenario_npv_discounts_future_years():
    cost_matrix = pd.DataFrame({"a": [100, 100, 100]}, index=[2026, 2027, 2028])
    npv = scenario_npv(cost_matrix, discount_rate=0.10)
    assert npv["a"] < 300.0
    assert npv["a"] == pytest.approx(273.55, abs=0.01)


def test_cvar_averages_the_exact_worst_slice():
    # alpha=0.5 on 4 scenarios -> worst 2 of 4, no interpolation needed
    npv = pd.Series([10, 20, 30, 40])
    assert _cvar(npv, alpha=0.5) == pytest.approx(35.0)  # average of 40 and 30


def test_cvar_interpolates_a_fractional_tail():
    # alpha=0.5 on 3 scenarios -> worst 1.5 of 3, interpolates between the worst and 2nd worst
    npv = pd.Series([10, 20, 30])
    assert _cvar(npv, alpha=0.5) == pytest.approx(26.666, abs=0.001)
