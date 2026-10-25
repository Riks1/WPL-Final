import pytest

from app.services.model_loader import model_registry


def balls(runs_seq=(), wides=0, wickets=0, dots=0):
    """Build a history: given runs (legal balls), then wides, then wicket balls, then dots."""
    out = [{"runs": r, "legal": True, "wickets": 0} for r in runs_seq]
    out += [{"runs": 1, "legal": False, "wickets": 0}] * wides
    out += [{"runs": 0, "legal": True, "wickets": 1}] * wickets
    out += [{"runs": 0, "legal": True, "wickets": 0}] * dots
    return out


def live(client, **kw):
    return client.post("/api/live-predict", json=kw)


# ---------------- health / model card ----------------
def test_health(client):
    data = client.get("/api/health").get_json()
    assert data["status"] == "healthy" and data["model_version"] == "v1"


def test_model_card_records_provenance(client):
    card = client.get("/api/model-info").get_json()
    for key in ("snapshot_sha256", "trained_utc", "libraries", "label", "live", "prematch"):
        assert key in card
    assert card["live"]["family"] in ("parscore", "logistic")


# ---------------- live ----------------
def test_live_predict_from_ball_history(client):
    resp = live(client, innings=2, target=166, balls=balls([4, 1, 0, 6, 1, 1], wides=1, wickets=1))
    data = resp.get_json()
    assert resp.status_code == 200 and data["success"]
    assert data["score"] == {"runs": 14, "wickets": 1, "legal_balls": 7, "overs": "1.1"}
    assert data["bat_first_win_prob"] + data["chasing_win_prob"] == pytest.approx(100, abs=0.02)
    assert data["match_state"]["runs_needed"] == 152
    assert data["model"]["family"] == model_registry.live_model["family"]


def test_live_empty_history_is_before_ball_one(client):
    resp = live(client, innings=1, balls=[])
    assert resp.status_code == 200 and resp.get_json()["score"]["legal_balls"] == 0


def test_live_separates_won_and_lost_chases(client):
    """The v0 bug gave 51-53% to both of these. They must now be far apart."""
    cruising = live(client, innings=2, target=160, balls=balls([2] * 75 + [0] * 33, wickets=0)).get_json()
    lost = live(client, innings=2, target=160, balls=balls([1] * 60, wickets=8, dots=40)).get_json()
    assert cruising["score"]["runs"] == 150 and lost["score"]["runs"] == 60
    assert cruising["chasing_win_prob"] > 75 and lost["chasing_win_prob"] < 5


def test_live_more_runs_helps_the_chaser(client):
    p = [live(client, innings=2, target=170, balls=balls([r] * 60 + [0] * 30)).get_json()["chasing_win_prob"] for r in (1, 2)]
    assert p[1] > p[0]


def test_live_terminal_states(client):
    won = live(client, innings=2, target=10, balls=balls([6, 4])).get_json()
    lost = live(client, innings=2, target=50, balls=balls([1] * 10, wickets=10)).get_json()
    assert won["chasing_win_prob"] == 100 and lost["chasing_win_prob"] == 0


@pytest.mark.parametrize("payload,field", [
    ({"innings": 2, "balls": []}, "target"),
    ({"innings": 3, "balls": []}, "innings"),
    ({"innings": 1}, "balls"),
    ({"innings": 1, "balls": [{"runs": 0, "legal": True, "wickets": 0}] * 61, "max_balls": 60}, "balls"),
    ({"innings": 1, "balls": [{"runs": 0, "legal": True, "wickets": 1}] * 11}, "balls"),
    ({"innings": 1, "balls": [{"runs": 15}]}, "balls"),
])
def test_live_validation(client, payload, field):
    resp = live(client, **payload)
    assert resp.status_code == 400 and field in resp.get_json()["details"]


def test_cricapi_route_is_explicitly_disabled(client):
    resp = client.get("/api/cricapi-live/123")
    assert resp.status_code == 501 and "ball-by-ball" in resp.get_json()["error"]


# ---------------- pre-match ----------------
def test_prematch_predict_success(client, app):
    t = model_registry.prematch_model["teams"]
    resp = client.post("/api/prematch-predict", json={"bat_first_team": t[0], "chase_team": t[1], "toss_winner": t[1]})
    data = resp.get_json()
    assert resp.status_code == 200 and data["success"] and data["features"]["toss_bf"] == 0
    assert data["bat_first_win_prob"] + data["chasing_win_prob"] == pytest.approx(100, abs=0.02)


def test_prematch_unknown_team(client, app):
    t = model_registry.prematch_model["teams"]
    resp = client.post("/api/prematch-predict", json={"bat_first_team": "Nope XI", "chase_team": t[1], "toss_winner": t[1]})
    assert resp.status_code == 400 and "known_teams" in resp.get_json()["details"]


@pytest.mark.parametrize("payload,field", [
    ({"bat_first_team": "A", "chase_team": "A", "toss_winner": "A"}, "chase_team"),
    ({"bat_first_team": "A", "chase_team": "B", "toss_winner": "C"}, "toss_winner"),
    ({"bat_first_team": "A"}, "chase_team"),
])
def test_prematch_validation(client, payload, field):
    resp = client.post("/api/prematch-predict", json=payload)
    assert resp.status_code == 400 and field in resp.get_json()["details"]


# ---------------- history / misc ----------------
def test_history_logs_predictions(client):
    live(client, innings=1, balls=balls([1, 2]))
    data = client.get("/api/history").get_json()
    assert data["count"] >= 1 and data["predictions"][0]["endpoint"] == "live-predict"


def test_unknown_route_returns_404(client):
    assert client.get("/api/does-not-exist").status_code == 404


def test_index_page_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200 and b"ball by ball" in resp.data
