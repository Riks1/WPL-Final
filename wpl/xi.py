"""XI strength and venue bat-first prior (RATINGS_SPEC v1.1 §10–§11). Every feature is as-of the match date."""
import numpy as np
import pandas as pd

import wpl.data.entities as E

BALLS = 120
CAP = 24                                   # four overs
MIN_BOWLERS = 5
PRIOR_MATCHES = 20                         # venue bat-first prior strength


def toss_xi(T):
    """Team sheet minus players who only came on as replacements (concussion subs): the XI named at the toss."""
    pl = T['players'].copy()
    pl['sheet_order'] = pl.groupby(['match_id', 'team']).cumcount()
    rep = T['replacements']
    subs = set(zip(rep.match_id, rep.team, rep.in_id)) if len(rep) else set()
    xi = pl[[(m, t, p) not in subs for m, t, p in zip(pl.match_id, pl.team, pl.player_id)]].copy()
    xi['xi_size'] = xi.groupby(['match_id', 'team']).player_id.transform('size')
    return xi
def position_shares(T, before='2024-01-01'):
    """Average share of a team's balls faced by batting position 1..11, matches before `before` (§10.2)."""
    u = E.build_usage(T).merge(T['matches'][['match_id', 'date']], on='match_id')
    u = u[(u.date < pd.Timestamp(before)) & u.bat_pos.notna()]
    tot = u.groupby(['match_id', 'innings']).balls_faced.transform('sum')
    u = u[tot > 0].assign(share=lambda d: d.balls_faced / tot[tot > 0])
    s = u[u.bat_pos <= 11].groupby('bat_pos').share.mean()
    s = s.reindex(range(1, 12), fill_value=0.0)
    return (s / s.sum()).to_numpy()
def _asof_mean(per_match, rosters, value):
    """Mean of `value` over a player's matches dated strictly before each roster date (same-day excluded)."""
    daily = per_match.groupby(['player_id', 'date'])[value].agg(['sum', 'count']).reset_index().sort_values('date')
    daily[['cs', 'cn']] = daily.groupby('player_id')[['sum', 'count']].cumsum()
    r = rosters.sort_values('date')
    m = pd.merge_asof(r, daily[['player_id', 'date', 'cs', 'cn']], on='date', by='player_id',
                      direction='backward', allow_exact_matches=False)
    return m.set_index(['match_id', 'player_id'])['cs'].div(m.set_index(['match_id', 'player_id'])['cn'])

def usage_history(T, xi):
    """As-of mean batting position and mean legal balls bowled per match played, for every XI player."""
    m = T['matches'][['match_id', 'date']]
    u = E.build_usage(T)
    bat = u.groupby(['match_id', 'player_id']).bat_pos.min().reset_index().merge(m, on='match_id')
    bowl = u.groupby(['match_id', 'player_id']).legal_balls_bowled.sum()
    played = xi[['match_id', 'player_id']].drop_duplicates().merge(m, on='match_id')
    played['legal_balls_bowled'] = bowl.reindex(pd.MultiIndex.from_frame(played[['match_id', 'player_id']])).fillna(0).to_numpy()
    rost = xi[['match_id', 'player_id']].drop_duplicates().merge(m, on='match_id')
    out = pd.DataFrame({'mean_bat_pos': _asof_mean(bat.dropna(subset=['bat_pos']), rost, 'bat_pos'),
                        'mean_balls_bowled': _asof_mean(played, rost, 'legal_balls_bowled')})
    return out.reset_index()
def bowling_shares(balls_hist):
    """balls_hist: as-of mean legal balls bowled, in team-sheet order (NaN or 0 = no bowling history) -> shares (§10.3)."""
    b = np.nan_to_num(np.asarray(balls_hist, float))
    b = np.minimum(b, CAP)
    has = b > 0
    if has.sum() < MIN_BOWLERS:
        extra = [i for i in range(len(b)) if not has[i]][:MIN_BOWLERS - has.sum()]
        if extra:
            b[extra] = min(CAP, max(BALLS - b.sum(), 0) / len(extra))
    if b.sum() == 0:
        return b
    s = b / b.sum()
    for _ in range(20):                               # cap at 24/120 and hand the excess to the others
        over = s > CAP / BALLS + 1e-12
        if not over.any():
            break
        excess = (s[over] - CAP / BALLS).sum()
        s[over] = CAP / BALLS
        free = (~over) & (s > 0)
        if not free.any():
            break
        s[free] += excess * s[free] / s[free].sum()
    return s
