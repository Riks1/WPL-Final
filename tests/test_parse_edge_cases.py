"""Step 2.6: every parser rule in D-005 / D-013 / D-015 pinned by a tiny hand-made match."""
import math

import pytest

from _factory import A, B, dl, inns, match, out, simple, to_zip
import wpl.data.parse as P


def parse(tmp_path, matches, **kw):
    return P.parse_snapshot(to_zip(tmp_path, matches), verbose=False, **kw)


def test_extras_and_derived_columns(tmp_path):
    i1 = inns("India", [[dl(extras={"wides": 1}), dl(bat=4, extras={"noballs": 1}), dl(extras={"byes": 2}),
                         dl(extras={"legbyes": 1}), dl(bat=6), dl(bat=4, non_boundary=True), dl(bat=1)]])
    i2 = inns("England", [[dl("B1", "A1", "B2", bat=1)]], target={"runs": 21, "overs": 20})
    d = parse(tmp_path, {"1": match([i1, i2])})["deliveries"].query("innings == 1")
    assert list(d.legal) == [False, False, True, True, True, True, True]
    assert list(d.ball_faced) == [False, True, True, True, True, True, True]   # a no-ball is faced, a wide is not
    assert list(d.bowler_runs) == [1, 5, 0, 0, 6, 4, 1]                       # byes and leg byes not charged
    assert list(d.is_four) == [False, True, False, False, False, False, False]  # all-run four is not a boundary
    assert d.is_six.sum() == 1 and d.runs_total.sum() == 20

def test_dismissal_kinds(tmp_path):
    i1 = inns("India", [[dl(wickets=[out("A1", "caught", "B5")]),
                         dl("A3", ns="A2", wickets=[out("A2", "run out", "B4")]),
                         dl("A3", ns="A4", wickets=[out("A3", "retired hurt")]),
                         dl("A5", ns="A4", wickets=[out("A5", "retired out")])]])
    i2 = inns("England", [[dl("B1", "A1", "B2", bat=1)]], target={"runs": 1, "overs": 20})
    T = parse(tmp_path, {"1": match([i1, i2], outcome={"winner": "England", "by": {"wickets": 10}})})
    w = T["wickets"].set_index("kind")
    assert w.loc["caught", "bowler_credited"] and w.loc["caught", "team_dismissal"]
    assert not w.loc["run out", "bowler_credited"] and w.loc["run out", "team_dismissal"]
    assert not w.loc["retired hurt", "team_dismissal"]                        # D-005
    assert w.loc["retired out", "team_dismissal"] and not w.loc["retired out", "bowler_credited"]
    assert w.loc["caught", "fielder_ids"] == ["id_B5"]
    assert list(T["deliveries"].query("innings == 1").n_dismissals) == [1, 1, 0, 1]
    assert T["innings"].query("innings == 1").wickets.item() == 3


def test_penalties_and_target_fallback(tmp_path):
    i1 = inns("India", [[dl(bat=4), dl(bat=6)]], penalty_runs={"post": 5})
    i2 = inns("England", [[dl("B1", "A1", "B2", bat=2)]])                    # no target in the file
    inn = parse(tmp_path, {"1": match([i1, i2])})["innings"]
    assert inn.query("innings == 1").total.item() == 15
    assert math.isnan(inn.query("innings == 2").target_runs.item())
    assert inn.query("innings == 2").target.item() == 16

def test_reduced_target_sets_max_balls(tmp_path):
  i1 = inns("India", [[dl(bat=4)]])
  i2 = inns("England", [[dl("B1", "A1", "B2", bat=1)]], target={"runs": 50, "overs": 5.3})
  T = parse(tmp_path,{'1':match([i1,i2])})
  assert T["innings"].query("innings == 2").max_balls.item() == 33
  assert T["innings"].query("innings == 2").target.item() == 50
  assert T["matches"].reduced.item()

