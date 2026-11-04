"""Evaluation harness, ported unchanged from the Stage 1 notebook (D-003): rolling-origin season folds,
log-loss / Brier, match-level paired bootstrap (2,000 resamples, seed 0), reliability and ECE."""
import numpy as np
import pandas as pd

EPS = 1e-6
N_BOOT, SEED = 2000, 0


def season_folds(seasons, min_train_seasons=1):
    """Rolling origin: train on every season before S, test on S."""
    s = sorted(set(int(x) for x in seasons))
    return [(s[:i], s[i]) for i in range(min_train_seasons, len(s))]


def log_loss_vec(y, p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    y = np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def brier_vec(y, p):
    return (np.asarray(p, float) - np.asarray(y, float)) ** 2


LOSSES = {'log_loss': log_loss_vec, 'brier': brier_vec}


def bootstrap_table(df, models, loss='log_loss', weighting='match', reference=None,
                    n_boot=N_BOOT, seed=SEED, alpha=0.05):
    """Point estimate and percentile CI per model, plus paired differences vs `reference`.
    The match is the resampling unit, and the SAME resampled matches are used for every model."""
    f = LOSSES[loss]
    codes, uniq = pd.factorize(df['match_id'].values)
    n = len(uniq)
    counts = np.bincount(codes, minlength=n).astype(float)
    sums = np.column_stack([np.bincount(codes, weights=f(df['y'].values, df[m].values), minlength=n) for m in models])

    def stat(s, c):
        return (s / c[..., None]).mean(axis=-2) if weighting == 'match' else s.sum(axis=-2) / c.sum(axis=-1)[..., None]

    point = stat(sums, counts)
    idx = np.random.default_rng(seed).integers(0, n, size=(n_boot, n))
    boot = np.stack([stat(sums[i], counts[i]) for i in idx])
    lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2], axis=0)
    rows = []
    for k, m in enumerate(models):
        r = {'model': m, loss: point[k], 'ci_low': lo[k], 'ci_high': hi[k]}
        if reference is not None:
            d = boot[:, k] - boot[:, models.index(reference)]
            r['delta'] = point[k] - point[models.index(reference)]
            r['delta_ci_low'], r['delta_ci_high'] = np.quantile(d, [alpha / 2, 1 - alpha / 2])
        rows.append(r)
    out = pd.DataFrame(rows)
    out.attrs.update(n_matches=n, n_rows=int(counts.sum()))
    return out


def paired_delta(df, a, b, n_boot=N_BOOT, seed=SEED):
    """Per-match log-loss of a minus b, with paired bootstrap CI. Negative = a is better."""
    r = bootstrap_table(df, [a, b], reference=b, n_boot=n_boot, seed=seed).iloc[0]
    return {'a': a, 'b': b, 'delta': float(r['delta']), 'ci_low': float(r['delta_ci_low']),
            'ci_high': float(r['delta_ci_high'])}


def reliability(y, p, n_bins=10):
    y, p = np.asarray(y, float), np.asarray(p, float)
    bins = np.clip((p * n_bins).astype(int), 0, n_bins - 1)
    rows = [{'bin': b, 'mean_pred': p[bins == b].mean(), 'observed': y[bins == b].mean(), 'n': int((bins == b).sum())}
            for b in range(n_bins) if (bins == b).any()]
    return pd.DataFrame(rows)


def ece(y, p, n_bins=10):
    r = reliability(y, p, n_bins)
    return float((r['n'] * (r['mean_pred'] - r['observed']).abs()).sum() / r['n'].sum())
def _logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def _fit_logistic(y, X, offset, iters=50):

    b = np.zeros(X.shape[1])
    for _ in range(iters):
        mu = 1 / (1 + np.exp(-(X @ b + offset)))
        grad = X.T @ (y - mu)
        hess = X.T @ (X * (mu * (1 - mu))[:, None])
        step = np.linalg.solve(hess, grad)
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return b


def calibration_slope_intercept(y, p):
    """Clinical-prediction calibration (TRIPOD). Slope: fit y ~ a + b*logit(p); 1 is ideal, <1 means
    over-confident. Intercept (calibration-in-the-large): fit y ~ a + offset(logit(p)); 0 is ideal."""
    y, z = np.asarray(y, float), _logit(p)
    slope = _fit_logistic(y, np.column_stack([np.ones_like(z), z]), np.zeros_like(z))[1]
    intercept = _fit_logistic(y, np.ones((len(z), 1)), z)[0]
    return {'slope': float(slope), 'intercept': float(intercept)}
