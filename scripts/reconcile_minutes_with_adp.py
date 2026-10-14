"""Catch depth-chart minutes that are stale for fantasy-relevant players.

The minutes in config/minutes.yaml come from a RealGM depth-chart capture taken
2026-09-21. Rosters were refreshed from Basketball Reference on 2026-10-08, and
the two disagree for players who were hurt, moved, or simply missing on the
day of the capture. On 2026-10-14, checking the board against ADP found the
damage: Tyrese Haliburton (ADP 12), Kyrie Irving and Damian Lillard at 0 mpg;
Trae Young at 13; Jaylen Brown at 15; LaMelo Ball at 19; Kawhi Leonard at 22.

Rule: for a player the fantasy market drafts (FantasyPros average ADP <= 160),
if his configured minutes sit more than 6 below his own recent history
(0.6 * last season + 0.4 * the one before, seasons with 20+ games), raise him
toward that history (capped at 36): all the way for ADP <= 60, sliding to
halfway at ADP 160, since a later pick is weaker evidence of a full role. Being drafted that early is evidence he is in a
rotation; his history is the best available estimate of how much. Each team's
added minutes are taken back from its players the market doesn't draft, in
proportion to their minutes, so the team still sums to the same total.

The Lakers are skipped: Ryan reviewed them by hand and hand review outranks a
generated value (Bronny James at 0 mpg is his call, ADP notwithstanding).

Usage: python scripts/reconcile_minutes_with_adp.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import draft  # noqa: E402  (reuses the ADP -> player_id matcher)

CANON = ROOT / "data" / "canonical"
CONFIG = ROOT / "config"
REPORTS = ROOT / "reports"
ADP_CUTOFF = 160
FULL_TRUST_ADP = 60
GAP = 6.0
CAP = 36.0
HAND_REVIEWED_TEAMS = {"LAL"}
SEASONS = ["2025-26", "2024-25", "2023-24"]


def main() -> None:
    path = CONFIG / "minutes.yaml"
    raw = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    minutes = doc["minutes"]

    rosters = pd.read_csv(CANON / "rosters_2627.csv")
    adp, _ = draft.load_adp(rosters)
    relevant = set(adp.loc[adp["avg_adp"] <= ADP_CUTOFF, "player_id"].dropna())
    adp_of = dict(zip(adp["player_id"], adp["avg_adp"]))

    matched = rosters.dropna(subset=["player_id"]).drop_duplicates("player_id")
    team_of = dict(zip(matched["player_id"], matched["team"]))
    name_of = dict(zip(matched["player_id"], matched["roster_name"]))
    ps = pd.read_csv(CANON / "player_seasons.csv")
    ps = ps[(ps["g"] >= 20) & ps["season"].isin(SEASONS)]
    hist = {pid: g.set_index("season")["mpg"] for pid, g in ps.groupby("player_id")}

    changes = []
    added: dict[str, float] = {}
    for pid in sorted(relevant):
        team = team_of.get(pid)
        if team is None or team in HAND_REVIEWED_TEAMS or pid not in hist:
            continue
        h = hist[pid]
        played = [s for s in SEASONS if s in h.index][:2]
        if not played:
            continue
        hm = 0.6 * h[played[0]] + 0.4 * h[played[1]] if len(played) == 2 else h[played[0]]
        cur = minutes.get(pid, {}).get("mpg", 0.0)
        if cur < hm - GAP:
            # How far to trust history scales with how early the market drafts
            # him: fully by ADP 60 (clear starters), halfway by ADP 160 (bench
            # players whose old role may have shrunk on a new team).
            a = adp_of.get(pid, ADP_CUTOFF)
            w = 1.0 if a <= FULL_TRUST_ADP else 1.0 - 0.5 * (a - FULL_TRUST_ADP) / (ADP_CUTOFF - FULL_TRUST_ADP)
            target = min(float(hm), CAP)
            new = float(round(cur + w * (target - cur), 1))
            minutes.setdefault(pid, {"estimated": False, "mpg": 0.0})
            minutes[pid]["mpg"] = new
            minutes[pid]["estimated"] = False
            added[team] = added.get(team, 0.0) + (new - cur)
            changes.append({"player_id": pid, "player": name_of.get(pid), "team": team, "role": "raised",
                            "adp": adp_of.get(pid), "old_mpg": cur, "new_mpg": new, "history_mpg": round(float(hm), 1)})

    for team, delta in added.items():
        donors = [pid for pid, e in minutes.items()
                  if team_of.get(pid) == team and pid not in relevant and e["mpg"] > 0]
        pool = sum(minutes[p]["mpg"] for p in donors)
        if pool <= 0:
            continue
        scale = max(0.0, (pool - delta) / pool)
        for p in donors:
            old = minutes[p]["mpg"]
            minutes[p]["mpg"] = round(old * scale, 1)
            changes.append({"player_id": p, "player": name_of.get(p), "team": team, "role": "donor",
                            "adp": adp_of.get(p), "old_mpg": old, "new_mpg": minutes[p]["mpg"], "history_mpg": None})

    newline = "\r\n" if "\r\n" in raw else "\n"
    path.write_bytes(yaml.safe_dump(doc, sort_keys=True).replace("\n", newline).encode("utf-8"))
    out = pd.DataFrame(changes)
    REPORTS.mkdir(exist_ok=True)
    out.to_csv(REPORTS / "minutes_adp_reconciliation.csv", index=False)
    raised = out[out["role"] == "raised"] if len(out) else out
    print(f"raised {len(raised)} fantasy-relevant players across {len(added)} teams; "
          f"{len(out) - len(raised)} bench rows gave minutes back")
    if len(raised):
        print(raised.sort_values("adp")[["team", "player", "adp", "old_mpg", "new_mpg"]].to_string(index=False))


if __name__ == "__main__":
    main()
