import json, os, re, zipfile
import numpy as np
import pandas as pd

FULL_MEMBERS = {'Australia', 'Bangladesh', 'England', 'India', 'Ireland', 'New Zealand', 'Pakistan',
                'South Africa', 'Sri Lanka', 'West Indies', 'Zimbabwe', 'Afghanistan'}
SCOPE_EVENTS = ["Women's Premier League", "Women's T20 Challenge"]          # D-011
NOT_DISMISSALS = {'retired hurt', 'retired not out'}                        # D-005 / decision 1a
BOWLER_KINDS = {'bowled', 'caught', 'caught and bowled', 'lbw', 'stumped', 'hit wicket'}
TEAM_ALIASES = {"Royal Challengers Bangalore": "Royal Challengers Bengaluru"}
TABLES = ('matches', 'innings', 'deliveries', 'wickets', 'players', 'replacements')
EMPTY_COLUMNS = {
    'wickets': ['match_id', 'innings', 'seq', 'player_out_id', 'kind', 'bowler_id', 'fielder_ids',
                'bowler_credited', 'team_dismissal'],
    'replacements': ['match_id', 'innings', 'seq', 'team', 'in_id', 'out_id', 'reason'],
}
WPL = "Women's Premier League"


def canon(team):
    return TEAM_ALIASES.get(team, team)


def strip_women(t):
    return re.sub(r'\s+Women$', '', t)


def overs_to_balls(overs):
    return int(overs) * 6 + round((overs % 1) * 10)


# ---- 2.3a ----
def classify(info):
    """(competition, in_scope) under D-011."""
    if (info.get('gender') != 'female' or info.get('match_type') not in ('T20', 'IT20')
            or info.get('overs') != 20 or info.get('balls_per_over', 6) != 6):
        return None, False
    teams = {strip_women(t) for t in info.get('teams', [])}
    if info.get('match_type') == 'IT20' or info.get('team_type') == 'international':
        if teams <= FULL_MEMBERS:
            comp = 'T20I India' if 'India' in teams else 'T20I other full members'
        else:
            comp = 'T20I associate'
        return comp, comp == 'T20I India'
    comp = re.sub(r'\s+\d{4}(/\d{2,4})?$', '', (info.get('event') or {}).get('name', 'unknown')).strip()
    return comp, any(k.lower() in comp.lower() for k in SCOPE_EVENTS)


# ---- 2.3b ----
def resolve_result(info):
    """Stage 1 label rule. Returns (winner, result_type)."""
    out = info.get('outcome', {})
    if 'winner' in out:
        return out['winner'], 'win'
    if out.get('eliminator'):
        return out['eliminator'], 'tie_super_over'
    return None, ('tie' if out.get('result') == 'tie' else 'no_result')


