"""Phase 3.5b: the API's XI strength reproduces the training pipeline, and the new endpoints validate their input."""
import json
from pathlib import Path

import pytest

from app import create_app
from app.config import TestConfig
from app.services.model_loader import model_registry
from wpl.serving import lookup_players, predict_xi_strength
from wpl.strength import team_strength

MODELS = Path(__file__).resolve().parents[1] / "models"
FIXTURE = json.loads((MODELS / "xi_parity_fixture.json").read_text())
RATINGS = json.loads((MODELS / "ratings_v3.json").read_text())
CASES = FIXTURE["cases"]
TOKEN = {"X-Internal-Token": TestConfig.INTERNAL_TOKEN}


def xis():
    """Both XIs of the first fixture match."""
    a, b = CASES[0], CASES[1]
    assert a["match_id"] == b["match_id"]
    return a["xi"], b["xi"]


def post(client, **kw):
    return client.post("/api/xi-strength", json=kw)


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['match_id']}-{c['team']}")
def test_serving_matches_training_side(case):
    cols, unknown = lookup_players(RATINGS, case["xi"])
    got = team_strength(cols, RATINGS["lambda"], RATINGS["shares_by_pos"], RATINGS["data_min"])
    assert not unknown
    for k, v in case["expected"].items():
        assert got[k] == pytest.approx(v, abs=1e-9), k


def test_xi_strength_endpoint(client):
    bf, ch = xis()
    resp = post(client, bat_first_xi=bf, chase_xi=ch)
    data = resp.get_json()
    assert resp.status_code == 200 and data["success"]
    assert data["xi_margin"] == pytest.approx(data["bat_first"]["strength"] - data["chase"]["strength"], abs=0.002)
    assert data["bat_first"]["strength"] == pytest.approx(CASES[0]["expected"]["strength"], abs=0.001)
    assert data["ratings"]["version"] == "v3" and data["unknown_players"] == []
    assert "not a win probability" in data["note"]


def test_unknown_player_refused_unless_allowed(client):
    bf, ch = xis()
    bf = bf[:10] + ["ffffffff"]
    resp = post(client, bat_first_xi=bf, chase_xi=ch)
    assert resp.status_code == 400 and resp.get_json()["details"]["unknown"] == ["ffffffff"]
    ok = post(client, bat_first_xi=bf, chase_xi=ch, allow_unknown=True).get_json()
    assert ok["success"] and ok["unknown_players"] == ["ffffffff"] and ok["bat_first"]["n_debut"] >= 1


def test_debutant_gets_the_prior():
    cols, unknown = lookup_players(RATINGS, ["ffffffff"], allow_unknown=True)
    assert unknown == ["ffffffff"]
    assert cols["bat_runs"] == [RATINGS["debutant"]["bat_runs"]] and cols["legal_faced"] == [0.0]


@pytest.mark.parametrize("change, field", [
    (lambda bf, ch: (bf[:10], ch), "bat_first_xi"),                       # 10 players
    (lambda bf, ch: (bf[:10] + [ch[0]], ch), "chase_xi"),                 # same player in both XIs
    (lambda bf, ch: (bf[:10] + ["Mandhana"], ch), "bat_first_xi"),        # not a Cricsheet id
])
def test_xi_input_validation(client, change, field):
    bf, ch = change(*xis())
    resp = post(client, bat_first_xi=bf, chase_xi=ch)
    assert resp.status_code == 400 and field in resp.get_json()["details"]


def test_predict_xi_strength_reports_both_teams_unknowns():
    bf, ch = xis()
    with pytest.raises(KeyError) as e:
        predict_xi_strength(RATINGS, bf[:10] + ["ffffffff"], ch[:10] + ["eeeeeeee"])
    assert e.value.args[0] == ["ffffffff", "eeeeeeee"]


def test_ratings_lookup_needs_the_token(client):
    pid = CASES[0]["xi"][0]
    assert client.get(f"/api/ratings/{pid}").status_code == 401
    assert client.get(f"/api/ratings/{pid}", headers={"X-Internal-Token": "wrong"}).status_code == 401
    data = client.get(f"/api/ratings/{pid}", headers=TOKEN).get_json()
    assert data["success"] and data["player_id"] == pid and "bat_runs" in data
    assert client.get("/api/ratings/ffffffff", headers=TOKEN).status_code == 404


def test_ratings_lookup_hidden_without_token():
    class NoToken(TestConfig):
        INTERNAL_TOKEN = None
    client = create_app(NoToken).test_client()
    assert client.get(f"/api/ratings/{CASES[0]['xi'][0]}", headers=TOKEN).status_code == 404


def test_prematch_v3_serves_the_stage3_base_rate():
    class V3(TestConfig):
        PREMATCH_VERSION = "v3"
    client = create_app(V3).test_client()
    bundle = json.loads((MODELS / "prematch_v3.json").read_text())
    data = client.post("/api/prematch-predict", json={"bat_first_team": "Any Team A", "chase_team": "Any Team B",
                                                      "toss_winner": "Any Team A"}).get_json()
    assert data["success"] and data["bat_first_win_prob"] == round(100 * bundle["p_base"], 2)
    assert data["model"]["version"] == "v3" and "Stage 3" in data["model"]["note"] and data["features"] == {}


def test_health_reports_versions(client):
    data = client.get("/api/health").get_json()
    assert data["versions"] == {"live": "v1", "prematch": "v1", "ratings": "v3"} and data["ratings_loaded"]
