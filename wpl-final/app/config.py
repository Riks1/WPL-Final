import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Base config, driven by environment variables (see .env.example)."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'predictions.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CRICAPI_KEY = os.environ.get("CRICAPI_KEY")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    MODEL_DIR = os.environ.get("MODEL_DIR", str(BASE_DIR))


class TestConfig(Config):
    """Used by the test suite: in-memory DB, real models."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
