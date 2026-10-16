"""Rate a finished 9-cat draft: score every roster with the board model and simulate weekly H2H matchups.

Usage: python scripts/rate_draft.py drafts/<id>_picks.csv "<your team>" [--punt FT_IMPACT,TOV]

Reads the parsed picks (scripts/parse_draft.py) and reports/board_data.json. Prints each
team's simulated weekly matchup win rate, your category ranks, each of your picks against
the board's best available at that moment (under your punt, if given), and the best
undrafted players. Team strength in a category is the sum of per-game Z x GP/82; a
category is won with probability Phi(diff / sigma), sigma being week-to-week noise, and a
week is won with 5+ categories. Same scoring as scripts/simulate_punts.py. Unprojected
rookies count as average (zero Z). The model is grading picks it recommended, so the gaps
between teams matter more than the absolute win rates.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIGMA = {"PTS": 2.5, "REB": 2.5, "AST": 2.5, "STL": 5.0, "BLK": 4.5, "3PM": 3.5,
         "TOV": 3.5, "FG_IMPACT": 4.0, "FT_IMPACT": 4.0}
LABEL = {"FG_IMPACT": "FG%", "FT_IMPACT": "FT%", "TOV": "TO", "STL": "ST", "3PM": "3PTM"}


def win_prob_5of9(pw):
    d = np.zeros(len(pw) + 1)
    d[0] = 1
    for q in pw:
        d[1:] = d[1:] * (1 - q) + d[:-1] * q
        d[0] *= (1 - q)
    return d[5:].sum()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("picks")
    ap.add_argument("team")
    ap.add_argument("--punt", default="")
    a = ap.parse_args()
    punt = [c for c in a.punt.split(",") if c]

    picks = pd.read_csv(a.picks).sort_values("overall")
    teams = list(dict.fromkeys(picks["fantasy_team"]))
    n_teams = len(teams)
    rounds = len(picks) // n_teams
    board = json.loads((ROOT / "reports" / "board_data.json").read_text())
    cats = board["cats"]
    P = {p["id"]: p for p in board["players"]}
    proj = [p for p in board["players"] if not p.get("np")]
    pool = n_teams * rounds

    def floor_scores(punt_list):
        v = {p["id"]: sum(z for c, z in p["z"].items() if c not in punt_list) for p in proj}
        repl = sorted(v.values(), reverse=True)[pool - 1]
        return {k: (v[k] - repl) * P[k]["gp"] / 82 for k in v}

    fl = floor_scores(punt)
    rank = {k: i + 1 for i, k in enumerate(sorted(fl, key=lambda k: -fl[k]))}

    def contrib(pid):
        p = P.get(pid)
        if p is None or p.get("np"):
            return np.zeros(len(cats))
        return np.array([p["z"][c] for c in cats]) * p["gp"] / 82

    strength = {t: sum((contrib(pid) for pid in picks.loc[picks.fantasy_team == t, "player_id"]), np.zeros(len(cats))) for t in teams}
    sig = np.array([SIGMA[c] for c in cats])
    rows = []
    for t in teams:
        cw = mw = 0.0
        for o in teams:
            if o == t:
                continue
            pw = 0.5 * (1 + np.vectorize(math.erf)((strength[t] - strength[o]) / (sig * math.sqrt(2))))
            cw += pw.sum()
            mw += win_prob_5of9(pw)
        rows.append((t, mw / (n_teams - 1), cw / (n_teams - 1)))
    print(f"{n_teams} teams, {rounds} rounds. Simulated weekly matchup win rate:")
    for t, mw, cw in sorted(rows, key=lambda r: -r[1]):
        print(f"  {t[:30]:30s} {100 * mw:5.1f}%  ({cw:.2f} of 9 categories){'   <- you' if t == a.team else ''}")

    print(f"\nYour category strength and league rank (punting: {', '.join(LABEL.get(c, c) for c in punt) or 'nothing'}):")
    for i, c in enumerate(cats):
        vals = sorted([strength[t][i] for t in teams], reverse=True)
        print(f"  {LABEL.get(c, c):5s} {strength[a.team][i]:+6.2f}  rank {vals.index(strength[a.team][i]) + 1}/{n_teams}")

    print("\nYour picks vs the board's best available at that moment:")
    taken = set()
    for _, r in picks.iterrows():
        if r["fantasy_team"] == a.team:
            avail = sorted((k for k in fl if k not in taken), key=lambda k: -fl[k])
            pid = r["player_id"]
            v = fl.get(pid)
            vs = f"{v:5.1f}" if v is not None else "  n/a"
            print(f"  #{r['overall']:<4} {str(r['player']):22s} {vs}  (rank {rank.get(pid, '-')}, ADP {P.get(pid, {}).get('adp')})  | board top: "
                  + ", ".join(f"{P[k]['name']} {fl[k]:.1f}" for k in avail[:3]))
        taken.add(r["player_id"])

    und = sorted((k for k in fl if k not in taken), key=lambda k: -fl[k])[:6]
    print("\nBest undrafted:", ", ".join(f"{P[k]['name']} {P[k]['team']} ({fl[k]:.1f})" for k in und))


if __name__ == "__main__":
    main()
