"""Import captures and team unit losses from a CowParser game_data.json.

Usage: python3 scripts/import_news.py <game id>
Reads games/<id>/game_data.json and accumulates into games/<id>/gd_events.json (deduplicated by
articleId), so news that has scrolled out of the game's newspaper is kept from earlier fetches.
Timeline key = minutes since local midnight of the day on which game day 2 starts (see common.clock).
"""
import json, sys, os, datetime as dt
from common import game_dir, clock, TZ

GD = game_dir(sys.argv[1])
src = os.path.join(GD, 'game_data.json')
st = json.load(open(src, encoding='utf-8'))['result']['states']
BASE, _T0 = clock(GD, st)
nation = {int(k): v.get('nationName') for k, v in st['1']['players'].items() if isinstance(v, dict)}
loc = {l['id']: l.get('n') for l in st['3']['map']['locations'] if isinstance(l, dict) and 'id' in l}
units = {**st['11'].get('unitTypes', {}), **st['11'].get('allUnitTypes', {})}
uname = lambda i: (units.get(str(i)) or {}).get('unitName') or f'Unit {i}'

# teams come from the game itself: every nation played by a human with team 1 = Green (G), team 2 = Red (R)
TEAMKEY = {1: 'G', 2: 'R'}
TEAM = {}
for k, p in st['1']['players'].items():
    if not isinstance(p, dict) or int(k) <= 0: continue
    human = p.get('siteUserID', -1) not in (-1, 0, None) and not p.get('computerPlayer')
    if human and p.get('teamID') in TEAMKEY: TEAM[p.get('nationName')] = TEAMKEY[p['teamID']]

out = os.path.join(GD, 'gd_events.json')
db = json.load(open(out, encoding='utf-8')) if os.path.exists(out) else {'caps': {}, 'loss': {}}
db.setdefault('cas', {})
if TEAM: db['teams'] = TEAM   # latest known team per nation
# player slot per nation: the newspaper unit code (A 26, BW 22) is built from it
db['slots'] = {v: k for k, v in nation.items() if v and k > 0}
# today's newspaper plus the newspapers of earlier days that fetch.js saved in news_days/<day>.json
ND = os.path.join(GD, 'news_days')
papers = [(None, st['2'].get('newsArticles', []))]
if os.path.isdir(ND):
    for f in sorted(os.listdir(ND), key=lambda x: int(x.split('.')[0]) if x.split('.')[0].isdigit() else 0):
        if f.endswith('.json'):
            try: papers.append((int(f.split('.')[0]), json.load(open(os.path.join(ND, f), encoding='utf-8')).get('newsArticles', [])))
            except Exception as e: print('skip', f, e)
nc = nl = 0
for day, arts in papers:
  for a in arts:
      ad = a.get('articleData', {}); c = ad.get('@c'); aid = str(a.get('articleId'))
      t = int((dt.datetime.fromtimestamp(a['ingameTime'] / 1000, TZ) - BASE).total_seconds() // 60)
      if c == 'ProvinceCapturedArticleData':
          cp, army = ad['capturedProvince'], ad['conqueringArmy']
          p, who = loc.get(cp['locationId']), nation.get(army['ownerId'])
          if not p or not who: continue
          if aid not in db['caps']: nc += 1
          db['caps'][aid] = dict(t=t, p=p, c=who, u=uname(army['type']), cap=bool(cp.get('isCapital')), no=army.get('armyNumber'),
                                 sn=army.get('size'), frm=nation.get(cp['ownerId']))
      elif c == 'RevoltArticleData':
          # a province rising up and joining another nation also changes the owner
          pr = ad.get('province', {}); p = loc.get(pr.get('locationId')); who = nation.get(ad.get('newOwnerId'))
          if not p or not who or ad.get('newOwnerId') == ad.get('oldOwnerId'): continue
          if aid not in db['caps']: nc += 1
          db['caps'][aid] = dict(t=t, p=p, c=who, u='Revolt', cap=False, rev=True, frm=nation.get(ad.get('oldOwnerId')))
      elif c == 'UnitsDestroyedArticleData':
          army = ad['army']; who = nation.get(army['ownerId'])
          if not who: continue   # all nations are kept; the page shows the ones that are in a team
          # location comes from the matching ArmyDestroyedArticleData (same armyId)
          # whole army gone -> there is an ArmyDestroyedArticleData with the place; otherwise a partial loss
          # (the game does not say where a partial loss happened)
          ad2 = next((b['articleData'] for b in arts
                      if b['articleData'].get('@c') == 'ArmyDestroyedArticleData'
                      and b['articleData']['destroyedArmy']['armyId'] == army['armyId']), None)
          where = loc.get(ad2['location']['locationId']) if ad2 else None
          n = sum(ad['destroyedUnits'].values())
          what = ', '.join(f"{c}× {uname(u)}" for u, c in ad['destroyedUnits'].items())
          if aid not in db['loss']: nl += 1
          db['loss'][aid] = dict(t=t, p=where, c=who, u=uname(army['type']), what=what, n=n, dest=bool(ad2), no=army.get('armyNumber'),
                                 byno=ad2['enemyArmy'].get('armyNumber') if ad2 and ad2.get('enemyArmy') else None,
                                 byu=uname(ad2['enemyArmy']['type']) if ad2 and ad2.get('enemyArmy') else None,
                                 byn=ad2['enemyArmy'].get('size') if ad2 and ad2.get('enemyArmy') else None,
                                 by=nation.get(ad2['enemyArmy']['ownerId']) if ad2 and ad2.get('enemyArmy') else None)
      elif c == 'CasualtiesArticleData':
          v, e = nation.get(ad.get('victimId')), nation.get(ad.get('enemyId'))
          if not v or not e: continue
          key = f'{v}|{e}'; old = db['cas'].get(key)
          if not old or ad['casualties'] >= old['v']:
              db['cas'][key] = dict(v=ad['casualties'], ts=a['ingameTime'])
# remember which earlier days are stored, so fetch.js does not ask for them again
done = set(db.get('news_days', []))
for day, _ in papers:
    if day is not None: done.add(day)
db['news_days'] = sorted(done)
for day, _ in papers:
    if day is not None: os.remove(os.path.join(ND, f'{day}.json'))
# the game's own statistics: units lost per nation and type over the whole game (authoritative totals,
# also counts losses the newspaper never reported, e.g. ships sunk at sea)
col = {}
for u in units.values():
    if isinstance(u, dict) and 'statsColumnID' in u: col.setdefault(u['statsColumnID'], u.get('typeName') or u.get('unitName'))
stats = {}
for pid, days in (st.get('30', {}).get('playerIDToDaysStatsMap') or {}).items():
    n = nation.get(int(pid))
    if not n: continue
    for s_ in days.values():
        for k, v in s_.items():
            m = __import__('re').match(r'unit(\d+)lost$', k)
            if m and v: stats.setdefault(n, {}); stats[n][col.get(int(m.group(1)), 'Unit')] = stats[n].get(col.get(int(m.group(1)), 'Unit'), 0) + v
if stats: db['stats'] = dict(lost=stats, ts=int(st['30'].get('timeStamp', 0)))
json.dump(db, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'new captures {nc}, new unit losses {nl}; stored caps {len(db["caps"])}, losses {len(db["loss"])}, casualty pairs {len(db["cas"])}')

