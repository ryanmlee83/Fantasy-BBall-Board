"""Parse RealGM depth charts and allocate minutes from them (spec §3.5 helper).

Reads data/raw/realgm_depth_charts_*.txt (the pipe-delimited capture format
documented at the top of that file) and produces:

  * a tidy depth-chart table (team, tier, tier_index, position, name)
  * a crosswalk to BBRef player_id, scoped per team against rosters_2627.csv
  * a minutes allocation per player, summing to the team target

Design notes, because two obvious approaches are wrong here:

1. *Not* 48 minutes per position split down a depth curve. RealGM's chart does
   not cover positions evenly -- DAL lists exactly one PG, MIA two PFs, OKC/SAS
   no centers at all in the roster file. A per-position split hands DAL's lone
   PG 48 mpg. Allocation is therefore by TIER across the whole team, which is
   what the chart actually encodes: starters, then bench in rotation order.

2. Name matching is last-name + first-initial scoped to the team, and anything
   ambiguous is REPORTED, never guessed. RealGM abbreviates ("N. Alexander-
   Walker", "R. Harper, Jr."), and this project has already been bitten once by
   an initial-only match ("M. Brown Jr." -> Moses Brown, when it was really
   rookie Mikel Brown Jr.). See DATA_DICTIONARY.md.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "data" / "canonical"
RAW = ROOT / "data" / "raw"

POSITIONS = ["PG", "SG", "SF", "PF", "C"]

# RealGM team abbreviations -> the project's canonical (BBRef) abbreviations.
TEAM_FIXUPS = {"CHA": "CHO", "PHX": "PHO", "BKN": "BRK"}

# Starters get a FIXED mpg and the bench absorbs everything else.
#
# The obvious alternative -- weight every tier and normalise the whole team to
# 240 -- fails badly, because teams list wildly different numbers of bench
# bodies. ATL lists 8 non-garbage-time reserves and MIA lists 6; normalising
# across all of them drags ATL's starters down to ~26 mpg and puts Luka at
# 27.5. Real rotations don't work that way: starters sit around 32-35
# regardless of roster depth, and it's the back of the bench that gets
# squeezed. So fix the starters and distribute the remainder.
STARTER_MPG = 33.0
TEAM_TARGET_MPG = 240.0
# Relative weights for the bench, by rotation row. Steep, because listed depth
# is longer than actual rotation depth -- NBA teams really play 9-10 men.
BENCH_WEIGHTS = {2: 1.0, 3: 0.45, 4: 0.20, 5: 0.10}
BENCH_FALLBACK_WEIGHT = 0.05
LIM_PT_MPG = 0.0
MAX_MPG = 37.0
MAX_BENCH_MPG = 26.0


# ------------------------------------------------------------------ parsing

def parse_capture(path: Path) -> pd.DataFrame:
    """Parse the pipe-delimited capture into tidy rows.

    Validates hard: every data line must carry exactly 6 fields and each team's
    row count must match its declared ROWS=. A silent cell drop is the failure
    mode that matters here (a dropped player is minutes that never get
    allocated), so this raises rather than warns.
    """
    rows: list[dict] = []
    team: str | None = None
    declared: dict[str, int] = {}
    seen: dict[str, int] = {}

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("TEAM="):
            m = re.fullmatch(r"TEAM=([A-Z]{3})\s+ROWS=(\d+)", line)
            if not m:
                raise ValueError(f"{path.name}:{lineno}: bad TEAM header: {line!r}")
            team = TEAM_FIXUPS.get(m.group(1), m.group(1))
            declared[team] = int(m.group(2))
            seen[team] = 0
            continue
        if team is None:
            raise ValueError(f"{path.name}:{lineno}: data line before any TEAM header")

        fields = [f.strip() for f in line.split("|")]
        if len(fields) != 6:
            raise ValueError(
                f"{path.name}:{lineno}: expected 6 fields, got {len(fields)}: {line!r}"
            )
        seen[team] += 1
        tier_label, cells = fields[0], fields[1:]
        for pos, cell in zip(POSITIONS, cells):
            if cell == "EMPTY" or not cell:
                continue
            rows.append(
                {
                    "team": team,
                    "tier_label": tier_label,
                    "tier_index": seen[team],
                    "position": pos,
                    "roster_name": cell,
                }
            )

    bad = {t: (declared[t], seen[t]) for t in declared if declared[t] != seen[t]}
    if bad:
        raise ValueError(f"{path.name}: declared vs parsed row count mismatch: {bad}")

    return pd.DataFrame(rows)


def assign_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse each player to their single best (numerically lowest) tier.

    A player listed at two positions is one player with one role; summing their
    slots would double-count minutes now that allocation is team-level.
    """
    df = df.copy()
    df["is_lim"] = df.tier_label.str.lower().str.startswith("lim")
    # rank tiers: all non-Lim tiers keep their index; Lim PT sorts last
    df["tier_rank"] = df.tier_index.where(~df.is_lim, 99)
    best = (
        df.sort_values(["team", "roster_name", "tier_rank"])
        .groupby(["team", "roster_name"], as_index=False)
        .first()
    )
    slots = (
        df.groupby(["team", "roster_name"])
        .apply(
            lambda g: ", ".join(
                f"{r.tier_label}/{r.position}" for r in g.itertuples()
            ),
            include_groups=False,
        )
        .rename("all_slots")
        .reset_index()
    )
    return best.merge(slots, on=["team", "roster_name"])


