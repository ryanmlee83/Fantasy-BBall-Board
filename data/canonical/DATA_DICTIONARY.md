# Canonical Dataset — Data Dictionary

Generated from the nine raw sources in the project folder. All source quirks are
already resolved. **Do not re-ingest the raw files** — start here.

Conventions across every file:
- UTF-8, comma-delimited, LF line endings, one header row, no BOM.
- `snake_case` column names. No `%`, `/`, or spaces in any header.
- Empty string means genuinely missing/not-applicable. It never means zero.
- Primary key for players is `player_id` (Basketball Reference ID, e.g. `hardeja01`).
  **Never join on player name.**
- Team codes are canonical 3-letter Basketball Reference abbreviations everywhere.
- Season is a string, `2025-26` format.

---

## `teams.csv` — 30 rows

The team registry. Join target for every `team` column.

| column | type | notes |
|---|---|---|
| `team` | str | Canonical code. BBRef convention: **BRK, CHO, PHO** (not BKN/CHA/PHX) |
| `team_name` | str | Full name |
| `conference` | str | East / West |
| `division` | str | |
| `aliases` | str | Pipe-delimited alternates seen in source data, for future ingestion |

The alias list is why the NBA.com-format team stats and the BBRef player files now agree.
If you add a data source with different abbreviations, extend the aliases here rather
than writing a second mapping.

---

## `player_seasons.csv` — 1,723 rows, 56 cols

One row per player-season. Per-100 and advanced stats already merged. Traded players
are **deduplicated to their combined season line**.

| column | type | notes |
|---|---|---|
| `player_id` | str | PK with `season` |
| `player_name` | str | Display only |
| `season` | str | |
| `age` | int | Age during that season, per BBRef |
| `team` | str | Canonical code, or **empty if the player was traded** |
| `teams_played` | str | Team code, or `2TM`/`3TM`/`4TM` for traded players |
| `multi_team` | bool | True if traded mid-season |
| `pos` | str | BBRef position |
| `g`, `gs`, `mp` | int | **Raw season totals**, not per-100 |
| `mpg` | float | Derived: `mp / g` |
| `*_p100` | float | Per-100-possessions rates: `fg`, `fga`, `fg3`, `fg3a`, `fg2`, `fg2a`, `ft`, `fta`, `orb`, `drb`, `trb`, `ast`, `stl`, `blk`, `tov`, `pf`, `pts` |
| `fg_pct`, `fg3_pct`, `fg2_pct`, `ft_pct`, `efg_pct`, `ts_pct` | float | **Empty when attempts were zero.** Do not `fillna(0)` |
| `ortg`, `drtg` | int | |
| advanced | float | `per`, `fg3a_rate`, `ft_rate`, `orb_pct`, `drb_pct`, `trb_pct`, `ast_pct`, `stl_pct`, `blk_pct`, `tov_pct`, `usg_pct`, `ows`, `dws`, `ws`, `ws48`, `obpm`, `dbpm`, `bpm`, `vorp` |

Counts: 572 (2023-24), 569 (2024-25), 582 (2025-26). 802 distinct players; 374 in all three.

**Use this file for player-level projection work.**

---

## `player_team_seasons.csv` — 1,972 rows

One row per player-**team stint**. Traded players appear once per team; everyone else
appears once. Every row has a real team code — no `2TM` placeholders.

Columns: `player_id`, `player_name`, `season`, `team`, `g`, `mp`, `pts_p100`,
`fga_p100`, `fta_p100`, `trb_p100`, `ast_p100`, `tov_p100`, `stl_p100`, `blk_p100`,
`fg3_p100`, `usg_pct`, `ts_pct`, `bpm`.

Per-stint advanced stats (`usg_pct`, `ts_pct`, `bpm`) come from the advanced source
files, which carry the same team-split structure as the per-100 files. So usage is
available for traded players on a per-team basis, not only as a season combination.

**Use this file for any team-level rollup** (pace, vacated minutes, team totals).
Using `player_seasons.csv` instead silently drops every traded player from team sums,
which inflates implied pace by roughly 14%. This was a real bug during construction.

---

## `team_seasons.csv` — 30 rows

2025-26 team stats plus both pace estimates.

| column | notes |
|---|---|
| `team`, `team_name`, `season`, `gp`, `w`, `l` | |
| `pts_pg`, `fga_pg`, `fta_pg`, `oreb_pg`, `dreb_pg`, `tov_pg` | Per-game team averages |
| `pace_simple` | `FGA + 0.44×FTA − OREB + TOV`. Runs ~3% high (source lacks opponent columns needed for the full BBRef rebound correction). Cross-check only |
| `pace_implied` | **Use this one.** Solved from player per-100 points, minutes, and team scoring, so converting per-100 back to per-game reproduces actual team output exactly |
| `minutes_share` | Summed player minutes ÷ (240 × GP). Should be ~1.00; it is a data-integrity canary |

