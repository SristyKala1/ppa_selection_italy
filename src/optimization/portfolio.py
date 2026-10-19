import pandas as pd
import pyomo.environ as pyo

from scenarios.contracts import contract_cost_matrices
from scenarios.eligibility import eligible_contracts
from scenarios.load_profile import ARCHETYPES
from scenarios.price_scenarios import ZONES

DISCOUNT_RATE = 0.08
ALPHA = 0.95

COVERAGE_SHARES = [0.1, 0.2, 0.3, 0.5, 0.75, 1.0]
SIZED_TYPES = {"pap_solar", "pap_wind", "sleeved", "sleeved_wind", "baseload", "vppa_solar", "vppa_wind"}


def scenario_npv(cost_matrix, discount_rate=DISCOUNT_RATE):
    years = cost_matrix.index
    factors = pd.Series(
        [(1 + discount_rate) ** -(year - years[0]) for year in years],
        index=years,
    )
    return cost_matrix.mul(factors, axis=0).sum(axis=0)


def _cvar(npv, alpha=ALPHA):
    worst = npv.sort_values(ascending=False).to_numpy()
    k = (1 - alpha) * len(worst)
    whole = int(k)
    return (worst[:whole].sum() + (k - whole) * worst[whole]) / k


def optimize_portfolio(cost_npvs, rho=0, alpha=ALPHA, cvar_budget=None):
    # either penalise tail cost (rho), or cap it (cvar_budget) and minimise expected cost
    if rho < 0:
        raise ValueError(f"rho must be >= 0, got {rho}")

    types = list(cost_npvs)
    index = cost_npvs[types[0]].index
    n = len(index)
    values = {t: cost_npvs[t].to_numpy() for t in types}
    cost = {(t, i): v for t in types for i, v in enumerate(values[t])}

    m = pyo.ConcreteModel()
    m.T = pyo.Set(initialize=types)
    m.S = pyo.RangeSet(0, n - 1)
    m.w = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.eta = pyo.Var(domain=pyo.Reals)
    m.z = pyo.Var(m.S, domain=pyo.NonNegativeReals)

    def scenario_cost(mm, i):
        return sum(mm.w[t] * cost[(t, i)] for t in types)

    m.weights_sum = pyo.Constraint(expr=sum(m.w[t] for t in types) == 1)
    m.tail = pyo.Constraint(m.S, rule=lambda mm, i: mm.z[i] >= scenario_cost(mm, i) - mm.eta)

    # linear in the weights, so the mean over scenarios is just each type's own mean
    expected = sum(m.w[t] * values[t].mean() for t in types)
    cvar = m.eta + sum(m.z[i] for i in m.S) / ((1 - alpha) * n)
    if cvar_budget is not None:
        m.budget = pyo.Constraint(expr=cvar <= cvar_budget)
    m.obj = pyo.Objective(expr=expected + rho * cvar, sense=pyo.minimize)

    outcome = pyo.SolverFactory("appsi_highs").solve(m)
    if outcome.solver.termination_condition != pyo.TerminationCondition.optimal:
        raise RuntimeError(f"solver did not converge: {outcome.solver.termination_condition}")

    raw = {t: max(pyo.value(m.w[t]), 0.0) for t in types}
    total = sum(raw.values())
    weights = {t: v / total for t, v in raw.items()}
    portfolio_npv = pd.Series(sum(weights[t] * values[t] for t in types), index=index)

    result = {
        "weights": weights,
        "expected_cost": portfolio_npv.mean(),
        "cvar": _cvar(portfolio_npv, alpha),
        "portfolio_npv": portfolio_npv,
    }
    if "spot_only" in cost_npvs:
        do_nothing = cost_npvs["spot_only"]
        result["do_nothing_expected"] = do_nothing.mean()
        result["do_nothing_cvar"] = _cvar(do_nothing, alpha)
        result["expected_cost_change"] = result["expected_cost"] - result["do_nothing_expected"]
        result["cvar_reduction"] = result["do_nothing_cvar"] - result["cvar"]
    return result


def candidate_npvs(zone, archetype, annual_kwh, reference_zone=None,
                   has_wholesale_market_access=False):
    if zone not in ZONES:
        raise ValueError(f"unknown zone '{zone}', expected one of {ZONES}")
    if reference_zone is not None and reference_zone not in ZONES:
        raise ValueError(f"unknown reference zone '{reference_zone}', expected one of {ZONES}")
    if archetype not in ARCHETYPES:
        raise ValueError(f"unknown archetype '{archetype}', expected one of {list(ARCHETYPES)}")
    if annual_kwh <= 0:
        raise ValueError(f"annual_kwh must be positive, got {annual_kwh}")

    eligible = eligible_contracts(
        zone, annual_kwh,
        has_wholesale_market_access=has_wholesale_market_access,
        reference_zone=reference_zone,
    )

    # no point building vppa matrices for a reference zone the screen already rejected
    vppa_reference = reference_zone if eligible & {"vppa_solar", "vppa_wind"} else None
    selected = {}
    for share in COVERAGE_SHARES:
        matrices = contract_cost_matrices(zone, archetype, annual_kwh, coverage=share,
                                           reference_zone=vppa_reference)
        for name in sorted(eligible & SIZED_TYPES):
            selected[f"{name}_{share:.0%}"] = matrices[name]
    # spot has no size, so it goes in once
    selected["spot_only"] = matrices["spot_only"]

    return eligible, {name: scenario_npv(mat) for name, mat in selected.items()}


def tail_frontier(cost_npvs, tolerances):
    # tolerance 1 = accept the cheapest portfolio's tail, 0 = lowest tail reachable
    for tol in tolerances:
        if not 0 <= tol <= 1:
            raise ValueError(f"tail_tolerance must be between 0 and 1, got {tol}")
    cheapest = optimize_portfolio(cost_npvs, rho=0)
    safest = optimize_portfolio(cost_npvs, rho=1000)

    frontier = {}
    for tol in tolerances:
        budget = safest["cvar"] + tol * (cheapest["cvar"] - safest["cvar"])
        # small slack so the budget at 0 stays feasible after solver rounding
        result = optimize_portfolio(cost_npvs, cvar_budget=budget + 1)
        result["cheapest"] = cheapest
        result["safest"] = safest
        frontier[tol] = result
    return frontier


def recommend_from_npvs(cost_npvs, tail_tolerance):
    return tail_frontier(cost_npvs, [tail_tolerance])[tail_tolerance]


def recommend(zone, archetype, annual_kwh, tail_tolerance, reference_zone=None,
              has_wholesale_market_access=False):
    eligible, cost_npvs = candidate_npvs(zone, archetype, annual_kwh, reference_zone,
                                         has_wholesale_market_access)
    result = recommend_from_npvs(cost_npvs, tail_tolerance)
    result["eligible"] = sorted(eligible)
    result["contract_npvs"] = cost_npvs
    return result
