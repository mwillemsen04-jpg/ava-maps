// Fetch the current state of one or more Call of War games.
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
const GAME_IDS = process.argv.slice(2).length ? process.argv.slice(2) : (process.env.COW_GAME_ID ? [process.env.COW_GAME_ID] : []);
if (!GAME_IDS.length) { console.log('Usage: node scripts/fetch.js <gameId> [<gameId> ...]'); process.exit(1); }

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

async function fetchGame(TARGET_GAME_ID, activeCookies) {
    // 4. Lobby Fetch & Automatic UserID Extraction
    logAction("4. Fetching Lobby to Extract User Identity & Hashes", { gameID: TARGET_GAME_ID });
    const lobby = await client.get(`https://www.callofwar.com/game.php?gameID=${TARGET_GAME_ID}&bust=1`, {
      headers: { Cookie: activeCookies }
    });

    const clientUrlMatch = lobby.data.match(/(clients\/ww2-client-ultimate\/ww2-client-ultimate_live\/index\.html\?[^"'\s<>]+)/);
    if (!clientUrlMatch) {
      // the game page did not open the game (ended long ago and closed, wrong code, or no access):
      // report what the page says instead, so the reason shows on the overview page
      const html = String(lobby.data || '');
      const title = (html.match(/<title>([^<]*)/i) || [])[1] || '';
      const text = html.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, ' ').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
      const said = (text.match(/[^.!?]*\b(game|match|spiel|round)\b[^.!?]*[.!?]/gi) || []).slice(0, 3).join(' ').trim().slice(0, 300);
      const where = lobby.request?.res?.responseUrl || '';
      throw new Error(`The game page did not open the game${where && !where.includes('game.php') ? ' (sent on to ' + where + ')' : ''}${title ? ' · page: ' + title.trim() : ''}${said ? ' · ' + said : ''}`);
    }

    const parsedUrl = new URL(`https://www.callofwar.com/${clientUrlMatch[1].replace(/&amp;/g, '&')}`);
    
    // Extracted automatically from the session
    const autoUserID = parsedUrl.searchParams.get('userID');
    const authHash = parsedUrl.searchParams.get('uberAuthHash') || parsedUrl.searchParams.get('authHash');
    const authTstamp = parsedUrl.searchParams.get('uberAuthTstamp') || parsedUrl.searchParams.get('authTstamp');

    if (!autoUserID) throw new Error("Failed to auto-extract userID from lobby parameters.");
    logAction("Identity Automatically Extracted", { autoUserID });

    // 5. Game Server Token
    logAction("5. Requesting Dedicated Game Server Token");
    const rawData = `gameID=${TARGET_GAME_ID}&authTstamp=${authTstamp}&authUserID=${autoUserID}&source=browser-desktop`;
    const b64Data = Buffer.from(rawData).toString('base64');
    const apiSignature = crypto.createHash('sha1').update(`ingameWw2UltimategetGameToken${rawData}${authHash}`).digest('hex');

    const tokenUrl = `https://www.callofwar.com/index.php?action=getGameToken&eID=api&key=ingameWw2Ultimate&hash=${apiSignature}&outputFormat=json&apiVersion=20141208&L=0&source=browser-desktop`;
    const tokenRes = await client.post(tokenUrl, `data=${b64Data}`, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://www.callofwar.com',
        'Referer': 'https://www.callofwar.com/',
        'Cookie': activeCookies
      }
    });

    if (tokenRes.data.resultCode !== 0) {
      throw new Error(`Token API failed: ${tokenRes.data.resultMessage}`);
    }

    const tokenContainer = tokenRes.data.result.token;
    const gameServerSubdomain = tokenContainer.gs || 'thi-cow-gs-0n40.c.bytro.com';
    const syncedTstamp = tokenContainer.authTstamp || authTstamp;
    const authString = typeof tokenContainer === 'object' ? tokenContainer.auth : tokenContainer;

    // 6. Discovery Query & Dynamic Nation Resolution
    logAction("6. Discovery Handshake Query");
    const gameServerUrl = `https://${gameServerSubdomain}/`;

    const makePayload = (slot) => ({
      "requestID": 1,
      "@c": "ultshared.action.UltUpdateGameStateAction",
      "actions": [],
      "lastCallDuration": 150,
      "stateIDs": {},
      "tstamps": {},
      "version": "213",
      "client": "ww2-client-ultimate",
      "siteUserID": parseInt(autoUserID, 10),
      "adminLevel": 0,
      "gameID": parseInt(TARGET_GAME_ID, 10),
      "playerID": parseInt(slot, 10),
      "rights": "chat",
      "userAuth": authString,
      "tstamp": syncedTstamp
    });

    // Initial query to fetch State 1
    let stateResponse = await client.post(gameServerUrl, makePayload(0), {
      headers: {
        'Content-Type': 'text/plain;charset=UTF-8',
        'Origin': 'https://www.callofwar.com',
        'Referer': 'https://www.callofwar.com/'
      }
    });

    // Auto-detect player slot by checking State 1 for autoUserID
    const detected = detectPlayerFromState(stateResponse.data, autoUserID);

    if (detected) {
      writeToFileAndConsole(`🎯 [RESOLVED IDENTITY] User ID: ${autoUserID} -> Nation: ${detected.nationName} (Slot ID: ${detected.slotID})`);
      
      // Re-query with the discovered player slot to lift Fog of War on State 6 (Armies)
      logAction("Refreshing Map State to Lift Fog of War", { targetSlot: detected.slotID });
      stateResponse = await client.post(gameServerUrl, makePayload(detected.slotID), {
        headers: {
          'Content-Type': 'text/plain;charset=UTF-8',
          'Origin': 'https://www.callofwar.com',
          'Referer': 'https://www.callofwar.com/'
        }
      });
    } else {
      writeToFileAndConsole(`⚠️ User ID [${autoUserID}] was not found among assigned nations in this match (spectator/lobby).`);
    }

    // Save final state file
    if (!stateResponse.data?.result?.states) throw new Error('Game server returned no game state.');
    const dir = path.join(__dirname, '..', 'games', String(TARGET_GAME_ID));
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, 'game_data.json'), JSON.stringify(stateResponse.data));
    writeToFileAndConsole(`🎉 [SUCCESS] game ${TARGET_GAME_ID} saved to games/${TARGET_GAME_ID}/game_data.json`);

    // 7. Newspapers of earlier days. The game's current newspaper only covers today, but the server
    // still gives the full newspaper of any earlier day (option = day number). Every finished day that
    // import_news.py has not stored yet (from day 2 on; day 1 is not shown) (gd_events.json -> news_days) is fetched once, so a game added
    // late (or already finished) gets its whole history, and a missed round never leaves a gap.
    try {
      const today = stateResponse.data.result.states['2']?.day;
      let done = [];
      try { done = JSON.parse(fs.readFileSync(path.join(dir, 'gd_events.json'), 'utf8')).news_days || []; } catch (e) {}
      const want = [];
      for (let d = 2; today && d < today; d++) if (!done.includes(d)) want.push(d);
      if (want.length) {
        logAction("7. Fetching newspapers of earlier days", { days: want });
        const nd = path.join(dir, 'news_days');
        fs.mkdirSync(nd, { recursive: true });
        const slot = detected ? detected.slotID : 0;
        for (const d of want) {
          const r = await client.post(gameServerUrl, { ...makePayload(slot), stateType: 2, option: d }, {
            headers: { 'Content-Type': 'text/plain;charset=UTF-8', 'Origin': 'https://www.callofwar.com', 'Referer': 'https://www.callofwar.com/' }
          });
          const res = r.data?.result || {};
          const news = String(res['@c'] || '').includes('Newspaper') ? res : res.states?.['2'];
          if (!news || news.day !== d) { writeToFileAndConsole(`⚠️ newspaper of day ${d} not returned`); continue; }
          fs.writeFileSync(path.join(nd, `${d}.json`), JSON.stringify({ day: d, newsArticles: news.newsArticles || [] }));
          writeToFileAndConsole(`📰 day ${d}: ${(news.newsArticles || []).length} articles`);
        }
      }
    } catch (err) {
      writeToFileAndConsole(`⚠️ earlier newspapers skipped: ${err.message}`);
    }
}

(async () => {
  let failed = 0, cookies;
  try { cookies = await login(); }
  catch (err) {
    writeToFileAndConsole(`❌ [ERROR] login: ${err.message}`);
    for (const id of GAME_IDS) { try { const f = path.join(__dirname, '..', 'games', String(id), 'fetch_error.txt'); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, 'Login to Call of War failed: ' + err.message); } catch (e) {} }
    process.exit(1);
  }
  // the last error per game is kept in games/<id>/fetch_error.txt (removed again after a good fetch);
  // run.py shows it on the overview page
  const errFile = (id) => path.join(__dirname, '..', 'games', String(id), 'fetch_error.txt');
  for (const id of GAME_IDS) {
    try { await fetchGame(id, cookies); try { fs.unlinkSync(errFile(id)); } catch (e) {} }
    catch (err) {
      failed++; writeToFileAndConsole(`❌ [ERROR] game ${id}: ${err.message}`);
      try { fs.mkdirSync(path.dirname(errFile(id)), { recursive: true }); fs.writeFileSync(errFile(id), String(err.message).slice(0, 500)); } catch (e) {}
    }
  }
  process.exit(failed === GAME_IDS.length ? 1 : 0);
})();