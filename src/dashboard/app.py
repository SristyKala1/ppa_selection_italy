import sys
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import yaml
from plotly.subplots import make_subplots

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from optimization.portfolio import ALPHA, DISCOUNT_RATE, _cvar, candidate_npvs, tail_frontier
from explainability.rationale import (
    CONTRACT_LABELS, contract_rationale, screening_notes, shape_and_basis_notes, split_contract_name,
)
from scenarios.contracts import (
    COUNTERPARTY_SPREAD, HOURS_PER_YEAR, SLEEVING_MARGIN, STRIKE_PRICE_SOLAR, STRIKE_PRICE_WIND,
    CAPTURE_BY_TECH, baseload_strike, mw_for_coverage,
)
from scenarios.load_profile import ARCHETYPES
from scenarios.price_scenarios import build_zonal_price_matrix

with open(PROJECT_ROOT / "config.yaml") as f:
    config = yaml.safe_load(f)

ZONES = list(config["zones"].keys())
TOLERANCE_STEPS = list(range(0, 101, 10))  # percent

# one fixed colour per contract type (reference dark palette, slots 1-7), spot stays neutral grey
TYPE_COLORS = {
    "pap_solar": "#3987e5", "vppa_wind": "#d95926", "baseload": "#199e70",
    "sleeved": "#c98500", "pap_wind": "#d55181", "vppa_solar": "#008300", "sleeved_wind": "#9085e9",
}
SPOT_COLOR = "#898781"
TAIL_COLOR = "#d03b3b"
INK, INK_MUTED, GRID, AXIS = "#ffffff", "#898781", "#2c2c2a", "#383835"


def pretty(name):
    return name.replace("_", "-").title() if "_" in name else name.title()


def pretty_archetype(name):
    return name.replace("_", " ").capitalize()


@st.cache_data(show_spinner=False)
def cached_candidates(zone, archetype, annual_kwh, reference_zone, has_wholesale_market_access):
    return candidate_npvs(zone, archetype, annual_kwh, reference_zone, has_wholesale_market_access)


@st.cache_data(show_spinner=False)
def cached_frontier(zone, archetype, annual_kwh, reference_zone, has_wholesale_market_access):
    _, npvs = cached_candidates(zone, archetype, annual_kwh, reference_zone, has_wholesale_market_access)
    by_fraction = tail_frontier(npvs, [p / 100 for p in TOLERANCE_STEPS])
    return {p: by_fraction[p / 100] for p in TOLERANCE_STEPS}


def coverage_by_type(weights):
    # a weight w on a contract sized at s% of consumption ~ a contract covering w*s%
    coverage = {}
    for t, w in weights.items():
        base, share = split_contract_name(t)
        if base == "spot_only" or w < 0.005:
            continue
        coverage[base] = coverage.get(base, 0) + w * share
    return dict(sorted(coverage.items(), key=lambda kv: -kv[1]))


def style(fig, height):
    fig.update_layout(
        height=height, margin=dict(l=70, r=30, t=30, b=60),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK_MUTED, size=13),
        hoverlabel=dict(bgcolor="#1a1a19", bordercolor=AXIS, font_color=INK),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font_color=INK),
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, automargin=True)
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, automargin=True)
    return fig


def coverage_chart(coverage):
    unhedged = max(1 - sum(coverage.values()), 0)
    fig = go.Figure()
    segments = [(CONTRACT_LABELS[b], c, TYPE_COLORS[b]) for b, c in coverage.items()]
    segments.append(("Bought at spot", unhedged, SPOT_COLOR))
    for label, share, color in segments:
        if share < 0.005:
            continue
        fig.add_bar(
            y=[""], x=[share * 100], orientation="h", name=label,
            marker=dict(color=color, line=dict(color="#0d0d0d", width=2)),
            text=f"{share:.0%}" if share >= 0.06 else "", textposition="inside",
            insidetextanchor="middle", textfont=dict(color=INK, size=14),
            hovertemplate=f"{label}: {share:.1%} of annual consumption<extra></extra>",
        )
    fig.update_layout(barmode="stack", showlegend=True, bargap=0.3, legend_traceorder="normal")
    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(showticklabels=False, showgrid=False)
    fig = style(fig, 150)
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    return fig


