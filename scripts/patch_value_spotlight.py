"""One-off patch (2026-10-19): add the value spotlight to both board templates.

A "value" player is in the top VALUE_TOP available by board score, and the market
(ADP rank among the same available players) takes him at least one round
(TEAMS spots) later than the board ranks him. Every value player gets a tag and a
highlighted board row; the three best-scoring ones not already in the top six
cards get their own row of cards.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sub(text, old, new, count=1):
    assert text.count(old) == count, (old[:80], text.count(old))
    return text.replace(old, new)


CSS = """.card.value { border-color: var(--value); box-shadow: 0 0 0 1px var(--value) inset; }
.tag.value { background: var(--value-soft); border-color: transparent; color: var(--value); }
tr.p.val td:first-child { box-shadow: inset 3px 0 0 var(--value); }
.valhead { font-family: var(--display); font-weight: 700; font-size: 16px; letter-spacing: .02em; color: var(--value); margin: 12px 0 6px;
  display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.valhead small { font-family: var(--body); font-weight: 500; font-size: 12px; color: var(--muted); letter-spacing: 0; }
.waitline {"""

HTML = """<div class="sugg" id="sugg"></div>
        <div id="valueWrap" hidden>
          <div class="valhead">Value picks <small>In the board's top 20 available, but the market takes them at least a round later. +N is how many spots later.</small></div>
          <div class="sugg" id="valueSugg"></div>
        </div>"""

# computed right after recAvail; uses every available player with an ADP (rookies
# included, since the market drafts them) to rank by ADP
VALUE_JS = """
    // value spotlight: top-20 available by board score whose ADP rank among the same
    // available players is at least a round later than their board rank
    const VALUE_TOP = 20, VALUE_GAP = TEAMS;
    const adpRank = new Map(players.filter(p => !T.has(p.id) && !skipped(p))
      .sort((a, b) => (a.adp ?? 999) - (b.adp ?? 999)).map((p, i) => [p.id, i + 1]));
    const valueInfo = new Map();
    recAvail.slice(0, VALUE_TOP).forEach((p, i) => {
      const a = adpRank.get(p.id), gap = a - (i + 1);
      if (gap >= VALUE_GAP) valueInfo.set(p.id, { b: i + 1, a, gap });
    });
    const valueTag = p => {
      const v = valueInfo.get(p.id);
      return v ? `<span class="tag value" title="Board ranks him #${v.b} available; ADP ranks him #${v.a} available">Value +${v.gap}</span>` : "";
    };
"""

VALUE_ROW_JS = """
    const valuePicks = recAvail.filter(p => valueInfo.has(p.id) && !top.includes(p)).slice(0, 3);
    el("valueSugg").innerHTML = valuePicks.map(p => cardHtml(p, "value")).join("");
    el("valueWrap").hidden = !valuePicks.length;
"""


def patch_common(t):
    t = sub(t, "  --mine: #1f4fd1;\n", "  --mine: #1f4fd1;\n  --value: #8a3fc4;\n  --value-soft: #f1e6fa;\n")
    t = sub(t, "--good-soft: #15302b; --mine: #7d9cff; color-scheme: dark;",
            "--good-soft: #15302b; --mine: #7d9cff; --value: #c99bf0; --value-soft: #2c1f3b; color-scheme: dark;", count=2)
    t = sub(t, ".waitline {", CSS)
    t = sub(t, '<div class="sugg" id="sugg"></div>', HTML)
    t = sub(t, "    const recAvail = state.only.length ? avail.filter(p => !skipped(p)) : avail;\n",
            "    const recAvail = state.only.length ? avail.filter(p => !skipped(p)) : avail;\n" + VALUE_JS)
    # keep the "also likely there" line from repeating the value cards
    t = sub(t, "score.get(p.id) > topScore * 0.6 && !top.includes(p)).slice(0, 4);",
            "score.get(p.id) > topScore * 0.6 && !top.includes(p) && !valuePicks.includes(p)).slice(0, 4);")
    return t


def patch_9cat(t):
    t = patch_common(t)
    old_open = """    el("sugg").innerHTML = top.map((p, i) => {
      const fill = fillInfo.get(p.id);
      return `<div class="card ${i === 0 ? "best" : ""}">"""
    new_open = """    const cardHtml = (p, cls) => {
      const fill = fillInfo.get(p.id);
      return `<div class="card ${cls}">"""
    t = sub(t, old_open, new_open)
    t = sub(t, """<div class="tags">${availTag(p, ctx)}${fill ? `<span class="tag fill">Fills ${fill === "UTIL" ? "Util" : fill}</span>` : ""}${p.adp != null ? `<span class="tag">ADP ${p.adp}</span>` : ""}${p.inj ? `<span class="tag inj" title="${esc(p.inj)}">Injury</span>` : ""}${p.minEst""",
            """<div class="tags">${valueTag(p)}${availTag(p, ctx)}${fill ? `<span class="tag fill">Fills ${fill === "UTIL" ? "Util" : fill}</span>` : ""}${p.adp != null ? `<span class="tag">ADP ${p.adp}</span>` : ""}${p.inj ? `<span class="tag inj" title="${esc(p.inj)}">Injury</span>` : ""}${p.minEst""")
    old_close = """        <div class="acts"><button type="button" class="mini mine" data-mine="${p.id}">Mine</button><button type="button" class="mini" data-take="${p.id}">Taken</button></div>
      </div>`;
    }).join("");

    // can-wait line"""
    new_close = """        <div class="acts"><button type="button" class="mini mine" data-mine="${p.id}">Mine</button><button type="button" class="mini" data-take="${p.id}">Taken</button></div>
      </div>`;
    };
    el("sugg").innerHTML = top.map((p, i) => cardHtml(p, i === 0 ? "best" : "")).join("");
""" + VALUE_ROW_JS + """
    // can-wait line"""
    t = sub(t, old_close, new_close)
    # board table rows
    t = sub(t, """      return `<tr class="p ${t ? "taken" : ""} ${t && t.mine ? "mine" : ""}">""",
            """      return `<tr class="p ${t ? "taken" : ""} ${t && t.mine ? "mine" : ""} ${!t && valueInfo.has(p.id) ? "val" : ""}">""")
    t = sub(t, """<td><div class="nm">${esc(p.name)} ${p.inj ? `<span class="tag inj" title="${esc(p.inj)}">Inj</span>` : ""}</div>""",
            """<td><div class="nm">${esc(p.name)} ${t ? "" : valueTag(p)} ${p.inj ? `<span class="tag inj" title="${esc(p.inj)}">Inj</span>` : ""}</div>""")
    return t


def patch_highscore(t):
    t = patch_common(t)
    old_open = """    el("sugg").innerHTML = top.map((p, i) => {
      const g = gm.get(p.id), fill = fillInfo.get(p.id);
      return `<div class="card ${i === 0 ? "best" : ""}">"""
    new_open = """    const cardHtml = (p, cls) => {
      const g = gm.get(p.id), fill = fillInfo.get(p.id);
      return `<div class="card ${cls}">"""
    t = sub(t, old_open, new_open)
    t = sub(t, """<div class="tags">${availTag(p, ctx)}${fill ? `<span class="tag fill">Fills""",
            """<div class="tags">${valueTag(p)}${availTag(p, ctx)}${fill ? `<span class="tag fill">Fills""")
    old_close = """        <div class="acts"><button type="button" class="mini mine" data-mine="${p.id}">Mine</button><button type="button" class="mini" data-take="${p.id}">Taken</button></div>
      </div>`;
    }).join("");

    if (ctx.target) {"""
    new_close = """        <div class="acts"><button type="button" class="mini mine" data-mine="${p.id}">Mine</button><button type="button" class="mini" data-take="${p.id}">Taken</button></div>
      </div>`;
    };
    el("sugg").innerHTML = top.map((p, i) => cardHtml(p, i === 0 ? "best" : "")).join("");
""" + VALUE_ROW_JS + """
    if (ctx.target) {"""
    t = sub(t, old_close, new_close)
    t = sub(t, """      return `<tr class="p ${t ? "taken" : ""} ${t && t.mine ? "mine" : ""}">""",
            """      return `<tr class="p ${t ? "taken" : ""} ${t && t.mine ? "mine" : ""} ${!t && valueInfo.has(p.id) ? "val" : ""}">""")
    t = sub(t, """<td><div class="nm">${esc(p.name)} ${p.inj ? `<span class="tag inj" title="${esc(p.inj)}">Inj</span>` : ""}</div>""",
            """<td><div class="nm">${esc(p.name)} ${t ? "" : valueTag(p)} ${p.inj ? `<span class="tag inj" title="${esc(p.inj)}">Inj</span>` : ""}</div>""")
    return t


for name, fn in [("draft_board.template.html", patch_9cat), ("highscore_board.template.html", patch_highscore)]:
    path = ROOT / "board" / name
    text = path.read_text(encoding="utf-8")
    assert "valueInfo" not in text, f"{name} already patched"
    path.write_text(fn(text), encoding="utf-8")
    print("patched", name)
