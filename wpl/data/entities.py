import re
import pandas as pd
import difflib
from wpl.data.parse import WPL

COMP_ALIASES = {"Women's T20 Challenge Match": "Women's T20 Challenge","New Zealand Cricket Women's Twenty20" :"Women's Super Smash", "Women's T20 Blaze": "T20 Blaze"}
VENUE_EXACT = {'Sylhet International Cricket Stadium, Academy Ground': 'sylhetacademyground'}
GENERIC_VENUES = {'countyground', 'gymkhanaclubground', 'universityoval'}
VENUE_ALIASES = {
    'ferozshahkotla': 'arunjaitleystadium',
    'darrensammynationalcricketstadium': 'darensammynationalcricketstadium',
    'gahangainternationalcricketstadiumrwanda': 'gahangainternationalcricketstadium',
    'tafawabalewasquaretbscricketoval': 'tafawabalewasquarecricketoval',
    'newwanderersstadium': 'thewanderersstadium',
     'beausejourstadium': 'darensammynationalcricketstadium',
}


def venue_key(venue, city=None):
  if venue in VENUE_EXACT:
    return VENUE_EXACT[venue]
  parts = [p.strip() for p in str(venue).split(',')]
  k = re.sub(r'[^a-z]', '', parts[0].lower())
  if k in GENERIC_VENUES:
    c = city if isinstance(city, str) and city else (parts[1] if len(parts) > 1 else '')
    k += re.sub(r'[^a-z]', '', c.lower())
  return VENUE_ALIASES.get(k, k)


def apply_aliases(T):
  m = T['matches']
  m['competition'] = m.competition.replace(COMP_ALIASES)
  m['venue_id'] = [venue_key(v, c) for v, c in zip(m.venue, m.city)]
  return T
def build_venues(T):
  m = T['matches'].sort_values('date')
  g = m.groupby('venue_id')
  v = pd.DataFrame({'name': g.venue.last(), 'city': g.city.last(), 'matches': g.size(),
                      'first': g.date.min(), 'last': g.date.max(),
                      'names_seen': g.venue.agg(lambda s: sorted(set(s)))})
  return v.reset_index()
def venue_review(venues, cutoff=0.85):
  ids = venues.venue_id.tolist()
  pairs = []
  for i, a in enumerate(ids):
      for b in difflib.get_close_matches(a, ids[i + 1:], n=5, cutoff=cutoff):
        pairs.append((a, b, round(difflib.SequenceMatcher(None, a, b).ratio(), 2)))
  return pd.DataFrame(pairs, columns=['venue_a', 'venue_b', 'similarity'])
def build_people(T):
  players_df = pd.DataFrame(T['players']) if isinstance(T['players'], list) else T['players']
  pl = players_df.merge(T['matches'][['match_id', 'date']], on='match_id').sort_values('date')
  g = pl.groupby('player_id')
  people = pd.DataFrame({'name': g.name.last(), 'names_seen': g.name.agg(lambda s: sorted(set(s))),
                           'matches': g.match_id.nunique(), 'first': g.date.min(), 'last': g.date.max()})
  dl = T['deliveries']
  on_field = set(pd.concat([dl.batter_id, dl.bowler_id, dl.non_striker_id]).dropna())
  missing = sorted(on_field - set(people.index))
  return people.reset_index(), missing
def build_player_team_season(T):
  players_df = pd.DataFrame(T['players']) if isinstance(T['players'], list) else T['players']
  pl = players_df.merge(T['matches'][['match_id', 'competition', 'season', 'date']], on='match_id')
  return (pl.groupby(['player_id', 'competition', 'season', 'team'])
              .agg(matches=('match_id', 'nunique'), first=('date', 'min'), last=('date', 'max'))
              .reset_index())
def build_switches(pts, people, competition=WPL):
  w = pts[pts.competition == competition].sort_values(['player_id','season','first'])
  main = w.sort_values('matches', kind='stable').groupby(['player_id','season']).tail(1)
  multi = w.groupby(['player_id','season']).team.nunique()
  main = main.sort_values(['player_id','season'])
  main['prev_team'] = main.groupby('player_id').team.shift(1)
  main['prev_season'] = main.groupby('player_id').season.shift(1)
  s = main[main.prev_team.notna() & (main.team != main.prev_team)]
  s = s.assign(gap=s.season - s.prev_season,
                two_teams_in_season=s.set_index(['player_id', 'season']).index.map(multi).values > 1)
  s = s.merge(people[['player_id', 'name']], on='player_id')
  return s[['player_id', 'name', 'prev_team', 'prev_season', 'team', 'season', 'gap', 'two_teams_in_season']] \
        .rename(columns={'prev_team': 'from_team', 'prev_season': 'from_season', 'team': 'to_team', 'season': 'to_season'})

def build_usage(T):
    dl = T['deliveries']
    dl = dl[~dl.super_over]
    keys = ['match_id', 'innings']
    # batting position: order of first appearance as striker or non-striker (striker first on ball 1)
    app = pd.concat([dl[keys + ['seq', 'batter_id']].rename(columns={'batter_id': 'player_id'}).assign(o=0),
                     dl[keys + ['seq', 'non_striker_id']].rename(columns={'non_striker_id': 'player_id'}).assign(o=1)])
    app = app.sort_values(keys + ['seq', 'o']).drop_duplicates(keys + ['player_id'])
    app['bat_pos'] = app.groupby(keys).cumcount() + 1
    bat = dl.groupby(keys + ['batter_id']).agg(balls_faced=('ball_faced', 'sum'), runs=('runs_batter', 'sum'),
                                               fours=('is_four', 'sum'), sixes=('is_six', 'sum')) \
        .reset_index().rename(columns={'batter_id': 'player_id'})
    w = T['wickets']
    out = w[w.team_dismissal.astype(bool)].groupby(keys + ['player_out_id']).size().rename('dismissed').reset_index() \
        .rename(columns={'player_out_id': 'player_id'})
    bowl = dl.groupby(keys + ['bowler_id']).agg(legal_balls_bowled=('legal', 'sum'), runs_conceded=('bowler_runs', 'sum'),
                                                wides=('wides', 'sum'), noballs=('noballs', 'sum')) \
        .reset_index().rename(columns={'bowler_id': 'player_id'})
    bw = w[w.bowler_credited.astype(bool)].groupby(keys + ['bowler_id']).size().rename('wickets').reset_index() \
        .rename(columns={'bowler_id': 'player_id'})
    bat_side = app[keys + ['player_id', 'bat_pos']].merge(bat, on=keys + ['player_id'], how='left') \
        .merge(out, on=keys + ['player_id'], how='left')
    bat_side = bat_side.fillna({'balls_faced': 0, 'runs': 0, 'fours': 0, 'sixes': 0, 'dismissed': 0})
    bowl_side = bowl.merge(bw, on=keys + ['player_id'], how='left').fillna({'wickets': 0})
    u = bat_side.merge(bowl_side, on=keys + ['player_id'], how='outer')
    for c in ['balls_faced', 'runs', 'fours', 'sixes', 'dismissed', 'legal_balls_bowled', 'runs_conceded',
              'wides', 'noballs', 'wickets']:
        u[c] = u[c].fillna(0).astype(int)
    return u
