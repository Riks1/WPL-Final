# Model card: pre-match win probability, v3 (Stage 3)

**Served model: base rate, P(team batting first wins) = 0.398** (88 WPL matches, seasons 2023-2026).

## Question

Do XI-strength features (as-of empirical Bayes player ratings, docs/stage3/RATINGS_SPEC.md) improve the post-toss pre-match probability over the base rate? Plan: docs/stage3/PREREG_stage3.md.

## Evaluation design

- Test set: 66 WPL matches, seasons 2024-2026; rolling origin (train on earlier WPL seasons only).

- Primary: StandardScaler + LogisticRegression(C=1.0) on `xi_margin`, `toss_bf`. Secondary (reported only): S1 adds `venue_bf_prior`; S2 uses ratings with no time decay.

- Metric: per-match log-loss; paired percentile bootstrap over matches (2,000 resamples, seed 0).

- Rule, fixed in advance: deploy the primary only if the 95% CI upper bound of (primary - base rate) < 0.

## Result (WPL, decides deployment)

| model     |   log_loss |   delta |   delta_ci_low |   delta_ci_high |   brier |   ece |   cal_slope |   cal_intercept |   accuracy |
|:----------|-----------:|--------:|---------------:|----------------:|--------:|------:|------------:|----------------:|-----------:|
| base_rate |      0.703 |   0     |          0     |           0     |   0.254 | 0.116 |      -1.706 |           0.234 |      0.576 |
| primary   |      0.789 |   0.087 |          0.012 |           0.162 |   0.283 | 0.173 |      -0.792 |           0.189 |      0.53  |
| s1        |      0.826 |   0.123 |          0.055 |           0.197 |   0.3   | 0.198 |      -1.457 |           0.261 |      0.53  |
| s2        |      0.79  |   0.088 |          0.014 |           0.162 |   0.283 | 0.131 |      -0.812 |           0.187 |      0.53  |

**Verdict: serve the base rate.** Primary - base rate = +0.087 [+0.012, +0.162]: the primary is worse, with the whole interval above 0.

The primary's calibration slope is -0.79: across the test matches its favourites lost more often than its underdogs, the signature of coefficients fitted on 22-66 matches.

## Supporting analysis: India T20Is (53 test matches; never decides)

| model     |   log_loss |   delta |   delta_ci_low |   delta_ci_high |   brier |   ece |   cal_slope |   cal_intercept |   accuracy |
|:----------|-----------:|--------:|---------------:|----------------:|--------:|------:|------------:|----------------:|-----------:|
| base_rate |      0.694 |   0     |          0     |           0     |   0.25  | 0.015 |     -16.124 |           0.058 |      0.509 |
| primary   |      0.491 |  -0.203 |         -0.312 |          -0.079 |   0.166 | 0.164 |       1.148 |           0.035 |      0.717 |
| s1        |      0.51  |  -0.184 |         -0.302 |          -0.05  |   0.172 | 0.127 |       1.046 |          -0.113 |      0.717 |
| s2        |      0.493 |  -0.201 |         -0.306 |          -0.085 |   0.165 | 0.133 |       1.259 |           0.017 |      0.698 |

Primary - base rate = -0.203 [-0.312, -0.079]. The same features and code carry real signal where strength gaps are larger and training data longer. The base rate there is close to 0.5, a weak baseline, so this supports the ratings but is not a headline result.

Excluded no-results in test seasons: ['1434292'].

## Pre-registration record

The analysis plan, decision rule and hyperparameters were approved before any test-season outcome was scored. Through a tagging error, the tag `prereg-s3` (308c096) points to a Stage 2 commit that does not contain the documents; they were first committed at e39e0a3 (2026-11-01), after the evaluation first ran. What git records independently: the ratings and the match features were committed before the evaluation results (ratings summary 03cb314 2026-10-29; features 81cec9a 2026-10-29; evaluation code e3af417 2026-11-01). Document SHA-256: `PREREG_stage3.md` 3b62451cd73ec4b9…; `RATINGS_SPEC.md` 90ec09baabf53041….

## Data and versions

- Snapshot `all_female_json_20261025b.zip` (sha256 0f5bb2ac113c4e60…); ratings content hash 1e5c4bd424cfdd6b…; half-life h = 4.0 years.

- Excluded no-results in WPL test seasons: none.

- Rebuilt from scratch in the same software environment, the ratings reproduced the same content hash. After a later Colab library update a rebuild gave a different hash (`566af77f…`, the build behind the served `models/ratings_v3.json`) with every match feature within 1.4e-14 runs of the evaluated build: exact reproducibility holds per software environment, and build summaries now record library versions.

## Limitations

- WPL has 22 matches a season: the evaluation can only detect log-loss gains of about 0.07 or more.

- WPL-only training (pooled training across competitions is Stage 4).

- No impact-player swaps; India T20I data gaps in 2013, 2015 and 2017; Indian domestic cricket absent, so uncapped players start at the debutant prior.

- The base rate ignores the teams entirely; it is served because nothing tested beat it.

## Reproduce

```
python -m scripts.build_ratings --snapshot all_female_json_20261025b.zip
python -m scripts.build_xi --snapshot all_female_json_20261025b.zip
python -m scripts.evaluate_prematch --snapshot all_female_json_20261025b.zip
python -m scripts.write_prematch_card --snapshot all_female_json_20261025b.zip
```
