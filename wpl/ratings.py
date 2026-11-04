import hashlib

import numpy as np
import pandas as pd

COMPONENTS = ('bat_runs', 'bat_dis', 'bowl_runs', 'bowl_wkt')
ACTOR = {'bat_runs': 'batter', 'bat_dis': 'batter', 'bowl_runs': 'bowler', 'bowl_wkt': 'bowler'}
OPPONENT = {'bat_runs': 'bowl_runs', 'bat_dis': 'bowl_wkt', 'bowl_runs': 'bat_runs', 'bowl_wkt': 'bat_dis'}
RUN_COMPONENTS = ('bat_runs', 'bowl_runs')            # the venue effect applies to these
T0 = 2000.0                                          # time origin: keeps 2^(t/h) small (t in years since 2000)
DEFAULTS = dict(h=2.0, k_cell=500.0, k_venue=1000.0, k_pool=2000.0,
                k={c: 100.0 for c in COMPONENTS}, mu0={c: 0.0 for c in COMPONENTS}, sigma2=None)


def frac_year(dates):
    d = pd.to_datetime(pd.Series(list(dates)))
    return (d.dt.year + (d.dt.dayofyear - 1) / 365.25).to_numpy()
def prepare_balls(T, scope='all'):
    """One row per main-innings delivery with the four outcomes and context keys (RATINGS_SPEC §1–§3).
    scope='all' uses every parsed match; 'ratings' keeps ratings_scope matches only."""
    m = T['matches']
    keep = m if scope == 'all' else m[m.ratings_scope]
    d = T['deliveries']
    d = d[~d.super_over & d.match_id.isin(keep.match_id)]
    d = d.merge(m[['match_id', 'date', 'competition', 'venue_id']], on='match_id')
    key = ['match_id', 'innings', 'seq']
    w = T['wickets']
    striker_out = (w[w.team_dismissal.astype(bool)].merge(d[key + ['batter_id']], on=key)
                   .query('player_out_id == batter_id')[key].drop_duplicates().assign(bat_dis=1.0))
    credited = w[w.bowler_credited.astype(bool)][key].drop_duplicates().assign(bowl_wkt=1.0)
    d = d.merge(striker_out, on=key, how='left').merge(credited, on=key, how='left')
    d = d.sort_values(['date', 'match_id', 'innings', 'seq']).reset_index(drop=True)
    wk_before = d.groupby(['match_id', 'innings']).n_dismissals.cumsum() - d.n_dismissals
    return pd.DataFrame({
        'match_id': d.match_id, 'date': d.date, 'innings': d.innings, 'seq': d.seq,
        'batter': d.batter_id, 'bowler': d.bowler_id, 'competition': d.competition, 'venue': d.venue_id,
        'phase': np.select([d.over <= 5, d.over <= 14], [0, 1], 2),
        'wk': np.select([wk_before <= 2, wk_before <= 5], [0, 1], 2),
        'faced': d.ball_faced.astype(bool), 'legal': d.legal.astype(bool),
        'bat_runs': d.runs_batter.astype(float), 'bat_dis': d.bat_dis.fillna(0.0),
        'bowl_runs': d.bowler_runs.astype(float), 'bowl_wkt': d.bowl_wkt.fillna(0.0)})
def rosters_from(T,match_ids = None):
  pl = T['players'].merge(T['matches'][['match_id','date']],on = 'match_id')
  if match_ids is not None:
    pl = pl[pl.match_id.isin(set(match_ids))]
  return pl[['match_id','date','player_id']].drop_duplicates().dropna().reset_index(drop = True)
def lambda_runs_per_wicket(T, before='2024-01-01'):
  ids = T['matches'].loc[T['matches'].date < pd.Timestamp(before),'match_id']
  inn = T['innings']
  inn = inn[-inn.super_over & inn.match_id.isin(ids)]
  return float(inn.runs.sum() / inn.wickets.sum())