def frontier_chart(frontier, selected, spot_npv):
    tols = sorted(frontier)
    exp = [frontier[t]["expected_cost"] / 1e6 for t in tols]
    cvar = [frontier[t]["cvar"] / 1e6 for t in tols]
    fig = go.Figure()
    fig.add_scatter(
        x=exp, y=cvar, mode="lines+markers", name="Efficient portfolios",
        line=dict(color=AXIS, width=2), marker=dict(color=SPOT_COLOR, size=9),
        customdata=[f"{100 - t}%" for t in tols],
        hovertemplate="Protection %{customdata}<br>Expected €%{x:.2f}M<br>CVaR €%{y:.2f}M<extra></extra>",
    )
    fig.add_scatter(
        x=[spot_npv.mean() / 1e6], y=[_cvar(spot_npv) / 1e6], mode="markers+text", name="Stay on spot",
        marker=dict(color="rgba(0,0,0,0)", size=12, line=dict(color=SPOT_COLOR, width=2)),
        text=["Stay on spot"], textposition="top left", textfont=dict(color=INK_MUTED),
        hovertemplate="Stay on spot<br>Expected €%{x:.2f}M<br>CVaR €%{y:.2f}M<extra></extra>",
    )
    s = frontier[selected]
    fig.add_scatter(
        x=[s["expected_cost"] / 1e6], y=[s["cvar"] / 1e6], mode="markers+text", name="Your portfolio",
        marker=dict(color=TYPE_COLORS["pap_solar"], size=18, line=dict(color="#0d0d0d", width=2)),
        text=["Your portfolio"], textposition="middle right", textfont=dict(color=INK),
        hovertemplate="Your portfolio<br>Expected €%{x:.2f}M<br>CVaR €%{y:.2f}M<extra></extra>",
    )
    fig.update_xaxes(title="Expected cost (€M, 15-yr NPV)", tickprefix="€")
    fig.update_yaxes(title="Worst-case cost, CVaR 95% (€M)", tickprefix="€")
    fig.update_layout(showlegend=False)
    return style(fig, 460)


def distribution_chart(spot_npv, portfolio_npv):
    edges = np.histogram_bin_edges(np.concatenate([spot_npv, portfolio_npv]) / 1e6, bins=45)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=("Stay on spot", "Recommended portfolio"))
    for row, npv in ((1, spot_npv), (2, portfolio_npv)):
        values = npv.to_numpy() / 1e6
        counts, _ = np.histogram(values, bins=edges)
        threshold = np.quantile(values, ALPHA)
        centers = (edges[:-1] + edges[1:]) / 2
        in_tail = edges[1:] > threshold
        base_color = SPOT_COLOR if row == 1 else TYPE_COLORS["pap_solar"]
        for mask, color, name in ((~in_tail, base_color, "Scenarios"), (in_tail, TAIL_COLOR, "Worst 5% (CVaR tail)")):
            fig.add_bar(
                x=centers[mask], y=counts[mask], width=(edges[1] - edges[0]) * 0.9,
                marker=dict(color=color), name=name, showlegend=False,
                hovertemplate="€%{x:.1f}M: %{y} scenarios<extra></extra>", row=row, col=1,
            )
        cvar = _cvar(npv) / 1e6
        fig.add_vline(x=cvar, line=dict(color=INK, width=1.5, dash="dash"), row=row, col=1)
        fig.add_annotation(x=cvar, y=1, yref=f"y{'' if row == 1 else row} domain", text=f"CVaR €{cvar:.1f}M",
                           showarrow=False, xanchor="left", xshift=6, font=dict(color=INK), row=row, col=1)
    fig.update_annotations(selector=dict(text="Stay on spot"), font=dict(color=INK, size=14), x=0, xanchor="left")
    fig.update_annotations(selector=dict(text="Recommended portfolio"), font=dict(color=INK, size=14),
                           x=0, xanchor="left")
    fig.update_xaxes(title="15-year cost NPV (€M)", tickprefix="€", showticklabels=True, row=2, col=1)
    fig.update_yaxes(title_text="Scenarios", title_standoff=8)
    fig.update_layout(bargap=0)
    return style(fig, 460)


