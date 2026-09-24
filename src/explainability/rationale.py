from optimization.portfolio import _cvar
from scenarios.contracts import annual_residual_mwh, zonal_basis_risk
from scenarios.eligibility import MIN_SOLAR_CF, MIN_WIND_CF, MIN_BASELOAD_VOLUME_MWH
from scenarios.load_profile import load_profile_for_archetype
from scenarios.price_scenarios import zone_annual_cf

TECH_BY_TYPE = {"pap_solar": "solar", "pap_wind": "wind", "sleeved": "solar"}


def contract_rationale(result, min_weight=0.01):
    weights = result["weights"]
    npvs = result["contract_npvs"]

    contract_types = [t for t in npvs if t != "spot_only"]
    stats = {t: {"mean": npvs[t].mean(), "cvar": _cvar(npvs[t])} for t in contract_types}
    cheapest = min(stats, key=lambda t: stats[t]["mean"])
    safest = min(stats, key=lambda t: stats[t]["cvar"])

    chosen = [(t, w) for t, w in sorted(weights.items(), key=lambda kv: -kv[1]) if w >= min_weight and t in stats]

    lines = []
    for t, w in chosen:
        s = stats[t]
        if t == cheapest and t == safest:
            lines.append(f"{t} ({w:.0%}): cheapest option and lowest tail risk, no tradeoff to make.")
        elif t == cheapest:
            ref = stats[safest]
            gap = s["cvar"] - ref["cvar"]
            lines.append(
                f"{t} ({w:.0%}): cheapest on average (€{s['mean']/1e6:.2f}M), but its CVaR "
                f"(€{s['cvar']/1e6:.2f}M) is €{gap/1e6:.2f}M worse than {safest}'s tail."
            )
        else:
            ref = stats[cheapest]
            premium = s["mean"] - ref["mean"]
            saved = ref["cvar"] - s["cvar"]
            lines.append(
                f"{t} ({w:.0%}): costs €{premium/1e6:.2f}M more on average than the cheapest "
                f"option ({cheapest}), but cuts CVaR by €{saved/1e6:.2f}M, worth it at this risk setting."
            )

    if "do_nothing_expected" in result:
        lines.append(
            f"Vs. staying on spot: saves €{-result['expected_cost_change']/1e6:.2f}M "
            f"expected, cuts CVaR by €{result['cvar_reduction']/1e6:.2f}M."
        )
    return lines


def shape_and_basis_notes(result, zone, archetype, annual_kwh, reference_zone=None,
                           contracted_mw=2, min_weight=0.01):
    weights = result["weights"]
    load = load_profile_for_archetype(archetype, annual_kwh)
    annual_load_mwh = load.sum() / 1000

    notes = []
    for t, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        if w < min_weight or t == "spot_only":
            continue
        if t in TECH_BY_TYPE:
            tech = TECH_BY_TYPE[t]
            residual = annual_residual_mwh(tech, zone, contracted_mw, load)
            uncovered_pct = residual.mean() / annual_load_mwh
            notes.append(
                f"{t}: {tech} generation leaves {uncovered_pct:.0%} of your load uncovered on "
                f"average, hour by hour (bought back at spot), a shape mismatch cost, not just "
                f"a total output shortfall, and it varies by weather year (std {residual.std()/annual_load_mwh:.1%} "
                f"of annual load), which is part of why {t} carries scenario to scenario cost variance."
            )
        elif t == "baseload":
            notes.append(
                f"baseload: a fixed {contracted_mw} MW block delivered flat across all 8,760 hours, "
                f"by construction it has zero weather driven shape mismatch (the residual vs. your load "
                f"is a constant, not a weather year varying one), which is the direct reason its cost "
                f"has the lowest variance of any contract type in this portfolio."
            )
        elif t == "vppa" and reference_zone is not None:
            basis = zonal_basis_risk(zone, reference_zone)
            notes.append(
                f"vppa: you buy 100% of load at {zone}'s own price, but the CfD settles against "
                f"{reference_zone}'s price, the gap (basis risk) averages "
                f"€{basis.to_numpy().mean():.1f}/MWh with a scenario spread (std) of "
                f"€{basis.to_numpy().std():.1f}/MWh, on top of the shape mismatch from wind CF alone."
            )
    return notes


def screening_notes(zone, annual_kwh, has_wholesale_market_access=False, reference_zone=None):
    annual_load_mwh = annual_kwh / 1000
    solar_cf = zone_annual_cf("solar", zone).mean()
    wind_cf = zone_annual_cf("wind", zone).mean()

    notes = []

    if solar_cf < MIN_SOLAR_CF:
        notes.append(
            f"pap_solar and sleeved screened out, {zone}'s solar capacity factor "
            f"({solar_cf:.1%}) is below the {MIN_SOLAR_CF:.0%} minimum."
        )

    if wind_cf < MIN_WIND_CF:
        notes.append(
            f"pap_wind screened out, {zone}'s wind capacity factor ({wind_cf:.1%}) "
            f"is below the {MIN_WIND_CF:.0%} minimum."
        )
    elif not has_wholesale_market_access:
        notes.append("pap_wind screened out, no wholesale market access (sleeved wind isn't modeled).")

    if annual_load_mwh < MIN_BASELOAD_VOLUME_MWH:
        notes.append(
            f"baseload screened out, annual load ({annual_load_mwh:,.0f} MWh) is below "
            f"the {MIN_BASELOAD_VOLUME_MWH:,.0f} MWh minimum for a firmed block."
        )

    if reference_zone is not None:
        ref_wind_cf = zone_annual_cf("wind", reference_zone).mean()
        if ref_wind_cf < MIN_WIND_CF:
            notes.append(
                f"vppa screened out, {reference_zone}'s wind capacity factor ({ref_wind_cf:.1%}) "
                f"is below the {MIN_WIND_CF:.0%} minimum."
            )

    return notes
