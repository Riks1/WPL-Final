import pandas as pd

from app.errors import ModelNotLoadedError
from app.services.model_loader import model_registry


def _engineer_features(raw: dict):
    cum_runs = raw["cum_runs"]
    cum_wickets = raw["cum_wickets"]
    balls_faced = raw["balls_faced"]
    target = raw["target"]

    wickets_left = 10 - cum_wickets
    balls_remaining = max(120 - balls_faced, 0)
    overs_remaining = balls_remaining / 6
    overs_bowled = balls_faced / 6

    current_rr = (cum_runs / overs_bowled) if overs_bowled > 0 else 0.0
    runs_needed = target - cum_runs
    required_rr = (runs_needed / overs_remaining) if overs_remaining > 0 else 0.0
    rr_diff = required_rr - current_rr
    over_num = balls_faced // 6
    resources_remaining = (balls_remaining / 120) * (wickets_left / 10)

    state = {
        "innings": raw.get("innings", 2),
        "cum_runs": cum_runs,
        "cum_wickets": cum_wickets,
        "wickets_left": wickets_left,
        "balls_faced": balls_faced,
        "balls_remaining": balls_remaining,
        "overs_remaining": overs_remaining,
        "current_rr": current_rr,
        "required_rr": required_rr,
        "rr_diff": rr_diff,
        "runs_last_6_overs": raw.get("runs_last_6_overs", 48),
        "last_6_overs_rr": raw.get("last_6_overs_rr", 8.0),
        "is_powerplay": 1 if over_num < 6 else 0,
        "is_middle_overs": 1 if 6 <= over_num < 16 else 0,
        "is_death_overs": 1 if over_num >= 16 else 0,
        "target": target,
        "runs_needed": runs_needed,
    }
    summary = {
        "current_rr": current_rr,
        "required_rr": required_rr,
        "rr_diff": rr_diff,
        "resources_remaining": resources_remaining,
    }
    return state, summary


def predict(raw: dict) -> dict:
    if model_registry.live_model is None:
        raise ModelNotLoadedError("Live model not loaded")

    bundle = model_registry.live_model
    state, summary = _engineer_features(raw)

    df = pd.DataFrame([state])
    X = df[bundle["features"]].fillna(0)

    if bundle["best_name"] == "GradientBoosting" and bundle.get("scaler") is not None:
        X = bundle["scaler"].transform(X)

    proba = bundle["model"].predict_proba(X)[:, 1][0]

    return {
        "batting_win_prob": round(float(proba * 100), 2),
        "bowling_win_prob": round(float((1 - proba) * 100), 2),
        "match_state": {k: round(v, 3) for k, v in summary.items()},
    }
