"""Phase 3.4 (D11): the pre-registered pre-match evaluation, run once on the frozen features.

    python -m scripts.evaluate_prematch --snapshot all_female_json_20261025b.zip

Needs scripts.build_xi to have run, and the git tag prereg-s3 to exist."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

import wpl.data.snapshots as S
import wpl.prematch as PM

ROOT = Path(S.ROOT)
MODELS = [PM.BASE] + list(PM.MODELS)
DOCS = ('docs/stage3/PREREG_stage3.md', 'docs/stage3/RATINGS_SPEC.md')


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
def prereg_check():
    """What git can prove about the pre-registration: where the tag points, whether the documents are in it,
    when they were first committed, and their hashes now. It never reports 'unchanged' for files the tag lacks."""
    missing = [d for d in DOCS if not (ROOT / d).exists()]
    if missing:
        raise SystemExit(f'pre-registration documents missing: {missing}')
    tag = git('rev-list', '-n', '1', 'prereg-s3')
    if tag.returncode != 0:
        raise SystemExit('tag prereg-s3 not found: run `git fetch --tags` first')
    in_tag = all(git('cat-file', '-e', f'prereg-s3:{d}').returncode == 0 for d in DOCS)
    unchanged = in_tag and git('diff', '--quiet', 'prereg-s3', 'HEAD', '--', *DOCS).returncode == 0
    first = {d: git('log', '--diff-filter=A', '--format=%H %cI', '--', d).stdout.strip() or 'not committed' for d in DOCS}
    return {'prereg_tag_commit': tag.stdout.strip(), 'docs_in_tag': in_tag, 'docs_unchanged_since_tag': unchanged,
            'docs_first_committed': first, 'docs_sha256': {d: S.sha256_of_file(ROOT / d) for d in DOCS},
            'head_commit': git('rev-parse', 'HEAD').stdout.strip()}
def run(feats,competition):
  pred = PM.rolling_predictions(feats,competition)
  ll, br, extra = PM.metrics(pred, MODELS)
  table = ll.merge(br[['model','brier']],on = 'model').merge(extra,on = 'model')
  return pred,table,PM.verdict(ll)
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', required=True)
    ap.add_argument('--reports', default=str(ROOT / 'reports' / 'stage3'))
    a = ap.parse_args(argv)

    rep = Path(a.reports)
    proc = ROOT / 'data' / 'processed' / Path(a.snapshot).stem
    feats = pd.read_parquet(proc / 'xi_features.parquet')
    build = json.loads((rep / 'ratings_build.json').read_text())
    meta = {'snapshot': a.snapshot, 'snapshot_sha256': S.load_registry()[a.snapshot]['sha256'],
            'ratings_content_hash': build['content_hash'], 'h': build['params']['h'], **prereg_check(),
            'n_boot': 2000, 'seed': 0}

    preds, results, md = [], {}, []
    for label, comp in (('wpl', PM.WPL), ('india_t20i_supporting', PM.INDIA)):
        if not (feats.competition == comp).any():
            continue
        pred, table, v = run(feats, comp)
        preds.append(pred)
        washed = feats[(feats.competition == comp) & (feats.result_type == 'no_result') & feats.season.isin(PM.TEST_SEASONS)]
        results[label] = {'n_matches': len(pred), 'excluded_no_result': washed.match_id.tolist(), 'matches_by_season': pred.season.value_counts().sort_index().to_dict(),
                          'table': table.to_dict('records'), 'verdict_if_deciding': v}
        md += [f'## {comp} ({len(pred)} test matches){"" if label == "wpl" else " - supporting only, never decides"}',
               table.round(4).to_markdown(index=False),
               f"primary - base_rate log-loss: {v['delta']:+.4f} [{v['ci_low']:+.4f}, {v['ci_high']:+.4f}]"]

    decision = results['wpl']['verdict_if_deciding']
    out = {'question': 'Do XI-strength features beat the base rate pre-match? (PREREG_stage3.md)',
           'decision': decision, **results, 'metadata': meta}
    pd.concat(preds, ignore_index=True).to_csv(rep / 'prematch_predictions.csv', index=False)
    (rep / 'prematch_results.json').write_text(json.dumps(out, indent=2, default=str))
    head = ['# Stage 3 pre-match evaluation (D11)',
            (f"Pre-registration in tag `prereg-s3` ({meta['prereg_tag_commit'][:12]}), unchanged since." if meta['docs_in_tag'] else
             f"Note: tag `prereg-s3` ({meta['prereg_tag_commit'][:12]}) does not contain the pre-registration documents; "
             f"first committed: {meta['docs_first_committed'][DOCS[0]]}. See the model card."),
            f"Snapshot `{a.snapshot}`; ratings `{meta['ratings_content_hash'][:16]}…`; h = {meta['h']}.",
            f"**Verdict: serve `{decision['serve']}`** - primary vs base rate {decision['delta']:+.4f} "
            f"[{decision['ci_low']:+.4f}, {decision['ci_high']:+.4f}]; deploy iff the upper bound < 0."]
    (rep / 'prematch_results.md').write_text('\n\n'.join(head + md) + '\n')
    print('\n\n'.join(head + md))
    return 0


if __name__ == '__main__':
    sys.exit(main())
