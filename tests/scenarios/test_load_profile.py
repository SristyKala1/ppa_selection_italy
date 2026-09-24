import pytest

from scenarios.load_profile import load_profile_for_archetype


def test_rejects_unknown_archetype():
    with pytest.raises(ValueError):
        load_profile_for_archetype("spaceship_yard", 20_000_000)


def test_rejects_zero_annual_kwh():
    with pytest.raises(ValueError):
        load_profile_for_archetype("chemicals", 0)


def test_rejects_negative_annual_kwh():
    with pytest.raises(ValueError):
        load_profile_for_archetype("chemicals", -500)


def test_scales_to_the_requested_annual_total():
    load = load_profile_for_archetype("chemicals", 20_000_000)
    assert load.sum() == pytest.approx(20_000_000, rel=1e-6)
