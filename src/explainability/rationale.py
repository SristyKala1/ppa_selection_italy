import re

from optimization.portfolio import _cvar
from scenarios.contracts import (
    CAPTURE_BY_TECH, HOURS_PER_YEAR, annual_residual_mwh, mw_for_coverage, zonal_basis_risk,
)
from scenarios.eligibility import MIN_SOLAR_CF, MIN_WIND_CF, MIN_BASELOAD_VOLUME_MWH
from scenarios.load_profile import load_profile_for_archetype
from scenarios.price_scenarios import ZONES, zone_annual_cf

TECH_BY_TYPE = {"pap_solar": "solar", "pap_wind": "wind", "sleeved": "solar", "sleeved_wind": "wind"}

CONTRACT_LABELS = {
    "pap_solar": "Solar PPA",
    "pap_wind": "Wind PPA",
    "sleeved": "Sleeved solar PPA",
    "sleeved_wind": "Sleeved wind PPA",
    "baseload": "Baseload PPA",
    "vppa_solar": "Virtual solar PPA",
    "vppa_wind": "Virtual wind PPA",
    "spot_only": "Stay on spot",
}

SIZE_SUFFIX = re.compile(r"^(.+)_(\d+)%$")


def split_contract_name(t):
    match = SIZE_SUFFIX.match(t)
    if match:
        return match.group(1), int(match.group(2)) / 100
    return t, 1.0


def display_name(t):
    base, share = split_contract_name(t)
    label = CONTRACT_LABELS.get(base, base)
    if SIZE_SUFFIX.match(t):
        return f"{label} sized at {share:.0%} of consumption"
    return label


def contract_rationale(result, min_weight=0.01):
    weights = result["weights"]
    npvs = result["contract_npvs"]

    contract_types = [t for t in npvs if t != "spot_only"]
    stats = {t: {"mean": npvs[t].mean(), "cvar": _cvar(npvs[t])} for t in contract_types}
    cheapest = min(stats, key=lambda t: stats[t]["mean"])
    safest = min(stats, key=lambda t: stats[t]["cvar"])

    chosen = [(t, w) for t, w in sorted(weights.items(), key=lambda kv: -kv[1]) if w >= min_weight and t in stats]

    lines = []
    for t, _ in chosen:
        s = stats[t]
        name = display_name(t)
        if t == cheapest and t == safest:
            lines.append(f"{name}: cheapest option and lowest tail risk, no tradeoff to make.")
        elif t == cheapest:
            ref = stats[safest]
            gap = s["cvar"] - ref["cvar"]
            lines.append(
                f"{name}: cheapest on average (€{s['mean']/1e6:.2f}M), but its CVaR "
                f"(€{s['cvar']/1e6:.2f}M) is €{gap/1e6:.2f}M worse than the safest option's "
                f"({display_name(safest)})."
            )
        else:
            ref = stats[cheapest]
            premium = s["mean"] - ref["mean"]
            saved = ref["cvar"] - s["cvar"]
            lines.append(
                f"{name}: costs €{premium/1e6:.2f}M more on average than the cheapest "
                f"option ({display_name(cheapest)}), but cuts CVaR by €{saved/1e6:.2f}M, "
                f"worth it at this risk setting."
            )

    if "do_nothing_expected" in result:
        lines.append(
            f"Vs. staying on spot: saves €{-result['expected_cost_change']/1e6:.2f}M "
            f"expected, cuts CVaR by €{result['cvar_reduction']/1e6:.2f}M."
        )
    return lines


def shape_and_basis_notes(result, zone, archetype, annual_kwh, reference_zone=None, min_weight=0.01):
    weights = result["weights"]
    load = load_profile_for_archetype(archetype, annual_kwh)
    annual_load_mwh = load.sum() / 1000

    notes = []
    for t, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        if w < min_weight or t == "spot_only":
            continue
        base, share = split_contract_name(t)
        name = display_name(t)
        if base in TECH_BY_TYPE:
            tech = TECH_BY_TYPE[base]
            mw = mw_for_coverage(tech, zone, share, annual_load_mwh)
            residual = annual_residual_mwh(tech, zone, mw, load)
            uncovered_pct = residual.mean() / annual_load_mwh
            notes.append(
                f"{name}: {tech} generation leaves {uncovered_pct:.0%} of your load uncovered on "
                f"average, hour by hour (bought back at spot), a shape mismatch cost, not just "
                f"a total output shortfall, and it varies by weather year (std {residual.std()/annual_load_mwh:.1%} "
                f"of annual load), which is part of why it carries scenario to scenario cost variance."
            )
        elif base == "baseload":
            notes.append(
                f"{name}: a fixed {share * annual_load_mwh / HOURS_PER_YEAR:.1f} MW block delivered flat across all 8,760 hours, "
                f"by construction it has zero weather driven shape mismatch (the residual vs. your load "
                f"is a constant, not a weather year varying one), which is the direct reason its cost "
                f"has the lowest variance of any contract type in this portfolio."
            )
        elif base in ("vppa_solar", "vppa_wind") and reference_zone is not None:
            tech = base.removeprefix("vppa_")
            basis = zonal_basis_risk(zone, reference_zone)
            notes.append(
                f"{name}: you buy 100% of load at {zone}'s own price, but the CfD settles against "
                f"{reference_zone}'s price, the gap (basis risk) averages "
                f"€{basis.to_numpy().mean():.1f}/MWh with a scenario spread (std) of "
                f"€{basis.to_numpy().std():.1f}/MWh, and {tech} there only earns "
                f"{CAPTURE_BY_TECH[tech][reference_zone]:.0%} of the average price (capture rate)."
            )
    return notes


def screening_notes(zone, annual_kwh, has_wholesale_market_access=False, reference_zone=None):
    annual_load_mwh = annual_kwh / 1000
    solar_cf = zone_annual_cf("solar", zone).mean()
    wind_cf = zone_annual_cf("wind", zone).mean()

    notes = []

    if solar_cf < MIN_SOLAR_CF:
        notes.append(
            f"Solar PPA and sleeved solar PPA screened out, {zone}'s solar capacity factor "
            f"({solar_cf:.1%}) is below the {MIN_SOLAR_CF:.0%} minimum."
        )

    if wind_cf < MIN_WIND_CF:
        notes.append(
            f"Wind PPA and sleeved wind PPA screened out, {zone}'s wind capacity factor ({wind_cf:.1%}) "
            f"is below the {MIN_WIND_CF:.0%} minimum."
        )

    if annual_load_mwh < MIN_BASELOAD_VOLUME_MWH:
        notes.append(
            f"Baseload PPA screened out, annual load ({annual_load_mwh:,.0f} MWh) is below "
            f"the {MIN_BASELOAD_VOLUME_MWH:,.0f} MWh minimum for a firmed block."
        )

    if reference_zone is not None:
        for tech, threshold in (("wind", MIN_WIND_CF), ("solar", MIN_SOLAR_CF)):
            ref_cf = zone_annual_cf(tech, reference_zone).mean()
            if ref_cf < threshold:
                # just which zones pass the same threshold, not which one would be best (that's the optimizer's job)
                passing = [z for z in ZONES if z not in (zone, reference_zone)
                           and zone_annual_cf(tech, z).mean() >= threshold]
                notes.append(
                    f"Virtual {tech} PPA screened out, {reference_zone}'s {tech} capacity factor ({ref_cf:.1%}) "
                    f"is below the {threshold:.0%} minimum. Reference zones that pass: {', '.join(passing)}."
                )

    return notes
