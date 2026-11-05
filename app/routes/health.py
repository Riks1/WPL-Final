import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from app.services.model_loader import model_registry

health_bp = Blueprint("health", __name__, url_prefix="/api")
BUILD_FILE = Path(__file__).resolve().parents[2] / "build_info.json"     # optional, written by a deploy pipeline
BUILD = json.loads(BUILD_FILE.read_text()) if BUILD_FILE.exists() else {"sha": "local", "ref": "local"}


@health_bp.route("/health")
def health():
    return jsonify(
        {
            "status": "healthy" if model_registry.is_ready else "degraded",
            "prematch_loaded": model_registry.prematch_model is not None,
            "live_loaded": model_registry.live_model is not None,
            "model_version": model_registry.version,
            "versions": model_registry.versions,
            "ratings_loaded": model_registry.ratings is not None,
            "build": BUILD,
            # Startup result only: health is polled every 5 minutes, and querying the database here would keep
            # Neon's free compute awake around the clock and exhaust its monthly allowance.
            "database": current_app.config.get("DB_STATUS", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@health_bp.route("/model-info")
def model_info():
    """The model card: library versions, features, data hash, training date, decision."""
    if model_registry.model_card is None:
        return jsonify({"success": False, "error": "model card not loaded"}), 503
    return jsonify({"success": True, **model_registry.model_card})
