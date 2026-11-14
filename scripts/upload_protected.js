// Uploads the built AVA site to the backend database, so the maps are served
// behind the clan password instead of being public on GitHub.
//
// Runs in the GitHub Action after the site is built. Needs:
//   BACKEND_URL    e.g. https://af-farm-backend.onrender.com
//   CLAN_PASSWORD  the same clan password as on Render
//   SITE           optional, the built-site folder (default "site")
//
// It stores: ava/index (the games list), ava/overview (the overview page) and
// ava/page_<id> (each game's page). Pages bigger than one database document are
// split into ava/page_<id>_0, _1, ... and stitched back together by the backend.

const fs = require('fs');
const path = require('path');

const BASE = (process.env.BACKEND_URL || '').replace(/\/+$/, '');
const PW = process.env.CLAN_PASSWORD || '';
const SITE = process.env.SITE || 'site';
const CHUNK = 700000; // characters per database document (stays under the 1 MB limit)

if (!BASE || !PW) { console.error('Set BACKEND_URL and CLAN_PASSWORD'); process.exit(1); }

function put(name, obj) {
  return fetch(BASE + '/api/doc/' + name, {
    method: 'PUT',
    headers: { 'Authorization': 'Bearer ' + PW, 'Content-Type': 'application/json' },
    body: JSON.stringify(obj)
  }).then(r => {
    if (!r.ok) throw new Error('PUT ' + name + ' -> ' + r.status);
  });
}

// Store an HTML string as one document, or as numbered chunks if it is big.
async function putHtml(name, html) {
  if (html.length <= CHUNK) { await put(name, { html }); return 1; }
  const n = Math.ceil(html.length / CHUNK);
  for (let i = 0; i < n; i++) await put(name + '_' + i, { part: html.slice(i * CHUNK, (i + 1) * CHUNK) });
  await put(name, { chunks: n });
  return n;
}

function read(p) { return fs.readFileSync(p, 'utf8'); }
function exists(p) { return fs.existsSync(p); }

(async () => {
  // 1) the games list
  const regPath = exists('games.json') ? 'games.json' : path.join(SITE, 'games.json');
  if (exists(regPath)) { await put('ava/index', JSON.parse(read(regPath))); console.log('uploaded ava/index'); }

  // 2) the overview page
  const ov = path.join(SITE, 'index.html');
  if (exists(ov)) { const n = await putHtml('ava/overview', read(ov)); console.log('uploaded ava/overview (' + n + ' part(s))'); }
  else console.warn('no', ov, '- did the site build run?');

  // 3) each game's page
  const gamesDir = path.join(SITE, 'games');
  let count = 0;
  if (exists(gamesDir)) {
    for (const id of fs.readdirSync(gamesDir)) {
      const page = path.join(gamesDir, id, 'index.html');
      if (!/^[0-9A-Za-z_-]{1,40}$/.test(id) || !exists(page)) continue;
      const n = await putHtml('ava/page_' + id, read(page));
      console.log('uploaded ava/page_' + id + ' (' + n + ' part(s))');
      count++;
    }
  }
  console.log('done: ' + count + ' game page(s) uploaded to the backend');
})().catch(e => { console.error(e.message); process.exit(1); });
