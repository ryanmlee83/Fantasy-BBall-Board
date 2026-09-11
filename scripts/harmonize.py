#!/usr/bin/env python3
"""Harmonize all raw fantasy-basketball sources into canonical CSVs."""
import re, csv, json, unicodedata, collections, datetime, sys
from pathlib import Path
from openpyxl import load_workbook

RAW = Path('/mnt/project')
OUT = Path('/home/claude/work/out')
OUT.mkdir(parents=True, exist_ok=True)

SEASONS = {'2324': '2023-24', '2425': '2024-25', '2526': '2025-26'}
MULTI = {'2TM', '3TM', '4TM', '5TM', 'TOT'}

# ---------------------------------------------------------------- teams
# Canonical = Basketball Reference abbreviation (6 of 9 source files use it).
TEAMS = [
    # canon, full name, conference, division, aliases
    ('ATL','Atlanta Hawks','East','Southeast',['ATL']),
    ('BOS','Boston Celtics','East','Atlantic',['BOS']),
    ('BRK','Brooklyn Nets','East','Atlantic',['BKN','BRK','BRO']),
    ('CHO','Charlotte Hornets','East','Southeast',['CHA','CHO','CHH']),
    ('CHI','Chicago Bulls','East','Central',['CHI']),
    ('CLE','Cleveland Cavaliers','East','Central',['CLE']),
    ('DAL','Dallas Mavericks','West','Southwest',['DAL']),
    ('DEN','Denver Nuggets','West','Northwest',['DEN']),
    ('DET','Detroit Pistons','East','Central',['DET']),
    ('GSW','Golden State Warriors','West','Pacific',['GSW','GS']),
    ('HOU','Houston Rockets','West','Southwest',['HOU']),
    ('IND','Indiana Pacers','East','Central',['IND']),
    ('LAC','Los Angeles Clippers','West','Pacific',['LAC','LA Clippers']),
    ('LAL','Los Angeles Lakers','West','Pacific',['LAL']),
    ('MEM','Memphis Grizzlies','West','Southwest',['MEM']),
    ('MIA','Miami Heat','East','Southeast',['MIA']),
    ('MIL','Milwaukee Bucks','East','Central',['MIL']),
    ('MIN','Minnesota Timberwolves','West','Northwest',['MIN']),
    ('NOP','New Orleans Pelicans','West','Southwest',['NOP','NO']),
    ('NYK','New York Knicks','East','Atlantic',['NYK','NY']),
    ('OKC','Oklahoma City Thunder','West','Northwest',['OKC']),
    ('ORL','Orlando Magic','East','Southeast',['ORL']),
    ('PHI','Philadelphia 76ers','East','Atlantic',['PHI']),
    ('PHO','Phoenix Suns','West','Pacific',['PHX','PHO']),
    ('POR','Portland Trail Blazers','West','Northwest',['POR']),
    ('SAC','Sacramento Kings','West','Pacific',['SAC']),
    ('SAS','San Antonio Spurs','West','Southwest',['SAS','SA']),
    ('TOR','Toronto Raptors','East','Atlantic',['TOR']),
    ('UTA','Utah Jazz','West','Northwest',['UTA','UTH']),
    ('WAS','Washington Wizards','East','Southeast',['WAS','WSH']),
]
ALIAS2CANON = {}
for canon, full, conf, div, aliases in TEAMS:
    ALIAS2CANON[canon] = canon
    ALIAS2CANON[full.lower()] = canon
    for a in aliases:
        ALIAS2CANON[a.lower()] = canon
        ALIAS2CANON[a] = canon

def team_canon(x):
    if x is None: return None
    x = str(x).strip()
    return ALIAS2CANON.get(x) or ALIAS2CANON.get(x.lower())

# ---------------------------------------------------------------- names
SUFFIX = re.compile(r'\b(jr|sr|ii|iii|iv|v)\.?\b')
# German/Nordic transliteration: BBRef uses oe/ue/ae, NFKD gives o/u/a.
TRANSLIT = str.maketrans({'ö': 'oe', 'ü': 'ue', 'ä': 'ae', 'Ö': 'oe', 'Ü': 'ue', 'Ä': 'ae'})
# Nicknames and spellings that differ between Wikipedia rosters and Basketball Reference.
# Keyed on normalized roster name -> normalized BBRef name. Extend as the report surfaces more.
NAME_ALIASES = {
    'sviatoslav mykhailiuk': 'svi mykhailiuk',
}

