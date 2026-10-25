---
title: WPL Win Probability
sdk: docker
app_port: 7860
---

# WPL Decision Engine: live win probability (stage 1 of 10)

![CI](https://github.com/Riks1/WPL-Final/actions/workflows/ci.yml/badge.svg)

Ball-by-ball win probability for the Women's Premier League, served by a Flask API on a Hugging Face Space.
Stage 1 rebuilt the project from an audit of the original version (v0). Every number below comes from
`notebooks/stage1_training.ipynb` on the snapshot `data/snapshots/wpl_json_20261025.zip`
(sha256 `533e7937056b47f1…`); the full report is in `reports/stage1/results.md`.

**Label.** P(team batting first wins). A tie decided by a super over counts for the super-over winner; no-results are excluded.

## Results (66 held-out matches)

Rolling-origin evaluation by season: train on every season before S, test on S (2024, 2025, 2026).
95% intervals come from a bootstrap over matches, paired across models.

| Model | Log-loss per match [95% CI] | Δ vs base rate [95% CI] | Brier |
|---|---|---|---|
| Base rate | 0.703 [0.633, 0.770] | 0 | 0.254 |
| **Par-score: DLS resource curve + negative binomial (deployed)** | **0.528 [0.428, 0.633]** | **−0.175 [−0.286, −0.059]** | **0.179** |
| Same curve, Poisson noise (reference) | 0.663 [0.472, 0.874] | −0.040 [−0.235, 0.178] | 0.190 |
| Logistic regression, per innings | 0.575 [0.453, 0.717] | −0.128 [−0.243, 0.002] | 0.190 |
| Random forest, per innings | 0.652 [0.512, 0.814] | −0.050 [−0.185, 0.101] | 0.208 |

- **Deployment rule, fixed before the final run:** the par-score model is deployed unless a learned model beats
  it with a paired 95% CI excluding 0. Logistic − par-score = +0.047 [−0.023, +0.118]; random forest − par-score =
  +0.124 [+0.045, +0.208]. So the 5-parameter par-score model is deployed.
- **No post-hoc calibrator.** Fitted on earlier seasons only, Platt (+0.060 [+0.006, +0.116]) and isotonic
  (+0.082 [+0.023, +0.144]) made the par-score model worse; temperature scaling changed nothing (+0.004 [−0.031, +0.037]).
  Season-to-season differences in how often the team batting first wins are consistent with noise
  (7, 11, 7 and 10 of 22; χ² = 2.42, p = 0.49).
- **Pre-match information did not help.** A post-toss model (form, head-to-head, toss) scored worse than the base rate
  (+0.066 [+0.001, +0.135]), so `/api/prematch-predict` serves the base rate and says so in its response.

## What the audit found in v0

Reproducible with `python -m legacy.audit_v0 --snapshot data/snapshots/wpl_json_20261025.zip`.

1. The pre-match "73.8% accuracy" equalled the majority-class rate: the model predicted the same class for every test match.
2. The live model never saw the target: `target`, `runs_needed` and `required_rr` were 0 on every training row.
3. The live "log-loss 0.652" leaked: cross-validation split ball rows, so every match was in train and validation.
4. The deployed live model received unscaled inputs (it was trained on standardised ones), giving ~51–53% for both won and lost chases.
5. `class_weight='balanced'` distorted the probabilities.

Design decisions and their evidence: `docs/DECISIONS.md`.

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/live-predict` | POST | Win probability from the ball history of the current innings |
| `/api/prematch-predict` | POST | After the toss, before ball 1 (currently the base rate) |
| `/api/model-info` | GET | Model card: data hash, training date, library versions, deployment decision |
| `/api/history` | GET | Recent logged predictions |
| `/api/health` | GET | Model load status |

```json
POST /api/live-predict
{"innings": 2, "target": 166,
 "balls": [{"runs": 4, "legal": true, "wickets": 0}, {"runs": 1, "legal": false, "wickets": 0}]}
```
`runs` is the total off the delivery including extras; `legal` is false for wides and no-balls; `wickets` counts
dismissals (retired hurt is 0). The server computes the score, recent runs and wickets (last 30 legal balls)
and the current partnership with the same code as the training notebook. `tests/test_parity_fixture.py`
checks the API reproduces the notebook's probabilities on 200 real match states.

## Reproduce

- **Training and evaluation:** open `notebooks/stage1_training.ipynb` in Colab and run all. It verifies the snapshot hash.
- **App and tests:** `pip install -r requirements-dev.txt && pytest -v`, then `python run.py`.

## Limitations

- No team, player or venue information in the live model yet (stage 3).
- WPL only: about 22 matches per season, so intervals are wide. Seasons 2023–25 were also used during development,
  so the genuinely independent test of the deployment rule is WPL 2027.
- The prediction log is stored on the Space's temporary disk and is lost on restart.

## License

MIT, see [LICENSE](LICENSE).
