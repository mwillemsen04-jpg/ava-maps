// Record a video of a map, frame by frame, from a "Make video <game>" request (the 🎥 Video button).
// Usage (GitHub): TITLE="Make video 10917564" BODY="from day: 4\nto day: 6\n..." node scripts/make_video.js
// Local test:     PAGE_URL=file:///.../site/games/10917564/index.html node scripts/make_video.js
// Needs: playwright-core, Google Chrome (or CHROME_PATH), ffmpeg. Writes videos/<name>.mp4 and, on GitHub,
// the outputs file= and name= . On failure the reason is written to video_error.txt.
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright-core');

const FPS = 25;
const MAX_SECONDS = 15 * 60;   // longest video: 15 minutes
const SIZES = { '1920x1080': [1920, 1080], '1280x720': [1280, 720], '1080x1080': [1080, 1080] };
const SPEEDS = [15, 30, 60, 120, 240];   // game minutes per second of video
const SETTINGS = ['lab', 'ecaps', 'loss', 'airep', 'allrep', 'paths'];

function fail(msg) {
  fs.writeFileSync('video_error.txt', msg);
  console.error('❌ ' + msg);
  process.exit(1);
}

// ---- read the request ----
const title = process.env.TITLE || '';
const gid = (title.match(/Make video\s+(\d{5,12})/i) || [])[1];
if (!gid) fail('The request title must be "Make video <game code>".');
const opt = {};
for (const line of String(process.env.BODY || '').split(/\r?\n/)) {
  const m = line.match(/^\s*([a-z ]+?)\s*:\s*(.*?)\s*$/i);
  if (m) opt[m[1].toLowerCase()] = m[2];
}
const from = parseInt(opt['from day'], 10), to = parseInt(opt['to day'], 10);
if (!(from >= 1 && from <= 400) || !(to >= from && to <= 400)) fail('Choose the days again: "from day" and "to day" are missing or wrong.');
const speed = SPEEDS.includes(+opt.speed) ? +opt.speed : 60;
const [W, H] = SIZES[opt.size] || SIZES['1920x1080'];
let view = 'europe';
if (opt.view && opt.view !== 'europe') {
  const v = opt.view.split(',').map(Number);
  if (v.length === 3 && v.every(Number.isFinite) && v[2] > 50) view = v;
}
const set = String(opt.settings || '').split(',').map(s => s.trim()).filter(s => SETTINGS.includes(s));
const trail = Math.max(0, Math.min(72, parseFloat(opt.window) || 0));
const who = String(opt.country || 'all').slice(0, 60);

const repo = process.env.GITHUB_REPOSITORY || '';
const [owner, name] = repo.split('/');
const pageUrl = process.env.PAGE_URL || (owner && name ? `https://${owner.toLowerCase()}.github.io/${name}/games/${gid}/index.html` : '');
if (!pageUrl) fail('Unknown site address.');

(async () => {
  const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const hash = '#video=' + encodeURIComponent(JSON.stringify({ from, to, set, trail, who, view }));
  const res = await page.goto(pageUrl + hash, { waitUntil: 'load', timeout: 120000 });
  if (res && res.status && res.status() >= 400) fail(`The map of game ${gid} was not found on the site (${res.status()}).`);
  await page.waitForTimeout(1500);
  if (!(await page.evaluate(() => typeof window.__frame === 'function'))) {
    fail(`The map of game ${gid} does not have the video function yet. It gets it at its next update; try again after that.`);
  }
  const range = await page.evaluate(() => window.__vidReady);
  if (!range || !(range.to > range.from)) fail(`There is nothing to show between day ${from} and day ${to}.`);
  await page.evaluate(() => document.fonts && document.fonts.ready);

  const step = speed / FPS;   // game minutes per frame
  const moving = Math.ceil((range.to - range.from) / step) + 1;
  const hold0 = FPS, hold1 = 2 * FPS;   // 1 s still at the start, 2 s at the end
  const total = hold0 + moving + hold1;
  if (total / FPS > MAX_SECONDS) fail(`That video would be ${Math.round(total / FPS / 60)} minutes long; the maximum is ${MAX_SECONDS / 60}. Choose fewer days or a higher speed.`);
  console.log(`🎥 game ${gid}: day ${from}–${to}, ${speed} min/s, ${W}x${H}, ${total} frames (${(total / FPS).toFixed(1)} s)`);

  fs.mkdirSync('videos', { recursive: true });
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace('T', '-').slice(0, 13);
  const file = path.join('videos', `game-${gid}_day${from}-${to}_${stamp}.mp4`);
  const ff = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', file], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((ok, bad) => { ff.on('close', c => c === 0 ? ok() : bad(new Error('ffmpeg exit ' + c))); ff.on('error', bad); });
  const put = buf => new Promise(ok => { if (ff.stdin.write(buf)) ok(); else ff.stdin.once('drain', ok); });
  const shot = () => page.screenshot({ type: 'jpeg', quality: 90 });

  const t0 = Date.now();
  await page.evaluate(t => window.__frame(t), range.from);
  let img = await shot();
  for (let i = 0; i < hold0; i++) await put(img);
  for (let i = 0; i < moving; i++) {
    await page.evaluate(t => window.__frame(t), Math.min(range.to, range.from + i * step));
    img = await shot();
    await put(img);
    if (i % 250 === 0) console.log(`  frame ${i}/${moving} · ${((Date.now() - t0) / 1000).toFixed(0)} s`);
  }
  for (let i = 0; i < hold1; i++) await put(img);
  ff.stdin.end();
  await done;
  await browser.close();
  if (errors.length) console.log('page errors:', errors.slice(0, 5));
  const mb = (fs.statSync(file).size / 1e6).toFixed(1);
  console.log(`✅ ${file} (${mb} MB) in ${((Date.now() - t0) / 1000).toFixed(0)} s`);
  if (process.env.GITHUB_OUTPUT) {
    fs.appendFileSync(process.env.GITHUB_OUTPUT, `file=${file}\nname=${path.basename(file)}\nlength=${Math.round(total / FPS)}\nmb=${mb}\n`);
  }
})().catch(e => fail('Recording failed: ' + e.message));
