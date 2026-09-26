"""Add or stop games in the database (games.json).

  python3 scripts/manage.py add <game id> [name]
  python3 scripts/manage.py stop <game id> [folder]
  python3 scripts/manage.py move <game id> <folder>[; <folder> ...]   (a saved game can be in several folders; "-" = none)
  python3 scripts/manage.py delete <game id>       (saved games only: removes the game and its map for good)
  python3 scripts/manage.py folder <name>           (make an empty folder)
  python3 scripts/manage.py delete-folder <name>    (its games go back to Unsorted)
  python3 scripts/manage.py every <game id> <minutes>   (how often a live game is updated: 15, 30, 60, 120 or 240)
  python3 scripts/manage.py list
  python3 scripts/manage.py from-issue      (GitHub: reads TITLE and BODY from the environment)

A GitHub issue titled "Add game 10917564" (optional "Name: KH vs PHK" in the body),
"Stop game 10917564" (optional "Folder: Season 1" in the body) or
"Move game 10917564 to Season 1; Clan wars" (several folders, "-" for none), "Set update 10917564 every 30", "Delete game 10917564", "Create folder Season 1" or "Delete folder Season 1"
does the same from the website.
"""
import os, re, sys, shutil, datetime as dt
from common import load_registry, save_registry, TZ, ROOT, SITE, game_dir


def today():
    return dt.datetime.now(TZ).strftime('%Y-%m-%d %H:%M')


def add(gid, name=None):
    gid = str(gid).strip()
    if not re.fullmatch(r'\d{6,10}', gid):
        sys.exit(f'"{gid}" is not a game code (6 to 10 digits)')
    reg = load_registry()
    g = next((g for g in reg['games'] if str(g['id']) == gid), None)
    if g and g.get('status') == 'live':
        print(f'game {gid} is already live'); return
    if g:   # a saved game is started again
        g.update(status='live', reason=None, ended=None)
    else:
        reg['games'].append(dict(id=gid, name=(name or '').strip() or None, status='live', added=today()))
    save_registry(reg); print(f'added game {gid}')


def folders_of(g):
    """The folders a game is in (older entries have one "folder" instead of a list)."""
    fl = g.get('folders')
    if fl is None:
        fl = [g['folder']] if g.get('folder') else []
    return [f for f in fl if f]


def split_folders(text):
    """"Season 1; Clan wars" -> ["Season 1", "Clan wars"]; "-" or empty -> no folder."""
    out = []
    for f in re.split(r'[;\n]', text or ''):
        f = f.strip()[:60]
        if f and f != '-' and f not in out:
            out.append(f)
    return out


def set_folders(g, reg, folders):
    g.pop('folder', None)
    if folders:
        g['folders'] = folders
        for f in folders:
            remember(reg, f)
    else:
        g.pop('folders', None)


def stop(gid, reason='stopped', folders=None):
    reg = load_registry()
    g = next((g for g in reg['games'] if str(g['id']) == str(gid)), None)
    if not g:
        sys.exit(f'game {gid} is not in the database')
    if g.get('status') == 'saved':
        print(f'game {gid} is already saved'); return
    g.update(status='saved', reason=reason, ended=today(), rebuild=True)   # the next run builds its final page
    if folders:
        set_folders(g, reg, folders)
    save_registry(reg); print(f'saved game {gid} ({reason})')


def move(gid, folders):
    """Put a game in exactly these folders (a list, or text like "Season 1; Clan wars"; empty = no folder)."""
    reg = load_registry()
    g = next((g for g in reg['games'] if str(g['id']) == str(gid)), None)
    if not g:
        sys.exit(f'game {gid} is not in the database')
    fl = split_folders(folders) if isinstance(folders, str) else list(folders or [])
    set_folders(g, reg, fl)
    save_registry(reg); print(f'game {gid} -> folders {fl or "(none)"}')


