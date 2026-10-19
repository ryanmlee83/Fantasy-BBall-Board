"""Embed reports/board_data.json into the draft board page.

Usage: python -m src.cli board && python scripts/build_board_page.py [9cat|highscore]
Writes board/draft_board.html, a single self-contained page (no network calls
besides Google Fonts) that runs the live draft: log picks, switch punts, see
your roster and category profile. State is kept in the browser's localStorage.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
PAGES = {"9cat": ("draft_board.template.html", "draft_board.html"),
         "highscore": ("highscore_board.template.html", "highscore_board.html"),
         "9cat_239233": ("draft_board.template.html", "draft_board_239233.html"),
         "9cat_260146": ("draft_board.template.html", "draft_board_260146.html")}
# per-page changes on top of the template: 10-team league 239233 uses a 130-player
# replacement pool, its own saved state, and no punt guide (simulated for 12 teams)
VARIANTS = {"9cat_239233": {
    "teams": 10, "pool": 130, "drop_guide": True,
    "text": [("<title>Prize 20 Draft Board</title>", "<title>League 239233 Draft Board</title>"),
             ("<h1>Prize 20 Draft Board</h1>", "<h1>League 239233 Draft Board</h1>"),
             ('const STORE_KEY = "prize20-draft-238445";', 'const STORE_KEY = "draft-239233";'),
             ("Yahoo H2H 9-cat · 12 teams · 13 rounds", "Yahoo H2H 9-cat · 10 teams · 13 rounds"),
             ("(12 teams × 13 picks)", "(10 teams × 13 picks)")]},
    # Zalgiris league 260146: 12 teams like Prize 20, but 1 C, 4 Util and 2 bench.
    # Keeps the 12-team punt guide (simulated with Prize 20's roster, close enough).
    "9cat_260146": {
    "teams": 12, "pool": 156, "drop_guide": False,
    "slots": {"PG": 1, "SG": 1, "G": 1, "SF": 1, "PF": 1, "F": 1, "C": 1, "UTIL": 4, "BENCH": 2, "IL": 3},
    "text": [("<title>Prize 20 Draft Board</title>", "<title>Zalgiris Draft Board</title>"),
             ("<h1>Prize 20 Draft Board</h1>", "<h1>Zalgiris Draft Board</h1>"),
             ('const STORE_KEY = "prize20-draft-238445";', 'const STORE_KEY = "draft-260146";'),
             ("Yahoo H2H 9-cat · 12 teams · 13 rounds", "Yahoo H2H 9-cat · league 260146 · 12 teams · 13 rounds"),
             ('const START_SLOTS = ["PG", "SG", "G", "SF", "PF", "F", "C", "C", "UTIL", "UTIL"];',
              'const START_SLOTS = ["PG", "SG", "G", "SF", "PF", "F", "C", "UTIL", "UTIL", "UTIL", "UTIL"];'),
             ("[0, 1, 2].map(i => `<span class=\"s\">BN</span>", "[0, 1].map(i => `<span class=\"s\">BN</span>"),
             ("benchIds.length > 3 ?", "benchIds.length > 2 ?"),
             ("benchIds.slice(3)", "benchIds.slice(2)")]}}
board = json.loads((ROOT / "reports" / "board_data.json").read_text(encoding="utf-8"))
guide = ROOT / "reports" / "punt_by_slot.json"
if guide.exists():  # from scripts/simulate_punts.py
    board["puntGuide"] = json.loads(guide.read_text(encoding="utf-8"))
for key in (sys.argv[1:] or PAGES):
    tpl_name, out_name = PAGES[key]
    template = (ROOT / "board" / tpl_name).read_text(encoding="utf-8")
    assert "/*BOARD_DATA*/" in template
    b = json.loads(json.dumps(board))
    v = VARIANTS.get(key)
    if v:
        b["league"]["teams"], b["poolSize"] = v["teams"], v["pool"]
        if v.get("slots"):
            b["league"]["slots"] = v["slots"]
        if v.get("drop_guide"):
            b.pop("puntGuide", None)
        for old, new in v["text"]:
            assert old in template, old
            template = template.replace(old, new)
    data = json.dumps(b, separators=(",", ":")).replace("</", "<\\/")
    out = ROOT / "board" / out_name
    out.write_text(template.replace("/*BOARD_DATA*/", data), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
