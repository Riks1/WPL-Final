import hmac
import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from marshmallow import ValidationError

from app.errors import AppError, InvalidInputError, ModelNotLoadedError
from app.routes.predict import _log_prediction
from app.schemas import XiStrengthInputSchema
from app.services.model_loader import model_registry
from wpl.serving import predict_xi_strength

xi_bp = Blueprint("xi", __name__, url_prefix="/api")

NOTE = ("XI strength is in runs, not a win probability. Under the pre-specified Stage 3 evaluation it did not "
        "improve WPL pre-match probabilities; see docs/stage3/MODEL_CARD_prematch_v3.md.")


def _rounded(team):
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in team.items()}


def _ratings_meta(r):
    return {k: r[k] for k in ("version", "as_of", "snapshot", "snapshot_sha256", "ratings_content_hash")}


@xi_bp.route("/xi-strength", methods=["POST"])
def xi_strength():
    ratings = model_registry.ratings
    if ratings is None:
        raise ModelNotLoadedError("Ratings not loaded")
    try:
        data = XiStrengthInputSchema().load(request.get_json(silent=True) or {})
    except ValidationError as err:
        raise InvalidInputError("Invalid XI-strength input", payload=err.messages)

    start = time.perf_counter()
    try:
        out = predict_xi_strength(ratings, data["bat_first_xi"], data["chase_xi"], data["allow_unknown"])
    except KeyError as err:
        raise InvalidInputError("Unknown player ids (send allow_unknown=true to rate them as debutants)",
                                payload={"unknown": err.args[0]})
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    response = {"success": True, "timestamp": datetime.now(timezone.utc).isoformat(),
                "bat_first": _rounded(out["bat_first"]), "chase": _rounded(out["chase"]),
                "xi_margin": round(out["xi_margin"], 3), "xi_margin_sd": round(out["xi_margin_sd"], 3),
                "unknown_players": out["unknown_players"], "ratings": _ratings_meta(ratings), "note": NOTE}
    _log_prediction("xi-strength", data, response, latency_ms)
    return jsonify(response)


@xi_bp.route("/ratings/<player_id>")
def player_ratings(player_id):
    """Internal: one player's ratings. Needs the X-Internal-Token header; without INTERNAL_TOKEN set it does not exist."""
    token = current_app.config.get("INTERNAL_TOKEN")
    if not token:
        raise AppError("Endpoint not found", status_code=404)
    if not hmac.compare_digest(request.headers.get("X-Internal-Token", ""), token):
        raise AppError("Unauthorized", status_code=401)
    ratings = model_registry.ratings
    if ratings is None:
        raise ModelNotLoadedError("Ratings not loaded")
    row = ratings["players"].get(player_id)
    if row is None:
        raise AppError("Unknown player id", status_code=404)
    return jsonify({"success": True, "player_id": player_id, **dict(zip(ratings["fields"], row)),
                    "ratings": _ratings_meta(ratings)})
