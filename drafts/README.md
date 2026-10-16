# Draft archive

Every draft run with the board is kept here so the engine can be graded against what
actually happens. Each draft has three things:

- `<id>_raw.txt`: the pasted Yahoo draft results, untouched
- `<id>_picks.csv`: every pick matched to a Basketball Reference `player_id`
  (`python scripts/parse_draft.py <raw> <teams> <out>`; ambiguous initials are resolved by
  ADP and flagged in `match_note`)
- a row in `index.csv` with the league, format, your slot, and the **commit of the board
  data you drafted with**. `git show <commit>:reports/board_data.json` recovers the exact
  projections, GP and ADP behind every recommendation, even after the model changes.

## Adding a draft

1. Paste the draft results into chat (results page or draft-room list, both parse).
2. Claude saves the raw text, parses it, adds the index row and tags the board commit.
3. For a High Score draft, `python scripts/rate_highscore_draft.py drafts/<id>_picks.csv "<team>"`
   rates it; for 9-cat, `python scripts/rate_draft.py`.

## End-of-season evaluation (planned for April 2027)

Inputs: Basketball Reference 2026-27 per-100 and advanced exports (the same files as the
three seasons already in the project) plus final standings for each league.

1. **Projection error by player and category**: projected per-game line (from each draft's
   board commit) vs actual, split by the things the model handles differently: rookies and
   unprojected players, starters vs promoted bench players, age bands, players whose
   minutes were raised from ADP, injured-at-draft players.
2. **Minutes and games played**: projected vs actual MPG and GP. GP is where the model is
   least sure (backtest MAE ~15.6 games), so this is the first place to look for drift.
3. **Draft calls**: for every pick, the board's value at that moment vs the player's
   realised value. Where the board disagreed with ADP, who was right?
4. **Format model**: for High Score, the projected best-game-of-week vs actual weekly highs,
   which tests the game-to-game swing estimate directly.

Weekly lineups and matchup results aren't public; paste a week's matchup page any time
and it will be filed under `lineups/` for the same review.
