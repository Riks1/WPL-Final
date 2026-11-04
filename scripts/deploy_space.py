"""Phase 3.5d (D14): deploy one git ref to the Hugging Face Space.

    python -m scripts.deploy_space --space riksss/wpl-win-probability --ref v3-rc1 --sha <commit>

Uploads only what the server needs (no tests, data, notebooks, reports or v0 pickles), stamps the build with the
commit it came from, then waits until the Space has built. Needs HF_TOKEN with write access to the Space.
`--dry-run` builds the folder and stops (used by the tests)."""
import argparse
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIP = ['app', 'wpl', 'models', 'templates', 'run.py', 'requirements.txt', 'Dockerfile']
IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc')
FAILED = {'BUILD_ERROR', 'RUNTIME_ERROR', 'CONFIG_ERROR', 'NO_APP_FILE'}


def build_tree(src, out, sha, ref):
    """Copy the shipped files from `src` into `out`, add the Space README and build_info.json."""
    src, out = Path(src), Path(out)
    for name in SHIP:
        p = src / name
        if p.is_dir():
            shutil.copytree(p, out / name, ignore=IGNORE)
        else:
            shutil.copy2(p, out / name)
    header = (src / 'deploy' / 'hf_space_header.md').read_text()
    (out / 'README.md').write_text(header + '\nWPL win-probability API. Source, tests and model cards: '
                                   'https://github.com/Riks1/WPL-Final\n')
    info = {'sha': sha, 'ref': ref, 'built_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    (out / 'build_info.json').write_text(json.dumps(info, indent=2))
    return info


def wait_for_build(api, space, timeout=1200, every=20, grace=120):
    """Poll the Space until the new build runs. A failure state only counts once the Space has picked up the
    upload (seen BUILDING or APP_STARTING) or after a grace period, because right after an upload the Space can
    still report the state of the previous commit."""
    t0, picked_up = time.time(), False
    while time.time() - t0 < timeout:
        stage = api.get_space_runtime(space).stage
        elapsed = time.time() - t0
        print(f'  {int(elapsed):4d}s  {stage}', flush=True)
        if stage in ('BUILDING', 'RUNNING_BUILDING', 'APP_STARTING'):
            picked_up = True
        if stage in FAILED and (picked_up or elapsed > grace):
            raise SystemExit(f'Space failed: {stage}. See the logs on the Space page.')
        if stage == 'RUNNING' and (picked_up or elapsed > 60):
            return stage
        time.sleep(every)
    raise SystemExit(f'Space did not reach RUNNING within {timeout}s')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--space', required=True)
    ap.add_argument('--ref', required=True)
    ap.add_argument('--sha', required=True)
    ap.add_argument('--src', default=str(ROOT))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)

    out = Path(tempfile.mkdtemp(prefix='space-'))
    info = build_tree(a.src, out, a.sha, a.ref)
    files = sorted(str(p.relative_to(out)) for p in out.rglob('*') if p.is_file())
    print(f'built {len(files)} files for {a.ref} ({a.sha[:12]}) in {out}')
    if a.dry_run:
        return 0

    from huggingface_hub import HfApi
    api = HfApi()                                             # reads HF_TOKEN from the environment
    # delete_patterns=['*']: remove files from the previous deploy that this build no longer ships. The library
    # never deletes .gitattributes, and does not delete files that are re-uploaded in the same commit.
    api.upload_folder(repo_id=a.space, repo_type='space', folder_path=str(out),
                      commit_message=f"Deploy {a.ref} ({a.sha[:12]})", delete_patterns=['*'])
    print(f"uploaded {info['ref']} to {a.space}; waiting for the build")
    wait_for_build(api, a.space)
    return 0


if __name__ == '__main__':
    sys.exit(main())
