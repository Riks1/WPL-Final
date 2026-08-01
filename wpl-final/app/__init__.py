from pathlib import Path

from flask import Flask

from app.config import Config
from app.errors import register_error_handlers
from app.extensions import db
from app.logging_config import setup_logging
from app.services.model_loader import model_registry


def create_app(config_class=Config):
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(__name__, template_folder=str(project_root / "templates"))
    app.config.from_object(config_class)

    setup_logging(app)

    (project_root / "instance").mkdir(exist_ok=True)

    db.init_app(app)
    register_error_handlers(app)

    from app.routes.cricapi import cricapi_bp
    from app.routes.health import health_bp
    from app.routes.history import history_bp
    from app.routes.main import main_bp
    from app.routes.predict import predict_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(predict_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(cricapi_bp)

    with app.app_context():
        # Blueprints above import app.models (PredictionLog), which registers it
        # with db.metadata — that import MUST happen before create_all(), or the
        # table silently never gets created.
        db.create_all()
        model_registry.load(model_dir=app.config["MODEL_DIR"])

    app.logger.info("Application startup complete (models ready: %s)", model_registry.is_ready)
    return app
