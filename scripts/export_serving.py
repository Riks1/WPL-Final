"""Phase 3.5b (D12): the serving copy of the ratings, as JSON (no pyarrow in the API image), plus a parity fixture.

    python -m scripts.export_serving --snapshot all_female_json_20261025b.zip

Needs scripts.build_ratings to have run. Writes models/ratings_v3.json and models/xi_parity_fixture.json."""
import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

import wpl.data.entities as E
import wpl.data.parse as P
import wpl.data.snapshots as S
import wpl.xi as XI
from scripts.build_ratings import library_versions
from wpl.strength import RATING_COLS, team_strength

ROOT = Path(S.ROOT)
CUTOFF = '2024-01-01'
FIELDS = ['name'] + [c + s for c in RATING_COLS for s in ('', '_sd')] + \
         ['legal_faced', 'legal_bowled', 'mean_bat_pos', 'mean_balls_bowled']


def clean(x):
    """JSON has no NaN: missing values become null."""
    return None if isinstance(x, float) and math.isnan(x) else x


def player_table(T, state, params):
    """One row per rated player, as of after the last match: ratings, their SD, exposure and usage."""
    t = state.set_index('player_id')
    for c in RATING_COLS:
        t[c + '_sd'] = (params['sigma2'][c] / (t[c + '_eff'] + params['k'][c])) ** 0.5
    t = t.join(XI.usage_overall(T))
    people, _ = E.build_people(T)
    t['name'] = people.set_index('player_id').name.reindex(t.index)
    return t[FIELDS].sort_index()


def parity_cases(T, table, lam, shares, n_matches=8):
    """The toss XIs of the last model-scope matches, with strengths computed from the table (training side)."""
    xi = XI.toss_xi(T)
    last = T['matches'][T['matches'].model_scope].sort_values(['date', 'match_id']).match_id.tail(n_matches)
    cases = []
    for mid in last:
        for team, g in xi[xi.match_id == mid].groupby('team', sort=True):
            ids = g.sort_values('sheet_order').player_id.tolist()
            rows = table.reindex(ids)
            p = {c: rows[c].to_numpy(float) for c in FIELDS[1:]}
            p['sheet_order'] = list(range(len(ids)))
            cases.append({'match_id': str(mid), 'team': team, 'xi': ids,
                          'expected': team_strength(p, lam, shares)})
    return cases


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', required=True)
    a = ap.parse_args(argv)
    proc = ROOT / 'data' / 'processed' / Path(a.snapshot).stem
    build = json.loads((ROOT / 'reports' / 'stage3' / 'ratings_build.json').read_text())
    if build['snapshot'] != a.snapshot:
        raise SystemExit('ratings_build.json was built from a different snapshot')
    exclusions = json.loads((ROOT / 'data' / 'exclusions.json').read_text())
    T = E.apply_aliases(P.parse_snapshot(S.fetch(a.snapshot), exclusions, verbose=False))
    params, lam = build['params'], build['lambda_runs_per_wicket']
    shares = [float(x) for x in XI.position_shares(T, CUTOFF)]
    table = player_table(T, pd.read_parquet(proc / 'ratings_state.parquet'), params)

    debutant = {c: params['mu0'][c] for c in RATING_COLS}
    debutant.update({c + '_sd': (params['sigma2'][c] / params['k'][c]) ** 0.5 for c in RATING_COLS})
    bundle = {'kind': 'ratings', 'version': 'v3', 'as_of': str(T['matches'].date.max().date()),
              'snapshot': a.snapshot, 'snapshot_sha256': build['sha256'],
              'ratings_content_hash': build['content_hash'], 'libraries': library_versions(), 'h': params['h'], 'lambda': lam, 'data_min': 60,
              'shares_by_pos': shares, 'debutant': debutant, 'fields': FIELDS,
              'players': {pid: [clean(v) for v in row] for pid, row in zip(table.index, table.itertuples(index=False))}}
    (ROOT / 'models' / 'ratings_v3.json').write_text(json.dumps(bundle, separators=(',', ':')))
    cases = parity_cases(T, table, lam, shares)
    (ROOT / 'models' / 'xi_parity_fixture.json').write_text(json.dumps({'ratings_version': 'v3', 'cases': cases}, indent=1))
    print(f"{len(table)} players as of {bundle['as_of']} -> models/ratings_v3.json; "
          f"{len(cases)} parity cases -> models/xi_parity_fixture.json")
    return 0


if __name__ == '__main__':
    sys.exit(main())
