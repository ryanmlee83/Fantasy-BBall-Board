"""Rebuild data/canonical/rosters_2627.csv from Basketball Reference team pages.

Supersedes the Wikipedia-derived docx parse in harmonize.py as the source of
roster truth. Reasons, recorded because this replaced a working pipeline:

  * The docx is a point-in-time export that goes stale silently. Scored against
    BBRef across 10 teams it ran 92% precise, and its misses were not random --
    they clustered on recently-transacted players (Kawhi Leonard still on LAC,
    Brandon Ingram still on TOR), which is exactly the population that matters
    for minutes.
  * BBRef team pages carry the project's native `player_id`, so the crosswalk is
    a lookup rather than a name match. Name matching has produced three real
    bugs in this project's history (Moses Brown / Mikel Brown Jr., the two
    Bridges, V. J. Edgecombe losing his initial to the Roman numeral five).
  * The pages also carry height, weight and date of birth, so
    `age_at_season_start` -- which feeds the §3 age curve -- comes from the same
    fetch instead of a separate research pass.

Reuses `harmonize.norm_name` deliberately so `name_norm` stays byte-compatible
with the file this replaces.

Input: a capture file of `TEAM|Name|Pos|Height|Weight|DOB` lines.
Usage: python scripts/build_rosters_from_bbref.py <capture.txt> [--out PATH]
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "data" / "canonical"
SEASON = "2026-27"
SEASON_START = datetime.date(2026, 10, 21)  # matches harmonize.py

# import harmonize's normaliser without running its __main__ work
_spec = importlib.util.spec_from_file_location("_harm", Path(__file__).parent / "harmonize.py")


def _norm_name_fallback(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().replace(".", " ").replace("'", "").replace("-", " ")
    toks = re.sub(r"[^a-z ]", "", s).split()
    while len(toks) > 2 and toks[-1] in {"jr", "sr", "ii", "iii", "iv", "v"}:
        toks.pop()
    out, buf = [], []
    for t in toks:
        if len(t) == 1:
            buf.append(t)
        else:
            if buf:
                out.append("".join(buf))
                buf = []
            out.append(t)
    if buf:
        out.append("".join(buf))
    return " ".join(out)


try:
    import harmonize  # type: ignore
    norm_name = harmonize.norm_name
except Exception:
    norm_name = _norm_name_fallback


def parse_height(h: str) -> int | None:
    m = re.fullmatch(r"(\d+)-(\d+)", h.strip())
    return int(m.group(1)) * 12 + int(m.group(2)) if m else None


def parse_dob(d: str) -> datetime.date | None:
    d = d.strip()
    for fmt in ("%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.datetime.strptime(d, fmt).date()
        except ValueError:
            continue
    return None


def load_capture(path: Path) -> list[dict]:
    rows = []
    for lineno, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        f = ln.split("|")
        if len(f) != 6:
            raise SystemExit(f"{path.name}:{lineno}: expected 6 fields, got {len(f)}: {ln!r}")
        team, name, pos, ht, wt, dob = (x.strip() for x in f)
        rows.append({"team": team, "roster_name": name, "pos_roster": pos,
                     "height_in": parse_height(ht),
                     "weight_lb": int(wt) if wt.isdigit() else None,
                     "dob": parse_dob(dob)})
    return rows


def _write_derived(out_rows: list[dict], byname: dict) -> None:
    """Regenerate crosswalk_unmatched.csv and unrostered_players.csv.

    Mirrors harmonize.py's own outputs, including its fuzzy-suggestion rule:
    suggest only when the SURNAME matches exactly and then compare first names
    only, because comparing whole strings lets a shared surname carry the score
    (Dillon vs Davion Mitchell).
    """
    import difflib

    all_keys = list(byname)
    name_by_id, seasons = {}, {}
    for r in csv.DictReader(open(CANON / "player_seasons.csv")):
        name_by_id[r["player_id"]] = r["player_name"]
        if r["season"] == "2025-26":
            seasons[r["player_id"]] = r

    unmatched = []
    for r in (x for x in out_rows if not x["player_id"]):
        nn = r["name_norm"]
        surname = nn.split()[-1] if nn else ""
        first = " ".join(nn.split()[:-1])
        pool = {k: " ".join(k.split()[:-1]) for k in all_keys if k.split()[-1:] == [surname]}
        near = difflib.get_close_matches(first, list(pool.values()), n=1, cutoff=0.82) if pool else []
        sugg = ""
        if near:
            key = next(k for k, v in pool.items() if v == near[0])
            cand = sorted(byname[key])
            sugg = f"{name_by_id[cand[0]]} ({cand[0]})"
        unmatched.append({"team": r["team"], "roster_name": r["roster_name"],
                          "pos_roster": r["pos_roster"], "jersey": r["jersey"],
                          "two_way": r["two_way"], "dob": r["dob"],
                          "age_at_season_start": r["age_at_season_start"],
                          "match": r["match"], "fuzzy_suggestion": sugg})
    unmatched.sort(key=lambda r: (r["match"], r["team"]))
    with open(CANON / "crosswalk_unmatched.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["team", "roster_name", "pos_roster", "jersey",
                                           "two_way", "dob", "age_at_season_start",
                                           "match", "fuzzy_suggestion"])
        w.writeheader(); w.writerows(unmatched)

    rostered = {r["player_id"] for r in out_rows if r["player_id"]}
    unrostered = []
    for pid, r in seasons.items():
        if pid in rostered:
            continue
        unrostered.append({"player_id": pid, "player_name": r["player_name"],
                           "team_2526": r["team"] or r["teams_played"],
                           "mp_2526": r["mp"], "mpg_2526": r["mpg"]})
    unrostered.sort(key=lambda r: -float(r["mp_2526"] or 0))
    with open(CANON / "unrostered_players.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["player_id", "player_name", "team_2526",
                                           "mp_2526", "mpg_2526"])
        w.writeheader(); w.writerows(unrostered)

    sug = sum(1 for r in unmatched if r["fuzzy_suggestion"])
    print(f"  crosswalk_unmatched.csv : {len(unmatched)} rows ({sug} with a fuzzy suggestion)")
    print(f"  unrostered_players.csv  : {len(unrostered)} rows")


def build(capture: Path, out: Path, twoway: Path | None = None) -> None:
    rows = load_capture(capture)

    # player_id lookup from the project's own historical table, by exact
    # normalised full name. A name that maps to more than one id is reported,
    # never guessed.
    byname = collections.defaultdict(set)
    for r in csv.DictReader(open(CANON / "player_seasons.csv")):
        byname[norm_name(r["player_name"])].add(r["player_id"])

    # two-way flags, if a capture was supplied: "TEAM|Name|yes/no" lines
    tw = {}
    if twoway and twoway.exists():
        for ln in twoway.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            f = ln.split("|")
            if len(f) >= 3:
                tw[(f[0].strip(), norm_name(f[1]))] = f[2].strip().lower().startswith("y")

    # carry forward two-way for players already in the file we're replacing,
    # so an absent capture degrades to the previous value rather than to False
    prev = {}
    old_path = CANON / "rosters_2627.csv"
    if old_path.exists():
        for r in csv.DictReader(open(old_path)):
            prev[norm_name(r["roster_name"])] = r["two_way"] == "True"

    out_rows, ambiguous, tw_source = [], [], collections.Counter()
    for r in rows:
        nn = norm_name(r["roster_name"])
        ids = byname.get(nn, set())
        if len(ids) == 1:
            pid, match = next(iter(ids)), "exact"
        elif len(ids) > 1:
            pid, match = None, "ambiguous"
            ambiguous.append((r["team"], r["roster_name"], sorted(ids)))
        else:
            pid, match = None, "no_history"

        age = None
        if r["dob"]:
            d = r["dob"]
            age = (SEASON_START.year - d.year
                   - ((SEASON_START.month, SEASON_START.day) < (d.month, d.day)))

        key = (r["team"], nn)
        if key in tw:
            two_way = tw[key]; tw_source["fetched"] += 1
        elif nn in prev:
            two_way = prev[nn]; tw_source["carried_forward"] += 1
        else:
            two_way = False; tw_source["defaulted_false"] += 1

        out_rows.append({
            "team": r["team"], "season": SEASON, "roster_name": r["roster_name"],
            "name_norm": nn, "pos_roster": r["pos_roster"], "jersey": "",
            "two_way": two_way, "height_in": r["height_in"],
            "weight_lb": r["weight_lb"],
            "dob": r["dob"].isoformat() if r["dob"] else "",
            "age_at_season_start": age, "player_id": pid or "", "match": match,
        })

    out_rows.sort(key=lambda r: (r["team"], r["roster_name"]))
    cols = ["team", "season", "roster_name", "name_norm", "pos_roster", "jersey",
            "two_way", "height_in", "weight_lb", "dob", "age_at_season_start",
            "player_id", "match"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)

    # --- derived files that must stay consistent with the roster, or the test
    # suite rightly fails: crosswalk_unmatched.csv is asserted to have exactly
    # as many rows as the roster has unmatched entries.
    if out.parent == CANON:
        _write_derived(out_rows, byname)

    sizes = collections.Counter(r["team"] for r in out_rows)
    print(f"wrote {out}  ({len(out_rows)} rows, {len(sizes)} teams, sizes {min(sizes.values())}-{max(sizes.values())})")
    print(f"  player_id matched : {sum(1 for r in out_rows if r['player_id'])}")
    print(f"  no BBRef history  : {sum(1 for r in out_rows if r['match']=='no_history')}")
    print(f"  missing dob       : {sum(1 for r in out_rows if not r['dob'])}")
    print(f"  two_way provenance: {dict(tw_source)}")
    if ambiguous:
        print(f"  AMBIGUOUS, left unmatched ({len(ambiguous)}):")
        for t, n, ids in ambiguous:
            print(f"    {t} {n} -> {ids}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("capture", type=Path)
    p.add_argument("--out", type=Path, default=CANON / "rosters_2627.csv")
    p.add_argument("--twoway", type=Path, default=None)
    a = p.parse_args()
    build(a.capture, a.out, a.twoway)
