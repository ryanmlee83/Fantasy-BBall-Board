"""Draft mode -- spec §9 stage 8. Builds the data the live draft board runs on.

`python -m src.cli board` writes reports/board_data.json, which the board page
(board/draft_board.html) embeds. The page does the live arithmetic -- which
categories to punt, who is still available, what the user's roster needs --
so this module only has to supply honest per-player inputs.

What each player carries:
  * per-game projections from the existing pipeline (src/project.py), using
    config/minutes.yaml (healthy-night minutes) and config/games_played.yaml
  * per-game Z-scores for all nine categories against a draftable pool of
    12 teams x 13 drafted spots = 156, exactly as src/value.py computes them
    (FG/FT as volume-weighted impact, TOV inverted)
  * projected games played, so the board can rank by value above replacement
    times availability -- the "high floor" view -- or by per-game value
  * Yahoo positional eligibility and ADP from FantasyPros (fetched 2026-10-14,
    data/raw/fantasypros_adp_20261014.csv), matched to player_id on
    (normalised name, team) -- never on surname or initials alone
  * any injury note from config/injuries.yaml

Players in the ADP list who have no NBA history (2026 rookies, international
signings) can't be projected by a historical-blend model (§10 puts rookie
modeling out of scope). They are included with ADP and positions only and
flagged `np`, so the board can show them without inventing numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yaml

from src import ingest, project, value

ROOT = Path(__file__).resolve().parents[1]
ADP_PATH = ROOT / "data" / "raw" / "fantasypros_adp_20261014.csv"
INJURIES_PATH = ROOT / "config" / "injuries.yaml"
OUT_PATH = ROOT / "reports" / "board_data.json"

TEAM_ALIASES = {"UTH": "UTA", "NOR": "NOP", "BKN": "BRK", "CHA": "CHO", "PHX": "PHO",
                "GS": "GSW", "SA": "SAS", "NY": "NYK", "NO": "NOP"}
POSITIONS = ["PG", "SG", "SF", "PF", "C"]
CATS = value.ALL_CATEGORIES  # PTS REB AST STL BLK 3PM FG_IMPACT FT_IMPACT TOV


def _norm_name():
    """Same normalisation as scripts/harmonize.py:norm_name (which can't be
    imported -- it runs its whole build at import time). Kept byte-compatible
    so `name_norm` in rosters_2627.csv matches."""
    import re
    import unicodedata

    suffixes = {"jr", "sr", "ii", "iii", "iv", "v"}

    def norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
        s = s.lower().replace(".", " ").replace("'", "").replace("-", " ")
        toks = re.sub(r"[^a-z ]", "", s).split()
        while len(toks) > 2 and toks[-1] in suffixes:  # trailing only -- see V. J. Edgecombe
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

    return norm


def fallback_positions(bbref_pos: str | None, roster_pos: str | None) -> list[str]:
    """Used only when a player isn't in the ADP list. BBRef gives one position
    per season; Yahoo usually grants a neighbour too, so add it when the
    roster listing (G / F / C, possibly hyphenated) supports it."""
    pos = (bbref_pos or "").split("-")[0]
    out = [pos] if pos in POSITIONS else []
    rp = set((roster_pos or "").split("-"))
    if "G" in rp:
        out += ["PG", "SG"] if not out else (["SG"] if pos == "PG" else ["PG"] if pos == "SG" else ["SG"])
    if "F" in rp:
        out += ["SF", "PF"] if not out else (["PF"] if pos == "SF" else ["SF"] if pos == "PF" else ["SF"])
    if "C" in rp:
        out += ["C"] if pos != "C" else ["PF"]
    seen = []
    for p in out:
        if p in POSITIONS and p not in seen:
            seen.append(p)
    return seen or ["UTIL"]


def load_adp(rosters: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    norm = _norm_name()
    adp = pd.read_csv(ADP_PATH)
    adp["team_c"] = adp["team"].map(lambda t: TEAM_ALIASES.get(t, t))
    adp["name_norm"] = adp["player"].map(norm)
    r = rosters.copy()
    r["name_norm2"] = r["roster_name"].map(norm)
    key = {}
    for _, row in r.iterrows():
        key.setdefault((row["name_norm2"], row["team"]), []).append(row)
        key.setdefault((row["name_norm"], row["team"]), []).append(row)
    pids, rnames, problems = [], [], []
    for _, a in adp.iterrows():
        hits = key.get((a["name_norm"], a["team_c"]), [])
        uniq = {(h["roster_name"], h["player_id"] if pd.notna(h["player_id"]) else None) for h in hits}
        if len(uniq) == 1:
            name, pid = next(iter(uniq))
            pids.append(pid)
            rnames.append(name)
        else:
            pids.append(None)
            rnames.append(None)
            problems.append(f"{a['player']} ({a['team']}): {'ambiguous' if uniq else 'no roster match'}")
    adp["player_id"] = pids
    adp["roster_name"] = rnames
    return adp, problems


def build_board_data() -> dict:
    data = ingest.load_canonical(validate=False)
    config = project.load_league_config()
    rosters = data["rosters"]
    minutes_cfg = project.load_minutes_config()
    gp_cfg = project.load_games_played_config()
    projected = project.project_players(data, config, minutes_cfg, gp_cfg)

    pool_size = config["valuation"].get("draft_pool_size", config["valuation"]["pool_size"])
    pool_ids, _ = value.select_draftable_pool(projected, pool_size)
    with_impact = value.add_percentage_impact(projected, pool_ids)
    valued = value.zscore_value(with_impact, pool_ids, punt=[])
    fg_mean, ft_mean = value.pool_percentage_means(projected, pool_ids)

    adp, adp_problems = load_adp(rosters)
    adp_by_pid = adp.dropna(subset=["player_id"]).set_index("player_id")
    injuries = (yaml.safe_load(INJURIES_PATH.read_text(encoding="utf-8")) or {}).get("injuries", {})

    roster_rows = rosters.dropna(subset=["player_id"]).drop_duplicates("player_id").set_index("player_id")
    last_pos = (data["player_seasons"].sort_values("season").groupby("player_id")["pos"].last())

    players = []
    for pid, row in valued.iterrows():
        rr = roster_rows.loc[pid] if pid in roster_rows.index else None
        a = adp_by_pid.loc[pid] if pid in adp_by_pid.index else None
        if a is not None:
            positions = [p.strip() for p in str(a["positions"]).split(",") if p.strip() in POSITIONS]
        else:
            positions = fallback_positions(last_pos.get(pid), rr["pos_roster"] if rr is not None else None)
        inj = injuries.get(pid) or {}
        players.append({
            "id": pid,
            "name": rr["roster_name"] if rr is not None else pid,
            "team": row["team"],
            "pos": positions,
            "posSrc": "yahoo" if a is not None else "bbref",
            "age": int(rr["age_at_season_start"]) if rr is not None and pd.notna(rr["age_at_season_start"]) else None,
            "mpg": round(float(row["mpg"]), 1),
            "gp": int(row["gp"]),
            "minEst": bool(row["minutes_estimated"]),
            "s": {  # per-game stat line
                "PTS": round(row["PTS"], 1), "REB": round(row["REB"], 1), "AST": round(row["AST"], 1),
                "STL": round(row["STL"], 2), "BLK": round(row["BLK"], 2), "3PM": round(row["3PM"], 1),
                "TOV": round(row["TOV"], 1), "FGP": round(row["FG_PCT"], 3), "FTP": round(row["FT_PCT"], 3),
                "FGA": round(row["FGA"], 1), "FTA": round(row["FTA"], 1),
            },
            "z": {c: round(float(row[f"z_{c}"]), 3) for c in CATS},
            "adp": None if a is None or pd.isna(a["yahoo_adp"]) else float(a["yahoo_adp"]),
            "adpAvg": None if a is None else float(a["avg_adp"]),
            "inj": inj.get("note", ""),
            "inPool": pid in pool_ids,
        })

    # ADP-listed players with no projection (rookies / no NBA history)
    projected_ids = set(valued.index)
    for _, a in adp.iterrows():
        if a["team_c"] == "FA":
            continue
        pid = a["player_id"] if pd.notna(a["player_id"]) else None
        if pid is not None and pid in projected_ids:
            continue
        players.append({
            "id": pid or f"np_{a['name_norm'].replace(' ', '_')}",
            "name": a["roster_name"] if pd.notna(a["roster_name"]) else a["player"],
            "team": a["team_c"],
            "pos": [p.strip() for p in str(a["positions"]).split(",") if p.strip() in POSITIONS],
            "posSrc": "yahoo",
            "np": True,
            "adp": None if pd.isna(a["yahoo_adp"]) else float(a["yahoo_adp"]),
            "adpAvg": float(a["avg_adp"]),
            "inj": (injuries.get(pid) or {}).get("note", "") if pid else "",
        })

    return {
        "generated": pd.Timestamp.now(tz="America/Chicago").strftime("%Y-%m-%d %H:%M %Z"),
        "league": {
            "teams": config["league"]["teams"],
            "rounds": config["league"].get("draft_rounds", 13),
            "slots": config["league"]["roster_slots"],
        },
        "poolSize": pool_size,
        "poolMeans": {"FG": round(fg_mean, 4), "FT": round(ft_mean, 4)},
        "cats": CATS,
        "adpSource": "FantasyPros consensus ADP (Yahoo + ESPN), fetched 2026-10-14",
        "adpUnmatched": adp_problems,
        "players": players,
    }


def write_board_data(path: Path = OUT_PATH) -> Path:
    board = build_board_data()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, separators=(",", ":")), encoding="utf-8")
    return path
