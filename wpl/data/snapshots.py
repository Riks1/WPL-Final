import datetime, hashlib, json, os, shutil
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = os.environ.get('WPL_SNAPSHOT_DIR', str(ROOT / 'data' / 'snapshots'))
REGISTRY_PATH = str(ROOT / 'data' / 'snapshots' / 'registry.json')

def sha256_of_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(chunk), b''):
            h.update(block)
    return h.hexdigest()

def load_registry():
    if not os.path.exists(REGISTRY_PATH):
        return {}
    with open(REGISTRY_PATH) as f:
        return json.load(f)

def save_registry(reg):
    tmp = REGISTRY_PATH + '.part'
    with open(tmp, 'w') as f:
        json.dump(reg, f, indent=2, sort_keys=True)
    os.replace(tmp, REGISTRY_PATH)

def make_manifest(path, source_url, downloaded_utc=None):
    if downloaded_utc is None:
        downloaded_utc = datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc).isoformat(timespec='seconds')
    return {'file': os.path.basename(path), 'sha256': sha256_of_file(path), 'bytes': os.path.getsize(path),
            'source_url': source_url, 'downloaded_utc': downloaded_utc}

def download(url, name):
    import requests
    path = os.path.join(SNAPSHOT_DIR, name)
    reg = load_registry()
    if name in reg and not os.path.exists(path):
        raise RuntimeError(f"{name} is registered: use fetch('{name}'). Cricsheet's file changes daily, so "
                           "downloading again would put a different file under the same name")
    if os.path.exists(path):
        man = make_manifest(path, url)
        if name in reg and reg[name]['sha256'] != man['sha256']:
            raise RuntimeError(f"{name}: local file does not match the registry; it changed or is corrupt")
        print(f"reusing {name}")
        return path, reg.get(name, man)
    r = requests.get(url, stream=True, timeout=300)
    r.raise_for_status()
    with open(path + '.part', 'wb') as f:
        for block in r.iter_content(1 << 20):
            f.write(block)
    os.replace(path + '.part', path)
    return path, make_manifest(path, url, datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'))

def publish(name, manifest, hf_repo):
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ.get('HF_TOKEN'))
    path = os.path.join(SNAPSHOT_DIR, name)
    reg = load_registry()
    if name in reg:
        if reg[name]['sha256'] != manifest['sha256']:
            raise RuntimeError(f"{name} is already registered with a different hash; use a new name")
        print(f"{name} already published at {reg[name]['hf_revision'][:8]}")
        return reg[name]
    hf_path = f"snapshots/{name}"
    info = api.upload_file(path_or_fileobj=path, path_in_repo=hf_path, repo_id=hf_repo, repo_type='dataset',
                           commit_message=f"add {name} (sha256 {manifest['sha256'][:16]})")
    reg[name] = {**manifest, 'hf_repo': hf_repo, 'hf_path': hf_path, 'hf_revision': info.oid}
    save_registry(reg)
    return reg[name]

def fetch(name):
    reg = load_registry()
    if name not in reg:
        raise KeyError(f"{name} is not in {REGISTRY_PATH}")
    e = reg[name]
    path = os.path.join(SNAPSHOT_DIR, name)
    if os.path.exists(path):
        if sha256_of_file(path) == e['sha256']:
            return path
        raise RuntimeError(f"{name}: local copy does not match sha256 {e['sha256'][:16]}; delete it and fetch again")
    from huggingface_hub import hf_hub_download
    dl = hf_hub_download(e['hf_repo'], e['hf_path'], repo_type='dataset', revision=e['hf_revision'],
                         token=os.environ.get('HF_TOKEN'))
    if sha256_of_file(dl) != e['sha256']:
        raise RuntimeError(f"{name}: download from {e['hf_repo']}@{e['hf_revision'][:8]} has the wrong hash")
    shutil.copyfile(dl, path + '.part')
    os.replace(path + '.part', path)
    return path
