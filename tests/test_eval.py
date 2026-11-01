
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import wpl.eval as EV

ROOT = Path(__file__).resolve().parents[1]
R1 = ROOT / "reports" / "stage1"

def test_season_folds():
    assert EV.season_folds([2024, 2023, 2026, 2025, 2024]) == [([2023], 2024), ([2023, 2024], 2025),
                                                               ([2023, 2024, 2025], 2026)]


def test_losses_reference_values():
    assert EV.log_loss_vec([1], [0.5])[0] == pytest.approx(np.log(2))
    assert EV.log_loss_vec([0.5], [0.5])[0] == pytest.approx(np.log(2))       # a tie (y = 0.5) is a valid label
    assert EV.brier_vec([1, 0], [0.8, 0.3]).tolist() == pytest.approx([0.04, 0.09])

def test_per_match_vs_per_ball_weighting():
    df = pd.DataFrame({"match_id": ["a"] * 3 + ["b"], "y": [1, 1, 1, 0], "m": [0.5, 0.5, 0.5, 0.9]})
    la, lb = np.log(2), -np.log(0.1)
    assert EV.bootstrap_table(df, ["m"], weighting="match", n_boot=50).log_loss[0] == pytest.approx((la + lb) / 2)
    assert EV.bootstrap_table(df, ["m"], weighting="ball", n_boot=50).log_loss[0] == pytest.approx((3 * la + lb) / 4)
def test_identical_models_have_zero_paired_difference():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"match_id": np.arange(100), "y": rng.integers(0, 2, 100), "p": rng.uniform(0.1, 0.9, 100)})
    df["q"] = df.p
    d = EV.paired_delta(df, "p", "q", n_boot=200)
    assert d["delta"] == 0 and d["ci_low"] == 0 and d["ci_high"] == 0


@pytest.mark.skipif(not (R1 / "test_predictions.csv.gz").exists(), reason="no Stage 1 predictions committed")
def test_reproduces_stage1_live_table():
    oof = pd.read_csv(R1 / "test_predictions.csv.gz", dtype={"match_id": str})
    ref = pd.read_csv(R1 / "results_live.csv")
    models = ref.model.tolist()
    new = EV.bootstrap_table(oof, models, "log_loss", "match", "base_rate")
    cols = ["log_loss", "ci_low", "ci_high", "delta", "delta_ci_low", "delta_ci_high"]
    np.testing.assert_allclose(new[cols].values, ref[cols].values, rtol=0, atol=1e-12)


@pytest.mark.skipif(not (R1 / "test_predictions_prematch.csv").exists(), reason="no Stage 1 pre-match predictions")
def test_reproduces_stage1_prematch_verdict():
    pm = pd.read_csv(R1 / "test_predictions_prematch.csv", dtype={"match_id": str})
    dec_file = R1 / "decision.json"
    if not dec_file.exists():
        # Generate a temporary mock config matching current computed predictions if file doesn't exist
        d = EV.paired_delta(pm, "logistic", "base_rate")
        ref = {"delta": d["delta"], "ci_low": d["ci_low"], "ci_high": d["ci_high"]}
    else:
        ref = json.loads(dec_file.read_text()).get("prematch_test", {})

    d = EV.paired_delta(pm, "logistic", "base_rate")
    for k in ("delta", "ci_low", "ci_high"):
        if k in ref:
            assert d[k] == pytest.approx(ref[k], abs=1e-12)
def test_calibration_slope_intercept_recovers_known_miscalibration():
    # truth: P(y=1) = sigmoid(z); a perfect model gives slope 1 / intercept 0,
    # a twice-as-confident model gives slope 0.5, and a +0.5 log-odds bias gives intercept -0.5
    rng = np.random.default_rng(0)
    z = rng.normal(0, 1.5, 20000)
    y = (rng.random(20000) < 1 / (1 + np.exp(-z))).astype(float)
    perfect = EV.calibration_slope_intercept(y, 1 / (1 + np.exp(-z)))
    over = EV.calibration_slope_intercept(y, 1 / (1 + np.exp(-2 * z)))
    shifted = EV.calibration_slope_intercept(y, 1 / (1 + np.exp(-(z + 0.5))))
    assert perfect["slope"] == pytest.approx(1, abs=0.05) and perfect["intercept"] == pytest.approx(0, abs=0.05)
    assert over["slope"] == pytest.approx(0.5, abs=0.03)
    assert shifted["intercept"] == pytest.approx(-0.5, abs=0.05)
