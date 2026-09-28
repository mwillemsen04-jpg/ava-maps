// Fetch the full (not reduced) map of a Call of War game: provinces, sea zones and all connections.
// Usage: node scripts/fetch_map.js [<gameId> ...]   (tries the games in order until one opens)
// Credentials come from COW_USERNAME / COW_PASSWORD (GitHub secrets) or a .env file, exactly like fetch.js.
// Everything goes to mapdata/: <mapID>.json when the full map is found, plus probe.txt with what was tried.
try { require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') }); } catch (e) {}
const path = require('path');
const fs = require('fs');
const https = require('https');
const crypto = require('crypto');
const axios = require('axios');
const { CookieJar } = require('tough-cookie');

const USERNAME = process.env.COW_USERNAME, PASSWORD = process.env.COW_PASSWORD;
if (!USERNAME || !PASSWORD) { console.log('Missing COW_USERNAME / COW_PASSWORD'); process.exit(1); }
const GAMES = process.argv.slice(2).length ? process.argv.slice(2) : ['10920696', '10917564', '10922880', '10911706', '10920944'];
const OUT = path.join(__dirname, '..', 'mapdata');
fs.mkdirSync(OUT, { recursive: true });
const probe = [];
const log = (s) => { console.log(s); probe.push(s); };
const saveProbe = () => fs.writeFileSync(path.join(OUT, 'probe.txt'), probe.join('\n') + '\n');

const jar = new CookieJar();
const client = axios.create({
  httpsAgent: new https.Agent({ rejectUnauthorized: false }),
  headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Accept-Language': 'en-US,en;q=0.9' },
  maxContentLength: 200 * 1024 * 1024, maxBodyLength: 200 * 1024 * 1024
});
client.interceptors.request.use(async (c) => { const s = await jar.getCookieString(c.url || 'https://www.callofwar.com'); if (s) c.headers.Cookie = c.headers.Cookie ? `${c.headers.Cookie}; ${s}` : s; return c; });
const keep = async (r) => { const ck = r?.headers?.['set-cookie']; if (ck) for (const c of ck) await jar.setCookie(c, r.config.url || 'https://www.callofwar.com'); };
client.interceptors.response.use(async (r) => { await keep(r); return r; }, async (e) => { if (e.response) await keep(e.response); return Promise.reject(e); });

async function login() {
  const home = await client.get('https://www.callofwar.com/');
  const ref = home.data.match(/(sg_cb_\d+_\d+_[a-f0-9]+)/)?.[1], req = home.data.match(/(sg_req_\d+_\d+_[a-f0-9]+)/)?.[1];
  if (!ref || !req) throw new Error('homepage tokens not found');
  const a = await client.post(`https://www.callofwar.com/index.php?eID=ajax&action=loginPassword&L=0&ref=${ref}&req=${req}&reqID=0&${Date.now()}`,
    new URLSearchParams({ titleID: '510', userName: USERNAME.toLowerCase(), pwd: PASSWORD }),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest' } });
  if (!String(a.data).includes('func_loginbox_form')) throw new Error('login rejected');
  try { await client.post('https://www.callofwar.com/index.php?id=304', new URLSearchParams({ user: USERNAME, pass: PASSWORD, logintype: 'login' }), { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, maxRedirects: 0 }); }
  catch (e) { if (![301, 302, 303].includes(e.response?.status)) throw e; }
  return jar.getCookieString('https://www.callofwar.com');
}

async function get(url, opts = {}) {
  try { const r = await client.get(url, { responseType: 'text', transformResponse: (x) => x, validateStatus: () => true, ...opts }); return { status: r.status, body: r.data, type: r.headers['content-type'] || '' }; }
  catch (e) { return { status: 'ERR ' + e.message, body: '' }; }
}

function isFullMap(txt) {
  // a full map has locations with connections (sea provinces too), a reduced one does not
  return /"(connections|c|neighbours|neighbors|borderProvinces)"\s*:/.test(txt) && /"sp"|seaProvince|"@c"\s*:\s*"sp"/.test(txt);
}

async function tryGame(gameId, cookies) {
  log(`\n=== game ${gameId}`);
  const lobby = await client.get(`https://www.callofwar.com/game.php?gameID=${gameId}&bust=1`, { headers: { Cookie: cookies } });
  const m = String(lobby.data).match(/(clients\/ww2-client-ultimate\/ww2-client-ultimate_live\/index\.html\?[^"'\s<>]+)/);
  if (!m) { log('game page did not open the client'); return null; }
  const clientUrl = `https://www.callofwar.com/${m[1].replace(/&amp;/g, '&')}`;
  const u = new URL(clientUrl);
  const userID = u.searchParams.get('userID'), authHash = u.searchParams.get('uberAuthHash') || u.searchParams.get('authHash'), authTstamp = u.searchParams.get('uberAuthTstamp') || u.searchParams.get('authTstamp');
  log('client params: ' + [...u.searchParams.keys()].join(','));
  for (const [k, v] of u.searchParams) if (/map|static|cdn|url|host|server/i.test(k)) log(`  ${k} = ${v}`);

  // token + game server
  const raw = `gameID=${gameId}&authTstamp=${authTstamp}&authUserID=${userID}&source=browser-desktop`;
  const sig = crypto.createHash('sha1').update(`ingameWw2UltimategetGameToken${raw}${authHash}`).digest('hex');
  const tok = await client.post(`https://www.callofwar.com/index.php?action=getGameToken&eID=api&key=ingameWw2Ultimate&hash=${sig}&outputFormat=json&apiVersion=20141208&L=0&source=browser-desktop`,
    `data=${Buffer.from(raw).toString('base64')}`, { headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest', Origin: 'https://www.callofwar.com', Referer: 'https://www.callofwar.com/', Cookie: cookies } });
  if (tok.data.resultCode !== 0) { log('token failed: ' + tok.data.resultMessage); return null; }
  const tc = tok.data.result.token;
  log('token keys: ' + Object.keys(typeof tc === 'object' ? tc : {}).join(','));
  for (const [k, v] of Object.entries(typeof tc === 'object' ? tc : {})) if (typeof v === 'string' && /map|static|http|cdn/i.test(k + v) && k !== 'auth') log(`  token.${k} = ${v}`);
  const gs = `https://${tc.gs || 'thi-cow-gs-0n40.c.bytro.com'}/`;
  const payload = (extra) => ({ requestID: 1, '@c': 'ultshared.action.UltUpdateGameStateAction', actions: [], lastCallDuration: 150, stateIDs: {}, tstamps: {}, version: '213', client: 'ww2-client-ultimate', siteUserID: +userID, adminLevel: 0, gameID: +gameId, playerID: 0, rights: 'chat', userAuth: typeof tc === 'object' ? tc.auth : tc, tstamp: tc.authTstamp || authTstamp, ...extra });
  const post = (extra) => client.post(gs, payload(extra), { headers: { 'Content-Type': 'text/plain;charset=UTF-8', Origin: 'https://www.callofwar.com', Referer: 'https://www.callofwar.com/' }, validateStatus: () => true });

  // premium state (14) holds the War Bonds price of healing ("Army Reinforcement" offer)
  try {
    const ps = await post({ stateType: 14 });
    const pt = JSON.stringify(ps.data || {});
    fs.writeFileSync(path.join(OUT, 'premium_state.json'), pt);
    log(`premium state 14 -> ${ps.status} ${pt.length} bytes`);
  } catch (e) { log('premium state failed: ' + e.message); }
  // army state (6): which armies this login can see, with their commands (route + arrival times)
  try {
    const as = await post({ stateType: 6 });
    const at = JSON.stringify(as.data || {});
    fs.writeFileSync(path.join(OUT, `army_state_${gameId}.json`), at);
    const armies = as.data?.result?.armies || {};
    const list = Object.values(armies).filter((a) => a && typeof a === 'object');
    const owners = {}; let withCmd = 0;
    for (const a of list) { owners[a.o ?? a.owner ?? a.ownerID ?? '?'] = (owners[a.o ?? a.owner ?? a.ownerID ?? '?'] || 0) + 1; if (a.commands || a.c || a.cmds) withCmd++; }
    log(`army state 6 game ${gameId} -> ${as.status} ${at.length} bytes, ${list.length} armies, ${withCmd} with commands, owners ${JSON.stringify(owners)}`);
    if (list[0]) log('   first army: ' + JSON.stringify(list[0]).slice(0, 1500));
  } catch (e) { log('army state failed: ' + e.message); }
  const st = await post({ stateType: 3 });
  const s3 = st.data?.result?.['@c'] === 'ultshared.UltMapState' ? st.data.result : (st.data?.result?.states?.['3'] || st.data?.result);
  const map = s3?.map || {};
  const mapID = map.mapID || '23114_3';
  log(`state 3: isReduced=${map.isReduced} mapID=${mapID} keys=${Object.keys(map).join(',')}`);
  for (const [k, v] of Object.entries(s3 || {})) if (typeof v === 'string' && /http|map|\.json/i.test(v)) log(`  state3.${k} = ${v}`);

  // look inside the client for where it loads the map from
  const templates = new Set();
  const idx = await get(clientUrl);
  log(`client index: ${idx.status} ${String(idx.body).length} bytes`);
  const base = clientUrl.split('index.html')[0];
  const scripts = [...String(idx.body).matchAll(/<script[^>]+src=["']([^"']+)["']/g)].map((x) => new URL(x[1], base).href);
  const inline = String(idx.body);
  const texts = [['index.html', inline]];
  for (const s of scripts) { const r = await get(s); log(`script ${s} -> ${r.status} ${String(r.body).length} bytes`); if (r.status === 200) texts.push([s, String(r.body)]); }
  // keep the game's own client code (not the libraries) so the heal price rules can be read from it
  const CL = path.join(OUT, 'client');
  fs.mkdirSync(CL, { recursive: true });
  for (const [name, t] of texts) {
    const b = name.split('/').pop().split('?')[0];
    if (name !== 'index.html' && !/^pkg\.|^image-properties/.test(b)) fs.writeFileSync(path.join(CL, b), t);
  }
  for (const [name, t] of texts) {
    const hits = new Set();
    for (const x of t.matchAll(/["'`]([^"'`\s]{0,120}(?:mapjson|map_json|mapdata|\/maps?\/|mapID|mapUrl|mapURL|staticUrl|staticURL|static[0-9]?\.bytro)[^"'`\s]{0,120})["'`]/gi)) hits.add(x[1]);
    for (const x of t.matchAll(/.{0,80}(?:mapjson|mapUrl|mapURL|getMapUrl|loadMap)\b.{0,120}/g)) hits.add(x[0].replace(/\s+/g, ' '));
    if (hits.size) { log(`-- hints in ${name}:`); [...hits].slice(0, 60).forEach((h) => log('   ' + h)); }
    for (const h of hits) { const mm = h.match(/https?:\/\/[^"'`\s]+/); if (mm) templates.add(mm[0]); }
  }

  // healing with War Bonds: collect every piece of client code about healing and its price
  try {
    const out = [];
    for (const [name, t] of texts) {
      const seen = new Set();
      for (const re of [/heal/gi, /repair/gi, /hitpointsRestore|restoreHitpoints|HealArmy|healArmy|healCost|getHealPrice|premiumHeal/g]) {
        let m; let n = 0;
        while ((m = re.exec(t)) && n < 400) {
          n++; const i = m.index; const key = Math.floor(i / 400);
          if (seen.has(key)) continue; seen.add(key);
          out.push(`--- ${name.split('/').pop()} @${i}\n` + t.slice(Math.max(0, i - 500), i + 700).replace(/\s+/g, ' '));
        }
      }
    }
    fs.writeFileSync(path.join(OUT, 'client_heal.txt'), out.join('\n\n'));
    log(`heal code snippets: ${out.length} saved in mapdata/client_heal.txt`);
  } catch (e) { log('heal snippets failed: ' + e.message); }
  // the client builds the map address from mapJsonServer (a client parameter) + /fileadmin/mapjson/live/ + a version file
  const app = texts.find(([n]) => /app\./.test(n));
  if (app) for (const key of ['mapJsonFolder', 'mapjson-bust', 'loadMapBusts', 'getMapJson', 'mapJsonServer']) {
    let i = -1, n = 0;
    while ((i = app[1].indexOf(key, i + 1)) >= 0 && n++ < 4) log(`-- code around ${key}: ` + app[1].slice(Math.max(0, i - 300), i + 500).replace(/\s+/g, ' '));
  }
  const mjs = u.searchParams.get('mapJsonServer') || (typeof tc === 'object' && tc.mapJsonServer) || 'static.supremacy1914.com';
  const folder = `https://${mjs}/fileadmin/mapjson/live/`;
  const bustR = await get(`${folder}mapjson-bust.json`);
  log(`bust file ${folder}mapjson-bust.json -> ${bustR.status} ${String(bustR.body).slice(0, 600)}`);
  let bust = null;
  let bj = {};
  try { bj = JSON.parse(bustR.body); } catch (e) {}
  const mine = Object.keys(bj).filter((k) => k.startsWith(mapID + '@') || k.startsWith(mapID + '.'));
  log('bust entries for this map: ' + JSON.stringify(mine.map((k) => [k, bj[k]])));
  if (app) { const i = app[1].indexOf('async load(e)'); if (i >= 0) log('-- code of load(): ' + app[1].slice(i, i + 1500).replace(/\s+/g, ' ')); }
  const quality = [...mine].sort((x, y) => (/@high/.test(y) ? 1 : 0) - (/@high/.test(x) ? 1 : 0));
  const pre = [];
  for (const k of quality) { const h = bj[k]; pre.push(`${folder}${k}?${h}`, `${folder}${k}?bust=${h}`, `${folder}${k}`, `${folder}${k.replace('.json', '')}.${h}.json`, `${folder}${k.replace('.json', '')}_${h}.json`); }
  // candidate addresses of the full map
  const cands = new Set([
    ...pre,
    `${folder}${mapID}.json`,
    bust != null ? `${folder}${mapID}.json?${bust}` : null,
    bust != null ? `${folder}${mapID}.json?bust=${bust}` : null,
    bust != null ? `${folder}${mapID}_${bust}.json` : null,
    `https://${mjs}/fileadmin/mapjson/${mapID}.json`,
    `https://static1.bytro.com/fileadmin/mapjson/live/${mapID}.json`,
    `https://static2.bytro.com/fileadmin/mapjson/live/${mapID}.json`,
    `https://static1.bytro.com/fileadmin/mapjson/${mapID}.json`,
    `https://static1.bytro.com/fileadmin/mapjson/live/${mapID.split('_')[0]}.json`,
    `https://www.callofwar.com/clients/ww2-client-ultimate/ww2-client-ultimate_live/maps/${mapID}.json`,
    `${gs}map/${mapID}.json`
  ]);
  for (const t of templates) {
    if (/\{|\$|%s/.test(t) || /mapjson|maps?\//i.test(t)) cands.add(t.replace(/\$\{[^}]+\}|\{[^}]+\}|%s/g, mapID).replace(/\/$/, '/' + mapID + '.json'));
  }
  for (const c of cands) {
    if (!c) continue;
    const r = await get(c);
    const full = r.status === 200 && isFullMap(String(r.body));
    log(`try ${c} -> ${r.status} ${String(r.body).length} bytes${full ? '  FULL MAP' : ''}`);
    if (r.status === 200 && String(r.body).length > 100000) {
      const f = path.join(OUT, `${mapID}${full ? '' : '_candidate'}.json`);
      fs.writeFileSync(f, r.body); log(`   saved ${path.basename(f)}`);
      if (full) return mapID;
    }
  }
  // the game server may also give the full map when asked for it without the reduced flag
  for (const extra of [{ stateType: 3, option: 'full' }, { stateType: 3, option: 1 }, { stateType: 3, reduced: false }]) {
    const r = await post(extra); const t = JSON.stringify(r.data || {});
    const full = isFullMap(t);
    log(`game server ${JSON.stringify(extra)} -> ${r.status} ${t.length} bytes${full ? '  FULL MAP' : ''}`);
    if (full) { fs.writeFileSync(path.join(OUT, `${mapID}_state3.json`), t); return mapID; }
  }
  return null;
}

(async () => {
  let cookies;
  try { cookies = await login(); log('login ok'); } catch (e) { log('login failed: ' + e.message); saveProbe(); process.exit(1); }
  let found = null;
  for (const g of GAMES) {
    try { found = await tryGame(g, cookies); } catch (e) { log(`game ${g}: ${e.message}`); }
    if (found) break;
  }
  log(found ? `\nRESULT: full map ${found} saved in mapdata/` : '\nRESULT: full map not found yet, see the hints above');
  saveProbe();
})();
