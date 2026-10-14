# Evaluation: `nba_depth_charts_2026_2027.md`

**2026-10-08.** Verdict: **usable for the Eastern Conference, discard the West.** Scored
against Basketball Reference across 10 verified teams, the file is **93% precise in the
East and 47% in the West**. That split is the actionable finding; an overall average hides
it. Ryan confirms the file came from Gemini, prompted to fetch current ESPN depth charts
five at a time by division.

**Three corrections to the first version of this evaluation, all of them mine:**
1. I flagged Gabe McGlothan (BOS), Ben Humrichous (BRK) and Allen Graves (TOR) as possibly
   fabricated because they appeared in no source. **All three are real and correctly
   placed** — they are 2026 rookies/UDFAs that both of our September snapshots simply
   predate. Two of them are the only entries in the whole file that beat our own data.
2. The conflict count was **43, not 46**. My analysis matcher keyed on first-initial +
   surname and collapsed **Mikal Bridges (NYK)** with **Miles Bridges (PHO)** — so I
   reported Bridges as an error the file made when it had him right, and both of our
   sources had the two players correctly separated all along. This is the project's own
   Mikel-Brown-Jr. lesson, committed in my own analysis code.
3. "Both independent sources agree against it, so it's wrong" was overconfident as stated.
   Our two sources are both snapshots dated on or before 2026-09-21 and can be stale
   *together*. BBRef is the arbiter, not their agreement.

Checked three ways: internal consistency, against the two independent datasets already in
the repo (`data/raw/realgm_depth_charts_20260921.txt` and `rosters_2627.csv`), and against
Basketball Reference's own 2026-27 roster pages for six teams.

---

## 1. It fails internal consistency — so it is not a scrape of anything

**13 players are listed on more than one team.** Kevon Looney appears on three (GSW, LAL,
NOP). Also doubled: Terance Mann (BRK/LAC), Michael Porter Jr. (BRK/DEN), De'Aaron Fox
(SAC/SAS), John Collins (DET/UTA), Max Christie (LAL/DAL), Isaiah Stewart (DET/MEM), Josh
Minott (BRK/MIN), Trayce Jackson-Davis (TOR/GSW), Jevon Carter (CHI/ORL), Jordan Hawkins
(CHI/NOP), Kobe Brown (IND/LAC), Jordan McLaughlin (SAC/SAS).

No real source can produce that. A scrape of a live depth-chart page cannot place one
player on two rosters.

**Completeness tracks position in the document, not reality.** Eastern Conference teams are
mostly full at 15 — exactly the cap of the 5 positions × 3 depth slots template — while
Western teams degrade steadily: PHO 12, MEM/SAC/DAL/GSW/ORL/MIA 13, SAS/DEN 11, MIN/OKC 10,
HOU/POR 9, UTA 8, **NOP 6**. New Orleans is given one player per position and `Vacant`
everywhere else. Real rosters don't thin out alphabetically.

**The template can't hold a real roster.** 15 slots per team, where actual 2026-27 rosters
run 17-21 players. Even filled perfectly it would be structurally incomplete.

## 2. Where it disagrees with our data, it loses

**43 team assignments conflict with both** the RealGM capture and `rosters_2627.csv`, with
exact-name matching. **17 are at starter level**, including Kevin Durant (PHO vs HOU),
Jonathan Kuminga (GSW vs MIN), Deandre Ayton (POR vs WAS), John Collins (UTA vs DET),
Jordan Clarkson (UTA vs NYK) and Terance Mann (LAC vs BRK).

A further 22 entries can't be adjudicated without guessing — an abbreviated name whose
surname is shared by more than one player in the league (`Michael Porter Jr.`,
`Jaylin Williams`, `Robert Williams III`). Those are left unresolved rather than assumed.

## 3. Verified against Basketball Reference — the numbers

Six teams checked directly against BBRef's 2026-27 roster pages:

