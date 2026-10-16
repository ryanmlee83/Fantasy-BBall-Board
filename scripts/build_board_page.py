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
         "highscore": ("highscore_board.template.html", "highscore_board.html")}
board = json.loads((ROOT / "reports" / "board_data.json").read_text(encoding="utf-8"))
guide = ROOT / "reports" / "punt_by_slot.json"
if guide.exists():  # from scripts/simulate_punts.py
    board["puntGuide"] = json.loads(guide.read_text(encoding="utf-8"))
data = json.dumps(board, separators=(",", ":")).replace("</", "<\\/")
for key in (sys.argv[1:] or PAGES):
    tpl_name, out_name = PAGES[key]
    template = (ROOT / "board" / tpl_name).read_text(encoding="utf-8")
    assert "/*BOARD_DATA*/" in template
    out = ROOT / "board" / out_name
    out.write_text(template.replace("/*BOARD_DATA*/", data), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
