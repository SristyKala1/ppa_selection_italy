import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

import optimization.portfolio as portfolio
from optimization.portfolio import candidate_npvs, tail_frontier

# same profiles as Table 9.1: zone, archetype, kWh/yr, VPPA reference
CASES = {
    "Nord": ("nord", "chemicals", 20e6, "sud"),
    "Sicilia": ("sicilia", "chemicals", 50e6, "sardegna"),
    "Sardegna": ("sardegna", "chemicals", 25e6, "sicilia"),
}
ALPHAS = [0.90, 0.95, 0.99]
TOLERANCES = [1.0, 0.6, 0.0]
FINE_TOLERANCES = [round(0.05 * k, 2) for k in range(21)]
RHOS = [0, 0.1, 0.25, 0.5, 1, 2, 5, 10, 1000]


def summary(result):
    return {"weights": {t: round(w, 3) for t, w in result["weights"].items() if w > 0.001},
            "expected_M": round(result["expected_cost"] / 1e6, 2),
            "cvar_M": round(result["cvar"] / 1e6, 2)}


npvs = {case: candidate_npvs(zone, archetype, kwh, reference_zone=ref,
                             has_wholesale_market_access=True)[1]
        for case, (zone, archetype, kwh, ref) in CASES.items()}
original = portfolio.optimize_portfolio

# confidence level: tail_frontier looks optimize_portfolio up by name, so swapping it passes alpha through
alpha_rows = []
for alpha in ALPHAS:
    portfolio.optimize_portfolio = partial(original, alpha=alpha)
    for case, cost_npvs in npvs.items():
        for tol, result in tail_frontier(cost_npvs, TOLERANCES).items():
            alpha_rows.append({"alpha": alpha, "case": case, "tolerance": tol, **summary(result)})
portfolio.optimize_portfolio = original

# CVaR limit: budget form at 5% steps against the penalty form, Nord only
limit_rows = []
for tol, result in tail_frontier(npvs["Nord"], FINE_TOLERANCES).items():
    limit_rows.append({"form": "budget", "setting": tol, **summary(result)})
for rho in RHOS:
    limit_rows.append({"form": "penalty", "setting": rho, **summary(original(npvs["Nord"], rho=rho))})

pd.set_option("display.max_colwidth", None, "display.width", 250)
here = Path(__file__).resolve().parent
for name, rows in [("cvar_alpha", alpha_rows), ("cvar_limit", limit_rows)]:
    out = pd.DataFrame(rows)
    print(out.to_string(index=False), "\n")
    out.to_csv(here / f"{name}.csv", index=False)
