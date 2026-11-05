import json
import logging
from pathlib import Path

from wpl.serving import load_bundle

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Loads the versioned JSON bundles once, at startup.

    Files: <MODEL_DIR>/live_<v>.json, prematch_<v>.json, ratings_<v>.json (optional), model_card.json.
    Each model has its own version (LIVE_VERSION, PREMATCH_VERSION, RATINGS_VERSION env vars), so a rollback
    or an upgrade of one model is a config change, not a code change.
    """

    def __init__(self):
        self.prematch_model = None
        self.live_model = None
        self.ratings = None
        self.model_card = None
        self.versions = {}

    @property
    def version(self):
        """Kept for the v1 API: the live model's version."""
        return self.versions.get("live")

    def load(self, model_dir="models", live_version="v1", prematch_version="v1", ratings_version=None):
        model_dir = Path(model_dir)
        self.versions = {"live": live_version, "prematch": prematch_version, "ratings": ratings_version}
        files = [("live_model", f"live_{live_version}.json"), ("prematch_model", f"prematch_{prematch_version}.json")]
        if ratings_version:
            files.append(("ratings", f"ratings_{ratings_version}.json"))
        for attr, name in files:
            try:
                setattr(self, attr, load_bundle(model_dir / name))
                logger.info("Loaded %s", name)
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
        """Live and pre-match are required; the ratings only power /api/xi-strength."""
        return self.prematch_model is not None and self.live_model is not None


model_registry = ModelRegistry()