League average implied pace **99.36**; range 94.9 (BOS) to 103.4 (MIA).
Correlation between the two methods **0.971**; ratio 0.969.

2026-27 pace is a projection, not in this file. Default each team to its 2025-26
`pace_implied` and override per team in config for coaching changes.

---

## `rosters_2627.csv` — 598 rows

2026-27 rosters as of **2026-10-08**, built by `scripts/build_rosters_from_bbref.py`
from **Basketball Reference team pages** (`basketball-reference.com/teams/<T>/2027.html`),
one fetch per team, all 30 verified. This **supersedes the Wikipedia-derived docx parse**
in `harmonize.py` as the source of roster truth. 30 teams, 17-22 players each.

### Why the source changed

The docx was scored against BBRef across 10 teams and came in **92% precise** — but its
misses were not random. They clustered on recently-transacted players (Kawhi Leonard still
listed on LAC, Brandon Ingram still on TOR, DeMar DeRozan missing entirely), which is
exactly the population that matters most for minutes. A point-in-time export of a wiki page
goes stale silently; this had already been patched by hand twice.

BBRef also carries two things the docx does not:
- **native `player_id`**, so the crosswalk is a lookup rather than a name match. Name
  matching has caused three real bugs in this project (Moses Brown / Mikel Brown Jr.; the
  two Bridges — Mikal/NYK vs Miles/PHO; `V. J. Edgecombe` losing his leading initial to the
  Roman numeral five). This build had **zero ambiguous name matches**.
- **height, weight and date of birth**, so `age_at_season_start` — which feeds the §3 age
  curve — comes from the same fetch. **0 rows are missing a DOB.** The previous build needed
  a separate research pass for this.

### What changed against the 541-row docx build

| | count |
|---|---|
| rows | 541 → **598** |
| added | 91 |
| dropped | 34 |
| team reassigned | 10 |
| matched to `player_id` | **485** |
| no BBRef history (rookie / international / UDFA) | 113 |

The 10 team reassignments are precisely the players the 2026-09-21 session flagged as
roster-gap suspects, now confirmed: Bennedict Mathurin LAC→NOP, Brandon Ingram TOR→LAC,
Buddy Hield ATL→CHI, Devin Carter ATL→BOS, Dorian Finney-Smith CHO→ATL, Gradey Dick
TOR→LAC, Johni Broome LAC→MIL, Jordan Hawkins MEM→CHI, **Kawhi Leonard LAC→TOR**, Ryan
Nembhard ATL→DEN.

Consequential additions (1,000+ minutes in 2025-26, previously on no roster at all):
DeMar DeRozan (DEN, 2,406 min), Bruce Brown (NYK, 1,998), Rui Hachimura (LAC, 1,927),
Nicolas Batum (LAC, 1,295).

Two apparent drop/add pairs are **spelling variants, not roster changes** — `Jakob Pöltl` →
`Jakob Poeltl` and `Sviatoslav Mykhailiuk` → `Svi Mykhailiuk`. Both resolve to the same
`player_id` (`poeltja01`, `mykhasv01`) and the same team, so the pipeline is unaffected;
only a naive name-keyed diff is fooled. This is why the diff above says 34 dropped / 91
added rather than 36 / 93.

### Known gaps in this build

- **`jersey` is empty for every row.** BBRef's roster table does not expose it through a
  plain fetch. Nothing in the pipeline consumes it — `scripts/validate.py` only prints a
  duplicate-jersey INFO line — so it is left null rather than fetched from a second source.
- **`two_way` is not fully sourced.** 505 rows carry the value forward from the docx build
  and **93 new rows default to `False`**. BBRef does expose two-way status, but it needs its
  own fetch per team. This field feeds `reports.py`'s standard-contract filter and the
  `validate.py` counts; it does **not** touch minutes, projections or valuation, so an
  imperfect value degrades a report line rather than the model. Flagged rather than
  papered over.

### Derived files regenerated with it

`crosswalk_unmatched.csv` (113 rows, **0 with a fuzzy suggestion** — no unmatched name is a
near-neighbour of an existing player, which is the guard that caught the Mikel Brown Jr.
error), `unrostered_players.csv` (119 rows), and `vacated_opportunity.csv`. The test suite
asserts `crosswalk_unmatched` has exactly as many rows as the roster has unmatched entries,
so these three must move together — three tests correctly failed when they did not.

