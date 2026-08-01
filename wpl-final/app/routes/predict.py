import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from marshmallow import ValidationError

from app.errors import InvalidInputError
from app.extensions import db
from app.models import PredictionLog
from app.schemas import LiveInputSchema, PrematchInputSchema
from app.services import live as live_service
from app.services import prematch as prematch_service

predict_bp = Blueprint("predict", __name__, url_prefix="/api")


def _log_prediction(endpoint, request_payload, response_payload, latency_ms):
    """Best-effort logging — a DB hiccup should never break a prediction response."""
    try:
        entry = PredictionLog(
            endpoint=endpoint,
            request_payload=request_payload,
            response_payload=response_payload,
            latency_ms=latency_ms,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to write prediction log for %s", endpoint)


@predict_bp.route("/prematch-predict", methods=["POST"])
def prematch_predict():
    try:
        data = PrematchInputSchema().load(request.get_json(silent=True) or {})
    except ValidationError as err:
        raise InvalidInputError("Invalid pre-match input", payload=err.messages)

    start = time.perf_counter()
    result = prematch_service.predict(data)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    response = {"success": True, "timestamp": datetime.now(timezone.utc).isoformat(), **result}
    _log_prediction("prematch-predict", data, response, latency_ms)
    return jsonify(response)


@predict_bp.route("/live-predict", methods=["POST"])
def live_predict():
    try:
        data = LiveInputSchema().load(request.get_json(silent=True) or {})
    except ValidationError as err:
        raise InvalidInputError("Invalid live-match input", payload=err.messages)

    start = time.perf_counter()
    result = live_service.predict(data)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    response = {"success": True, "timestamp": datetime.now(timezone.utc).isoformat(), **result}
    _log_prediction("live-predict", data, response, latency_ms)
    return jsonify(response)
