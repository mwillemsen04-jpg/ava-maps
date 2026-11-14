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

const BASE = (process.env.BACKEND_URL || 'https://af-farm-backend.onrender.com').replace(/\/+$/, '');
const PW = process.env.CLAN_PASSWORD || '';
const SITE = process.env.SITE || 'site';
const CHUNK = 700000; // characters per database document (stays under the 1 MB limit)

if (!PW) { console.error('Set the CLAN_PASSWORD secret'); process.exit(1); }

const sleep = ms => new Promise(r => setTimeout(r, ms));

// Wake the free backend before uploading, so the first request does not fail
// on a cold start (it can take ~50s to spin up).
async function wake() {
  for (let i = 0; i < 20; i++) {
    try { const r = await fetch(BASE + '/healthz'); if (r.ok) { console.log('backend awake'); return; } } catch (e) {}
    await sleep(4000);
  }
  console.warn('backend did not respond to /healthz; trying anyway');
}

async function put(name, obj) {
  let last;
  for (let i = 0; i < 4; i++) {
    try {
      const r = await fetch(BASE + '/api/doc/' + name, {
        method: 'PUT',
        headers: { 'Authorization': 'Bearer ' + PW, 'Content-Type': 'application/json' },
        body: JSON.stringify(obj)
      });
      if (r.status === 401) throw new Error('PUT ' + name + ' -> 401 (the CLAN_PASSWORD secret does not match the one on Render)');
      if (!r.ok) throw new Error('PUT ' + name + ' -> ' + r.status);
      return;
    } catch (e) { last = e; await sleep(2000); }
  }
  throw last;
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
  await wake();
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
