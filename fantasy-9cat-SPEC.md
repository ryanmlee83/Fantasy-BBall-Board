# Fantasy Basketball 9-Cat Draft Engine — Build Spec

**Target league:** 12-team, head-to-head, 9-category (PTS, REB, AST, STL, BLK, 3PM, FG%, FT%, TO)
**Season:** 2026-27
**Language:** Python 3.11+. Pandas, NumPy, PyYAML. No web framework needed; CLI + CSV/Parquet output.

---

## 0. What this is

A projection and valuation pipeline that ingests three seasons of Basketball Reference
data plus current rosters, produces per-player 9-category projections for 2026-27, and
converts those into draft-board rankings under configurable punt scenarios.

**Design principle: the model is a calculator, not an oracle.** Every judgment input
(projected minutes, games played, pace) lives in a human-editable config file, not in
code. The pipeline's job is to be correct and reproducible given those inputs, and to
make it obvious when an input is missing or implausible.

**Non-goal:** scraping. All source data arrives as files. Do not write a Basketball
Reference scraper — their rate limit is 20 req/min and their data-use policy discourages
tool-building on scraped data. The manual export path works fine.

---

## 1. Input data — ALREADY HARMONIZED

**Do not write an ingestion layer for the raw Basketball Reference files.** They have
been cleaned, joined, validated, and written to canonical CSVs. Start from those.

Canonical inputs live in `data/canonical/`. See `DATA_DICTIONARY.md` for full column
definitions; the short version:

| File | Rows | Purpose |
|---|---|---|
| `teams.csv` | 30 | Team registry + alias table. Join target for all `team` columns |
| `player_seasons.csv` | 1,723 | One row per player-season, per-100 + advanced merged, traded players deduped to combined line. **Player-level work uses this** |
| `player_team_seasons.csv` | 1,972 | One row per player-team stint, real team codes only. **Team rollups use this** |
| `team_seasons.csv` | 30 | 2025-26 team stats + both pace estimates |
| `rosters_2627.csv` | 517 | 2026-27 rosters as of 2026-08-20, crosswalked to `player_id` |
| `crosswalk_unmatched.csv` | 77 | Roster entries with no BBRef history |
| `unrostered_players.csv` | 150 | 2025-26 players with no 2026-27 spot |
| `vacated_opportunity.csv` | 30 | Minutes and usage departed per team |

Guarantees already established, verified by `validate.py`:

- UTF-8, comma-delimited, `snake_case` headers, no `%` or `/` in column names.
- `player_id` is the universal key. **Never join on player name.**
- Team codes canonical everywhere (BBRef convention: `BRK`, `CHO`, `PHO`).
- Traded players deduplicated; combined and split views separated into two files.
- Percentage columns are **empty, not zero**, when attempts were zero. Preserve this —
  `fillna(0)` here corrupts the percentage-impact calculation in §4.2.
- Cross-season joins verified by age progression: 464/464 and 447/447 exact.
- Pace computed both ways; `pace_implied` (league avg 99.36) is the one to use.

### 1.1 The one trap worth stating explicitly

`player_seasons.csv` has a **blank `team`** for any player traded mid-season, because
their stat line is a league-wide combination. Summing that file by team silently omits
every traded player and inflates implied pace by ~14%. This happened during construction.

**Any team-level aggregation reads `player_team_seasons.csv`.** No exceptions.

---

## 2. Ingestion layer

Almost none required. Read the canonical CSVs, coerce dtypes, and assert the invariants
in §8.1-8.3 on load.

Two things the pipeline still owns:

1. **Dtype coercion.** Empty string to `None`/`NaN`, not to `0`. Confirm `ft_pct` is NaN
   for every row where `fta_p100 == 0` after loading.
2. **A `NAME_ALIASES` hook.** When a new source arrives with different name spellings,
   extend the alias table rather than loosening the matcher. Two known entries already:
   German transliteration (`Poeltl` vs `Pöltl`) and nicknames (`Svi`/`Sviatoslav`).

If raw files ever need re-ingesting, `harmonize.py` is the reference implementation and
documents every source quirk in comments.

## 3. Projection engine

Output: for each rostered player, projected per-game values in all nine categories
plus `FGA`, `FTA` (needed for percentage impact) and projected `GP`.

### 3.1 Rate basis

Work in **per-100 possessions** throughout. This is deliberate: with heavy roster
turnover, a player changing teams sees his per-game counting stats move purely from pace.
Per-100 isolates ability from context; pace is re-applied at the end (§3.5).

### 3.2 Multi-season blend

Weighted average of available seasons, most recent heaviest. Default weights
`[0.5, 0.3, 0.2]` for [2025-26, 2024-25, 2023-24], configurable.

