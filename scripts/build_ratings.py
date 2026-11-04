"""Phase 3.2 in one command: frozen snapshot -> as-of player ratings (RATINGS_SPEC v1.1).

    python -m scripts.build_ratings --snapshot all_female_json_20261025b.zip

Writes data/processed/<snapshot>/ratings_*.parquet and reports/stage3/ratings_build.json."""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

import wpl.data.entities as E
import wpl.data.parse as P
import wpl.data.snapshots as S
import wpl.ratings as RT

ROOT = Path(S.ROOT)
CUTOFF = '2024-01-01'                          # PREREG: settings use balls before the first test season only


def jsonable(params):
    return {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in params.items()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', required=True)
    ap.add_argument('--out', default=str(ROOT / 'data' / 'processed'))
    ap.add_argument('--reports', default=str(ROOT / 'reports' / 'stage3'))
    a = ap.parse_args(argv)

    t0 = time.time()
    exclusions = json.loads((ROOT / 'data' / 'exclusions.json').read_text())
    T = E.apply_aliases(P.parse_snapshot(S.fetch(a.snapshot), exclusions, verbose=False))
    balls, rosters = RT.prepare_balls(T), RT.rosters_from(T)

    table, best = RT.tune_h(balls, rosters, before=CUTOFF)                    # primary settings
    asof, preds, state = RT.build_ratings(balls, rosters, best)
    p_inf = RT.fit_ratings(balls, rosters, float('inf'), before=CUTOFF)       # secondary S2: no decay
    asof_inf, _, _ = RT.build_ratings(balls, rosters, p_inf)

    out = Path(a.out) / Path(a.snapshot).stem
    out.mkdir(parents=True, exist_ok=True)
    asof.to_parquet(out / 'ratings_asof.parquet', index=False)
    asof_inf.to_parquet(out / 'ratings_asof_hinf.parquet', index=False)
    state.to_parquet(out / 'ratings_state.parquet', index=False)

    summary = {
        'snapshot': a.snapshot, 'sha256': S.load_registry()[a.snapshot]['sha256'], 'cutoff': CUTOFF,
        'balls': len(balls), 'rated_rows': len(asof), 'players': len(state),
        'h_grid': [{'h': (None if not np.isfinite(r.h) else r.h), 'mse_bat_runs': r.mse_bat_runs, 'n': int(r.n)}
                   for r in table.itertuples()],
        'params': jsonable(best), 'params_hinf': jsonable(p_inf),
        'lambda_runs_per_wicket': RT.lambda_runs_per_wicket(T, CUTOFF),
        'content_hash': RT.content_hash(asof), 'content_hash_hinf': RT.content_hash(asof_inf),
        'seconds': round(time.time() - t0, 1),
    }
    rep = Path(a.reports)
    rep.mkdir(parents=True, exist_ok=True)
    (rep / 'ratings_build.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ('balls', 'rated_rows', 'players', 'h_grid', 'lambda_runs_per_wicket',
                                              'content_hash', 'seconds')}, indent=2))
    print('chosen h:', summary['params']['h'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
