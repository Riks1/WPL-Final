
import json
from pathlib import Path

import pandas as pd
import pytest

import wpl.data.parse as P
from wpl.data.snapshots import sha256_of_file

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "tests" / "fixtures" / "stage1_ball_reference.json"
REF = ROOT / "tests" / "fixtures" / "stage1_ball_reference.csv.gz"


@pytest.mark.skipif(not (META.exists() and REF.exists()), reason="no stage 1 reference committed")
def test_stage2_parser_reproduces_stage1_ball_table():
    meta = json.loads(META.read_text())
    snap = ROOT / "data" / "snapshots" / meta["snapshot"]
    assert snap.exists(), f"{snap} missing"
    assert sha256_of_file(snap) == meta["sha256"]
    ref = pd.read_csv(REF, dtype={"match_id": str})
    new = P.stage1_ball_table(P.parse_snapshot(snap, verbose=False))
    assert len(new) == meta["rows"] == len(ref)
    pd.testing.assert_frame_equal(new[P.STAGE1_COLS].reset_index(drop=True),
                                  ref[P.STAGE1_COLS].reset_index(drop=True),
                                  check_dtype=False, check_exact=False, rtol=0, atol=1e-9)
