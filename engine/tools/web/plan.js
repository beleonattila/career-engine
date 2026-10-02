// ---------------------------------------------------------------- plan: Timeline + To-do
// Injected into dashboard.html by dashboard.py. One store, two views (engine/tools/plan.py):
//   Timeline -- every item, past included: the long plan and how it has progressed.
//   To-do    -- open items still ahead, in the important x urgent matrix: what to do next.
// Ticking, flagging or recolouring an item in either view changes it in both.
// Saving needs the page served by engine/tools/serve.py; opened from disk it is read-only.
const DAY = 864e5, LANE = 28, BAR_H = 22;
const PLAN_API = location.protocol.indexOf('http') === 0;
let PLAN = DATA.plan.doc;                 // {version, rev, items, overrides}
const DERIVED = DATA.plan.derived;        // from records: applications sent, live deadlines
const PALETTE = ['#4f8cff', '#2ecc71', '#f1c40f', '#e67e22', '#e74c3c', '#9b59b6', '#1abc9c', '#ec6fb0', '#8d99ae'];
const KIND = {sent: 'applied', deadline: 'deadline'};
let planMsg = DATA.plan.error ? [DATA.plan.error, 'bad'] : ['', ''];

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function dms(s) { const p = String(s).split('-'); return Date.UTC(+p[0], +p[1] - 1, +p[2]); }
function isoOf(ms) { return new Date(ms).toISOString().slice(0, 10); }
// "Today" is the viewer's, not the generation date: a page opened from disk can be days old.
const TODAY_MS = (() => { const d = new Date(); return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()); })();
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function fmt(ms) { const d = new Date(ms); return d.getUTCDate() + ' ' + MON[d.getUTCMonth()] + (d.getUTCFullYear() !== new Date(TODAY_MS).getUTCFullYear() ? ' ' + d.getUTCFullYear() : ''); }
function textOn(hex) {
  const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  return (0.299 * r + 0.587 * g + 0.114 * b) > 150 ? '#0b0d10' : '#fff';
}

// ---- the store
function planItems() {
  const ov = PLAN.overrides || {};
  const der = DERIVED.map(d => Object.assign({}, d, ov[d.id] || {})).filter(d => !d.hidden);
  return PLAN.items.map(i => Object.assign({kind: 'user'}, i)).concat(der);
}
function findItem(id) { return planItems().find(i => i.id === id); }
function dueMs(i) { return dms(i.end || i.start); }
function filterQ() { const f = document.getElementById('filter'); return f ? f.value.toLowerCase() : ''; }
function matches(i) { const q = filterQ(); return !q || (i.title + ' ' + (i.notes || '')).toLowerCase().includes(q); }
// To-do = not done and not over. A span that has started but not ended is in progress, so it stays.
function isOpenTodo(i) { return !i.done && dueMs(i) >= TODAY_MS; }
// Your own items left open after their date. Record deadlines are excluded: once passed, the
// lead is retired by expire_sweep and there is nothing left to do.
function isPastOpen(i) { return !i.done && i.kind === 'user' && dueMs(i) < TODAY_MS; }
function planCount(id) { const it = planItems(); return id === 'todo' ? it.filter(isOpenTodo).length : it.length; }

