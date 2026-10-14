# Minutes modeling: why VORP scaling shouldn't drive minutes

**Session 3, 2026-09-21.** Investigated before building, per the plan to replace the flat
30/12/5/1/0 depth curve with VORP-based scaling. Three findings, one recommendation.
Nothing in the repo was changed.

---

## Finding 1 — VORP/BPM has almost no incremental power to predict minutes

The advanced tables already carry `bpm`, `obpm`, `dbpm` and `vorp` per player-season, so no
new data was needed. First a definitional note: BBRef's `vorp` is *already* scaled by
minutes played (`VORP = (BPM − (−2.0)) × %minutes × team_games/82`), so using it to
allocate minutes is circular. The non-circular talent rate is **BPM**, which is what the
test below uses — blended over 3 seasons, minutes-weighted, shrunk toward the same −2.0
replacement level the project's other shrinkage uses.

Backtest: take each team's actual 2025-26 roster as given, use only 2023-24 + 2024-25 to
estimate talent, allocate the team's actual total minutes, compare to actual 2025-26
minutes. Players with ≥500 actual minutes, n=386.

| Model for next-season minute share | R² | Δ vs baseline |
|---|---|---|
| **prior minutes alone (baseline)** | **0.199** | — |
| + value above replacement (BPM) | 0.205 | **+0.006** |
| + age | 0.217 | +0.018 |
| + minutes trend (24-25 vs 23-24) | 0.208 | +0.009 |
| + prior games played | 0.203 | +0.003 |
| + usage rate | 0.199 | +0.000 |
| everything combined | 0.240 | +0.040 |

Value above replacement is the **weakest** of the signals tested — it adds 0.6 points of R²
where age alone adds 1.8. And as a standalone allocator it is far worse than doing nothing
clever:

| Allocator | MAE | correlation |
|---|---|---|
| naive: prior minutes | **6.76 mpg** | **0.447** |
| pure BPM value above replacement | 10.44 mpg | 0.318 |
| prior minutes × var^0.25 | 9.73 mpg | 0.402 |
| prior minutes × var^1 | 11.50 mpg | 0.370 |

Every mix that gives BPM weight is worse than prior minutes alone.

The wider point is worth sitting with: **even the full model explains only 24% of variance
in next-season minute share.** Three quarters of what determines minutes — role, health,
coach trust, transactions — is invisible to box-score data. This is a sharper version of
the backtest finding already in the project ("minutes projection is most of the available
edge"): the edge isn't just uncaptured, it's largely *uncapturable from stats*.

## Finding 2 — the failure mode is systematic, not noisy

Run the VORP allocator on LAL, the one team with hand-reviewed minutes, and it disagrees
with real judgment by 6.66 mpg MAE (corr 0.659) — but the disagreements are all the same
two mistakes:

```
               player pos mpg 23/24/25  Ryan  VORP  diff
          Luka Dončić   G   37, 35, 36  36.0  37.0   1.0
        Austin Reaves   G   32, 35, 35  32.0  35.8   3.8
       Quentin Grimes   G   20, 27, 29  31.0   8.7 -22.3
         Jake LaRavia   F   23, 20, 25  30.0   8.9 -21.1
       Walker Kessler   C   23, 30, 31  30.0  30.8   0.8
        Collin Sexton   G   27, 28, 24  21.0  22.9   1.9
Sandro Mamukelashvili F/C   10, 11, 22  16.0  36.8  20.8
         Kevon Looney   C   16, 15, 15  14.0  15.9   1.9
     Matisse Thybulle G/F   23, 21, 16   7.0  37.0  30.0
    Jarred Vanderbilt   F   20, 16, 17   5.0   4.7  -0.3
```

- **Small-sample efficiency specialists get promoted to starters.** Thybulle goes 7 → 37
  mpg because his DBPM is +6.1 off a 6.0 STL% in 480 minutes. Mamukelashvili goes 16 → 37
  on bench efficiency. Both absurd.
- **High-volume, low-efficiency starters get demoted to the bench.** Grimes (BPM −1.6
  across 2,206 minutes) drops 31 → 9. LaRavia (BPM −1.2) drops 30 → 9. Both will start.

This is the mechanism behind Finding 1: BPM measures efficiency, minutes are assigned by
role, and the players where the two diverge most are exactly the ones a rotation is built
around. Note the allocator gets the *easy* cases right — Luka, Reaves, Kessler, Sexton,
Looney, Vanderbilt are all within 2 mpg. It only breaks where judgment is actually needed,
which is the worst possible place to break.

## Finding 3 — an unrelated real bug: the 240 constraint can't be satisfied

Separate from VORP, and worth fixing either way. `minutes_sanity_check` compares
`Σ(mpg × gp)` against 240 × 82 = 19,680, but the depth-curve method constrains `Σ mpg` to
240. **Those two constraints are mutually incompatible whenever any player's GP < 82** —
mathematically, not approximately.

LAL as reviewed: `Σ mpg` = 223, `Σ(mpg × gp)` = 15,375 = **78.1%** of target. At LAL's own
GP profile, `Σ mpg` would need to be **~285**, not 240, to reach 19,680. In real 2025-26
data every team's season minutes came to ~19,784 while per-player mpg summed well above
240, because minutes from missed games get absorbed by whoever is available.

So LAL's 78.1% is not explained by Cameron Carr's unmodeled 17 mpg and conservative GP, as
currently documented — those are second-order. The dominant cause is the constraint
conflict, and it will flag **every** properly-reviewed team as failing while leaving naive
teams (GP pinned at 82) looking fine. That's backwards.

**Fix:** allocate *season* minutes (19,680) and derive `mpg = season_minutes / gp`, or
equivalently target `Σ(mpg × gp) = 19,680` directly. Absences then redistribute the way
they do in reality, and the sanity check starts measuring something true.

---

## Recommendation

**Don't make VORP the minutes source.** It would replace a good signal — a current depth
chart plus your own judgment, which together encode the coach's intent that actually sets
minutes — with a measurably worse one. The hand-review isn't a stopgap waiting to be
automated; given what's in the data, it's the best available method.

**Do use the statistical data as an auditor instead.** The rule you already invented for
Luka is the correct use of it: don't let BPM *set* minutes, let it *flag* hand-set minutes
that disagree with a player's own stable history. Worth automating as a report over
whatever you enter, checking:

1. hand-set mpg far below a stable multi-season history (the Luka case)
2. hand-set mpg far above history without vacated-opportunity justification
3. age drift — the one signal that did beat VORP, and it points the same way every year
4. per-team `Σ(mpg × gp)` against 19,680 under the corrected constraint

That keeps every bit of value the VORP idea was reaching for — catching flat-curve errors
automatically — without handing minute-setting to a metric that can't do it.

**Also still needed:** the RealGM depth chart (basketball.realgm.com/nba/depth-charts).
It couldn't be fetched this session — both browsers were unreachable and the web-fetch
approval didn't land. Under this recommendation it becomes the primary input rather than a
nice-to-have, and it should be committed into the repo with its parser this time so it
stops disappearing between sessions.
