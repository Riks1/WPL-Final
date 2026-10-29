import numpy as np
import pandas as pd

HARD = {'dup_delivery_keys', 'completed_without_2_innings', 'awarded_not_excluded', 'wickets_gt_10',
        'batter_not_in_xi', 'bowler_not_in_xi', 'winner_vs_scores_model_scope'}
def check(name, bad, cols=None, show=10):
    n = len(bad)
    print(f"[{'ok ' if n == 0 else 'FLAG'}] {name}: {n}")
    if n:
        print(bad[cols].head(show).to_string(index=False) if cols else bad.head(show).to_string(index=False))
    return bad


def validate(T, usage):
    m, inn, dl, w, pl = T['matches'], T['innings'], T['deliveries'], T['wickets'], T['players']
    main = inn[~inn.super_over]
    res = {}
    res['dup_delivery_keys'] = check('duplicate delivery keys', dl[dl.duplicated(['match_id', 'innings', 'seq'])])
    n_inn = main.groupby('match_id').size()
    odd = m[~m.match_id.map(n_inn).fillna(0).eq(2) & (m.result_type != 'no_result')]
    res['completed_without_2_innings'] = check('completed matches without exactly 2 innings', odd,
                                               ['match_id', 'date', 'competition', 'result_type'])
    res['awarded_not_excluded'] = check('awarded results still in the data', m[m.method == 'Awarded'],
                                        ['match_id', 'date', 'competition', 'winner'])
    res['wickets_gt_10'] = check('innings with more than 10 wickets', main[main.wickets > 10])
    res['balls_over_max'] = check('innings with more legal balls than max_balls',
                                  main[main.legal_balls > main.max_balls],
                                  ['match_id', 'innings', 'legal_balls', 'max_balls'])
    i1 = main[main.innings == 1][['match_id', 'total']]
    i2 = main[main.innings == 2][['match_id', 'target', 'target_overs', 'total']]
    t = i1.merge(i2, on='match_id', suffixes=('_1', '_2')).merge(
        m[['match_id', 'date', 'competition', 'model_scope', 'reduced', 'method']], on='match_id')
    res['target_mismatch'] = check('file target != innings-1 total + 1 (unreduced, no method)',
                                   t[~t.reduced & t.method.isna() & (t.target != t.total_1 + 1)],
                                   ['match_id', 'date', 'competition', 'total_1', 'target', 'target_overs'])
    t = t.merge(m[['match_id', 'result_type', 'winner', 'bat_first_team', 'y']], on='match_id')
    plain = t[(t.result_type == 'win') & t.method.isna()]
    implied = np.where(plain.total_2 >= plain.target, 0.0, 1.0)
    res['winner_vs_scores'] = check('winner disagrees with the scores', plain[implied != plain.y],
                                    ['match_id', 'date', 'competition', 'total_1', 'total_2', 'target', 'winner'])
    bad = res['winner_vs_scores']
    res['winner_vs_scores_model_scope'] = check('  ... of which in the model scope', bad[bad.model_scope])
    over_legal = dl[~dl.super_over].groupby(['match_id', 'innings', 'over']).legal.sum()
    res['overs_gt_6_legal'] = check('overs with more than 6 legal balls', over_legal[over_legal > 6].reset_index())
    res['bowler_gt_4_overs'] = check('bowlers with more than 24 legal balls in an innings',
                                     usage[usage.legal_balls_bowled > 24],
                                     ['match_id', 'innings', 'player_id', 'legal_balls_bowled'])
    res['bat_pos_gt_11'] = check('batting positions above 11', usage[usage.bat_pos > 11],
                                 ['match_id', 'innings', 'player_id', 'bat_pos'])
    xi = set(zip(pl.match_id, pl.team, pl.player_id))
    d = dl[~dl.super_over]
    bad_bat = d[[(a, b, c) not in xi for a, b, c in zip(d.match_id, d.batting_team, d.batter_id)]]
    bad_bowl = d[[(a, b, c) not in xi for a, b, c in zip(d.match_id, d.bowling_team, d.bowler_id)]]
    res['batter_not_in_xi'] = check('deliveries whose batter is not in the batting XI',
                                    bad_bat.drop_duplicates(['match_id', 'batter_id']), ['match_id', 'innings', 'batter_id'])
    res['bowler_not_in_xi'] = check('deliveries whose bowler is not in the bowling XI',
                                    bad_bowl.drop_duplicates(['match_id', 'bowler_id']), ['match_id', 'innings', 'bowler_id'])
    k = m.assign(teams=m[['bat_first_team', 'chase_team']].apply(lambda r: tuple(sorted(map(str, r))), axis=1))
    res['duplicate_matches'] = check('possible duplicate matches (same date, venue, teams)',
                                     k[k.duplicated(['date', 'venue_id', 'teams'], keep=False)],
                                     ['match_id', 'date', 'venue', 'teams', 'competition'])
    xi_n = pl.groupby(['match_id', 'team']).size().rename('n').reset_index()
    rep = T['replacements'].groupby(['match_id', 'team']).size().rename('reps').reset_index()
    x = xi_n[xi_n.n != 11].merge(rep, on=['match_id', 'team'], how='left').fillna({'reps': 0})
    res['xi_not_11_unexplained'] = check('team sheets != 11 not explained by a replacement', x[x.n - x.reps != 11])
    return res
def hard_failures(res):
    return {k: len(b) for k, b in res.items() if k in HARD and len(b)}
