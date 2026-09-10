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
`fga_p100`, `fta_p100`, `trb_p100`, `ast_p100`, `tov_p100`.

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

## `rosters_2627.csv` — 517 rows

2026-27 active rosters as of **2026-08-20**, parsed from the Wikipedia roster templates.
30 teams, 14-20 players each.

| column | notes |
|---|---|
| `team` | Canonical code |
| `season` | `2026-27` |
| `roster_name` | As written on the roster |
| `name_norm` | Normalized form used for matching |
| `pos_roster` | Wikipedia position (`G`, `F/C`, ...). Coarser than BBRef's `pos` |
| `jersey` | int. **Not unique per team** — 10 collisions exist in the source, mostly #0 for unsigned rookies. Never use as a key |
| `two_way` | bool. 74 of 517. Minimal fantasy relevance; filter early |
| `height_in`, `weight_lb` | int |
| `dob` | ISO date. More precise than BBRef's integer `age` |
| `age_at_season_start` | int, computed against 2026-10-21 |
| `player_id` | BBRef ID, or **empty if unmatched** |
| `match` | `exact` / `none` / `ambiguous` |

440 of 517 matched to BBRef history (394 of 443 standard contracts). The 77 unmatched
are 28 two-way players and 49 aged 22 or under — rookies and international signings with
no NBA season in 2023-26. **This is expected, not a defect.**

---

## `crosswalk_unmatched.csv` — 77 rows

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

## `unrostered_players.csv` — 150 rows

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
| `pts_p100_wtd_vacated` | Minute-weighted per-100 scoring of the departed group — distinguishes losing a star from losing bench filler |
| `n_departed` | Headcount |

Observed range 6.2% to 57.6%, so this genuinely discriminates.

**Caveat:** a returning player who failed the crosswalk would be counted as departed.
The fuzzy-suggestion check above is what guards against that, so keep it passing.

---

## Known limitations

- **`pace_simple` is biased high.** Documented, retained for cross-checking only.
- **Rosters are a 2026-08-20 snapshot.** Trades and camp cuts since are not reflected,
  and training-camp battles were unresolved at that date.
- **Positions are coarse.** `pos_roster` is Wikipedia's; `pos` in `player_seasons` is
  BBRef's. Neither reflects fantasy-site eligibility, which is what your league actually
  uses. Reconcile against your platform before trusting positional scarcity math.
- **No 2026-27 projections here.** This is cleaned input only.
- **No minutes or games-played projections.** Those are human judgment; see spec §3.5.
