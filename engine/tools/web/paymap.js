// PhD pay map tab: a choropleth of Europe with one switchable measure, a hover card per country and
// a sortable table under the map. Data: DATA.paymap, read by dashboard.py from
// engine/data/phd_pay_europe.toml; outline: EU_GEO (europe_geo.js, generated from Natural Earth).
// Colour (the user's choice, 2026-11-21): red = bad, white = middle, green = good, on every
// measure. `good` says which end is good. White sits at the median country, except on Left over,
// where it sits at EUR 0: below that a month costs more than it pays. Red/green is hard for
// colour-blind readers, so the values stay in the hover card and the table.
const PM_METRICS = [
  {id: 'gross',  label: 'Gross pay',     good: 'high', sub: 'before tax and contributions, EUR/month'},
  {id: 'net',    label: 'Net pay',       good: 'high', sub: 'after income tax and social contributions, EUR/month'},
  {id: 'tax',    label: 'Tax',           good: 'low',  sub: 'share of gross taken as tax and contributions'},
  {id: 'ppp',    label: 'PPP',           good: 'high', sub: 'net pay in EU-average prices (net ÷ price level), EUR/month'},
  {id: 'rent',   label: 'Housing',       good: 'low',  sub: 'rent of a studio for one in the city, EUR/month'},
  {id: 'living', label: 'Living cost',   good: 'low',  sub: 'everything one person spends in a month, rent included, EUR'},
  {id: 'left',   label: 'Left over',     good: 'high', sub: 'net pay minus living cost: money left at the end of the month, EUR', zero: true},
];
const PM_BAD = '#e0453f', PM_MID = '#f4f4f2', PM_GOOD = '#1fa35b', PM_NODATA = '#1f232b';
let pmMetric = 'left', pmSortDir = -1, pmHover = null;
try { const m = localStorage.getItem('pmMetric'); if (PM_METRICS.some(x => x.id === m)) pmMetric = m; } catch (e) {}

function pmRows() {
  const pm = DATA.paymap || {};
  return (pm.country || []).map(c => Object.assign({}, c, {
    tax: c.gross ? Math.round((1 - c.net / c.gross) * 1000) / 10 : 0,
    ppp: c.pli ? Math.round(c.net / (c.pli / 100)) : null,
    left: c.net - c.living,
  }));
}
function pmFmt(id, v) {
  if (v == null) return '—';
  if (id === 'tax') return v.toFixed(1) + '%';
  return (v < 0 ? '−€' : '€') + Math.abs(Math.round(v)).toLocaleString('en-US');
}
function pmHex(h) { return [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)); }
function pmMix(a, b, t) {
  const x = pmHex(a), y = pmHex(b);
  return '#' + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, '0')).join('');
}
// Two arms around the midpoint, each stretched to its own extreme, so the best and the worst
// country are both full colour however lopsided the spread is.
function pmScale(rows, m) {
  const vals = rows.map(r => r[m.id]).filter(v => v != null).sort((a, b) => a - b);
  const lo = vals[0], hi = vals[vals.length - 1], n = vals.length;
  const mid = m.zero ? 0 : (n % 2 ? vals[(n - 1) / 2] : (vals[n / 2 - 1] + vals[n / 2]) / 2);
  const loC = m.good === 'high' ? PM_BAD : PM_GOOD, hiC = m.good === 'high' ? PM_GOOD : PM_BAD;
  return {min: lo, mid: mid, max: hi, lo: loC, hi: hiC, color: v => v < mid
    ? pmMix(PM_MID, loC, Math.min(1, (mid - v) / ((mid - lo) || 1)))
    : pmMix(PM_MID, hiC, Math.min(1, (v - mid) / ((hi - mid) || 1)))};
}

