"""Phase 3.3: XI strength and venue prior are as-of, and their arithmetic matches RATINGS_SPEC §10–§11."""
import numpy as np
import pandas as pd
import pytest

from _factory import A, B, dl, inns, match, out, simple, to_zip
import wpl.data.entities as E
import wpl.data.parse as P
import wpl.ratings as RT
import wpl.xi as XI


def tables(tmp_path, matches, name="snap.zip"):
    return E.apply_aliases(P.parse_snapshot(to_zip(tmp_path, matches, name), verbose=False))


def test_toss_xi_drops_concussion_substitutes(tmp_path):
    sub = {"in": "A12", "out": "A3", "team": "India", "reason": "concussion_substitute"}
    i1 = inns("India", [[dl(bat=4, repl=[sub]), dl(bat=6)]])
    i2 = inns("England", [[dl("B1", "A1", "B2", bat=1)]], target={"runs": 11, "overs": 20})
    T = tables(tmp_path, {"1": match([i1, i2], players={"India": A + ["A12"], "England": B})})
    xi = XI.toss_xi(T)
    india = xi[xi.team == "India"]
    assert "id_A12" not in set(india.player_id) and len(india) == 11 and (india.xi_size == 11).all()


@pytest.mark.parametrize("hist,expected", [
    ([24, 24, 24, 24, 24, 0, 0, 0, 0, 0, 0], [0.2] * 5 + [0] * 6),          # five full spells
    ([40, 0, 0, 0, 0, 0], [0.2] * 5 + [0]),                                    # capped at 4 overs, filled to 5 bowlers
    ([12, 12, 12, 12, 12, 12, 0], [1 / 6] * 6 + [0]),                          # six equal bowlers
    ([0] * 11, [0.2] * 5 + [0] * 6),                                           # nobody has history: first five on the sheet
])
def test_bowling_shares(hist, expected):
    s = XI.bowling_shares(hist)
    assert s.sum() == pytest.approx(1) and s.max() <= 0.2 + 1e-12
    assert s.tolist() == pytest.approx(expected)


def test_strength_arithmetic_with_known_ratings(tmp_path):
    T = tables(tmp_path, {"1": simple()})
    xi = XI.toss_xi(T)
    asof = xi[["match_id", "player_id"]].assign(
        date=pd.Timestamp("2024-01-01"), bat_runs=0.1, bat_dis=0.01, bowl_runs=-0.05, bowl_wkt=0.002,
        bat_runs_sd=0.0, bat_dis_sd=0.0, bowl_runs_sd=0.0, bowl_wkt_sd=0.0, legal_faced=0.0, legal_bowled=0.0)
    shares = np.full(11, 1 / 11)
    st = XI.xi_strength(T, asof, lam=20.0, shares_by_pos=shares).set_index("team")
    # batting: 120 * sum(1/11 * (0.1 - 20*0.01)) = 120 * (-0.1) = -12
    assert st.loc["India", "bat_value"] == pytest.approx(-12.0)
    # bowling (no history -> first five, 0.2 each): 120 * 5 * 0.2 * (20*0.002 + 0.05) = 120 * 0.09 = 10.8
    assert st.loc["India", "bowl_value"] == pytest.approx(10.8)
    assert st.loc["India", "coverage"] == 0 and st.loc["India", "n_debut"] == 11


def test_usage_history_is_as_of(tmp_path):
    def g(date, opener):
        order = [opener] + [p for p in A if p != opener]
        i1 = inns("India", [[dl(order[0], "B1", order[1], bat=1)]])
        i2 = inns("England", [[dl("B1", "A1", "B2", bat=0)]], target={"runs": 2, "overs": 20})
        return match([i1, i2], date=date, players={"India": order, "England": B})
    T = tables(tmp_path, {"1": g("2024-01-01", "A5"), "2": g("2024-02-01", "A5"), "3": g("2024-02-01", "A1")})
    h = XI.usage_history(T, XI.toss_xi(T)).set_index(["match_id", "player_id"])
    assert np.isnan(h.loc[("1", "id_A5"), "mean_bat_pos"])            # nothing before match 1
    assert h.loc[("2", "id_A5"), "mean_bat_pos"] == 1                  # opened in match 1
    assert h.loc[("3", "id_A1"), "mean_bat_pos"] == 2                  # match 2 is the same day, so not seen


def test_venue_prior_is_as_of_and_shrunk(tmp_path):
    T = tables(tmp_path, {"1": simple(date="2024-01-01"), "2": simple(date="2024-02-01"),
                          "3": simple(date="2024-02-01")})
    v = XI.venue_bf_prior(T)
    assert v["1"] == pytest.approx(0.5)                                 # no history: neutral
    # after one bat-first win (y=1): pooled rate = 1, venue (1 + 20*1)/(1 + 20) = 1
    assert v["2"] == pytest.approx(1.0) and v["3"] == pytest.approx(1.0)   # same day: 2 and 3 don't see each other


def test_match_features_ignore_later_results(tmp_path):
    base = {"1": simple(date="2024-01-01"), "2": simple(date="2024-02-01"), "3": simple(date="2024-03-01")}
    flip = dict(base)
    flip["3"] = simple(date="2024-03-01", outcome={"winner": "England", "by": {"wickets": 5}})
    feats = []
    for name, ms in (("a.zip", base), ("b.zip", flip)):
        T = tables(tmp_path, ms, name)
        asof, _, _ = RT.build_ratings(RT.prepare_balls(T), RT.rosters_from(T), {"h": 4.0})
        st = XI.xi_strength(T, asof, 19.0, np.full(11, 1 / 11))
        feats.append(XI.match_features(T, st).set_index("match_id"))
    cols = ["xi_margin", "venue_bf_prior", "toss_bf"]
    pd.testing.assert_frame_equal(feats[0].loc[["1", "2", "3"], cols], feats[1].loc[["1", "2", "3"], cols])
