"""Parse a pasted Yahoo draft into picks matched to player_id.

Handles the three formats Ryan has pasted so far:
  * results page:  "(3) Ryan - Allen, Jarrett (CLE - C)" under "Round N" headers
  * draft room:    blocks of  pick# / "J. Hart" / "J. Hart" / [status] / positions / NBA team / fantasy team
  * team blocks:   a fantasy team name line, then "1.<tab>(3)<tab>Luka Dončić (LAL - PG,SG)" per pick

Draft-room names are first initial + surname, so a name alone can be ambiguous
(the project's standing lesson: Moses Brown / Mikel Brown Jr., Mikal / Miles
Bridges). Matching therefore requires initial + surname + NBA team, and when
that still leaves more than one player (OKC's Jalen and Jaylin Williams), it
picks the one with the earlier ADP and records the call in `match_note` so it
can be audited rather than silently guessed.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TEAM_ALIASES = {"BKN": "BRK", "CHA": "CHO", "PHX": "PHO", "UTH": "UTA", "NOR": "NOP", "GS": "GSW", "SA": "SAS", "NY": "NYK", "NO": "NOP"}
SUFFIX = {"jr", "sr", "ii", "iii", "iv", "v"}


def tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace(".", " ").replace("'", "").replace("-", " ")
    t = re.sub(r"[^a-z ]", " ", s).split()
    while len(t) > 2 and t[-1] in SUFFIX:
        t.pop()
    return t


def name_matches(pasted: str, full: str) -> bool:
    """'J. Hart' matches 'Josh Hart'; 'K. Towns' matches 'Karl-Anthony Towns';
    a full pasted first name ('Jalen Williams') must match the first name exactly."""
    pt, ft = tokens(pasted), tokens(full)
    if len(pt) < 2 or len(ft) < 2:
        return False
    first, surname = pt[0], pt[1:]
    if ft[-len(surname):] != surname or len(ft) <= len(surname):
        return False
    lead = ft[:-len(surname)]
    if len(first) == 1:
        return lead[0][0] == first
    return "".join(lead) == first or lead[0] == first


def parse_results(text: str) -> list[dict]:
    picks, rnd = [], 0
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"Round (\d+)", line)
        if m:
            rnd = int(m.group(1))
            continue
        m = re.match(r"\((\d+)\) (.+?) - (.+?), (.+?) \((\w+) - ([A-Z,]+)\)", line)
        if m:
            slot, team, last, first, nba, pos = m.groups()
            picks.append({"round": rnd, "slot_in_round": int(slot), "fantasy_team": team,
                          "name": f"{first} {last}", "nba": nba, "pos": pos})
    return picks


PICK_IN_BLOCK = re.compile(r"^\d+\.\s+\((\d+)\)\s+(.+?) \((\w+) - ([A-Z,]+)\)$")


def parse_blocks(text: str) -> list[dict]:
    """Team-by-team results: a header line names the fantasy team, each pick line carries the overall pick."""
    picks, team = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = PICK_IN_BLOCK.match(line)
        if m:
            overall, name, nba, pos = m.groups()
            picks.append({"overall": int(overall), "fantasy_team": team, "name": name, "nba": nba, "pos": pos})
        else:
            team = line
    return sorted(picks, key=lambda p: p["overall"])


def parse_room(text: str) -> list[dict]:
    lines = [l.strip() for l in text.splitlines()]
    picks, i = [], 0
    while i < len(lines):
        if re.fullmatch(r"\d+", lines[i]) and i + 2 < len(lines) and lines[i + 1] and lines[i + 1] == lines[i + 2]:
            no, name = int(lines[i]), lines[i + 1]
            j = i + 3
            status = None
            # anything that isn't a position list is a status tag (Q, O, P, GTD, INJ, ...)
            if not re.fullmatch(r"(?:PG|SG|SF|PF|C|G|F|FC|Util)(?:,(?:PG|SG|SF|PF|C|G|F|FC|Util))*", lines[j]):
                status = lines[j]
                j += 1
            pos, nba, team = lines[j], lines[j + 1], lines[j + 2]
            picks.append({"overall": no, "name": name, "status": status, "pos": pos, "nba": nba, "fantasy_team": team})
            i = j + 3
        else:
            i += 1
    return sorted(picks, key=lambda p: p["overall"])


def match(picks: list[dict], board: dict) -> pd.DataFrame:
    by_team: dict[str, list[dict]] = {}
    for p in board["players"]:
        by_team.setdefault(p["team"], []).append(p)
    rows = []
    for k in picks:
        nba = TEAM_ALIASES.get(k["nba"], k["nba"])
        hits = [p for p in by_team.get(nba, []) if name_matches(k["name"], p["name"])]
        note = ""
        if not hits and len(tokens(k["name"])[0]) > 1:
            # full first name given: a player who changed teams after the board's roster snapshot
            # can be matched league-wide, but only when exactly one player has that full name
            full = [p for p in board["players"] if tokens(p["name"]) == tokens(k["name"])]
            if len(full) == 1:
                hits = full
                note = f"team differs: board {full[0]['team']}, Yahoo {nba}"
        if len(hits) > 1:
            hits = sorted(hits, key=lambda p: p.get("adp") or p.get("adpAvg") or 999)
            note = f"ambiguous ({' / '.join(h['name'] for h in hits)}); took earlier ADP"
        p = hits[0] if hits else None
        rows.append({**k, "player_id": p["id"] if p else None, "player": p["name"] if p else None,
                     "projected": bool(p and not p.get("np")), "match_note": note if p else "NO MATCH"})
    return pd.DataFrame(rows)


def main() -> None:
    raw, teams = Path(sys.argv[1]), int(sys.argv[2])
    out = Path(sys.argv[3])
    text = raw.read_text(encoding="utf-8")
    picks = parse_results(text) or parse_blocks(text) or parse_room(text)
    for p in picks:
        if "overall" not in p:
            p["overall"] = (p["round"] - 1) * teams + p["slot_in_round"]
        p.setdefault("round", (p["overall"] - 1) // teams + 1)
    board = json.loads((ROOT / "reports" / "board_data.json").read_text(encoding="utf-8"))
    df = match(picks, board).sort_values("overall")
    df.to_csv(out, index=False)
    print(f"{len(df)} picks -> {out}; unmatched: {int(df['player_id'].isna().sum())}")
    notes = df[df["match_note"] != ""]
    if len(notes):
        print(notes[["overall", "name", "nba", "player", "match_note"]].to_string(index=False))


if __name__ == "__main__":
    main()