def contract_card(base, coverage, zone, annual_load_mwh, reference_zone):
    if base == "pap_solar":
        mw = mw_for_coverage("solar", zone, coverage, annual_load_mwh)
        rows = [("Delivery", f"Physical, {pretty(zone)}"), ("Strike", f"€{STRIKE_PRICE_SOLAR + COUNTERPARTY_SPREAD:.2f}/MWh"),
                ("Settlement", "Pay-as-produced"), ("Capacity", f"{mw:.1f} MW solar")]
    elif base == "pap_wind":
        mw = mw_for_coverage("wind", zone, coverage, annual_load_mwh)
        rows = [("Delivery", f"Physical, {pretty(zone)}"), ("Strike", f"€{STRIKE_PRICE_WIND + COUNTERPARTY_SPREAD:.2f}/MWh"),
                ("Settlement", "Pay-as-produced"), ("Capacity", f"{mw:.1f} MW wind")]
    elif base in ("sleeved", "sleeved_wind"):
        tech = "wind" if base == "sleeved_wind" else "solar"
        mw = mw_for_coverage(tech, zone, coverage, annual_load_mwh)
        strike = (STRIKE_PRICE_WIND if tech == "wind" else STRIKE_PRICE_SOLAR) + COUNTERPARTY_SPREAD + SLEEVING_MARGIN
        rows = [("Delivery", f"Physical via supplier, {pretty(zone)}"), ("Strike", f"€{strike:.2f}/MWh incl. sleeving"),
                ("Settlement", "Pay-as-produced"), ("Capacity", f"{mw:.1f} MW {tech}")]
    elif base == "baseload":
        strike = baseload_strike(build_zonal_price_matrix(zone))
        rows = [("Delivery", f"Physical, {pretty(zone)}"), ("Strike", f"€{strike:.2f}/MWh"),
                ("Settlement", "Flat block, every hour"), ("Capacity", f"{coverage * annual_load_mwh / HOURS_PER_YEAR:.1f} MW flat")]
    else:  # vppa_solar / vppa_wind
        tech = base.removeprefix("vppa_")
        mw = mw_for_coverage(tech, reference_zone, coverage, annual_load_mwh)
        strike = (STRIKE_PRICE_WIND if tech == "wind" else STRIKE_PRICE_SOLAR) + COUNTERPARTY_SPREAD
        rows = [("Delivery", "Financial only (CfD)"), ("Strike", f"€{strike:.2f}/MWh"),
                ("Settlement", f"vs. {pretty(reference_zone)} price × {CAPTURE_BY_TECH[tech][reference_zone]:.2f} capture"),
                ("Capacity", f"{mw:.1f} MW {tech} in {pretty(reference_zone)}")]

    lines = "".join(
        f"<div style='display:flex;justify-content:space-between;gap:16px;padding:4px 0;"
        f"border-top:1px solid {GRID}'><span style='color:{INK_MUTED}'>{label}</span>"
        f"<span style='text-align:right'>{value}</span></div>"
        for label, value in rows
    )
    with st.container(border=True):
        st.markdown(f"**{CONTRACT_LABELS[base]}**")
        st.caption(f"Covers ≈{coverage:.0%} of annual consumption")
        st.markdown(f"<div style='font-size:0.9rem'>{lines}</div>", unsafe_allow_html=True)


st.set_page_config(page_title="PPA Portfolio Selector", layout="wide")
st.title("Renewable PPA Portfolio Selector")
st.caption("Risk-aware PPA portfolio recommendation for Italian industrial electricity buyers")

with st.sidebar:
    st.header("Factory profile")
    zone = st.selectbox("Zone", ZONES, format_func=pretty)
    archetype = st.selectbox("Industry type", list(ARCHETYPES.keys()), format_func=pretty_archetype)
    annual_gwh = st.number_input("Annual consumption (GWh)", min_value=0.1, value=20.0, step=0.5, format="%.1f")
    has_wholesale_market_access = st.checkbox("Has wholesale market access")

    st.header("Virtual PPA")
    use_vppa = st.checkbox("Consider Virtual PPA (cross-zone)", value=True)
    reference_zone = None
    if use_vppa:
        other_zones = [z for z in ZONES if z != zone]
        reference_zone = st.selectbox("Reference zone", other_zones, format_func=pretty)

    run = st.button("Recommend portfolio", type="primary")

    st.header("Risk appetite")
    protection_pct = st.slider(
        "Protection against bad years", 0, 100, 50, step=10, format="%d%%",
        help="How much of the avoidable worst-case cost to remove. 0% = cheapest portfolio, "
             "no extra protection. 100% = lowest worst-case cost reachable, whatever it costs on average.",
    )
    # the model works in tail tolerance, the mirror image of protection
    tolerance_pct = 100 - protection_pct

annual_kwh = annual_gwh * 1e6
profile = (zone, archetype, annual_kwh, reference_zone, has_wholesale_market_access)
if run:
    st.session_state["profile"] = profile

# one slot for the prompt and the loading message, so the spinner replaces the prompt instead of overlapping it
status_slot = st.empty()
if "profile" not in st.session_state:
    status_slot.info("Set your factory profile in the sidebar and click **Recommend portfolio**.")
    st.stop()

if st.session_state["profile"] != profile:
    st.info("Inputs changed, click **Recommend portfolio** to update the results.")

