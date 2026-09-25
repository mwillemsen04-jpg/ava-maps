"""Write the overview page site/index.html from games.json.

The page lists live maps and saved games. "Create map" and "Stop & save" open a pre-filled GitHub
issue ("Add game <code>" / "Stop game <code>"); the update workflow picks it up for repository
members only. Set the repository in config.json ("repo": "user/name") or let GitHub Actions fill
GITHUB_REPOSITORY.
"""
import json, os
from common import SITE, config, load_registry

cfg = config()
repo = os.environ.get('GITHUB_REPOSITORY') or cfg.get('repo') or ''
reg = load_registry()
games = reg['games']
data = dict(title=cfg['title'], repo=repo, tz=cfg['timezone'], folders=reg.get('folders', []),
            games=[dict({k: g.get(k) for k in ('id', 'name', 'status', 'reason', 'added', 'ended', 'last', 'folder', 'every')},
                        page=os.path.exists(os.path.join(SITE, 'games', str(g['id']), 'index.html'))) for g in games])

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Share+Tech+Mono&display=swap">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0c10;color:#e2e8f0;font-family:'Rajdhani',sans-serif;min-height:100vh}
button,input{font-family:inherit}
input{background:#1a1f2e;border:1px solid #333;border-radius:4px;color:#e2e8f0;font-size:16px;padding:10px 14px;min-height:44px}
input::placeholder{color:#64748b}
button,.btn{cursor:pointer;border:none;border-radius:6px;min-height:40px;font-weight:700;font-size:13px;padding:9px 22px;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;white-space:nowrap}
:focus-visible{outline:2px solid #b48c3c;outline-offset:2px}
.mono{font-family:'Share Tech Mono',monospace}
/* splash */
#splash{position:fixed;inset:0;z-index:50;background:#0a0c10;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;transition:opacity .5s}
#splash.out{opacity:0;pointer-events:none}
@keyframes fadeIn{from{opacity:0;transform:scale(.9)}to{opacity:1;transform:scale(1)}}
@keyframes glow{0%,100%{box-shadow:0 0 40px rgba(180,140,60,.3)}50%{box-shadow:0 0 80px rgba(180,140,60,.7)}}
@keyframes blink{0%,100%{opacity:.3}50%{opacity:1}}
.logo-btn{background:none;border:0;padding:0;border-radius:50%;cursor:pointer;margin-bottom:28px;min-height:0;transition:transform .2s}.logo-btn:hover{transform:scale(1.05)}.logo-btn:focus-visible{outline:3px solid #b48c3c;outline-offset:6px}
.logo-splash{display:block;width:220px;height:220px;border-radius:50%;object-fit:cover;border:3px solid rgba(180,140,60,.6);animation:fadeIn 1.2s ease forwards,glow 3s ease-in-out 1.2s infinite}
.splash-t{font-size:38px;font-weight:700;letter-spacing:8px;text-transform:uppercase;margin-bottom:6px;text-align:center}
.splash-s{font-size:14px;letter-spacing:5px;color:#b48c3c;text-transform:uppercase;margin-bottom:50px}
.enter{font-size:12px;color:#475569;letter-spacing:3px;text-transform:uppercase;animation:blink 2s ease-in-out infinite;background:none;min-height:0;padding:0;font-weight:400}
/* header */
header{background:#0d1117;border-bottom:1px solid #1e293b;padding:12px 20px;display:flex;align-items:center;gap:14px}
header img{height:40px;width:40px;border-radius:50%;object-fit:cover;border:2px solid rgba(180,140,60,.5)}
.ht{font-size:18px;font-weight:700;letter-spacing:3px;line-height:1}
.hs{font-size:10px;letter-spacing:2px;color:#b48c3c;text-transform:uppercase}
.counts{margin-left:auto;display:flex;gap:8px;font-size:12px;color:#64748b;letter-spacing:1px;text-transform:uppercase}
.counts b{color:#e2e8f0;font-family:'Share Tech Mono',monospace;font-size:14px;margin-right:4px}
/* cards */
.inner{max-width:860px;margin:48px auto;padding:0 24px}
.card{background:#0d1117;border-radius:14px;padding:28px;margin-bottom:24px;border:1px solid #1e293b}
.label{font-size:11px;font-weight:700;color:#b48c3c;letter-spacing:3px;text-transform:uppercase;margin-bottom:14px}
.label span{color:#334155;font-weight:400}
.addrow{display:flex;gap:8px;flex-wrap:wrap}
#code{flex:1;min-width:180px;font-family:'Share Tech Mono',monospace}
#gname{flex:1;min-width:180px}
#create{background:#1a2330;color:#475569;padding:0 28px;font-size:15px;min-height:44px}
#create.ok{background:#16a34a;color:#fff}
.hint{font-size:12px;color:#475569;margin-top:10px;line-height:1.5}
.err{font-size:13px;color:#f87171;margin-top:8px}
.empty{color:#334155;font-size:13px;padding:24px 0;text-align:center;border-top:1px solid #1e293b}
.item{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 20px;margin-bottom:8px;border-radius:8px;background:#111827;border:1px solid #1e293b;border-left:3px solid #b48c3c;transition:background .15s}
.item:hover{background:#151e2d}
.item.live{border-left-color:#22c55e}
.item:last-child{margin-bottom:0}
.info{flex:1;min-width:0}
.name{font-size:18px;font-weight:700;margin-bottom:4px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.pill{font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:2px 8px;border-radius:4px;border:1px solid}
.pill.live{color:#22c55e;border-color:#14532d;background:#052e16}
.pill.saved{color:#94a3b8;border-color:#334155;background:#0f172a}
.meta{font-size:11px;color:#475569;display:flex;gap:10px;flex-wrap:wrap}
.score{display:flex;align-items:center;gap:10px;margin:10px 0 8px;font-size:13px;font-weight:700}
.score .g{color:#22c55e}.score .r{color:#ef4444}
.score b{font-family:'Share Tech Mono',monospace;font-size:17px;font-weight:400}
.bar{flex:1;display:flex;height:6px;border-radius:3px;overflow:hidden;background:#1e293b;min-width:80px;max-width:260px}
.bar i{background:#22c55e}.bar em{flex:1;background:#ef4444}
.tm{display:flex;flex-direction:column;gap:5px}.teams{display:flex;gap:5px;flex-wrap:wrap}.chip.side{min-width:48px;text-align:center}
.chip{font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;letter-spacing:.5px;color:#fff;opacity:.9}
.chip.side{background:none;border:1px solid;opacity:1}
.acts{display:flex;gap:6px;flex-shrink:0}
.open{background:#1e3a5f;color:#60a5fa;border:1px solid #1e40af}
.stop{background:#1a0a0a;color:#f87171;border:1px solid #7f1d1d;padding:9px 14px}
.folders{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
.fchip{background:#111827;color:#94a3b8;border:1px solid #1e293b;padding:6px 12px;min-height:34px;font-size:13px;font-weight:600;border-radius:6px}
.fchip b{color:#475569;font-weight:400;margin-left:4px}
.fchip.new{border-style:dashed;color:#b48c3c}.fchip.new:hover{border-color:#b48c3c}
.fdel{background:none;border:0;color:#64748b;font-size:12px;margin-left:8px;cursor:pointer;text-decoration:underline}.fdel:hover{color:#fca5a5}
.fchip.on{background:#1e293b;color:#e2e8f0;border-color:#b48c3c}
.fhead{display:flex;align-items:center;gap:8px;margin:18px 0 8px;font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#94a3b8}
.fhead:first-child{margin-top:0}.fhead b{color:#475569;font-weight:400}
.del{background:#1a0a0a;color:#f87171;border:1px solid #7f1d1d;padding:9px 14px}.del:hover{background:#2a0e0e}
.move{background:#111827;color:#94a3b8;border:1px solid #334155;padding:9px 14px}
.field{display:flex;flex-direction:column;gap:6px;margin-bottom:18px}
.field label{font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#b48c3c}
.field input{width:100%}
.note{font-size:12px;color:#f87171;margin:-8px 0 14px}
.chip.g{background:#14532d;color:#bbf7d0}.chip.r{background:#7f1d1d;color:#fecaca}
.foot{text-align:center;margin-top:24px;font-size:10px;color:#1e293b;letter-spacing:2px;text-transform:uppercase}
dialog{background:#0d1117;color:#e2e8f0;border:1px solid #1e293b;border-radius:14px;padding:28px;max-width:440px;margin:auto}
dialog::backdrop{background:rgba(0,0,0,.7)}
dialog h3{font-size:20px;letter-spacing:1px;margin-bottom:10px}
dialog p{color:#94a3b8;font-size:14px;line-height:1.5;margin-bottom:20px}
dialog .acts{justify-content:flex-end}
.keep{background:#1a2330;color:#94a3b8;border:1px solid #334155}
@media (max-width:640px){.inner{margin:24px auto;padding:0 12px}.card{padding:18px}.item{flex-direction:column;align-items:stretch}.acts{justify-content:flex-end}.counts{display:none}.splash-t{font-size:26px;letter-spacing:5px}.logo-splash{width:170px;height:170px}}
</style>
</head>
<body>
<div id="splash">
  <button class="logo-btn" id="enterbtn" type="button" aria-label="Enter the database"><img class="logo-splash" src="__LOGO__" alt="AF logo"></button>
  <div class="splash-t">Amicitia Ferox</div>
  <div class="splash-s">__TITLE__</div>
  <div class="enter">&#10022; Click to enter &#10022;</div>
</div>
<header>
  <img src="__LOGO__" alt="AF logo">
  <div><div class="ht">__TITLE__</div><div class="hs">Amicitia Ferox</div></div>
  <div class="counts"><span><b id="nlive">0</b>live</span><span>·</span><span><b id="nsaved">0</b>saved</span></div>
</header>
<div class="inner">
  <section class="card">
    <div class="label">&#10133; New map</div>
    <form class="addrow" id="add" novalidate>
      <input id="code" inputmode="numeric" autocomplete="off" placeholder="Game code, e.g. 10917564" aria-label="Game code">
      <input id="gname" autocomplete="off" placeholder="Name (optional)" aria-label="Name">
      <button id="create" type="submit">Create &#8594;</button>
    </form>
    <div class="err" id="err" hidden></div>
    <div class="hint" id="how"></div>
  </section>
  <section class="card">
    <div class="label">&#128994; Live maps <span id="cl">(0)</span></div>
    <div id="live"></div>
  </section>
  <section class="card">
    <div class="label">&#128190; Saved games <span id="cs">(0)</span></div>
    <div id="saved"></div>
  </section>
  <div class="foot">Amicitia Ferox · Since 2024</div>
</div>
<datalist id="flist"></datalist>
<dialog id="stopdlg" aria-labelledby="stopt"><h3 id="stopt">Are you sure?</h3><p id="stopp"></p>
  <div class="field"><label for="stopf">Save in folder <span style="color:#475569;letter-spacing:0;text-transform:none;font-weight:400">(optional)</span></label><input id="stopf" list="flist" placeholder="e.g. Season 1" autocomplete="off"></div>
  <p class="note" id="stopn" hidden>Not connected to GitHub yet (config.json → "repo").</p>
  <div class="acts"><button class="keep" id="keep" type="button">Cancel</button><a class="btn stop" id="stopgo" href="#" target="_blank" rel="noopener">Yes, stop &amp; save</a></div></dialog>
<dialog id="newdlg" aria-labelledby="newt"><h3 id="newt">New folder</h3><p>Make an empty folder for saved games, e.g. a season or a clan war.</p>
  <div class="field"><label for="newf">Folder name</label><input id="newf" placeholder="e.g. Season 1" maxlength="60" autocomplete="off"></div>
  <p class="note" id="newn" hidden>Not connected to GitHub yet (config.json → "repo").</p>
  <div class="acts"><button class="keep" id="nkeep" type="button">Cancel</button><a class="btn open" id="newgo" href="#" target="_blank" rel="noopener">Create folder</a></div></dialog>
<dialog id="deldlg" aria-labelledby="delt"><h3 id="delt">Delete folder?</h3><p id="delp"></p>
  <p class="note" id="deln" hidden>Not connected to GitHub yet (config.json → "repo").</p>
  <div class="acts"><button class="keep" id="dkeep" type="button">Cancel</button><a class="btn stop" id="delgo" href="#" target="_blank" rel="noopener">Yes, delete folder</a></div></dialog>
<dialog id="delgdlg" aria-labelledby="delgt"><h3 id="delgt">Delete this game?</h3><p id="delgp"></p>
  <p class="note" id="delgn" hidden>Not connected to GitHub yet (config.json → "repo").</p>
  <div class="acts"><button class="keep" id="gkeep" type="button">Cancel</button><a class="btn stop" id="delggo" href="#" target="_blank" rel="noopener">Yes, delete for good</a></div></dialog>
<dialog id="movedlg" aria-labelledby="movet"><h3 id="movet">Move to folder</h3><p id="movep"></p>
  <div class="field"><label for="movef">Folder</label><input id="movef" list="flist" placeholder="Existing or new folder name" autocomplete="off"></div>
  <p class="note" id="moven" hidden>Not connected to GitHub yet (config.json → "repo").</p>
  <div class="acts"><button class="keep" id="mkeep" type="button">Cancel</button><a class="btn open" id="movego" href="#" target="_blank" rel="noopener">Move</a></div></dialog>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);
const DOC={1:['Axis','#455a64'],2:['Allies','#1565c0'],3:['Comintern','#16a34a'],4:['Pan-Asian','#e53935']};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const when=ms=>ms?new Date(ms).toLocaleString('en-GB',{timeZone:D.tz,day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}):'—';
const issue=(t,b)=>D.repo?`https://github.com/${D.repo}/issues/new?title=${encodeURIComponent(t)}&body=${encodeURIComponent(b||'')}`:null;
// splash: every time the page opens; a click anywhere (or Enter / Space) opens the database
// coming back from a map (back arrow, or the browser's back button in the same tab) skips the splash
const sp=$('splash');let entered=false;try{entered=sessionStorage.getItem('avaIn')==='1'}catch(e){}
if(location.hash==='#games'||entered){sp.remove();if(location.hash)history.replaceState(null,'',location.pathname+location.search)}
else{sp.onclick=()=>{sp.classList.add('out');try{sessionStorage.setItem('avaIn','1')}catch(e){}setTimeout(()=>sp.remove(),600)};$('enterbtn').focus()}
const live=D.games.filter(g=>g.status==='live'),saved=D.games.filter(g=>g.status==='saved').reverse();
$('nlive').textContent=live.length;$('nsaved').textContent=saved.length;$('cl').textContent='('+live.length+')';$('cs').textContent='('+saved.length+')';
$('how').textContent=D.repo?'Create opens a short GitHub form: press "Submit new issue" and the map is ready within a few minutes (members of the repository only).':'Set "repo" in config.json so Create and Stop can open GitHub.';
const teams=L=>L&&L.teams?['G','R'].map(k=>`<div class="teams"><span class="chip side" style="color:${k==='G'?'#22c55e':'#ef4444'};border-color:${k==='G'?'#14532d':'#7f1d1d'}">${k==='G'?'Green':'Red'}</span>`+L.teams[k].map(n=>`<span class="chip ${k==='G'?'g':'r'}" title="${esc(n.c)}${DOC[n.f]?' · '+DOC[n.f][0]:''}">${esc(n.c)}</span>`).join('')+'</div>').join(''):'';
const score=L=>L&&L.score?`<div class="score"><span class="g">Green <b>${L.score.G}</b></span><span class="bar"><i style="width:${Math.round(L.score.G/Math.max(1,L.score.G+L.score.R)*100)}%"></i><em></em></span><span class="r"><b>${L.score.R}</b> Red</span></div>`:'';
const item=(g,isLive)=>{const L=g.last,name=esc(g.name||('Game '+g.id));
  const metaL=isLive?(L&&g.page?[`&#128339; ${when(L.fetched)}`,`&#128197; Day ${L.day??'?'}`,`&#127757; ${L.provinces.G} / ${L.provinces.R} provinces`,`&#128260; every ${({15:'15 min',30:'30 min',60:'hour',120:'2 hours',240:'4 hours'})[g.every||60]||((g.every||60)+' min')}`]:[`&#128339; added ${esc(g.added||'')}`,'waiting for the first update'])
    :[`&#128190; ${esc(g.ended||'')}`,g.reason==='ended'?'game ended':'stopped by you',L&&L.winner?(L.winner==='G'?'Team green won':'Team red won'):''];
  return `<div class="item${isLive?' live':''}"><div class="info">
    <div class="name">${name}<span class="pill ${isLive?'live':'saved'}">${isLive?'&#9679; Live':'Saved'}</span></div>
    <div class="meta"><span class="mono">#${esc(g.id)}</span>${metaL.filter(Boolean).map(x=>`<span>${x}</span>`).join('')}</div>
    ${score(L)}<div class="tm">${teams(L)}</div></div>
    <div class="acts">${g.page?`<a class="btn open" href="games/${esc(g.id)}/index.html">Open</a>`:''}${isLive?`<button class="stop" type="button" data-stop="${esc(g.id)}" data-name="${name}" aria-label="Stop and save ${name}">&#9632; Stop</button>`:`<button class="move" type="button" data-move="${esc(g.id)}" data-name="${name}" aria-label="Move ${name} to a folder">&#128193; Move</button><button class="del" type="button" data-delg="${esc(g.id)}" data-name="${name}" aria-label="Delete ${name}">&#128465; Delete</button>`}</div></div>`};
$('live').innerHTML=live.length?live.map(g=>item(g,true)).join(''):'<div class="empty">No live maps — enter a game code above</div>';
// saved games in folders: a bar to pick one folder, or all folders grouped
const FOLDERS=[...new Set([...(D.folders||[]),...saved.map(g=>g.folder)].filter(Boolean))].sort((a,b)=>a.localeCompare(b));
$('flist').innerHTML=FOLDERS.map(f=>`<option value="${esc(f)}">`).join('');
let fsel='*';try{fsel=localStorage.getItem('avaFolder')||'*'}catch(e){}
if(fsel!=='*'&&fsel!==''&&!FOLDERS.includes(fsel))fsel='*';
function drawSaved(){
  const n=f=>saved.filter(g=>(g.folder||'')===f).length,uns=n('');
  const bar=`<div class="folders" role="tablist"><button class="fchip${fsel==='*'?' on':''}" data-f="*" type="button">All<b>${saved.length}</b></button>${FOLDERS.map(f=>`<button class="fchip${fsel===f?' on':''}" data-f="${esc(f)}" type="button">&#128193; ${esc(f)}<b>${n(f)}</b></button>`).join('')}${uns&&FOLDERS.length?`<button class="fchip${fsel===''?' on':''}" data-f="" type="button">Unsorted<b>${uns}</b></button>`:''}<button class="fchip new" id="newbtn" type="button">+ New folder</button></div>`;
  const group=f=>saved.filter(g=>(g.folder||'')===f).map(g=>item(g,false)).join('');
  const emptyF='<div class="empty">Empty folder — use Move on a saved game, or pick this folder when you stop a game</div>';
  const del=f=>`<button class="fdel" type="button" data-del="${esc(f)}">delete</button>`;
  const body=!saved.length&&!FOLDERS.length&&fsel==='*'?'<div class="empty">Games that end, or that you stop, are saved here</div>'
    :fsel==='*'?(FOLDERS.length?[...FOLDERS.map(f=>`<div class="fhead">&#128193; ${esc(f)} <b>(${n(f)})</b>${del(f)}</div>`+(group(f)||emptyF)),uns?`<div class="fhead">Unsorted <b>(${uns})</b></div>`+group(''):''].join(''):group(''))
    :fsel===''?group(''):(group(fsel)||emptyF)+`<div style="text-align:right">${del(fsel)}</div>`;
  $('saved').innerHTML=bar+(body||'<div class="empty">No games here</div>')}
drawSaved();
$('saved').addEventListener('click',e=>{
  if(e.target.closest('#newbtn')){$('newf').value='';$('newn').hidden=!!D.repo;$('newgo').href='#';$('newdlg').showModal();$('newf').focus();return}
  const d=e.target.closest('[data-del]');if(d){const f=d.dataset.del,c=saved.filter(g=>g.folder===f).length;$('delp').innerHTML='Delete the folder <b>'+esc(f)+'</b>?'+(c?' Its '+c+' game'+(c>1?'s go':' goes')+' back to Unsorted; nothing is deleted.':' It is empty.');
    $('deln').hidden=!!D.repo;$('delgo').href=D.repo?issue('Delete folder '+f,''):'#';$('deldlg').showModal();return}
  const b=e.target.closest('[data-f]');if(!b)return;fsel=b.dataset.f;try{localStorage.setItem('avaFolder',fsel)}catch(e){}drawSaved()});
const code=$('code'),btn=$('create'),err=$('err');
const valid=()=>/^\d{6,10}$/.test(code.value.trim());
code.addEventListener('input',()=>{code.value=code.value.replace(/\D/g,'');btn.classList.toggle('ok',valid());err.hidden=true});
$('add').addEventListener('submit',e=>{e.preventDefault();const c=code.value.trim();
  if(!valid()){err.textContent='A game code is a number of 6 to 10 digits.';err.hidden=false;return}
  if(live.some(g=>String(g.id)===c)){err.textContent='This game already has a live map.';err.hidden=false;return}
  const u=issue('Add game '+c,$('gname').value.trim()?'Name: '+$('gname').value.trim():'');
  if(u)window.open(u,'_blank','noopener');else{err.textContent='No GitHub repository set yet (config.json → "repo").';err.hidden=false}});
// Stop: always asks "Are you sure?" first; the folder (optional) goes along with the request
const dlg=$('stopdlg'),mdlg=$('movedlg');let target=null;
const stopUrl=()=>issue('Stop game '+target.id,$('stopf').value.trim()?'Folder: '+$('stopf').value.trim():'');
const moveUrl=()=>issue('Move game '+target.id+' to '+$('movef').value.trim(),'');
document.addEventListener('click',e=>{const b=e.target.closest('[data-stop],[data-move]');if(!b)return;
  if(b.dataset.stop){target={id:b.dataset.stop};$('stopp').innerHTML='Stop updating <b>'+b.dataset.name+'</b>? It moves to Saved games with everything up to now and stops fetching new data. You can still open and replay it.';
    $('stopf').value='';$('stopn').hidden=!!D.repo;$('stopgo').href=D.repo?stopUrl():'#';$('stopgo').setAttribute('aria-disabled',String(!D.repo));dlg.showModal()}
  else{target={id:b.dataset.move};$('movep').innerHTML='Put <b>'+b.dataset.name+'</b> in a folder. Type a new name to make a new folder.';
    $('movef').value='';$('moven').hidden=!!D.repo;$('movego').href='#';mdlg.showModal();$('movef').focus()}});
$('stopf').addEventListener('input',()=>{if(D.repo)$('stopgo').href=stopUrl()});
$('movef').addEventListener('input',()=>{if(D.repo&&$('movef').value.trim())$('movego').href=moveUrl()});
// Delete (saved games only): always asks "are you sure?" first
document.addEventListener('click',e=>{const b=e.target.closest('[data-delg]');if(!b)return;
  $('delgp').innerHTML='Delete <b>'+b.dataset.name+'</b> (#'+esc(b.dataset.delg)+')? The saved map and all its history are removed for good. This cannot be undone.';
  $('delgn').hidden=!!D.repo;$('delggo').href=D.repo?issue('Delete game '+b.dataset.delg,''):'#';$('delgdlg').showModal()});
$('delggo').addEventListener('click',e=>{if(!D.repo){e.preventDefault();return}$('delgdlg').close()});
$('gkeep').onclick=()=>$('delgdlg').close();
$('newf').addEventListener('input',()=>{if(D.repo&&$('newf').value.trim())$('newgo').href=issue('Create folder '+$('newf').value.trim(),'')});
$('newgo').addEventListener('click',e=>{if(!D.repo||!$('newf').value.trim()){e.preventDefault();$('newf').focus();return}$('newdlg').close()});
$('delgo').addEventListener('click',e=>{if(!D.repo){e.preventDefault();return}$('deldlg').close()});
$('nkeep').onclick=()=>$('newdlg').close();$('dkeep').onclick=()=>$('deldlg').close();
$('keep').onclick=()=>dlg.close();$('mkeep').onclick=()=>mdlg.close();
$('stopgo').addEventListener('click',e=>{if(!D.repo){e.preventDefault();return}dlg.close()});
$('movego').addEventListener('click',e=>{if(!D.repo||!$('movef').value.trim()){e.preventDefault();$('movef').focus();return}mdlg.close()});
</script>
</body>
</html>
'''

os.makedirs(SITE, exist_ok=True)
import base64
logo = os.path.join(os.path.dirname(SITE), 'map', 'logo.png')
LOGO = 'data:image/png;base64,' + base64.b64encode(open(logo, 'rb').read()).decode() if os.path.exists(logo) else ''
html = HTML.replace('__LOGO__', LOGO).replace('__TITLE__', cfg['title']).replace('__DATA__', json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
open(os.path.join(SITE, 'index.html'), 'w', encoding='utf-8').write(html)
open(os.path.join(SITE, '.nojekyll'), 'w').write('')
print(f"overview: {sum(g['status'] == 'live' for g in data['games'])} live, {sum(g['status'] == 'saved' for g in data['games'])} saved")
