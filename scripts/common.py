"""Shared paths and the game clock for the AVA map database."""
import json, os, datetime as dt
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, 'map')            # the map itself: same for every game
GAMES = os.path.join(ROOT, 'games')        # one folder per game: its collected history
SITE = os.path.join(ROOT, 'site')          # what is published: overview + one map page per game
REGISTRY = os.path.join(ROOT, 'games.json')
CONFIG = os.path.join(ROOT, 'config.json')


def config():
    c = {'timezone': 'Europe/Amsterdam', 'title': 'AVA Games Database'}
    if os.path.exists(CONFIG):
        c.update(json.load(open(CONFIG, encoding='utf-8')))
    return c


TZ = ZoneInfo(config()['timezone'])


def load_registry():
    if not os.path.exists(REGISTRY):
        return {'games': []}
    return json.load(open(REGISTRY, encoding='utf-8'))


def save_registry(reg):
    json.dump(reg, open(REGISTRY, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def game_dir(gid):
    d = os.path.join(GAMES, str(gid))
    os.makedirs(d, exist_ok=True)
    return d


def clock(gdir, states=None):
    """Timeline key = minutes since local midnight of the day on which game day 2 starts.

    Day 2 starts 24 h after the game started; everything before it is not shown.
    Stored once per game in meta.json so the key never shifts between runs.
    Returns (BASE datetime, t0 = minute at which day 2 starts).
    """
    meta_f = os.path.join(gdir, 'meta.json')
    meta = json.load(open(meta_f, encoding='utf-8')) if os.path.exists(meta_f) else {}
    if 'base' not in meta:
        if states is None:
            raise RuntimeError('no game data yet to start the clock')
        start = int(states['12']['startOfGame'])
        day2 = dt.datetime.fromtimestamp(start + 86400, TZ)
        base = day2.replace(hour=0, minute=0, second=0, microsecond=0)
        meta.update(base=[base.year, base.month, base.day], t0=int((day2 - base).total_seconds() // 60), start=start)
        json.dump(meta, open(meta_f, 'w', encoding='utf-8'), indent=1)
    y, m, d = meta['base']
    return dt.datetime(y, m, d, tzinfo=TZ), meta['t0']


def tkey(base, ts):
    """Timeline minute of a unix timestamp (seconds or milliseconds)."""
    if ts > 1e11: ts /= 1000
    return int((dt.datetime.fromtimestamp(ts, TZ) - base).total_seconds() // 60)
