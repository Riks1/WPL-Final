"""Logistic models from saved plain-number parameters (scaler mean/scale + coefficients)."""

import numpy as np


def predict(params: dict, X) -> np.ndarray:
    z = ((np.asarray(X, float) - np.array(params['mean'])) / np.array(params['scale'])) @ np.array(params['coef'])
    return 1 / (1 + np.exp(-(z + params['intercept'])))
