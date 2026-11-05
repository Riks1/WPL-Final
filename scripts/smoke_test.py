"""Check a running API over HTTP, the way a user would call it (e.g. after `docker run`).

    python -m scripts.smoke_test --url http://localhost:7860 --expect-sha local

1. Waits until /api/health reports the expected commit (so the old build answering cannot pass the test).
2. Replays live cases from models/parity_fixture.json and XI cases from models/xi_parity_fixture.json against the
   probabilities and strengths computed by the training code.
3. Checks pre-match, input validation, that the internal ratings lookup is protected, and that predictions are logged.
Every request carries X-Smoke-Test, so the prediction log records it as smoke/<endpoint>. Exits non-zero on failure."""
import argparse
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {'X-Smoke-Test': '1'}


def wait_for_build(url, sha, timeout):
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        try:
            h = requests.get(f'{url}/api/health', headers=HEADERS, timeout=30).json()
            last = h.get('build', {}).get('sha')
            if last == sha and h.get('status') == 'healthy':
                return h
        except (requests.RequestException, ValueError):
            pass                                              # Space restarting: not up yet
        time.sleep(15)
    raise SystemExit(f'health never reported build {sha[:12]} as healthy within {timeout}s (last seen: {last})')


def check(name, ok, detail=''):
    print(f"  [{'ok' if ok else 'FAIL'}] {name}{': ' + detail if detail and not ok else ''}")
    return ok


def post(url, path, payload):
    return requests.post(f'{url}{path}', json=payload, headers=HEADERS, timeout=60)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--expect-sha', required=True)
    ap.add_argument('--timeout', type=int, default=900)
    ap.add_argument('--live-cases', type=int, default=20)
    a = ap.parse_args(argv)
    url = a.url.rstrip('/')

    health = wait_for_build(url, a.expect_sha, a.timeout)
    print(f"build {health['build']['ref']} ({a.expect_sha[:12]}) is live; versions {health['versions']}")
    results = []

    live = json.loads((ROOT / 'models' / 'parity_fixture.json').read_text())['cases'][:a.live_cases]
    worst = 0.0
    for c in live:
        payload = {'innings': c['innings'], 'max_balls': c['max_balls'],
                   'balls': [{'runs': r, 'legal': bool(l), 'wickets': w} for r, l, w in c['balls']]}
        if c['target'] is not None:
            payload['target'] = c['target']
        got = post(url, '/api/live-predict', payload).json()['bat_first_win_prob']
        worst = max(worst, abs(got - round(100 * c['expected_bat_first_prob'], 2)))
    results.append(check(f'live: {len(live)} parity cases within 0.011 points', worst <= 0.011, f'worst {worst:.4f}'))

    xi = json.loads((ROOT / 'models' / 'xi_parity_fixture.json').read_text())['cases']
    bf, ch = xi[0], xi[1]
    r = post(url, '/api/xi-strength', {'bat_first_xi': bf['xi'], 'chase_xi': ch['xi']}).json()
    results.append(check('xi-strength: matches the training-side strengths',
                         r.get('success') and abs(r['bat_first']['strength'] - bf['expected']['strength']) < 0.001
                         and abs(r['chase']['strength'] - ch['expected']['strength']) < 0.001, json.dumps(r)[:300]))

    v = health['versions']['prematch']
    bundle = json.loads((ROOT / 'models' / f'prematch_{v}.json').read_text())
    r = post(url, '/api/prematch-predict', {'bat_first_team': 'Mumbai Indians', 'chase_team': 'Delhi Capitals',
                                            'toss_winner': 'Mumbai Indians'}).json()
    if bundle['family'] == 'base_rate':
        ok = r.get('success') and r['bat_first_win_prob'] == round(100 * bundle['p_base'], 2)
    else:
        ok = r.get('success') and 0 < r['bat_first_win_prob'] < 100
    results.append(check(f'prematch ({v}) answers as the registry says', ok, json.dumps(r)[:300]))

    bad = post(url, '/api/xi-strength', {'bat_first_xi': bf['xi'][:10], 'chase_xi': ch['xi']})
    results.append(check('invalid input is rejected with 400', bad.status_code == 400, str(bad.status_code)))

    lookup = requests.get(f"{url}/api/ratings/{bf['xi'][0]}", headers=HEADERS, timeout=30)
    results.append(check('ratings lookup is not open (401 without the token, or 404 when no token is configured)',
                         lookup.status_code in (401, 404), str(lookup.status_code)))

    hist = requests.get(f'{url}/api/history?limit=100', headers=HEADERS, timeout=30).json()
    logged = sum(p['endpoint'].startswith('smoke/') for p in hist.get('predictions', []))
    results.append(check('smoke requests were written to the prediction log', logged >= 3, f'{logged} smoke rows'))

    print(f"{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
