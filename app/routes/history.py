from flask import Blueprint, jsonify, request

from app.models import PredictionLog

history_bp = Blueprint("history", __name__, url_prefix="/api")


@history_bp.route("/history")
def history():
    limit = min(int(request.args.get("limit", 20)), 100)
    rows = (
        PredictionLog.query.order_by(PredictionLog.created_at.desc()).limit(limit).all()
    )
    return jsonify(
        {"success": True, "count": len(rows), "predictions": [r.to_dict() for r in rows]}
    )