SUFFIX_TOKENS = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}

def norm_name(s, translit=False):
    if translit:
        s = s.translate(TRANSLIT)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = s.lower().replace('.', ' ').replace("'", '').replace('-', ' ')
    toks = re.sub(r'[^a-z ]', '', s).split()
    # Strip generational suffixes ONLY as trailing tokens. Doing it anywhere in the
    # string eats leading initials: "V. J. Edgecombe" -> "j edgecombe".
    while len(toks) > 2 and toks[-1] in SUFFIX_TOKENS:
        toks.pop()
    # collapse runs of single letters: ["p","j","washington"] -> ["pj","washington"]
    out, buf = [], []
    for t in toks:
        if len(t) == 1:
            buf.append(t)
        else:
            if buf: out.append(''.join(buf)); buf = []
            out.append(t)
    if buf: out.append(''.join(buf))
    return ' '.join(out)

def name_keys(s):
    """All normalized forms a name might match under."""
    ks = {norm_name(s), norm_name(s, translit=True)}
    ks |= {NAME_ALIASES[k] for k in list(ks) if k in NAME_ALIASES}
    return {k for k in ks if k}

# ---------------------------------------------------------------- schema
P100_MAP = {
    'Player':'player_name','Age':'age','Team':'team','Pos':'pos','G':'g','GS':'gs','MP':'mp',
    'FG':'fg_p100','FGA':'fga_p100','FG%':'fg_pct','3P':'fg3_p100','3PA':'fg3a_p100','3P%':'fg3_pct',
    '2P':'fg2_p100','2PA':'fg2a_p100','2P%':'fg2_pct','eFG%':'efg_pct','FT':'ft_p100','FTA':'fta_p100',
    'FT%':'ft_pct','ORB':'orb_p100','DRB':'drb_p100','TRB':'trb_p100','AST':'ast_p100','STL':'stl_p100',
    'BLK':'blk_p100','TOV':'tov_p100','PF':'pf_p100','PTS':'pts_p100','ORtg':'ortg','DRtg':'drtg',
    'Player-additional':'player_id',
}
ADV_MAP = {
    'PER':'per','TS%':'ts_pct','3PAr':'fg3a_rate','FTr':'ft_rate','ORB%':'orb_pct','DRB%':'drb_pct',
    'TRB%':'trb_pct','AST%':'ast_pct','STL%':'stl_pct','BLK%':'blk_pct','TOV%':'tov_pct','USG%':'usg_pct',
    'OWS':'ows','DWS':'dws','WS':'ws','WS/48':'ws48','OBPM':'obpm','DBPM':'dbpm','BPM':'bpm','VORP':'vorp',
}
NUM = set(P100_MAP.values()) | set(ADV_MAP.values())
NUM -= {'player_name','team','pos','player_id'}

def to_num(v):
    if v is None: return None
    v = str(v).strip()
    return None if v == '' else float(v)

def read_bbref(path):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        rd = csv.DictReader(fh)
        hdr = rd.fieldnames
        rows = []
        for r in rd:
            if len(r) != len(hdr): continue
            if r.get('Player') in ('Player', 'League Average'): continue
            if (r.get('Player-additional') or '').strip() == '-9999': continue
            if not (r.get('Player') or '').strip(): continue
            rows.append(r)
    return rows

def dedup(rows):
    c = collections.Counter(r['Player-additional'] for r in rows)
    dups = {k for k, v in c.items() if v > 1}
    for pid in dups:
        if not any(r['Team'] in MULTI for r in rows if r['Player-additional'] == pid):
            raise SystemExit(f'FATAL: duplicate {pid} has no combined-team row')
    return [r for r in rows if r['Team'] in MULTI or r['Player-additional'] not in dups]

