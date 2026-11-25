from pathlib import Path

import numpy as np
import pandas as pd

# annual means of GME's hourly MGP zonal prices (Anno 2005-2024 files from mercatoelettrico.org);
# 2007 is missing, the file would not download. Calabria only exists from 2021 and is left out
HERE = Path(__file__).resolve().parent
prices = pd.read_csv(HERE / "gme_zonal_annual.csv", index_col="year")
ZONES = ["NORD", "CNOR", "CSUD", "SUD", "SICI", "SARD"]
PHI = 0.52  # national AR(1) persistence, same as the model


def shock_correlations(first, last):
    # detrend each zone's log price the same way as the national fit, then correlate
    # the AR(1) innovations of consecutive years only
    sub = prices.loc[first:last]
    x = {}
    for z in ZONES:
        log_p = np.log(sub[z])
        x[z] = log_p - np.polyval(np.polyfit(log_p.index, log_p, 1), log_p.index)
    x = pd.DataFrame(x)
    years = [y for y in x.index if y - 1 in x.index]
    innovations = pd.DataFrame({y: x.loc[y] - PHI * x.loc[y - 1] for y in years}).T
    corr = innovations.corr()
    pairs = [(a, b) for i, a in enumerate(ZONES) for b in ZONES[i + 1:]]
    return pd.DataFrame([
        {"window": f"{first}-{last}", "pair": f"{a}-{b}", "correlation": round(corr.loc[a, b], 4),
         "annual_gap_std": round((sub[a] - sub[b]).std(), 2)}
        for a, b in pairs
    ])


out = pd.concat([shock_correlations(2005, 2024), shock_correlations(2016, 2024)])
print(out.to_string(index=False))
print(out.groupby("window")["correlation"].describe()[["min", "50%", "max"]])
out.to_csv(HERE / "zone_correlation_fit.csv", index=False)
