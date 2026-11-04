# Technical report: Stages 1–3

[`wpl_stage1-3_report.pdf`](wpl_stage1-3_report.pdf) — *Win Probability for the Women's Premier League: A Reproducible
Baseline, As-Of Player Ratings, and a Pre-Specified Null Result* (November 2026).

Every number in the results tables is generated from committed repository files, not typed by hand:

```bash
python paper/make_tables.py .        # from the repo root: rewrites paper/tab_*.tex from reports/ and the evaluation code
cd paper && latexmk -pdf main.tex    # or upload this folder to Overleaf
```

`make_tables.py` also computes the exploratory per-fold breakdown (Table 6), which was computed after the Stage 3
results were committed and cannot change the verdict.
