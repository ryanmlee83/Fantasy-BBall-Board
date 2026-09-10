#!/usr/bin/env python3
"""Validation suite for the canonical dataset. Exit 1 on any failure."""
import csv, collections, statistics, sys
from pathlib import Path

# Directory holding the canonical CSVs. Order of preference:
#   1. path given as the first command-line argument
#   2. ./data/canonical relative to the current working directory
#   3. the directory this script lives in
if len(sys.argv) > 1:
    OUT = Path(sys.argv[1])
elif (Path.cwd() / 'data' / 'canonical' / 'teams.csv').exists():
    OUT = Path.cwd() / 'data' / 'canonical'
else:
    OUT = Path(__file__).resolve().parent

if not (OUT / 'teams.csv').exists():
    sys.exit(f'No canonical CSVs found in {OUT}\n'
             f'Usage: python validate.py [path-to-data/canonical]')
print(f'Validating: {OUT}')

def load(n): return list(csv.DictReader(open(OUT / n, encoding='utf-8')))
fails = []
def check(label, cond, detail=''):
    (print(f'  PASS  {label}') if cond else fails.append(label) or print(f'  FAIL  {label}  {detail}'))

ps  = load('player_seasons.csv')
pts_ = load('player_team_seasons.csv')
tm  = load('team_seasons.csv')
ros = load('rosters_2627.csv')

print('\n-- player_seasons --')
bys = collections.Counter(r['season'] for r in ps)
check('season counts 572/569/582',
      (bys['2023-24'], bys['2024-25'], bys['2025-26']) == (572, 569, 582), dict(bys))
check('player_id unique within season',
      all(len({r['player_id'] for r in ps if r['season'] == s}) == bys[s] for s in bys))
ids_by_s = {s: {r['player_id'] for r in ps if r['season'] == s} for s in bys}
allids = set().union(*ids_by_s.values())
check('802 distinct players', len(allids) == 802, len(allids))
check('374 in all three seasons',
      len(set.intersection(*ids_by_s.values())) == 374,
      len(set.intersection(*ids_by_s.values())))

print('\n-- cross-season join integrity --')
age = {(r['player_id'], r['season']): int(float(r['age'])) for r in ps}
common = ids_by_s['2024-25'] & ids_by_s['2025-26']
bad = [p for p in common if age[(p, '2025-26')] - age[(p, '2024-25')] != 1]
check(f'age +1 for all {len(common)} common players (24-25 -> 25-26)', not bad, bad[:5])
c2 = ids_by_s['2023-24'] & ids_by_s['2024-25']
bad2 = [p for p in c2 if age[(p, '2024-25')] - age[(p, '2023-24')] != 1]
check(f'age +1 for all {len(c2)} common players (23-24 -> 24-25)', not bad2, bad2[:5])

print('\n-- percentage nulls preserved --')
zero_fta = [r for r in ps if r['fta_p100'] and float(r['fta_p100']) == 0]
check('players with 0 FTA have blank ft_pct (not 0.0)',
      all(r['ft_pct'] == '' for r in zero_fta), len(zero_fta))

print('\n-- teams --')
check('30 canonical teams in team_seasons', len(tm) == 30, len(tm))
check('every player_team_seasons team is canonical',
      {r['team'] for r in pts_} <= {r['team'] for r in tm})
check('player_seasons team blank iff multi_team',
      all((r['team'] == '') == (r['multi_team'] == 'True') for r in ps))

print('\n-- pace --')
imp = [float(r['pace_implied']) for r in tm]
sim = [float(r['pace_simple']) for r in tm]
avg = sum(imp) / 30
check(f'implied league avg 99.4 (got {avg:.2f})', 99.2 <= avg <= 99.6)
check(f'implied/simple ratio ~0.969 (got {avg/(sum(sim)/30):.3f})',
      0.96 <= avg / (sum(sim) / 30) <= 0.98)
r = statistics.correlation(imp, sim)
check(f'simple/implied correlation ~0.97 (got {r:.3f})', r >= 0.95)
ms = [float(x['minutes_share']) for x in tm]
check(f'team minutes share 100-101% (range {min(ms)*100:.1f}-{max(ms)*100:.1f}%)',
      all(0.99 <= m <= 1.02 for m in ms))

print('\n-- rosters --')
per = collections.Counter(r['team'] for r in ros)
check('30 teams on 2026-27 rosters', len(per) == 30, len(per))
check(f'13-21 players per team (range {min(per.values())}-{max(per.values())})',
      all(13 <= v <= 21 for v in per.values()))
check('every roster team is canonical', set(per) <= {r['team'] for r in tm})
jer = collections.Counter((r['team'], r['jersey']) for r in ros)
dupj = [k for k, v in jer.items() if v > 1]
# Not an assertion: Wikipedia August rosters legitimately carry unresolved number
# clashes (mostly #0) for new signings and rookies. Jersey is not a join key.
print(f'  INFO  {len(dupj)} duplicate team/jersey pairs (expected; source quirk)')
# The meaningful invariant is not a match RATE -- rookies and international signings
# legitimately have no 2023-26 NBA season. It is that no unmatched name has a close
# fuzzy neighbour, since that would indicate a normalization bug rather than a real
# absence. Any row here needs either a NAME_ALIASES entry or confirmation it is new.
unm_csv = load('crosswalk_unmatched.csv')
near = [r for r in unm_csv if r.get('fuzzy_suggestion')]
check('no unmatched name has a close fuzzy neighbour', not near,
      [(r['roster_name'], r['fuzzy_suggestion']) for r in near[:5]])
std = [r for r in ros if r['two_way'] != 'True']
smid = sum(1 for r in std if r['player_id'])
mid = sum(1 for r in ros if r['player_id'])
print(f'  INFO  crosswalk: {mid}/{len(ros)} overall, {smid}/{len(std)} standard-contract')
tw = sum(1 for r in ros if r['two_way'] == 'True')
print(f'  INFO  {tw} two-way, {len(ros)-tw} standard')
unm = [r for r in ros if not r['player_id']]
print(f'  INFO  {len(unm)} unmatched: '
      f'{sum(1 for r in unm if r["two_way"]=="True")} two-way, '
      f'{sum(1 for r in unm if int(r["age_at_season_start"])<=22)} age<=22')

print('\n' + ('ALL CHECKS PASSED' if not fails else f'{len(fails)} FAILURES: {fails}'))
sys.exit(1 if fails else 0)