function putItem(it) {
  if (it.kind === 'user') {
    const rec = {id: it.id, title: it.title, start: it.start, end: it.end || null, color: it.color,
      important: !!it.important, urgent: !!it.urgent, done: !!it.done, notes: it.notes || '',
      created: it.created || isoOf(TODAY_MS)};
    const k = PLAN.items.findIndex(x => x.id === it.id);
    if (k < 0) PLAN.items.push(rec); else PLAN.items[k] = rec;
  } else {
    // A record's item: only the look and the flags are ours; the date stays in the record.
    PLAN.overrides[it.id] = Object.assign({}, PLAN.overrides[it.id] || {},
      {color: it.color, important: !!it.important, urgent: !!it.urgent, done: !!it.done, notes: it.notes || ''});
  }
}
function dropItem(it) {
  if (it.kind === 'user') PLAN.items = PLAN.items.filter(x => x.id !== it.id);
  else PLAN.overrides[it.id] = Object.assign({}, PLAN.overrides[it.id] || {}, {hidden: true});
}
async function savePlan(okMsg) {
  if (!PLAN_API) return;
  planMsg = ['saving…', ''];
  showStatus();
  try {
    const r = await fetch('/api/plan', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(PLAN)});
    const b = await r.json().catch(() => null);
    if (r.status === 409 && b && b.plan) { PLAN = b.plan; planMsg = ['plan.json changed on disk — reloaded it; redo the last edit', 'warn']; }
    else if (!r.ok) { planMsg = ['not saved: ' + ((b && b.error) || r.status), 'bad']; await reloadPlan(); }
    else { PLAN = b.plan; planMsg = [okMsg || 'saved', 'ok']; }
  } catch (e) { planMsg = ['not saved — is serve.py still running?', 'bad']; }
  tabs(); render();
}
async function reloadPlan() {
  try { const r = await fetch('/api/plan', {cache: 'no-store'}); const b = await r.json(); if (r.ok && b.plan) PLAN = b.plan; } catch (e) {}
}
function planInit() {
  if (!PLAN_API) return;
  reloadPlan().then(() => { tabs(); if (active === 'timeline' || active === 'todo') render(); });
  window.addEventListener('focus', () => reloadPlan().then(() => { if (active === 'todo' && !document.querySelector('.pl-modal')) render(); }));
}
function showStatus() { const s = document.getElementById('planStatus'); if (s) { s.textContent = planMsg[0]; s.className = 'pl-status ' + planMsg[1]; } }
function roBanner() {
  return PLAN_API ? '' : '<div class="pl-ro"><b>Read-only.</b> This page was opened from disk, which cannot save. '
    + 'To add, edit or tick items run <code>python engine/tools/serve.py</code> — it opens this dashboard with saving switched on.</div>';
}

