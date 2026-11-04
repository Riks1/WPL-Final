"""Phase 3.2 (D9): as-of ratings are leak-free, deterministic and behave as RATINGS_SPEC v1.1 says."""
import copy

import numpy as np
import pandas as pd
import pytest

from _factory import A, B, dl, inns, match, out, simple, to_zip
import wpl.data.entities as E
import wpl.data.parse as P
import wpl.ratings as RT


def tables(tmp_path, matches, name="snap.zip"):
    return E.apply_aliases(P.parse_snapshot(to_zip(tmp_path, matches, name), verbose=False))

def game(date, a_runs=4, b_runs=1):
    i1 = inns("India", [[dl("A1", "B1", "A2", bat=a_runs), dl("A1", "B1", "A2", bat=a_runs)]])
    i2 = inns("England", [[dl("B1", "A1", "B2", bat=b_runs)]], target={"runs": 2 * a_runs + 1, "overs": 20})
    return match([i1, i2], date=date)
def test_future_perturbation_invariance(tmp_path):
    """Changing every ball on or after a date must not change any as-of rating before that date's matches."""
    base = {"1": game("2024-01-01"), "2": game("2024-02-01"), "3": game("2024-03-01")}
    changed = copy.deepcopy(base)
    changed["2"] = game("2024-02-01", a_runs=6, b_runs=6)
    changed["3"] = game("2024-03-01", a_runs=0, b_runs=0)
    a1, _, _ = build(tables(tmp_path, base, "a.zip"))
    a2, _, _ = build(tables(tmp_path, changed, "b.zip"))
    key = ["match_id", "player_id"]
    left = a1[a1.match_id.isin(["1", "2"])].sort_values(key).reset_index(drop=True)
    right = a2[a2.match_id.isin(["1", "2"])].sort_values(key).reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)                       # match 2's ratings never see match 2
    assert not a1[a1.match_id == "3"].reset_index(drop=True).equals(a2[a2.match_id == "3"].reset_index(drop=True))
def test_same_day_matches_do_not_see_each_other(tmp_path):
    T = tables(tmp_path, {"1": game("2024-01-01"), "2": game("2024-01-01", a_runs=6)})
    asof, _, _ = build(T)
    assert (asof[[c + "_eff" for c in RT.COMPONENTS]].to_numpy() == 0).all()


def build(T, **params):
    return RT.build_ratings(RT.prepare_balls(T), RT.rosters_from(T), params)
def test_first_appearance_gets_the_prior(tmp_path):
    mu0 = {"bat_runs": -0.1, "bat_dis": 0.01, "bowl_runs": 0.05, "bowl_wkt": -0.002}
    k = {c: 50.0 for c in RT.COMPONENTS}
    sigma2 = {c: 2.0 for c in RT.COMPONENTS}
    asof, _, _ = build(tables(tmp_path, {"1": game("2024-01-01")}), mu0=mu0, k=k, sigma2=sigma2)
    for c in RT.COMPONENTS:
        assert np.allclose(asof[c], mu0[c]) and np.allclose(asof[c + "_sd"], np.sqrt(2.0 / 50.0))
def test_outcomes_credit_the_right_players(tmp_path):
    i1 = inns("India", [[dl("A1", "B1", "A2", wickets=[out("A1", "caught", "B3")]),
                         dl("A3", "B1", "A2", wickets=[out("A2", "run out", "B4")]),
                         dl("A3", "B1", "A4", extras={"wides": 1})]])
    i2 = inns("England", [[dl("B1", "A1", "B2", bat=1)]], target={"runs": 2, "overs": 20})
    b = RT.prepare_balls(tables(tmp_path, {"1": match([i1, i2])})).query("innings == 1")
    assert b.bat_dis.tolist() == [1, 0, 0]          # non-striker run out is not the striker's dismissal
    assert b.bowl_wkt.tolist() == [1, 0, 0]         # run out is not the bowler's wicket
    assert b.faced.tolist() == [True, True, False]  # a wide is not faced
    assert b.bowl_runs.tolist() == [0, 0, 1]

def test_strong_batter_moves_up_and_shrinks_with_less_data(tmp_path):
    T = tables(tmp_path, {"0": game("2023-12-01"), "1": game("2024-01-01", a_runs=6), "2": game("2024-02-01", a_runs=6),
                          "3": game("2024-03-01", a_runs=6)})
    asof, _, _ = build(T, k={c: 10.0 for c in RT.COMPONENTS})
    a1 = asof[asof.player_id == "id_A1"].set_index("match_id").bat_runs
    assert a1["1"] == 0 and 0 < a1["2"] < a1["3"]                  # more evidence, less shrinkage


def test_decay_halves_weight_every_half_life(tmp_path):
    T = tables(tmp_path, {"0": game("2019-12-01"), "1": game("2020-01-01"), "2": game("2022-01-01")})
    asof, _, _ = build(T, h=2.0)
    eff = asof[(asof.player_id == "id_A1") & (asof.match_id == "2")].bat_runs_eff.item()
    assert eff == pytest.approx(2 * 0.5)                           # 2 balls faced, two years ago, h = 2

def test_build_is_deterministic(tmp_path):
    T = tables(tmp_path, {"1": game("2024-01-01"), "2": game("2024-02-01", a_runs=6)})
    assert RT.content_hash(build(T)[0]) == RT.content_hash(build(T)[0])


def test_lambda_is_runs_per_team_dismissal(tmp_path):
    i1 = inns("India", [[dl(bat=4), dl(bat=6, wickets=[out("A1", "bowled")])]])
    i2 = inns("England", [[dl("B1", "A1", "B2", bat=2, wickets=[out("B1", "lbw")])]], target={"runs": 11, "overs": 20})
    T = tables(tmp_path, {"1": match([i1, i2], date="2023-01-01")})
    assert RT.lambda_runs_per_wicket(T) == pytest.approx(12 / 2)


def test_first_day_has_no_predictions_and_teaches_no_player(tmp_path):
    asof, preds, state = build(tables(tmp_path, {"1": game("2024-01-01"), "2": game("2024-02-01")}))
    assert preds[preds.match_id == "1"].pred_bat_runs.isna().all()
    assert preds[preds.match_id == "2"].pred_bat_runs.notna().all()
    assert (asof[asof.match_id == "2"].bat_runs_eff == 0).all()

