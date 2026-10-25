"""Pre-match (post-toss) features from the team history stored in the serving bundle.
Mirrors the notebook's TeamHistory (parity-tested)."""

from __future__ import annotations


class TeamHistory:
    def __init__(self, d: dict):
        self.window = d["window"]
        self.results = {k: list(v)[-self.window:] for k, v in d["results"].items()}
        self.h2h = {(a, b): (w, g) for a, b, w, g in d["h2h"]}

    def _form(self, team: str) -> float:
        r = self.results.get(team, [])
        return (sum(r) + 1) / (len(r) + 2)

    def features(self, bat_first: str, chase: str, toss_bf: int) -> dict:
        wins, games = self.h2h.get((bat_first, chase), (0, 0))
        return {"form_diff": self._form(bat_first) - self._form(chase),
                "h2h_adv": (wins + 1) / (games + 2) - 0.5,
                "toss_bf": int(toss_bf)}