// ---- the editor (add, and the info page behind every ribbon and card)
const TRASH = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>';
function newItem(over) {
  return Object.assign({id: 'u-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), kind: 'user',
    title: '', start: isoOf(TODAY_MS), end: null, color: PALETTE[0], important: false, urgent: false, done: false, notes: ''}, over || {});
}
function openEditor(it, isNew) {
  closeEditor();
  const ro = !PLAN_API, rec = it.kind !== 'user', lockDates = ro || rec;
  const m = document.createElement('div');
  m.className = 'pl-modal';
  m.innerHTML = '<div class="pl-card" role="dialog" aria-modal="true" aria-label="Plan item">'
    + '<h3><span id="peDot" style="width:12px;height:12px;border-radius:50%;background:' + esc(it.color) + '"></span>'
    + (isNew ? 'Add to the plan' : (rec ? 'From your records' : 'Plan item'))
    + '<button class="x" id="peX" title="Close (Esc)">×</button></h3>'
    + '<label for="peT">Title</label><input type="text" id="peT" maxlength="200" value="' + esc(it.title) + '"' + (lockDates ? ' disabled' : '') + '>'
    + '<div class="pl-row"><div><label for="peS">Start</label><input type="date" id="peS" value="' + esc(it.start) + '"' + (lockDates ? ' disabled' : '') + '></div>'
    + '<div><label for="peE">End</label><input type="date" id="peE" value="' + esc(it.end || '') + '"' + (lockDates ? ' disabled' : '') + '></div></div>'
    + '<div class="pl-hint">' + (rec ? 'This date lives in the record — change it there with <code>/track</code>.'
        : 'Leave End empty for a single moment, e.g. an application sent.') + '</div>'
    + '<label>Colour</label><div class="pl-sw" id="peC">'
    + PALETTE.map(c => '<button type="button" data-c="' + c + '" style="background:' + c + '" title="' + c + '"' + (ro ? ' disabled' : '') + '></button>').join('')
    + '<input type="color" id="peCC" value="' + esc(it.color) + '" title="Any colour"' + (ro ? ' disabled' : '') + '></div>'
    + '<div class="pl-checks">'
    + ['important', 'urgent', 'done'].map(k => '<label><input type="checkbox" id="pe_' + k + '"' + (it[k] ? ' checked' : '') + (ro ? ' disabled' : '') + '>' + k[0].toUpperCase() + k.slice(1) + '</label>').join('')
    + '</div>'
    + '<label for="peN">Notes</label><textarea id="peN" maxlength="4000"' + (ro ? ' disabled' : '') + '>' + esc(it.notes || '') + '</textarea>'
    + (rec && it.path ? '<div class="pl-hint">Record: <a href="' + esc(it.path) + '">' + esc(it.path) + '</a></div>' : '')
    + '<div class="pl-err" id="peErr"></div>'
    + '<div class="pl-foot">'
    + (!isNew && !ro ? '<button class="pl-btn danger" id="peDel" title="' + (rec ? 'Hide from the plan — the record itself is untouched' : 'Delete this item') + '">' + TRASH + (rec ? 'Hide' : 'Delete') + '</button>' : '')
    + '<span class="sp"></span><button class="pl-btn" id="peCancel">' + (ro ? 'Close' : 'Cancel') + '</button>'
    + (ro ? '' : '<button class="pl-btn primary" id="peSave">' + (isNew ? 'Add' : 'Save') + '</button>')
    + '</div></div>';
  document.body.appendChild(m);
  let color = it.color;
  const $ = id => document.getElementById(id);
  const paint = () => {
    $('peDot').style.background = color; $('peCC').value = color;
    m.querySelectorAll('#peC button').forEach(b => b.classList.toggle('on', b.dataset.c === color));
  };
  paint();
  m.querySelectorAll('#peC button').forEach(b => b.onclick = () => { color = b.dataset.c; paint(); });
  $('peCC').oninput = e => { color = e.target.value; paint(); };
  // A new item dated entirely in the past is a record of what happened, not a task: pre-tick Done.
  if (isNew) {
    const pastDone = () => { const d = $('peE').value || $('peS').value; if (d) $('pe_done').checked = dms(d) < TODAY_MS; };
    $('peS').onchange = pastDone; $('peE').onchange = pastDone;
  }
  $('peX').onclick = closeEditor; $('peCancel').onclick = closeEditor;
  m.onclick = e => { if (e.target === m) closeEditor(); };
  if ($('peDel')) $('peDel').onclick = () => {
    if (!rec && !confirm('Delete “' + it.title + '”? This cannot be undone.')) return;
    dropItem(it); closeEditor(); savePlan(rec ? 'hidden from the plan' : 'deleted');
  };
  if ($('peSave')) $('peSave').onclick = () => {
    const t = $('peT').value.trim(), s = $('peS').value, e = $('peE').value || null;
    if (!t) return $('peErr').textContent = 'Give it a title.';
    if (!s) return $('peErr').textContent = 'Pick a start date.';
    if (e && e < s) return $('peErr').textContent = 'End is before start.';
    putItem(Object.assign({}, it, {title: t, start: s, end: e, color: color, notes: $('peN').value,
      important: $('pe_important').checked, urgent: $('pe_urgent').checked, done: $('pe_done').checked}));
    closeEditor(); savePlan(isNew ? 'added' : 'saved');
  };
  setTimeout(() => (isNew ? $('peT') : $('peCancel')).focus(), 0);
}
function closeEditor() { const m = document.querySelector('.pl-modal'); if (m) m.remove(); }
document.addEventListener('keydown', e => {
  if (!document.querySelector('.pl-modal')) return;
  if (e.key === 'Escape') closeEditor();
  if (e.key === 'Enter' && e.target.tagName === 'INPUT' && document.getElementById('peSave')) document.getElementById('peSave').click();
});
function addButton(over) {
  return PLAN_API ? '<button class="pl-btn primary" data-add=\'' + esc(JSON.stringify(over || {})) + '\'>+ Add</button>' : '';
}

