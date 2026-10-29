"""Stage 2 in one command: registered snapshot -> tables -> entities -> validation -> reports.

    python -m scripts.build_stage2 --snapshot all_female_json_20261025b.zip --wpl-snapshot wpl_json_20261025.zip

Exits with status 1 if any HARD validation check fails (wpl/data/validate.py).
"""
import argparse
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

import wpl.data.entities as E
import wpl.data.parse as P
import wpl.data.snapshots as S
import wpl.data.validate as V
import wpl.data.weights as W

ROOT = Path(S.ROOT)
FOLDS = (2024, 2025, 2026)
DRIFT_COLS = ['runs_total', 'legal', 'n_dismissals', 'batter_id', 'bowler_id', 'non_striker_id']


def build(zip_path, exclusions):
    T = E.apply_aliases(P.parse_snapshot(zip_path, exclusions))
    people, missing = E.build_people(T)
    pts = E.build_player_team_season(T)
    ent = {'venues': E.build_venues(T), 'people': people, 'player_team_season': pts,
           'switches': E.build_switches(pts, people), 'usage': E.build_usage(T)}
    return T, ent, missing


def wpl_drift(T_new, T_ref):
    """Did Cricsheet change any WPL delivery between the stage 1 snapshot and this one?"""
    ids_new = set(T_new['matches'].query('competition == @P.WPL').match_id)
    ids_ref = set(T_ref['matches'].query('competition == @P.WPL').match_id)
    key = ['match_id', 'innings', 'seq']
    common = ids_new & ids_ref
    a = T_ref['deliveries'][T_ref['deliveries'].match_id.isin(common)][key + DRIFT_COLS]
    b = T_new['deliveries'][T_new['deliveries'].match_id.isin(common)][key + DRIFT_COLS]
    j = a.merge(b, on=key, how='outer', suffixes=('_ref', '_new'), indicator=True)
    changed = j[(j._merge != 'both') | np.logical_or.reduce(
        [j[f'{c}_ref'].astype(str) != j[f'{c}_new'].astype(str) for c in DRIFT_COLS])]
    return {'matches_compared': len(common), 'only_in_stage1': sorted(ids_ref - ids_new),
            'only_in_new': sorted(ids_new - ids_ref), 'changed_deliveries': len(changed),
            'changed_matches': sorted(changed.match_id.unique())}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', required=True)
    ap.add_argument('--wpl-snapshot', default=None, help='stage 1 snapshot, for the drift check')
    ap.add_argument('--out', default=str(ROOT / 'data' / 'processed'))
    ap.add_argument('--reports', default=str(ROOT / 'reports' / 'stage2'))
    a = ap.parse_args(argv)

    reg = S.load_registry()
    exclusions = json.loads((ROOT / 'data' / 'exclusions.json').read_text())
    T, ent, missing = build(S.fetch(a.snapshot), exclusions)

    buf = io.StringIO()
    with redirect_stdout(buf):
        res = V.validate(T, ent['usage'])
    report = buf.getvalue()
    print(report)
    hard = V.hard_failures(res)

    m = T['matches']
    summary = {
        'snapshot': a.snapshot, 'sha256': reg[a.snapshot]['sha256'], 'hf_revision': reg[a.snapshot]['hf_revision'],
        'excluded': sorted(exclusions), 'matches': len(m), 'model_scope': int(m.model_scope.sum()),
        'ratings_scope': int(m.ratings_scope.sum()),
        'model_scope_by_competition': {k: int(v) for k, v in m[m.model_scope].competition.value_counts().items()},
        'main_deliveries': int((~T['deliveries'].super_over).sum()),
        'result_types': {k: int(v) for k, v in m.result_type.value_counts().items()},
        'players': len(ent['people']), 'on_field_not_in_team_sheet': len(missing), 'venues': len(ent['venues']),
        'wpl_switches_by_season': {int(k): int(v) for k, v in ent['switches'].to_season.value_counts().sort_index().items()},
        'checks': {k: len(v) for k, v in res.items()}, 'hard_failures': hard, 'folds': {},
    }
    for s in FOLDS:
        w = W.match_weights(T, s)
        summary['folds'][s] = {'s_c': {k: round(v, 3) for k, v in W.relevance(T, s).items()},
                               'matches': len(w), 'effective_n': round(W.effective_n(w.weight), 1)}
    if a.wpl_snapshot:
        with redirect_stdout(io.StringIO()):
            T_ref = E.apply_aliases(P.parse_snapshot(S.fetch(a.wpl_snapshot), exclusions))
        summary['wpl_drift'] = wpl_drift(T, T_ref)

    out = Path(a.out) / Path(a.snapshot).stem
    P.write_tables({**T, **ent}, out)
    rep = Path(a.reports)
    rep.mkdir(parents=True, exist_ok=True)
    (rep / 'validation.txt').write_text(report)
    (rep / 'build_summary.json').write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({k: summary[k] for k in ('matches', 'model_scope', 'ratings_scope', 'main_deliveries',
                                              'hard_failures')}))
    print('wpl drift:', summary.get('wpl_drift', 'not checked'))
    print(f'tables -> {out} | reports -> {rep}')
    return 1 if hard else 0


if __name__ == '__main__':
    sys.exit(main())
