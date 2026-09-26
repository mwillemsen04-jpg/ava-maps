"""One update round: fetch every live game, rebuild its map, move finished games to the archive,
and rebuild the overview page.

  python3 scripts/run.py            fetch + build the games that are due (GitHub runs this at :00, :15, :30 and :45)
  python3 scripts/run.py --all      fetch + build every live game, due or not
  python3 scripts/run.py --no-fetch build from the game data already on disk
  python3 scripts/run.py --check    only say whether any game is due (GitHub: writes due=true/false)

Each live game has its own update interval ("every", minutes, default 60) in games.json, chosen on its map page.

Output: site/ (publish this folder). Saved games keep their final page in archive/<id>.html.
"""
import json, os, shutil, subprocess, sys, datetime as dt
from common import ROOT, SITE, GAMES, TZ, load_registry, save_registry, game_dir

PY = sys.executable
ARCHIVE = os.path.join(ROOT, 'archive')


def sh(*cmd):
    print('$', ' '.join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode


def last_mark(every, now_dt):
    """The most recent whole-interval moment in local time: with 60 minutes the last full hour (01:00, 02:00, ...),
    with 30 minutes the last :00 or :30, with 120 minutes the last even hour, and so on (counted from midnight)."""
    mins = now_dt.hour * 60 + now_dt.minute
    return now_dt.replace(second=0, microsecond=0) - dt.timedelta(minutes=mins % every)


def is_due(g, now):
    """A live game is due when it has not been updated since its last whole-interval moment."""
    every = int(g.get('every') or 60)
    mark = last_mark(every, dt.datetime.fromtimestamp(now / 1000, TZ))
    return (g.get('ran') or 0) < int(mark.timestamp() * 1000)


def main():
    fetch = '--no-fetch' not in sys.argv
    reg = load_registry()
    now = int(dt.datetime.now(TZ).timestamp() * 1000)
    # a timed run and a request from the website (Add / Stop / Folders / Update every / Delete) only fetch the
    # games that are due or new; the "Run workflow" button and a local run update every live game
    timed = os.environ.get('GITHUB_EVENT_NAME') in ('schedule', 'issues') and '--all' not in sys.argv
    todo = [g for g in reg['games'] if g.get('rebuild') or (g.get('status') == 'live' and (not timed or is_due(g, now)))]
    if '--check' in sys.argv:
        due = bool(todo)
        print('due' if due else 'nothing due', [str(g['id']) for g in todo])
        if os.environ.get('GITHUB_OUTPUT'):
            open(os.environ['GITHUB_OUTPUT'], 'a').write(f"due={'true' if due else 'false'}\n")
        return
    for g in todo:
        if g.get('status') == 'live':
            g['ran'] = now
    save_registry(reg)
    if fetch and todo:
        sh('node', 'scripts/fetch.js', *[str(g['id']) for g in todo])   # a failed game keeps its last data

    for g in todo:
        gid = str(g['id'])
        if not os.path.exists(os.path.join(game_dir(gid), 'game_data.json')):
            print(f'game {gid}: no game data yet, skipped'); continue
        if sh(PY, 'scripts/import_news.py', gid) or sh(PY, 'scripts/build_game.py', gid):
            print(f'game {gid}: build failed'); continue
        s = json.load(open(os.path.join(GAMES, gid, 'summary.json'), encoding='utf-8'))
        g['last'] = {k: s.get(k) for k in ('day', 'score', 'provinces', 'fetched', 'winner', 'teams')}
        if not g.get('name'):
            g['name'] = s['name']
        if g.get('status') == 'live' and s.get('game_over'):
            # the game has ended: stop updating it and build its final page
            g.update(status='saved', reason='ended', ended=dt.datetime.now(TZ).strftime('%Y-%m-%d %H:%M'))
            save_registry(reg)
            sh(PY, 'scripts/build_game.py', gid)
        if g.get('status') == 'saved':
            os.makedirs(ARCHIVE, exist_ok=True)
            shutil.copyfile(os.path.join(SITE, 'games', gid, 'index.html'), os.path.join(ARCHIVE, f'{gid}.html'))
            g.pop('rebuild', None)
        save_registry(reg)

    # live games that were not due keep the page of their last update (restored from the cache);
    # only when it is missing it is built again from the game data on disk, without fetching
    done = {str(g['id']) for g in todo}
    for g in reg['games']:
        gid = str(g['id'])
        refresh = g.pop('refresh', None)   # e.g. a new update interval: rebuild the page, without fetching new data
        if g.get('status') == 'live' and gid not in done and (refresh or not os.path.exists(os.path.join(SITE, 'games', gid, 'index.html'))) \
                and os.path.exists(os.path.join(game_dir(gid), 'game_data.json')):
            sh(PY, 'scripts/build_game.py', gid)

    # saved games are not rebuilt: their final page comes from the archive
    for g in reg['games']:
        a = os.path.join(ARCHIVE, f"{g['id']}.html")
        out = os.path.join(SITE, 'games', str(g['id']), 'index.html')
        if g.get('status') == 'saved' and os.path.exists(a) and not os.path.exists(out):
            os.makedirs(os.path.dirname(out), exist_ok=True); shutil.copyfile(a, out)
    save_registry(reg)
    sh(PY, 'scripts/build_site.py')


if __name__ == '__main__':
    main()
