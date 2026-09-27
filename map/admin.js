// Manage mode (admin) for the overview page and the map pages.
// Whoever has a key (a GitHub token with "Contents: Read and write" on this repository) pastes it once under
// the ⚙️ button; it is kept only in this browser. With a key every button (add, stop, delete, rename, folders,
// update interval, video) acts straight away: the page writes a small request file into requests/ and GitHub
// handles it within a few minutes. Without a key the management buttons are hidden and the site is view-only.
// Needs on the page: window.AVA = {repo, root}  (root: '' on the overview, '../../' on a map page)
(function () {
  const A = window.AVA || {}, REPO = A.repo || '', ROOT = A.root || '';
  const KEY = 'avaAdmin';
  const get = () => { try { return JSON.parse(localStorage.getItem(KEY) || 'null') } catch (e) { return null } };
  const put = v => { try { v ? localStorage.setItem(KEY, JSON.stringify(v)) : localStorage.removeItem(KEY) } catch (e) {} };
  const PKEY = 'avaPending';
  const pending = () => { try { return JSON.parse(localStorage.getItem(PKEY) || '[]') } catch (e) { return [] } };
  const setPending = v => { try { localStorage.setItem(PKEY, JSON.stringify(v.slice(-20))) } catch (e) {} };
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const on = () => !!(get() && REPO);

  // ---- styles, button, dialog, toasts ----
  const css = document.createElement('style');
  css.textContent = `
  body:not(.ava-admin) .adm{display:none!important}
  #avaGear{position:fixed;left:14px;bottom:14px;z-index:60;width:40px;height:40px;min-height:0;padding:0;border-radius:50%;border:1px solid #334155;background:#0d1117;color:#94a3b8;font-size:18px;cursor:pointer;opacity:.75;display:flex;align-items:center;justify-content:center}
  #avaGear:hover{opacity:1;border-color:#b48c3c}
  body.ava-admin #avaGear{border-color:#b48c3c;color:#b48c3c;opacity:1}
  #avaDlg,#avaAsk{background:#0d1117;color:#e2e8f0;border:1px solid #1e293b;border-radius:14px;padding:24px;max-width:460px;width:calc(100% - 32px);margin:auto;font-family:'Rajdhani',system-ui,sans-serif}
  #avaDlg::backdrop,#avaAsk::backdrop{background:rgba(0,0,0,.7)}
  #avaDlg h3,#avaAsk h3{font-size:20px;letter-spacing:1px;margin:0 0 10px}
  #avaDlg p,#avaAsk p{color:#94a3b8;font-size:14px;line-height:1.5;margin:0 0 14px}
  #avaDlg label,#avaAsk label{display:block;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#b48c3c;margin:0 0 6px}
  #avaDlg input,#avaAsk input{width:100%;box-sizing:border-box;background:#1a1f2e;border:1px solid #333;border-radius:6px;color:#e2e8f0;font-size:15px;padding:10px 12px;margin:0 0 14px;font-family:inherit}
  #avaDlg .row,#avaAsk .row{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}
  #avaDlg button,#avaAsk button{min-height:38px;padding:8px 16px;border-radius:6px;border:1px solid #334155;background:#1a2330;color:#e2e8f0;font:700 14px 'Rajdhani',system-ui,sans-serif;cursor:pointer}
  #avaDlg button.go,#avaAsk button.go{background:#b48c3c;border-color:#b48c3c;color:#0a0c10}
  #avaDlg .msg{font-size:13px;margin:-6px 0 12px;color:#f87171}
  #avaDlg .ok{color:#4ade80}
  #avaDlg ol{color:#94a3b8;font-size:13px;line-height:1.5;margin:0 0 14px;padding-left:18px}
  #avaToasts{position:fixed;right:14px;bottom:14px;z-index:70;display:flex;flex-direction:column;gap:8px;max-width:min(380px,calc(100% - 28px))}
  .avaT{background:#0d1117;border:1px solid #334155;border-left:3px solid #b48c3c;border-radius:8px;padding:10px 12px;color:#e2e8f0;font:600 14px 'Rajdhani',system-ui,sans-serif;box-shadow:0 6px 20px rgba(0,0,0,.4);display:flex;gap:10px;align-items:flex-start}
  .avaT.ok{border-left-color:#22c55e}.avaT.bad{border-left-color:#ef4444}
  .avaT span{flex:1}.avaT a{color:#60a5fa}
  .avaT button{background:none;border:0;color:#64748b;cursor:pointer;font-size:16px;min-height:0;padding:0}`;
  document.head.appendChild(css);
  const gear = document.createElement('button');
  gear.id = 'avaGear'; gear.type = 'button'; gear.title = 'Manage'; gear.setAttribute('aria-label', 'Manage'); gear.innerHTML = '&#9881;&#65039;';
  const toasts = document.createElement('div'); toasts.id = 'avaToasts'; toasts.setAttribute('aria-live', 'polite');
  const dlg = document.createElement('dialog'); dlg.id = 'avaDlg';
  const ask = document.createElement('dialog'); ask.id = 'avaAsk';
  document.body.append(gear, toasts, dlg, ask);

  function toast(html, kind, stay) {
    const t = document.createElement('div'); t.className = 'avaT' + (kind ? ' ' + kind : '');
    t.innerHTML = `<span>${html}</span><button type="button" aria-label="Close">&times;</button>`;
    t.querySelector('button').onclick = () => t.remove(); toasts.appendChild(t);
    if (!stay) setTimeout(() => t.remove(), 8000);
    return t;
  }

  function refresh() { document.body.classList.toggle('ava-admin', on()); }
  refresh();

  function showDlg() {
    const a = get();
    if (!REPO) {
      dlg.innerHTML = `<h3>Manage</h3><p>This page is not on GitHub, so it cannot be managed from here.</p><div class="row"><button type="button" data-x>Close</button></div>`;
    } else if (a) {
      dlg.innerHTML = `<h3>Manage mode is on</h3><p>Connected as <b>${esc(a.name || a.login || 'manager')}</b>. Every button works straight away, without a GitHub form. The key is only stored in this browser.</p>
        <div class="row"><button type="button" id="avaOff">Sign out on this device</button><button type="button" class="go" data-x>Close</button></div>`;
    } else {
      dlg.innerHTML = `<h3>Manage</h3><p>Paste your manage key to add, stop, rename and delete games and sort them into folders, without GitHub forms. The key is only stored in this browser.</p>
        <label for="avaTok">Manage key</label><input id="avaTok" type="password" autocomplete="off" placeholder="github_pat_…">
        <label for="avaName">Your name <span style="text-transform:none;letter-spacing:0;color:#64748b;font-weight:400">(shown in the history)</span></label><input id="avaName" autocomplete="off" maxlength="30" placeholder="e.g. Mike">
        <div class="msg" id="avaMsg" hidden></div>
        <div class="row"><button type="button" data-x>Cancel</button><button type="button" class="go" id="avaGo">Connect</button></div>`;
    }
    dlg.querySelectorAll('[data-x]').forEach(b => b.onclick = () => dlg.close());
    const off = dlg.querySelector('#avaOff'); if (off) off.onclick = () => { put(null); refresh(); dlg.close(); toast('Manage mode is off on this device.') };
    const go = dlg.querySelector('#avaGo');
    if (go) go.onclick = async () => {
      const tok = dlg.querySelector('#avaTok').value.trim(), name = dlg.querySelector('#avaName').value.trim(), msg = dlg.querySelector('#avaMsg');
      const say = (t, ok) => { msg.textContent = t; msg.className = 'msg' + (ok ? ' ok' : ''); msg.hidden = false };
      if (!tok) { say('Paste the key first.'); return }
      go.disabled = true; say('Checking…', true);
      try {
        const r = await fetch(`https://api.github.com/repos/${REPO}`, { headers: { Authorization: 'Bearer ' + tok, Accept: 'application/vnd.github+json' }, cache: 'no-store' });
        if (r.status === 401) { say('This key does not work (expired or not copied completely).'); go.disabled = false; return }
        const j = await r.json();
        if (!r.ok || !j.permissions || !(j.permissions.push || j.permissions.admin)) { say('This key cannot change ' + REPO + '. Make one with "Contents: Read and write".'); go.disabled = false; return }
        let login = ''; try { const u = await fetch('https://api.github.com/user', { headers: { Authorization: 'Bearer ' + tok } }); if (u.ok) login = (await u.json()).login || '' } catch (e) {}
        put({ token: tok, name: name || login, login }); refresh(); dlg.close();
        toast('&#9989; Manage mode is on. The buttons now work straight away.', 'ok');
      } catch (e) { say('No connection with GitHub. Try again.'); go.disabled = false }
    };
    dlg.showModal();
  }
  gear.onclick = showDlg;

  // a small question dialog (rename): resolves with the typed text, or null
  function askText(title, label, value, okText) {
    return new Promise(res => {
      ask.innerHTML = `<h3>${esc(title)}</h3><label for="avaAskIn">${esc(label)}</label><input id="avaAskIn" maxlength="60" autocomplete="off" value="${esc(value || '')}">
        <div class="row"><button type="button" id="avaAskNo">Cancel</button><button type="button" class="go" id="avaAskOk">${esc(okText || 'Save')}</button></div>`;
      const inp = ask.querySelector('#avaAskIn'); let done = false;
      const fin = v => { if (done) return; done = true; ask.close(); res(v) };
      ask.querySelector('#avaAskNo').onclick = () => fin(null);
      ask.querySelector('#avaAskOk').onclick = () => { const v = inp.value.trim(); if (v) fin(v); else inp.focus() };
      inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); ask.querySelector('#avaAskOk').click() } });
      ask.addEventListener('close', () => fin(null), { once: true });
      ask.showModal(); inp.select();
    });
  }

  // ---- send a request ----
  const b64 = s => btoa(unescape(encodeURIComponent(s)));
  const label = t => t.replace(/^Make video (\d+)/i, 'Video of game $1').replace(/^Set update (\d+) every (\d+)/i, (m, g, n) => `Game ${g}: update every ${n >= 60 ? n / 60 + ' h' : n + ' min'}`);
  async function send(title, body) {
    const a = get(); if (!a || !REPO) return false;
    const video = /^\s*make video/i.test(title);
    const id = new Date().toISOString().replace(/\D/g, '').slice(0, 14) + '-' + Math.random().toString(36).slice(2, 7);
    const file = `requests/${video ? 'video-' : ''}${id}.json`;
    const req = { id, title, body: body || '', by: a.name || a.login || '', at: new Date().toISOString() };
    const t = toast('&#9203; ' + esc(label(title)) + ' – sending…', '', true);
    try {
      const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${file}`, {
        method: 'PUT', headers: { Authorization: 'Bearer ' + a.token, Accept: 'application/vnd.github+json' },
        body: JSON.stringify({ message: 'Site: ' + title + (req.by ? ' (' + req.by + ')' : ''), content: b64(JSON.stringify(req, null, 1)) })
      });
      if (!r.ok) {
        t.remove();
        toast(r.status === 401 ? '&#10060; Your key no longer works. Connect again under &#9881;&#65039;.' : r.status === 403 || r.status === 404 ? '&#10060; Your key cannot write (needs "Contents: Read and write").' : '&#10060; Sending failed (' + r.status + '). Try again.', 'bad', true);
        return true;
      }
      t.querySelector('span').innerHTML = '&#9203; ' + esc(label(title)) + (video ? ' – the video is being made; this takes a few minutes. The link appears here.' : ' – saved, the site is being updated (1–3 min)…');
      t.dataset.id = id;
      setPending([...pending(), { id, title, video, at: Date.now() }]);
      poll();
    } catch (e) { t.remove(); toast('&#10060; No connection with GitHub. Try again.', 'bad', true) }
    return true;
  }

  // ---- follow requests until they are done ----
  let polling = null;
  const toastFor = id => [...toasts.children].find(x => x.dataset.id === id);
  async function check() {
    const list = pending(); if (!list.length) { clearInterval(polling); polling = null; return }
    const a = get(); let status = {}, vids = {};
    try { const r = await fetch(ROOT + 'status.json?t=' + Date.now(), { cache: 'no-store' }); if (r.ok) status = (await r.json()).done || {} } catch (e) {}
    if (a && list.some(p => p.video)) {
      try { const r = await fetch(`https://api.github.com/repos/${REPO}/contents/videos_log.json?t=${Date.now()}`, { headers: { Authorization: 'Bearer ' + a.token, Accept: 'application/vnd.github.raw+json' }, cache: 'no-store' }); if (r.ok) vids = await r.json() } catch (e) {}
    }
    let reload = false; const left = [];
    for (const p of list) {
      const s = p.video ? vids[p.id] : status[p.id];
      if (!s) {
        if (Date.now() - p.at > (p.video ? 90 : 15) * 60000) { const t = toastFor(p.id); t && t.remove(); toast('&#9888;&#65039; ' + esc(label(p.title)) + ' is taking very long. Check GitHub → Actions.', 'bad', true) }
        else { left.push(p); if (!toastFor(p.id)) { const t = toast('&#9203; ' + esc(label(p.title)) + ' – working…', '', true); t.dataset.id = p.id } }
        continue;
      }
      const t = toastFor(p.id); t && t.remove();
      if (p.video) toast(s.ok ? `&#127909; Video ready: <a href="${esc(s.url)}" target="_blank" rel="noopener">download</a> (${esc(s.length || '')} s)` : '&#10060; Video failed: ' + esc(s.msg || ''), s.ok ? 'ok' : 'bad', true);
      else if (s.ok) { toast('&#9989; ' + esc(label(p.title)) + ' – done.', 'ok'); reload = true }
      else toast('&#10060; ' + esc(label(p.title)) + ' – not done: ' + esc(s.msg || ''), 'bad', true);
    }
    setPending(left);
    if (reload && !document.querySelector('dialog[open]')) setTimeout(() => location.reload(), 1500);
  }
  function poll() { if (!polling) { polling = setInterval(check, 10000); setTimeout(check, 4000) } }
  if (pending().length) poll();

  // ---- every GitHub-form link and window.open on the page goes through send() when beheer is on ----
  const ISSUE = REPO ? `https://github.com/${REPO}/issues/new` : '\u0000';
  const fromUrl = u => { try { const x = new URL(u); return [x.searchParams.get('title') || '', x.searchParams.get('body') || ''] } catch (e) { return null } };
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[href]'); if (!a || !on() || !a.href.startsWith(ISSUE)) return;
    e.preventDefault(); const tb = fromUrl(a.href); if (tb && tb[0]) send(tb[0], tb[1]);
    const d = a.closest('dialog'); if (d) d.close();
  }, true);
  const open0 = window.open.bind(window);
  window.open = function (u, ...rest) {
    if (on() && typeof u === 'string' && u.startsWith(ISSUE)) { const tb = fromUrl(u); if (tb && tb[0]) send(tb[0], tb[1]); return null }
    return open0(u, ...rest);
  };

  window.AVA_ADMIN = { on, send, ask: askText, toast };
})();
