"""Write depth-chart-derived mpg into config/minutes.yaml (spec §3.5).

Edits minutes.yaml in place via read-modify-write on the existing text so the
file's CRLF line endings and key order survive and the diff shows only the
players actually touched.

Policy decisions, all deliberate:

  * Teams already hand-reviewed are SKIPPED, not overwritten. LAL was reviewed
    by hand from a different (ESPN) chart and that judgement outranks a
    generated value. The disagreement is reported instead.
  * A rostered player absent from the depth chart gets mpg 0 but STAYS
    estimated: true. Absence is an open question (injured? departed?), not a
    decision, and estimated: true is what keeps them in the warning list.
  * games_played.yaml gets only the missing roster rows seeded at the spec
    default of 82, flagged estimated: true. Existing GP values are never
    changed -- GP is a separate judgement call -- but a player with no entry
    at all reads as GP 0 in the sanity check, which is a bug, not a judgement.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

import depth_charts as dc

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
REPORTS = ROOT / "reports"

# Teams whose minutes were set by hand and must not be regenerated.
HAND_REVIEWED = {"LAL"}


def set_entries(text: str, updates: dict[str, tuple[float, bool]],
                value_key: str = "mpg",
                value_fmt=lambda v: str(round(float(v), 1))) -> tuple[str, list[str]]:
    """Rewrite `<value_key>:` / `estimated:` for the given player_ids, in place.

    Operates on the raw text rather than round-tripping through yaml.dump so
    line endings, ordering and untouched entries are byte-identical. Used for
    both minutes.yaml (mpg) and games_played.yaml (gp).
    """
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    # locate each player's block: "  <pid>:" followed by its indented keys
    index: dict[str, int] = {}
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.endswith(":") and ln.startswith("  ") and not ln.startswith("    "):
            index[s[:-1]] = i

    inserted = []
    for pid, (mpg, estimated) in updates.items():
        start = index.get(pid)
        if start is None:
            inserted.append(pid)
            continue
        j = start + 1
        while j < len(lines) and lines[j].startswith("    "):
            key = lines[j].strip().split(":")[0]
            if key == value_key:
                lines[j] = f"    {value_key}: {value_fmt(mpg)}"
            elif key == "estimated":
                lines[j] = f"    estimated: {'true' if estimated else 'false'}"
            j += 1

    # Players on the roster but absent from the config entirely -- minutes.yaml
    # predates the supplemental roster rows. Insert them in sorted position so
    # the file stays ordered by player_id.
    for pid in sorted(inserted):
        mpg, estimated = updates[pid]
        block = [f"  {pid}:",
                 f"    estimated: {'true' if estimated else 'false'}",
                 f"    {value_key}: {value_fmt(mpg)}"]
        after = [k for k in index if k < pid]
        if after:
            anchor = max(after)
            at = index[anchor] + 1
            while at < len(lines) and lines[at].startswith("    "):
                at += 1
        else:
            at = 1  # straight after the "minutes:" header
        lines[at:at] = block
        # rebuild the index; line numbers shifted
        index = {ln.strip()[:-1]: i for i, ln in enumerate(lines)
                 if ln.startswith("  ") and not ln.startswith("    ")
                 and ln.strip().endswith(":")}
    return nl.join(lines), inserted


def main(dry_run: bool = False) -> None:
    res = dc.build()
    alloc, rosters = res["allocation"], res["rosters"]
    captured = sorted(alloc.team.unique())
    targets = [t for t in captured if t not in HAND_REVIEWED]

    ps = pd.read_csv(ROOT / "data" / "canonical" / "player_seasons.csv")
    hist = (
        ps.sort_values("season")
        .groupby("player_id")
        .agg(mpg_hist=("mpg", lambda s: ", ".join(f"{v:.0f}" for v in s)),
             mpg_last=("mpg", "last"), mp_last=("mp", "last"))
    )

    # ---- players to write: matched depth-chart entries on target teams
    a = alloc[alloc.team.isin(targets) & alloc.player_id.notna()].copy()
    updates = {r.player_id: (round(float(r.mpg), 1), False) for r in a.itertuples()}

    # ---- rostered but not on the chart: zero, but keep flagged
    on_chart = set(alloc.player_id.dropna())
    ros = rosters[rosters.player_id.notna() & rosters.team.isin(targets)]
    absent = ros[~ros.player_id.isin(on_chart)].copy()
    for r in absent.itertuples():
        updates[r.player_id] = (0.0, True)

    with open(CONFIG / "minutes.yaml", encoding="utf-8", newline="") as fh:
        text = fh.read()
    new_text, inserted = set_entries(text, updates)

    # games_played.yaml has the same staleness gap: roster rows added after it
    # was generated have no entry at all. minutes_sanity_check reads a missing
    # GP as 0 (not 82), so those players silently contribute zero season
    # minutes and their team looks short. Seed them at the spec §3.5 default.
    gp_cfg = yaml.safe_load((CONFIG / "games_played.yaml").read_text(encoding="utf-8"))["games_played"]
    all_rostered = rosters[rosters.player_id.notna()].player_id
    gp_missing = {p: (82, True) for p in all_rostered if p not in gp_cfg}
    with open(CONFIG / "games_played.yaml", encoding="utf-8", newline="") as fh:
        gp_text = fh.read()
    new_gp_text, gp_inserted = set_entries(
        gp_text, gp_missing, value_key="gp", value_fmt=lambda v: str(int(v))
    )

    # ---------------------------------------------------------------- reports
    a["mpg_hist"] = a.player_id.map(hist.mpg_hist)
    a["mpg_last"] = a.player_id.map(hist.mpg_last)
    a["delta_vs_last"] = (a.mpg - a.mpg_last).round(1)
    review = a[["team", "roster_name", "tier_label", "tier_index", "position",
                "mpg", "mpg_last", "delta_vs_last", "mpg_hist",
                "match_kind", "all_slots"]].sort_values(
        ["team", "mpg"], ascending=[True, False])
    REPORTS.mkdir(exist_ok=True)
    review.to_csv(REPORTS / "depth_chart_minutes_review.csv", index=False)

    gaps = alloc[alloc.player_id.isna() & (alloc.mpg > 0)][
        ["team", "roster_name", "tier_label", "position", "mpg", "match_kind", "match_note"]
    ].sort_values("mpg", ascending=False)
    gaps.to_csv(REPORTS / "depth_chart_roster_gaps.csv", index=False)

    absent["mpg_last"] = absent.player_id.map(hist.mpg_last)
    absent["mp_last"] = absent.player_id.map(hist.mp_last)
    absent.sort_values("mp_last", ascending=False)[
        ["team", "roster_name", "pos_roster", "player_id", "mpg_last", "mp_last"]
    ].to_csv(REPORTS / "depth_chart_absent_from_chart.csv", index=False)

    print(f"teams captured        : {len(captured)}  ({', '.join(captured)})")
    print(f"teams written         : {len(targets)}   (skipped hand-reviewed: {sorted(HAND_REVIEWED)})")
    print(f"players given mpg     : {len(a)}")
    print(f"rostered, off-chart   : {len(absent)}  -> mpg 0, still estimated: true")
    print(f"chart entries w/o id  : {int(alloc.player_id.isna().sum())} "
          f"({int(gaps.shape[0])} of them with mpg > 0)")
    if inserted:
        print(f"minutes.yaml inserts  : {len(inserted)} (roster rows that postdate the config)")
    if gp_inserted:
        print(f"games_played inserts  : {len(gp_inserted)} seeded at 82, estimated: true")

    if dry_run:
        print("\n[dry run] no files modified")
        return
    with open(CONFIG / "minutes.yaml", "w", encoding="utf-8", newline="") as fh:
        fh.write(new_text)
    with open(CONFIG / "games_played.yaml", "w", encoding="utf-8", newline="") as fh:
        fh.write(new_gp_text)
    print("\nminutes.yaml and games_played.yaml updated")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    main(**vars(p.parse_args()))
