"""Phase 3.3 in one command: ratings -> XI strength, venue prior, match features, validation report (D10).

    python -m scripts.build_xi --snapshot all_female_json_20261025b.zip

Needs scripts.build_ratings to have run. No metric here compares features with match results (PREREG §8)."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import wpl.data.entities as E
import wpl.data.parse as P
import wpl.data.snapshots as S
import wpl.xi as XI

ROOT = Path(S.ROOT)
CUTOFF = '2024-01-01'
WPL = "Women's Premier League"

def season_end_ratings(asof, T, min_eff=100):
  m = T['matches'][['match_id','season','competition']]
  a = asof.merge(m,on='match_id')
  a = a[a.competition == WPL].sort_values('date')
  return a.groupby(['season', 'player_id']).tail(1)
def validation_report(T, asof, feats, people):
    """Coverage, face validity and stability. Ratings and coverage only; never match outcomes."""
    out = {}
    cov = feats.assign(cov=(feats.coverage_bf + feats.coverage_ch) / 2,
                       debut=(feats.n_debut_bf + feats.n_debut_ch) / (feats.xi_size_bf + feats.xi_size_ch))
    out['coverage'] = cov.groupby(['competition','season'])[['cov','debut']].mean().round(3).reset_index()
    out['xi_margin_by_season'] = feats.groupby(['competition', 'season']).xi_margin.agg(['mean', 'std', 'count']).round(2).reset_index()
    se = season_end_ratings(asof, T)
    names = people.set_index('player_id').name
    tops = []
    for season,g in se.groupby('season'):
      bat = g[g.bat_runs_eff>=100].nlargest(10,'bat_runs')
      bowl = g[g.bowl_runs_eff >= 100].nsmallest(10, 'bowl_runs')
      tops += [{'season': season, 'list': 'batting runs (top)', 'player': names.get(p, p), 'rating': round(v, 3)}
                 for p, v in zip(bat.player_id, bat.bat_runs)]
      tops += [{'season': season, 'list': 'bowling economy (best)', 'player': names.get(p, p), 'rating': round(v, 3)}
                 for p, v in zip(bowl.player_id, bowl.bowl_runs)]
    out['top10'] = pd.DataFrame(tops)
    stab = []
    seasons = sorted(se.season.unique())
    for s1, s2 in zip(seasons, seasons[1:]):
        a = se[se.season == s1].set_index('player_id')
        b = se[se.season == s2].set_index('player_id')
        for comp in ('bat_runs', 'bowl_runs'):
            both = a.index.intersection(b.index)
            both = [p for p in both if a.loc[p, comp + '_eff'] >= 100 and b.loc[p, comp + '_eff'] >= 100]
            rho = a.loc[both, comp].corr(b.loc[both, comp], method='spearman') if len(both) > 2 else np.nan
            stab.append({'from': s1, 'to': s2, 'component': comp, 'players': len(both), 'spearman': round(rho, 3)})
    out['stability'] = pd.DataFrame(stab)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', required=True)
    ap.add_argument('--out', default=str(ROOT / 'data' / 'processed'))
    ap.add_argument('--reports', default=str(ROOT / 'reports' / 'stage3'))
    a = ap.parse_args(argv)

    proc = Path(a.out) / Path(a.snapshot).stem
    rep = Path(a.reports)
    build = json.loads((rep / 'ratings_build.json').read_text())
    exclusions = json.loads((ROOT / 'data' / 'exclusions.json').read_text())
    T = E.apply_aliases(P.parse_snapshot(S.fetch(a.snapshot), exclusions, verbose=False))
    asof = pd.read_parquet(proc / 'ratings_asof.parquet')
    asof_inf = pd.read_parquet(proc / 'ratings_asof_hinf.parquet')
    lam = build['lambda_runs_per_wicket']

    shares = XI.position_shares(T, CUTOFF)
    st = XI.xi_strength(T, asof, lam, shares)
    st_inf = XI.xi_strength(T, asof_inf, lam, shares)
    feats = XI.match_features(T, st, st_inf)
    feats.to_parquet(proc / 'xi_features.parquet', index=False)
    feats.to_csv(rep / 'xi_features.csv', index=False)

    people, _ = E.build_people(T)
    vr = validation_report(T, asof, feats, people)
    md = ['# Stage 3 ratings validation report (D10)',
          f"Snapshot `{a.snapshot}`; ratings content hash `{build['content_hash'][:16]}…`; h = {build['params']['h']}; "
          f"λ = {lam:.2f}. No metric here uses match results (PREREG §8).",
          '## Batting-position shares (pre-2024)', ', '.join(f'{i + 1}: {s:.3f}' for i, s in enumerate(shares))]
    for key, title in (('coverage', 'Coverage: share of XI slots with ≥60 legal balls faced or bowled before the match; debutant share'),
                       ('xi_margin_by_season', 'xi_margin (runs) by competition and season'),
                       ('stability', 'Season-to-season rank stability (players with ≥100 effective balls in both)'),
                       ('top10', 'Face validity: top 10 WPL players by season-end rating (≥100 effective balls)')):
        md += [f'## {title}', vr[key].to_markdown(index=False)]
    (rep / 'validation_report.md').write_text('\n\n'.join(md) + '\n')
    summary = {'snapshot': a.snapshot, 'ratings_content_hash': build['content_hash'], 'lambda': lam,
               'position_shares': [round(float(x), 4) for x in shares], 'features_rows': len(feats),
               'coverage': vr['coverage'].to_dict('records'), 'stability': vr['stability'].to_dict('records')}
    (rep / 'xi_build.json').write_text(json.dumps(summary, indent=2, default=str))
    print(vr['coverage'].to_string(index=False))
    print(vr['stability'].to_string(index=False))
    print(f'features: {len(feats)} matches -> {proc / "xi_features.parquet"}; report -> {rep / "validation_report.md"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())


