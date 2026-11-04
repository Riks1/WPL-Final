"""Stage 1 audit of the v0 models: re-run the ORIGINAL notebook code and show why its
reported numbers (accuracy 73.8%, AUC 0.586, log-loss 0.652) are not valid.

    pip install -r legacy/requirements-audit.txt
    python -m legacy.audit_v0 --snapshot data/snapshots/<file>.zip

The original notebook read a `wpl_data/` folder that no cell created, so its exact
inputs are unknown. This script uses the matches dated on or before the original run
(2026-01-14) from the given snapshot, applies only the fix needed for the code to run
at all (`winner_AA` -> `winner_A`), and prints what it finds.
"""

import argparse
import json
import os
import pickle
import shutil
import sys
import tempfile
import warnings
import zipfile
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"   # also silences joblib worker processes
HERE = Path(__file__).resolve().parent
REPORTED = {"prematch_accuracy": 0.7385, "prematch_auc": 0.5858, "live_logloss": 0.6524}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--cutoff", default="2026-01-14")
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp())
    (work / "wpl_data").mkdir()
    with zipfile.ZipFile(args.snapshot) as z:
        for n in z.namelist():
            if n.endswith(".json"):
                m = json.loads(z.read(n))
                if m["info"]["dates"][0] <= args.cutoff:
                    (work / "wpl_data" / Path(n).name).write_bytes(z.read(n))

    src = (HERE / "notebook_v0_functions.py").read_text().replace("test_df['winner_AA']", "test_df['winner_A']")
    ns = {}
    exec(src, ns)
    cwd = os.getcwd()
    os.chdir(work)
    try:
        m = ns["load_and_extract_match_data"]("wpl_data")
        mf = ns["build_match_features"](m)
        b = ns["live_features_add"](ns["load_ball_by_ball_data"]("wpl_data"))
        pm = ns["train_prematch_model"](mf)
        lm = ns["train_live_model"](b)
    finally:
        os.chdir(cwd)
        shutil.rmtree(work)

    split = int(len(mf) * 0.6)
    test = mf.iloc[split:]
    p = pm["model"].predict_proba(test[pm["features"]])[:, 1]
    majority = max(test["winner_A"].mean(), 1 - test["winner_A"].mean())

    print(f"matches with a winner (<= {args.cutoff}): {len(m)}")
    print(f"\n{'':40s}{'reported':>10s}{'re-run':>10s}")
    print(f"{'pre-match test accuracy':40s}{REPORTED['prematch_accuracy']:>10.3f}{pm['metrics']['Test_Accuracy']:>10.3f}")
    print(f"{'pre-match test AUC':40s}{REPORTED['prematch_auc']:>10.3f}{pm['metrics']['test_auc']:>10.3f}")
    print(f"{'live CV log-loss':40s}{REPORTED['live_logloss']:>10.3f}{lm['metrics']['logloss']:>10.3f}")
    print("\nWhy these numbers are not valid:")
    print(f" 1. Pre-match predicts class 1 for {np.mean(p > 0.5):.0%} of test rows; accuracy "
          f"{pm['metrics']['Test_Accuracy']:.3f} vs majority-class share {majority:.3f}.")
    print(f" 2. Pre-match table has {len(mf)} rows from {len(m)} matches: teams merged on (file-creation date, venue).")
    print(f" 3. toss_won_by_A == toss_choice on {np.mean(mf.toss_won_by_A == mf.toss_choice):.0%} of rows (same column twice).")
    print(f" 4. Live target / required_rr nonzero on {int((b.target != 0).sum())} / {int((b.required_rr != 0).sum())} "
          f"of {len(b)} rows: the chase never knew the target.")
    print(f" 5. Live CV folds: rows sorted by (innings, over, ball) across ALL matches; first rows: "
          f"{b[['innings', 'over_num', 'ball_num']].head(3).values.tolist()} -> every match is in train and validation.")
    with open(HERE / "models" / "live_model.pkl", "rb") as f:
        v0 = pickle.load(f)
    thr = [t for e in v0["model"].estimators_[:20] for f_, t in zip(e.tree_.feature, e.tree_.threshold) if f_ == 1]
    print(f" 6. Deployed RF split thresholds on cum_runs span [{min(thr):.2f}, {max(thr):.2f}] (z-scores), "
          f"but the v0 API sent raw runs and no scaler was saved.")


if __name__ == "__main__":
    sys.exit(main())
