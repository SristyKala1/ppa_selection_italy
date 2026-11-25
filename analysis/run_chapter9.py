import subprocess
import sys
from pathlib import Path

# reruns every Chapter 9 analysis with whatever values are set in src/, in the order the
# chapter uses them; each script writes its own CSV next to it
HERE = Path(__file__).resolve().parent
SCRIPTS = [
    "case_studies.py",          # Tables 9.1, 9.3 inputs, Sections 9.2-9.3
    "sensitivities.py",         # Section 9.4, Table 9.2
    "baseload_premium.py",
    "zone_shock_correlation.py",
    "shock_volatility.py",
    "size_grid.py",
    "cvar_settings.py",
    "benchmark_no_shocks.py",   # Section 9.5, Table 9.3
]

for script in SCRIPTS:
    print(f"--- {script}", flush=True)
    subprocess.run([sys.executable, str(HERE / script)], check=True, stdout=subprocess.DEVNULL)

# Figures 9.1 and 9.2 come from the thesis figure script, which is kept outside the repo
figures = HERE.parent / "thesis_figures" / "make_figures.py"
if figures.exists():
    print("--- figures 9.1 and 9.2", flush=True)
    subprocess.run([sys.executable, "-c",
                    "import make_figures as m; t = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]; "
                    "m.portfolio_frontier_figure('nord', 'chemicals', 20_000_000, 'sud', True, t, "
                    "'Figure 9.1. Nord case: how consumption is covered across tail-risk tolerance', "
                    "'fig_9_1_nord_frontier.png'); "
                    "m.portfolio_frontier_figure('sicilia', 'chemicals', 50_000_000, 'sardegna', True, t, "
                    "'Figure 9.2. Sicilia case: how consumption is covered across tail-risk tolerance', "
                    "'fig_9_2_sicilia_frontier.png')"],
                   check=True, cwd=figures.parent)
