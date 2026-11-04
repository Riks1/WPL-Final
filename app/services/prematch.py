from app.errors import InvalidInputError, ModelNotLoadedError
from app.services.model_loader import model_registry
from wpl.serving import predict_prematch


def predict(data: dict) -> dict:
    if model_registry.prematch_model is None:
        raise ModelNotLoadedError("Pre-match model not loaded")

    bundle = model_registry.prematch_model
    teams = bundle.get("teams")                      # v1 knows the WPL teams; the v3 base rate needs none
    unknown = [t for t in (data["bat_first_team"], data["chase_team"]) if teams and t not in teams]
    if unknown:
        raise InvalidInputError("Unknown team", payload={"unknown": unknown, "known_teams": bundle["teams"]})

    out = predict_prematch(bundle, data["bat_first_team"], data["chase_team"], data["toss_winner"])
    p = out["bat_first_win_prob"]
    if bundle["family"] != "base_rate":
        note = ""
    elif "decision" in bundle:                       # Stage 3 registry entry
        d = bundle["decision"]
        note = (f"Served as the base rate: under the pre-specified Stage 3 rule, XI-strength features did not beat it "
                f"on 66 held-out WPL matches (log-loss {d['delta']:+.3f} [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}]); "
                "see docs/stage3/MODEL_CARD_prematch_v3.md.")
    else:
        note = ("Served as the base rate: on held-out seasons the pre-match model did not beat it "
                "(see reports/stage1/results.md).")
    return {
        "bat_first_win_prob": round(100 * p, 2),
        "chasing_win_prob": round(100 * (1 - p), 2),
        "features": {k: round(float(v), 3) for k, v in out["features"].items()},
        "model": {"version": model_registry.versions.get("prematch"), "family": bundle["family"], "note": note},
    }
