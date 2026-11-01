import sys
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
TOLERANCES = [1.0, 0.6, 0.0]
GRIDS = {
    "final": [0.1, 0.2, 0.3, 0.5, 0.75, 1.0],
    "fine 5%": [round(0.05 * k, 2) for k in range(1, 21)],
    "coarse, no 30%": [0.25, 0.5, 0.75, 1.0],
}


def coverage(weights):
    # weight on a contract sized at s% covers about weight x s% of consumption
    covered = {}
    for name, w in weights.items():
        if w <= 0.001 or name == "spot_only":
            continue
        kind, share = name.rsplit("_", 1)
        covered[kind] = covered.get(kind, 0) + w * float(share.rstrip("%"))
    return {kind: round(c, 1) for kind, c in covered.items()}


rows = []
for grid, shares in GRIDS.items():
    portfolio.COVERAGE_SHARES = shares
    for case, (zone, archetype, kwh, ref) in CASES.items():
        _, npvs = candidate_npvs(zone, archetype, kwh, reference_zone=ref,
                                 has_wholesale_market_access=True)
        for tol, result in tail_frontier(npvs, TOLERANCES).items():
            rows.append({"grid": grid, "case": case, "candidates": len(npvs),
                         "tolerance": tol,
                         "weights": {t: round(w, 3) for t, w in result["weights"].items() if w > 0.001},
                         "coverage_%": coverage(result["weights"]),
                         "expected_M": round(result["expected_cost"] / 1e6, 2),
                         "cvar_M": round(result["cvar"] / 1e6, 2)})

out = pd.DataFrame(rows)
pd.set_option("display.max_colwidth", None, "display.width", 250)
print(out.to_string(index=False))
out.to_csv(Path(__file__).resolve().parent / "size_grid.csv", index=False)
