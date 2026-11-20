// Home: the OS-style entry page (replaced the Overview top-5 tables on 2026-11-20).
// Needs from dashboard.py: TABS, setTab, countFor, active, DATA.integrity, NAME, GEN_DATE.
const HOME_APPS = {
  stats:        {c:'#3b82f6,#6366f1', i:'<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'},
  timeline:     {c:'#06b6d4,#3b82f6', i:'<path d="M3 12h18"/><circle cx="7" cy="12" r="2"/><circle cx="14" cy="12" r="2"/><path d="M7 6v4M14 14v4M19 8v8"/>'},
  todo:         {c:'#f59e0b,#ef4444', i:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 9l2 2 4-4M8 16h8"/>'},
  applications: {c:'#a855f7,#ec4899', i:'<path d="M4 4h16v16H4z"/><path d="M4 8l8 6 8-6"/>'},
  company:      {c:'#10b981,#0ea5e9', i:'<path d="M3 21h18M5 21V7l7-4 7 4v14M9 10h2M13 10h2M9 14h2M13 14h2"/>'},
  group:        {c:'#14b8a6,#22c55e', i:'<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3"/><path d="M7 15h10"/>'},
  position:     {c:'#6366f1,#a855f7', i:'<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18"/>'},
  phd:          {c:'#f43f5e,#f59e0b', i:'<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c3 2 9 2 12 0v-5M22 9v6"/>'},
};
const HOME_LOGO = '<svg class="hm-logo" viewBox="0 0 400 400" aria-hidden="true"><defs>'
 +'<linearGradient id="hmg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#93c5fd"/>'
 +'<stop offset=".5" stop-color="#c4b5fd"/><stop offset="1" stop-color="#5eead4"/></linearGradient></defs>'
 +'<g fill="none" stroke="url(#hmg)">'
 +'<g class="ring1"><circle cx="200" cy="200" r="190" stroke-width="2" stroke-dasharray="4 10"/>'
 +'<circle cx="200" cy="200" r="172" stroke-width="14" stroke-dasharray="22 14"/></g>'
 +'<g class="ring2"><circle cx="200" cy="200" r="140" stroke-width="1.5"/>'
 +'<circle cx="200" cy="200" r="128" stroke-width="3" stroke-dasharray="60 20 6 20"/></g>'
 +'<path d="M200 92l94 54v108l-94 54-94-54V146z" stroke-width="3"/>'
 +'<path d="M160 120c80 40-80 120 0 160M240 120c-80 40 80 120 0 160" stroke-width="5"/>'
 +'<path d="M172 148h56M166 200h68M172 252h56" stroke-width="3"/></g></svg>';

function homeIcons() {
  return TABS.filter(t => HOME_APPS[t.id]).map(t => {
    const a = HOME_APPS[t.id], [c1, c2] = a.c.split(','), n = countFor(t.id);
    return '<button class="hm-app" onclick="setTab(\'' + t.id + '\')" title="Open ' + t.label + '">'
      + '<div class="hm-ico" style="background:linear-gradient(135deg,' + c1 + ',' + c2 + ')">'
      + '<svg viewBox="0 0 24 24">' + a.i + '</svg>'
      + (t.id !== 'stats' && n ? '<span class="hm-badge">' + n + '</span>' : '') + '</div>'
      + '<span class="lbl">' + t.label + '</span></button>';
  }).join('');
}
function homeTray() {
  const it = DATA.integrity || [];
  return it.length ? '<span style="color:#fbbf24">⚠ ' + it.length + ' issue' + (it.length > 1 ? 's' : '') + '</span>'
                   : '<span style="color:#4ade80">✓ all clear</span>';
}
function homeNotes() {
  const it = DATA.integrity || [];
  if (!it.length) return '<b style="color:#4ade80">Integrity check</b><div style="margin-top:6px;color:#aab3c8">No tracking inconsistencies found.</div>';
  return '<b style="color:#fbbf24">Integrity check — ' + it.length + ' issue(s)</b><ul>'
    + it.map(x => '<li><span class="tier">[' + x.kind + ']</span> <a href="' + x.path + '">' + x.msg + '</a></li>').join('') + '</ul>';
}
function toggleNotes(force) {
  const el = document.getElementById('hm-notes'); if (!el) return;
  el.classList.toggle('hidden', force === undefined ? !el.classList.contains('hidden') : !force);
}
function homeClock() {
  const el = document.getElementById('hm-clock'); if (!el) return;
  const d = new Date();
  el.innerHTML = d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})
    + '<small>' + d.toLocaleDateString([], {weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'}) + '</small>';
}
function renderHome() {
  let el = document.getElementById('desktop');
  if (!el) { el = document.createElement('div'); el.id = 'desktop'; document.body.prepend(el); }
  el.innerHTML = HOME_LOGO
    + '<div class="hm-top"><b>◆ Career Engine</b><span>' + (NAME ? NAME + ' · ' : '') + 'data from ' + GEN_DATE + '</span></div>'
    + '<div class="hm-main"><div class="hm-title"><h1>CAREER ENGINE</h1><p>applications · leads · plans</p></div>'
    + '<nav class="hm-apps" aria-label="Pages">' + homeIcons() + '</nav></div>'
    + '<div class="hm-notes hidden" id="hm-notes">' + homeNotes() + '</div>'
    + '<div class="hm-bar"><div class="hm-orb" title="Home"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2">'
    + '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M9 8c4 2-4 6 0 8M15 8c-4 2 4 6 0 8"/></svg></div>'
    + '<span class="sp"></span><button class="hm-tray" onclick="toggleNotes()" title="Integrity check">' + homeTray() + '</button>'
    + '<div class="hm-clock" id="hm-clock"></div></div>';
  homeClock();
}
setInterval(homeClock, 15000);
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && active !== 'home' && !document.querySelector('.pl-modal')) setTab('home');
  else if (e.key === 'Escape') toggleNotes(false);
});