# ---- 2.3b-d ----
def parse_match(match_id, d, competition,model_scope):
    info = d['info']
    reg = info.get('registry', {}).get('people', {})
    pid = lambda name: reg.get(name)
    T = {k: [] for k in ('matches', 'innings', 'deliveries', 'wickets', 'players', 'replacements')}

    all_inns = d.get('innings', [])
    main = [i for i in all_inns if not i.get('super_over')]
    winner, result_type = resolve_result(info)
    bat_first = main[0]['team'] if main else None
    chase = next((t for t in info['teams'] if t != bat_first), None) if bat_first else None
    tgt = main[1].get('target', {}) if len(main) > 1 else {}
    sched = overs_to_balls(info.get('overs', 20))

    T['matches'].append({
        'match_id': match_id, 'date': pd.Timestamp(info['dates'][0]), 'season': int(info['dates'][0][:4]),
        'competition': competition, 'model_scope': model_scope, 'event': (info.get('event') or {}).get('name'),

        'team_type': info.get('team_type'), 'venue': info.get('venue'), 'city': info.get('city'),
        'bat_first_team': canon(bat_first) if bat_first else None, 'chase_team': canon(chase) if chase else None,
        'toss_winner': canon(info['toss']['winner']) if 'toss' in info else None,
        'toss_decision': info.get('toss', {}).get('decision'),
        'winner': canon(winner) if winner else None, 'result_type': result_type,
        'y': float(winner == bat_first) if winner else (0.5 if result_type == 'tie' else np.nan),
        'method': info.get('outcome', {}).get('method'), 'sched_balls': sched,
        'reduced': bool(tgt.get('overs') and overs_to_balls(tgt['overs']) < sched),
    })
    for team, names in info.get('players', {}).items():
        for n in names:
            T['players'].append({'match_id': match_id, 'team': canon(team), 'player_id': pid(n), 'name': n})

    for idx, inn in enumerate(all_inns, 1):
        bat = inn['team']
        bowl = next(t for t in info['teams'] if t != bat)
        so = bool(inn.get('super_over'))
        if so:
            max_balls = 6
        elif idx == 2 and 'overs' in tgt:
            max_balls = overs_to_balls(tgt['overs'])
        else:
            max_balls = sched
        runs = wkts = legal = 0
        seq = 0
        for o in inn['overs']:
            for b, dl in enumerate(o['deliveries']):
                seq += 1
                ex = dl.get('extras', {})
                wd, nb = ex.get('wides', 0), ex.get('noballs', 0)
                is_legal = not wd and not nb
                n_out = 0
                for w in dl.get('wickets', []):
                    team_dis = w['kind'] not in NOT_DISMISSALS
                    n_out += team_dis
                    T['wickets'].append({
                        'match_id': match_id, 'innings': idx, 'seq': seq, 'player_out_id': pid(w['player_out']),
                        'kind': w['kind'], 'bowler_id': pid(dl['bowler']),
                        'fielder_ids': [pid(f['name']) for f in w.get('fielders', []) if 'name' in f],
                        'bowler_credited': w['kind'] in BOWLER_KINDS, 'team_dismissal': team_dis})
                for r in dl.get('replacements', {}).get('match', []):
                    T['replacements'].append({'match_id': match_id, 'innings': idx, 'seq': seq,
                                              'team': canon(r.get('team', '')), 'in_id': pid(r.get('in')),
                                              'out_id': pid(r.get('out')), 'reason': r.get('reason')})
                rb = dl['runs']['batter']
                nonb = bool(dl['runs'].get('non_boundary'))
                T['deliveries'].append({
                    'match_id': match_id, 'innings': idx, 'seq': seq, 'over': o['over'], 'ball_in_over': b,
                    'super_over': so, 'batting_team': canon(bat), 'bowling_team': canon(bowl),
                    'batter_id': pid(dl['batter']), 'bowler_id': pid(dl['bowler']),
                    'non_striker_id': pid(dl['non_striker']),
                    'runs_batter': rb, 'runs_extras': dl['runs']['extras'], 'runs_total': dl['runs']['total'],
                    'wides': wd, 'noballs': nb, 'byes': ex.get('byes', 0), 'legbyes': ex.get('legbyes', 0),
                    'penalty': ex.get('penalty', 0), 'non_boundary': nonb,
                    'legal': is_legal, 'ball_faced': not wd, 'bowler_runs': rb + wd + nb,
                    'is_four': rb == 4 and not nonb, 'is_six': rb == 6 and not nonb, 'n_dismissals': n_out})
                runs += dl['runs']['total']; legal += is_legal; wkts = min(wkts + n_out, 10)
        pen = inn.get('penalty_runs', {})
        it = inn.get('target', {})
        T['innings'].append({
            'match_id': match_id, 'innings': idx, 'super_over': so, 'batting_team': canon(bat),
            'bowling_team': canon(bowl), 'runs': runs, 'penalty_pre': pen.get('pre', 0),
            'penalty_post': pen.get('post', 0), 'total': runs + pen.get('pre', 0) + pen.get('post', 0),
            'wickets': wkts, 'legal_balls': legal, 'max_balls': max_balls,
            'target_runs': it.get('runs'), 'target_overs': it.get('overs')})
    return T