# ---------------------------------------------------------------- build player_seasons
log = []
player_seasons = {}
player_team_seasons = []   # one row per player-team stint (traded players appear once per team)
name_by_id = {}
for tag, season in SEASONS.items():
    p_all = read_bbref(RAW / f'{tag}p100.txt')
    a_all = read_bbref(RAW / f'{tag}adv.txt')
    # Advanced stats keyed by (player, team) so per-stint usage is available for traded
    # players too -- the adv files carry the same team-split structure as per100.
    adv_split = {(r['Player-additional'], r['Team']): r for r in a_all if r['Team'] not in MULTI}
    # team-split view: real team codes only. For traded players this is their per-team
    # stints; for everyone else it is their single row. Correct basis for team rollups.
    for r in p_all:
        if r['Team'] in MULTI: continue
        av = adv_split.get((r['Player-additional'], r['Team']), {})
        player_team_seasons.append({
            'player_id': r['Player-additional'], 'player_name': r['Player'], 'season': season,
            'team': team_canon(r['Team']), 'g': to_num(r['G']), 'mp': to_num(r['MP']),
            'pts_p100': to_num(r['PTS']), 'fga_p100': to_num(r['FGA']), 'fta_p100': to_num(r['FTA']),
            'trb_p100': to_num(r['TRB']), 'ast_p100': to_num(r['AST']), 'tov_p100': to_num(r['TOV']),
            'stl_p100': to_num(r['STL']), 'blk_p100': to_num(r['BLK']), 'fg3_p100': to_num(r['3P']),
            'usg_pct': to_num(av.get('USG%')), 'ts_pct': to_num(av.get('TS%')), 'bpm': to_num(av.get('BPM')),
        })
    p = dedup(p_all)
    a = dedup(read_bbref(RAW / f'{tag}adv.txt'))
    pi = {r['Player-additional']: r for r in p}
    ai = {r['Player-additional']: r for r in a}
    assert set(pi) == set(ai), f'{season}: per100/adv id mismatch'
    for pid, r in pi.items():
        rec = {'player_id': pid, 'season': season}
        for src, dst in P100_MAP.items():
            rec[dst] = r.get(src)
        for src, dst in ADV_MAP.items():
            rec[dst] = ai[pid].get(src)
        rec['multi_team'] = r['Team'] in MULTI
        rec['team'] = None if r['Team'] in MULTI else team_canon(r['Team'])
        rec['teams_played'] = r['Team'] if r['Team'] in MULTI else team_canon(r['Team'])
        for k in NUM:
            if k in rec: rec[k] = to_num(rec[k])
        # derived per-game-independent totals
        if rec['mp'] and rec['g']:
            rec['mpg'] = round(rec['mp'] / rec['g'], 2)
        player_seasons[(pid, season)] = rec
        name_by_id[pid] = r['Player']
    log.append(f'{season}: {len(pi)} players')

# ---------------------------------------------------------------- team_seasons + pace
wb = load_workbook(RAW / 'team_stats.xlsx', read_only=True)
ws = wb.active
rows = [list(r) for r in ws.iter_rows(values_only=True)]
hdr = rows[0]
team_rows = []
i = 1
while i < len(rows):
    r = rows[i]
    if r[0] is not None and str(r[0]).strip().isdigit():
        d = dict(zip(hdr, r))
        d['_name'] = str(rows[i + 1][1]).strip() if i + 1 < len(rows) else None
        team_rows.append(d); i += 2
    else:
        i += 1
if len(team_rows) != 30:
    raise SystemExit(f'FATAL: parsed {len(team_rows)} teams, expected 30')

teams_season = {}
for d in team_rows:
    canon = team_canon(d['_name'])
    if not canon:
        raise SystemExit(f'FATAL: unmapped team name {d["_name"]!r}')
    teams_season[canon] = {
        'team': canon, 'season': '2025-26', 'team_name': d['_name'],
        'gp': d['GP'], 'w': d['W'], 'l': d['L'],
        'pts_pg': d['PTS'], 'fga_pg': d['FGA'], 'fta_pg': d['FTA'],
        'oreb_pg': d['OREB'], 'dreb_pg': d['DREB'], 'tov_pg': d['TOV'],
        'pace_simple': round(d['FGA'] + 0.44 * d['FTA'] - d['OREB'] + d['TOV'], 2),
    }
if len(teams_season) != 30:
    raise SystemExit(f'FATAL: {len(teams_season)} canonical teams after mapping')

# implied pace: solve  sum_p (pts_p100/100 * P * mp/(48*GP)) = pts_pg
by_team = collections.defaultdict(list)
for rec in player_team_seasons:
    if rec['season'] == '2025-26':
        by_team[rec['team']].append(rec)
for canon, t in teams_season.items():
    ps = by_team.get(canon, [])
    denom = sum((r['pts_p100'] or 0) / 100 * (r['mp'] or 0) / (48 * t['gp']) for r in ps)
    t['pace_implied'] = round(t['pts_pg'] / denom, 2) if denom else None
    t['minutes_share'] = round(sum(r['mp'] or 0 for r in ps) / (240 * t['gp']), 4)