## `crosswalk_unmatched.csv` — 113 rows

Roster entries with no `player_id`, each with a `fuzzy_suggestion` column.

**The invariant that matters: this column should be empty for every row.** A populated
suggestion means name normalization failed, not that the player is new. Two real bugs
surfaced this way during construction:

- The generational-suffix stripper was matching anywhere in the string, so
  `V. J. Edgecombe` lost its leading initial and became `j edgecombe`.
- Initials were being split, so BBRef's `P.J. Washington` did not match Wikipedia's
  `P. J. Washington`.

If a suggestion appears after adding a source, add a `NAME_ALIASES` entry rather than
loosening the matcher.

---

## `unrostered_players.csv` — 119 rows

Players with a 2025-26 season but no 2026-27 roster spot, sorted by minutes descending.
Retirements, unsigned free agents, and overseas departures. Worth one read-through:
anyone here with heavy minutes who you believe is still in the league indicates a
crosswalk miss rather than a real absence.

---

## `vacated_opportunity.csv` — 30 rows

Per team, how much 2025-26 playing time belongs to players no longer on the roster.
The strongest quantitative breakout signal derivable from this data.

| column | notes |
|---|---|
| `mp_2526_single_team` | Team's total 2025-26 player-minutes |
| `mp_vacated` | Minutes belonging to departed players |
| `pct_vacated` | Percentage |
| `pts_p100_wtd_vacated` | Minute-weighted per-100 scoring of the departed group |
| `usg_wtd_vacated` | Minute-weighted average usage rate of the departed group |
| `usg_minutes_vacated` | Usage × minutes, the volume of shots and possessions freed. **This is the metric spec §3.5 calls for.** It ranks differently from raw minutes: a team can vacate many low-usage minutes (little opportunity freed) or fewer high-usage ones (a lot). Observed rank disagreements of up to 9 places between the two |
| `n_departed` | Headcount |

Observed range 6.2% to 57.6%, so this genuinely discriminates.

**Caveat:** a returning player who failed the crosswalk would be counted as departed.
The fuzzy-suggestion check above is what guards against that, so keep it passing.

---

## `../raw/realgm_depth_charts_20260921.txt` — depth-chart capture

RealGM depth charts (`basketball.realgm.com/nba/depth-charts`), captured 2026-09-21 and
checked in so it survives between sessions. Pipe-delimited: `tier|PG|SG|SF|PF|C`, one line
per tier row, `EMPTY` for a blank cell, preceded by `TEAM=<abbrev> ROWS=<n>`. Names are
verbatim and often abbreviated (`N. Alexander-Walker`, `R. Harper, Jr.`).

**All 30 teams.** ATL-MIN were captured from the RealGM page directly. NOP-WAS were
supplied by Ryan as a workbook export of the same source — tiered rows with a stat sub-row
under each and a `<team> Leaders` block closing every section — converted by
`scripts/parse_depth_chart_workbook.py`, which anchors on the Leaders title as the section
boundary rather than guessing from blank rows (several teams' last tier has no stat
sub-row at all).

`scripts/depth_charts.py` parses it, crosswalks to `player_id`, and allocates minutes.
`scripts/apply_depth_minutes.py` writes the result into `config/minutes.yaml`.
The parser validates that every line has exactly 6 fields and that each team's parsed row
count matches its declared `ROWS=`; a dropped cell is a player whose minutes silently
vanish, so it raises rather than warns. That check has already caught one bad capture.

### Allocation method

Starters get a **fixed 33 mpg**; the bench splits the remaining 75 by rotation tier
(weights 1.0 / 0.45 / 0.20 / 0.10 down the Rotation rows), and `Lim PT` gets 0.

Two approaches were tried and rejected first, both worth recording:

- **48 minutes per position, split down a depth curve** (the earlier ESPN-era method).
  RealGM does not cover positions evenly — DAL lists exactly one PG — so this hands that
  player 48 mpg. Allocation has to be team-level.
- **Weighting every tier and normalising the whole team to 240.** Teams list very
  different numbers of reserves (ATL 8, MIA 6), so normalising across all of them drags
  deep teams' starters down: Luka came out at 27.5 mpg and Derrick White at 25.0. Real
  rotations hold starters near 32-35 regardless of bench depth and squeeze the back end.

### Roster gaps this surfaced

Cross-referencing the chart against `rosters_2627.csv` found two real problems.

**Players on the RealGM chart with no roster row at all** — their minutes never reach the
model, which is precisely why LAC (76.3%), DEN (86.3%) and CHO (86.2%) fail the §3.5
sanity check:

