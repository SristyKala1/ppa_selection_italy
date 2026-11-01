import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

import scenarios.price_scenarios as ps
from optimization.portfolio import candidate_npvs, tail_frontier

# same profiles as Table 9.1: zone, archetype, kWh/yr, VPPA reference
CASES = {
    "Nord": ("nord", "chemicals", 20e6, "sud"),
    "Sicilia": ("sicilia", "chemicals", 50e6, "sardegna"),
    "Sardegna": ("sardegna", "chemicals", 25e6, "sicilia"),
}
TOLERANCES = [1.0, 0.6, 0.0]


def run_cases(label):
    rows = []
    for case, (zone, archetype, kwh, ref) in CASES.items():
        _, npvs = candidate_npvs(zone, archetype, kwh, reference_zone=ref,
                                 has_wholesale_market_access=True)
        n_scenarios = len(npvs["spot_only"])
        for tol, result in tail_frontier(npvs, TOLERANCES).items():
            chosen = {t: round(w, 3) for t, w in result["weights"].items() if w > 0.001}
            rows.append({"run": label, "case": case, "scenarios": n_scenarios,
                         "tolerance": tol, "portfolio": chosen,
                         "expected_M": round(result["expected_cost"] / 1e6, 2),
                         "cvar_M": round(result["cvar"] / 1e6, 2),
                         "spot_E_M": round(result["do_nothing_expected"] / 1e6, 2),
                         "spot_cvar_M": round(result["do_nothing_cvar"] / 1e6, 2)})
    return rows


rows = run_cases("final model")
# old scenario set: no shocks, one path per pathway -> 3 x 33 = 99 scenarios
ps.PRICE_SHOCK_VOLATILITY = 0
ps.N_PRICE_PATHS = 1
ps.build_zonal_price_matrix.cache_clear()
rows += run_cases("no shocks")

out = pd.DataFrame(rows)
pd.set_option("display.max_colwidth", None, "display.width", 250)
print(out.to_string(index=False))
out.to_csv(Path(__file__).resolve().parent / "benchmark_no_shocks.csv", index=False)
