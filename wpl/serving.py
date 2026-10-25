"""Prediction entry points for the Flask services. Bundles are plain JSON written by step 8 of
the training notebook: no pickle, so loading cannot execute code and does not depend on the
exact library versions used in Colab."""

from __future__ import annotations

import json

import numpy as np

from wpl import linear, parscore
from wpl.live_features import state_from_history, terminal_prob
from wpl.prematch_features import TeamHistory


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
    feats = TeamHistory(bundle['history']).features(bat_first_team, chase_team, int(toss_winner == bat_first_team))
    if bundle['family'] == 'base_rate':
        p = float(bundle['p_base'])
    else:
        p = float(linear.predict(bundle['params'], [[feats[f] for f in bundle['features']]])[0])
    return {'bat_first_win_prob': p, 'features': feats}
