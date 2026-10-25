import json
import logging
from pathlib import Path

from wpl.serving import load_bundle

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Loads the versioned JSON bundles written by step 8 of the training notebook, once, at startup.

    Files: <MODEL_DIR>/live_<version>.json, prematch_<version>.json, model_card.json.
    MODEL_VERSION (env var) picks the version, so a rollback is a config change, not a code change.
    """

    def __init__(self):
        self.prematch_model = None
        self.live_model = None
        self.model_card = None
        self.version = None

    def load(self, model_dir="models", version="v1"):
        model_dir = Path(model_dir)
        self.version = version
        for attr, name in (("live_model", f"live_{version}.json"), ("prematch_model", f"prematch_{version}.json")):
            try:
                setattr(self, attr, load_bundle(model_dir / name))
                logger.info("Loaded %s (family=%s)", name, getattr(self, attr)["family"])
            except Exception:
                setattr(self, attr, None)
                logger.exception("Failed to load %s", name)
        try:
            self.model_card = json.loads((model_dir / "model_card.json").read_text())
        except Exception:
            self.model_card = None
            logger.exception("Failed to load model_card.json")

    @property
    def is_ready(self):
        return self.prematch_model is not None and self.live_model is not None


model_registry = ModelRegistry()
