from app.errors import InvalidInputError, ModelNotLoadedError
from app.services.model_loader import model_registry
from wpl.serving import predict_prematch


def predict(data: dict) -> dict:
    if model_registry.prematch_model is None:
        raise ModelNotLoadedError("Pre-match model not loaded")

    bundle = model_registry.prematch_model
    unknown = [t for t in (data["bat_first_team"], data["chase_team"]) if t not in bundle["teams"]]
    if unknown:
        raise InvalidInputError("Unknown team", payload={"unknown": unknown, "known_teams": bundle["teams"]})

    out = predict_prematch(bundle, data["bat_first_team"], data["chase_team"], data["toss_winner"])
    p = out["bat_first_win_prob"]
    note = ("Served as the base rate: on held-out seasons the pre-match model did not beat it "
            "(see reports/stage1/results.md)." if bundle["family"] == "base_rate" else "")
    return {
        "bat_first_win_prob": round(100 * p, 2),
        "chasing_win_prob": round(100 * (1 - p), 2),
        "features": {k: round(float(v), 3) for k, v in out["features"].items()},
        "model": {"version": model_registry.version, "family": bundle["family"], "note": note},
    }
