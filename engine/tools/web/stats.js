// Statistics tab: the vault's numbers and the search telemetry, as charts. Hand-built SVG, because
// the dashboard is one self-contained file with no dependencies. Data comes from dashboard.py
// (DATA.vault, DATA.telemetry), which takes the telemetry from log_run.py and the latest
// analyze_misses.py report rather than re-deriving it, so this tab and `log_run.py --stats` agree.
//
// Mark specs follow the data-viz reference: bars <= 24px with a 4px rounded data-end and a square
// baseline, 2px surface gap between touching fills, >= 8px dots with a 2px surface ring, hairline
// solid gridlines, a legend for every chart with two or more series, text in ink tokens only, a
// hover/focus tooltip on every mark, and a data table under every chart.
const VZ_NS = 'http://www.w3.org/2000/svg';
const VZ_SERIES = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)'];
// The user's name for domain_fit (user/settings.toml [domain_fit] label), e.g. 'Protein'.
const VZ_LABEL = DATA.label || 'Domain', VZ_FIT = VZ_LABEL + ' fit';
const VZ_CAUSE = {
  SOURCE_INCOMPLETE: 'Searched, not returned', CHANNEL_SKIPPED: 'Channel skipped',
  QUERY_GAP: 'No query matched', AGE_EXCLUDED: 'Older than the window',
  CHANNEL_NOT_RUN: 'Channel not run', CHANNEL_FAILED: 'Channel failed', GEO_GAP: 'Country not searched',
  GATED_OUT: 'Seen, rejected by a gate', UNTIERED: 'Sweep returned it untiered',
  UNSCREENED: 'Sweep printed it, not screened',
};

