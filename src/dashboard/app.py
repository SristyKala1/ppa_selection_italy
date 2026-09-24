import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from optimization.portfolio import recommend
from explainability.rationale import contract_rationale, shape_and_basis_notes, screening_notes
from scenarios.load_profile import ARCHETYPES

with open(PROJECT_ROOT / "config.yaml") as f:
    config = yaml.safe_load(f)

ZONES = list(config["zones"].keys())

RISK_LEVELS = {
    "Minimize cost": 0,
    "Balanced": 3,
    "Risk averse": 8,
    "Very risk averse": 20,
}

st.set_page_config(page_title="PPA Portfolio Selector", layout="wide")
st.title("Renewable PPA Portfolio Selector")
st.caption("CVaR-based portfolio recommendation for Italian industrial electricity buyers")

with st.sidebar:
    st.header("Factory profile")
    zone = st.selectbox("Zone", ZONES)
    archetype = st.selectbox("Industry type", list(ARCHETYPES.keys()))
    annual_kwh = st.number_input("Annual consumption (kWh)", min_value=100_000, value=20_000_000, step=100_000)
    has_wholesale_market_access = st.checkbox("Has wholesale market access")

    st.header("Virtual PPA")
    use_vppa = st.checkbox("Consider Virtual PPA (cross-zone)", value=True)
    reference_zone = None
    if use_vppa:
        other_zones = [z for z in ZONES if z != zone]
        reference_zone = st.selectbox("Reference zone", other_zones)

    st.header("Risk appetite")
    risk_label = st.select_slider("Risk aversion", options=list(RISK_LEVELS.keys()), value="Balanced")
    rho = RISK_LEVELS[risk_label]

    run = st.button("Recommend portfolio", type="primary")

if run:
    result = recommend(
        zone, archetype, annual_kwh, rho,
        reference_zone=reference_zone,
        has_wholesale_market_access=has_wholesale_market_access,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Expected cost (15yr NPV)", f"€{result['expected_cost']/1e6:.2f}M")
    col2.metric("CVaR (worst 5%)", f"€{result['cvar']/1e6:.2f}M")
    if "expected_cost_change" in result:
        col3.metric("Expected saving vs. spot", f"€{-result['expected_cost_change']/1e6:.2f}M")
        col4.metric("CVaR reduction vs. spot", f"€{result['cvar_reduction']/1e6:.2f}M")

    st.subheader("Recommended portfolio")
    weights = pd.Series(result["weights"]).sort_values(ascending=False)
    weights = weights[weights > 0.001]
    st.bar_chart(weights)

    st.subheader("Why this mix")
    for line in contract_rationale(result):
        st.write(f"- {line}")

    st.subheader("What's driving each type's cost and risk")
    for line in shape_and_basis_notes(result, zone, archetype, annual_kwh, reference_zone=reference_zone):
        st.write(f"- {line}")

    if not result["eligible"]:
        st.warning("No renewable PPA types are eligible for this profile, staying on spot is the only option.")

    notes = screening_notes(zone, annual_kwh, has_wholesale_market_access=has_wholesale_market_access,
                             reference_zone=reference_zone)
    if notes:
        st.subheader("Why other types aren't showing up")
        for line in notes:
            st.write(f"- {line}")
else:
    st.write("Set your factory profile in the sidebar and click Recommend portfolio.")