| team | submitted: listed / correct / precision | our capture: listed / correct / precision |
|---|---|---|
| HOU | 9 / 9 / **100%** | 19 / 18 / 95% |
| PHI | 15 / 15 / **100%** | 21 / 21 / 100% |
| LAC | 14 / 6 / **43%** | 21 / 19 / 90% |
| MIN | 10 / 5 / **50%** | 17 / 15 / 88% |
| SAC | 13 / 4 / **31%** | 17 / 16 / 94% |
| PHO | 12 / 3 / **25%** | 18 / 17 / 94% |
| **total** | **73 / 42 / 58%** | **113 / 106 / 94%** |

Extending to the full Atlantic division (BOS, BRK, NYK, PHI, TOR — all five verified
against BBRef) changes the picture materially, because the East is where the file is good:

| team | conf | submitted | RealGM capture | `rosters_2627.csv` |
|---|---|---|---|---|
| BOS | East | 15/15 **100%** | 19/19 100% | 18/18 100% |
| BRK | East | 15/15 **100%** | 17/18 94% | 17/18 94% |
| PHI | East | 15/15 **100%** | 21/21 100% | 16/16 100% |
| TOR | East | 13/14 **93%** | 18/19 95% | 16/20 80% |
| NYK | East | 11/15 **73%** | 17/18 94% | 14/14 100% |
| HOU | West | 9/9 **100%** | 18/19 95% | 18/19 95% |
| MIN | West | 5/10 **50%** | 15/17 88% | 15/17 88% |
| LAC | West | 6/14 **43%** | 19/21 90% | 15/19 79% |
| SAC | West | 4/13 **31%** | 16/17 94% | 15/16 94% |
| PHO | West | 3/12 **25%** | 17/18 94% | 17/18 94% |
| **all 10** | | **73%** | **95%** | **92%** |

Split by conference, the submitted file is **93% precise in the East (69 right, 5 wrong)**
and **47% in the West (27 right, 31 wrong)**. Four of five Atlantic teams are 93-100%.
Houston is 100% too — so the West failure isn't uniform, but below Houston it collapses.

Coverage of the actual rosters on the original six teams: submitted charts capture **36%**
of real rostered players, our capture **90%**.

**It contributed nothing.** Across all six teams there is not one real player the submitted
charts caught that our capture missed. The reverse list runs 64 players deep — including
Kevin Durant, Fred VanVleet, Marcus Smart, Steven Adams and Clint Capela all missing from
Houston, and Darius Garland, Brook Lopez, Bradley Beal and Max Strus all missing from the
Clippers.

## 4. The error signature

The wrong entries are not random. They are overwhelmingly **players returned to a team they
were associated with one or two seasons earlier**:

| player | submitted | actually (BBRef / both our sources) | was on the submitted team in |
|---|---|---|---|
| Kevin Durant | PHO | HOU | 2023-25 |
| Michael Porter Jr. | DEN | BRK | through 2024-25 |
| Jonathan Kuminga | GSW | MIN | through 2024-25 |
| Mikal Bridges | NYK | PHO | 2023-25 |
| John Collins | UTA (at C) | DET | 2024-25 |
| Deandre Ayton | POR | WAS | 2023-25 |
| Jusuf Nurkic | PHO | UTA | 2022-24 |
| Jordan Clarkson | UTA | NYK | through 2024-25 |
| Donte DiVincenzo | NYK | MIN | 2023-24 |
| Terance Mann | LAC | WAS | through 2023-24 |
| De'Aaron Fox | SAC (2nd str.) | SAS | through 2024-25 |

Alongside that, **players whose careers appear to have ended are restored to their last
team**: Sasha Vezenkov (last played 2023-24, placed back on SAC), Christian Wood (2023-24 →
LAL), Bol Bol and Damion Lee (2024-25 → PHO), P.J. Tucker (2024-25 → LAC), Keita Bates-Diop
(2023-24 → NYK), Daishen Nix (2024-25 → MIN), Vlatko Cancar (2024-25 → DEN), Alex Len and
Mason Jones (→ SAC).