avg_imp = sum(t['pace_implied'] for t in teams_season.values()) / 30
if not (95 <= avg_imp <= 104):
    raise SystemExit(f'FATAL: implied league pace {avg_imp:.1f} out of range')
log.append(f'pace: implied league avg {avg_imp:.2f}')

# ---------------------------------------------------------------- rosters
ROSTER_PAT = re.compile(
    r'\[(?P<pos>C|F|G|F/C|G/F|PF|SF|SG|PG)\]\(\S+\)\s*'
    r'(?P<num>\d{1,2})\s*'
    r'\[(?P<name>[^\]]+)\]\(\S+\)\s*'
    r'(?P<tw>\(TW\))?\s*'
    r'(?P<ft>\d+)\s*ft\s*(?P<inch>\d+)\s*in[^|]*?'
    r'(?P<wt>\d+)\s*lb[^|]*?'
    r'(?P<dob>\d{4}-\d{2}-\d{2})')
HEAD_PAT = re.compile(r'^\[\*\*([^*]+)\*\*\]', re.M)
SEASON_START = datetime.date(2026, 10, 21)  # nominal; only used for age_at_season_start

roster = []
for fname in ['east_rosters_26.docx', 'West_Rosters_26.docx']:
    txt = open(RAW / fname, encoding='utf-8').read()
    heads = [(m.start(), m.group(1)) for m in HEAD_PAT.finditer(txt)]
    heads = [(pos, nm) for pos, nm in heads if team_canon(nm)]
    for idx, (start, nm) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(txt)
        canon = team_canon(nm)
        found = 0
        for m in ROSTER_PAT.finditer(txt[start:end]):
            dob = datetime.date.fromisoformat(m.group('dob'))
            age = SEASON_START.year - dob.year - ((SEASON_START.month, SEASON_START.day) < (dob.month, dob.day))
            roster.append({
                'team': canon, 'season': '2026-27',
                'roster_name': m.group('name').strip(),
                'name_norm': norm_name(m.group('name')),
                'pos_roster': m.group('pos'), 'jersey': int(m.group('num')),
                'two_way': bool(m.group('tw')),
                'height_in': int(m.group('ft')) * 12 + int(m.group('inch')),
                'weight_lb': int(m.group('wt')),
                'dob': m.group('dob'), 'age_at_season_start': age,
            })
            found += 1
        if not (13 <= found <= 21):
            raise SystemExit(f'FATAL: {canon} parsed {found} players (expected 13-21)')
teams_seen = {r['team'] for r in roster}
if len(teams_seen) != 30:
    raise SystemExit(f'FATAL: rosters cover {len(teams_seen)} teams')
log.append(f'rosters: {len(roster)} entries, {sum(1 for r in roster if r["two_way"])} two-way, 30 teams')

# ---------------------------------------------------------------- crosswalk
import difflib
norm2ids = collections.defaultdict(set)
for pid, nm in name_by_id.items():
    for k in name_keys(nm):
        norm2ids[k].add(pid)
ambiguous = {k: v for k, v in norm2ids.items() if len(v) > 1}
all_keys = list(norm2ids)

matched = unmatched = 0
for r in roster:
    ids = set()
    for k in name_keys(r['roster_name']):
        ids |= norm2ids.get(k, set())
    if len(ids) == 1:
        r['player_id'] = next(iter(ids)); r['match'] = 'exact'; matched += 1
    else:
        r['player_id'] = None
        r['match'] = 'ambiguous' if ids else 'none'
        # Suggest only when the SURNAME matches exactly -- otherwise unrelated players
        # with similar first names (Dillon vs Davion Mitchell) produce false flags.
        surname = r['name_norm'].split()[-1] if r['name_norm'] else ''
        first = ' '.join(r['name_norm'].split()[:-1])
        pool = {k: ' '.join(k.split()[:-1]) for k in all_keys if k.split()[-1:] == [surname]}
        # Compare FIRST names only, with the surname already pinned. Comparing full
        # strings lets a shared surname carry the score (Dillon/Davion Mitchell).
        near = difflib.get_close_matches(first, list(pool.values()), n=1, cutoff=0.82)
        r['fuzzy_suggestion'] = ''
        if near:
            key = next(k for k, v in pool.items() if v == near[0])
            cand = sorted(norm2ids[key])
            r['fuzzy_suggestion'] = f'{name_by_id[cand[0]]} ({cand[0]})'
        unmatched += 1