function renderPayMap() {
  const el = document.getElementById('table');
  const pm = DATA.paymap || {};
  if (pm.error) { el.innerHTML = '<div class="notice">' + pm.error + '</div>'; return; }
  const rows = pmRows(), m = PM_METRICS.find(x => x.id === pmMetric), sc = pmScale(rows, m);
  const by = {}; rows.forEach(r => by[r.iso] = r);
  const btns = PM_METRICS.map(x => '<button class="pm-btn' + (x.id === pmMetric ? ' on' : '') + '" onclick="pmSet(\'' + x.id + '\')">' + x.label + '</button>').join('');
  let shapes = '';
  (typeof EU_GEO !== 'undefined' ? EU_GEO.shapes : []).forEach(s => {
    const r = by[s.id];
    shapes += '<path d="' + s.d + '" data-iso="' + s.id + '" class="' + (r ? 'pm-c' : 'pm-x') + '" fill="'
      + (r ? sc.color(r[m.id]) : PM_NODATA) + '"' + (r ? ' tabindex="0" aria-label="' + r.name + ': ' + pmFmt(m.id, r[m.id]) + '"' : '') + '/>';
  });
  // The white stop sits where the midpoint falls in the value range, so the ramp reads like the map.
  const at = Math.round(Math.max(0, Math.min(1, (sc.mid - sc.min) / ((sc.max - sc.min) || 1))) * 100);
  const legend = '<div class="pm-legend"><span>' + pmFmt(m.id, sc.min) + '</span><span class="pm-ramp" style="background:linear-gradient(90deg,'
    + sc.lo + ' 0%,' + PM_MID + ' ' + at + '%,' + sc.hi + ' 100%)"></span><span>' + pmFmt(m.id, sc.max) + '</span>'
    + '<span class="pm-zero">white = ' + (m.zero ? '€0' : 'median ' + pmFmt(m.id, sc.mid)) + ' · '
    + (m.good === 'high' ? 'higher' : 'lower') + ' is better</span><span class="pm-nd"><i></i>no data</span></div>';
  const sorted = rows.slice().sort((a, b) => ((a[m.id] ?? -1e9) - (b[m.id] ?? -1e9)) * pmSortDir);
  const head = '<tr><th>#</th><th>Country</th>' + PM_METRICS.map(x => '<th class="num' + (x.id === pmMetric ? ' on' : '')
    + '" onclick="pmSet(\'' + x.id + '\',true)">' + x.label + (x.id === pmMetric ? (pmSortDir < 0 ? ' ▼' : ' ▲') : '') + '</th>').join('') + '<th>Conf.</th></tr>';
  const body = sorted.map((r, i) => '<tr data-iso="' + r.iso + '" onmouseenter="pmHi(\'' + r.iso + '\')" onmouseleave="pmHi(null)"><td class="tier">' + (i + 1)
    + '</td><td><b>' + r.name + '</b><div class="tier">' + r.city + '</div></td>'
    + PM_METRICS.map(x => '<td class="num' + (x.id === pmMetric ? ' on' : '') + '">' + pmFmt(x.id, r[x.id]) + '</td>').join('')
    + '<td class="tier">' + (r.confidence || '') + '</td></tr>').join('');
  el.innerHTML = '<div class="pm">'
    + '<h2>PhD pay across Europe</h2><p class="pm-lede">' + (pm.meta && pm.meta.basis || '') + ' Estimates as of '
    + (pm.meta && pm.meta.as_of || '?') + ', not an official dataset: edit <code>engine/data/phd_pay_europe.toml</code>.</p>'
    + '<div class="pm-btns" role="group" aria-label="Measure">' + btns + '</div>'
    + '<div class="pm-card"><h3>' + m.label + '</h3><p class="pm-sub">' + m.sub + '</p>' + legend
    + '<div class="pm-mapwrap"><svg class="pm-map" viewBox="0 0 ' + (EU_GEO ? EU_GEO.w + ' ' + EU_GEO.h : '0 0') + '" role="img" aria-label="Map of Europe coloured by ' + m.label + '">'
    + shapes + '</svg><div class="pm-tip hidden" id="pm-tip"></div></div></div>'
    + '<div class="pm-card"><h3>All countries, ranked by ' + m.label.toLowerCase() + '</h3><p class="pm-sub">Click a column to switch the map to it.</p>'
    + '<div class="pm-tablewrap"><table class="pm-table"><thead>' + head + '</thead><tbody>' + body + '</tbody></table></div></div></div>';
  const svg = el.querySelector('.pm-map');
  svg.addEventListener('mousemove', e => { const iso = e.target.dataset && e.target.dataset.iso; pmShowTip(by[iso], e); });
  svg.addEventListener('mouseleave', () => pmShowTip(null));
  svg.addEventListener('focusin', e => { const r = by[e.target.dataset.iso]; if (r) pmShowTip(r, null, e.target); });
  svg.addEventListener('focusout', () => pmShowTip(null));
  pmDots(svg, by);
}
// Luxembourg and Malta are a few pixels wide: give them a dot so they can be seen and hovered.
function pmDots(svg, by) {
  ['LU', 'MT'].forEach(iso => {
    const p = svg.querySelector('path[data-iso="' + iso + '"]'); if (!p || !by[iso]) return;
    const b = p.getBBox(), c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', b.x + b.width / 2); c.setAttribute('cy', b.y + b.height / 2); c.setAttribute('r', 6);
    c.setAttribute('fill', p.getAttribute('fill')); c.setAttribute('class', 'pm-c pm-dot'); c.dataset.iso = iso;
    svg.appendChild(c);
  });
}
function pmShowTip(r, e, target) {
  const tip = document.getElementById('pm-tip'); if (!tip) return;
  pmHi(r ? r.iso : null, true);
  if (!r) { tip.classList.add('hidden'); return; }
  tip.innerHTML = '<b>' + r.name + '</b> <span class="tier">' + r.city + '</span><table>'
    + PM_METRICS.map(x => '<tr class="' + (x.id === pmMetric ? 'on' : '') + '"><td>' + x.label + '</td><td>' + pmFmt(x.id, r[x.id]) + '</td></tr>').join('')
    + '<tr><td>Price level</td><td>' + (r.pli ?? '—') + ' <span class="tier">(EU = 100)</span></td></tr></table>'
    + (r.note ? '<div class="tier">' + r.note + '</div>' : '') + '<div class="tier">confidence: ' + (r.confidence || '?') + '</div>';
  tip.classList.remove('hidden');
  const box = tip.parentNode.getBoundingClientRect();
  let x, y;
  if (e) { x = e.clientX - box.left + 14; y = e.clientY - box.top + 14; }
  else { const t = target.getBoundingClientRect(); x = t.right - box.left + 8; y = t.top - box.top; }
  x = Math.min(x, box.width - tip.offsetWidth - 4); y = Math.min(y, box.height - tip.offsetHeight - 4);
  tip.style.left = Math.max(4, x) + 'px'; tip.style.top = Math.max(4, y) + 'px';
}
function pmHi(iso, fromMap) {
  if (pmHover === iso) return; pmHover = iso;
  document.querySelectorAll('.pm .hl').forEach(n => n.classList.remove('hl'));
  if (!iso) return;
  document.querySelectorAll('.pm [data-iso="' + iso + '"]').forEach(n => {
    n.classList.add('hl'); if (n.tagName === 'path' || n.tagName === 'circle') n.parentNode.appendChild(n);
  });
}
function pmSet(id, fromHeader) {
  if (fromHeader && id === pmMetric) pmSortDir *= -1; else pmSortDir = -1;
  pmMetric = id; pmHover = null;
  try { localStorage.setItem('pmMetric', id); } catch (e) {}
  renderPayMap();
}