// ---- Timeline: a zoomed, draggable Gantt view over a colour-only miniature of the whole plan
const TL = {ppd: null, left: null};       // pixels per day, left edge (ms)
const ZOOMS = [['1M', 31], ['3M', 92], ['6M', 183], ['1Y', 365], ['2Y', 730]];
let measureCtx = null;
function textW(s) {
  if (!measureCtx) { measureCtx = document.createElement('canvas').getContext('2d'); measureCtx.font = '12px -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif'; }
  return measureCtx.measureText(s).width;
}
function extent(items) {
  let lo = TODAY_MS - 90 * DAY, hi = TODAY_MS + 180 * DAY;
  items.forEach(i => { lo = Math.min(lo, dms(i.start)); hi = Math.max(hi, dueMs(i) + DAY); });
  return [lo - 21 * DAY, hi + 21 * DAY];
}
function flags(i) { return (i.important ? '★ ' : '') + (i.urgent ? '! ' : ''); }
// Greedy lane packing: each item takes the first lane free at its left edge. `span` gives an
// item's [left, right) in pixels, label included, so labels never overlap either.
function pack(items, span) {
  const S = items.map((it, k) => span(it, k));
  const ord = items.map((_, k) => k).sort((a, b) => S[a][0] - S[b][0]);
  const ends = [], lane = [];
  ord.forEach(k => {
    const [l, r] = S[k];
    let L = ends.findIndex(e => e <= l);
    if (L < 0) { L = ends.length; ends.push(r); } else ends[L] = r;
    lane[k] = L;
  });
  return {lane: lane, n: ends.length};
}
function viewDays() { const m = document.getElementById('tlMain'); return ((m && m.clientWidth) || 1000) / TL.ppd; }
function setZoom(days, centerMs) {
  const W = document.getElementById('tlMain').clientWidth || 1000;
  const c = centerMs != null ? centerMs : TL.left + viewDays() * DAY / 2;
  TL.ppd = Math.min(60, Math.max(0.15, W / days));
  TL.left = c - (W / TL.ppd) * DAY / 2;
  drawTimeline();
}
function renderTimeline() {
  const el = document.getElementById('table');
  el.innerHTML = roBanner() + '<div class="pl-bar">' + addButton()
    + '<span class="pl-sep"></span>' + ZOOMS.map(z => '<button class="pl-btn" data-zoom="' + z[1] + '">' + z[0] + '</button>').join('')
    + '<button class="pl-btn" data-zoom="all">All</button><span class="pl-sep"></span>'
    + '<button class="pl-btn" id="tlToday">Today</button>'
    + '<span class="pl-status" id="planStatus"></span></div>'
    + '<div class="tl-main" id="tlMain"><div class="tl-axis" id="tlAxis"></div><div class="tl-body" id="tlBody"></div></div>'
    + '<canvas class="tl-mini" id="tlMini" title="The whole plan — drag the window, or click to jump"></canvas>'
    + '<p class="note">Drag or scroll the wheel to move through time · Ctrl + wheel to zoom · click a ribbon to edit it'
    + (PLAN_API ? ' · double-click empty space to add an item there' : '') + '. ★ important · ! urgent · faded = done. '
    + 'Ribbons are spans; diamonds are moments. Applications sent and live deadlines come from your records.</p>';
  showStatus();
  const main = document.getElementById('tlMain');
  if (TL.ppd == null) { TL.ppd = Math.max(1, main.clientWidth / 150); TL.left = TODAY_MS - 45 * DAY; }
  el.querySelectorAll('[data-zoom]').forEach(b => b.onclick = () => {
    if (b.dataset.zoom !== 'all') return setZoom(+b.dataset.zoom);
    const [lo, hi] = extent(planItems());
    setZoom((hi - lo) / DAY, (lo + hi) / 2);
  });
  document.getElementById('tlToday').onclick = () => setZoom(viewDays(), TODAY_MS + viewDays() * DAY * 0.2);
  bindAdd(el);
  bindTimeline(main, document.getElementById('tlMini'));
  drawTimeline();
}
let tlFrame = 0;
function redraw() { if (!tlFrame) tlFrame = requestAnimationFrame(() => { tlFrame = 0; drawTimeline(); }); }
function drawTimeline() {
  const main = document.getElementById('tlMain');
  if (!main) return;
  // A hidden pane has no width; drawing then would only produce garbage (and the tick loops
  // below must always see a finite range), so wait for the resize that shows it.
  if (!(main.clientWidth > 0) || !isFinite(TL.ppd) || !isFinite(TL.left) || TL.ppd <= 0) return;
  const W = main.clientWidth, ppd = TL.ppd, left = TL.left, right = left + W / ppd * DAY;
  const X = ms => (ms - left) / DAY * ppd;
  document.querySelectorAll('[data-zoom]').forEach(b => b.classList.toggle('on', b.dataset.zoom !== 'all' && Math.abs(+b.dataset.zoom - W / ppd) < 2));

  // axis: months always; weeks or days once there is room to read them
  const ax = [], grid = [], monthPx = ppd * 30.4;
  const first = new Date(left - 31 * DAY);
  for (let y = first.getUTCFullYear(), m = first.getUTCMonth(); ; m++) {
    if (m > 11) { m = 0; y++; }
    const ms = Date.UTC(y, m, 1);
    if (ms > right) break;
    const x = X(ms), jan = m === 0;
    const lab = monthPx >= 44 ? MON[m] + (jan || ms <= left + 31 * DAY ? ' ' + y : '')
      : monthPx >= 13 ? (jan ? String(y) : m % 3 === 0 ? MON[m] : '') : (jan ? String(y) : '');
    ax.push('<div class="tl-tick' + (jan ? ' year' : '') + '" style="left:' + x + 'px">' + lab + '</div>');
    grid.push('<div class="tl-grid' + (jan ? ' year' : '') + '" style="left:' + x + 'px"></div>');
  }
  if (ppd >= 3) {
    const step = ppd >= 14 ? 1 : 7;
    let d = Math.floor(left / DAY) * DAY;
    if (step === 7) while (new Date(d).getUTCDay() !== 1) d += DAY;   // weeks start on Monday
    for (; d <= right; d += step * DAY) {
      const dd = new Date(d).getUTCDate();
      if (dd === 1) continue;
      ax.push('<div class="tl-tick minor" style="left:' + X(d) + 'px">' + (ppd * step >= 22 ? dd : '') + '</div>');
    }
  }
  document.getElementById('tlAxis').innerHTML = ax.join('');

  // ribbons and moments, packed into lanes at this zoom
  const items = planItems().filter(matches);
  const geo = i => {
    const x0 = X(dms(i.start));
    if (!i.end) return {pt: true, x0: x0, l: x0 - 7, r: x0 + 14 + textW(flags(i) + i.title) + 14};
    // a ribbon too short for its own label carries it outside, to the right, like a moment
    const x1 = X(dms(i.end) + DAY), w = Math.max(6, x1 - x0), tw = textW(flags(i) + i.title), out = w < Math.min(tw + 20, 120);
    return {pt: false, out: out, x0: x0, w: w, l: x0, r: x0 + w + (out ? 12 + tw : 0) + 6};
  };
  const G = items.map(geo);
  const P = pack(items, (i, k) => [G[k].l, G[k].r]);
  const body = document.getElementById('tlBody');
  body.style.height = (Math.max(P.n, 4) * LANE + 14) + 'px';
  const html = grid.slice();
  const tx = X(TODAY_MS);
  if (tx >= 0 && tx <= W) html.push('<div class="tl-today" style="left:' + tx + 'px"><span>TODAY</span></div>');
  items.forEach((i, k) => {
    const g = G[k];
    if (g.r < -50 || g.l > W + 50) return;
    const top = 8 + P.lane[k] * LANE, title = esc(flags(i) + i.title);
    const tip = esc(i.title + ' — ' + fmt(dms(i.start)) + (i.end ? ' → ' + fmt(dms(i.end)) : '') + (i.kind !== 'user' ? ' (from records)' : ''));
    const cls = 'tl-item ' + (g.pt ? 'pt' : 'bar') + (g.out ? ' out' : '') + (i.done ? ' done' : '');
    if (g.pt) html.push('<div class="' + cls + '" data-id="' + esc(i.id) + '" title="' + tip + '" style="left:' + (g.x0 - 6) + 'px;top:' + top + 'px"><i style="background:' + esc(i.color) + '"></i><span>' + title + '</span></div>');
    else {
      // keep a ribbon's label in view when the ribbon starts off-screen to the left
      const pad = g.out ? 0 : Math.max(0, Math.min(-g.x0, g.w - 60));
      html.push('<div class="' + cls + '" data-id="' + esc(i.id) + '" title="' + tip + '" style="left:' + g.x0 + 'px;width:' + g.w + 'px;top:' + top
        + 'px;background:' + esc(i.color) + ';color:' + textOn(i.color) + '"><span style="margin-left:' + pad + 'px">' + title + '</span></div>');
    }
  });
  body.innerHTML = html.join('');
  drawMini(items);
}
function drawMini(items) {
  const cv = document.getElementById('tlMini'), main = document.getElementById('tlMain');
  if (!cv) return;
  const W = cv.clientWidth, H = 58, dpr = window.devicePixelRatio || 1;
  cv.width = W * dpr; cv.height = H * dpr;
  const c = cv.getContext('2d');
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  const [lo, hi] = extent(planItems());
  TL.mini = {lo: lo, hi: hi, W: W};
  const sx = ms => (ms - lo) / (hi - lo) * W;
  const span = i => { const a = sx(dms(i.start)); return [a, Math.max(a + 3, i.end ? sx(dms(i.end) + DAY) : a + 3) + 1]; };
  const P = pack(items, span);
  const lh = Math.max(1.5, Math.min(6, (H - 8) / Math.max(P.n, 1)));
  items.forEach((i, k) => {
    const [a, b] = span(i);
    c.globalAlpha = i.done ? 0.45 : 1;
    c.fillStyle = i.color;
    c.fillRect(a, 4 + P.lane[k] * lh, b - a - 1, Math.max(1, lh - 1));
  });
  c.globalAlpha = 1;
  c.fillStyle = '#e74c3c';
  c.fillRect(sx(TODAY_MS), 0, 1.5, H);
  const a = sx(TL.left), b = sx(TL.left + main.clientWidth / TL.ppd * DAY);
  c.fillStyle = 'rgba(255,255,255,.09)';
  c.fillRect(a, 0, b - a, H);
  c.strokeStyle = '#4f8cff'; c.lineWidth = 1.5;
  c.strokeRect(a + .75, .75, Math.max(2, b - a - 1.5), H - 1.5);
}
function bindTimeline(main, mini) {
  let drag = null;
  main.onpointerdown = e => {
    if (e.button !== 0) return;
    const hit = e.target.closest('.tl-item');
    drag = {x: e.clientX, left: TL.left, moved: false, id: hit ? hit.dataset.id : null};
    main.setPointerCapture(e.pointerId);
  };
  main.onpointermove = e => {
    if (!drag) return;
    const dx = e.clientX - drag.x;
    if (Math.abs(dx) > 3) { drag.moved = true; main.classList.add('drag'); }
    if (drag.moved) { TL.left = drag.left - dx / TL.ppd * DAY; redraw(); }
  };
  main.onpointerup = () => {
    if (drag && !drag.moved && drag.id) { const it = findItem(drag.id); if (it) openEditor(it, false); }
    drag = null; main.classList.remove('drag');
  };
  main.ondblclick = e => {
    if (!PLAN_API || e.target.closest('.tl-item')) return;
    const ms = TL.left + (e.clientX - main.getBoundingClientRect().left) / TL.ppd * DAY;
    openEditor(newItem({start: isoOf(Math.floor(ms / DAY) * DAY)}), true);
  };
  main.onwheel = e => {
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) {
      const cx = e.clientX - main.getBoundingClientRect().left, at = TL.left + cx / TL.ppd * DAY;
      TL.ppd = Math.min(60, Math.max(0.15, TL.ppd * Math.exp(-e.deltaY * 0.0015)));
      TL.left = at - cx / TL.ppd * DAY;
    } else {
      const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      TL.left += d / TL.ppd * DAY;
    }
    redraw();
  };
  let mdrag = null;
  const msAt = e => { const m = TL.mini; return m.lo + (e.clientX - mini.getBoundingClientRect().left) / m.W * (m.hi - m.lo); };
  mini.onpointerdown = e => {
    const ms = msAt(e), span = viewDays() * DAY;
    if (ms < TL.left || ms > TL.left + span) TL.left = ms - span / 2;   // jump, then drag from there
    mdrag = {off: ms - TL.left};
    mini.setPointerCapture(e.pointerId);
    redraw();
  };
  mini.onpointermove = e => { if (mdrag) { TL.left = msAt(e) - mdrag.off; redraw(); } };
  mini.onpointerup = () => { mdrag = null; };
}
window.addEventListener('resize', () => { if (active === 'timeline') redraw(); });

