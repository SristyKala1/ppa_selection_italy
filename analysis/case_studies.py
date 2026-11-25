import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from explainability.rationale import split_contract_name
from optimization.portfolio import candidate_npvs, tail_frontier

# the case studies of Chapter 9 (Table 9.1), plus the two variants the chapter discusses
CASES = {
    "Nord": ("nord", "chemicals", 20e6, "sud", True),
    "Nord without VPPA": ("nord", "chemicals", 20e6, None, True),
    "Sicilia": ("sicilia", "chemicals", 50e6, "sardegna", True),
    "Minimal": ("nord", "office_services", 1e5, None, False),
    "Data center": ("centro_sud", "data_center", 30e6, "sicilia", True),
    "Sardegna": ("sardegna", "chemicals", 25e6, "sicilia", True),
    "Sardegna (Centro-Nord ref)": ("sardegna", "chemicals", 25e6, "centro_nord", True),
}
TOLERANCES = [round(t / 10, 1) for t in range(10, -1, -1)]


def coverage_by_type(weights):
    # a weight w on a contract sized at s covers about w * s of consumption (Section 7.2.2)
    shares = {}
    for t, w in weights.items():
        if w > 0.001 and t != "spot_only":
            base, size = split_contract_name(t)
            shares[base] = shares.get(base, 0) + w * size
    return {b: round(s, 3) for b, s in shares.items()}


rows = []
for case, (zone, archetype, kwh, ref, access) in CASES.items():
    _, npvs = candidate_npvs(zone, archetype, kwh, reference_zone=ref,
                             has_wholesale_market_access=access)
    for tol, result in tail_frontier(npvs, TOLERANCES).items():
        rows.append({"case": case, "tolerance": tol,
                     "portfolio": {t: round(w, 3) for t, w in result["weights"].items() if w > 0.001},
                     "coverage": coverage_by_type(result["weights"]),
                     "expected_M": round(result["expected_cost"] / 1e6, 2),
                     "cvar_M": round(result["cvar"] / 1e6, 2),
                     "spot_E_M": round(result["do_nothing_expected"] / 1e6, 2),
                     "spot_cvar_M": round(result["do_nothing_cvar"] / 1e6, 2)})

out = pd.DataFrame(rows)
out["saving_E_M"] = (out["spot_E_M"] - out["expected_M"]).round(2)
out["cvar_cut_M"] = (out["spot_cvar_M"] - out["cvar_M"]).round(2)
pd.set_option("display.max_colwidth", None, "display.width", 250)
print(out.to_string(index=False))
out.to_csv(Path(__file__).resolve().parent / "case_studies.csv", index=False)
