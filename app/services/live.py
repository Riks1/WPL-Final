from app.errors import ModelNotLoadedError
from app.services.model_loader import model_registry
from wpl.serving import predict_live


def predict(data: dict) -> dict:
    if model_registry.live_model is None:
        raise ModelNotLoadedError("Live model not loaded")

    bundle = model_registry.live_model
    out = predict_live(bundle, data["innings"], data["balls"], data.get("max_balls", 120), data.get("target"))
    p = out["bat_first_win_prob"]
    batting = p if data["innings"] == 1 else 1 - p
    s = out["state"]
    legal = int(s["legal_balls"])
    return {
        "bat_first_win_prob": round(100 * p, 2),
        "chasing_win_prob": round(100 * (1 - p), 2),
        "batting_win_prob": round(100 * batting, 2),
        "bowling_win_prob": round(100 * (1 - batting), 2),
        "score": {"runs": int(s["cum_runs"]), "wickets": int(s["cum_wickets"]), "legal_balls": legal,
                  "overs": f"{legal // 6}.{legal % 6}"},
        "match_state": {k: round(v, 3) for k, v in s.items()},
        "model": {"version": model_registry.version, "family": bundle["family"]},
    }
