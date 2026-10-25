"""Par-score prediction from saved parameters. Mirrors the notebook's ParScore.predict exactly
(tests/test_parity_fixture.py checks the app reproduces the notebook's probabilities)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import special, stats

from wpl.live_features import terminal_prob


def expected_runs(params: dict, balls_left, wickets_lost) -> np.ndarray:
    """E[runs still to come]. DLS form: (r/b)(1 - exp(-b u)), u = overs left, w = wickets lost."""
    u = np.asarray(balls_left, float) / 6.0
    w = np.asarray(wickets_lost, float)
    th = params['theta']
    if params['mean'] == 'dls':
        a0, t1, c0, c1 = th[:4]
        r = np.exp(a0 - np.exp(t1) * w)
        b = np.exp(c0 + c1 * w)
        mu = (r / b) * (-np.expm1(-b * u))
    else:
        x = u / 20.0
        X = np.column_stack([np.ones_like(u), w, w ** 2, x, w * x])
        mu = np.exp(np.log(np.maximum(u, 1e-9)) + X @ np.asarray(th[:5]))
    return np.where((u <= 0) | (w >= 10), 0.0, mu)


def _pmf(params, k, mu):
    if params['noise'] == 'poisson':
        return stats.poisson.pmf(k, mu)
    a = params['alpha']
    return stats.nbinom.pmf(k, 1 / a, 1 / (1 + a * mu))


def _cdf(params, k, mu):
    if params['noise'] == 'poisson':
        return stats.poisson.cdf(k, mu)
    a = params['alpha']
    return stats.nbinom.cdf(k, 1 / a, 1 / (1 + a * mu))


def predict(params: dict, df: pd.DataFrame) -> np.ndarray:
    """P(team batting first wins) for rows with live features (see wpl.live_features)."""
    mu = np.maximum(expected_runs(params, df['balls_remaining'].values, df['cum_wickets'].values), 1e-12)
    live = mu > 1e-9
    out = np.empty(len(df))
    link = params['link']
    m1 = (df['innings'] == 1).values
    if m1.any():
        k = np.arange(params['r_max'] + 1)
        pmf = np.where(live[m1, None], _pmf(params, k[None, :], mu[m1, None]), (k[None, :] == 0).astype(float))
        pmf /= pmf.sum(axis=1, keepdims=True)
        totals = df['cum_runs'].values[m1][:, None] + k[None, :]
        out[m1] = (pmf * special.expit(link['a'] + link['c'] * (totals - link['t_mean']) / link['t_sd'])).sum(axis=1)
    m2 = (df['innings'] == 2).values
    if m2.any():
        need = df['runs_needed'].values[m2]
        out[m2] = _cdf(params, need - 2, mu[m2]) + 0.5 * _pmf(params, need - 1, mu[m2])
    term = terminal_prob(df).values
    return np.where(np.isnan(term), out, term)