function vzEl(tag, attrs, parent) {
  const n = document.createElementNS(VZ_NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
function vzText(parent, x, y, s, attrs) {
  const t = vzEl('text', Object.assign({x: x, y: y}, attrs || {}), parent);
  t.textContent = s;
  return t;
}
function vzFmt(n) { return (+n).toLocaleString('en-US'); }

// A bar with a 4px rounded data-end and a square baseline. Horizontal bars grow right from x;
// columns grow up from the baseline at y+h.
function vzBar(parent, x, y, w, h, fill, horizontal) {
  if (w <= 0 || h <= 0) return vzEl('rect', {x: x, y: y, width: 0, height: 0}, parent);
  const r = Math.min(4, horizontal ? w : h, horizontal ? h / 2 : w / 2);
  const d = horizontal
    ? `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`
    : `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  return vzEl('path', {d: d, style: 'fill:' + fill}, parent);
}

// One tooltip for the whole tab. Built with textContent only: record names are data.
function vzTip() {
  let t = document.getElementById('vz-tip');
  if (!t) { t = document.createElement('div'); t.id = 'vz-tip'; document.body.appendChild(t); }
  return t;
}
function vzHover(node, title, rows) {
  node.setAttribute('class', 'vz-mark');
  node.setAttribute('tabindex', '0');
  node.setAttribute('aria-label', title + ': ' + rows.map(r => r.value + ' ' + r.label).join(', '));
  const show = (x, y) => {
    const t = vzTip();
    t.replaceChildren();
    const h = document.createElement('div'); h.className = 'vz-tt'; h.textContent = title; t.appendChild(h);
    rows.forEach(r => {
      const row = document.createElement('div'); row.className = 'vz-tr';
      if (r.color) { const i = document.createElement('i'); i.style.background = r.color; row.appendChild(i); }
      const b = document.createElement('b'); b.textContent = r.value; row.appendChild(b);
      const s = document.createElement('span'); s.textContent = r.label; row.appendChild(s);
      t.appendChild(row);
    });
    t.style.display = 'block';
    const w = t.offsetWidth, hh = t.offsetHeight;
    t.style.left = Math.min(x + 14, window.innerWidth - w - 8) + 'px';
    t.style.top = Math.max(8, y - hh - 10) + 'px';
  };
  const hide = () => { vzTip().style.display = 'none'; };
  node.addEventListener('pointermove', e => show(e.clientX, e.clientY));
  node.addEventListener('pointerleave', hide);
  node.addEventListener('focus', () => { const b = node.getBoundingClientRect(); show(b.right, b.top); });
  node.addEventListener('blur', hide);
}

function vzLegend(card, series) {
  if (series.length < 2) return;                  // one series: the title names it
  const l = document.createElement('div'); l.className = 'vz-legend';
  series.forEach(s => {
    const sp = document.createElement('span'); const i = document.createElement('i');
    i.style.background = s.color; sp.appendChild(i); sp.appendChild(document.createTextNode(s.name));
    l.appendChild(sp);
  });
  card.appendChild(l);
}
function vzTable(card, head, rows) {
  const d = document.createElement('details'); const s = document.createElement('summary');
  s.textContent = 'Show data'; d.appendChild(s);
  const t = document.createElement('table'); t.className = 'vz-table';
  const tr = document.createElement('tr');
  head.forEach(h => { const th = document.createElement('th'); th.textContent = h; tr.appendChild(th); });
  const thead = document.createElement('thead'); thead.appendChild(tr); t.appendChild(thead);
  const tb = document.createElement('tbody');
  rows.forEach(r => {
    const row = document.createElement('tr');
    r.forEach(c => { const td = document.createElement('td'); td.textContent = c; row.appendChild(td); });
    tb.appendChild(row);
  });
  t.appendChild(tb); d.appendChild(t); card.appendChild(d);
}
function vzCard(grid, title, sub) {
  const c = document.createElement('div'); c.className = 'vz-card';
  const h = document.createElement('h3'); h.textContent = title; c.appendChild(h);
  if (sub) { const p = document.createElement('p'); p.className = 'vz-sub'; p.textContent = sub; c.appendChild(p); }
  grid.appendChild(c);
  return c;
}
function vzEmpty(card, msg) {
  const p = document.createElement('p'); p.className = 'vz-empty'; p.textContent = msg; card.appendChild(p);
}
function vzWidth(card) { return Math.max(320, card.clientWidth - 32); }
function vzTicks(max, n) {
  const raw = max / (n || 4), mag = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || raw;
  const out = []; for (let v = 0; v <= max + 1e-9; v += step) out.push(+v.toFixed(6));
  if (out[out.length - 1] < max) out.push(+(out[out.length - 1] + step).toFixed(6));
  return out;
}

// Horizontal bars: one series, or two grouped side by side. items: {label, values:[...], tip}
function vzHBars(card, items, series, opts) {
  opts = opts || {};
  vzLegend(card, series);
  const W = vzWidth(card), labelW = opts.labelW || 170, valW = 54;
  const k = series.length, barH = k > 1 ? 11 : 16, gap = 2, rowH = k * barH + (k - 1) * gap + 12;
  const H = items.length * rowH + 22;
  const max = opts.max || Math.max(1, ...items.flatMap(i => i.values));
  const ticks = vzTicks(max, 4), top = ticks[ticks.length - 1];
  const plotW = W - labelW - valW, sx = v => labelW + (v / top) * plotW;
  const svg = vzEl('svg', {viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': card.firstChild.textContent});
  ticks.forEach(t => {
    vzEl('line', {x1: sx(t), x2: sx(t), y1: 0, y2: H - 18, style: 'stroke:var(--vz-grid);stroke-width:1'}, svg);
    vzText(svg, sx(t), H - 4, (opts.fmt || vzFmt)(t), {'text-anchor': 'middle'});
  });
  vzEl('line', {x1: labelW, x2: labelW, y1: 0, y2: H - 18, style: 'stroke:var(--vz-base);stroke-width:1'}, svg);
  items.forEach((it, i) => {
    const y0 = i * rowH + 6;
    vzText(svg, labelW - 8, y0 + (rowH - 12) / 2 + 4, it.label, {'text-anchor': 'end'});
    const g = vzEl('g', {}, svg);
    it.values.forEach((v, j) => {
      const y = y0 + j * (barH + gap);
      vzBar(g, labelW, y, sx(v) - labelW, barH, series[j].color, true);
      vzText(g, sx(v) + 6, y + barH / 2 + 4, (opts.fmt || vzFmt)(v), {class: 'vz-val'});
    });
    // The hit target is the whole row, bigger than the bars.
    const hit = vzEl('rect', {x: 0, y: y0 - 3, width: W, height: rowH - 6, style: 'fill:transparent'}, g);
    vzHover(hit, it.tip || it.label, it.values.map((v, j) => ({
      value: (opts.fmt || vzFmt)(v) + (it.extra && it.extra[j] ? ' ' + it.extra[j] : ''),
      label: series[j].name, color: series[j].color})));
  });
  card.appendChild(svg);
}

// Columns along an ordered axis; segments stack bottom-up with a 2px surface gap.
// items: {label, tick, segs:[values per series], tip, rows}
function vzCols(card, items, series, opts) {
  opts = opts || {};
  vzLegend(card, series);
  const W = vzWidth(card), H = opts.height || 190, left = 34, bottom = 22, top = 8;
  const max = Math.max(1, ...items.map(i => i.segs.reduce((a, b) => a + b, 0)));
  const ticks = vzTicks(max, 4), yMax = ticks[ticks.length - 1];
  const plotH = H - bottom - top, sy = v => top + plotH - (v / yMax) * plotH;
  const slot = (W - left) / Math.max(1, items.length), colW = Math.min(24, Math.max(3, slot - 2));
  const svg = vzEl('svg', {viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': card.firstChild.textContent});
  ticks.forEach(t => {
    vzEl('line', {x1: left, x2: W, y1: sy(t), y2: sy(t), style: 'stroke:var(--vz-grid);stroke-width:1'}, svg);
    vzText(svg, left - 6, sy(t) + 4, vzFmt(t), {'text-anchor': 'end'});
  });
  vzEl('line', {x1: left, x2: W, y1: sy(0), y2: sy(0), style: 'stroke:var(--vz-base);stroke-width:1'}, svg);
  items.forEach((it, i) => {
    const x = left + i * slot + (slot - colW) / 2, g = vzEl('g', {}, svg);
    let acc = 0;
    const live = it.segs.map((v, j) => [v, j]).filter(([v]) => v > 0);
    live.forEach(([v, j], n) => {
      const y1 = sy(acc + v), y0 = sy(acc), last = n === live.length - 1;
      // Only the top segment gets the rounded data-end; lower ones stay square under a 2px gap.
      if (last) vzBar(g, x, y1, colW, y0 - y1 - (n ? 2 : 0), series[j].color, false);
      else vzEl('rect', {x: x, y: y1, width: colW, height: Math.max(0, y0 - y1 - (n ? 2 : 0)),
                         style: 'fill:' + series[j].color}, g);
      acc += v;
    });
    if (it.tick) vzText(svg, x + colW / 2, H - 6, it.tick, {'text-anchor': 'middle'});
    const hit = vzEl('rect', {x: left + i * slot, y: top, width: slot, height: plotH, style: 'fill:transparent'}, g);
    vzHover(hit, it.tip || it.label, it.rows || it.segs.map((v, j) => ({value: vzFmt(v), label: series[j].name,
                                                                         color: series[j].color})));
  });
  card.appendChild(svg);
}

// Domain fit (x) against skill match (y), one dot per live lead.
function vzScatter(card, pts, series, opts) {
  vzLegend(card, series);
  const W = vzWidth(card), H = Math.min(330, Math.round(W * 0.6)), left = 34, bottom = 30, top = 20, right = 10;
  const sx = v => left + (v / 100) * (W - left - right), sy = v => top + (1 - v / 100) * (H - top - bottom);
  const svg = vzEl('svg', {viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': card.firstChild.textContent});
  [0, 25, 50, 75, 100].forEach(t => {
    vzEl('line', {x1: sx(t), x2: sx(t), y1: top, y2: H - bottom, style: 'stroke:var(--vz-grid);stroke-width:1'}, svg);
    vzEl('line', {x1: left, x2: W - right, y1: sy(t), y2: sy(t), style: 'stroke:var(--vz-grid);stroke-width:1'}, svg);
    vzText(svg, sx(t), H - bottom + 14, String(t), {'text-anchor': 'middle'});
    vzText(svg, left - 6, sy(t) + 4, String(t), {'text-anchor': 'end'});
  });
  // The on-direction bar: right of it is work the user wants. A labelled hairline, not a dash.
  vzEl('line', {x1: sx(opts.onDirection), x2: sx(opts.onDirection), y1: top, y2: H - bottom,
                style: 'stroke:var(--vz-base);stroke-width:1'}, svg);
  vzText(svg, sx(opts.onDirection), 10, 'on-direction ≥ ' + opts.onDirection, {'text-anchor': 'middle'});
  vzText(svg, (left + W - right) / 2, H - 2, VZ_FIT + ' →', {'text-anchor': 'middle'});
  vzText(svg, left, 10, 'skill match ↑', {'text-anchor': 'middle'});
  pts.forEach(p => {
    const j = series.findIndex(s => s.key === p.cat);
    const c = vzEl('circle', {cx: sx(p.domain), cy: sy(p.skill), r: 4.5,
      style: 'fill:' + series[j].color + ';stroke:var(--vz-surface);stroke-width:2'}, svg);
    // A larger invisible ring makes the small dot easy to hit.
    const hit = vzEl('circle', {cx: sx(p.domain), cy: sy(p.skill), r: 9, style: 'fill:transparent'}, svg);
    vzHover(hit, p.name, [{value: p.domain, label: VZ_FIT, color: series[j].color},
                          {value: p.skill, label: 'skill match'}]);
    c.setAttribute('aria-hidden', 'true');
  });
  card.appendChild(svg);
}

function vzSection(root, title, lede) {
  const h = document.createElement('h2'); h.textContent = title; root.appendChild(h);
  if (lede) { const p = document.createElement('p'); p.className = 'vz-lede'; p.textContent = lede; root.appendChild(p); }
  const g = document.createElement('div'); g.className = 'vz-grid'; root.appendChild(g);
  return g;
}
function vzKpis(card, list) {
  const k = document.createElement('div'); k.className = 'vz-kpis';
  list.forEach(([n, l]) => {
    const d = document.createElement('div'); const b = document.createElement('b'); b.textContent = n;
    const s = document.createElement('span'); s.textContent = l; d.appendChild(b); d.appendChild(s); k.appendChild(d);
  });
  card.appendChild(k);
}

function renderStats() {
  const host = document.getElementById('table');
  host.replaceChildren();
  const root = document.createElement('div'); root.className = 'vz'; host.appendChild(root);
  const V = DATA.vault, T = DATA.telemetry || {}, one = [{name: '', color: VZ_SERIES[0]}];

  // ------------------------------------------------------------------ vault
  let g = vzSection(root, 'Vault', 'What the vault holds and how far applications have got. ' +
    'Counts are what the other tabs show: live leads reaching ' + S.min_fit_shown + ' on at least one score.');
  let c = vzCard(g, 'Application funnel', 'From everything the searches collected to offers. ' +
    S.rejections + ' rejection(s) on record.');
  vzHBars(c, V.funnel.map(([l, n]) => ({label: l, values: [n]})), one);
  vzTable(c, ['Stage', 'Count'], V.funnel.map(([l, n]) => [l, vzFmt(n)]));

  c = vzCard(g, 'Records by kind', 'Visible on the dashboard.' + (S.stale ? ' ⚠ ' + S.stale +
    ' lead(s) are past the ' + S.stale_days + '-day age limit and should already be retired: run expire_sweep.py.' : ''));
  vzHBars(c, V.kinds.map(([l, n]) => ({label: l, values: [n]})), one);
  vzTable(c, ['Kind', 'Count'], V.kinds.map(([l, n]) => [l, vzFmt(n)]));

  c = vzCard(g, 'Live leads: ' + VZ_FIT + ' against skill match',
    'Right of the line is the science you want; up is what you can already do. ' +
    'Top right is the shortlist, bottom right the stretches, top left the fallbacks.');
  const scS = [{key: 'position', name: 'Position', color: VZ_SERIES[0]}, {key: 'phd', name: 'PhD', color: VZ_SERIES[1]}];
  if (V.scatter.length) vzScatter(c, V.scatter, scS, {onDirection: S.on_direction});
  else vzEmpty(c, 'No live scored leads.');
  vzTable(c, ['Lead', 'Kind', VZ_LABEL, 'Skill'],
    V.scatter.slice().sort((a, b) => b.domain - a.domain).map(p => [p.name, p.cat, p.domain, p.skill]));

  c = vzCard(g, 'Leads collected per week', 'Position and PhD records by the week they were created ' +
    '(last 16 weeks), split by the search track that found them.');
  const wkS = [{name: 'Career track', color: VZ_SERIES[0]}, {name: 'Skill track', color: VZ_SERIES[1]}];
  if (V.weeks.length) vzCols(c, V.weeks.map((w, i) => ({
    label: 'Week of ' + w.week, tick: (i % 2 === 0 || V.weeks.length < 9) ? w.week.slice(5) : '',
    segs: [w.career, w.skill]})), wkS);
  else vzEmpty(c, 'No dated leads.');
  vzTable(c, ['Week of', 'Career track', 'Skill track'], V.weeks.map(w => [w.week, w.career, w.skill]));

  // ------------------------------------------------------------------ telemetry
  g = vzSection(root, 'Search telemetry', 'How the /search-positions runs perform and what they miss. ' +
    'A miss is a lead a later run found while it was already live during an earlier one.');
  if (T.error) { vzEmpty(vzCard(g, 'No telemetry'), T.error); return; }
  const M = T.misses;
  c = vzCard(g, 'At a glance', M ? 'Miss attribution from ' + M.file + ' (written ' + M.written +
    '). Re-run python engine/tools/analyze_misses.py to refresh it.' : 'No miss attribution report yet: run python engine/tools/analyze_misses.py.');
  vzKpis(c, [
    [vzFmt(T.n_runs), 'runs logged'],
    [T.n_deep + (T.deep_age != null ? ' · ' + T.deep_age + 'd ago' : ''), 'deep passes · last'],
    [T.li_hits ? (100 * T.li_short / T.li_hits).toFixed(1) + '%' : '—', 'LinkedIn hits shortlisted (' + vzFmt(T.li_short) + ' of ' + vzFmt(T.li_hits) + ')'],
    [M ? vzFmt(M.total) : '—', 'miss-events attributed'],
  ]);

  if (M) {
    c = vzCard(g, 'Why leads were missed', 'Share of miss-events by cause, over all leads and over strong leads ' +
      '(' + VZ_FIT + ' ≥ ' + M.threshold + ', ' + M.strong_leads + ' leads). Act on the strong-lead bars.');
    const causes = Object.keys(Object.assign({}, M.all, M.strong));
    const tA = Object.values(M.all).reduce((a, b) => a + b, 0) || 1;
    const tS = Object.values(M.strong).reduce((a, b) => a + b, 0) || 1;
    const rows = causes.map(k => ({code: k, a: 100 * (M.all[k] || 0) / tA, s: 100 * (M.strong[k] || 0) / tS,
                                   na: M.all[k] || 0, ns: M.strong[k] || 0}))
      .sort((x, y) => y.s - x.s || y.a - x.a);
    const pct = v => (+v).toFixed(v >= 10 || v === 0 ? 0 : 1) + '%';
    vzHBars(c, rows.map(r => ({label: VZ_CAUSE[r.code] || r.code, tip: r.code, values: [r.a, r.s],
      extra: ['(' + r.na + ')', '(' + r.ns + ')']})),
      [{name: 'All leads', color: VZ_SERIES[0]}, {name: 'Strong leads', color: VZ_SERIES[1]}],
      {fmt: pct, labelW: 190});
    vzTable(c, ['Cause', 'Code', 'All leads', 'Strong leads'],
      rows.map(r => [VZ_CAUSE[r.code] || r.code, r.code, r.na + ' (' + pct(r.a) + ')', r.ns + ' (' + pct(r.s) + ')']));
  }

  c = vzCard(g, 'Net-new leads per run', 'One column per logged run, oldest first; each track of a two-track ' +
    'run is its own column. Deep passes drop the age window and are meant to run weekly.');
  const rS = [{name: 'Fast pass', color: VZ_SERIES[0]}, {name: 'Deep pass', color: VZ_SERIES[1]}];
  let lastMonth = '';
  vzCols(c, T.runs.map(r => {
    const m = r.date.slice(0, 7), tick = m !== lastMonth ? r.date.slice(5, 7) + '/' + r.date.slice(2, 4) : '';
    lastMonth = m;
    const deep = r.mode === 'deep';
    return {label: r.id, tick: tick, segs: deep ? [0, r.new] : [r.new, 0],
      tip: r.id + ' · ' + r.mode + ' · ' + r.cfg,
      rows: [{value: r.new, label: 'net-new leads', color: deep ? VZ_SERIES[1] : VZ_SERIES[0]},
             {value: r.strong, label: 'strong (' + VZ_FIT + ' ≥ ' + T.strong_fit + ')'},
             {value: r.screened, label: 'screened and rejected'},
             {value: r.mins == null ? '—' : r.mins + ' min', label: 'runtime'}]};
  }), rS, {height: 200});
  vzTable(c, ['Run', 'Mode', 'Model/effort', 'Net-new', 'Strong', 'Screened', 'Minutes'],
    T.runs.map(r => [r.id, r.mode, r.cfg, r.new, r.strong, r.screened, r.mins == null ? '—' : r.mins]));

  c = vzCard(g, 'What each channel found', 'Net-new leads per channel and how many became strong ' +
    '(' + VZ_FIT + ' ≥ ' + T.strong_fit + '). Each vault record is credited once.');
  const ch = Object.entries(T.channels).sort((a, b) => b[1].new - a[1].new);
  vzHBars(c, ch.map(([k, v]) => ({label: k, values: [v.new, v.strong]})),
    [{name: 'Net-new', color: VZ_SERIES[0]}, {name: 'Strong', color: VZ_SERIES[1]}], {labelW: 130});
  vzTable(c, ['Channel', 'Net-new', 'Strong', 'Strong rate'],
    ch.map(([k, v]) => [k, v.new, v.strong, v.new ? Math.round(100 * v.strong / v.new) + '%' : '—']));

  c = vzCard(g, 'Channel coverage', 'Of the runs that listed each channel, how many reached it, skipped it ' +
    'for budget, or failed. Skipped is not "found nothing".');
  const cv = Object.entries(T.coverage).sort((a, b) => (b[1].skipped + b[1].failed) - (a[1].skipped + a[1].failed));
  const cvS = [{name: 'Reached', color: VZ_SERIES[0]}, {name: 'Skipped', color: VZ_SERIES[1]},
               {name: 'Failed', color: VZ_SERIES[2]}];
  vzStack100(c, cv.map(([k, v]) => ({label: k, values: [v.reached, v.skipped, v.failed]})), cvS);
  vzTable(c, ['Channel', 'Reached', 'Skipped', 'Failed'], cv.map(([k, v]) => [k, v.reached, v.skipped, v.failed]));

  c = vzCard(g, 'Why candidates were rejected', 'Screening rejections by reason code, every run. ' +
    'dedup is the vault recognising a lead it already has.');
  vzHBars(c, T.reasons.map(([k, n]) => ({label: k, values: [n]})), one, {labelW: 110});
  vzTable(c, ['Reason', 'Rejections'], T.reasons.map(([k, n]) => [k, n]));

  if (M && M.lags.length) {
    const bins = [[0, 3], [4, 7], [8, 14], [15, 21], [22, 30], [31, 60], [61, 90], [91, 1e9]];
    const counts = bins.map(([a, b]) => M.lags.filter(v => v >= a && v <= b).length);
    const sorted = M.lags.slice().sort((a, b) => a - b), med = sorted[Math.floor(sorted.length / 2)];
    c = vzCard(g, 'Days from posting to discovery', 'For the ' + M.lags.length + ' dated leads. Median ' +
      med + ' days; the fast pass reads LinkedIn 21 days back, so the bins past 21 are what deep passes recover.');
    const lab = ([a, b]) => b > 1e8 ? a + '+' : a + '–' + b;
    vzCols(c, bins.map((bn, i) => ({label: lab(bn) + ' days', tick: lab(bn), segs: [counts[i]]})),
      [{name: 'Leads', color: VZ_SERIES[0]}], {height: 170});
    vzTable(c, ['Days', 'Leads'], bins.map((bn, i) => [lab(bn), counts[i]]));
  }
}

// 100% stacked horizontal bars, one per item, segments separated by a 2px surface gap.
function vzStack100(card, items, series) {
  vzLegend(card, series);
  const W = vzWidth(card), labelW = 130, valW = 60, barH = 16, rowH = 28, H = items.length * rowH + 4;
  const plotW = W - labelW - valW;
  const svg = vzEl('svg', {viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': card.firstChild.textContent});
  items.forEach((it, i) => {
    const y = i * rowH + 6, tot = it.values.reduce((a, b) => a + b, 0) || 1, g = vzEl('g', {}, svg);
    vzText(svg, labelW - 8, y + barH / 2 + 4, it.label, {'text-anchor': 'end'});
    let x = labelW;
    const live = it.values.map((v, j) => [v, j]).filter(([v]) => v > 0);
    live.forEach(([v, j], n) => {
      const w = (v / tot) * plotW - (n < live.length - 1 ? 2 : 0);
      if (n === live.length - 1) vzBar(g, x, y, w, barH, series[j].color, true);
      else vzEl('rect', {x: x, y: y, width: Math.max(0, w), height: barH, style: 'fill:' + series[j].color}, g);
      x += w + 2;
    });
    vzText(svg, labelW + plotW + 6, y + barH / 2 + 4, it.values[0] + ' of ' + (tot), {class: 'vz-val'});
    const hit = vzEl('rect', {x: 0, y: y - 5, width: W, height: rowH - 2, style: 'fill:transparent'}, g);
    vzHover(hit, it.label, it.values.map((v, j) => ({value: v + ' (' + Math.round(100 * v / tot) + '%)',
                                                    label: series[j].name, color: series[j].color})));
  });
  card.appendChild(svg);
}

// Charts are sized to their card, so re-draw when the window changes width.
let vzResize;
window.addEventListener('resize', () => {
  clearTimeout(vzResize);
  vzResize = setTimeout(() => { if (typeof active !== 'undefined' && active === 'stats') renderStats(); }, 150);
});