Three names appeared in no source at all: Gabe McGlothan (BOS), Ben Humrichous (BRK),
Allen Graves (TOR). **All three turned out to be real** and correctly placed — see the
corrections at the top. Keyshawn Hall (MIA) remains unverified.

This is the signature of content generated from stale knowledge rather than collected from
a live source. The header's claim of "September/October 2026 real-time data" is not
supported by what the file contains. Notably it is *bimodally* wrong — perfect on Houston
and Philadelphia, 25-31% on Phoenix and Sacramento — so partial correctness is not evidence
of a reliable source here.

---

## What it did usefully establish

1. **Our Sept-21 capture holds up well**: 94% precision, 90% recall against BBRef. The
   depth-chart minutes built on it are sound.
2. **Last session's roster-staleness finding is confirmed.** BBRef's LAC roster contains
   Darius Garland, Rui Hachimura, Yuki Kawamura, Gradey Dick and Brandon Ingram — exactly
   the players flagged as missing from `rosters_2627.csv`. That file is genuinely stale and
   the flagged gaps are real.
3. **Both our sources are blind to ~10% of real rosters** — mostly two-ways and late
   signings: Blake Wesley and Nicolas Batum (LAC), Antonio Reeves, Drew Timme, KJ Martin,
   Norchad Omier (MIN), Duop Reath, Kennedy Chandler, Phillip Wheeler (PHO), Killian Hayes,
   Leaky Black, Tristen Newton (SAC).
4. **Basketball Reference publishes 2026-27 roster pages**, keyed to the same player IDs the
   whole pipeline already uses. That is a better source than either the Wikipedia-derived
   docx or RealGM, and refreshing `rosters_2627.csv` from it would resolve the open
   roster-gap decision outright instead of patching 18 players by hand.

## Why the fetch failed, which is the reusable lesson

ESPN's depth-chart page (`espn.com/nba/team/depth/_/name/<abbr>`) is **client-rendered** —
fetching it returns an empty shell with no roster content. That is almost certainly what
happened here: the fetch was attempted, returned nothing, and the gap was filled from model
priors without the substitution being disclosed. It explains the East/West gradient too —
priors are strongest for the teams and players with the most coverage.

What *does* read cleanly through a plain fetch:

| source | works? | gives |
|---|---|---|
| `basketball-reference.com/teams/<T>/2027.html` | **yes** | full roster, native `player_id` |
| `basketball.realgm.com/nba/depth-charts` | **yes** | tiered depth ordering |
| `espn.com/nba/team/depth/...` | **no** | JS shell, empty |
| `site.api.espn.com/.../teams/<T>/roster` | partly | JSON, but summarisation truncates it |
| `sports.core.api.espn.com/.../depthcharts` | partly | ranked positions, athletes as URL refs only |

So ESPN is reachable only via its JSON API, and that needs a second ID-resolution call per
team. BBRef and RealGM between them cover both needs — membership and ordering — with no
such plumbing.

## Recommendation

1. **Keep the Eastern Conference pages** as a usable cross-check; they are 93% precise.
2. **Discard the Western Conference pages.** Phoenix, Sacramento, LAC and Minnesota are
   25-50% precise and would do real damage if ingested.
3. **Refresh `rosters_2627.csv` from BBRef**, division by division. The Atlantic is done and
   verified. This is the better source than either the Wikipedia docx (92%) or RealGM (95%),
   it carries native player IDs so there is no name-matching guesswork, and it resolves the
   outstanding 18-player roster gap rather than patching it by hand.
4. **Standing rule worth adopting:** nothing enters the repo as roster or depth-chart truth
   unless it came from a fetch this project ran itself. A model's report that it fetched
   something is not evidence that it did.
