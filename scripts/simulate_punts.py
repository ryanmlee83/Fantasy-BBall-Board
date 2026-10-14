"""Which punt wins the most from each draft slot? Monte Carlo over the real draft.

Tests Ryan's hypothesis (2026-09-11) that the right punt depends on draft
position. For every slot 1-12 and every build (balanced, each single-category
punt, and the three named pairs), simulate the whole 12-team, 13-round snake:

  * the 11 other teams draft by Yahoo ADP with noise -- each sim draws a
    noisy order once (ADP x lognormal(0, 0.18) + N(0, 2)), and the same draws
    are reused across slots and builds so the comparison isn't drowned in
    noise (common random numbers). Players outside the ADP list are ranked
    after it by per-game value. Rookies without a projection are drafted by
    ADP like anyone else and score zero for whoever takes them.
  * "you" draft greedily by the board's Floor score for that build (value
    above replacement x GP/82, punted categories excluded), keeping enough
    picks back to fill every starting slot.

Each finished roster is scored against a simulated "true" season, not the
projections it was drafted from: every player's per-game Z is perturbed by
the backtest's typical error (sd 0.45 per category) and his games played by
the GP model's (sd 15), so a build that only looks good inside the model is
not rewarded for it. Then rosters are scored the way H2H weeks are won. Team strength in a
category is the sum of its players' per-game Z x GP/82. Against each of the
11 opponents, P(win category) = Phi(diff / sigma_cat), where sigma_cat is the
week-to-week noise in the same units (2.5 for PTS/REB/AST up to 5 for STL,
from game-to-game variance over ~35 player-games a week). The weekly matchup
is won with 5+ categories; that probability comes from the exact distribution
of the nine category results.

Outputs reports/punt_by_slot.csv and reports/punt_by_slot.json (embedded in
the draft board). It answers "which build, from which slot" against a field
that drafts by ADP. It is a model of the field, not of these 11 managers.

Usage: python scripts/simulate_punts.py [--sims 150]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "reports" / "board_data.json"
OUT_CSV = ROOT / "reports" / "punt_by_slot.csv"
OUT_JSON = ROOT / "reports" / "punt_by_slot.json"

TEAMS, ROUNDS = 12, 13
CATS = ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV", "FG_IMPACT", "FT_IMPACT"]
SIGMA = {"PTS": 2.5, "REB": 2.5, "AST": 2.5, "STL": 5.0, "BLK": 4.5, "3PM": 3.5,
         "TOV": 3.5, "FG_IMPACT": 4.0, "FT_IMPACT": 4.0}
Z_ERROR_SD = 0.45
GP_ERROR_SD = 15.0
BUILDS = [[]] + [[c] for c in CATS] + [["FT_IMPACT", "TOV"], ["FG_IMPACT", "3PM"], ["BLK", "FG_IMPACT"]]
START_SLOTS = ["PG", "SG", "G", "SF", "PF", "F", "C", "C", "UTIL", "UTIL"]
ELIG = {"PG": {"PG", "G", "UTIL"}, "SG": {"SG", "G", "UTIL"}, "SF": {"SF", "F", "UTIL"},
        "PF": {"PF", "F", "UTIL"}, "C": {"C", "UTIL"}}


def label(build: list[str]) -> str:
    short = {"FG_IMPACT": "FG%", "FT_IMPACT": "FT%", "TOV": "TO", "STL": "ST", "3PM": "3PTM"}
    return "Balanced" if not build else "Punt " + " + ".join(short.get(c, c) for c in build)


def my_picks(slot: int) -> list[int]:
    return [(r - 1) * TEAMS + slot if r % 2 else r * TEAMS - slot + 1 for r in range(1, ROUNDS + 1)]


def owner_of(pick: int) -> int:
    r = (pick - 1) // TEAMS + 1
    i = (pick - 1) % TEAMS
    return i + 1 if r % 2 else TEAMS - i


def match_size(fits: list[set[str]]) -> int:
    owner = [None] * len(START_SLOTS)

    def go(k: int, seen: list[bool]) -> bool:
        for i, s in enumerate(START_SLOTS):
            if s in fits[k] and not seen[i]:
                seen[i] = True
                if owner[i] is None or go(owner[i], seen):
                    owner[i] = k
                    return True
        return False

    return sum(go(k, [False] * len(START_SLOTS)) for k in range(len(fits)))


def win_matchup_prob(p: np.ndarray) -> float:
    """P(win >= 5 of 9 categories) for independent category win probs p."""
    dist = np.zeros(len(p) + 1)
    dist[0] = 1.0
    for q in p:
        dist[1:] = dist[1:] * (1 - q) + dist[:-1] * q
        dist[0] *= (1 - q)
    return float(dist[5:].sum())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=150)
    ap.add_argument("--seed", type=int, default=20261015)
    args = ap.parse_args()

    board = json.loads(BOARD.read_text(encoding="utf-8"))
    players = board["players"]
    n = len(players)
    proj = np.array([not p.get("np") for p in players])
    Z = np.array([[p["z"][c] if not p.get("np") else 0.0 for c in CATS] for p in players])
    gp = np.array([p.get("gp", 0) if not p.get("np") else 0 for p in players], dtype=float)
    avail_w = gp / 82.0
    contrib = Z * avail_w[:, None]  # what a player adds to a team's category strength
    fits = []
    for p in players:
        s = set()
        for x in p.get("pos") or []:
            s |= ELIG.get(x, {"UTIL"})
        fits.append(s or {"UTIL"})

    # ADP used for the field: Yahoo, else consensus, else after everyone by per-game value
    pg_value = Z.sum(axis=1)
    adp = np.array([p.get("adp") if p.get("adp") is not None else (p.get("adpAvg") or np.nan) for p in players], dtype=float)
    no_adp = np.isnan(adp)
    order_rest = np.argsort(-pg_value[no_adp])
    rest_rank = np.empty(no_adp.sum())
    rest_rank[order_rest] = np.arange(no_adp.sum())
    adp[no_adp] = 210 + rest_rank

    # board scores per build (Floor mode), mirroring the page
    pool_n = board["poolSize"]
    scores = []
    for b in BUILDS:
        keep = [i for i, c in enumerate(CATS) if c not in b]
        v = Z[:, keep].sum(axis=1)
        v_proj = np.sort(v[proj])[::-1]
        repl = v_proj[min(pool_n, len(v_proj)) - 1]
        s = (v - repl) * avail_w
        s[~proj] = -1e9  # the board never recommends an unprojected player
        scores.append(s)

    rng = np.random.default_rng(args.seed)
    sims = args.sims
    orders, truths = [], []
    for _ in range(sims):
        key = adp * np.exp(rng.normal(0, 0.18, n)) + rng.normal(0, 2.0, n)
        orders.append(np.argsort(key))
        # what actually happens this season: projections are wrong by about the
        # backtest error (~0.45 Z per category) and games played are wrong by
        # about the GP backtest MAE (sd 15 games), clipped to a season
        z_true = Z + rng.normal(0, Z_ERROR_SD, Z.shape)
        gp_true = np.clip(gp + rng.normal(0, GP_ERROR_SD, n), 0, 82)
        truths.append(z_true * (gp_true / 82.0)[:, None])

    sig = np.array([SIGMA[c] for c in CATS])
    results = {}  # (slot, build_idx) -> list of (cats_won, matchup_win)
    for slot in range(1, TEAMS + 1):
        mine = set(my_picks(slot))
        for bi, b in enumerate(BUILDS):
            sc = scores[bi]
            cw, mw = [], []
            for s in range(sims):
                taken = np.zeros(n, dtype=bool)
                rosters = {t: [] for t in range(1, TEAMS + 1)}
                order = orders[s]
                ptr = 0
                my_count = 0
                for pick in range(1, TEAMS * ROUNDS + 1):
                    t = owner_of(pick)
                    if pick in mine:
                        my_count += 1
                        cand = np.where(~taken, sc, -np.inf)
                        left = ROUNDS - my_count  # picks after this one
                        cur_fits = [fits[i] for i in rosters[t]]
                        base = match_size(cur_fits) if cur_fits else 0
                        open_slots = len(START_SLOTS) - base
                        top = np.argsort(-cand)[:40]
                        choice = None
                        for i in top:
                            if not np.isfinite(cand[i]):
                                break
                            if open_slots > left:  # must fill a starting slot now
                                if match_size(cur_fits + [fits[i]]) <= base:
                                    continue
                            choice = i
                            break
                        if choice is None:
                            choice = int(top[0])
                    else:
                        while taken[order[ptr]]:
                            ptr += 1
                        choice = order[ptr]
                    taken[choice] = True
                    rosters[t].append(int(choice))
                truth = truths[s]
                team_str = {t: truth[r].sum(axis=0) for t, r in rosters.items()}
                me = team_str[slot]
                cats_won, match_win = 0.0, 0.0
                for t, opp in team_str.items():
                    if t == slot:
                        continue
                    pwin = 0.5 * (1 + np.vectorize(math.erf)((me - opp) / (sig * math.sqrt(2))))
                    cats_won += pwin.sum()
                    match_win += win_matchup_prob(pwin)
                cw.append(cats_won / (TEAMS - 1))
                mw.append(match_win / (TEAMS - 1))
            results[(slot, bi)] = (float(np.mean(cw)), float(np.mean(mw)), float(np.std(mw) / math.sqrt(sims)))
        print(f"slot {slot:2d} done: best = {label(BUILDS[max(range(len(BUILDS)), key=lambda k: results[(slot, k)][1])])}")

    rows = []
    for (slot, bi), (cw, mw, se) in results.items():
        rows.append({"slot": slot, "build": label(BUILDS[bi]), "punt": BUILDS[bi],
                     "cats_won": round(cw, 2), "matchup_win": round(mw, 3), "se": round(se, 3)})
    OUT_JSON.write_text(json.dumps({"sims": sims, "builds": [label(b) for b in BUILDS], "rows": rows}), encoding="utf-8")
    import csv
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["slot", "build", "cats_won", "matchup_win", "se"])
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["slot"], -r["matchup_win"])):
            w.writerow({k: r[k] for k in ["slot", "build", "cats_won", "matchup_win", "se"]})
    print(f"wrote {OUT_CSV} and {OUT_JSON}")


if __name__ == "__main__":
    main()