def test_super_over(tmp_path):
    i1 = inns("India", [[dl(bat=6)]])
    i2 = inns("England", [[dl("B1", "A1", "B2", bat=6)]], target={"runs": 7, "overs": 20})
    s1 = inns("England", [[dl("B1", "A1", "B2", bat=4)]], super_over=True)
    s2 = inns("India", [[dl(bat=6)]], super_over=True)
    T = parse(tmp_path, {"1": match([i1, i2, s1, s2], outcome={"result": "tie", "eliminator": "India"})})
    m = T["matches"].iloc[0]
    assert m.result_type == "tie_super_over" and m.y == 1.0                  # India batted first and won it
    assert T["deliveries"].super_over.sum() == 2
    assert T["innings"].query("super_over").max_balls.tolist() == [6, 6]


def test_tie_and_no_result_labels(tmp_path):
    tie = parse(tmp_path, {"1": simple(outcome={"result": "tie"})})["matches"].iloc[0]
    assert tie.result_type == "tie" and tie.y == 0.5                          # half a win each (D-001 update)
    nr = parse(tmp_path, {"2": simple(outcome={"result": "no result"})})["matches"].iloc[0]
    assert nr.result_type == "no_result" and math.isnan(nr.y)

@pytest.mark.parametrize("kw,expected", [
    (dict(teams=("India", "England")), ("T20I India", True)),
    (dict(teams=("India Women", "England Women")), ("T20I India", True)),            # name suffix stripped
    (dict(teams=("England", "Australia")), ("T20I other full members", False)),
    (dict(teams=("India", "Thailand")), ("T20I associate", False)),                  # D-011: associates out
    (dict(match_type="IT20", team_type=None), ("T20I India", True)),                 # IT20 alone marks a T20I
    (dict(team_type="club", event="Women's Premier League 2024"), ("Women's Premier League", True)),
    (dict(team_type="club", event="Women's Big Bash League 2024/25"), ("Women's Big Bash League", False)),
    (dict(bpo=5), (None, False)),                                                    # The Hundred
    (dict(overs=50), (None, False)),
    (dict(gender="male"), (None, False)),
])
def test_classify(kw, expected):
    kw = dict(kw)
    teams = kw.pop("teams", ("India", "England"))
    drop_team_type = kw.get("team_type", "x") is None
    info = simple(teams=teams, **kw)["info"]
    if drop_team_type:
        info.pop("team_type")
    assert P.classify(info) == expected
def test_exclusions_drop_the_match(tmp_path):
    T = parse(tmp_path, {"1": simple(), "2": simple(date="2024-01-02")}, exclusions={"2": {"reason": "test"}})
    assert T["matches"].match_id.tolist() == ["1"]
    assert set(T["deliveries"].match_id) == {"1"}


def test_ratings_scope_needs_a_wpl_player(tmp_path):
    wpl, wbbl = ("Mumbai Indians", "Delhi Capitals"), ("Perth Scorchers", "Hobart Hurricanes")
    xs, ys = [f"X{i}" for i in range(1, 12)], [f"Y{i}" for i in range(1, 12)]
    T = parse(tmp_path, {
        "w": simple(teams=wpl, team_type="club", event="Women's Premier League 2024"),
        "with": simple(teams=wbbl, team_type="club", event="Women's Big Bash League 2024/25",
                       players={wbbl[0]: A, wbbl[1]: xs}),
        "without": simple(teams=wbbl, team_type="club", event="Women's Big Bash League 2024/25",
                          players={wbbl[0]: xs, wbbl[1]: ys}),
    })
    s = T["matches"].set_index("match_id")
    assert s.loc["w", "model_scope"] and s.loc["w", "ratings_scope"]
    assert not s.loc["with", "model_scope"] and s.loc["with", "ratings_scope"]
    assert not s.loc["without", "ratings_scope"]


def test_empty_wickets_table_still_has_columns(tmp_path):
    T = parse(tmp_path, {"1": simple()})
    assert len(T["wickets"]) == 0 and "team_dismissal" in T["wickets"].columns
    assert len(T["replacements"]) == 0 and "in_id" in T["replacements"].columns
