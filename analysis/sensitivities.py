import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

import scenarios.contracts as contracts
import scenarios.price_scenarios as ps
from optimization.portfolio import candidate_npvs, tail_frontier

# the one-at-a-time tests of Section 9.4 that don't have a script of their own
# (shock volatility, size grid, CVaR settings, baseload premium and zone correlation do)
CASES = {
    "Nord": ("nord", "chemicals", 20e6, "sud", True),
    "Nord without VPPA": ("nord", "chemicals", 20e6, None, True),
    "Nord without access": ("nord", "chemicals", 20e6, None, False),
    "Sicilia": ("sicilia", "chemicals", 50e6, "sardegna", True),
    "Sardegna": ("sardegna", "chemicals", 25e6, "sicilia", True),
    "Minimal": ("nord", "office_services", 1e5, None, False),
    "Data center": ("centro_sud", "data_center", 30e6, "sicilia", True),
}
# the surplus test checks the other of the two values discussed in Section 7.2.4
OTHER_SURPLUS_FACTOR = 1.0 if contracts.SURPLUS_CAPTURE_FACTOR == 0.5 else 0.5
TOLERANCES = [1.0, 0.6, 0.0]


@contextmanager
def setting(module, name, value):
    old = getattr(module, name)
    setattr(module, name, value)
    ps.build_zonal_price_matrix.cache_clear()
    try:
        yield
    finally:
        setattr(module, name, old)
        ps.build_zonal_price_matrix.cache_clear()


@contextmanager
def capture_shift(delta):
    old = {tech: dict(rates) for tech, rates in contracts.CAPTURE_BY_TECH.items()}
    for rates in contracts.CAPTURE_BY_TECH.values():
        for zone in rates:
            rates[zone] += delta
    try:
        yield
    finally:
        for tech, rates in contracts.CAPTURE_BY_TECH.items():
            rates.update(old[tech])


TESTS = [
    ("price level", "x0.87", lambda: setting(ps, "GME_PUN_2024", ps.GME_PUN_2024 * 0.87), ["Nord", "Nord without VPPA"]),
    ("price level", "x1.15", lambda: setting(ps, "GME_PUN_2024", ps.GME_PUN_2024 * 1.15), ["Nord", "Nord without VPPA"]),
    ("capture rates", "-0.05", lambda: capture_shift(-0.05), ["Nord"]),
    ("capture rates", "+0.05", lambda: capture_shift(+0.05), ["Nord"]),
    ("seed", "1", lambda: setting(ps, "PRICE_SHOCK_SEED", 1), ["Nord"]),
    ("seed", "7", lambda: setting(ps, "PRICE_SHOCK_SEED", 7), ["Nord"]),
    ("shock paths", "20", lambda: setting(ps, "N_PRICE_PATHS", 20), ["Nord"]),
    ("baseload discount", "3%", lambda: setting(contracts, "BASELOAD_DISCOUNT", 0.03), ["Nord"]),
    ("baseload discount", "8%", lambda: setting(contracts, "BASELOAD_DISCOUNT", 0.08), ["Nord"]),
    ("baseload discount", "10%", lambda: setting(contracts, "BASELOAD_DISCOUNT", 0.10), ["Nord"]),
    ("baseload discount", "12%", lambda: setting(contracts, "BASELOAD_DISCOUNT", 0.12), ["Nord"]),
    ("counterparty spread", "€0", lambda: setting(contracts, "COUNTERPARTY_SPREAD", 0.0), ["Nord", "Sicilia", "Sardegna"]),
    ("counterparty spread", "€2.5", lambda: setting(contracts, "COUNTERPARTY_SPREAD", 2.5), ["Nord", "Sicilia", "Sardegna"]),
    ("counterparty spread", "€7.5", lambda: setting(contracts, "COUNTERPARTY_SPREAD", 7.5), ["Nord", "Sicilia", "Sardegna"]),
    ("counterparty spread", "€10", lambda: setting(contracts, "COUNTERPARTY_SPREAD", 10.0), ["Nord", "Sicilia", "Sardegna"]),
    ("sleeving margin", "€0", lambda: setting(contracts, "SLEEVING_MARGIN", 0.0), ["Minimal", "Nord without access"]),
    ("sleeving margin", "€5", lambda: setting(contracts, "SLEEVING_MARGIN", 5.0), ["Minimal", "Nord without access"]),
    ("surplus credit", f"f = {OTHER_SURPLUS_FACTOR}",
     lambda: setting(contracts, "SURPLUS_CAPTURE_FACTOR", OTHER_SURPLUS_FACTOR),
     ["Nord", "Nord without VPPA", "Sicilia", "Sardegna", "Data center", "Minimal"]),
]


def run(test, value, case_names):
    rows = []
    for case in case_names:
        zone, archetype, kwh, ref, access = CASES[case]
        _, npvs = candidate_npvs(zone, archetype, kwh, reference_zone=ref,
                                 has_wholesale_market_access=access)
        for tol, result in tail_frontier(npvs, TOLERANCES).items():
            rows.append({"test": test, "value": value, "case": case, "tolerance": tol,
                         "portfolio": {t: round(w, 3) for t, w in result["weights"].items() if w > 0.001},
                         "expected_M": round(result["expected_cost"] / 1e6, 2),
                         "cvar_M": round(result["cvar"] / 1e6, 2),
                         "spot_E_M": round(result["do_nothing_expected"] / 1e6, 2),
                         "spot_cvar_M": round(result["do_nothing_cvar"] / 1e6, 2)})
    return rows


all_cases = sorted({c for *_, cases in TESTS for c in cases}, key=list(CASES).index)
rows = run("base", "main case", all_cases)
for test, value, change, case_names in TESTS:
    with change():
        rows += run(test, value, case_names)
    print(f"done: {test} {value}", flush=True)

out = pd.DataFrame(rows)
pd.set_option("display.max_colwidth", None, "display.width", 250)
print(out.to_string(index=False))
out.to_csv(Path(__file__).resolve().parent / "sensitivities.csv", index=False)