def build_ratings(balls, rosters, params=None):
  p = {**DEFAULTS, **(params or {})}
  rate = 0.0 if not np.isfinite(p['h']) else 1.0 / p['h']
  b = balls.reset_index(drop=True)
  rost = rosters.reset_index(drop=True)
  players = pd.Index(sorted(set(pd.concat([b.batter, b.bowler, rost.player_id]).dropna())))
  cell_keys = ['competition', 'phase', 'wk', 'innings']
  cells = pd.MultiIndex.from_frame(b[cell_keys].drop_duplicates().sort_values(cell_keys))
  pools = pd.MultiIndex.from_frame(b[cell_keys[1:]].drop_duplicates().sort_values(cell_keys[1:]))
  venues = pd.Index(sorted(b.venue.dropna().unique()))
  who = {'batter': players.get_indexer(b.batter),'bowler': players.get_indexer(b.bowler)}
  ci = cells.get_indexer(pd.MultiIndex.from_frame(b[cell_keys]))
  pi = pools.get_indexer(pd.MultiIndex.from_frame(b[cell_keys[1:]]))
  vi = venues.get_indexer(b.venue)
  y_all = {c: b[c].to_numpy(float) for c in COMPONENTS}
  rows = {c: (b.faced.to_numpy() if ACTOR[c] == 'batter' else np.ones(len(b), bool)) for c in COMPONENTS}
  legal = b.legal.to_numpy()
  sigma2 = p['sigma2'] or {c: 1.0 for c in COMPONENTS}

  nP = len(players)
  S = {c: {'w': np.zeros(nP), 'wr': np.zeros(nP)} for c in COMPONENTS}     # player sums, scaled by 2^(t/h)
  C = {c: {'w': np.zeros(len(cells)), 'wy': np.zeros(len(cells))} for c in COMPONENTS}
  Q = {c: {'w': np.zeros(len(pools)), 'wy': np.zeros(len(pools))} for c in COMPONENTS}
  G = {c: [0.0, 0.0] for c in COMPONENTS}
  V = {'w': np.zeros(len(venues)), 'wr': np.zeros(len(venues))}
  n_legal = {'batter': np.zeros(nP), 'bowler': np.zeros(nP)}

  def ratings(f):          # posterior mean with prior mu0 and prior strength k (RATINGS_SPEC §6)
        return {c: (S[c]['wr'] * f + p['k'][c] * p['mu0'][c]) / (S[c]['w'] * f + p['k'][c]) for c in COMPONENTS}

  pred = {c: np.full(len(b), np.nan) for c in COMPONENTS}
  # Convert keys to pandas Timestamps to ensure dictionary keys align perfectly
  ball_days = {pd.Timestamp(k): v for k, v in b.groupby('date').indices.items()}
  rost_days = {pd.Timestamp(k): v for k, v in rost.groupby(pd.to_datetime(rost.date)).indices.items()}
  out = []
  for day in sorted(set(ball_days.keys()) | set(rost_days.keys())):
    t = frac_year([day])[0] - T0
    f, wv = 2.0 ** (-rate * t), 2.0 ** (rate * t)
    R = ratings(f)
    if day in rost_days:
      g = rost.iloc[rost_days[day]]
      ix = players.get_indexer(g.player_id)
      rec = {'match_id': g.match_id.to_numpy(), 'player_id': g.player_id.to_numpy(), 'date': day}
      for c in COMPONENTS:
        eff = S[c]['w'][ix]*f
        rec[c], rec[c + '_sd'], rec[c + '_eff'] = R[c][ix], np.sqrt(sigma2[c] / (eff + p['k'][c])), eff
      rec['legal_faced'], rec['legal_bowled'] = n_legal['batter'][ix], n_legal['bowler'][ix]
      out.append(pd.DataFrame(rec))
    if day in ball_days:
      j = ball_days[day]                                                      # (2) predict
      venue_eff = V['wr'] * f / (V['w'] * f + p['k_venue'])
      for c in COMPONENTS:
        if G[c][0] == 0:
          continue
        g_mean = G[c][1]/G[c][0]
        pool = (Q[c]['wy'][pi[j]]*f + p['k_pool']*g_mean)/(Q[c]['w'][pi[j]] * f + p['k_pool'])
        cell = (C[c]['wy'][ci[j]] * f + p['k_cell'] * pool) / (C[c]['w'][ci[j]] * f + p['k_cell'])
        venue = venue_eff[vi[j]] if c in RUN_COMPONENTS else 0.0
        opp_role = 'bowler' if ACTOR[c] == 'batter' else 'batter'
        pred[c][j] = cell + venue + R[OPPONENT[c]][who[opp_role][j]]
      for c in COMPONENTS:
          m_ = rows[c][j]
          jj = j[m_]
          y = y_all[c][jj]
          np.add.at(C[c]['w'], ci[jj], wv); np.add.at(C[c]['wy'], ci[jj], wv * y)
          np.add.at(Q[c]['w'], pi[jj], wv); np.add.at(Q[c]['wy'], pi[jj], wv * y)
          G[c][0] += wv * len(jj); G[c][1] += wv * y.sum()
          ok = ~np.isnan(pred[c][jj])               # players learn only from balls that had a prediction
          a = who[ACTOR[c]][jj][ok]
          np.add.at(S[c]['w'], a, wv); np.add.at(S[c]['wr'], a, wv * (y[ok] - pred[c][jj][ok]))
      jr = j[rows['bat_runs'][j] & ~np.isnan(pred['bat_runs'][j])]            # venue: batting-run residual
      np.add.at(V['w'], vi[jr], wv)                                           # before the venue term
      np.add.at(V['wr'], vi[jr], wv * (y_all['bat_runs'][jr] - pred['bat_runs'][jr] + venue_eff[vi[jr]]))
      np.add.at(n_legal['batter'], who['batter'][j][legal[j]], 1)
      np.add.at(n_legal['bowler'], who['bowler'][j][legal[j]], 1)
  asof = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
  preds = b[['match_id', 'date', 'innings', 'seq', 'batter', 'bowler', 'faced'] + list(COMPONENTS)].copy()
  for c in COMPONENTS:
      preds['pred_' + c] = pred[c]
  f_end = 2.0 ** (-rate * (frac_year([b.date.max() + pd.Timedelta(days=1)])[0] - T0))
  R = ratings(f_end)
  state = pd.DataFrame({'player_id': players, **{c: R[c] for c in COMPONENTS},
                        **{c + '_eff': S[c]['w'] * f_end for c in COMPONENTS},
                        'legal_faced': n_legal['batter'], 'legal_bowled': n_legal['bowler']})
  return asof, preds, state


