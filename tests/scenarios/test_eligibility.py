from scenarios.eligibility import eligible_contracts


def test_nord_with_market_access_gets_pap_solar_not_pap_wind():
    eligible = eligible_contracts("nord", 20_000_000, has_wholesale_market_access=True)
    assert "pap_solar" in eligible
    assert "pap_wind" not in eligible  # nord wind CF (~7.2%) is below the 10% minimum
    assert "sleeved" not in eligible


def test_nord_without_market_access_gets_sleeved_instead_of_pap_solar():
    eligible = eligible_contracts("nord", 20_000_000, has_wholesale_market_access=False)
    assert "sleeved" in eligible
    assert "pap_solar" not in eligible
    assert "pap_wind" not in eligible


def test_sicilia_with_market_access_gets_both_pap_types():
    eligible = eligible_contracts("sicilia", 20_000_000, has_wholesale_market_access=True)
    assert "pap_solar" in eligible
    assert "pap_wind" in eligible


def test_baseload_needs_enough_volume():
    small = eligible_contracts("nord", 100_000, has_wholesale_market_access=True)
    large = eligible_contracts("nord", 20_000_000, has_wholesale_market_access=True)
    assert "baseload" not in small
    assert "baseload" in large


def test_vppa_depends_on_the_reference_zones_wind_cf():
    strong_wind_ref = eligible_contracts("nord", 20_000_000, reference_zone="sicilia")
    weak_wind_ref = eligible_contracts("nord", 20_000_000, reference_zone="nord")
    assert "vppa" in strong_wind_ref
    assert "vppa" not in weak_wind_ref


def test_spot_only_is_never_in_the_eligible_set():
    eligible = eligible_contracts("nord", 20_000_000, has_wholesale_market_access=True)
    assert "spot_only" not in eligible