When a season is missing, renormalize over available seasons — do not treat missing as
zero. **Weight within a season by minutes played**, so a 200-minute season contributes
less than a 2,400-minute one even at equal season weight.

### 3.3 Regression to the mean

Small-sample per-100 rates are the single largest error source in homemade projections.
Shrink each player's blended rate toward a positional baseline:

```
shrunk = (MP_total × observed + K_cat × positional_mean) / (MP_total + K_cat)
```

`K_cat` is a per-category constant in minutes, in config. Suggested starting values,
heaviest for the noisiest categories:

| Category | K (minutes) |
|---|---|
| STL | 1400 |
| BLK | 1400 |
| TOV | 900 |
| 3PM | 800 |
| AST | 600 |
| REB | 500 |
| PTS | 500 |
| FG% | 900 |
| FT% | 1100 |

These are starting guesses, not derived constants. Section 8.4 describes how to tune them
empirically. **Flag in the output that they are untuned until that runs.**

Positional baselines computed from the draftable pool (§4.1), by `Pos`, from the most
recent season.

### 3.4 Pace

Two methods, both implemented. **Default to `implied`.**

**`simple`** — from `team_stats.xlsx`:
```
poss_per_game ≈ FGA + 0.44×FTA − OREB + TOV
```
Runs ~3% high because the file lacks opponent columns needed for the full
Basketball-Reference offensive-rebound correction. Retained for cross-checking only.

**`implied`** — solved from the player data itself. For each team, team points per game
is known and every player's per-100 points and minutes are known, so possessions is the
only unknown:
```
Σ_players [ (PTS_per100_p / 100) × P × MP_p / (48 × GP_team) ]  =  PTS_per_game_team
```
Solve for `P`. Exclude multi-team players (their combined line can't be assigned to one
team). This is self-consistent by construction: converting per-100 back to per-game with
it reproduces actual team scoring exactly.

Verified: the two methods correlate at **r = 0.971**. League averages 102.6 (simple) vs
**99.4 (implied)**; ratio 0.969. Implied range 94.9 (BOS) to 103.4 (MIA).

Emit a warning if implied league-average pace falls outside 95-104 — that means the
input data or the team-name mapping broke.

**2026-27 pace** is a projection, not a measurement. Default each team to its 2025-26
implied pace, overridable per-team in config. Teams with coaching changes are the
obvious manual edits.

### 3.5 Minutes and games played — the judgment layer

**This is where the model's accuracy actually lives, and it is not computed.**

Generate `config/minutes.yaml`, one entry per rostered player, pre-populated with last
season's MPG as a starting point and flagged `estimated: true`. The user edits it. Any
player still marked `estimated: true` at run time appears in a warning list.

The pipeline computes one input to help: **vacated minutes and usage per team.** For each
2026-27 roster, sum the 2025-26 minutes and USG% of players no longer on it. Output
`reports/vacated_opportunity.csv` sorted by minutes vacated. This is the single strongest
quantitative signal for breakouts and it is fully derivable from data already in hand.

Enforce a sanity constraint: projected minutes per team must total 240 × 82 ± 3%. Report
teams that violate it rather than silently rescaling.

`config/games_played.yaml` works the same way — default 82, user edits down for injury
history, age, and load management. **Do not skip this.** Per-game value multiplied by
projected GP is what determines season totals, and a fragile roster that looks strong
per-game is exactly the failure mode the "high floor" goal is meant to avoid.

### 3.6 Age curve

Apply to shrunk per-100 rates, keyed on age at season start. Peak roughly 25-28.
Separate curves per category — steals and blocks decay earlier than assists and free
throw rate. Ship a simple piecewise-linear default in config; it is a first-order
correction, not a precision instrument.

### 3.7 Assembly

```
per_game_stat = shrunk_per100_rate / 100 × projected_pace × (projected_MPG / 48)
season_total  = per_game_stat × projected_GP
```

---

## 4. Valuation

### 4.1 Draftable pool

Z-scores must be computed against the **draftable pool**, not the full player universe.
Standardizing against all ~580 players compresses everyone toward the middle and makes
replacement level look far closer to star level than it is.

Default pool: **top 150 by projected minutes**. Rationale: a 12-team league with 13
roster spots rosters ~156 players, and 279 players cleared 1000 minutes last season, so
150 sits comfortably inside real data. Configurable.

The pool definition is circular (you need values to rank, and rankings to define the
pool). Resolve by iterating: seed on projected minutes, compute values, reselect the top
150 by value, recompute. Two or three passes converge. Cap at 5 and assert stability.

### 4.2 Percentage categories

Raw FG% and FT% are useless as-is — a 92% shooter on 1.2 attempts per game is nearly
irrelevant, while a 65% shooter on 11 attempts is category-defining. Convert to
volume-weighted impact:

