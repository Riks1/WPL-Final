"""Team strength from player ratings (RATINGS_SPEC v1.1 §10). numpy only, so the training pipeline (wpl.xi)
and the API (wpl.serving) compute XI strength with the same function and cannot drift apart."""
import numpy as np

BALLS = 120
CAP = 24                                   # four overs
MIN_BOWLERS = 5
RATING_COLS = ('bat_runs', 'bat_dis', 'bowl_runs', 'bowl_wkt')


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


def batting_shares(mean_bat_pos, sheet_order, shares_by_pos):
    """Rank the XI by as-of mean batting position (no history -> last, ties keep team-sheet order) and give each
    rank its pre-2024 share of balls faced (§10.2)."""
    order = np.where(np.isnan(np.asarray(mean_bat_pos, float)), np.inf, mean_bat_pos)
    rank = np.empty(len(order), int)
    rank[np.lexsort((np.asarray(sheet_order), order))] = np.arange(len(order))
    return np.array([shares_by_pos[r] if r < 11 else 0.0 for r in rank])


def team_strength(p, lam, shares_by_pos, data_min=60):
    """p: dict of equal-length arrays in team-sheet order with keys sheet_order, mean_bat_pos, mean_balls_bowled,
    the four ratings, their '_sd', legal_faced and legal_bowled. Returns the §10 team values in runs."""
    a = {k: np.asarray(v, float) for k, v in p.items()}
    bat_share = batting_shares(a['mean_bat_pos'], a['sheet_order'], shares_by_pos)
    bowl_share = bowling_shares(a['mean_balls_bowled'])
    bat_val = BALLS * np.nansum(bat_share * (a['bat_runs'] - lam * a['bat_dis']))
    bowl_val = BALLS * np.nansum(bowl_share * (lam * a['bowl_wkt'] - a['bowl_runs']))
    var = (np.nansum(bat_share ** 2 * (a['bat_runs_sd'] ** 2 + lam ** 2 * a['bat_dis_sd'] ** 2))
           + np.nansum(bowl_share ** 2 * (a['bowl_runs_sd'] ** 2 + lam ** 2 * a['bowl_wkt_sd'] ** 2)))
    supported = (a['legal_faced'] >= data_min) | (a['legal_bowled'] >= data_min)
    return {'bat_value': float(bat_val), 'bowl_value': float(bowl_val), 'strength': float(bat_val + bowl_val),
            'strength_sd': float(BALLS * np.sqrt(var)), 'coverage': float(supported.mean()),
            'n_debut': int(((a['legal_faced'] == 0) & (a['legal_bowled'] == 0)).sum())}