zone, archetype, annual_kwh, reference_zone, has_wholesale_market_access = st.session_state["profile"]
with status_slot.container():
    with st.spinner("Simulating every price and weather scenario, the first run for a new profile takes about a minute..."):
        eligible, npvs = cached_candidates(*st.session_state["profile"])
        frontier = cached_frontier(*st.session_state["profile"])
status_slot.empty()
result = dict(frontier[tolerance_pct], eligible=sorted(eligible), contract_npvs=npvs)
spot_npv = npvs["spot_only"]
annual_load_mwh = annual_kwh / 1000

n_scenarios = len(spot_npv)
ref_text = f" · VPPA reference: {pretty(reference_zone)}" if reference_zone else ""
st.markdown(
    f"#### {pretty_archetype(archetype)} · {pretty(zone)} · {annual_kwh / 1e6:.1f} GWh/yr{ref_text}"
)
st.caption(f"{n_scenarios:,} price × weather scenarios · 15-year contracts · costs as NPV at "
           f"{DISCOUNT_RATE:.0%} · solved with HiGHS")

if not result["eligible"]:
    st.warning("No renewable PPA types are eligible for this profile, staying on spot is the only option.")

coverage = coverage_by_type(result["weights"])
renewable = sum(c for b, c in coverage.items() if b != "baseload")
k1, k2, k3, k4 = st.columns(4)
def money(value):
    # short enough to fit a card on a laptop screen
    return f"€{value/1e6:.1f}M" if abs(value) >= 1e6 else f"€{value/1e3:.0f}k"


def money_delta(value):
    # leading sign so streamlit reads the direction correctly ("-€1.4M", not "€-1.4M")
    sign = "-" if value < 0 else "+"
    return f"{sign}{money(abs(value))} vs. spot"


with k1.container(border=True):
    st.metric("Expected cost", money(result["expected_cost"]),
              delta=money_delta(result["expected_cost_change"]), delta_color="inverse",
              help="Average 15-year cost NPV across all scenarios.")
with k2.container(border=True):
    st.metric("Worst-case cost", money(result["cvar"]),
              delta=money_delta(-result["cvar_reduction"]), delta_color="inverse",
              help="CVaR 95%: the average cost of the worst 5% of scenarios.")
with k3.container(border=True):
    st.metric("Under contract", f"{sum(coverage.values()):.0%}", delta="of consumption",
              delta_color="off", delta_arrow="off",
              help="Share of annual consumption locked in by the recommended contracts.")
with k4.container(border=True):
    st.metric("Renewable", f"{renewable:.0%}", delta="of consumption",
              delta_color="off", delta_arrow="off",
              help="Covered by solar, wind and virtual PPAs (baseload excluded).")

with st.container(border=True):
    st.markdown("**How your consumption is covered**")
    st.plotly_chart(coverage_chart(coverage), width="stretch", theme=None,
                    config={"displayModeBar": False})
    if coverage:
        cols = st.columns(max(len(coverage), 3))
        for col, (base, cov) in zip(cols, coverage.items()):
            with col:
                contract_card(base, cov, zone, annual_load_mwh, reference_zone)

left, right = st.columns([2, 3])
with left.container(border=True):
    st.markdown("**Cost vs. tail risk**")
    st.caption("Each grey point is the cheapest portfolio for one protection level.")
    st.plotly_chart(frontier_chart(frontier, tolerance_pct, spot_npv), width="stretch", theme=None,
                    config={"displayModeBar": False})
with right.container(border=True):
    st.markdown("**Cost across every scenario**")
    st.caption("Each bar counts scenarios. Red bars are the worst 5%, whose average is the CVaR.")
    st.plotly_chart(distribution_chart(spot_npv, result["portfolio_npv"]), width="stretch", theme=None,
                    config={"displayModeBar": False})

st.subheader("Why this recommendation")
why_tab, drivers_tab, screened_tab = st.tabs(["Why this mix", "Cost and risk drivers", "Screened-out contracts"])
with why_tab:
    for line in contract_rationale(result):
        st.markdown(f"- {line}")
with drivers_tab:
    for line in shape_and_basis_notes(result, zone, archetype, annual_kwh, reference_zone=reference_zone):
        st.markdown(f"- {line}")
with screened_tab:
    notes = screening_notes(zone, annual_kwh, has_wholesale_market_access=has_wholesale_market_access,
                            reference_zone=reference_zone)
    if notes:
        for line in notes:
            st.markdown(f"- {line}")
    else:
        st.markdown("Every contract type is eligible for this profile.")