```
FG_impact = (player_FG%  − pool_mean_FG%) × player_FGA
FT_impact = (player_FT%  − pool_mean_FT%) × player_FTA
```

Standardize the *impact*, never the raw percentage. Players with zero attempts land at
zero impact, which is the correct answer and falls out naturally — provided §2.1 rule 7
was honored and blanks were left as NaN.

### 4.3 Z-score

Per category, over the draftable pool:
```
z_cat = (value − pool_mean) / pool_stdev
```
**Invert the sign on turnovers.** Sum the nine for total value.

Guard against a zero or near-zero stdev (possible on a tiny pool) rather than dividing by it.

### 4.4 G-score

Behind a config flag, default off initially.

Z-scores implicitly model value as proportional to a category's season-long standard
deviation, which is correct for roto. In head-to-head you win *weekly matchups*, so what
matters is the variance of a single week, and categories where one player can decide a
week get valued differently. The adjustment is a different denominator, not a different
concept.

Implement Z first and verify it. Then add G behind `valuation.method: g_score`, and
produce a diff report showing the players whose ranking moves most between methods —
that diff is itself the interesting output. The reference is Zach Rosenof's work on
G-score; look up the current formulation rather than reconstructing it from memory.

### 4.5 Punt scenarios

Core feature, not an add-on. In a 12-team H2H league, committing to eight categories and
conceding one raises the floor: you need five of eight rather than five of nine
coin-flips, and you get to draft players the rest of the league has discounted.

Implement `value(player, punt_categories: list)` which recomputes the pool means and
standard deviations **with the punted category excluded entirely** — not zeroed, excluded,
so the remaining eight restandardize against each other.

Ship a `--punt-report` mode that ranks all single-category punts plus the common pairs
(FT%+TO, FG%+3PM, BLK+FG%), and for each shows the top 30 board and how much each
player's rank moves versus the balanced build. Players who rise 40+ spots under a given
punt are that build's value targets.

---

## 5. Draft mode

Interactive CLI, run live during the draft.

- Load the board. Mark players drafted (`d <name-or-id>`), with fuzzy name matching and
  disambiguation on collision. Undo (`u`) — misclicks happen and the tool must not become
  the bottleneck.
- Track your own roster separately (`m <name>` for my pick).
- After each of your picks, report: your current category totals as z-sums, which
  categories you are strong and weak in, and **which punt build your roster is closest
  to.** The punt should be observed, not pre-declared.
- Show best-available under the balanced build and under each live punt candidate, side
  by side.
- Positional scarcity: remaining draftable players by position against remaining roster
  slots. Configurable slot structure (this matters — a two-center league values bigs
  completely differently from a one-center league).
- Persist draft state to disk after every action. A crash mid-draft must not lose the room.

**Latency matters more than features here.** Every command should return in under a
second. Precompute all punt scenarios up front rather than recomputing on each pick.

---

## 6. Configuration

Single `config/league.yaml`:

```yaml
league:
  teams: 12
  format: h2h              # h2h | roto
  categories: [PTS, REB, AST, STL, BLK, 3PM, FG_IMPACT, FT_IMPACT, TOV]
  roster_slots: {PG: 1, SG: 1, SF: 1, PF: 1, C: 1, G: 1, F: 1, UTIL: 3, BENCH: 3, IL: 2}
  draft_position: null     # fill when known
  waiver_type: null        # unlimited | weekly_cap | faab  — see note below

valuation:
  method: z_score          # z_score | g_score
  pool_size: 150
  pool_iterations: 3
  punt_scenarios: [[], [FT_IMPACT], [TOV], [BLK], [FT_IMPACT, TOV], [FG_IMPACT, 3PM]]

projection:
  season_weights: [0.5, 0.3, 0.2]
  pace_method: implied     # implied | simple
  regression_k: {STL: 1400, BLK: 1400, TOV: 900, 3PM: 800, AST: 600, REB: 500, PTS: 500, FG: 900, FT: 1100}
  age_curve: default
```

Separate files, because they are hand-edited and change often:
`config/minutes.yaml`, `config/games_played.yaml`, `config/pace_overrides.yaml`.

**Waiver rules are still unknown and are load-bearing.** If acquisitions are unlimited,
streaming to maximize weekly games played is probably the largest single edge in H2H
9-cat, and it changes roster construction substantially — you can paper over a weak
category with volume instead of drafting for it. If there is a weekly cap, that lever
mostly disappears and the draft carries more weight. Leave the field null and don't build
streaming logic yet, but don't hardcode assumptions that would block it.

---

## 7. Project layout

