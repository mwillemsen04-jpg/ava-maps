// TEST ONLY: can older newspaper days be requested? Writes probe/news_probe.json.
// Usage: node scripts/fetch.js <gameId> [<gameId> ...]
// Credentials come from the environment (COW_USERNAME, COW_PASSWORD) or a .env file next to package.json.
// Each game's state is written to games/<gameId>/game_data.json.
try { require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') }); } catch (e) {}
const path = require('path');
const axios = require('axios');
const { CookieJar } = require('tough-cookie');
const fs = require('fs');
const https = require('https');
const crypto = require('crypto');

function writeToFileAndConsole(output) {
  console.log(output);
}

const USERNAME = process.env.COW_USERNAME;
const PASSWORD = process.env.COW_PASSWORD;
const GAME_IDS = process.argv.slice(2).length ? process.argv.slice(2) : ['10911706', '10917564'];

if (!USERNAME || !PASSWORD) {
  writeToFileAndConsole("⚠️ [CRITICAL] Missing credentials: set COW_USERNAME and COW_PASSWORD");
  process.exit(1);
}

function logAction(name, details = {}) {
  const msg = `\n[ACTION] ${name}${Object.keys(details).length ? '\n' + JSON.stringify(details, null, 2) : ''}`;
  writeToFileAndConsole(msg);
}

const httpsAgent = new https.Agent({
  ciphers: 'TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384:HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA',
  honorCipherOrder: true,
  rejectUnauthorized: false
});

const jar = new CookieJar();
const client = axios.create({
  httpsAgent,
  headers: {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
  }
});

client.interceptors.request.use(async (config) => {
  const cookieString = await jar.getCookieString(config.url || 'https://www.callofwar.com');
  if (cookieString) {
    config.headers.Cookie = config.headers.Cookie ? `${config.headers.Cookie}; ${cookieString}` : cookieString;
  }
  return config;
});

client.interceptors.response.use(
  async (res) => {
    const cookies = res.headers['set-cookie'];
    if (cookies) {
      const url = res.config.url || 'https://www.callofwar.com';
      for (const c of cookies) await jar.setCookie(c, url);
    }
    return res;
  },
  async (err) => {
    if (err.response?.headers['set-cookie']) {
      const url = err.response.config.url || 'https://www.callofwar.com';
      for (const c of err.response.headers['set-cookie']) await jar.setCookie(c, url);
    }
    return Promise.reject(err);
  }
);

/**
 * Traverses State 1 to find the exact player slot associated with the authenticated userID
 */
function detectPlayerFromState(responseJson, targetUserID) {
  const states = responseJson?.result?.states || {};
  const playerState = states['1'];
  if (!playerState || !playerState.players) return null;

  for (const [slotKey, p] of Object.entries(playerState.players)) {
    if (String(p.siteUserID) === String(targetUserID)) {
      return {
        slotID: parseInt(slotKey, 10),
        nationName: p.nationName || p.title || p.name || `Nation ${slotKey}`
      };
    }
  }
  return null;
}

async function login() {
    // 1. Tokens
    logAction("1. Retrieving CSRF Tokens");
    const home = await client.get('https://www.callofwar.com/');
    const ref = home.data.match(/(sg_cb_\d+_\d+_[a-f0-9]+)/)?.[1];
    const req = home.data.match(/(sg_req_\d+_\d+_[a-f0-9]+)/)?.[1];
    if (!ref || !req) throw new Error("Could not find homepage tokens.");

    // 2. AJAX Auth
    logAction("2. Validating Credentials via AJAX");
    const ajaxUrl = `https://www.callofwar.com/index.php?eID=ajax&action=loginPassword&L=0&ref=${ref}&req=${req}&reqID=0&${Date.now()}`;
    const ajaxRes = await client.post(ajaxUrl, new URLSearchParams({ titleID: '510', userName: USERNAME.toLowerCase(), pwd: PASSWORD }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest' }
    });
    if (!ajaxRes.data.includes('func_loginbox_form')) throw new Error("AJAX Login rejected.");

    // 3. Login POST
    logAction("3. Session Verification");
    try {
      await client.post('https://www.callofwar.com/index.php?id=304', new URLSearchParams({ user: USERNAME, pass: PASSWORD, logintype: 'login' }), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        maxRedirects: 0
      });
    } catch (e) {
      if (![301, 302, 303].includes(e.response?.status)) throw e;
    }

    return await jar.getCookieString('https://www.callofwar.com');
}


