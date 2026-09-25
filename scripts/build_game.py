"""Build the map page of one game.

Usage: python3 scripts/build_game.py <game id>
Reads the map (map/), the game's history (games/<id>/: gd_events.json from import_news.py, the
latest game_data.json, optional frozen.json with older history) and writes
site/games/<id>/index.html plus games/<id>/summary.json for the overview page.
"""
import json, os, re, io, sys, base64
import numpy as np
from PIL import Image
from common import MAP, SITE, game_dir, clock, tkey, load_registry, config

GID = sys.argv[1]
GD = game_dir(GID)
G = lambda f: os.path.join(GD, f)
GAME_JSON = G('game_data.json')
os.chdir(MAP)   # map files are opened by their plain names below
SC = 0.6
# fallback only; the real teams are read from the game data on every run (gd_events.json -> teams)
T_FALLBACK = {"Southern United States": "G", "France": "G", "Germany": "G", "Poland": "G", "Communist Russia": "G",
              "Libya": "R", "Algeria": "R", "Greater Romania": "R", "Russian Empire": "R", "Ukraine": "R"}
COLS = {'G': (60, 190, 80), 'R': (220, 55, 55), 'X': (245, 215, 40), 'O': (240, 138, 36)}   # O = revolt

_st = json.load(open(GAME_JSON, encoding='utf-8'))['result']['states']
BASE, T0 = clock(GD, _st)
# older history collected before this database existed (only for the first game); new games start empty
d = json.load(open(G('frozen.json'), encoding='utf-8')) if os.path.exists(G('frozen.json')) else \
    dict(w=2900, h=1876, caps=[], atk=[], loss=[], pos={}, ov={})
d['t0'] = T0
d['base'] = [BASE.year, BASE.month, BASE.day]
gd = json.load(open(G('gd_events.json'), encoding='utf-8')) if os.path.exists(G('gd_events.json')) else {'caps': {}, 'loss': {}}
T = gd.get('teams') or T_FALLBACK
cs = json.load(open(G('cap_seed.json'), encoding='utf-8')) if os.path.exists(G('cap_seed.json')) else {}
n2s = json.load(open('name2seed.json', encoding='utf-8')) if os.path.exists('name2seed.json') else {}
clean = lambda s: re.sub(r"^[^A-Za-zÀ-ÿ]+|[^A-Za-zÀ-ÿ]+$", '', s)
by_ocr = {}
for k, v in json.load(open('seed_names.json', encoding='utf-8')).items():
    by_ocr.setdefault(clean(v), int(k))
seeds = np.load('seeds_v6.npy')

def seed_of(p):
    if p not in cs and p in n2s:
        cs[p] = n2s[p]
    if p not in cs and p in by_ocr:
        cs[p] = by_ocr[p]
    return cs.get(p)

_arr = {}
def arrays():
    if not _arr:
        z = np.load('maparrays.npz'); _arr.update(ws=z['ws'], landf=z['landf'], gray=z['gray'].astype(np.float32))
    return _arr

def overlay(p, k):
    A = arrays(); rid = cs[p] + 2
    ys, xs = np.nonzero(A['ws'] == rid)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    m = (A['ws'][y0:y1, x0:x1] == rid) & A['landf'][y0:y1, x0:x1]
    g3 = np.stack([A['gray'][y0:y1, x0:x1]] * 3, -1)
    tint = np.clip(g3 * 0.45 + np.array(COLS[k], np.float32) * 0.55 * (g3 / 170), 0, 255).astype(np.uint8)
    X0, Y0 = int(x0 * SC), int(y0 * SC); X1, Y1 = int(np.ceil(x1 * SC)), int(np.ceil(y1 * SC))
    rgba = np.zeros((y1 - y0, x1 - x0, 4), np.uint8); rgba[..., :3] = tint; rgba[..., 3] = m * 255
    im = Image.fromarray(rgba).resize((X1 - X0, Y1 - Y0), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True)
    return [X0, Y0, X1 - X0, Y1 - Y0], 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()

