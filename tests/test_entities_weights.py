"""Step 2.6 (D2): entities, validation, D-012 weights (incl. the per-fold leakage rule), snapshot guard."""
import pandas as pd
import pytest

from _factory import A, B, dl, inns, match, out, simple, to_zip
import wpl.data.entities as E
import wpl.data.parse as P
import wpl.data.snapshots as S
import wpl.data.validate as V
import wpl.data.weights as W


def parse(tmp_path, matches):
    return E.apply_aliases(P.parse_snapshot(to_zip(tmp_path, matches), verbose=False))


def wpl(team_a, team_b, a_players, b_players, date):
    return simple(teams=(team_a, team_b), team_type="club", event=f"Women's Premier League {date[:4]}",
                  date=date, players={team_a: a_players, team_b: b_players})


# ---------------- venues ----------------
@pytest.mark.parametrize("venue,city,key", [
    ("M.Chinnaswamy Stadium", None, "mchinnaswamystadium"),
    ("M Chinnaswamy Stadium, Bengaluru", "Bengaluru", "mchinnaswamystadium"),
    ("Feroz Shah Kotla", "Delhi", "arunjaitleystadium"),
    ("County Ground, Hove", None, "countygroundhove"),
    ("County Ground", "Bristol", "countygroundbristol"),
    ("University Oval", "Dunedin", "universityovaldunedin"),
    ("Sylhet International Cricket Stadium, Academy Ground", "Sylhet", "sylhetacademyground"),
    ("Beausejour Stadium, Gros Islet", None, "darensammynationalcricketstadium"),
])
def test_venue_key(venue, city, key):
    assert E.venue_key(venue, city) == key


def test_competition_alias():
    T = {"matches": pd.DataFrame({"competition": ["Women's T20 Challenge Match"], "venue": ["X"], "city": [None]})}
    assert E.apply_aliases(T)["matches"].competition.item() == "Women's T20 Challenge"


# ---------------- people, usage, switches ----------------
def test_batting_position_and_usage(tmp_path):
    i1 = inns("India", [[dl("A1", "B1", "A2", bat=1), dl("A2", "B1", "A1", wickets=[out("A2", "caught", "B3")]),
                         dl("A3", "B1", "A1", bat=4), dl("A3", "B1", "A1", wickets=[out("A1", "run out", "B2")]),
                         dl("A4", "B1", "A3", bat=2)]])
    i2 = inns("England", [[dl("B1", "A1", "B2", bat=1)]], target={"runs": 8, "overs": 20})
    T = parse(tmp_path, {"1": match([i1, i2])})
    people, missing = E.build_people(T)
    u = E.build_usage(T).query("innings == 1").set_index("player_id")
    assert u.loc[["id_A1", "id_A2", "id_A3", "id_A4"], "bat_pos"].tolist() == [1, 2, 3, 4]
    assert u.loc["id_A1", "dismissed"] == 1 and u.loc["id_A1", "balls_faced"] == 1
    assert u.loc["id_B1", "wickets"] == 1                                    # the run out is not hers
    assert u.loc["id_B1", "legal_balls_bowled"] == 5
    assert missing == [] and len(people) == 22


def test_usage_survives_a_match_without_wickets(tmp_path):
    u = E.build_usage(parse(tmp_path, {"1": simple()}))
    assert u.dismissed.sum() == 0 and u.wickets.sum() == 0


def test_switches(tmp_path):
    p = ["P"] + A[1:]
    q = [f"Q{i}" for i in range(11)]
    r = [f"R{i}" for i in range(11)]
    T = parse(tmp_path, {
        "1": wpl("Mumbai Indians", "Delhi Capitals", p, q, "2023-03-01"),
        "2": wpl("Mumbai Indians", "Delhi Capitals", A, ["P"] + q[1:], "2024-03-01"),   # P moves
        "3": wpl("UP Warriorz", "Gujarat Giants", r, ["P"] + q[1:], "2026-03-01"),      # misses 2025, moves again
    })
    people, _ = E.build_people(T)
    s = E.build_switches(E.build_player_team_season(T), people).query("player_id == 'id_P'")
    assert s[["from_team", "to_team", "to_season", "gap"]].values.tolist() == [
        ["Mumbai Indians", "Delhi Capitals", 2024, 1.0], ["Delhi Capitals", "Gujarat Giants", 2026, 2.0]]


# ---------------- validation ----------------
def test_hard_checks(tmp_path):
    T = parse(tmp_path, {"1": simple()})
    usage = E.build_usage(T)
    assert V.hard_failures(V.validate(T, usage)) == {}
    T["deliveries"] = pd.concat([T["deliveries"], T["deliveries"].iloc[[0]]])
    T["matches"].loc[0, "method"] = "Awarded"
    bad = V.hard_failures(V.validate(T, usage))
    assert bad["dup_delivery_keys"] == 1 and bad["awarded_not_excluded"] == 1


# ---------------- weights (D-012) ----------------
def test_relevance_uses_only_earlier_wpl_players(tmp_path):
    """A player whose WPL debut is in 2025 must not raise s_c for the 2025 fold (decision 4a)."""
    newbie = ["N"] + [f"I{i}" for i in range(10)]
    eng = [f"E{i}" for i in range(11)]
    t1 = inns("India", [[dl("N", "E0", "I0", bat=1)]])
    t2 = inns("England", [[dl("E0", "N", "E1", bat=1)]], target={"runs": 2, "overs": 20})
    T = parse(tmp_path, {
        "t": match([t1, t2], date="2024-06-01", players={"India": newbie, "England": eng}),
        "w23": wpl("Mumbai Indians", "Delhi Capitals", A, B, "2023-03-01"),
        "w25": wpl("Mumbai Indians", "Delhi Capitals", newbie, B, "2025-03-01"),
    })
    assert W.relevance(T, 2025)["T20I India"] == 0.0
    assert W.relevance(T, 2026)["T20I India"] == 1.0


def test_recency_halves_every_two_years_and_skips_the_test_season(tmp_path):
    T = parse(tmp_path, {"a": simple(date="2024-01-01"), "b": simple(date="2022-01-01"),
                         "c": simple(date="2026-01-01")})
    w = W.match_weights(T, 2026, use_relevance=False).set_index("match_id")
    assert set(w.index) == {"a", "b"}
    assert w.loc["a", "recency"] == pytest.approx(0.5) and w.loc["b", "recency"] == pytest.approx(0.25)
    assert W.effective_n([1, 1, 1, 1]) == 4


# ---------------- snapshots ----------------
def test_download_refuses_a_registered_name(tmp_path, monkeypatch):
    """The D-017 incident: a registered snapshot must come back through fetch, never a fresh download."""
    monkeypatch.setattr(S, "SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setattr(S, "REGISTRY_PATH", str(tmp_path / "registry.json"))
    S.save_registry({"x.zip": {"sha256": "0" * 64}})
    with pytest.raises(RuntimeError, match="use fetch"):
        S.download("https://example.invalid/x.zip", "x.zip")


def test_fetch_refuses_a_corrupt_local_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setattr(S, "REGISTRY_PATH", str(tmp_path / "registry.json"))
    f = tmp_path / "x.zip"
    f.write_bytes(b"abc")
    S.save_registry({"x.zip": {"sha256": S.sha256_of_file(f), "hf_repo": "r", "hf_path": "p", "hf_revision": "v"}})
    assert S.fetch("x.zip") == str(f)
    f.write_bytes(b"abcx")
    with pytest.raises(RuntimeError, match="does not match"):
        S.fetch("x.zip")
