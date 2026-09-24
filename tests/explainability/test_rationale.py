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
    result = recommend("sicilia", "chemicals", 20_000_000, rho=8, has_wholesale_market_access=True)
    lines = contract_rationale(result)
    assert any("no tradeoff" in l for l in lines)
    assert any("Vs. staying on spot" in l for l in lines)


def test_contract_rationale_narrates_both_types_in_a_two_way_portfolio():
    result = recommend(
        "nord", "chemicals", 20_000_000, rho=10,
        reference_zone="sud", has_wholesale_market_access=True,
    )
    lines = contract_rationale(result)
    assert any("pap_solar" in l and "no tradeoff" in l for l in lines)
    assert any("vppa" in l and "cuts CVaR by" in l for l in lines)


def test_shape_and_basis_notes_covers_vppa():
    result = recommend(
        "nord", "chemicals", 20_000_000, rho=10,
        reference_zone="sud", has_wholesale_market_access=True,
    )
    notes = shape_and_basis_notes(result, "nord", "chemicals", 20_000_000, reference_zone="sud")
    assert any("basis risk" in n for n in notes)


def test_shape_and_basis_notes_covers_baseload():
    # no real recommend() case picks baseload anymore at BASELOAD_DISCOUNT=0.03, so this
    # exercises the baseload branch directly with a constructed result instead
    result = {"weights": {"baseload": 1.0}}
    notes = shape_and_basis_notes(result, "nord", "chemicals", 20_000_000)
    assert any("zero weather driven shape mismatch" in n for n in notes)