def xi_strength(T, asof, lam, shares_by_pos, data_min=60):
    """One row per (match, team): batting and bowling value in runs, uncertainty and coverage (§10)."""
    xi = toss_xi(T)
    hist = usage_history(T, xi)
    d = (xi.merge(hist, on=['match_id', 'player_id'], how='left')
           .merge(asof.drop(columns=['date']), on=['match_id', 'player_id'], how='left'))
    rows = []
    for (mid, team), g in d.groupby(['match_id', 'team'], sort=False):
        g = g.sort_values('sheet_order')
        order = g.mean_bat_pos.fillna(np.inf).to_numpy()          # no batting history -> last
        rank = np.empty(len(g), int)
        rank[np.lexsort((g.sheet_order.to_numpy(), order))] = np.arange(len(g))   # ties keep team-sheet order
        bat_share = np.array([shares_by_pos[r] if r < 11 else 0.0 for r in rank])
        bowl_share = bowling_shares(g.mean_balls_bowled.to_numpy())
        bat_val = BALLS * np.sum(bat_share * (g.bat_runs - lam * g.bat_dis))
        bowl_val = BALLS * np.sum(bowl_share * (lam * g.bowl_wkt - g.bowl_runs))
        var = (np.sum(bat_share ** 2 * (g.bat_runs_sd ** 2 + lam ** 2 * g.bat_dis_sd ** 2))
               + np.sum(bowl_share ** 2 * (g.bowl_runs_sd ** 2 + lam ** 2 * g.bowl_wkt_sd ** 2)))
        supported = (g.legal_faced >= data_min) | (g.legal_bowled >= data_min)
        rows.append({'match_id': mid, 'team': team, 'bat_value': float(bat_val), 'bowl_value': float(bowl_val),
                     'strength': float(bat_val + bowl_val), 'strength_sd': float(BALLS * np.sqrt(var)),
                     'coverage': float(supported.mean()), 'n_debut': int(((g.legal_faced == 0) & (g.legal_bowled == 0)).sum()),
                     'xi_size': int(g.xi_size.iloc[0])})
    return pd.DataFrame(rows)



def venue_bf_prior(T, prior=PRIOR_MATCHES):
    """As-of share of model-scope matches at the venue won by the team batting first, shrunk to the as-of pooled rate (§11)."""
    m = T['matches'].sort_values(['date', 'match_id'])
    m = m[m.model_scope]
    out, ven, pool_w, pool_n = {}, {}, 0.0, 0
    for day, g in m.groupby('date', sort=True):
        pooled = pool_w / pool_n if pool_n else 0.5
        for r in g.itertuples():
            w, n = ven.get(r.venue_id, (0.0, 0))
            out[r.match_id] = (w + prior * pooled) / (n + prior)
        for r in g.itertuples():                     # update after the whole day: same-day matches don't see each other
            if pd.notna(r.y):
                w, n = ven.get(r.venue_id, (0.0, 0))
                ven[r.venue_id] = (w + r.y, n + 1)
                pool_w, pool_n = pool_w + r.y, pool_n + 1
    return pd.Series(out, name='venue_bf_prior')


def match_features(T, strength, strength_hinf=None):
    """One row per model-scope match: the pre-registered features plus the label."""
    m = T['matches'][T['matches'].model_scope].copy()
    s = strength.set_index(['match_id', 'team'])

    def side(col, team_col, frame=s):
        return frame[col].reindex(pd.MultiIndex.from_frame(m[['match_id', team_col]])).to_numpy()

    m['toss_bf'] = (m.toss_winner == m.bat_first_team).astype(int)
    for col in ('strength', 'strength_sd', 'coverage', 'n_debut', 'xi_size'):
        m[col + '_bf'], m[col + '_ch'] = side(col, 'bat_first_team'), side(col, 'chase_team')
    m['xi_margin'] = m.strength_bf - m.strength_ch
    if strength_hinf is not None:
        sh = strength_hinf.set_index(['match_id', 'team'])
        m['xi_margin_hinf'] = side('strength', 'bat_first_team', sh) - side('strength', 'chase_team', sh)
    m['venue_bf_prior'] = m.match_id.map(venue_bf_prior(T))
    keep = ['match_id', 'date', 'season', 'competition', 'venue_id', 'bat_first_team', 'chase_team', 'result_type', 'y',
            'toss_bf', 'xi_margin'] + (['xi_margin_hinf'] if strength_hinf is not None else []) + \
           ['venue_bf_prior'] + [c for c in m.columns if c.endswith(('_bf', '_ch')) and c not in ('toss_bf',)]
    return m[list(dict.fromkeys(keep))].reset_index(drop=True)
