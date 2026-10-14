"""Embed reports/board_data.json into the draft board page.

Usage: python -m src.cli board && python scripts/build_board_page.py
Writes board/draft_board.html, a single self-contained page (no network calls
besides Google Fonts) that runs the live draft: log picks, switch punts, see
your roster and category profile. State is kept in the browser's localStorage.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
template = (ROOT / "board" / "draft_board.template.html").read_text(encoding="utf-8")
data = (ROOT / "reports" / "board_data.json").read_text(encoding="utf-8").replace("</", "<\\/")
assert "/*BOARD_DATA*/" in template
out = ROOT / "board" / "draft_board.html"
out.write_text(template.replace("/*BOARD_DATA*/", data), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