# ---- 2.3e ----
def parse_snapshot(zip_path, exclusions=None, verbose=True):
    excl = set(exclusions or {})
    skipped = []
    tables = {k: [] for k in TABLES}
    with zipfile.ZipFile(zip_path) as z:
        for name in sorted(z.namelist()):
            if not name.endswith('.json'):
                continue
            mid = os.path.basename(name)[:-5]
            if mid in excl:
                skipped.append(mid)
                continue
            d = json.loads(z.read(name))
            comp, keep = classify(d['info'])
            if comp is None:
                continue
            for k, rows in parse_match(mid, d, comp, keep).items():
                tables[k].extend(rows)
    if verbose:
        print(f'excluded by data/exclusions.json: {len(skipped)} {skipped}')

    out = {k: pd.DataFrame(v) if v else pd.DataFrame(columns=EMPTY_COLUMNS.get(k, [])) for k, v in tables.items()}
    out['matches'] = out['matches'].sort_values(['date', 'match_id']).reset_index(drop=True)

    pl = out['players'].merge(out['matches'][['match_id', 'competition']], on='match_id')
    wpl_ever = set(pl.loc[pl.competition == WPL, 'player_id'].dropna())
    has_wpl = pl.assign(w=pl.player_id.isin(wpl_ever)).groupby('match_id').w.any()
    out['matches']['ratings_scope'] = out['matches'].match_id.map(has_wpl).fillna(False).astype(bool)

    inn = out['innings']                       # stage 1 target fallback (D-015)
    for c in ('target_runs', 'target_overs'):
        inn[c] = pd.to_numeric(inn[c]).astype(float)
    tot1 = inn[(inn.innings == 1) & ~inn.super_over].set_index('match_id').total
    is2 = (inn.innings == 2) & ~inn.super_over
    inn['target'] = np.where(is2, inn.target_runs.fillna(inn.match_id.map(tot1) + 1), np.nan)
    return out


def write_tables(tables, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for k, df in tables.items():
        df.to_parquet(os.path.join(out_dir, f'{k}.parquet'), index=False)

STAGE1_COLS = ['match_id', 'innings', 'seq', 'over_num', 'ball_num', 'batting_team', 'max_balls', 'target', 'y',
               'delivery_runs', 'is_legal', 'is_wicket', 'cum_runs', 'cum_wickets', 'legal_balls',
               'runs_last_30', 'wkts_last_30', 'partnership_runs', 'partnership_balls']


def stage1_ball_table(T):
    """The stage 1 ball table rebuilt from the stage 2 tables (continuity check, step E)."""
    from wpl.live_features import innings_state
    m = T['matches']
    m = m[m.result_type.isin(['win', 'tie_super_over'])]
    meta = T['innings'].set_index(['match_id', 'innings'])
    dl = T['deliveries']
    dl = dl[~dl.super_over & dl.match_id.isin(m.match_id) & dl.innings.isin([1, 2])] \
        .sort_values(['match_id', 'innings', 'seq'])
    rows = []
    for (mid, i), g in dl.groupby(['match_id', 'innings'], sort=False):
        states = innings_state([{'runs': r, 'legal': l, 'wickets': w}
                                for r, l, w in zip(g.runs_total, g.legal, g.n_dismissals)])
        mi = meta.loc[(mid, i)]
        for s, seq, ov, b in zip(states, g.seq, g.over, g.ball_in_over):
            rows.append({'match_id': mid, 'innings': i, 'seq': seq, 'over_num': ov, 'ball_num': b,
                         'batting_team': mi.batting_team, 'max_balls': mi.max_balls,
                         'target': mi.target if i == 2 else np.nan, **s})
    out = pd.DataFrame(rows).merge(m[['match_id', 'y']], on='match_id')
    return out[STAGE1_COLS].sort_values(['match_id', 'innings', 'seq']).reset_index(drop=True)


