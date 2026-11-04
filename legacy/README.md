# legacy/ — the v0 audit

The original version of this project (v0, tag [`v0-legacy`](https://github.com/Riks1/WPL-Final/tree/v0-legacy)) reported a pre-match
accuracy of 73.8% and a live log-loss of 0.652. Stage 1 began by re-running its code. Neither number survives.

```bash
pip install -r requirements-dev.txt -r legacy/requirements-audit.txt
python -m legacy.audit_v0 --snapshot data/snapshots/wpl_json_20261025.zip
```

The script executes the original notebook's functions (`notebook_v0_functions.py`, extracted from
`notebook/Untitled0_v0_redacted.ipynb`) with one fix needed to make them run at all, then prints what it finds:

1. The pre-match model predicts the same class for every test match; its accuracy equals the majority-class share.
2. The pre-match table has more rows than matches: teams were merged on (file-creation date, venue).
3. `toss_won_by_A` and `toss_choice` are the same column twice.
4. The live model never saw the target: `target` and `required_rr` are 0 on every training row.
5. Cross-validation split ball rows across all matches, so every match was in both training and validation.
6. The deployed random forest splits on standardised inputs, but the v0 API sent raw runs and no scaler was saved.

`models/*.pkl` are the v0 artefacts, kept only as evidence for finding 6. They are untrusted pickles: the
audit loads them in isolation, and the application never does (it serves plain JSON models from `models/`).
