from datetime import datetime, timezone

from flask import Blueprint, jsonify

from app.services.model_loader import model_registry

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.route("/health")
def health():
    return jsonify(
        {
            "status": "healthy" if model_registry.is_ready else "degraded",
            "prematch_loaded": model_registry.prematch_model is not None,
            "live_loaded": model_registry.live_model is not None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
