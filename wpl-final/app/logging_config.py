import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(app):
    log_dir = Path(app.root_path).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    level = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    app.logger.handlers.clear()
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(level)

    # keep Flask's default request logging from drowning out our own logs
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
