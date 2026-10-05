import pandas as pd
import pytest

from explainability.rationale import contract_rationale, screening_notes, shape_and_basis_notes
from optimization.portfolio import recommend


def test_flags_weak_wind_reference_zone():
    notes = screening_notes("nord", 20_000_000, has_wholesale_market_access=True, reference_zone="nord")
    assert any("vppa screened out" in n for n in notes)


def test_flags_low_baseload_volume():
    notes = screening_notes("sicilia", 100_000, has_wholesale_market_access=False)
    assert any("baseload screened out" in n for n in notes)


def test_no_notes_when_nothing_is_screened_out():
    notes = screening_notes("sicilia", 20_000_000, has_wholesale_market_access=True)
    assert notes == []


def test_contract_rationale_no_tradeoff_branch_when_one_type_dominates():
    # constructed: one contract cheaper and safer than spot in every scenario
    npvs = {"pap_solar_30%": pd.Series([90.0, 95.0, 100.0]), "spot_only": pd.Series([100.0, 110.0, 150.0])}
    result = {"weights": {"pap_solar_30%": 1.0, "spot_only": 0.0}, "contract_npvs": npvs}
    lines = contract_rationale(result)
    assert any("no tradeoff" in l for l in lines)


@pytest.fixture(scope="module")
def nord_sud_blend():
    return recommend(
        "nord", "chemicals", 20_000_000, tail_tolerance=0.6,
        reference_zone="sud", has_wholesale_market_access=True,
    )


def test_contract_rationale_narrates_both_types_in_a_two_way_portfolio(nord_sud_blend):
    lines = contract_rationale(nord_sud_blend)
    assert any("pap_solar_30%" in l and "cheapest on average" in l for l in lines)
    assert any("vppa_100%" in l and "cuts CVaR by" in l for l in lines)
    assert any("Vs. staying on spot" in l for l in lines)


def test_shape_and_basis_notes_covers_vppa(nord_sud_blend):
    notes = shape_and_basis_notes(nord_sud_blend, "nord", "chemicals", 20_000_000, reference_zone="sud")
    assert any("basis risk" in n for n in notes)
    assert any("pap_solar_30%" in n and "uncovered" in n for n in notes)


def test_shape_and_basis_notes_covers_baseload():
    # constructed result, so this doesn't need a full recommend() run
    result = {"weights": {"baseload_100%": 1.0}}
    notes = shape_and_basis_notes(result, "nord", "chemicals", 20_000_000)
    assert any("zero weather driven shape mismatch" in n for n in notes)
