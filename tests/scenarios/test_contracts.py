import numpy as np
import pytest

from scenarios.contracts import annual_residual_mwh, contract_cost_matrices, zonal_basis_risk
from scenarios.load_profile import load_profile_for_archetype
from scenarios.price_scenarios import (
    START_YEAR, END_YEAR, N_PRICE_PATHS, SCENARIOS, ZONE_STRUCTURAL_OFFSET_EUR_PER_MWH,
)


def test_returns_a_matrix_per_type_including_vppa_when_reference_zone_given():
    matrices = contract_cost_matrices("nord", "chemicals", 20_000_000, reference_zone="sicilia")
    assert set(matrices) == {"pap_solar", "pap_wind", "sleeved", "sleeved_wind", "baseload", "spot_only",
                             "vppa_solar", "vppa_wind"}


def test_vppa_missing_without_a_reference_zone():
    matrices = contract_cost_matrices("nord", "chemicals", 20_000_000)
    assert "vppa_solar" not in matrices
    assert "vppa_wind" not in matrices


def test_matrix_shape_is_15_contract_years_by_all_scenarios():
    matrices = contract_cost_matrices("nord", "chemicals", 20_000_000)
    assert matrices["pap_solar"].shape == (15, len(SCENARIOS) * N_PRICE_PATHS * (END_YEAR - START_YEAR + 1))


def test_costs_are_all_positive():
    matrices = contract_cost_matrices("nord", "chemicals", 20_000_000, reference_zone="sicilia")
    for name, matrix in matrices.items():
        assert (matrix > 0).all().all(), f"{name} has a non-positive cost somewhere"


def test_sleeved_is_pap_plus_a_positive_fee_for_both_technologies():
    matrices = contract_cost_matrices("sicilia", "chemicals", 20_000_000)
    assert (matrices["sleeved"] - matrices["pap_solar"] > 0).all().all()
    assert (matrices["sleeved_wind"] - matrices["pap_wind"] > 0).all().all()


def test_annual_residual_covers_every_weather_year_and_is_never_negative():
    load = load_profile_for_archetype("chemicals", 20_000_000)
    residual = annual_residual_mwh("solar", "nord", 2, load)
    assert len(residual) == END_YEAR - START_YEAR + 1
    assert (residual >= 0).all()


def test_basis_risk_against_own_zone_is_zero():
    basis = zonal_basis_risk("nord", "nord")
    assert np.allclose(basis.to_numpy(), 0.0)


def test_basis_risk_between_different_zones_has_a_real_nonzero_mean():
    # before the structural offset was added, this used to average to zero by
    # construction no matter which two zones you picked, that was the bug
    basis = zonal_basis_risk("nord", "sicilia")
    expected = ZONE_STRUCTURAL_OFFSET_EUR_PER_MWH["nord"] - ZONE_STRUCTURAL_OFFSET_EUR_PER_MWH["sicilia"]
    assert basis.to_numpy().mean() == pytest.approx(expected, abs=0.05)
