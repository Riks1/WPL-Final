import pytest


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["prematch_loaded"] is True
    assert data["live_loaded"] is True
    assert data["status"] == "healthy"


def test_prematch_predict_success(client):
    payload = {
        "win_rate_diff": 0.10,
        "win_rate_diff_10": 0.05,
        "venue_win_rate_diff": 0.05,
        "h2h_win_rate_diff": 0.60,
        "venue_exp": 5,
        "toss_won_by_A": 1,
        "toss_choice": 1,
    }
    resp = client.post("/api/prematch-predict", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert 0 <= data["team_a_prob"] <= 100
    assert abs((data["team_a_prob"] + data["team_b_prob"]) - 100) < 0.1


def test_prematch_predict_defaults_missing_fields(client):
    resp = client.post("/api/prematch-predict", json={})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_prematch_predict_rejects_invalid_type(client):
    resp = client.post("/api/prematch-predict", json={"toss_choice": "not-a-number"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "toss_choice" in data["details"]


def test_prematch_predict_rejects_out_of_range_choice(client):
    resp = client.post("/api/prematch-predict", json={"toss_choice": 5})
    assert resp.status_code == 400


def test_live_predict_success(client):
    payload = {"cum_runs": 142, "cum_wickets": 4, "balls_faced": 108, "target": 166}
    resp = client.post("/api/live-predict", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert 0 <= data["batting_win_prob"] <= 100
    assert data["match_state"]["current_rr"] == pytest.approx(142 / (108 / 6), rel=1e-2)


def test_live_predict_handles_zero_overs_bowled(client):
    payload = {"cum_runs": 0, "cum_wickets": 0, "balls_faced": 0, "target": 180}
    resp = client.post("/api/live-predict", json=payload)
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_live_predict_rejects_invalid_wickets(client):
    resp = client.post("/api/live-predict", json={"cum_wickets": 15})
    assert resp.status_code == 400


def test_history_logs_predictions(client):
    client.post(
        "/api/live-predict",
        json={"cum_runs": 50, "cum_wickets": 2, "balls_faced": 60, "target": 160},
    )
    resp = client.get("/api/history")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] >= 1
    assert data["predictions"][0]["endpoint"] == "live-predict"
    assert "latency_ms" in data["predictions"][0]


def test_unknown_route_returns_404(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404


def test_index_page_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
