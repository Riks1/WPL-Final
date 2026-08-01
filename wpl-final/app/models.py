from datetime import datetime, timezone

from app.extensions import db


class PredictionLog(db.Model):
    """Persists every prediction the API serves, for auditability and analysis."""

    __tablename__ = "prediction_logs"

    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(64), nullable=False, index=True)
    request_payload = db.Column(db.JSON, nullable=False)
    response_payload = db.Column(db.JSON, nullable=False)
    latency_ms = db.Column(db.Float, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "endpoint": self.endpoint,
            "request": self.request_payload,
            "response": self.response_payload,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat(),
        }
