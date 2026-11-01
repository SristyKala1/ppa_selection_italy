import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

import scenarios.price_scenarios as ps
from optimization.portfolio import candidate_npvs, tail_frontier

# Table 9.1 profiles, with and without their VPPA reference
CASES = {
    "Nord": ("nord", "chemicals", 20e6, "sud"),
    "Nord without VPPA": ("nord", "chemicals", 20e6, None),
    "Sicilia": ("sicilia", "chemicals", 50e6, "sardegna"),
    "Sicilia without VPPA": ("sicilia", "chemicals", 50e6, None),
}
TOLERANCES = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]


def run_cases(sigma):
    ps.PRICE_SHOCK_VOLATILITY = sigma
    ps.build_zonal_price_matrix.cache_clear()
    rows = []
    for case, (zone, archetype, kwh, ref) in CASES.items():
        _, npvs = candidate_npvs(zone, archetype, kwh, reference_zone=ref,
                                 has_wholesale_market_access=True)
        for tol, result in tail_frontier(npvs, TOLERANCES).items():
            chosen = {t: round(w, 3) for t, w in result["weights"].items() if w > 0.001}
            rows.append({"sigma": sigma, "case": case, "tolerance": tol, "portfolio": chosen,
                         "expected_M": round(result["expected_cost"] / 1e6, 2),
                         "cvar_M": round(result["cvar"] / 1e6, 2),
                         "spot_E_M": round(result["do_nothing_expected"] / 1e6, 2),
                         "spot_cvar_M": round(result["do_nothing_cvar"] / 1e6, 2)})
    return rows


rows = run_cases(0.38) + run_cases(0.19)

out = pd.DataFrame(rows)
pd.set_option("display.max_colwidth", None, "display.width", 250)
print(out.to_string(index=False))
out.to_csv(Path(__file__).resolve().parent / "shock_volatility.csv", index=False)
