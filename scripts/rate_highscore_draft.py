"""Rate a High Score draft: the board's value at each of your picks, and a
Monte Carlo of weekly H2H matchups between every drafted roster.

Valuation mirrors board/highscore_board.html exactly (weights, game-score
mean and swing, best-of-week, replacement = 100th player, GP/82 for Floor).
Season sim: each week a player is healthy with probability GP/82, his team
plays 2-5 games (3 or 4 in most weeks), the lineup is set from healthy
players by expected best game (G, G, FC, FC, FC, Util), and each starter
scores his best of n simulated games. Unprojected rookies are played as
replacement-level players.

Usage: python scripts/rate_highscore_draft.py drafts/<picks.csv> "<your team name>"
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
W = {"PTS": 1, "REB": 1, "AST": 2, "STL": 3, "BLK": 3}
WEEK_GAMES = [(2, .04), (3, .48), (4, .44), (5, .04)]
EMAX = {1: 0, 2: .5642, 3: .8463, 4: 1.0294, 5: 1.1630}
E_BEST = sum(p * EMAX[n] for n, p in WEEK_GAMES)
SLOTS = ["G", "G", "FC", "FC", "FC", "UTIL"]
ELIG = {"PG": {"G", "UTIL"}, "SG": {"G", "UTIL"}, "SF": {"FC", "UTIL"}, "PF": {"FC", "UTIL"}, "C": {"FC", "UTIL"}}


def game_model(s):
    mu = sum(W[k] * s[k] for k in W)
    v = W["PTS"] ** 2 * 2.2 * s["PTS"] + sum(W[k] ** 2 * s[k] for k in ["REB", "AST", "STL", "BLK"]) + (0.15 * mu) ** 2
    sd = math.sqrt(v)
    return mu, sd, mu + sd * E_BEST


def main():
    picks = pd.read_csv(sys.argv[1])
    me = sys.argv[2]
    board = json.loads((ROOT / "reports" / "board_data.json").read_text())
    P = {p["id"]: p for p in board["players"]}
    proj = [p for p in board["players"] if not p.get("np")]
    gm = {p["id"]: game_model(p["s"]) for p in proj}
    bests = sorted((g[2] for g in gm.values()), reverse=True)
    repl = bests[99]
    floor = {k: (g[2] - repl) * min(P[k]["gp"], 82) / 82 for k, g in gm.items()}
    rank = {k: i + 1 for i, k in enumerate(sorted(floor, key=lambda k: -floor[k]))}
    repl_mu, repl_sd = next((g[0], g[1]) for g in sorted(gm.values(), key=lambda g: -g[2])[99:100])

    # 1. your picks vs the board's best available at the time (Floor, default scoring)
    taken = set()
    print("Your picks vs the board's best available at that moment:")
    for _, r in picks.iterrows():
        if r["fantasy_team"] == me:
            avail = sorted((k for k in floor if k not in taken), key=lambda k: -floor[k])
            v = floor.get(r["player_id"], float("nan"))
            top = ", ".join(f"{P[k]['name']} {floor[k]:.1f}" for k in avail[:3])
            print(f"  #{r['overall']:<3} {r['player']:22s} {v:5.1f} (board rank {rank.get(r['player_id'], '-')}, ADP {P[r['player_id']].get('adp')})  | board top: {top}")
        taken.add(r["player_id"])

    # 2. season sim
    rng = np.random.default_rng(7)
    teams = list(dict.fromkeys(picks["fantasy_team"]))
    roster = {t: picks.loc[picks["fantasy_team"] == t, "player_id"].tolist() for t in teams}

    def info(pid):
        p = P[pid]
        if pid in gm:
            mu, sd, best = gm[pid]
            return mu, sd, best, min(p["gp"], 82) / 82
        return repl_mu, repl_sd, repl_mu + repl_sd * E_BEST, 0.8

    def fits(pid):
        s = set()
        for x in P[pid].get("pos") or []:
            s |= ELIG.get(x, {"UTIL"})
        return s or {"UTIL"}

    def lineup(ids):
        ids = sorted(ids, key=lambda k: -info(k)[2])
        owner = [None] * len(SLOTS)

        def go(k, seen):
            for i, sl in enumerate(SLOTS):
                if sl in fits(k) and not seen[i]:
                    seen[i] = True
                    if owner[i] is None or go(owner[i], seen):
                        owner[i] = k
                        return True
            return False
        for k in ids:
            go(k, [False] * len(SLOTS))
        return [o for o in owner if o]

    WEEKS = 3000
    ns, probs = zip(*WEEK_GAMES)
    scores = {}
    for t in teams:
        ids = roster[t]
        inf = {k: info(k) for k in ids}
        out = np.zeros(WEEKS)
        for w in range(WEEKS):
            healthy = [k for k in ids if rng.random() < inf[k][3]]
            tot = 0.0
            for k in lineup(healthy):
                n = rng.choice(ns, p=probs)
                tot += max(0.0, rng.normal(inf[k][0], inf[k][1], n).max())
            out[w] = tot
        scores[t] = out
    print("\nTeam            weekly matchup win%   avg weekly score   starters' healthy-week ceiling")
    rows = []
    for t in teams:
        win = np.mean([np.mean(scores[t] > scores[o]) for o in teams if o != t])
        ceil = sum(info(k)[2] for k in lineup(roster[t]))
        rows.append((t, win, scores[t].mean(), ceil))
    for t, win, avg, ceil in sorted(rows, key=lambda r: -r[1]):
        print(f"  {t[:30]:30s} {100 * win:5.1f}%   {avg:6.0f}   {ceil:6.0f}{'   <- you' if t == me else ''}")
    print("\nYour roster: GP and best-game value")
    for k in roster[me]:
        mu, sd, best, p = info(k)
        print(f"  {P[k]['name']:22s} avg {mu:5.1f}  best wk {best:5.1f}  gp {P[k].get('gp')}  healthy {100 * p:3.0f}%  {P[k].get('inj', '')[:60]}")


if __name__ == "__main__":
    main()
