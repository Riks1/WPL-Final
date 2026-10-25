"""Live-state features: the serving copy of the notebook's innings_state, live-feature maths and
terminal-state rule (tests/test_parity_fixture.py proves they match the notebook)."""

from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 30
RRR_CAP = 36.0


def innings_state(deliveries, window: int = WINDOW) -> list[dict]:
    """deliveries: [{'runs': int, 'legal': bool, 'wickets': int}, ...] in bowling order.
    Returns one dict per delivery: the state AFTER that delivery."""
    rows = []
    runs = wickets = legal = 0
    runs_at_legal, wkts_at_legal = [0], [0]
    part_runs0 = part_legal0 = 0
    for d in deliveries:
        runs += int(d["runs"])
        legal += int(bool(d["legal"]))
        wickets = min(wickets + int(d["wickets"]), 10)
        if d["legal"]:
            runs_at_legal.append(runs)
            wkts_at_legal.append(wickets)
        if d["wickets"]:
            part_runs0, part_legal0 = runs, legal
        k = max(legal - window, 0)
        rows.append({
            "delivery_runs": int(d["runs"]),
            "is_legal": int(bool(d["legal"])),
            "is_wicket": int(d["wickets"] > 0),
            "cum_runs": runs,
            "cum_wickets": wickets,
            "legal_balls": legal,
            "runs_last_30": runs - runs_at_legal[k],
            "wkts_last_30": wickets - wkts_at_legal[k],
            "partnership_runs": runs - part_runs0,
            "partnership_balls": legal - part_legal0,
        })
    return rows


def compute_live_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["current_rr"] = (out["cum_runs"] / (out["legal_balls"].replace(0, np.nan) / 6)).fillna(0)
    out["balls_remaining"] = (out["max_balls"] - out["legal_balls"]).clip(lower=0)
    out["overs_remaining"] = out["balls_remaining"] / 6
    out["wickets_left"] = 10 - out["cum_wickets"]
    inn2 = out["innings"] == 2
    out["target"] = out["target"].where(inn2, 0.0).astype(float)
    out["runs_needed"] = (out["target"] - out["cum_runs"]).where(inn2, 0.0)
    rrr = np.where(out["balls_remaining"] > 0,
                   out["runs_needed"] * 6 / out["balls_remaining"].replace(0, np.nan),
                   np.where(out["runs_needed"] > 0, RRR_CAP, 0.0))
    out["required_rr"] = np.clip(np.nan_to_num(rrr), 0.0, RRR_CAP)
    out["rr_diff"] = (out["required_rr"] - out["current_rr"]).where(inn2, 0.0)
    out["projected_total"] = out["cum_runs"] + out["current_rr"] * out["balls_remaining"] / 6
    out["resources_remaining"] = (out["balls_remaining"] / out["max_balls"]) * (out["wickets_left"] / 10)
    return out


def terminal_prob(df: pd.DataFrame) -> pd.Series:
    out = pd.Series(np.nan, index=df.index)
    inn2 = df["innings"] == 2
    need = df["target"] - df["cum_runs"]
    done = inn2 & ((df["legal_balls"] >= df["max_balls"]) | (df["cum_wickets"] >= 10))
    out[inn2 & (need <= 0)] = 0.0
    out[done & (need == 1)] = 0.5
    out[done & (need >= 2)] = 1.0
    return out


def state_from_history(innings: int, deliveries: list[dict], max_balls: int = 120, target=None) -> pd.DataFrame:
    """API entry point: ball history of the current innings -> one feature row (after the last ball).
    An empty history means 'before the first ball'."""
    hist = innings_state(deliveries) if deliveries else []
    last = hist[-1] if hist else {"delivery_runs": 0, "is_legal": 0, "is_wicket": 0, "cum_runs": 0, "cum_wickets": 0,
                                  "legal_balls": 0, "runs_last_30": 0, "wkts_last_30": 0,
                                  "partnership_runs": 0, "partnership_balls": 0}
    row = {**last, "innings": int(innings), "max_balls": int(max_balls),
           "target": float(target) if (innings == 2 and target is not None) else np.nan}
    return compute_live_features(pd.DataFrame([row]))
