from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[2] / "src" / "dashboard" / "app.py")


def test_dashboard_runs_and_recommends_without_crashing():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=240)
    assert not at.exception

    at.button[0].click().run(timeout=240)
    assert not at.exception
    assert "Why this recommendation" in [s.value for s in at.subheader]


def test_tiny_consumer_runs_cleanly_and_explains_the_screened_out_types():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=240)
    at.selectbox[1].set_value("office_services")  # archetype
    at.number_input[0].set_value(0.1)  # annual consumption, GWh
    at.checkbox[1].set_value(False)  # no VPPA

    at.button[0].click().run(timeout=240)
    assert not at.exception
    assert any("Baseload PPA screened out" in m.value for m in at.markdown)
