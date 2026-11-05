"""Phase 3.5c (D13): the prediction log on a real Postgres. The database tests run only when TEST_DATABASE_URL
is set (CI's Postgres service, or the Neon dev branch from Colab). They touch only rows they create themselves,
so they are safe against any database."""
import os
import uuid

import pytest

from app import create_app
from app.config import TestConfig, database_url
from app.extensions import db
from app.models import PredictionLog

URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not URL, reason="set TEST_DATABASE_URL to run against Postgres")


def make_app():
    """A fresh app on the test database: what each deploy does at startup (create_all, then serve)."""
    class Postgres(TestConfig):
        SQLALCHEMY_DATABASE_URI = database_url(URL)
    return create_app(Postgres)


def close(app):
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def endpoint_tag():
    tag = f"pg-test-{uuid.uuid4().hex[:8]}"
    yield tag
    app = make_app()
    with app.app_context():
        PredictionLog.query.filter_by(endpoint=tag).delete()
        db.session.commit()
    close(app)


@pytest.mark.parametrize("raw, expected", [
    ("postgres://u:p@h/db?sslmode=require", "postgresql+psycopg://u:p@h/db?sslmode=require"),
    ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ("sqlite:///x.db", "sqlite:///x.db"),
])
def test_database_url_names_the_driver(raw, expected):
    assert database_url(raw) == expected


@needs_db
def test_log_survives_three_restarts(endpoint_tag):
    for i in range(3):                                   # three "deploys", each writing one row
        app = make_app()
        with app.app_context():
            db.session.add(PredictionLog(endpoint=endpoint_tag, request_payload={"deploy": i},
                                         response_payload={"p": 0.5}, latency_ms=1.0))
            db.session.commit()
        close(app)
    app = make_app()                                     # a fourth start reads all three back
    with app.app_context():
        rows = PredictionLog.query.filter_by(endpoint=endpoint_tag).order_by(PredictionLog.id).all()
        assert [r.request_payload["deploy"] for r in rows] == [0, 1, 2]
        assert all(r.created_at.tzinfo is not None for r in rows)      # stored with its time zone
    close(app)


@needs_db
def test_api_call_is_logged_to_postgres():
    app = make_app()
    client = app.test_client()
    with app.app_context():
        before = db.session.query(db.func.max(PredictionLog.id)).scalar() or 0
    resp = client.post("/api/live-predict", json={"innings": 1, "balls": [{"runs": 4, "legal": True, "wickets": 0}]})
    assert resp.status_code == 200
    with app.app_context():
        new = PredictionLog.query.filter(PredictionLog.id > before, PredictionLog.endpoint == "live-predict").all()
        assert len(new) == 1 and new[0].response_payload["success"]
        for r in new:                                    # clean up only what this test wrote
            db.session.delete(r)
        db.session.commit()
    close(app)


def test_api_starts_and_predicts_without_a_database():
    class Down(TestConfig):
        SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://nobody@127.0.0.1:1/none?connect_timeout=2"
    client = create_app(Down).test_client()
    assert client.get("/api/health").get_json()["database"] == "unavailable at startup"
    resp = client.post("/api/live-predict", json={"innings": 1, "balls": [{"runs": 1, "legal": True, "wickets": 0}]})
    assert resp.status_code == 200 and resp.get_json()["success"]          # the prediction is served; the log is not
