import pandas as pd
import pytest

from optimization.portfolio import _cvar, efficient_frontier, optimize_portfolio, recommend, scenario_npv


def test_recommend_rejects_unknown_zone():
    with pytest.raises(ValueError):
        recommend("atlantis", "chemicals", 20_000_000, rho=3)


def test_recommend_rejects_unknown_reference_zone():
    with pytest.raises(ValueError):
        recommend("nord", "chemicals", 20_000_000, rho=3, reference_zone="atlantis")


def test_recommend_rejects_unknown_archetype():
    with pytest.raises(ValueError):
        recommend("nord", "spaceship_yard", 20_000_000, rho=3)


def test_recommend_rejects_non_positive_annual_kwh():
    with pytest.raises(ValueError):
        recommend("nord", "chemicals", 0, rho=3)


def test_optimize_portfolio_rejects_negative_rho():
    with pytest.raises(ValueError):
        optimize_portfolio({"spot_only": None}, rho=-5)


def test_recommend_happy_path_nord_sud_matches_documented_case():
    # nord buying, sud as the VPPA reference zone, the risk-return pivot example.
    # the earlier centro_nord/sardegna example didn't survive the basis-risk structural offset
    result = recommend(
        "nord", "chemicals", 20_000_000, rho=10,
        reference_zone="sud", has_wholesale_market_access=True,
    )
    assert result["weights"]["pap_solar"] == pytest.approx(0.581, abs=0.01)
    assert result["weights"]["vppa"] == pytest.approx(0.419, abs=0.01)
    assert sum(result["weights"].values()) == pytest.approx(1.0)


def test_recommend_tiny_consumer_collapses_to_spot_only():
    result = recommend("nord", "office_services", 100_000, rho=3, has_wholesale_market_access=False)
    assert result["weights"]["spot_only"] == pytest.approx(1.0)


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


def test_efficient_frontier_expected_cost_rises_and_cvar_falls_with_rho():
    result = recommend(
        "nord", "chemicals", 20_000_000, rho=10,
        reference_zone="sud", has_wholesale_market_access=True,
        frontier_rhos=[0, 5, 10, 20],
    )
    frontier = result["frontier"]
    assert len(frontier) == 4
    assert frontier.index.name == "rho"
    assert frontier["expected_cost"].is_monotonic_increasing
    assert frontier["cvar"].is_monotonic_decreasing
