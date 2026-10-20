"""Scout a 9-cat H2H league from its draft: simulate weekly matchups between every pair of teams.

Usage:
  python scripts/scout_league.py drafts/<id>_picks.csv "<my team>" --out reports/scout_<id>.json
      [--add "Mitchell Robinson"] [--drop "Brandon Ingram"]            # my current roster vs the draft
      [--out-player "Kevin Porter Jr."]                                 # released players on other teams
      [--variant "Dunn for Carter=+Kris Dunn;-Wendell Carter Jr."]      # what-if rosters for my team

Unlike scripts/rate_draft.py (sum of Z scores, fixed noise per category), this simulates raw
weekly box-score totals, so FG% and FT% come from makes and attempts and every category has
realistic week-to-week noise:

  * each NBA team plays 2-5 games a week (mean 3.5); teammates share the draw
  * each player is healthy for a week with probability GP/82 (projected games), and then plays
    every team game that week; absences come in whole weeks, as real injuries do
  * per game, minutes vary (one factor per player-week scales every stat, so a short-minutes
    week is short in every category); counting stats are Poisson, points carry extra spread,
    makes are binomial on attempts
  * a week a player misses is backfilled, with probability --backfill (default 0.5), by a
    waiver-level player: the average of the 40 best undrafted players. With 3 IL slots and
    3 adds a week, managers replace long injuries; short ones mostly go unfilled. Scoring a
    missed week as zero overrates healthy rosters; scoring it as an average player (what
    rate_draft.py effectively does, via Z x GP/82) overrates injured ones
  * the 11 daily starting slots are not modelled: with 13 players and about 3.5 games each, a
    team rarely has more than 11 players in action on one night

Veteran minutes fix (analysis only, until the board pipeline is fixed): the board's rule that
trims aging starters needs two straight seasons under 31 mpg, so a 31+ starter with one sharp
drop keeps the flat depth-chart 33 (Brook Lopez: 31.8 then 21.8 at 37). Here, any player at
exactly 33.0 mpg, aged 31+, whose latest 20-game season is under 30 mpg gets 0.6 x latest +
0.4 x prior instead, with his per-game counting stats and attempts scaled to match.

Unprojected 2026 rookies get a stand-in: the average stat line of projected players at the
same position group with an ADP within 12 spots of his. Released players (--out-player) are
replaced by the average of the ten best undrafted players, which is roughly who their manager
would pick up. Ties in a category count half.

Yahoo "Head-to-Head - Categories" counts every category in the standings, so the headline
number is expected categories won per week; the chance of winning a majority is reported too.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATS = ["FG%", "FT%", "3PM", "PTS", "REB", "AST", "STL", "BLK", "TO"]
LOWER_IS_BETTER = {"TO"}
GAMES_P = np.array([0.05, 0.42, 0.48, 0.05])     # 2, 3, 4, 5 games in a week
PTS_K = 14.0                                     # per-game points variance = mu + mu^2 / k
MIN_SD = 0.15                                    # per-game minutes factor spread


def pos_group(pos):
    return "big" if "C" in pos else "wing" if ("SF" in pos or "PF" in pos) else "guard"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("picks")
    ap.add_argument("my_team")
    ap.add_argument("--out", required=True)
    ap.add_argument("--add", action="append", default=[])
    ap.add_argument("--drop", action="append", default=[])
    ap.add_argument("--out-player", action="append", default=[])
    ap.add_argument("--variant", action="append", default=[])
    ap.add_argument("--weeks", type=int, default=6000)
    ap.add_argument("--backfill", type=float, default=0.5)
    ap.add_argument("--mpg", action="append", default=[], help='minutes override, e.g. "Jake LaRavia=24": scales his per-game stats')
    ap.add_argument("--replace", action="append", default=[], help="my players a free agent could replace (default: lowest board value)")
    ap.add_argument("--seed", type=int, default=20261020)
    a = ap.parse_args()

    board = json.loads((ROOT / "reports" / "board_data.json").read_text(encoding="utf-8"))
    P = {p["id"]: p for p in board["players"]}
    by_name = {p["name"]: p for p in board["players"]}
    picks = pd.read_csv(a.picks).sort_values("overall")
    teams = list(dict.fromkeys(picks["fantasy_team"]))
    rosters = {t: list(picks.loc[picks.fantasy_team == t, "player_id"]) for t in teams}
    drafted = set(picks.player_id)
    slot = {t: int(picks.loc[picks.fantasy_team == t, "overall"].min()) for t in teams}

    hist = defaultdict(dict)
    for r in csv.DictReader(open(ROOT / "data" / "canonical" / "player_seasons.csv", encoding="utf-8")):
        hist[r["player_id"]][r["season"]] = int(float(r["g"]))
    seasons = sorted({s for h in hist.values() for s in h})

    proj = [p for p in board["players"] if not p.get("np") and p.get("s")]
    pool = len(picks)
    zsum = {p["id"]: sum(p["z"].values()) for p in proj}
    repl = sorted(zsum.values(), reverse=True)[pool - 1]
    value = {k: (v - repl) * P[k]["gp"] / 82 for k, v in zsum.items()}

    # stat lines (per game) for everyone we might simulate
    mpg_hist = defaultdict(dict)
    for r in csv.DictReader(open(ROOT / "data" / "canonical" / "player_seasons.csv", encoding="utf-8")):
        if float(r["g"]) >= 20:
            mpg_hist[r["player_id"]][r["season"]] = float(r["mpg"])
    line, notes, mpg_used = {}, {}, {}
    for p in proj:
        line[p["id"]] = dict(p["s"], gp=p["gp"], team=p["team"])
        mpg_used[p["id"]] = p["mpg"]
        hs = [mpg_hist[p["id"]][x] for x in ["2025-26", "2024-25", "2023-24"] if x in mpg_hist[p["id"]]][:2]
        if abs(p["mpg"] - 33.0) < 1e-9 and p["age"] >= 31 and hs and hs[0] < 30:
            new_mpg = round(0.6 * hs[0] + 0.4 * hs[1], 1) if len(hs) == 2 else round(hs[0], 1)
            f = new_mpg / 33.0
            for k in ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV", "FGA", "FTA"]:
                line[p["id"]][k] = p["s"][k] * f
            mpg_used[p["id"]] = new_mpg
            notes[p["id"]] = f"minutes cut from the flat 33 to {new_mpg} (veteran with a recent drop: {', '.join(f'{x:.1f}' for x in hs)} mpg)"
    for pid in drafted:
        p = P[pid]
        if pid in line:
            continue
        adp = p.get("adp") or p.get("adpAvg") or 150
        grp = pos_group(p["pos"])
        peers = [q for q in proj if q.get("adp") and abs(q["adp"] - adp) <= 12 and pos_group(q["pos"]) == grp]
        keys = ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV", "FGA", "FTA"]
        st = {k: float(np.mean([q["s"][k] for q in peers])) for k in keys}
        fgm = np.mean([q["s"]["FGP"] * q["s"]["FGA"] for q in peers])
        ftm = np.mean([q["s"]["FTP"] * q["s"]["FTA"] for q in peers])
        st["FGP"], st["FTP"] = fgm / st["FGA"], ftm / st["FTA"]
        line[pid] = dict(st, gp=float(np.mean([q["gp"] for q in peers])), team=p["team"])
        notes[pid] = f"rookie stand-in: average of {len(peers)} projected {grp}s with ADP {adp - 12:.0f}-{adp + 12:.0f}"
    for spec in a.mpg:
        nm, m = spec.rsplit("=", 1)
        pid = by_name[nm]["id"]
        f = float(m) / mpg_used[pid]
        for k in ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV", "FGA", "FTA"]:
            line[pid][k] *= f
        notes[pid] = f"minutes set to {m} (was {mpg_used[pid]})"
        mpg_used[pid] = float(m)
    free = sorted([p for p in proj if p["id"] not in drafted], key=lambda p: -value[p["id"]])
    sub_keys = ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV", "FGA", "FTA"]
    top_free = free[:10]
    released_line = {k: float(np.mean([q["s"][k] for q in top_free])) for k in sub_keys}
    released_line["FGP"] = float(np.mean([q["s"]["FGP"] * q["s"]["FGA"] for q in top_free])) / released_line["FGA"]
    released_line["FTP"] = float(np.mean([q["s"]["FTP"] * q["s"]["FTA"] for q in top_free])) / released_line["FTA"]
    released_line["gp"] = float(np.mean([q["gp"] for q in top_free]))
    waiver = free[:40]
    waiver_line = {k: float(np.mean([q["s"][k] for q in waiver])) for k in sub_keys}
    waiver_line["FGP"] = float(np.mean([q["s"]["FGP"] * q["s"]["FGA"] for q in waiver])) / waiver_line["FGA"]
    waiver_line["FTP"] = float(np.mean([q["s"]["FTP"] * q["s"]["FTA"] for q in waiver])) / waiver_line["FTA"]
    for nm in a.out_player:
        pid = by_name[nm]["id"]
        line[pid] = dict(released_line, team="FA")
        notes[pid] = "released by his NBA team; replaced by the average of the ten best undrafted players"

    # my current roster
    me = a.my_team
    for nm in a.drop:
        rosters[me].remove(by_name[nm]["id"])
    for nm in a.add:
        rosters[me].append(by_name[nm]["id"])

    # ---- simulate every player's weekly box score once ----
    rng = np.random.default_rng(a.seed)
    W = a.weeks
    variant_names = [tok[1:] for v in a.variant for tok in v.split("=", 1)[1].split(";") if tok]
    ids = sorted(set(pid for r in rosters.values() for pid in r) | {by_name[nm]["id"] for nm in variant_names}
                 | {p["id"] for p in free[:120]})
    nba_teams = sorted({line[i]["team"] for i in ids})
    games = {t: rng.choice([2, 3, 4, 5], size=W, p=GAMES_P) for t in nba_teams}
    def draw(L, g):
        M = np.clip(g + rng.normal(0, MIN_SD, W) * np.sqrt(g), 0, None)
        out = {"PTS": np.clip(rng.normal(L["PTS"] * M, np.sqrt(g * (L["PTS"] + L["PTS"] ** 2 / PTS_K))), 0, None)}
        for k, c in [("REB", "REB"), ("AST", "AST"), ("STL", "STL"), ("BLK", "BLK"), ("3PM", "3PM"), ("TOV", "TO")]:
            out[c] = rng.poisson(L[k] * M)
        fga, fta = rng.poisson(L["FGA"] * M), rng.poisson(L["FTA"] * M)
        out["FGA"], out["FGM"] = fga, rng.binomial(fga, min(max(L["FGP"], 0), 1))
        out["FTA"], out["FTM"] = fta, rng.binomial(fta, min(max(L["FTP"], 0), 1))
        out["G"] = g
        return out

    stat = {}
    for pid in ids:
        L = line[pid]
        healthy = rng.random(W) < min(L["gp"], 82) / 82
        own = draw(L, games[L["team"]] * healthy)
        filled = (~healthy) & (rng.random(W) < a.backfill)
        sub = draw(waiver_line, rng.choice([2, 3, 4, 5], size=W, p=GAMES_P) * filled)
        stat[pid] = {k: own[k] + sub[k] for k in own}

    RAW = ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TO", "FGA", "FGM", "FTA", "FTM", "G"]

    def totals(roster):
        t = {k: sum(stat[p][k] for p in roster).astype(float) for k in RAW}
        t["FG%"] = np.divide(t["FGM"], t["FGA"], out=np.zeros(W), where=t["FGA"] > 0)
        t["FT%"] = np.divide(t["FTM"], t["FTA"], out=np.zeros(W), where=t["FTA"] > 0)
        return t

    def compare(ta, tb):
        """Per-category win probability for A (ties half), expected cats, P(A wins the week)."""
        won = np.zeros(W)
        per = {}
        for c in CATS:
            x, y = (tb[c], ta[c]) if c in LOWER_IS_BETTER else (ta[c], tb[c])
            w = (x > y) + 0.5 * (x == y)
            per[c] = float(w.mean())
            won += w
        return per, float(won.mean()), float(((won > 4.5) + 0.5 * (won == 4.5)).mean())

    T = {t: totals(rosters[t]) for t in teams}
    n = len(teams)
    exp_cats = np.zeros((n, n))
    p_week = np.zeros((n, n))
    cat_vs = {t: {c: [] for c in CATS} for t in teams}
    pair_cats = {}
    for i, ta in enumerate(teams):
        for j, tb in enumerate(teams):
            if i == j:
                continue
            per, e, pw = compare(T[ta], T[tb])
            exp_cats[i, j], p_week[i, j] = e, pw
            for c in CATS:
                cat_vs[ta][c].append(per[c])
            if ta == me:
                pair_cats[tb] = per

    def summary(t):
        return {
            "means": {c: float(T[t][c].mean()) for c in CATS + ["G"]},
            "cat_win": {c: float(np.mean(cat_vs[t][c])) for c in CATS},
        }

    team_out = []
    for i, t in enumerate(teams):
        s = summary(t)
        roster = []
        for pid in rosters[t]:
            p = P[pid]
            seas_g = [hist[pid][x] for x in seasons if x in hist.get(pid, {})]
            roster.append({
                "name": p["name"], "nba": p["team"], "pos": p["pos"],
                "pick": int(picks.loc[picks.player_id == pid, "overall"].iloc[0]) if pid in drafted else None,
                "gp": round(line[pid]["gp"]), "mpg": mpg_used.get(pid, p.get("mpg")),
                "value": round(value.get(pid, 0), 2) if pid in value and not notes.get(pid, "").startswith(("rookie", "released")) else None,
                "inj": p.get("inj", ""), "note": notes.get(pid, ""),
                "games_hist": seas_g, "added": pid not in drafted,
                "z": {k: round(v, 2) for k, v in p["z"].items()} if p.get("z") else None,
            })
        if t == me:
            for nm in a.drop:
                p = by_name[nm]
                roster.append({"name": p["name"], "nba": p["team"], "pos": p["pos"], "pick": int(picks.loc[picks.player_id == p["id"], "overall"].iloc[0]),
                               "gp": p["gp"], "mpg": p.get("mpg"), "value": round(value.get(p["id"], 0), 2), "inj": p.get("inj", ""),
                               "note": "on IL (not counted)", "games_hist": [], "added": False, "il": True, "z": None})
        team_out.append({
            "name": t, "slot": slot[t], **s,
            "exp_cats_vs_field": float(np.mean([exp_cats[i, j] for j in range(n) if j != i])),
            "p_week_vs_field": float(np.mean([p_week[i, j] for j in range(n) if j != i])),
            "roster": sorted(roster, key=lambda r: r["pick"] or 999),
        })
    for c in CATS:
        order = sorted(team_out, key=lambda x: x["means"][c], reverse=c not in LOWER_IS_BETTER)
        for rank, x in enumerate(order, 1):
            x.setdefault("rank", {})[c] = rank

    # what-if rosters for my team
    variants = []
    base_me = T[me]
    for v in a.variant:
        label, spec = v.split("=", 1)
        r = list(rosters[me])
        for tok in spec.split(";"):
            pid = by_name[tok[1:]]["id"]
            (r.append if tok[0] == "+" else r.remove)(pid)
        tv = totals(r)
        rows = {}
        for tb in teams:
            if tb == me:
                continue
            per, e, pw = compare(tv, T[tb])
            rows[tb] = {"exp_cats": e, "p_week": pw, "per": per}
        variants.append({"label": label, "spec": spec, "vs": rows,
                         "exp_cats_vs_field": float(np.mean([x["exp_cats"] for x in rows.values()])),
                         "p_week_vs_field": float(np.mean([x["p_week"] for x in rows.values()]))})

    # best undrafted players for my team, against each player they could replace
    my_active = rosters[me]
    # "OPEN" means an empty active spot (a player just moved to IL): the free agent is a pure add
    targets = [None if nm == "OPEN" else by_name[nm]["id"] for nm in a.replace] or [min(my_active, key=lambda pid: value.get(pid, -99))]
    base_e = np.mean([exp_cats[teams.index(me), j] for j in range(n) if teams[j] != me])
    fa = []
    for p in free[:120]:
        if mpg_used[p["id"]] < 15:
            continue
        seas_g = [hist[p["id"]][x] for x in seasons if x in hist.get(p["id"], {})]
        gains = {}
        for t_id in targets:
            tv = totals([x for x in my_active if x != t_id] + [p["id"]])
            gains["open spot" if t_id is None else P[t_id]["name"]] = float(np.mean([compare(tv, T[tb])[1] for tb in teams if tb != me]) - base_e)
        best = max(gains, key=gains.get)
        fa.append({"name": p["name"], "nba": p["team"], "pos": p["pos"], "gp": p["gp"], "mpg": mpg_used[p["id"]], "note": notes.get(p["id"], ""),
                   "adp": p.get("adp"), "inj": p.get("inj", ""), "games_hist": seas_g, "gain": gains[best],
                   "replace": best, "gains": gains, "z": {k: round(v, 2) for k, v in p["z"].items()}})
    fa.sort(key=lambda x: -x["gain"])

    out = {
        "league": "Zalgiris 260146", "my_team": me, "weeks_simulated": W, "cats": CATS,
        "teams": team_out,
        "matrix": {"teams": teams, "exp_cats": exp_cats.round(3).tolist(), "p_week": p_week.round(3).tolist()},
        "my_matchups": {tb: {"exp_cats": float(exp_cats[teams.index(me), teams.index(tb)]),
                             "p_week": float(p_week[teams.index(me), teams.index(tb)]),
                             "per": pair_cats[tb]} for tb in teams if tb != me},
        "variants": variants,
        "free_agents": {"targets": ["open spot" if t is None else P[t]["name"] for t in targets], "list": fa[:40]},
        "backfill": a.backfill,
        "notes": notes,
    }
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---- console summary ----
    print(f"{W} simulated weeks. Expected categories won per week vs the field (of 9), and chance of winning the week:")
    for x in sorted(team_out, key=lambda x: -x["exp_cats_vs_field"]):
        ranks = " ".join(f"{c}:{x['rank'][c]:>2}" for c in CATS)
        print(f"  {x['name'][:26]:26} {x['exp_cats_vs_field']:.2f}  {x['p_week_vs_field']:.0%}   {ranks}")
    print(f"\n{me} vs each opponent:")
    for tb, m in sorted(out["my_matchups"].items(), key=lambda kv: kv[1]["exp_cats"]):
        fav = [c for c in CATS if m["per"][c] >= .6]
        dog = [c for c in CATS if m["per"][c] <= .4]
        print(f"  {tb[:26]:26} {m['exp_cats']:.2f}-{9 - m['exp_cats']:.2f}  win week {m['p_week']:.0%}  | yours: {','.join(fav)} | theirs: {','.join(dog)}")
    for v in variants:
        print(f"\nvariant {v['label']}: {v['exp_cats_vs_field']:.2f} cats/week, win week {v['p_week_vs_field']:.0%}")
    print("\nbest undrafted players (gain in categories per week vs the field, by player replaced):")
    for f in fa[:25]:
        g = " ".join(f"{k.split()[-1][:7]} {v:+.3f}" for k, v in f["gains"].items())
        print(f"  {f['name'][:22]:22} {f['nba']} {'/'.join(f['pos']):9} | {g} | gp {f['gp']} mpg {f['mpg']} games {f['games_hist']} {('INJ ' + f['inj'][:40]) if f['inj'] else ''}")


if __name__ == "__main__":
    main()