# ------------------------------------------------------------- name matching

SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


def name_parts(name: str) -> tuple[str, str]:
    """Return (first_token, last_name) with suffixes stripped.

    Handles "R. Harper, Jr.", "C.J. McCollum" and "Ernest Udeh, Jr.".

    Leading single-letter tokens are concatenated so that "V.J. Edgecombe" and
    "V. J. Edgecombe" both yield first="vj" -- the two sources punctuate
    initials differently and that alone was costing real matches.

    Suffixes are stripped from the TAIL only. Stripping them anywhere drops the
    leading initial of "V. J. Edgecombe", because "v" is also the Roman numeral
    five; that silently cost a starter his 33 mpg.
    """
    n = str(name).replace(",", " ")
    toks = [t for t in norm(n).split() if t]
    while len(toks) > 1 and toks[-1] in SUFFIXES:
        toks.pop()
    if not toks:
        return "", ""
    if len(toks) == 1:
        return "", toks[0]
    lead, rest = [], list(toks[:-1])
    while rest and len(rest[0]) == 1:
        lead.append(rest.pop(0))
    first = "".join(lead) if lead else rest[0]
    return first, toks[-1]


# Ambiguous entries resolved by hand, with the evidence. Never widen the
# matcher to catch these -- an initial-only match that "looks obvious" is how
# Mikel Brown Jr. became Moses Brown (see DATA_DICTIONARY.md).
MANUAL_MATCHES = {
    # OKC lists "J. Williams" at C in the rotation AND "Jalen Williams" at SF
    # among the starters. Jalen is therefore already placed, so the centre must
    # be Jaylin Williams (PF/C, willija07). Kenrich Williams is the third
    # rostered Williams but is a G/F and not otherwise on the chart.
    ("OKC", "J. Williams"): "willija07",
}