def estimate_priors(preds, before='2024-01-01', first_n=60, min_n=30):
    """From a first pass (mu0 = 0): debutant prior mu0 = mean residual over players' first `first_n` rows;
    k = sigma2 / tau2 by method of moments; sigma2 = pooled residual variance (RATINGS_SPEC §6, §9)."""
    d = preds[preds.date < pd.Timestamp(before)]
    mu0, k, sigma2 = {}, {}, {}
    for c in COMPONENTS:
        actor = ACTOR[c]
        sub = d[d.faced] if actor == 'batter' else d
        r = (sub[c] - sub['pred_' + c]).rename('r')
        g = pd.DataFrame({'player': sub[actor].values, 'r': r.values})
        sigma2[c] = float(g.r.var())
        first = g.groupby('player').head(first_n)
        mu0[c] = float(first.r.mean())
        stats = g.groupby('player').r.agg(['mean', 'size'])
        stats = stats[stats['size'] >= min_n]
        tau2 = stats['mean'].var() - (sigma2[c] / stats['size']).mean()
        k[c] = float(sigma2[c] / max(tau2, sigma2[c] / 1e5))
    return {'mu0': mu0, 'k': k, 'sigma2': sigma2}


def fit_ratings(balls, rosters, h, before='2024-01-01'):
    """The two-pass procedure (RATINGS_SPEC §9): pass 1 on pre-`before` balls with mu0 = 0 and k = 100 gives
    mu0, k, sigma2; those are then fixed and returned with h."""
    pre = balls[balls.date < pd.Timestamp(before)]
    _, preds1, _ = build_ratings(pre, rosters[rosters.date < pd.Timestamp(before)], {'h': h})
    return {'h': h, **estimate_priors(preds1, before)}


def tune_h(balls, rosters, grid=(1.0, 2.0, 4.0, float('inf')), before='2024-01-01', eval_from='2022-01-01'):
    """Choose h by one-step-ahead MSE of batting runs per ball faced on [eval_from, before) (RATINGS_SPEC §9)."""
    pre = balls[balls.date < pd.Timestamp(before)]
    r_pre = rosters[rosters.date < pd.Timestamp(before)]
    rows = []
    for h in grid:
        params = fit_ratings(balls, rosters, h, before)
        _, preds, _ = build_ratings(pre, r_pre, params)
        e = preds[(preds.date >= pd.Timestamp(eval_from)) & preds.faced]
        rows.append({'h': h, 'mse_bat_runs': float(((e.bat_runs - e.pred_bat_runs) ** 2).mean()), 'n': len(e),
                     'params': params})
    table = pd.DataFrame(rows)
    return table, table.loc[table.mse_bat_runs.idxmin(), 'params']


def content_hash(df):
    """SHA-256 over sorted rows, rounded to 12 significant digits: the ratings version (RATINGS_SPEC §12)."""
    cols = sorted(df.columns)
    keys = [c for c in ('date', 'match_id', 'player_id') if c in cols]
    s = df[cols].sort_values(keys).to_csv(index=False, float_format='%.12g')
    return hashlib.sha256(s.encode()).hexdigest()