# sea zones and rivers have no province seed; fixed marker positions on the page map (0.6 scale)
NAVAL = r'Cruiser|Destroyer|Submarine|Battleship|Carrier|Transport'
SEA_NEAR = {'St. Lawrence River': 'Quebec', 'Kattegat': 'Gothenburg'}
SEA_POS = {'Strait of Florida': [274, 1750], 'Volga River': [2868, 849]}

def to_water(x, y, clear=4, reach=60):
    """Nearest open-water spot to page point (x, y): at least `clear` blocks (4 px each, full map) from any land."""
    L = arrays()['landf']; B = 4
    cx, cy = int(x / SC / B), int(y / SC / B)
    H, W = L.shape[0] // B, L.shape[1] // B
    y0, y1, x0, x1 = max(0, cy - reach), min(H, cy + reach + 1), max(0, cx - reach), min(W, cx + reach + 1)
    blk = L[y0 * B:y1 * B, x0 * B:x1 * B]
    blk = blk[:blk.shape[0] // B * B, :blk.shape[1] // B * B].reshape(blk.shape[0] // B, B, blk.shape[1] // B, B).any((1, 3))
    near = blk.copy()          # grow land by `clear` blocks; what stays free is open water
    for _ in range(clear):
        g = near.copy(); g[1:] |= near[:-1]; g[:-1] |= near[1:]; g[:, 1:] |= near[:, :-1]; g[:, :-1] |= near[:, 1:]; near = g
    best = None
    for c in range(clear, -1, -1):
        # prefer open water, but in a narrow river or strait accept a spot closer to the shore rather than
        # jumping far away from the place (a spot 10+ blocks away is only used when nothing nearer exists)
        ys, xs = np.nonzero(~near)
        if len(ys):
            d2 = (ys + y0 - cy) ** 2 + (xs + x0 - cx) ** 2; i = int(np.argmin(d2))
            best = [round((xs[i] + x0 + .5) * B * SC, 1), round((ys[i] + y0 + .5) * B * SC, 1)]
            if d2[i] <= 10 ** 2: return best
        near = blk.copy()
        for _ in range(c - 1):
            g = near.copy(); g[1:] |= near[:-1]; g[:-1] |= near[1:]; g[:, 1:] |= near[:, :-1]; g[:, :-1] |= near[:, 1:]; near = g
    return best

def place(p):
    if p in d['pos']: return True
    if p in SEA_POS: d['pos'][p] = SEA_POS[p]; return True
    s = seed_of(p)
    if s is None: return False
    x, y = seeds[s]; d['pos'][p] = [round(float(x) * SC, 1), round(float(y) * SC, 1)]; return True

def need_overlay(p, k):
    ov = d['ov'].setdefault(p, {'box': None, 'img': {}})
    if k not in ov['img'] and seed_of(p) is not None:
        box, img = overlay(p, k); ov['img'][k] = img; ov['box'] = ov['box'] or box

for e in d['caps']:
    e['k'] = 'O' if e.get('rev') else T.get(e['c'], 'X'); need_overlay(e['p'], e['k'])
for e in d['atk']:
    e['k'] = T.get(e['c'], 'X')

# newspaper unit code, e.g. Germany's 26th unit = A26, Austria's 2nd = BA2
# (prefix = player slot - 1 written in base 25 with letters A..Y, exactly as the game prints it)
SLOTS = gd.get('slots', {})
def prefix(nation):
    n = SLOTS.get(nation)
    if not n: return None
    n -= 1; out = ''
    while True:
        out = 'ABCDEFGHIJKLMNOPQRSTUVWXY'[n % 25] + out; n //= 25
        if not n: return out
def code(nation, no):
    p = prefix(nation)
    return f'{p}{no}' if p and no else None

skipped = []
have = {(e['t'], e['p'], e['c']) for e in d['caps']}
for e in sorted(gd['caps'].values(), key=lambda e: e['t']):
    if (e['t'], e['p'], e['c']) in have: continue
    if seed_of(e['p']) is None or not place(e['p']):
        skipped.append(e['p']); continue
    k = 'O' if e.get('rev') else T.get(e['c'], 'X'); need_overlay(e['p'], k)
    d['caps'].append(dict(t=e['t'], p=e['p'], c=e['c'], u=e['u'], cap=e['cap'], k=k, no=e.get('no'), sn=e.get('sn'), rev=e.get('rev'), frm=e.get('frm'))); have.add((e['t'], e['p'], e['c']))
d['caps'].sort(key=lambda e: e['t'])

# owner check: compare the timeline with who really holds each province in the game right now.
# A province held by a different side than the timeline says (capture missing from every newspaper we have)
# gets a 'holds it' entry at the time we first saw it; that time is remembered in gd_events.json.
def owner_sync(game_json):
    try:
        st = json.load(open(game_json, encoding='utf-8'))['result']['states']
    except Exception:
        return 0
    nat = {int(k): v.get('nationName') for k, v in st['1']['players'].items() if isinstance(v, dict)}
    fetched = int(st['2'].get('timeStamp', 0)) // 1000
    import datetime as _dt
    from zoneinfo import ZoneInfo
    tnow = tkey(BASE, fetched)
    last = {}
    for e in sorted(d['caps'], key=lambda e: e['t']):
        if not e.get('sync'): last[e['p']] = e
    sync = gd.setdefault('sync', {}); keep = {}; n = 0
    for l in st['3']['map']['locations']:
        if not isinstance(l, dict) or l.get('@c') != 'p' or l['n'] not in n2s: continue
        p = l['n']; o = nat.get(l.get('o')); core = nat.get((l.get('ci') or [None])[0])
        ot = T.get(o, 'X'); expect = T.get(last[p]['c'], 'X') if p in last else T.get(core, 'X')   # compare by owner's team (revolts are drawn orange)
        if ot == expect: continue
        if ot == 'X' and o == core and p not in last: continue
        prev = sync.get(p)
        t = prev['t'] if prev and prev['c'] == o else tnow
        keep[p] = dict(t=t, c=o)
    gd['sync'] = keep
    json.dump(gd, open(G('gd_events.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for p, v in keep.items():
        if seed_of(p) is None or not place(p): continue
        k = T.get(v['c'], 'X'); need_overlay(p, k)
        d['caps'].append(dict(t=v['t'], p=p, c=v['c'], u='', cap=False, k=k, sync=True)); n += 1
    d['caps'].sort(key=lambda e: e['t'])
    return n
synced = owner_sync(GAME_JSON)
for e in d['caps']:
    e['id'] = code(e['c'], e.get('no'))

watered = set()
# unit losses: audited report losses (frozen) + game news; same minute (±1), nation and unit type = same event
def dup(e):
    return any(abs(x['t'] - e['t']) <= 1 and x['c'] == e['c'] and x.get('u') == e.get('u') for x in d['loss'])
for e in gd['loss'].values():
    if not dup(e): d['loss'].append(dict(e))
all_loss = list(d['loss'])   # every reported loss, incl. nations outside both teams (e.g. a captured neutral's garrison)
for e in all_loss:
    e['id'] = code(e['c'], e.get('no')); e['byid'] = code(e.get('by'), e.get('byno'))
    e.setdefault('n', 1)
# a unit (stack) often dies over several reports: first single units are killed (a partial loss, the game
# does not say where), later the rest is wiped out at a named place. Link those partial losses to that
# final fight (same nation + unit number, within 6 h) so they get its place, and give the final fight the
# total number of units the stack lost
linked = 0
for x in sorted(all_loss, key=lambda e: e['t']):
    if x.get('p') or x.get('dest') or not x.get('no'): continue
    y = next((y for y in sorted(all_loss, key=lambda e: e['t']) if y is not x and y['c'] == x['c'] and y.get('no') == x['no']
              and y.get('p') and 0 <= y['t'] - x['t'] <= 360), None)
    if y:
        x['p'] = y['p']; x['pinf'] = True; y['tot'] = y.get('tot', y.get('n', 1)) + x.get('n', 1); linked += 1
print(f'  partial losses placed at the fight that finished the unit: {linked}')
# fill in the attacker from the battle reports (attacks list: who hit this place at that minute, with how
# many units) where the newspaper left it out, and the attacker's stack size where only the type is known
def _atk_for(e):
    c = [a for a in d['atk'] if a.get('p') == e.get('p') and a.get('d') == e['c'] and abs(a['t'] - e['t']) <= 2
         and (not e.get('by') or a['c'] == e['by']) and (not e.get('byu') or a['u'] == e['byu'])]
    return min(c, key=lambda a: (abs(a['t'] - e['t']), -a['n'])) if c else None
def _no_for(nat, u, p, t):
    c = [x for x in d['caps'] if x['c'] == nat and x.get('p') == p and x.get('u') == u and abs(x['t'] - t) <= 2 and x.get('no')]
    return c[0]['no'] if c else None
filled = 0
for e in all_loss:
    if e.get('p') and (not e.get('by') or not e.get('byn')):
        a = _atk_for(e)
        if a:
            if not e.get('by'): e['by'], e['byu'] = a['c'], a['u']; filled += 1
            if not e.get('byu'): e['byu'] = a['u']
            if not e.get('byn'): e['byn'] = a['n']
    if e.get('by') and not e.get('byno'):
        e['byno'] = _no_for(e['by'], e.get('byu'), e.get('p'), e['t'])
    e['byid'] = code(e.get('by'), e.get('byno'))
print(f'  attacker filled in from battle reports: {filled}')
# manual unit-type corrections (unit_fix.json): the newspaper names a fleet after one ship type, which
# is not always what the stack really is. Key = unit code (e.g. "E1" = Spain's unit 1); only the given
# type is replaced, because unit numbers are reused once a unit is gone (Spain's first E1 was infantry)
UFIX = json.load(open(G('unit_fix.json'), encoding='utf-8')) if os.path.exists(G('unit_fix.json')) else {}
UFIX = {k: v for k, v in UFIX.items() if not k.startswith('_')}
for e in all_loss + d['caps']:
    f = UFIX.get(e.get('byid') or '')
    if f and e.get('byu') == f['from']: e['byu'] = f['to']
    f = UFIX.get(e.get('id') or '')
    if f and e.get('u') == f['from']:
        e['u'] = f['to']
        if e.get('what'): e['what'] = e['what'].replace(f['from'], f['to'])
# every loss is kept: a team unit lost ("Unit losses") and any AI/non-team unit lost, whoever killed it
# ("AI deaths"); the colour follows the team involved, grey when two AI nations fought each other
for e in d['loss']:
    e['ai'] = T.get(e['c']) not in ('G', 'R')
    e['k'] = T.get(e['c']) or T.get(e.get('by')) or 'N'
    if e.get('p') and not place(e['p']):
        # sea zones and rivers have no fixed spot: put the marker next to the nearest land place this ship
        # was last seen at (a province it bombarded or fought over), else next to a known coast province
        ref = None
        seen = [x for x in d['loss'] + d['caps'] + list(gd['loss'].values()) if x is not e and abs(x['t'] - e['t']) <= 360 and x.get('p') and place(x['p'])
                and ((x.get('by') == e['c'] and x.get('byno') == e.get('no')) or (x['c'] == e['c'] and x.get('no') == e.get('no') and x in d['caps']))]
        if e.get('no') and seen: ref = min(seen, key=lambda x: abs(x['t'] - e['t']))['p']
        if not ref and SEA_NEAR.get(e['p']) and place(SEA_NEAR[e['p']]): ref = SEA_NEAR[e['p']]
        if ref:
            key = f"{e['p']} (near {ref})"
            if key not in d['pos']: x, y = d['pos'][ref]; d['pos'][key] = [round(x - 22, 1), round(y + 14, 1)]
            e['p'] = key
        else: e['nopos'] = True   # listed in the feed, no map marker
    if e.get('p') and e['p'] in d['pos'] and (' (near ' in e['p'] or e['p'] in SEA_POS or re.search(NAVAL, e.get('what') or '')):
        # ships and anything lost at sea: the marker always sits in open water, never on land
        if not (' (near ' in e['p'] or e['p'] in SEA_POS):
            key = e['p'] + ' (at sea)'; d['pos'].setdefault(key, d['pos'][e['p']]); e['p'] = key
        if e['p'] not in watered:
            w = to_water(*d['pos'][e['p']])
            if w: d['pos'][e['p']] = w
            watered.add(e['p'])
    if not e.get('p'): e['p'] = None
# reconcile with the game's own loss statistics: anything the newspaper missed is added as an
# extra loss with unknown time and place (so the totals always match the game)
st_ = gd.get('stats') or {}
if st_.get('lost'):
    import datetime as _dt
    from zoneinfo import ZoneInfo as _Z
    tnow = tkey(BASE, st_['ts']) if st_.get('ts') else max(e['t'] for e in d['loss'])
    have = {}
    for e in d['loss']:
        for m in re.finditer(r'(\d+)× ([^,]+)', e.get('what') or ''):
            have[(e['c'], m.group(2).strip())] = have.get((e['c'], m.group(2).strip()), 0) + int(m.group(1))
    for nat, types in st_['lost'].items():
        if T.get(nat) not in ('G', 'R'): continue
        for typ, n in types.items():
            miss = n - have.get((nat, typ), 0)
            if miss > 0:
                d['loss'].append(dict(t=tnow, p=None, c=nat, u=typ, what=f'{miss}× {typ}', n=miss, dest=False, k=T[nat], id=None, byid=None, stat=True))
                print(f'  from game statistics (not in newspaper): {nat} {miss}× {typ}')
d['loss'].sort(key=lambda e: e['t'])

# link each capture (and plain attack) to what the attacking unit destroyed there:
# match on the attacker's own code (nation+unit no.), same place, close in time — includes
# non-team (AI/neutral) nations' losses too, since those don't otherwise appear anywhere
for e in d['caps'] + d['atk']:
    aid = e.get('id')
    if not aid: continue
    kills = [x for x in all_loss if x.get('by') == e['c'] and x.get('p') == e.get('p') and (
             (x.get('byid') == aid and abs(x['t'] - e['t']) <= 60) or
             (not x.get('byid') and x.get('byu') == e.get('u') and abs(x['t'] - e['t']) <= 2))]
    if kills:
        e['kills'] = [dict(c=x['c'], what=x['what'], id=x.get('id')) for x in kills]


# soldiers killed per team nation, cumulative per war (game newspaper casualty reports)
cas = gd.get('cas', {})
nations = {}
for key, v in cas.items():
    victim, enemy = key.split('|')
    if victim in T:
        n = nations.setdefault(victim, dict(c=victim, k=T[victim], total=0, by=[]))
        n['total'] += v['v']; n['by'].append([enemy, v['v']])
for n in nations.values(): n['by'].sort(key=lambda x: -x[1])
d['cas'] = dict(asof=max([v['ts'] for v in cas.values()], default=None),
                teams={k: sum(n['total'] for n in nations.values() if n['k'] == k) for k in 'GR'},
                nations=sorted(nations.values(), key=lambda n: (n['k'], -n['total'])))
d['t1'] = max([e['t'] for e in d['caps'] + d['atk'] + d['loss']] + [T0 + 1])
d['teams'] = {k: sorted(n for n, v in T.items() if v == k) for k in 'GR'}

# base map: each team's home provinces (by the province's original nation) tinted, rebuilt when teams change
def build_base(game_json):
    try:
        st = json.load(open(game_json, encoding='utf-8'))['result']['states']
    except Exception:
        return False
    nat = {int(k): v.get('nationName') for k, v in st['1']['players'].items() if isinstance(v, dict)}
    home = {}
    for l in st['3']['map']['locations']:
        if isinstance(l, dict) and l.get('@c') == 'p' and l['n'] in n2s:
            core = nat.get((l.get('ci') or [None])[0])
            if T.get(core) in ('G', 'R'): home[n2s[l['n']] + 1] = T[core]
    key = json.dumps(sorted(home.items()))
    if os.path.exists(G('base_key.txt')) and open(G('base_key.txt')).read() == key and os.path.exists(G('base.jpg')):
        return False
    b = np.array(Image.open('base_live.jpg').convert('RGB')).astype(np.float32)
    ix = np.array(Image.open('idx.png').convert('RGB')).astype(np.int32); ix = ix[..., 0] + ix[..., 1] * 256
    lut = np.zeros(ix.max() + 1, np.uint8)
    for i, k in home.items():
        if i < len(lut): lut[i] = 1 if k == 'G' else 2
    team = lut[ix]; g = b[..., :1]
    for code, k in ((1, 'G'), (2, 'R')):
        m = team == code
        b[m] = np.clip(g * 0.45 + np.array(COLS[k], np.float32) * 0.55 * (g / 170), 0, 255)[m]
    Image.fromarray(b.astype(np.uint8)).save(G('base.jpg'), quality=82, optimize=True)
    open(G('base_key.txt'), 'w').write(key); return True
base_rebuilt = build_base(GAME_JSON)
import time
d['built'] = int(time.time() * 1000)
_src = GAME_JSON
try:
    d['fetched'] = int(json.load(open(_src, encoding='utf-8'))['result']['states']['2']['timeStamp'])
except Exception:
    d['fetched'] = None

# victory point cities (140, 10 points each) and the nation that held each one at the start of the game
# (vp_cities.json: city -> starting player slot, from the map definition)
if os.path.exists('vp_cities.json'):
    _vp = json.load(open('vp_cities.json', encoding='utf-8'))
    _gs = json.load(open(_src, encoding='utf-8'))['result']['states']
    _nat = {int(k): v.get('nationName') for k, v in _gs['1']['players'].items() if isinstance(v, dict)}
    d['cities'] = list(_vp)
    d['city0'] = {c: _nat.get(s) for c, s in _vp.items()}
    # starting nation of every province (the game's own 'ci' field = original owner), for province counts
    # unit icons per unit type and doctrine (downloaded from DTG by fetch_icons.bat into icons/)
    d['fac'] = {v.get('nationName'): v.get('faction') for v in _gs['1']['players'].values() if isinstance(v, dict)}
    if os.path.isdir('icons'):
        _ut = {**_gs['11'].get('unitTypes', {}), **_gs['11'].get('allUnitTypes', {})}
        icons, ubase = {}, {}
        for _i in json.load(open('icon_ids.json')):
            f = os.path.join('icons', f'{_i}.png')
            if not os.path.exists(f): continue
            im = Image.open(f).convert('RGBA'); im = im.crop(im.getbbox() or (0, 0) + im.size)
            if im.height > im.width * 1.8: im = im.rotate(90, expand=True)   # long ships lie flat so they stay readable
            S = 44; im.thumbnail((S, S), Image.LANCZOS)                            # every icon fits the same square
            sq = Image.new('RGBA', (S, S)); sq.paste(im, ((S - im.width) // 2, (S - im.height) // 2), im)
            # bake a soft light outline into the picture (cheaper than a CSS filter on hundreds of icons)
            from PIL import ImageFilter
            al = sq.split()[3].filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.8)).point(lambda v: min(255, int(v * 0.55)))
            glow = Image.new('RGBA', sq.size, (235, 240, 236, 0)); glow.putalpha(al)
            sq = Image.alpha_composite(glow, sq)
            b = io.BytesIO(); sq.save(b, 'PNG', optimize=True)
            icons[str(_i)] = 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
            x = _ut[str(_i)]; ubase[f"{x['typeName']}|{x['factions'][0]}"] = str(_i)
        # a type without an icon for this doctrine borrows the icon of another doctrine
        for x in _ut.values():
            for fc in (1, 2, 3, 4):
                k = f"{x.get('typeName')}|{fc}"
                if k not in ubase:
                    alt = next((ubase[f"{x.get('typeName')}|{o}"] for o in (1, 2, 3, 4) if f"{x.get('typeName')}|{o}" in ubase), None)
                    if alt: ubase[k] = alt
        d['icons'], d['ubase'] = icons, ubase
    d['prov0'] = {l['n']: _nat.get((l.get('ci') or [None])[0]) for l in _gs['3']['map']['locations']
                  if isinstance(l, dict) and l.get('@c') == 'p'}

# ---- this game's entry in the database: name, status, and a summary for the overview page ----
REG = next((g for g in load_registry()['games'] if str(g['id']) == str(GID)), {'id': GID})
d['gid'] = GID
d['every'] = int(REG.get('every') or 60)          # update interval chosen on the page (minutes)
d['ran'] = REG.get('ran') or d['built']           # last real update (a rebuild without new data keeps it)
d['repo'] = os.environ.get('GITHUB_REPOSITORY') or config().get('repo') or ''
NAME = REG.get('name') or f'Game {GID}'
_gi = _st.get('12', {})
_rank = _st['2'].get('ranking', {})
_nat = {int(k): v.get('nationName') for k, v in _st['1']['players'].items() if isinstance(v, dict)}
_owner = {l['n']: _nat.get(l.get('o')) for l in _st['3']['map']['locations'] if isinstance(l, dict) and l.get('@c') == 'p'}
_score = {k: 10 * sum(1 for c in d.get('cities', []) if T.get(_owner.get(c)) == k) for k in 'GR'}
_prov = {k: sum(1 for o in _owner.values() if T.get(o) == k) for k in 'GR'}
game_over = bool(_gi.get('endOfGame')) or _rank.get('winnerTeam', -1) not in (-1, None, 0)
winner = {1: 'G', 2: 'R'}.get(_rank.get('winnerTeam'))
if REG.get('status') == 'saved':
    d['ended'] = 'Game ended' if REG.get('reason') == 'ended' else 'Stopped and saved'
summary = dict(id=GID, name=NAME, day=_gi.get('dayOfGame'), score=_score, provinces=_prov, fetched=d.get('fetched'),
               built=d['built'], game_over=game_over, winner=winner,
               teams={k: [dict(c=c, f=d.get('fac', {}).get(c)) for c in d['teams'][k]] for k in 'GR'},
               events=len(d['caps']), losses=sum(e.get('n', 1) for e in d['loss']))
json.dump(summary, open(G('summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

html = open('page_template.html', encoding='utf-8').read()
html = html.replace('__TITLE__', NAME.replace('<', '&lt;'))
html = html.replace('__LOGO__', 'data:image/png;base64,' + base64.b64encode(open('logo.png', 'rb').read()).decode() if os.path.exists('logo.png') else '')
html = html.replace('__BASE__', 'data:image/jpeg;base64,' + base64.b64encode(open(G('base.jpg'), 'rb').read()).decode())
# unit icons are shown as <img> with the picture inline (CSS background pictures are blocked where the page is hosted)
html = html.replace('/*__ICONCSS__*/', '')
d['hasIcons'] = bool(d.get('icons'))
html = html.replace('__DATA__', json.dumps(d, ensure_ascii=False).replace('</', '<\\/'))
OUT = os.path.join(SITE, 'games', GID); os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
json.dump(cs, open(G('cap_seed.json'), 'w', encoding='utf-8'), ensure_ascii=False)
last = d['t1']
print(f"owner corrections {synced}, caps {len(d['caps'])}, unit losses {len(d['loss'])} ({sum(e['n'] for e in d['loss'])} units), soldiers killed G {d['cas']['teams']['G']} R {d['cas']['teams']['R']}, teams G {len(d['teams']['G'])} R {len(d['teams']['R'])}{' (base map redrawn)' if base_rebuilt else ''}, latest event {last//60%24:02d}:{last%60:02d}"
      + (f", skipped (no map position): {sorted(set(skipped))}" if skipped else ''))
