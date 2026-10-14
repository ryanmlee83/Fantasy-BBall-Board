"""Apply the standing starter-minutes rule to config/minutes.yaml.

The depth-chart allocator (scripts/apply_depth_minutes.py) gives every starter
a flat 33 mpg. That flattens the top of the board: it trims stars who reliably
play 35-37 and pads aging starters on managed minutes. The rule Ryan set while
reviewing the Lakers (2026-09-12) was to check each starter's own history
against the flat value and override when the history is a *stable, multi-
season* outlier, pulling the difference from the same team's bench so the team
total does not change. This script applies that rule mechanically to the 29
generated teams; the Lakers are hand-reviewed and left alone.

For each player at exactly 33.0 mpg (a depth-chart starter):
  * take the two most recent seasons in the 2023-24..2025-26 window with 20+ games
  * UP:   both seasons >= 33.5 mpg -> mpg = 0.6*recent + 0.4*prior, capped at 37
  * DOWN: both seasons <= 31.0 mpg and age >= 31 -> same blend, floored at 26
  * PROMOTED: recent-history mpg (0.6*recent + 0.4*prior, or the one season
    there is) below 30 and age < 31 -> halfway between that history and 33,
    floored at 24. A depth chart that names a 20-mpg backup the new starter is
    real information, but projecting him straight to 33 extrapolates per-100
    rates earned in a bench role to starter minutes, and flat-33 starters were
    the bulk of the model's suspicious risers (Ty Jerome ranked 6th overall at
    ADP 121, Cam Spencer 23rd unranked). Added 2026-10-14.
  * otherwise unchanged. For UP and DOWN one season is never enough (Walker
    Kessler's one-year jump was the cautionary case).
Each team's net change is absorbed by its bench players (0 < mpg < 33),
proportional to their minutes, so the team's total minutes are preserved.

Usage: python scripts/adjust_starter_minutes.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "data" / "canonical"
CONFIG = ROOT / "config"
REPORTS = ROOT / "reports"

FLAT_STARTER = 33.0
UP_THRESHOLD, UP_CAP = 33.5, 37.0
DOWN_THRESHOLD, DOWN_FLOOR, DOWN_MIN_AGE = 31.0, 26.0, 31
PROMO_THRESHOLD, PROMO_FLOOR, PROMO_MAX_AGE = 30.0, 24.0, 31
HAND_REVIEWED_TEAMS = {"LAL"}
SEASONS = ["2025-26", "2024-25", "2023-24"]


def main() -> None:
    path = CONFIG / "minutes.yaml"
    raw = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    minutes = doc["minutes"]

    rosters = pd.read_csv(CANON / "rosters_2627.csv").dropna(subset=["player_id"])
    team_of = dict(zip(rosters["player_id"], rosters["team"]))
    age_of = dict(zip(rosters["player_id"], rosters["age_at_season_start"]))
    ps = pd.read_csv(CANON / "player_seasons.csv")
    ps = ps[(ps["g"] >= 20) & ps["season"].isin(SEASONS)]
    hist = {pid: g.set_index("season")["mpg"] for pid, g in ps.groupby("player_id")}

    original = {pid: e["mpg"] for pid, e in minutes.items()}
    changes = []
    for pid, entry in minutes.items():
        team = team_of.get(pid)
        if team is None or team in HAND_REVIEWED_TEAMS or abs(entry["mpg"] - FLAT_STARTER) > 1e-9:
            continue
        h = hist.get(pid)
        if h is None:
            continue
        played = [s for s in SEASONS if s in h.index][:2]
        if not played:
            continue
        recent = float(h[played[0]])
        prior = float(h[played[1]]) if len(played) == 2 else None
        blend = 0.6 * recent + 0.4 * prior if prior is not None else recent
        age = age_of.get(pid, 0)
        new = None
        if prior is not None and recent >= UP_THRESHOLD and prior >= UP_THRESHOLD:
            new = min(blend, UP_CAP)
        elif prior is not None and recent <= DOWN_THRESHOLD and prior <= DOWN_THRESHOLD and age >= DOWN_MIN_AGE:
            new = max(blend, DOWN_FLOOR)
        elif blend < PROMO_THRESHOLD and age < PROMO_MAX_AGE:
            new = max(0.5 * (blend + FLAT_STARTER), PROMO_FLOOR)
        if new is not None:
            new = round(new, 1)
            changes.append({"player_id": pid, "team": team, "role": "starter", "old_mpg": FLAT_STARTER,
                            "new_mpg": new, "hist": f"{played[0]} {recent:.1f}" + (f", {played[1]} {prior:.1f}" if prior is not None else "")})

    by_team: dict[str, float] = {}
    for c in changes:
        by_team[c["team"]] = by_team.get(c["team"], 0.0) + (c["new_mpg"] - c["old_mpg"])
        minutes[c["player_id"]]["mpg"] = c["new_mpg"]

    for team, delta in by_team.items():
        # bench = non-starters by their ORIGINAL allocation, so a starter this
        # script just moved below 33 is never rescaled a second time
        bench = [pid for pid in minutes
                 if team_of.get(pid) == team and 0 < original[pid] < FLAT_STARTER]
        pool = sum(minutes[p]["mpg"] for p in bench)
        if pool <= 0:
            continue
        scale = max(0.0, (pool - delta) / pool)
        for p in bench:
            old = minutes[p]["mpg"]
            new = round(old * scale, 1)
            minutes[p]["mpg"] = new
            changes.append({"player_id": p, "team": team, "role": "bench", "old_mpg": old,
                            "new_mpg": new, "hist": f"team starter net {delta:+.1f}"})

    newline = "\r\n" if "\r\n" in raw else "\n"
    body = yaml.safe_dump(doc, sort_keys=True).replace("\n", newline)
    path.write_bytes(body.encode("utf-8"))

    out = pd.DataFrame(changes)
    REPORTS.mkdir(exist_ok=True)
    out.to_csv(REPORTS / "starter_minutes_adjustments.csv", index=False)
    starters = out[out["role"] == "starter"] if len(out) else out
    print(f"starters adjusted: {len(starters)} "
          f"(up {int((starters['new_mpg'] > FLAT_STARTER).sum())}, down/promoted {int((starters['new_mpg'] < FLAT_STARTER).sum())}); "
          f"bench rows rescaled: {len(out) - len(starters)} across {len(by_team)} teams")


if __name__ == "__main__":
    main()
