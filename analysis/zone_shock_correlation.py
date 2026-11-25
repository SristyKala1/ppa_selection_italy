import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

import scenarios.price_scenarios as ps
from optimization.portfolio import candidate_npvs, tail_frontier


# the Virtual PPA cases from Table 9.1; the reference zone is where basis risk comes from
CASES = {
    "Nord (Sud ref)": ("nord", "chemicals", 20e6, "sud"),
    "Sardegna (Sicilia ref)": ("sardegna", "chemicals", 25e6, "sicilia"),
    "Data center, Centro-Sud (Sicilia ref)": ("centro_sud", "data_center", 30e6, "sicilia"),
    "Sardegna (Centro-Nord ref)": ("sardegna", "chemicals", 25e6, "centro_nord"),
}
# 0.999 = median fit 2016-2024, 0.99 = median fit 2005-2024, 0.96 = lowest pair (Sicilia, 2005-2024)
CORRELATIONS = [1.0, 0.999, 0.99, 0.96]
TOLERANCES = [1.0, 0.6, 0.0]

rows = []
for corr in CORRELATIONS:
    ps.ZONE_SHOCK_CORRELATION = corr
    ps.build_zonal_price_matrix.cache_clear()
    for case, (zone, archetype, kwh, ref) in CASES.items():
        gap = ps.build_zonal_price_matrix(zone) - ps.build_zonal_price_matrix(ref)
        _, npvs = candidate_npvs(zone, archetype, kwh, reference_zone=ref,
                                 has_wholesale_market_access=True)
        for tol, result in tail_frontier(npvs, TOLERANCES).items():
            chosen = {t: round(w, 3) for t, w in result["weights"].items() if w > 0.001}
            rows.append({"correlation": corr, "case": case, "tolerance": tol, "portfolio": chosen,
                         "expected_M": round(result["expected_cost"] / 1e6, 2),
                         "cvar_M": round(result["cvar"] / 1e6, 2),
                         "gap_std": round(gap.values.std(), 2),
                         "spot_E_M": round(result["do_nothing_expected"] / 1e6, 2),
                         "spot_cvar_M": round(result["do_nothing_cvar"] / 1e6, 2)})

out = pd.DataFrame(rows)
pd.set_option("display.max_colwidth", None, "display.width", 250)
print(out.to_string(index=False))
out.to_csv(Path(__file__).resolve().parent / "zone_shock_correlation.csv", index=False)
