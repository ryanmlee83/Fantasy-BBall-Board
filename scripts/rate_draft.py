"""Rate a finished draft: score every roster with the board model and simulate weekly H2H matchups.

Reads data/raw/draft_results_238445.txt (Yahoo draft results text) and reports/board_data.json.
Prints each team's simulated weekly matchup win rate, your category ranks, each of your picks
against the board's best available at that moment, and the best undrafted players.
Same scoring as scripts/simulate_punts.py; unprojected rookies count as average (zero Z).

Usage: python scripts/rate_draft.py
"""
import json, re, unicodedata, math, itertools
import numpy as np
B = json.load(open('reports/board_data.json'))
CATS = B['cats']
def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower()
    s = s.replace('.', ' ').replace("'", '').replace('-', ' ')
    t = re.sub(r'[^a-z ]', '', s).split()
    while len(t) > 2 and t[-1] in {'jr','sr','ii','iii','iv','v'}: t.pop()
    out, buf = [], []
    for w in t:
        if len(w) == 1: buf.append(w)
        else:
            if buf: out.append(''.join(buf)); buf = []
            out.append(w)
    if buf: out.append(''.join(buf))
    return ' '.join(out)
idx = {}
for p in B['players']: idx.setdefault(norm(p['name']), []).append(p)
picks = []
rnd = 0
for line in open('data/raw/draft_results_238445.txt', encoding='utf-8'):
    line = line.strip()
    m = re.match(r'Round (\d+)', line)
    if m: rnd = int(m.group(1)); continue
    m = re.match(r'\((\d+)\) (.+?) - (.+?), (.+?) \((\w+) - ([A-Z,]+)\)', line)
    if not m: continue
    slot, team, last, first, nba, pos = m.groups()
    name = f"{first} {last}"
    hits = idx.get(norm(name), [])
    p = hits[0] if len(hits) == 1 else None
    overall = (rnd - 1) * 12 + int(slot)
    picks.append(dict(rnd=rnd, overall=overall, team=team, name=name, nba=nba, pos=pos, p=p))
miss = [x['name'] for x in picks if x['p'] is None]
print('unmatched:', miss)
teams = list(dict.fromkeys(x['team'] for x in picks))
# score: Floor value under balanced (same as board)
proj = [p for p in B['players'] if not p.get('np')]
v = {p['id']: sum(p['z'].values()) for p in proj}
repl = sorted(v.values(), reverse=True)[155]
floor = {p['id']: (v[p['id']] - repl) * p['gp'] / 82 for p in proj}
rank = {pid: i + 1 for i, pid in enumerate(sorted(floor, key=lambda k: -floor[k]))}
SIG = np.array([{"PTS":2.5,"REB":2.5,"AST":2.5,"STL":5.0,"BLK":4.5,"3PM":3.5,"TOV":3.5,"FG_IMPACT":4.0,"FT_IMPACT":4.0}[c] for c in CATS])
def contrib(p):
    if p is None or p.get('np'): return np.zeros(len(CATS))
    return np.array([p['z'][c] for c in CATS]) * p['gp'] / 82
strength = {t: sum(contrib(x['p']) for x in picks if x['team'] == t) for t in teams}
def matchup(a, b):
    pw = 0.5 * (1 + np.vectorize(math.erf)((a - b) / (SIG * math.sqrt(2))))
    d = np.zeros(10); d[0] = 1
    for q in pw: d[1:] = d[1:] * (1 - q) + d[:-1] * q; d[0] *= (1 - q)
    return pw.sum(), d[5:].sum()
rows = []
for t in teams:
    cw = mw = 0
    for o in teams:
        if o == t: continue
        c, m = matchup(strength[t], strength[o]); cw += c; mw += m
    tot = sum(floor.get(x['p']['id'], 0) for x in picks if x['team'] == t and x['p'] and not x['p'].get('np'))
    nrook = sum(1 for x in picks if x['team'] == t and (x['p'] is None or x['p'].get('np')))
    rows.append((t, mw / 11, cw / 11, tot, nrook))
rows.sort(key=lambda r: -r[1])
print('\nTEAM            win%  cats/9  floorSum rookies')
for r in rows: print(f"{r[0]:14s} {r[1]*100:5.1f}  {r[2]:5.2f}  {r[3]:7.1f}  {r[4]}")
# best build per team (punting the weakest), to see what Ryan should punt
print('\nRyan category strength (sum Z x GP/82) and league rank:')
for i, c in enumerate(CATS):
    vals = sorted([strength[t][i] for t in teams], reverse=True)
    print(f"  {c:10s} {strength['Ryan'][i]:+6.2f}  rank {vals.index(strength['Ryan'][i]) + 1}/12")
print('\nRyan picks:')
for x in picks:
    if x['team'] != 'Ryan': continue
    p = x['p']
    adp = p.get('adp') if p else None
    r = rank.get(p['id']) if p and not p.get('np') else None
    print(f"  R{x['rnd']:<2} #{x['overall']:<3} {x['name']:22s} ADP {adp}  model rank {r}  floor {floor.get(p['id'], float('nan')) if p else float('nan'):.1f}  gp {p.get('gp') if p else '-'} {('INJ: ' + p['inj']) if p and p.get('inj') else ''}")
# what was best available by model at each of Ryan's picks (balanced floor)
taken = set()
print('\nBest available by board (balanced Floor) at each of your picks:')
for x in picks:
    if x['team'] == 'Ryan':
        avail = [pid for pid in floor if pid not in taken]
        avail.sort(key=lambda k: -floor[k])
        names = {p['id']: p['name'] for p in B['players']}
        print(f"  #{x['overall']:<3} took {x['name']:22s} ({floor.get(x['p']['id'], float('nan')) if x['p'] else float('nan'):.1f})  board top: " + ', '.join(f"{names[k]} ({floor[k]:.1f})" for k in avail[:3]))
    if x['p']: taken.add(x['p']['id'])

drafted = {x['p']['id'] for x in picks if x['p']}
names = {p['id']: p for p in B['players']}
def floor_build(punt):
    vv = {p['id']: sum(z for c, z in p['z'].items() if c not in punt) for p in proj}
    rp = sorted(vv.values(), reverse=True)[155]
    return {k: (vv[k] - rp) * names[k]['gp'] / 82 for k in vv}
for punt in [[], ['AST'], ['AST', '3PM']]:
    fb = floor_build(punt)
    und = sorted([k for k in fb if k not in drafted], key=lambda k: -fb[k])[:8]
    mine = sorted([x['p']['id'] for x in picks if x['team'] == 'Ryan' and x['p'] and not x['p'].get('np')], key=lambda k: fb[k])[:4]
    print(f"\npunt {punt or 'none'}: top undrafted:", ', '.join(f"{names[k]['name']} {names[k]['team']} ({fb[k]:.1f}{', inj' if names[k].get('inj') else ''})" for k in und))
    print("   your lowest:", ', '.join(f"{names[k]['name']} ({fb[k]:.1f})" for k in mine))
# Ryan's matchup win % under punt-AST evaluation is same metric; show category win prob vs league avg
avg = sum(strength[t] for t in teams if t != 'Ryan') / 11
pw = 0.5 * (1 + np.vectorize(math.erf)((strength['Ryan'] - avg) / (SIG * math.sqrt(2))))
print('\nP(win cat) vs average opponent:', ', '.join(f"{c} {q*100:.0f}%" for c, q in zip(CATS, pw)))
