import pandas as pd
import pyomo.environ as pyo

from scenarios.contracts import contract_cost_matrices
from scenarios.eligibility import eligible_contracts
from scenarios.load_profile import ARCHETYPES
from scenarios.price_scenarios import ZONES

DISCOUNT_RATE = 0.08
ALPHA = 0.95


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


def optimize_portfolio(cost_npvs, rho, alpha=ALPHA):
    if rho < 0:
        raise ValueError(f"rho must be >= 0, got {rho}")

    types = list(cost_npvs)
    index = cost_npvs[types[0]].index
    n = len(index)
    cost = {(t, i): cost_npvs[t].iloc[i] for t in types for i in range(n)}

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

    expected = sum(scenario_cost(m, i) for i in m.S) / n
    cvar = m.eta + sum(m.z[i] for i in m.S) / ((1 - alpha) * n)
    m.obj = pyo.Objective(expr=expected + rho * cvar, sense=pyo.minimize)

    outcome = pyo.SolverFactory("appsi_highs").solve(m)
    if outcome.solver.termination_condition != pyo.TerminationCondition.optimal:
        raise RuntimeError(f"solver did not converge: {outcome.solver.termination_condition}")

    raw = {t: max(pyo.value(m.w[t]), 0.0) for t in types}
    total = sum(raw.values())
    weights = {t: v / total for t, v in raw.items()}
    portfolio_npv = pd.Series(
        [sum(weights[t] * cost[(t, i)] for t in types) for i in range(n)], index=index
    )

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


def efficient_frontier(cost_npvs, rhos):
    rows = {}
    for rho in rhos:
        r = optimize_portfolio(cost_npvs, rho)
        rows[rho] = {**r["weights"], "expected_cost": r["expected_cost"], "cvar": r["cvar"]}
    frontier = pd.DataFrame(rows).T
    frontier.index.name = "rho"
    return frontier


def recommend(zone, archetype, annual_kwh, rho, reference_zone=None,
              has_wholesale_market_access=False, frontier_rhos=None):
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
    matrices = contract_cost_matrices(zone, archetype, annual_kwh, reference_zone=reference_zone)

    selected = {name: matrices[name] for name in sorted(eligible)}
    selected["spot_only"] = matrices["spot_only"]
    cost_npvs = {name: scenario_npv(mat) for name, mat in selected.items()}

    result = optimize_portfolio(cost_npvs, rho)
    result["eligible"] = sorted(eligible)
    result["contract_npvs"] = cost_npvs
    if frontier_rhos is not None:
        result["frontier"] = efficient_frontier(cost_npvs, frontier_rhos)
    return result