def delete(gid):
    gid = str(gid).strip()
    reg = load_registry()
    g = next((g for g in reg['games'] if str(g['id']) == gid), None)
    if not g:
        sys.exit(f'game {gid} is not in the database')
    if g.get('status') != 'saved':
        sys.exit(f'game {gid} is live: stop it first, then delete it')
    reg['games'] = [x for x in reg['games'] if x is not g]
    save_registry(reg)
    for path in (game_dir(gid), os.path.join(SITE, 'games', gid)):
        shutil.rmtree(path, ignore_errors=True)
    a = os.path.join(ROOT, 'archive', f'{gid}.html')
    if os.path.exists(a):
        os.remove(a)
    print(f'deleted game {gid}')


EVERY = (15, 30, 60, 120, 240)   # minutes; the workflow runs every 15 minutes and only updates the games that are due


def set_every(gid, minutes):
    reg = load_registry()
    g = next((g for g in reg['games'] if str(g['id']) == str(gid)), None)
    if not g:
        sys.exit(f'game {gid} is not in the database')
    m = int(minutes)
    if m not in EVERY:
        sys.exit(f'{m} minutes is not a choice ({", ".join(map(str, EVERY))})')
    g['every'] = m
    g['refresh'] = True   # the next run rebuilds its page with the new interval (no extra fetch)
    save_registry(reg); print(f'game {gid}: updated every {m} minutes')


def remember(reg, folder):
    fl = reg.setdefault('folders', [])
    if folder not in fl:
        fl.append(folder)


def make_folder(name):
    name = (name or '').strip()[:60]
    if not name:
        sys.exit('folder name is empty')
    reg = load_registry(); remember(reg, name)
    save_registry(reg); print(f'folder "{name}" ready')


def delete_folder(name):
    name = (name or '').strip()
    reg = load_registry()
    reg['folders'] = [f for f in reg.get('folders', []) if f != name]
    for g in reg['games']:
        fl = folders_of(g)
        if name in fl:
            set_folders(g, reg, [f for f in fl if f != name])
    save_registry(reg); print(f'folder "{name}" removed')


def from_issue():
    title, body = os.environ.get('TITLE', ''), os.environ.get('BODY', '') or ''
    fm = re.match(r'\s*(create|delete)\s+folder\s+(.+)$', title, re.I)
    if fm:
        (make_folder if fm.group(1).lower() == 'create' else delete_folder)(fm.group(2)); return
    em = re.match(r'\s*set\s+update\s+(\d{6,10})\s+every\s+(\d+)', title, re.I)
    if em:
        set_every(em.group(1), em.group(2)); return
    dm = re.match(r'\s*delete\s+game\s+(\d{6,10})\s*$', title, re.I)
    if dm:
        delete(dm.group(1)); return
    mv = re.match(r'\s*move\s+game\s+(\d{6,10})\s+to\s+(.+)$', title, re.I)
    if mv:
        move(mv.group(1), mv.group(2)); return
    m = re.match(r'\s*(add|stop)\s+game\s+(\d{6,10})', title, re.I)
    if not m:
        sys.exit('issue title must be "Add game <code>", "Stop game <code>" or "Move game <code> to <folder>"')
    name = re.search(r'^\s*name\s*:\s*(.+)$', body, re.I | re.M)
    folders = [f for x in re.findall(r'^\s*folders?\s*:\s*(.+)$', body, re.I | re.M) for f in split_folders(x)]
    if m.group(1).lower() == 'add':
        add(m.group(2), name.group(1) if name else None)
    else:
        stop(m.group(2), folders=folders)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if cmd == 'add':
        add(sys.argv[2], ' '.join(sys.argv[3:]) or None)
    elif cmd == 'stop':
        stop(sys.argv[2], folders=split_folders(' '.join(sys.argv[3:])))
    elif cmd == 'move':
        move(sys.argv[2], ' '.join(sys.argv[3:]))
    elif cmd == 'every':
        set_every(sys.argv[2], sys.argv[3])
    elif cmd == 'delete':
        delete(sys.argv[2])
    elif cmd in ('folder', 'delete-folder'):
        name = ' '.join(a for a in sys.argv[2:] if a.strip())
        (make_folder if cmd == 'folder' else delete_folder)(name)
    elif cmd == 'from-issue':
        from_issue()
    else:
        for g in load_registry()['games']:
            print(g['id'], g.get('status'), g.get('name') or '')
