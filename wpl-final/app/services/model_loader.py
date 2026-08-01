import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Loads and holds the trained model artifacts in memory.

    A single instance (`models`, below) is shared across the app so the
    pickle files are only read from disk once, at startup.
    """

    def __init__(self):
        self.prematch_model = None
        self.live_model = None

    def load(self, model_dir="."):
        model_dir = Path(model_dir)

        try:
            with open(model_dir / "prematch_model.pkl", "rb") as f:
                self.prematch_model = pickle.load(f)
            logger.info(
                "Pre-match model loaded: %s", self.prematch_model["metrics"]["Model"]
            )
        except Exception:
            logger.exception("Failed to load pre-match model")

        try:
            with open(model_dir / "live_model.pkl", "rb") as f:
                self.live_model = pickle.load(f)
            logger.info("Live model loaded: %s", self.live_model["best_name"])
        except Exception:
            logger.exception("Failed to load live model")

    @property
    def is_ready(self):
        return self.prematch_model is not None and self.live_model is not None


# Module-level singleton, imported by services and routes.
model_registry = ModelRegistry()
