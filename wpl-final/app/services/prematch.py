import pandas as pd

from app.errors import ModelNotLoadedError
from app.services.model_loader import model_registry


def predict(features: dict) -> dict:
    if model_registry.prematch_model is None:
        raise ModelNotLoadedError("Pre-match model not loaded")

    bundle = model_registry.prematch_model
    ordered = {f: features.get(f, 0) for f in bundle["features"]}
    df = pd.DataFrame([ordered])
    proba = bundle["model"].predict_proba(df[bundle["features"]])

    return {
        "team_a_prob": round(float(proba[0][1] * 100), 2),
        "team_b_prob": round(float(proba[0][0] * 100), 2),
        "model_info": bundle["metrics"],
    }