def crosswalk(depth: pd.DataFrame, rosters: pd.DataFrame) -> pd.DataFrame:
    """Match depth-chart names to player_id, scoped per team.

    match_kind records how confident the match is so downstream code and the
    reviewer can treat them differently:
      full     -- full first name and last name agree
      initial  -- last name + first initial, and unique within the team
      ambig    -- last name matched >1 rostered player; NOT resolved
      none     -- no last-name match on that team
    """
    ros = rosters[rosters.player_id.notna()].copy()
    ros[["r_first", "r_last"]] = ros.roster_name.apply(
        lambda n: pd.Series(name_parts(n))
    )

    out = []
    for r in depth.itertuples():
        manual = MANUAL_MATCHES.get((r.team, r.roster_name))
        if manual:
            out.append({"player_id": manual, "match_kind": "manual",
                        "match_note": "resolved by hand; see MANUAL_MATCHES"})
            continue
        first, last = name_parts(r.roster_name)
        pool = ros[(ros.team == r.team) & (ros.r_last == last)]
        pid, kind, note = None, "none", ""
        if len(pool):
            exact = pool[pool.r_first == first]
            if len(exact) == 1:
                pid, kind = exact.player_id.iloc[0], "full"
            elif len(exact) > 1:
                kind, note = "ambig", f"{len(exact)} exact-name matches"
            else:
                ini = pool[pool.r_first.str[:1] == first[:1]] if first else pool
                if len(ini) == 1:
                    pid, kind = ini.player_id.iloc[0], "initial"
                elif len(ini) > 1:
                    kind, note = "ambig", "; ".join(sorted(ini.roster_name))
                else:
                    kind, note = "none", f"last name on team but initial differs: {'; '.join(sorted(pool.roster_name))}"
        out.append({"player_id": pid, "match_kind": kind, "match_note": note})

    return pd.concat([depth.reset_index(drop=True), pd.DataFrame(out)], axis=1)


# --------------------------------------------------------------- allocation

def allocate(depth: pd.DataFrame, target: float = TEAM_TARGET_MPG,
             starter_mpg: float = STARTER_MPG) -> pd.DataFrame:
    """Starters at a fixed mpg; the bench splits whatever is left.

    Lim PT players get zero. Bench minutes are water-filled against
    MAX_BENCH_MPG so a team with only one or two listed reserves can't hand
    them implausible starter-level workloads.
    """
    d = depth.copy()
    d["is_starter"] = (~d.is_lim) & (d.tier_index == 1)
    d["bench_w"] = [
        0.0 if (lim or t == 1)
        else BENCH_WEIGHTS.get(int(t), BENCH_FALLBACK_WEIGHT)
        for lim, t in zip(d.is_lim, d.tier_index)
    ]

    parts = []
    for team, g in d.groupby("team"):
        g = g.copy()
        g["mpg"] = 0.0
        g.loc[g.is_starter, "mpg"] = min(starter_mpg, MAX_MPG)
        remaining = target - g.mpg.sum()

        bench = g.index[g.bench_w > 0]
        if len(bench) and remaining > 0:
            free = list(bench)
            for _ in range(10):
                w = g.loc[free, "bench_w"]
                if w.sum() <= 0:
                    break
                prop = remaining * w / w.sum()
                over = prop.index[prop > MAX_BENCH_MPG]
                if not len(over):
                    g.loc[free, "mpg"] = prop
                    break
                g.loc[over, "mpg"] = MAX_BENCH_MPG
                remaining -= MAX_BENCH_MPG * len(over)
                free = [i for i in free if i not in set(over)]
                if not free:
                    break
        g["mpg"] = g.mpg.round(1)
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def build(capture: Path | None = None) -> dict[str, pd.DataFrame]:
    capture = capture or sorted(RAW.glob("realgm_depth_charts_*.txt"))[-1]
    rosters = pd.read_csv(CANON / "rosters_2627.csv")
    tidy = parse_capture(capture)
    best = assign_tiers(tidy)
    matched = crosswalk(best, rosters)
    alloc = allocate(matched)
    return {"tidy": tidy, "allocation": alloc, "rosters": rosters}


if __name__ == "__main__":
    res = build()
    a = res["allocation"]
    print(f"teams captured      : {a.team.nunique()}")
    print(f"depth-chart players : {len(a)}")
    print("\nmatch quality:")
    print(a.match_kind.value_counts().to_string())
    print("\nper-team mpg totals:")
    print(a.groupby("team").mpg.sum().round(1).to_string())
