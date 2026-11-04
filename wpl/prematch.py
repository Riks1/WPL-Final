"""Phase 3.4: the pre-registered pre-match evaluation (PREREG_stage3.md §3-§7).
Rolling origin by season; base rate vs StandardScaler + LogisticRegression(C=1.0); paired bootstrap verdict."""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import wpl.eval as EV

WPL = "Women's Premier League"
INDIA = 'T20I India'
TEST_SEASONS = (2024, 2025, 2026)
BASE = 'base_rate'
MODELS = {'primary': ['xi_margin', 'toss_bf'],
          's1': ['xi_margin', 'toss_bf', 'venue_bf_prior'],
          's2': ['xi_margin_hinf', 'toss_bf']}

def expand_ties(X, y):
    """scikit-learn needs 0/1 labels. A tie (y = 0.5) becomes one win row and one loss row, each with
    weight 0.5, which gives exactly the same log-likelihood as a 0.5 label (D-013)."""
    y = np.asarray(y, float)
    tie = y == 0.5
    Xe = np.vstack([X[~tie], X[tie], X[tie]])
    ye = np.concatenate([y[~tie], np.ones(tie.sum()), np.zeros(tie.sum())]).astype(int)
    w = np.concatenate([np.ones((~tie).sum()), np.full(2 * tie.sum(), 0.5)])
    return Xe, ye, w

def fit_logistic(train,features):
  X,y,w = expand_ties(train[features].to_numpy(float),train['y'])
  model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0))
  model.fit(X,y,logisticregression__sample_weight = w)
  return model
def rolling_predictions(feats, competition=WPL, test_seasons=TEST_SEASONS):
    """Out-of-fold predictions: for each test season S, fit on that competition's seasons before S only."""
    d = feats[(feats.competition == competition) & (feats.result_type != 'no_result')]   # D-001: no winner, no label
    d = d.sort_values(['date', 'match_id'])
    cols = sorted({c for f in MODELS.values() for c in f})
    if d[cols + ['y']].isna().any().any():
        raise ValueError('missing feature values: the evaluation never imputes')
    out = []
    for S in test_seasons:
        train, test = d[d.season < S], d[d.season == S]
        if train.empty or test.empty:
            continue
        p = test[['match_id', 'date', 'season', 'competition', 'y']].copy()
        p[BASE] = train['y'].mean()
        for name, f in MODELS.items():
            p[name] = fit_logistic(train, f).predict_proba(test[f].to_numpy(float))[:, 1]
        out.append(p)
    return pd.concat(out, ignore_index=True)

def safe_calibration(y, p):
    """Calibration slope/intercept, or NaN when they can't be fitted (e.g. a near-constant base rate)."""
    try:
        with np.errstate(all='ignore'):
            c = EV.calibration_slope_intercept(y, p)
        return c if np.isfinite(list(c.values())).all() else {'slope':np.nan,'intercept':np.nan}
    except np.linalg.LinAlgError:
        return {'slope': np.nan, 'intercept': np.nan}
def metrics(pred, models):
  ll = EV.bootstrap_table(pred, models, 'log_loss', reference=BASE)
  br = EV.bootstrap_table(pred, models, 'brier', reference=BASE)
  decided = pred['y'] != 0.5
  extra = []
  for m in models:
      cal = safe_calibration(pred['y'], pred[m])
      extra.append({'model': m, 'ece': EV.ece(pred['y'], pred[m]), 'cal_slope': cal['slope'],
                      'cal_intercept': cal['intercept'],
                      'accuracy': float(((pred.loc[decided, m] > 0.5) == (pred.loc[decided, 'y'] > 0.5)).mean())})
  return ll, br, pd.DataFrame(extra)

def verdict(ll):
    """PREREG §5: deploy the primary iff the upper end of the 95% CI of (primary - base rate) is below 0."""
    r = ll.set_index('model').loc['primary']
    deploy = bool(r['delta_ci_high'] < 0)
    return {'rule': 'deploy primary iff the 95% CI upper bound of log-loss(primary) - log-loss(base_rate) < 0',
            'delta': float(r['delta']), 'ci_low': float(r['delta_ci_low']), 'ci_high': float(r['delta_ci_high']),
            'deploy_primary': deploy, 'serve': 'primary' if deploy else BASE}
