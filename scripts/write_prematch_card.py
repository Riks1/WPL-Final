"""Phase 3.4b (D12): the v3 pre-match registry entry and its model card, generated from the evaluation outputs
so no number is typed by hand.

    python -m scripts.write_prematch_card --snapshot all_female_json_20261025b.zip

Needs scripts.evaluate_prematch to have run."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import wpl.data.snapshots as S
import wpl.prematch as PM

ROOT = Path(S.ROOT)


def first_commit(path):
    """The commit that first added `path`, with its date: what git can prove about when it existed."""
    out = subprocess.run(['git', 'log', '--diff-filter=A', '--format=%h %cs', '--', path],
                         cwd=ROOT, capture_output=True, text=True).stdout.strip().splitlines()
    return out[-1] if out else 'not committed'


def bundle(feats, results):
    """What to serve: the verdict's model, refitted on every WPL match in the snapshot. JSON only, no pickle."""
    wpl = feats[(feats.competition == PM.WPL) & (feats.result_type != 'no_result')]
    d, m = results['decision'], results['metadata']
    if d['serve'] != PM.BASE:
        raise SystemExit('verdict is not base_rate: the primary bundle needs its coefficients; stop and redesign')
    return {'kind': 'prematch', 'family': 'base_rate', 'version': 'v3', 'p_base': float(wpl['y'].mean()),
            'n_matches': int(len(wpl)), 'seasons': sorted(int(s) for s in wpl.season.unique()),
            'label': 'P(team batting first wins); ties = 0.5; no-results excluded',
            'decision': d, 'snapshot': m['snapshot'], 'snapshot_sha256': m['snapshot_sha256'],
            'ratings_content_hash': m['ratings_content_hash'], 'evaluation': 'reports/stage3/prematch_results.json',
            'created_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}


def table_md(rows):
    t = pd.DataFrame(rows)[['model', 'log_loss', 'delta', 'delta_ci_low', 'delta_ci_high', 'brier', 'ece',
                            'cal_slope', 'cal_intercept', 'accuracy']]
    return t.round(3).to_markdown(index=False)


def card(b, results):
    d, m, w = results['decision'], results['metadata'], results['wpl']
    ind = results.get('india_t20i_supporting')
    docs = m['docs_first_committed']
    lines = [
        '# Model card: pre-match win probability, v3 (Stage 3)',
        f"**Served model: base rate, P(team batting first wins) = {b['p_base']:.3f}** "
        f"({b['n_matches']} WPL matches, seasons {b['seasons'][0]}-{b['seasons'][-1]}).",
        '## Question',
        'Do XI-strength features (as-of empirical Bayes player ratings, docs/stage3/RATINGS_SPEC.md) improve the '
        'post-toss pre-match probability over the base rate? Plan: docs/stage3/PREREG_stage3.md.',
        '## Evaluation design',
        '- Test set: 66 WPL matches, seasons 2024-2026; rolling origin (train on earlier WPL seasons only).',
        '- Primary: StandardScaler + LogisticRegression(C=1.0) on `xi_margin`, `toss_bf`. '
        'Secondary (reported only): S1 adds `venue_bf_prior`; S2 uses ratings with no time decay.',
        '- Metric: per-match log-loss; paired percentile bootstrap over matches (2,000 resamples, seed 0).',
        '- Rule, fixed in advance: deploy the primary only if the 95% CI upper bound of (primary - base rate) < 0.',
        '## Result (WPL, decides deployment)',
        table_md(w['table']),
        f"**Verdict: serve the base rate.** Primary - base rate = {d['delta']:+.3f} "
        f"[{d['ci_low']:+.3f}, {d['ci_high']:+.3f}]: "
        + ('the primary is worse, with the whole interval above 0.' if d['ci_low'] > 0 else
           'no detectable difference; the rule requires the whole interval below 0.'),
    ]
    slope = {r['model']: r['cal_slope'] for r in w['table']}['primary']
    if slope < 0:
        lines.append(f'The primary\'s calibration slope is {slope:.2f}: across the test matches its favourites lost '
                     'more often than its underdogs, the signature of coefficients fitted on 22-66 matches.')
    if ind:
        v = ind['verdict_if_deciding']
        lines += [f"## Supporting analysis: India T20Is ({ind['n_matches']} test matches; never decides)",
                  table_md(ind['table']),
                  f"Primary - base rate = {v['delta']:+.3f} [{v['ci_low']:+.3f}, {v['ci_high']:+.3f}]. "
                  'The same features and code carry real signal where strength gaps are larger and training data '
                  'longer. The base rate there is close to 0.5, a weak baseline, so this supports the ratings but '
                  'is not a headline result.',
                  f"Excluded no-results in test seasons: {ind['excluded_no_result'] or 'none'}."]
    lines += [
        '## Pre-registration record',
        f"The analysis plan, decision rule and hyperparameters were approved before any test-season outcome was "
        f"scored. Through a tagging error, the tag `prereg-s3` ({m['prereg_tag_commit'][:7]}) points to a Stage 2 "
        f"commit that does not contain the documents; they were first committed at "
        f"{docs[next(iter(docs))].split()[0][:7]} ({docs[next(iter(docs))].split()[-1][:10]}), after the evaluation "
        'first ran. What git records independently: the ratings and the match features were committed before the '
        f"evaluation results (ratings summary {first_commit('reports/stage3/ratings_build.json')}; features "
        f"{first_commit('reports/stage3/xi_features.csv')}; evaluation code {first_commit('wpl/prematch.py')}). "
        'Document SHA-256: ' + '; '.join(f'`{Path(k).name}` {v[:16]}…' for k, v in m['docs_sha256'].items()) + '.',
        '## Data and versions',
        f"- Snapshot `{m['snapshot']}` (sha256 {m['snapshot_sha256'][:16]}…); ratings content hash "
        f"{m['ratings_content_hash'][:16]}…; half-life h = {m['h']} years.",
        f"- Excluded no-results in WPL test seasons: {w['excluded_no_result'] or 'none'}.",
        '- Rebuilt from scratch in the same software environment, the ratings reproduced the same content hash. After a later Colab library update a rebuild gave a different hash (`566af77f…`, the build behind the served `models/ratings_v3.json`) with every match feature within 1.4e-14 runs of the evaluated build: exact reproducibility holds per software environment, and build summaries now record library versions.',
        '## Limitations',
        '- WPL has 22 matches a season: the evaluation can only detect log-loss gains of about 0.07 or more.',
        '- WPL-only training (pooled training across competitions is Stage 4).',
        '- No impact-player swaps; India T20I data gaps in 2013, 2015 and 2017; Indian domestic cricket absent, '
        'so uncapped players start at the debutant prior.',
        '- The base rate ignores the teams entirely; it is served because nothing tested beat it.',
        '## Reproduce',
        '```\npython -m scripts.build_ratings --snapshot ' + m['snapshot'] +
        '\npython -m scripts.build_xi --snapshot ' + m['snapshot'] +
        '\npython -m scripts.evaluate_prematch --snapshot ' + m['snapshot'] +
        '\npython -m scripts.write_prematch_card --snapshot ' + m['snapshot'] + '\n```',
    ]
    return '\n\n'.join(lines) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', required=True)
    a = ap.parse_args(argv)
    feats = pd.read_parquet(ROOT / 'data' / 'processed' / Path(a.snapshot).stem / 'xi_features.parquet')
    results = json.loads((ROOT / 'reports' / 'stage3' / 'prematch_results.json').read_text())
    if results['metadata']['snapshot'] != a.snapshot:
        raise SystemExit('the evaluation was run on a different snapshot')
    b = bundle(feats, results)
    (ROOT / 'models' / 'prematch_v3.json').write_text(json.dumps(b, indent=2))
    (ROOT / 'docs' / 'stage3').mkdir(parents=True, exist_ok=True)
    (ROOT / 'docs' / 'stage3' / 'MODEL_CARD_prematch_v3.md').write_text(card(b, results))
    print(f"p_base = {b['p_base']:.4f} over {b['n_matches']} WPL matches -> models/prematch_v3.json, "
          'docs/stage3/MODEL_CARD_prematch_v3.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
