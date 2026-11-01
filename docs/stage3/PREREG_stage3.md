# PREREG — Stage 3 pre-match evaluation

Status: **approved (all recommended options).** It is committed with `RATINGS_SPEC.md` (v1.1) and tagged `prereg-s3` before any test-season outcome score is computed. Any later change needs a new version (`prereg-s3.1`, …); results under every version are reported.

## 1. Question
Do XI-strength features (as-of player ratings, RATINGS_SPEC v1.1) improve the post-toss pre-match probability that the team batting first wins, compared with the base rate?

## 2. Frozen inputs
- **Snapshot:** `all_female_json_20261025b.zip`, sha256 `0f5bb2ac113c4e60785bac4f16187b3b3148d6dfca8aee80e9f4921acbf8ac48`.
- **Ratings:** RATINGS_SPEC v1.1, as committed at the `prereg-s3` tag. Hyperparameters fixed by its section 9 before the tag.
- **Label:** D-001, with ties = 0.5 (D-013); there are no ties in the test set.

## 3. Folds and data
- **Test set:** the 66 WPL matches of 2024, 2025 and 2026 (22 each), the same matches as Stage 1. Rolling origin: train on WPL seasons before S, test on S.
- **Training data:** WPL only (pooled training is Stage 4). Fold 2024 trains on 22 matches; 2025 on 44; 2026 on 66.
- **Features:** as-of the match date (strictly earlier balls). Model parameters are fitted on training seasons only.

## 4. Models
| Role | Model | Features |
|---|---|---|
| Baseline | Base rate | Training-season share of matches won by the team batting first |
| **Primary** (only this one can earn deployment) | StandardScaler + LogisticRegression, C = 1.0, no tuning | `xi_margin`, `toss_bf` |
| Secondary S1 (reported only) | Same | `xi_margin`, `toss_bf`, `venue_bf_prior` |
| Secondary S2 (reported only) | Same as primary | `xi_margin` built from ratings with half-life = ∞ |

No post-hoc calibrator (D-004). The definitions of `xi_margin` and `venue_bf_prior` are in RATINGS_SPEC sections 10–11.

## 5. Metric and decision rule
- **Headline:** log-loss per match, with a paired percentile bootstrap over matches (2,000 resamples, seed 0), using `wpl/eval.py`.
- **Rule:** deploy the primary if and only if the upper end of the 95% CI for (primary − base rate) is below 0. Otherwise keep serving the base rate.
- **Also reported:** Brier, ECE, **calibration slope and intercept** (`wpl.eval.calibration_slope_intercept`), accuracy and reliability, for every model.

## 6. Power statement
Stage 1's paired CI on the same 66 matches had a half-width of about 0.067 log-loss. Improvements smaller than roughly 0.07 can't be detected. A no-deploy verdict is likely, and it is a valid result.

## 7. Supporting analysis (never decides deployment)
- **India full-member T20Is, 2024–2026:** the same features and procedure, training on India T20Is before S, with the same metrics.
- **Report:** S1 and S2 alongside the primary.

## 8. Prohibited before the tag
Computing any metric that compares XI-feature predictions with match results on 2024–2026 WPL or India T20I matches.

**Allowed:**
- ball-level rating diagnostics;
- coverage;
- top-N lists;
- hyperparameter selection on balls before 2024-01-01 (RATINGS_SPEC section 9).

## 9. Outputs
The evaluation writes `reports/stage3/prematch_results.json` and `prematch_predictions.csv`, containing:
- every model's out-of-fold predictions;
- the tables;
- the verdict;
- the snapshot sha;
- the ratings content hash;
- **the git commit of `prereg-s3`**.

The verdict also goes into the model card and the README.
