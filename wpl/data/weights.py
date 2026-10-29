import numpy as np
import pandas as pd

from wpl.data.parse import WPL

HALF_LIFE = 2.0                                          # D-012, pre-registered


def relevance(T, S, n_seasons=3):
    """s_c for the fold with test season S (D-012, decisions 4a and 7a)."""
    m = T['matches'].loc[T['matches'].model_scope, ['match_id', 'competition', 'season']]
    pl = T['players'].merge(m, on='match_id')
    wpl_ids = set(pl.loc[(pl.competition == WPL) & (pl.season < S), 'player_id'].dropna())
    d = T['deliveries']
    d = d[d.legal & ~d.super_over].merge(m, on='match_id')
    d = d[d.season < S]
    out = {}
    for comp, g in d.groupby('competition'):
        last = sorted(g.season.unique())[-n_seasons:]            # last 3 seasons it was played before S
        g = g[g.season.isin(last)]
        out[comp] = float((g.batter_id.isin(wpl_ids) | g.bowler_id.isin(wpl_ids)).mean())
    out[WPL] = 1.0
    return pd.Series(out, name=f's_c (S={S})')


def season_age(dates, S):
    """Fractional years from each match date to 1 January of season S."""
    d = pd.to_datetime(pd.Series(dates))
    return S - (d.dt.year + (d.dt.dayofyear - 1) / 365.25)


def match_weights(T, S, half_life=HALF_LIFE, use_relevance=True):
    """Training weights for fold S: model-scope matches from seasons before S, w = s_c * 0.5**(age/h)."""
    m = T['matches']
    m = m.loc[m.model_scope & (m.season < S), ['match_id', 'competition', 'season', 'date']].copy()
    m['recency'] = 0.5 ** (season_age(m.date.values, S).values / half_life)
    m['s_c'] = m.competition.map(relevance(T, S)) if use_relevance else 1.0
    m['weight'] = m.s_c * m.recency
    return m


def effective_n(w):
    """(sum w)^2 / sum w^2: how many equally weighted matches the weights are worth."""
    w = np.asarray(w, float)
    return float(w.sum() ** 2 / (w ** 2).sum()) if len(w) else 0.0
