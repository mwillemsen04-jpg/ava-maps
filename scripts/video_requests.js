// Make the videos asked for in manage mode: every requests/video-<id>.json, oldest first.
// Each one is recorded with make_video.js, uploaded to the "videos" download page (Releases) and reported in
// videos_log.json (the site shows the download link from there). Needs GH_TOKEN and GITHUB_REPOSITORY.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const RQ = path.join(ROOT, 'requests');
const LOG = path.join(ROOT, 'videos_log.json');
const repo = process.env.GITHUB_REPOSITORY || '';
const log = fs.existsSync(LOG) ? JSON.parse(fs.readFileSync(LOG, 'utf8')) : {};
const files = fs.existsSync(RQ) ? fs.readdirSync(RQ).filter(f => /^video-.*\.json$/.test(f)).sort() : [];
if (!files.length) console.log('no video requests');

for (const f of files) {
  const full = path.join(RQ, f);
  let r = {};
  try { r = JSON.parse(fs.readFileSync(full, 'utf8')); } catch (e) {}
  const id = r.id || f.replace(/^video-|\.json$/g, '');
  console.log(`\n=== video request ${id} from ${r.by || '?'}: ${r.title}`);
  const out = path.join(ROOT, `.video_out_${id}`);
  try { fs.unlinkSync(path.join(ROOT, 'video_error.txt')); } catch (e) {}
  const run = spawnSync('node', ['scripts/make_video.js'], {
    cwd: ROOT, stdio: 'inherit',
    env: { ...process.env, TITLE: String(r.title || ''), BODY: String(r.body || ''), VIDEO_ID: id, GITHUB_OUTPUT: out }
  });
  const res = { title: r.title, by: r.by || '', at: new Date().toISOString() };
  const o = {};
  try { for (const line of fs.readFileSync(out, 'utf8').split('\n')) { const i = line.indexOf('='); if (i > 0) o[line.slice(0, i)] = line.slice(i + 1); } } catch (e) {}
  try { fs.unlinkSync(out); } catch (e) {}
  if (run.status === 0 && o.file) {
    const up = spawnSync('gh', ['release', 'upload', 'videos', o.file, '--clobber'], { cwd: ROOT, stdio: 'inherit' });
    if (up.status === 0) Object.assign(res, { ok: true, url: `https://github.com/${repo}/releases/download/videos/${o.name}`, length: o.length, mb: o.mb });
    else Object.assign(res, { ok: false, msg: 'the video was made but could not be put on the download page' });
    try { fs.unlinkSync(path.join(ROOT, o.file)); } catch (e) {}
  } else {
    let why = 'something went wrong';
    try { why = fs.readFileSync(path.join(ROOT, 'video_error.txt'), 'utf8').trim(); } catch (e) {}
    Object.assign(res, { ok: false, msg: why });
  }
  console.log(res.ok ? `✅ ${res.url}` : `❌ ${res.msg}`);
  log[id] = res;
  fs.unlinkSync(full);
}
const keep = Object.entries(log).sort((a, b) => String(a[1].at).localeCompare(String(b[1].at))).slice(-60);
fs.writeFileSync(LOG, JSON.stringify(Object.fromEntries(keep), null, 1));