// ---- To-do: the important x urgent matrix of what is still open and still ahead
const QUADS = [
  {imp: true, urg: true, cls: 'do', name: 'Do now', sub: 'important · urgent'},
  {imp: false, urg: true, cls: 'quick', name: 'Keep it short', sub: 'urgent · not important'},
  {imp: true, urg: false, cls: 'plan', name: 'Plan it', sub: 'important · not urgent'},
  {imp: false, urg: false, cls: 'later', name: 'Later, or drop', sub: 'neither'},
];
function rel(ms) {
  const d = Math.round((ms - TODAY_MS) / DAY);
  if (d === 0) return 'today';
  if (d === 1) return 'tomorrow';
  if (d < 0) return -d + 'd ago';
  return d <= 21 ? 'in ' + d + 'd' : fmt(ms);
}
function dueText(i) {
  const s = dms(i.start), soon = dueMs(i) - TODAY_MS <= 3 * DAY && dueMs(i) >= TODAY_MS;
  let t;
  if (!i.end) t = rel(s);
  else if (s > TODAY_MS) t = 'starts ' + rel(s) + ' · ends ' + rel(dms(i.end));
  else t = 'in progress · ends ' + rel(dms(i.end));
  return soon ? '<span class="soon">' + t + '</span>' : t;
}
function card(i) {
  return '<div class="td" data-id="' + esc(i.id) + '" draggable="' + PLAN_API + '" style="border-left-color:' + esc(i.color) + '">'
    + '<input type="checkbox" data-done="' + esc(i.id) + '" title="Done"' + (i.done ? ' checked' : '') + (PLAN_API ? '' : ' disabled') + '>'
    + '<div><div class="td-t">' + esc(i.title) + (KIND[i.kind] ? '<span class="td-k">' + KIND[i.kind] + '</span>' : '') + '</div>'
    + '<div class="td-d">' + dueText(i) + '</div></div></div>';
}
function renderTodo() {
  const items = planItems().filter(matches);
  const open = items.filter(isOpenTodo).sort((a, b) => dueMs(a) - dueMs(b));
  const past = items.filter(isPastOpen).sort((a, b) => dueMs(a) - dueMs(b));
  const quad = q => {
    const rows = open.filter(i => !!i.important === q.imp && !!i.urgent === q.urg);
    return '<div class="q ' + q.cls + '" data-imp="' + q.imp + '" data-urg="' + q.urg + '">'
      + '<div class="q-h"><b>' + q.name + '</b><span class="tier">' + q.sub + ' · ' + rows.length + '</span>'
      + (PLAN_API ? '<button class="q-add" title="Add here" data-add=\'' + esc(JSON.stringify({important: q.imp, urgent: q.urg})) + '\'>+</button>' : '') + '</div>'
      + (rows.length ? rows.map(card).join('') : '<div class="q-empty">nothing here</div>') + '</div>';
  };
  const el = document.getElementById('table');
  el.innerHTML = roBanner() + '<div class="pl-bar">' + addButton() + '<span class="pl-status" id="planStatus"></span></div>'
    + '<div class="mx"><div></div><div class="mx-h">Important</div><div class="mx-h">Not important</div>'
    + '<div class="mx-v">Urgent</div>' + quad(QUADS[0]) + quad(QUADS[1])
    + '<div class="mx-v">Not urgent</div>' + quad(QUADS[2]) + quad(QUADS[3]) + '</div>'
    + (past.length ? '<details class="past"><summary>' + past.length + ' item(s) of yours are past their date and still open — tick them done or move them</summary>'
      + past.map(card).join('') + '</details>' : '')
    + '<p class="note">Open items whose date is today or later; a span stays while it is in progress. Done items and the past live on the Timeline. '
    + (PLAN_API ? 'Drag a card to another square to re-flag it; tick it when it is done.' : '') + '</p>';
  showStatus();
  bindAdd(el);
  el.querySelectorAll('.td').forEach(c => c.onclick = e => {
    if (e.target.matches('input')) return;
    const it = findItem(c.dataset.id); if (it) openEditor(it, false);
  });
  el.querySelectorAll('[data-done]').forEach(b => b.onchange = () => {
    const it = findItem(b.dataset.done); if (!it) return;
    it.done = b.checked; putItem(it); savePlan(b.checked ? 'done — still on the Timeline' : 'reopened');
  });
  if (!PLAN_API) return;
  el.querySelectorAll('.td').forEach(c => c.ondragstart = e => e.dataTransfer.setData('text/plain', c.dataset.id));
  el.querySelectorAll('.q').forEach(q => {
    q.ondragover = e => { e.preventDefault(); q.classList.add('over'); };
    q.ondragleave = () => q.classList.remove('over');
    q.ondrop = e => {
      e.preventDefault(); q.classList.remove('over');
      const it = findItem(e.dataTransfer.getData('text/plain')); if (!it) return;
      const imp = q.dataset.imp === 'true', urg = q.dataset.urg === 'true';
      if (!!it.important === imp && !!it.urgent === urg) return;
      it.important = imp; it.urgent = urg; putItem(it); savePlan('moved');
    };
  });
}
function bindAdd(el) {
  el.querySelectorAll('[data-add]').forEach(b => b.onclick = e => {
    e.stopPropagation();
    openEditor(newItem(JSON.parse(b.dataset.add || '{}')), true);
  });
}