| player | RealGM team / role | mpg lost |
|---|---|---|
| DeMar DeRozan | DEN, **starting SF** | 28.1 |
| Brandon Ingram | LAC, **starting SF** | 25.6 |
| Bez Mbeng | CHO, **starting SG** | 24.4 |
| Rui Hachimura | LAC, rotation | 16.0 |
| Gradey Dick | LAC, rotation | 10.4 |
| Yuki Kawamura | LAC, rotation | 10.4 |
| Moussa Cisse | DAL, rotation | 7.6 |
| Devin Carter | BOS, rotation | 6.3 |

Adding the other 12 teams extended the same pattern rather than contradicting it:
Jakob Poeltl (TOR, **starting C**), Emanuel Sharp (SAC, **starting PG**), Anthony Gill
(WAS), and four NYK rotation players (Bruce Brown Jr., James Wiseman, Ochai Agbaji, Drew
Eubanks, John Konchar) have no roster row either. Two earlier puzzles resolved themselves:
**Kawhi Leonard is on TOR**, not LAC, and **Bennedict Mathurin is on NOP**, not LAC — both
were previously logged as "rostered but missing from their team's chart", which was the
same staleness seen from the other side. 18 unmatched entries carry 258 mpg in total.

Five of these (Mbeng, Cisse, DeRozan, Hachimura, Kawamura) are exactly the players the
2026-09-21 `harmonize.py` re-run removed, on the finding that they were "confirmed absent
from both current docx sources by direct text search — not a parsing gap." That was true
of the docx and wrong about reality: **the Wikipedia-derived roster docs are stale**, not
merely differently-parsed. Ingram, Dick and Carter are a second class — on the roster file
but on the *wrong team*. LAC is the worst affected, missing four rotation players.

This is the second time this class of bug has appeared. The roster docx should not be
treated as authoritative for team assignment without a current cross-check.

**Rostered players absent from any chart** — set to 0 mpg but deliberately left
`estimated: true`, because absence is an open question, not a decision. Nine in total.
Jalen Duren (DET, 28.2 mpg last season) is the notable one: he is the `(FA)`-tagged player
the harmonize regex fix recovered, and he appears on no team's depth chart, so the tag was
flagging real roster uncertainty and he may be a phantom entry.

### Name-matching traps hit and fixed

- **`"v"` is both an initial and a Roman numeral.** Stripping suffix tokens anywhere in a
  name dropped the leading initial of `V. J. Edgecombe`, so PHI's starting SG matched
  nothing and silently lost 33 mpg. Suffixes are now stripped from the tail only.
- **The two sources punctuate initials differently** (`V.J.` vs `V. J.`). Leading
  single-letter tokens are now concatenated so both normalise to `vj`.
- **One genuine ambiguity, resolved by evidence rather than by loosening the matcher.**
  OKC lists `J. Williams` at C in the rotation *and* `Jalen Williams` at SF among the
  starters; since Jalen is already placed, the centre is Jaylin Williams (`willija07`).
  That sits in `MANUAL_MATCHES` in `scripts/depth_charts.py` with its reasoning. The
  matcher itself still refuses to guess — it correctly declined to match LAC's
  `Baba Miller` to the rostered `Jordan Miller`, which is the Mikel Brown Jr. pattern.

### Two config bugs fixed in passing

- **19 rostered players had no `games_played.yaml` entry at all** (the session-2
  supplemental rows plus the two harmonize recoveries). `minutes_sanity_check` reads a
  missing GP as **0**, not 82, so those players contributed zero season minutes and their
  teams looked short for no visible reason — MEM read 81.3% purely from this. Seeded at
  the spec §3.5 default of 82, flagged `estimated: true`. The same 19 were missing from
  `minutes.yaml` and were inserted there too.
- **`Σ mpg = 240` and `Σ(mpg × gp) = 19,680` are mutually incompatible** whenever any
  player's GP < 82 — mathematically, not approximately. LAL as hand-reviewed sums to 223
  mpg and 15,375 season minutes (78.1%); at its own GP profile `Σ mpg` would need to be
  ~285 to reach target. So LAL's shortfall is **not** mainly Cameron Carr's unmodeled
  minutes and conservative GP as documented earlier — those are second-order. Left
  unfixed for now (it changes the model's constraint and that's a judgement call), but the
  sanity check will keep flagging properly-reviewed teams while naive ones look fine.

---

## Known limitations

- **`pace_simple` is biased high.** Documented, retained for cross-checking only.
- **Rosters are a 2026-10-08 snapshot from Basketball Reference**; see the
  `rosters_2627.csv` section above. Transactions since are not reflected.