```
fantasy-bball/
  data/raw/           # the 9 source files, read-only
  data/interim/       # cleaned parquet, crosswalks, unmatched reports
  data/processed/     # projections, valuations, boards
  config/
  src/
    ingest.py         # §2
    project.py        # §3
    value.py          # §4
    draft.py          # §5
    reports.py
  tests/
  reports/
```

CLI: `python -m src.cli build` (full pipeline), `... punt-report`, `... draft`.

---

## 8. Validation

These are regression tests, not optional. Every number below was verified against the
actual files and should be asserted, not trusted.

### 8.1 Ingestion invariants
- Raw row counts after trailer/header removal: 735, 735, 735, 735, 733, 733.
- Dedup counts: 572, 572, 569, 569, 582, 582.
- per100 ↔ adv ID sets identical within each season, zero orphans either direction.
- `MP` agrees exactly across per100 and adv for every player, all seasons.
- 802 distinct players across three seasons; 374 in all three.
- Assert every duplicated ID has exactly one combined-team row.

### 8.2 Join integrity
- All 464 players common to 2024-25 and 2025-26 show exactly +1 age. **Zero tolerance** —
  any failure means the join is broken.

### 8.3 Pace
- Implied league-average pace = 99.4 ± 0.2; implied/simple ratio ≈ 0.969; r ≈ 0.971.
- Summed player minutes = 100-101% of 240 × GP for all 30 teams.

### 8.4 Backtest — the one that actually matters

Everything above proves the plumbing works. This proves the *model* works.

Run the pipeline using only 2023-24 and 2024-25 to project 2025-26. Compare projections
to what actually happened. Report MAE and correlation per category, and the twenty
largest misses in each direction.

Use it for two things. First, tune `regression_k` by grid search minimizing backtest
error — that turns the guessed constants in §3.3 into fitted ones. Second, calibrate
expectations: knowing the model's real per-category error tells you how much to trust a
three-slot gap on draft night. Almost certainly the answer is "less than it looks."

Caveat honestly: a two-season backtest with known-actual minutes is optimistic relative to
live use, where minutes are guessed. Report backtest error both with actual minutes and
with previous-season minutes as a naive proxy. The gap between those two numbers is the
value of doing the minutes work well, and it will be large.

---

## 9. Build order

1. §2 ingestion + §8.1-8.2 tests. Nothing else works if this is wrong.
2. §3.4 pace + §8.3.
3. Roster parsing + crosswalk reports (§2.3). Eyeball the unmatched lists.
4. `vacated_opportunity.csv` (§3.5). Useful immediately, before any projections exist.
5. §3 projection with default configs.
6. §4 valuation, Z-score only, with punt scenarios.
7. §8.4 backtest. Tune `regression_k`. **Do not skip to draft mode before this.**
8. §5 draft mode.
9. §4.4 G-score.

---

## 10. Explicitly out of scope

- Scraping Basketball Reference. See §0.
- ADP ingestion — needed eventually to find value gaps (value = your projection minus
  the market's), but not to build anything. Add as a CSV drop-in later.
- Injury news feeds and beat-writer sentiment. Deliberately deferred: it is noisy,
  easy to overfit, and best used as a tiebreaker between players the model already rates
  as close — not as a term in the ranking. Revisit in October when camp reports are
  actually flowing.
- Streaming optimization. League is waivers-only with no free agency, so acquisitions
  are rationed and this lever is weaker than in an open-waiver league. Low priority.

- **Schedule metrics — deferred but anticipated.** Lineups lock daily, so weekly game
  counts matter less than they would otherwise. Two narrow metrics are worth building
  later, and both are descriptive (they report a property of the roster; they never
  recommend a pick):

  1. **Playoff-week game counts.** Three or four weeks decide the season. A player whose
     team plays four games in the championship week is worth more than his season line
     implies. Use as a tiebreaker between closely-rated players, never as a ranking term.
  2. **Slot utilization.** With daily lineups the cost is not idle players, it is
     *collision* — too many rostered players active on the same night competing for the
     same starting slots, while other nights go unfilled. Measure startable player-games
     against total player-games across the season.

  Both read from one input: a `schedule.csv` in `data/canonical/`, keyed on the same
  team codes, giving which teams play on which dates. **Accept an optional `schedule.csv`
  now** — absent is fine — so adding this later is additive rather than surgery.

  Explicitly NOT worth building: a "which player best complements my roster's schedule"
  optimizer. Every team plays 82 games, so season totals converge and there is no such
  thing as a good aggregate schedule. Optimizing distribution at draft time solves with
  a draft pick what daily lineup management solves for free, and doing it properly means
  simulating weekly lineups under slot constraints for every available player, live,
  which will not meet the sub-second latency requirement in §5.
- Any web UI. CLI only.
