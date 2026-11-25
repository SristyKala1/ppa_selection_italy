import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

import scenarios.contracts as contracts
from optimization.portfolio import candidate_npvs, tail_frontier


# Table 9.1 profiles; the premium is added on top of the baseload strike in €/MWh
CASES = {
    "Nord": ("nord", "chemicals", 20e6, "sud"),
    "Nord without VPPA": ("nord", "chemicals", 20e6, None),
    "Sicilia": ("sicilia", "chemicals", 50e6, "sardegna"),
}
PREMIUMS = [0.0, 2.5, 5.0, 10.0, 15.0]  # 2.5 is the main case
TOLERANCES = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]

rows = []
for premium in PREMIUMS:
    contracts.BASELOAD_RISK_PREMIUM = premium
    for case, (zone, archetype, kwh, ref) in CASES.items():
        _, npvs = candidate_npvs(zone, archetype, kwh, reference_zone=ref,
                                 has_wholesale_market_access=True)
        baseload = npvs["baseload_100%"]
        for tol, result in tail_frontier(npvs, TOLERANCES).items():
            chosen = {t: round(w, 3) for t, w in result["weights"].items() if w > 0.001}
            rows.append({"premium": premium, "case": case, "tolerance": tol, "portfolio": chosen,
                         "expected_M": round(result["expected_cost"] / 1e6, 2),
                         "cvar_M": round(result["cvar"] / 1e6, 2),
                         "baseload_100_E_M": round(baseload.mean() / 1e6, 2),
                         "spot_E_M": round(result["do_nothing_expected"] / 1e6, 2),
                         "spot_cvar_M": round(result["do_nothing_cvar"] / 1e6, 2)})

out = pd.DataFrame(rows)
pd.set_option("display.max_colwidth", None, "display.width", 250)
print(out.to_string(index=False))
out.to_csv(Path(__file__).resolve().parent / "baseload_premium.csv", index=False)