- **The depth-chart capture is now the stale input, not the rosters.** It dates from
  2026-09-21 and 11 of its entries put a player on a team the current rosters disagree
  with, which is the entire remaining cause of the §3.5 sanity misses on SAC, CHO, ATL and
  CHI. Re-capturing the depth charts is the next refresh, not the rosters.
- **Positions are coarse.** `pos_roster` is Wikipedia's; `pos` in `player_seasons` is
  BBRef's. Neither reflects fantasy-site eligibility, which is what your league actually
  uses. Reconcile against your platform before trusting positional scarcity math.
- **No 2026-27 projections here.** This is cleaned input only.
- **Minutes are depth-chart-derived for 29 teams; LAL is hand-reviewed.** See the
  depth-chart section above. GP is now projected (see the 2026-10-14 section below). Spec §3.5
  still applies: these are a reviewable first pass, not a substitute for judgment.
- **25 of 30 teams pass the §3.5 sanity check** after the BBRef roster rebuild, up from 22.
  All five that don't are fully explained, and the cause has flipped from stale rosters to a
  stale depth chart: SAC 83.4% and CHO 84.1% (RealGM gives a starter's minutes to Emanuel
  Sharp — a genuine rookie with no BBRef history to project from — and to Bez Mbeng, whom
  BBRef puts on MIA); ATL 89.8% and CHI 96.7% (Buddy Hield, Ryan Nembhard and Rob
  Dillingham have since moved); LAL 78.1% unchanged (hand-set GP plus Cameron Carr's
  unmodeled minutes).
- **BPM/VORP does not predict minutes.** Tested directly (train 23-24 + 24-25, predict
  25-26): value above replacement adds +0.006 R² over prior minutes, and as a standalone
  allocator is far worse (MAE 10.4 vs 6.8 mpg, corr 0.32 vs 0.45). It systematically
  promotes small-sample efficiency specialists and demotes high-volume low-efficiency
  starters. Don't let it set minutes; it's an auditor at best.


---

## Draft-day changes (2026-10-14)

Made under the project-director handoff, the day before the 2026-10-15 draft. Each is a
script, so the chain can be rerun from the Sept 21 depth-chart minutes:

```
python scripts/adjust_starter_minutes.py      # starter rule + promotion rule
python scripts/reconcile_minutes_with_adp.py  # stale minutes for drafted players
python scripts/project_games_played.py        # GP from history + config/injuries.yaml
python -m src.cli build && python -m src.cli board
python scripts/simulate_punts.py              # optional, ~30 s
python scripts/build_board_page.py            # -> board/draft_board.html
```

**`config/minutes.yaml` now means healthy-night minutes.** The healthy rotation must sum
to 240 per team (25/30 pass; the five that don't are the stale-chart teams SAC, CHO, ATL,
CHI and LAL's unmodeled Cameron Carr). `mpg × GP` against 240 × 82 is reported as
coverage only: once GP is projected below 82, the gap is minutes covered by whoever
replaces injured players, which in H2H arrive through waivers.

**Starter minutes.** Flat 33 for every starter is replaced by each starter's own history
when it is a stable two-season outlier (up to 37, or down to 26 for starters 31+), and new
starters with no starter history go halfway from their history to 33. Changes in
`reports/starter_minutes_adjustments.csv`.

**Stale minutes for drafted players.** Haliburton, Irving and Lillard were at 0 mpg; Trae
Young 13, Jaylen Brown 15, LaMelo Ball 19, Jalen Duren 0. Players with average ADP ≤ 160
whose minutes sit 6+ below their history are raised toward it (all the way by ADP 60,
halfway by ADP 160). Changes in `reports/minutes_adp_reconciliation.csv`.

**Games played** (`scripts/project_games_played.py`): 0.5 × history + 0.5 × 62, minus 1 per
year past 30, then known injuries from `config/injuries.yaml`. Backtest MAE 15.8 games vs
25.1 for a flat 82; GP is mostly unpredictable (R² 0.04 with history, age and minutes), so
the model shrinks hard. LAL hand values kept.

**Two age-curve bugs fixed in `src/project.py`.** The curve multiplied FG% and FT%
themselves (LeBron .515 → .360), and it was applied as an absolute level rather than the
change since the blended seasons (cutting a 20-year-old's rates instead of raising them).
Backtest MAE on the 150-player pool: PTS 2.27 → 2.02, FG impact .361 → .293, FT impact
.161 → .136; every category but BLK improved.

**ADP and Yahoo positions**: `data/raw/fantasypros_adp_20261014.csv`, matched to
`player_id` on normalised name + team (11 unmatched, 9 of them free agents).