async function connect(TARGET_GAME_ID, activeCookies) {
    const lobby = await client.get(`https://www.callofwar.com/game.php?gameID=${TARGET_GAME_ID}&bust=1`, { headers: { Cookie: activeCookies } });
    const m = lobby.data.match(/(clients\/ww2-client-ultimate\/ww2-client-ultimate_live\/index\.html\?[^"'\s<>]+)/);
    if (!m) throw new Error("Client URL missing from lobby.");
    const u = new URL(`https://www.callofwar.com/${m[1].replace(/&amp;/g, '&')}`);
    const userID = u.searchParams.get('userID');
    const authHash = u.searchParams.get('uberAuthHash') || u.searchParams.get('authHash');
    const authTstamp = u.searchParams.get('uberAuthTstamp') || u.searchParams.get('authTstamp');
    const rawData = `gameID=${TARGET_GAME_ID}&authTstamp=${authTstamp}&authUserID=${userID}&source=browser-desktop`;
    const sig = crypto.createHash('sha1').update(`ingameWw2UltimategetGameToken${rawData}${authHash}`).digest('hex');
    const tokenRes = await client.post(`https://www.callofwar.com/index.php?action=getGameToken&eID=api&key=ingameWw2Ultimate&hash=${sig}&outputFormat=json&apiVersion=20141208&L=0&source=browser-desktop`,
      `data=${Buffer.from(rawData).toString('base64')}`, { headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://www.callofwar.com', 'Referer': 'https://www.callofwar.com/', 'Cookie': activeCookies } });
    if (tokenRes.data.resultCode !== 0) throw new Error(`Token API failed: ${tokenRes.data.resultMessage}`);
    const t = tokenRes.data.result.token;
    const url = `https://${t.gs || 'thi-cow-gs-0n40.c.bytro.com'}/`;
    const base = { "@c": "ultshared.action.UltUpdateGameStateAction", "actions": [], "lastCallDuration": 150, "version": "213", "client": "ww2-client-ultimate",
      "siteUserID": parseInt(userID, 10), "adminLevel": 0, "gameID": parseInt(TARGET_GAME_ID, 10), "rights": "chat",
      "userAuth": typeof t === 'object' ? t.auth : t, "tstamp": t.authTstamp || authTstamp };
    let rid = 1;
    const post = async (extra) => (await client.post(url, { requestID: rid++, ...base, ...extra }, { headers: { 'Content-Type': 'text/plain;charset=UTF-8', 'Origin': 'https://www.callofwar.com', 'Referer': 'https://www.callofwar.com/' } })).data;
    const first = await post({ playerID: 0, stateIDs: {}, tstamps: {} });
    let slot = 0;
    for (const [k, p] of Object.entries(first?.result?.states?.['1']?.players || {})) if (String(p.siteUserID) === String(userID)) slot = parseInt(k, 10);
    const st = first?.result?.states || {};
    return { post, slot, dayOfGame: st['12']?.dayOfGame ?? st['2']?.day, stateKeys: Object.keys(st) };
}

function summarize(data) {
  const res = data?.result;
  let news = null;
  if (res?.['@c'] && String(res['@c']).includes('Newspaper')) news = res;
  else if (res?.states?.['2']) news = res.states['2'];
  else if (res?.states) for (const s of Object.values(res.states)) if (s && String(s['@c'] || '').includes('Newspaper')) news = s;
  const times = []; let count = 0; const samples = [];
  const walk = (o) => {
    if (!o || typeof o !== 'object') return;
    if (Array.isArray(o)) return o.forEach(walk);
    const c = String(o['@c'] || '');
    if (c.includes('Article') || c.includes('UltArticle')) { count++; const tm = o.timeStamp ?? o.time ?? o.tstamp; if (tm) times.push(Number(tm)); if (samples.length < 2) samples.push(JSON.stringify(o).slice(0, 400)); }
    Object.values(o).forEach(walk);
  };
  walk(news);
  times.sort((a, b) => a - b);
  const iso = (x) => x ? new Date(x > 1e12 ? x : x * 1000).toISOString() : null;
  return { resultClass: res?.['@c'] || null, resultKeys: res ? Object.keys(res).slice(0, 20) : null, error: data?.result?.message || data?.error || null,
    newsClass: news?.['@c'] || null, newsDay: news?.day ?? null, newsKeys: news ? Object.keys(news).slice(0, 20) : null,
    articles: count, first: iso(times[0]), last: iso(times[times.length - 1]), samples };
}

(async () => {
  const out = { at: new Date().toISOString(), games: {} };
  let cookies;
  try { cookies = await login(); } catch (e) { out.login = e.message; }
  for (const id of GAME_IDS) {
    const g = out.games[id] = {};
    try {
      const c = await connect(id, cookies);
      g.slot = c.slot; g.dayOfGame = c.dayOfGame; g.stateKeys = c.stateKeys;
      const common = { playerID: c.slot, stateIDs: {}, tstamps: {} };
      const variants = {
        today: () => ({ ...common, stateType: 2 }),
        option: (d) => ({ ...common, stateType: 2, option: d }),
        optionFull: (d) => ({ ...common, stateType: 2, stateID: "0", addStateIDsOnSent: true, option: d }),
        stateID: (d) => ({ ...common, stateType: 2, stateID: String(d) }),
        day: (d) => ({ ...common, stateType: 2, day: d }),
      };
      g.results = {};
      for (const [name, fn] of Object.entries(variants)) {
        for (const d of (name === 'today' ? [null] : [2, 5])) {
          const key = name + (d == null ? '' : '_day' + d);
          try {
            const data = await c.post(fn(d));
            g.results[key] = summarize(data);
            if (key === 'option_day2') { fs.mkdirSync(path.join(__dirname, '..', 'probe'), { recursive: true }); fs.writeFileSync(path.join(__dirname, '..', 'probe', `raw_${id}_option_day2.json`), JSON.stringify(data).slice(0, 300000)); }
          } catch (e) { g.results[key] = { error: e.message }; }
        }
      }
    } catch (e) { g.error = e.message; }
  }
  fs.mkdirSync(path.join(__dirname, '..', 'probe'), { recursive: true });
  fs.writeFileSync(path.join(__dirname, '..', 'probe', 'news_probe.json'), JSON.stringify(out, null, 1));
  console.log(JSON.stringify(out, null, 1).slice(0, 20000));
})();