log.append(f'crosswalk: {matched} matched, {unmatched} unmatched, {len(ambiguous)} ambiguous norm-names')

rostered_ids = {r['player_id'] for r in roster if r['player_id']}
last = {pid for (pid, s) in player_seasons if s == '2025-26'}
unrostered = sorted(last - rostered_ids, key=lambda p: -(player_seasons[(p, '2025-26')]['mp'] or 0))

# ---------------------------------------------------------------- vacated opportunity
vac = []
for canon in teams_season:
    prev = [r for r in by_team.get(canon, [])]
    stay = {r['player_id'] for r in roster if r['team'] == canon and r['player_id']}
    gone = [r for r in prev if r['player_id'] not in stay]
    vac.append({
        'team': canon,
        'mp_2526_single_team': sum(r['mp'] or 0 for r in prev),
        'mp_vacated': sum(r['mp'] or 0 for r in gone),
        'pct_vacated': round(100 * sum(r['mp'] or 0 for r in gone) / max(1, sum(r['mp'] or 0 for r in prev)), 1),
        'pts_p100_wtd_vacated': round(sum((r['pts_p100'] or 0) * (r['mp'] or 0) for r in gone) / max(1, sum(r['mp'] or 0 for r in gone)), 1),
        # Spec 3.5 calls for usage-weighted vacancy: minutes tell you playing time freed,
        # usage tells you shots and possessions freed. They diverge for low-usage minute
        # eaters vs high-usage bench scorers.
        'usg_wtd_vacated': round(sum((r['usg_pct'] or 0) * (r['mp'] or 0) for r in gone) / max(1, sum(r['mp'] or 0 for r in gone)), 1),
        'usg_minutes_vacated': round(sum((r['usg_pct'] or 0) * (r['mp'] or 0) for r in gone) / 100, 0),
        'n_departed': len(gone),
    })
vac.sort(key=lambda x: -x['pct_vacated'])

# ---------------------------------------------------------------- write
def write_csv(name, rows, cols=None):
    if not rows: return
    cols = cols or list(rows[0].keys())
    with open(OUT / name, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)
    print(f'  {name}: {len(rows)} rows x {len(cols)} cols')

ps_rows = [player_seasons[k] for k in sorted(player_seasons, key=lambda k: (k[1], -(player_seasons[k]['mp'] or 0)))]
ps_cols = ['player_id','player_name','season','age','team','teams_played','multi_team','pos','g','gs','mp','mpg'] + \
          [c for c in P100_MAP.values() if c not in ('player_id','player_name','age','team','pos','g','gs','mp')] + \
          list(ADV_MAP.values())
ps_cols = list(dict.fromkeys(ps_cols))

print('\nwriting to', OUT)
write_csv('player_seasons.csv', ps_rows, ps_cols)
write_csv('teams.csv', [{'team':c,'team_name':f,'conference':cf,'division':d,'aliases':'|'.join(al)} for c,f,cf,d,al in TEAMS])
write_csv('team_seasons.csv', sorted(teams_season.values(), key=lambda t: -t['pace_implied']))
write_csv('rosters_2627.csv', sorted(roster, key=lambda r: (r['team'], r['roster_name'])))
write_csv('crosswalk_unmatched.csv', sorted([r for r in roster if not r['player_id']], key=lambda r: (r['match'], r['team'])), ['team','roster_name','pos_roster','jersey','two_way','dob','age_at_season_start','match','fuzzy_suggestion'])
write_csv('unrostered_players.csv', [{'player_id':p,'player_name':name_by_id[p],
                                      'team_2526':player_seasons[(p,'2025-26')]['teams_played'],
                                      'mp_2526':player_seasons[(p,'2025-26')]['mp'],
                                      'mpg_2526':player_seasons[(p,'2025-26')].get('mpg')} for p in unrostered])
write_csv('vacated_opportunity.csv', vac)
write_csv('player_team_seasons.csv', player_team_seasons)

print('\n'.join('  ' + l for l in log))
json.dump({'log':log,'ambiguous_names':{k:sorted(v) for k,v in ambiguous.items()},
           'pace_league_avg_implied':round(avg_imp,2)},
          open(OUT/'build_report.json','w'), indent=2)
