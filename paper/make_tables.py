"""Generate the LaTeX tables from the committed repo outputs (no hand-typed numbers)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
R = sys.argv[1] if len(sys.argv) > 1 else '.'
OUT = Path(__file__).resolve().parent          # tables are written next to this script
sys.path.insert(0, R)
import wpl.prematch as PM, wpl.eval as EV

res = json.load(open(f'{R}/reports/stage3/prematch_results.json'))
names = {'base_rate': 'Base rate', 'primary': 'Primary', 's1': 'S1 ($+$venue prior)', 's2': 'S2 ($h=\\infty$)'}
f = lambda x, d=3: f'{x:.{d}f}'
s = lambda x, d=3: f'{x:+.{d}f}'.replace('-', '$-$').replace('+', '$+$')
def ci(lo, hi, signed=False):
    g = s if signed else f
    return f'[{g(lo)}, {g(hi)}]'

def stage3_table(key, label, caption):
    rows = res[key]['table']
    out = ['\\begin{table}[t]\\centering\\footnotesize\\setlength{\\tabcolsep}{4pt}', f'\\caption{{{caption}}}\\label{{{label}}}',
           '\\begin{tabular}{lccccccc}\\toprule',
           'Model & Log-loss [95\\% CI] & $\\Delta$ vs base [95\\% CI] & Brier & ECE & Cal.\\ slope & Cal.\\ int. & Acc.\\\\\\midrule']
    for r in rows:
        dl = '0' if r['model'] == 'base_rate' else f"{s(r['delta'])} {ci(r['delta_ci_low'], r['delta_ci_high'], True)}"
        slope = s(r['cal_slope'], 2) + ('$^\\dagger$' if key != 'wpl' and r['model'] == 'base_rate' else '')
        out.append(f"{names[r['model']]} & {f(r['log_loss'])} {ci(r['ci_low'], r['ci_high'])} & {dl} & {f(r['brier'])} & "
                   f"{f(r['ece'])} & {slope} & {s(r['cal_intercept'], 2)} & {f(r['accuracy'])}\\\\")
    out += ['\\bottomrule\\end{tabular}', '\\end{table}']
    return '\n'.join(out)

open(OUT / 'tab_wpl.tex', 'w').write(stage3_table('wpl', 'tab:wpl',
    'Pre-match evaluation, WPL (66 test matches, 2024--2026). This comparison decides deployment.'))
open(OUT / 'tab_india.tex', 'w').write(stage3_table('india_t20i_supporting', 'tab:india',
    'Supporting analysis, India T20Is (53 test matches, 2024--2026; one no-result excluded). Never decides deployment. '
    '$^\\dagger$The base rate is almost constant ($\\approx 0.48$), so its calibration slope is not estimable in any useful sense.'))

rb = json.load(open(f'{R}/reports/stage3/ratings_build.json'))
hg = ' & '.join(('$\\infty$' if g['h'] is None else f"{g['h']:g}") for g in rb['h_grid'])
hm = ' & '.join((f"\\textbf{{{g['mse_bat_runs']:.5f}}}" if g['h'] == rb['params']['h'] else f"{g['mse_bat_runs']:.5f}") for g in rb['h_grid'])
p = rb['params']
comp = {'bat_runs': 'Batting runs', 'bat_dis': 'Batting dismissal', 'bowl_runs': 'Bowling runs', 'bowl_wkt': 'Bowling wicket'}
pr = '\n'.join(f"{comp[c]} & {s(p['mu0'][c], 4)} & {p['sigma2'][c]:.4f} & {p['k'][c]:.1f}\\\\" for c in comp)
open(OUT / 'tab_ratings.tex', 'w').write(
 '\\begin{table}[t]\\centering\\small\n\\caption{Ratings hyperparameters, all estimated on balls before 2024-01-01. '
 f"Top: half-life $h$ chosen by one-step-ahead MSE of batting runs per ball on 2022--2023 ({rb['h_grid'][0]['n']:,} balls). "
 'Bottom: empirical Bayes prior mean $\\mu_0$ (debutant prior), residual variance $\\sigma^2$ and prior strength $k=\\sigma^2/\\tau^2$ (in balls).}\\label{tab:ratings}\n'
 f'\\begin{{tabular}}{{lcccc}}\\toprule\nHalf-life $h$ (years) & {hg}\\\\\nMSE & {hm}\\\\\\bottomrule\\end{{tabular}}\n\n\\vspace{{6pt}}\n'
 f'\\begin{{tabular}}{{lccc}}\\toprule\nComponent & $\\mu_0$ & $\\sigma^2$ & $k$\\\\\\midrule\n{pr}\n\\bottomrule\\end{{tabular}}\n\\end{{table}}\n')

# exploratory per-fold diagnostics
feats = pd.read_csv(f'{R}/reports/stage3/xi_features.csv')
pred = pd.read_csv(f'{R}/reports/stage3/prematch_predictions.csv')
rows = []
for comp_, lab in ((PM.WPL, 'WPL'), (PM.INDIA, 'India T20I')):
    d = feats[(feats.competition == comp_) & (feats.result_type != 'no_result')]
    for S in PM.TEST_SEASONS:
        tr = d[d.season < S]
        lr = PM.fit_logistic(tr, PM.MODELS['primary'])[-1]
        g = pred[(pred.competition == comp_) & (pred.season == S)]
        rows.append(f"{lab} & {S} & {len(tr)} & {s(lr.coef_[0][0], 2)} & {s(lr.coef_[0][1], 2)} & {len(g)} & "
                    f"{f(EV.log_loss_vec(g.y, g.base_rate).mean())} & {f(EV.log_loss_vec(g.y, g.primary).mean())}\\\\")
    t = d[d.season.isin(PM.TEST_SEASONS) & (d.xi_margin != 0) & (d.y != 0.5)]
    rows.append(f"\\multicolumn{{8}}{{l}}{{\\quad {lab}, test seasons: stronger XI won {((t.xi_margin > 0) == (t.y == 1)).mean():.3f} "
                f"of {len(t)} matches; mean $|\\texttt{{xi\\_margin}}|$ = {t.xi_margin.abs().mean():.1f} runs}}\\\\\\midrule")
rows[-1] = rows[-1].replace('\\midrule', '')
open(OUT / 'tab_folds.tex', 'w').write(
 '\\begin{table}[t]\\centering\\small\n\\caption{Exploratory, computed after the results were committed; it cannot change the verdict. '
 'Per fold: training size, the fitted primary coefficients (per standard deviation of the feature) and the per-match log-loss of the base rate and the primary on that test season.}\\label{tab:folds}\n'
 '\\begin{tabular}{lccccccc}\\toprule\nData & Test season & $n_{\\text{train}}$ & $\\beta_{\\text{xi}}$ & $\\beta_{\\text{toss}}$ & $n_{\\text{test}}$ & LL base & LL primary\\\\\\midrule\n'
 + '\n'.join(rows) + '\n\\bottomrule\\end{tabular}\n\\end{table}\n')
print('tables written')
