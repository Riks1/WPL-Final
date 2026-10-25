"""The app must reproduce the notebook's probabilities from raw ball history.

models/parity_fixture.json is written by step 8 of the notebook: 200 real match states, each with
the ball history of its innings and the probability the NOTEBOOK computed. If the app's feature
code or model code ever drifts from training, this test fails."""

import json
from pathlib import Path

import pytest

from app.services.model_loader import model_registry
from wpl.serving import predict_live

FIXTURE = Path(__file__).resolve().parent.parent / "models" / "parity_fixture.json"
CASES = json.loads(FIXTURE.read_text())["cases"] if FIXTURE.exists() else []


def deliveries(case):
    return [{"runs": r, "legal": bool(l), "wickets": w} for r, l, w in case["balls"]]


@pytest.mark.skipif(not CASES, reason="no parity fixture")
def test_serving_code_reproduces_notebook(app):
    bundle = model_registry.live_model
    worst = max(abs(predict_live(bundle, c["innings"], deliveries(c), c["max_balls"], c["target"])["bat_first_win_prob"]
                    - c["expected_bat_first_prob"]) for c in CASES)
    assert worst < 1e-9, f"largest difference from the notebook: {worst}"


@pytest.mark.skipif(not CASES, reason="no parity fixture")
def test_api_reproduces_notebook(client):
    for c in CASES[:40]:
        payload = {"innings": c["innings"], "max_balls": c["max_balls"], "balls": deliveries(c)}
        if c["target"] is not None:
            payload["target"] = c["target"]
        resp = client.post("/api/live-predict", json=payload).get_json()
        assert resp["success"], resp
        assert resp["bat_first_win_prob"] == pytest.approx(round(100 * c["expected_bat_first_prob"], 2), abs=0.011)
