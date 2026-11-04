"""Prediction entry points for the Flask services. Bundles are plain JSON written by step 8 of
the training notebook: no pickle, so loading cannot execute code and does not depend on the
exact library versions used in Colab."""

from __future__ import annotations

import json

import numpy as np

from wpl import linear, parscore
from wpl.live_features import state_from_history, terminal_prob
from wpl.prematch_features import TeamHistory
from wpl.strength import team_strength


def load_bundle(path) -> dict:
    with open(path) as f:
        return json.load(f)


def predict_live(bundle: dict, innings: int, deliveries: list[dict], max_balls: int = 120, target=None) -> dict:
    row = state_from_history(innings, deliveries, max_balls, target)
    if bundle['family'] == 'parscore':
        p = float(parscore.predict(bundle['params'], row)[0])
        extra = {'expected_runs_to_come': float(parscore.expected_runs(bundle['params'], row['balls_remaining'],
                                                                         row['cum_wickets'])[0])}
    elif bundle['family'] == 'logistic':
        prm = bundle['params'][str(int(innings))]
        p_model = float(linear.predict(prm, row[prm['features']])[0])
        term = terminal_prob(row).values[0]
        p = p_model if np.isnan(term) else float(term)
        extra = {}
    else:
        raise ValueError(f"unsupported live family {bundle['family']!r}")
    s = row.iloc[0]
    state = {k: float(s[k]) for k in ('cum_runs', 'cum_wickets', 'legal_balls', 'balls_remaining', 'current_rr',
                                      'runs_last_30', 'wkts_last_30', 'partnership_runs', 'partnership_balls')}
    if innings == 2:
        state.update({k: float(s[k]) for k in ('target', 'runs_needed', 'required_rr')})
    return {'bat_first_win_prob': p, 'state': {**state, **extra}}


def predict_prematch(bundle: dict, bat_first_team: str, chase_team: str, toss_winner: str) -> dict:
    if 'history' not in bundle:                      # Stage 3 registry entry (v3): the base rate, no team features
        return {'bat_first_win_prob': float(bundle['p_base']), 'features': {}}
    feats = TeamHistory(bundle['history']).features(bat_first_team, chase_team, int(toss_winner == bat_first_team))
    if bundle['family'] == 'base_rate':
        p = float(bundle['p_base'])
    else:
        p = float(linear.predict(bundle['params'], [[feats[f] for f in bundle['features']]])[0])
    return {'bat_first_win_prob': p, 'features': feats}


def lookup_players(ratings: dict, ids: list[str], allow_unknown: bool = False) -> tuple[dict, list[str]]:
    """Columns for team_strength, in the given (team-sheet) order. Unknown ids get the debutant prior only if
    allowed; otherwise they are returned so the caller can refuse the request."""
    fields, players, deb = ratings['fields'], ratings['players'], ratings['debutant']
    unknown = [i for i in ids if i not in players]
    if unknown and not allow_unknown:
        return {}, unknown
    cols = {f: [] for f in fields[1:]}
    for i in ids:
        if i in players:
            for f, v in zip(fields[1:], players[i][1:]):
                cols[f].append(np.nan if v is None else v)
        else:                                            # debutant: prior ratings, no exposure, no usage
            for f in fields[1:]:
                cols[f].append(deb.get(f, 0.0 if f.startswith('legal') else np.nan))
    cols['sheet_order'] = list(range(len(ids)))
    return cols, unknown


def predict_xi_strength(ratings: dict, bat_first_xi: list[str], chase_xi: list[str], allow_unknown: bool = False) -> dict:
    """XI strength of both teams and the margin, with the same function the training pipeline uses (wpl.strength)."""
    out, unknown = {}, []
    for side, ids in (('bat_first', bat_first_xi), ('chase', chase_xi)):
        cols, unk = lookup_players(ratings, ids, allow_unknown)
        unknown += unk
        if cols:
            out[side] = team_strength(cols, ratings['lambda'], ratings['shares_by_pos'], ratings['data_min'])
    if len(out) < 2:
        raise KeyError(unknown)
    return {**out, 'xi_margin': out['bat_first']['strength'] - out['chase']['strength'],
            'xi_margin_sd': float(np.hypot(out['bat_first']['strength_sd'], out['chase']['strength_sd'])),
            'unknown_players': unknown}
