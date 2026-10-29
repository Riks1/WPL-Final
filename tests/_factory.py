"""Tiny Cricsheet-shaped matches for edge-case tests (no network, no real data)."""
import json
import zipfile
A = [f"A{i}" for i in range(1, 12)]          # batting-first XI
B = [f"B{i}" for i in range(1, 12)]          # chasing XI

def dl(batter="A1", bowler="B1", ns="A2", bat=0, extras=None, wickets=None, non_boundary=False, repl=None):
  ex = extras or {}
  d = {"batter": batter, "bowler": bowler, "non_striker": ns,
       "runs": {"batter": bat, "extras": sum(ex.values()), "total": bat + sum(ex.values())}}
  if non_boundary:
    d["runs"]["non_boundary"] = True
  if ex:
    d["extras"] = ex
  if wickets:
    d["wickets"] = wickets
  if repl:
    d["replacements"] = {"match": repl}
  return d
def out(player, kind, fielder=None):
    w = {"player_out": player, "kind": kind}
    if fielder:
        w["fielders"] = [{"name": fielder}]
    return w
def inns(team,overs,**kw):
  return {"team": team, "overs": [{"over": i, "deliveries": ds} for i, ds in enumerate(overs)], **kw}

def match(innings, teams=("India", "England"), team_type="international", match_type="T20", event=None,
          outcome=None, overs=20, bpo=6, gender="female", date="2024-01-01", venue="Wankhede Stadium, Mumbai",
          city="Mumbai", players=None):
  players = players or {teams[0]:A,teams[1]:B}
  people = {n: f"id_{n}" for names in players.values() for n in names}
  info = {"gender": gender, "match_type": match_type, "team_type": team_type, "overs": overs,
            "balls_per_over": bpo, "teams": list(teams), "dates": [date], "venue": venue, "city": city,
            "toss": {"winner": teams[0], "decision": "bat"},
            "outcome": outcome or {"winner": teams[0], "by": {"runs": 1}},
            "players": players, "registry": {"people": people}}
  if event:
      info["event"] = {"name": event}
  return {"info": info, "innings": innings}
def simple(teams=("India", "England"), **kw):
    """Two plain innings: 10 off the first, 6 off the second (team batting first wins)."""
    i1 = inns(teams[0], [[dl(bat=4), dl(bat=6)]])
    i2 = inns(teams[1], [[dl("B1", "A1", "B2", bat=6)]], target={"runs": 11, "overs": 20})
    return match([i1, i2], teams=teams, **kw)
def to_zip(tmp_path, matches, name="snap.zip"):
    """matches = {match_id: match dict} -> a zip parse_snapshot can read."""
    p = tmp_path / name
    with zipfile.ZipFile(p, "w") as z:
        for mid, m in matches.items():
            z.writestr(f"{mid}.json", json.dumps(m))
    return p
