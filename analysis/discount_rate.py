import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

import optimization.portfolio as portfolio
from optimization.portfolio import candidate_npvs, tail_frontier

# the 8% rate is an assumption (Section 7.2), so the cases are rerun at 5% and 10%
CASES = {
    "Nord": ("nord", "chemicals", 20e6, "sud"),
    "Nord without VPPA": ("nord", "chemicals", 20e6, None),
    "Sicilia": ("sicilia", "chemicals", 50e6, "sardegna"),
}
TOLERANCES = [1.0, 0.6, 0.0]
RATES = [0.05, 0.08, 0.10]


def run_cases(rate):
    # scenario_npv takes its rate as a default argument, so that default is what changes here
    portfolio.scenario_npv.__defaults__ = (rate,)
    rows = []
    for case, (zone, archetype, kwh, ref) in CASES.items():
        _, npvs = candidate_npvs(zone, archetype, kwh, reference_zone=ref,
                                 has_wholesale_market_access=True)
        for tol, result in tail_frontier(npvs, TOLERANCES).items():
            chosen = {t: round(w, 3) for t, w in result["weights"].items() if w > 0.001}
            rows.append({"discount_rate": rate, "case": case, "tolerance": tol, "portfolio": chosen,
                         "expected_M": round(result["expected_cost"] / 1e6, 2),
                         "cvar_M": round(result["cvar"] / 1e6, 2),
                         "spot_E_M": round(result["do_nothing_expected"] / 1e6, 2),
                         "spot_cvar_M": round(result["do_nothing_cvar"] / 1e6, 2)})
    return rows


rows = [row for rate in RATES for row in run_cases(rate)]
portfolio.scenario_npv.__defaults__ = (portfolio.DISCOUNT_RATE,)

out = pd.DataFrame(rows)
pd.set_option("display.max_colwidth", None, "display.width", 250)
print(out.to_string(index=False))
out.to_csv(Path(__file__).resolve().parent / "discount_rate.csv", index=False)
