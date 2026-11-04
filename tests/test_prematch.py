"""Phase 3.4: the evaluation is rolling-origin, handles ties, and applies the pre-registered rule."""
import numpy as np
import pandas as pd

import wpl.prematch as PM


def fake(n_per_season=40, signal=0.0, seed=1):
    """Synthetic feature table: 2023-2026, WPL. With signal > 0, y depends on xi_margin."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in (2023, 2024, 2025, 2026):
        for i in range(n_per_season):
            x = rng.normal(0, 20)
            y = float(rng.random() < 1 / (1 + np.exp(-signal * x)))
            rows.append({'match_id': f'{s}_{i}', 'date': pd.Timestamp(f'{s}-03-01') + pd.Timedelta(days=i),
                         'season': s, 'competition': PM.WPL, 'result_type': 'win','y': y, 'toss_bf': int(rng.random() < 0.5),
                         'xi_margin': x, 'xi_margin_hinf': x + rng.normal(0, 5), 'venue_bf_prior': rng.uniform(0.3, 0.6)})
    return pd.DataFrame(rows)


def test_expand_ties_matches_half_label():
    X = np.array([[1.0], [2.0], [3.0]])
    Xe, ye, w = PM.expand_ties(X, [1, 0.5, 0])
    assert Xe.shape == (4, 1) and list(ye) == [1, 0, 1, 0] and list(w) == [1, 1, 0.5, 0.5]
    assert list(Xe[2:, 0]) == [2.0, 2.0]


def test_predictions_never_see_test_or_later_seasons():
    f = fake()
    a = PM.rolling_predictions(f)
    g = f.copy()
    g.loc[g.season == 2025, 'y'] = 1 - g.loc[g.season == 2025, 'y']      # flip only the 2025 results
    b = PM.rolling_predictions(g)
    early = a.season <= 2025                  # 2024 and 2025 predictions must not see 2025 results; 2026 must
    cols = ['base_rate'] + list(PM.MODELS)
    np.testing.assert_allclose(a.loc[early, cols], b.loc[early, cols])
    assert not np.allclose(a.loc[~early, 'primary'], b.loc[~early, 'primary'])


def test_base_rate_is_training_share():
    f = fake()
    p = PM.rolling_predictions(f)
    for s in PM.TEST_SEASONS:
        assert np.isclose(p.loc[p.season == s, 'base_rate'].iloc[0], f.loc[f.season < s, 'y'].mean())
    assert set(p.season) == set(PM.TEST_SEASONS) and len(p) == 120


def test_strong_signal_beats_base_rate_and_deploys():
    p = PM.rolling_predictions(fake(n_per_season=100, signal=0.15))
    ll, br, extra = PM.metrics(p, ['base_rate'] + list(PM.MODELS))
    v = PM.verdict(ll)
    assert v['deploy_primary'] and v['ci_high'] < 0 and v['serve'] == 'primary'
    assert extra.set_index('model').loc['primary', 'accuracy'] > 0.7


def test_no_signal_keeps_base_rate():
    p = PM.rolling_predictions(fake(signal=0.0))
    ll, _, _ = PM.metrics(p, ['base_rate'] + list(PM.MODELS))
    v = PM.verdict(ll)
    assert not v['deploy_primary'] and v['serve'] == 'base_rate'


def test_missing_features_refused():
    f = fake()
    f.loc[0, 'xi_margin'] = np.nan
    try:
        PM.rolling_predictions(f)
    except ValueError:
        return
    raise AssertionError('NaN feature should be refused')
def test_no_results_are_dropped_not_imputed():
    f = fake()
    f.loc[f.index[-1], ['y', 'result_type']] = [np.nan, 'no_result']     # a 2026 washout
    p = PM.rolling_predictions(f)
    assert len(p) == 119 and f.match_id.iloc[-1] not in set(p.match_id)
