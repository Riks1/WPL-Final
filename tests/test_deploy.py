"""Phase 3.5d: the folder uploaded to the Space has what the server needs and nothing else."""
import json
from pathlib import Path

from scripts.deploy_space import ROOT, build_tree


def test_space_folder(tmp_path):
    info = build_tree(ROOT, tmp_path, sha="abc123", ref="v-test")
    names = {p.name for p in tmp_path.iterdir()}
    assert {"app", "wpl", "models", "templates", "run.py", "requirements.txt", "Dockerfile",
            "README.md", "build_info.json"} == names                       # no tests, data, legacy pickles, paper
    assert (tmp_path / "README.md").read_text().startswith("---\ntitle:")     # the Space's config header comes first
    assert json.loads((tmp_path / "build_info.json").read_text())["sha"] == "abc123" == info["sha"]
    assert not list(tmp_path.rglob("*.pyc")) and not list(tmp_path.rglob("*.pkl"))
    assert (tmp_path / "models" / "ratings_v3.json").exists()
