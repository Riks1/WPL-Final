import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def database_url(raw):
    """Hosted Postgres (Neon) hands out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named,
    and we use psycopg 3. Anything else (the local SQLite default) passes through unchanged."""
    for prefix in ("postgres://", "postgresql://"):
        if raw.startswith(prefix):
            return "postgresql+psycopg://" + raw[len(prefix):]
    return raw


class Config:
    """Base config, driven by environment variables (see .env.example)."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = database_url(
        os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'predictions.db'}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Neon suspends idle compute after 5 minutes, which silently kills pooled connections: test each one before
    # use, and never keep one longer than 4.5 minutes.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 270}
    CRICAPI_KEY = os.environ.get("CRICAPI_KEY")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    MODEL_DIR = os.environ.get("MODEL_DIR", str(BASE_DIR / "models"))
    MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1")
    LIVE_VERSION = os.environ.get("LIVE_VERSION", MODEL_VERSION)
    PREMATCH_VERSION = os.environ.get("PREMATCH_VERSION", MODEL_VERSION)
    RATINGS_VERSION = os.environ.get("RATINGS_VERSION", "v3")
    INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN")      # unset -> the internal ratings lookup does not exist


class TestConfig(Config):
    """Used by the test suite: in-memory DB, real models."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LIVE_VERSION = PREMATCH_VERSION = "v1"
    RATINGS_VERSION = "v3"
    INTERNAL_TOKEN = "test-internal-token"
