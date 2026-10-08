/* RivalRadar SPA */
'use strict';

/* ---------------------------------------------------------------- helpers */
const $ = (s, r = document) => r.querySelector(s);
const APP = { view: 'dashboard', arg: null, state: {}, polling: false };

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'html') e.innerHTML = v;
    else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
    else if (k === 'style') e.setAttribute('style', v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat(Infinity)) { if (k == null || k === false) continue; e.append(k.nodeType ? k : document.createTextNode(String(k))); }
  return e;
}
const frag = (...k) => { const f = document.createDocumentFragment(); k.flat(Infinity).forEach(x => x != null && x !== false && f.append(x.nodeType ? x : document.createTextNode(String(x)))); return f; };

const ICONS = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  radar: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12 19 5"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  cpu: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/>',
  link: '<path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
  settings: '<line x1="4" y1="7" x2="20" y2="7"/><circle cx="9" cy="7" r="2.5"/><line x1="4" y1="17" x2="20" y2="17"/><circle cx="15" cy="17" r="2.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  refresh: '<path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>',
  trash: '<path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m2 0v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V6"/>',
  external: '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><path d="M15 3h6v6M10 14 21 3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
  left: '<path d="M19 12H5M12 19l-7-7 7-7"/>',
  play: '<path d="M6 4v16l14-8z"/>',
  edit: '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4Z"/>',
  tag: '<path d="M20.6 13.4 12 22l-9-9V4a1 1 0 0 1 1-1h9Z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  server: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 8h.01M7 17h.01"/>',
  mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 6 10 7L22 6"/>',
  code: '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
  page: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
  pause: '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>',
};
function icon(name, size = 18, sw = 2) {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('width', size); s.setAttribute('height', size);
  s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor'); s.setAttribute('stroke-width', sw);
  s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round');
  s.innerHTML = ICONS[name] || ''; return s;
}

const CT = {
  new_page: { ic: 'plus', c: 'g', l: 'New page' }, removed_page: { ic: 'trash', c: 'r', l: 'Page removed' },
  content: { ic: 'edit', c: 'b', l: 'Content changed' }, title: { ic: 'tag', c: 'v', l: 'Title changed' },
  meta: { ic: 'tag', c: 'v', l: 'Meta changed' }, h1: { ic: 'tag', c: 'v', l: 'Headline changed' },
  status: { ic: 'alert', c: 'a', l: 'Status changed' }, tech_added: { ic: 'cpu', c: 's', l: 'Tech added' },
  tech_removed: { ic: 'cpu', c: 'a', l: 'Tech removed' }, price: { ic: 'tag', c: 'a', l: 'Price change' },
  sitemap: { ic: 'globe', c: 'b', l: 'Sitemap' }, promo: { ic: 'alert', c: 'r', l: 'Promotion' },
  keyword: { ic: 'search', c: 'v', l: 'Keyword alert' }, product: { ic: 'tag', c: 'g', l: 'Product' },
  article: { ic: 'page', c: 's', l: 'New article' },
};
const COLORVAR = { g: 'var(--green)', a: 'var(--amber)', r: 'var(--red)', b: 'var(--brand)', v: 'var(--violet)', s: 'var(--sky)' };

const fmt = n => (n == null ? '0' : Number(n).toLocaleString());
function timeAgo(ts) {
  if (!ts) return 'never'; const s = Date.now() / 1000 - ts;
  if (s < 60) return 'just now'; if (s < 3600) return Math.floor(s / 60) + 'm ago';
  if (s < 86400) return Math.floor(s / 3600) + 'h ago'; if (s < 2592000) return Math.floor(s / 86400) + 'd ago';
  return new Date(ts * 1000).toLocaleDateString();
}
const dt = ts => ts ? new Date(ts * 1000).toLocaleString() : '—';
function dur(ms) { if (!ms) return '0ms'; if (ms < 1000) return ms + 'ms'; return (ms / 1000).toFixed(1) + 's'; }
const esc = s => (s == null ? '' : String(s)).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const initials = s => (s || '?').trim().slice(0, 2).toUpperCase();

/* ---------------------------------------------------------------- api */
async function api(url, data) {
  const opt = {};
  if (data !== undefined) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(data)) { if (v == null) continue; if (Array.isArray(v)) v.forEach(x => fd.append(k, x)); else fd.append(k, String(v)); }
    opt.method = 'POST'; opt.body = fd;
  }
  let r; try { r = await fetch(url, opt); } catch (e) { return { ok: false, error: 'Cannot reach RivalRadar — is the app still running?' }; }
  let j; try { j = await r.json(); } catch (e) { j = { ok: r.ok, error: r.ok ? '' : 'Server error (' + r.status + ')' }; }
  if (!r.ok && j && typeof j === 'object' && j.ok === undefined) j.ok = false;
  return j;
}
const GET = u => api(u);
const POST = (u, d) => api(u, d || {});

/* ---------------------------------------------------------------- toast / modal */
function toast(msg, kind = 'ok', ms = 3200) {
  const t = h('div', { class: 'toast ' + kind }, msg); $('#toasts').append(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = '.3s'; setTimeout(() => t.remove(), 300); }, ms);
}
function modal({ title, icon: ic, body, footer, wide }) {
  const bg = h('div', { class: 'modal-bg', onclick: e => { if (e.target === bg) close(); } });
  const m = h('div', { class: 'modal' + (wide ? ' wide' : '') },
    h('div', { class: 'modal-h' }, ic ? icon(ic, 20) : null, h('h3', {}, title), h('span', { class: 'spacer' }),
      h('button', { class: 'icon-btn', onclick: () => close() }, icon('x', 18))),
    h('div', { class: 'modal-b' }, body), footer ? h('div', { class: 'modal-f' }, footer) : null);
  bg.append(m); $('#modal-root').append(bg);
  const onkey = e => { if (e.key === 'Escape') close(); };
  document.addEventListener('keydown', onkey);
  function close() { document.removeEventListener('keydown', onkey); bg.remove(); }
  return { close, el: m };
}
function confirmBox({ title, text, ok = 'Confirm', danger, typeText }) {
  return new Promise(res => {
    let input;
    const okBtn = btn(ok, { kind: danger ? 'danger' : 'primary', onclick: () => { if (typeText && (!input || input.value.trim() !== typeText)) return toast('Type ' + typeText + ' to confirm.', 'warn'); m.close(); res(true); } });
    if (typeText) { input = h('input', { placeholder: 'Type ' + typeText, oninput: () => okBtn.disabled = input.value.trim() !== typeText }); okBtn.disabled = true; }
    const m = modal({
      title, icon: danger ? 'alert' : 'check',
      body: h('div', {}, h('p', { style: 'margin:0 0 14px;color:var(--muted)' }, text), typeText ? input : null),
      footer: [btn('Cancel', { onclick: () => { m.close(); res(false); } }), h('span', { class: 'spacer' }), okBtn],
    });
  });
}
function btn(label, { kind, size, icon: ic, onclick, disabled } = {}) {
  const b = h('button', { class: 'btn' + (kind ? ' ' + kind : '') + (size ? ' ' + size : ''), type: 'button', disabled }, ic ? icon(ic, size === 'sm' ? 15 : 17) : null, label ? h('span', {}, label) : null);
  if (onclick) b.addEventListener('click', onclick); return b;
}
const pill = (t, c = '') => h('span', { class: 'pill ' + c }, t);
const banner = (kind, msg, acts) => h('div', { class: 'banner ' + kind }, icon(kind === 'ok' ? 'check' : kind === 'err' ? 'alert' : kind === 'warn' ? 'alert' : 'bell', 17), h('div', { style: 'flex:1' }, msg), acts ? h('div', { class: 'hstack' }, acts) : null);
function avatar(name, color, size = 42) { return h('div', { class: 'avatar', style: `width:${size}px;height:${size}px;background:${color || 'var(--brand)'}` }, initials(name)); }
function kpi(ic, color, bg, lab, num, foot) {
  return h('div', { class: 'kpi' }, h('div', { class: 'top-l' }, h('span', { class: 'lab' }, lab), h('span', { class: 'ic', style: `background:${bg};color:${color}` }, icon(ic, 17))),
    h('div', { class: 'num' }, num), foot ? h('div', { class: 'foot' }, foot) : null);
}
function card(title, sub, actions, bodyEl) {
  return h('div', { class: 'card' }, (title || actions) ? h('div', { class: 'card-h' }, title ? h('h3', {}, title) : null, sub ? h('span', { class: 'ch-sub' }, sub) : null, h('span', { class: 'spacer' }), actions || null) : null, bodyEl);
}
function emptyState(ic, title, text, action) {
  return h('div', { class: 'empty' }, h('div', { class: 'ic' }, icon(ic, 26)), h('h3', {}, title), h('p', {}, text), action ? h('div', { style: 'margin-top:16px' }, action) : null);
}
function statusPill(s) {
  return { ok: pill('OK', 'g'), new: pill('New', 'b'), scanning: h('span', { class: 'pill b' }, icon('refresh', 12), 'Scanning'), error: pill('Error', 'r'), paused: pill('Paused', 'a') }[s] || pill(s || '—');
}

/* ---------------------------------------------------------------- nav + shell */
const NAV = [
  { sec: 'Monitor' },
  { id: 'dashboard', ic: 'dashboard', label: 'Dashboard' },
  { id: 'competitors', ic: 'radar', label: 'Competitors' },
  { id: 'changes', ic: 'activity', label: 'Changes', badge: 'unseen' },
  { sec: 'Intel' },
  { id: 'tech', ic: 'cpu', label: 'Technology' },
  { id: 'compare', ic: 'dashboard', label: 'Compare' },
  { id: 'webhooks', ic: 'link', label: 'Alerts & webhooks' },
  { id: 'settings', ic: 'settings', label: 'Settings' },
];
function renderNav() {
  const unseen = (APP.state.competitors || []).reduce((a, c) => a + (c.unseen || 0), 0);
  $('#nav').replaceChildren(...NAV.map(n => {
    if (n.sec) return h('div', { class: 'nav-sec' }, n.sec);
    const badge = n.badge === 'unseen' && unseen ? h('span', { class: 'nb-badge' }, unseen > 99 ? '99+' : unseen) : null;
    return h('button', { class: 'nav-btn' + (APP.view === n.id ? ' on' : ''), type: 'button', onclick: () => go(n.id) }, icon(n.ic, 18), h('span', { style: 'flex:1' }, n.label), badge);
  }));
}
function setTop(...els) { $('#top-actions').replaceChildren(...els.filter(Boolean)); }
function toggleSide(v) { $('#side').classList.toggle('open', v); $('#backdrop').classList.toggle('show', v); }

/* ---------------------------------------------------------------- routing */
async function loadState() {
  const s = await GET('/api/state');
  if (s && !s.error) APP.state = s;
  $('#ver').textContent = 'v' + (APP.state.version || '1.0');
  renderNav();
  return APP.state;
}
function go(view, arg) {
  APP.view = view; APP.arg = arg;
  location.hash = view + (arg != null ? '/' + arg : '');
  toggleSide(false); render();
}
function parseHash() {
  const [v, a] = (location.hash.replace(/^#/, '') || 'dashboard').split('/');
  APP.view = v || 'dashboard'; APP.arg = a != null ? a : null;
}
const VIEWS = {};
async function render() {
  renderNav(); setTop();
  const fn = VIEWS[APP.view] || VIEWS.dashboard;
  try { await fn(APP.arg); } catch (e) { $('#view').replaceChildren(emptyState('alert', 'Something went wrong', String(e))); console.error(e); }
}

/* ---------------------------------------------------------------- live polling */
function startPolling() {
  if (APP.polling) return; APP.polling = true;
  const tick = async () => {
    const jobs = await GET('/api/jobs');
    const running = jobs && Object.keys(jobs).length;
    if (running) { await loadState(); if (['dashboard', 'competitors', 'competitor'].includes(APP.view)) render(); setTimeout(tick, 2200); }
    else { APP.polling = false; await loadState(); if (['dashboard', 'competitors', 'competitor'].includes(APP.view)) render(); }
  };
  setTimeout(tick, 1500);
}

/* ================================================================ DASHBOARD */
VIEWS.dashboard = async function () {
  $('#ttl').textContent = 'Dashboard'; $('#tsub').textContent = 'Everything your competitors changed, at a glance';
  setTop(btn('Scan all now', { kind: 'primary', icon: 'refresh', onclick: scanAll }));
  const v = $('#view'); v.replaceChildren(h('div', { class: 'muted' }, 'Loading…'));
  const d = await GET('/api/dashboard');
  const kps = h('div', { class: 'grid g4' },
    kpi('radar', 'var(--brand2)', 'var(--brand-l)', 'Competitors', fmt(d.competitors), `${fmt(d.active)} active`),
    kpi('page', 'var(--sky)', 'var(--sky-l)', 'Pages tracked', fmt(d.pages)),
    kpi('activity', 'var(--green-d)', 'var(--green-l)', 'Changes (7 days)', fmt(d.changes_7d), `${fmt(d.changes_24h)} in last 24h`),
    kpi('bell', 'var(--amber-d)', 'var(--amber-l)', 'Unseen changes', fmt(d.unseen), d.unseen ? 'needs your review' : 'all caught up'));

  const max = Math.max(1, ...d.series.map(x => x.n));
  const spark = h('div', { class: 'spark' }, d.series.map(x => h('div', { class: 'b', style: `height:${Math.max(3, x.n / max * 90)}px`, title: `${x.d}: ${x.n} changes` })));
  const types = Object.entries(d.by_type || {}).sort((a, b) => b[1] - a[1]);
  const totalT = types.reduce((a, [, n]) => a + n, 0) || 1;
  const breakdown = types.length ? types.map(([t, n]) => {
    const m = CT[t] || { l: t, c: 'b' };
    return h('div', { class: 'meter' }, h('div', { class: 'ml' }, h('span', {}, m.l), h('b', {}, fmt(n))), h('div', { class: 'pbar' }, h('div', { style: `width:${n / totalT * 100}%;background:${COLORVAR[m.c]}` })));
  }) : h('div', { class: 'muted small' }, 'No changes recorded in the last 30 days.');

  const recent = (d.recent || []).length ? h('div', { class: 'feed' }, d.recent.map(changeRow)) : emptyState('activity', 'No changes yet', 'Add a competitor and run a scan to start tracking.', btn('Add competitor', { kind: 'primary', icon: 'plus', onclick: addCompetitorModal }));

  v.replaceChildren(kps, h('div', { style: 'height:16px' }),
    h('div', { class: 'split' },
      card('Recent changes', 'Across all competitors', (d.recent || []).length ? btn('See all', { size: 'sm', onclick: () => go('changes') }) : null, h('div', { class: 'card-b' }, recent)),
      h('div', {},
        card('Activity · 14 days', null, null, h('div', { class: 'card-b' }, spark)),
        h('div', { style: 'height:16px' }),
        card('Change types · 30 days', null, null, h('div', { class: 'card-b' }, breakdown)))));
};

function changeRow(c) {
  const m = CT[c.type] || { ic: 'activity', c: 'b', l: c.type };
  return h('div', { class: 'feed-item', onclick: () => changeModal(c.id) },
    h('span', { class: 'feed-ic', style: `background:${COLORVAR[m.c]}22;color:${COLORVAR[m.c]}` }, icon(m.ic, 15)),
    h('div', { class: 'fi-main' },
      h('div', { class: 'hstack', style: 'gap:8px' }, h('span', { class: 'dot', style: `width:8px;height:8px;border-radius:50%;background:${c.comp_color || 'var(--brand)'}` }), h('b', { class: 'fi-t' }, c.comp_name), c.seen ? null : h('span', { class: 'pill b', style: 'padding:0 6px' }, 'new')),
      h('div', { class: 'fi-sub' }, c.summary)),
    h('span', { class: 'fi-when' }, timeAgo(c.ts)));
}

/* ================================================================ COMPETITORS */
VIEWS.competitors = async function () {
  $('#ttl').textContent = 'Competitors'; $('#tsub').textContent = 'The websites you are tracking';
  setTop(btn('Scan all', { icon: 'refresh', onclick: scanAll }), btn('Add competitor', { kind: 'primary', icon: 'plus', onclick: addCompetitorModal }));
  await loadState();
  const list = APP.state.competitors || [];
  const v = $('#view');
  if (!list.length) { v.replaceChildren(emptyState('radar', 'No competitors yet', 'Add a competitor website and RivalRadar will track every change they make.', btn('Add your first competitor', { kind: 'primary', icon: 'plus', onclick: addCompetitorModal }))); return; }
  v.replaceChildren(h('div', { class: 'comp-grid' }, list.map(compCard)));
};
function compCard(c) {
  const job = (APP.state.jobs || {})[c.id];
  const st = job ? 'scanning' : c.status;
  return h('div', { class: 'comp-card', onclick: () => go('competitor', c.id) },
    h('div', { class: 'bar', style: `background:${c.color}` }),
    h('div', { class: 'cc-top' }, avatar(c.name, c.color),
      h('div', { style: 'flex:1;min-width:0' }, h('h3', { class: 'ellipsis' }, c.name), h('div', { class: 'dom ellipsis' }, c.domain)),
      c.unseen ? h('span', { class: 'nb-badge', style: 'background:var(--red);color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:9px' }, c.unseen) : null),
    h('div', { class: 'comp-stats' },
      h('div', { class: 's' }, h('b', {}, fmt(c.pages)), h('span', {}, 'pages')),
      h('div', { class: 's' }, h('b', {}, fmt(c.changes7)), h('span', {}, 'changes/7d')),
      h('div', { class: 's' }, h('b', {}, fmt(c.tech_count)), h('span', {}, 'tech'))),
    h('div', { class: 'cc-foot' }, statusPill(st), h('span', { class: 'xs dim' }, 'Scanned ' + timeAgo(c.last_scan)), h('span', { class: 'spacer' }),
      btn('Scan', { size: 'sm', icon: 'refresh', onclick: e => { e.stopPropagation(); scanOne(c.id); } })));
}

async function scanOne(cid) {
  const r = await POST(`/api/competitors/${cid}/scan`);
  if (!r.ok) return toast(r.error || 'Could not start scan.', 'err');
  toast('Scan started…', 'ok'); await loadState(); render(); startPolling();
}
async function scanAll() {
  const r = await POST('/api/scan-all');
  if (!r.ok) return toast(r.error, 'err');
  toast(r.started ? `Scanning ${r.started} competitor(s)…` : 'Nothing to scan.', r.started ? 'ok' : 'info');
  await loadState(); render(); startPolling();
}

function addCompetitorModal() {
  const dom = h('input', { placeholder: 'competitor.com', autofocus: true });
  const name = h('input', { placeholder: 'Optional — defaults to the domain' });
  const iv = h('select', {}, [['0', 'Use default schedule'], ['60', 'Every hour'], ['360', 'Every 6 hours'], ['720', 'Every 12 hours'], ['1440', 'Daily'], ['10080', 'Weekly']].map(([v, l]) => h('option', { value: v }, l)));
  const notes = h('textarea', { placeholder: 'Notes (optional)' });
  const save = btn('Add & scan', { kind: 'primary', icon: 'plus', onclick: async () => {
    if (!dom.value.trim()) { dom.focus(); return toast('Enter a website address.', 'warn'); }
    save.disabled = true;
    const r = await POST('/api/competitors', { domain: dom.value, name: name.value, interval_min: iv.value, notes: notes.value, scan_now: '1' });
    if (!r.ok) { save.disabled = false; return toast(r.error, 'err'); }
    toast('Added — first scan running.', 'ok'); m.close(); await loadState(); go('competitor', r.id); startPolling();
  } });
  const m = modal({ title: 'Track a competitor', icon: 'radar', body: h('div', {},
    field('Website', dom, null, 'Just the domain — RivalRadar finds their pages automatically.'),
    field('Name', name), field('Check frequency', iv), field('Notes', notes)),
    footer: [btn('Cancel', { onclick: () => m.close() }), h('span', { class: 'spacer' }), save] });
  setTimeout(() => dom.focus(), 50);
}
function field(label, input, opt, hint) { return h('div', { class: 'fld' }, h('label', { class: 'f' }, label, opt ? h('span', { class: 'opt' }, ' · ' + opt) : null), input, hint ? h('div', { class: 'help', style: 'margin-top:6px' }, hint) : null); }

/* ================================================================ COMPETITOR DETAIL */
VIEWS.competitor = async function (cid) {
  const c = await GET('/api/competitors/' + cid);
  const v = $('#view');
  if (!c || c.error) { v.replaceChildren(emptyState('alert', 'Competitor not found', 'It may have been deleted.', btn('All competitors', { onclick: () => go('competitors') }))); return; }
  $('#ttl').textContent = c.name; $('#tsub').textContent = c.domain;
  const job = (APP.state.jobs || {})[c.id];
  setTop(btn('Visit site', { icon: 'external', onclick: () => window.open(c.base_url, '_blank') }),
    btn(job ? 'Scanning…' : 'Scan now', { kind: 'primary', icon: 'refresh', disabled: !!job, onclick: () => scanOne(c.id) }));

  const header = h('div', { class: 'hstack', style: 'margin-bottom:20px;flex-wrap:wrap' },
    avatar(c.name, c.color, 48), h('div', { style: 'flex:1;min-width:0' },
      h('div', { class: 'hstack' }, h('h2', { style: 'margin:0;font-size:20px' }, c.name), statusPill(job ? 'scanning' : c.status)),
      h('div', { class: 'small dim' }, c.domain + ' · scanned ' + timeAgo(c.last_scan) + (c.scan_error ? ' · ' + c.scan_error : ''))),
    btn('Settings', { size: 'sm', icon: 'settings', onclick: () => editCompetitorModal(c) }),
    btn('Delete', { size: 'sm', kind: 'danger', icon: 'trash', onclick: async () => {
      if (!await confirmBox({ title: 'Delete ' + c.name + '?', text: 'All tracked pages, snapshots, changes and tech for this competitor are removed.', ok: 'Delete', danger: true })) return;
      await POST(`/api/competitors/${cid}/delete`); toast('Deleted.'); go('competitors');
    } }));

  const tabs = ['Changes', 'Products & prices', 'Pages & watches', 'Technology', 'Intel', 'Articles', 'Scan log'];
  if (!tabs.includes(APP._ctab)) APP._ctab = 'Changes';
  const counts = { 'Products & prices': (c.products || []).filter(p => p.present).length, 'Articles': (c.feed || []).length };
  const tabBar = h('div', { class: 'tabs' }, tabs.map(t => h('button', { class: 'tab' + (APP._ctab === t ? ' on' : ''), onclick: () => { APP._ctab = t; renderTab(); } }, t, counts[t] ? h('span', { class: 'pill b', style: 'margin-left:6px;padding:0 6px' }, counts[t]) : null)));
  const body = h('div');
  function renderTab() {
    tabBar.querySelectorAll('.tab').forEach((b, i) => b.classList.toggle('on', tabs[i] === APP._ctab));
    const t = APP._ctab;
    if (t === 'Changes') body.replaceChildren(tabChanges(c));
    else if (t === 'Products & prices') body.replaceChildren(tabProducts(c));
    else if (t === 'Pages & watches') body.replaceChildren(tabPages(c));
    else if (t === 'Technology') body.replaceChildren(tabTech(c));
    else if (t === 'Intel') body.replaceChildren(tabIntel(c));
    else if (t === 'Articles') body.replaceChildren(tabArticles(c));
    else body.replaceChildren(tabScans(c));
  }
  renderTab();
  v.replaceChildren(header, tabBar, body);
};

function tabChanges(c) {
  if (!(c.changes || []).length) return emptyState('activity', 'No changes recorded', 'RivalRadar will list every change here after the next scans.');
  return h('div', {}, h('div', { class: 'hstack', style: 'margin-bottom:12px' }, h('span', { class: 'spacer' }),
    btn('Mark all seen', { size: 'sm', icon: 'check', onclick: async () => { await POST('/api/changes/seen', { competitor_id: c.id }); toast('Marked seen.'); go('competitor', c.id); } })),
    h('div', { class: 'feed' }, c.changes.map(changeRow)));
}
function tabPages(c) {
  const watches = c.pages.filter(p => p.kind === 'watch');
  const pages = c.pages.filter(p => p.kind !== 'watch');
  const row = p => h('tr', {},
    h('td', {}, h('a', { href: p.url, target: '_blank', class: 'ellipsis', style: 'max-width:340px;display:inline-block;vertical-align:bottom' }, p.url.replace(/^https?:\/\//, '')), p.label ? h('div', { class: 'xs dim' }, p.label) : null, p.selector ? h('span', { class: 'tag', style: 'margin-top:3px' }, p.selector) : null),
    h('td', {}, p.gone ? pill('Gone', 'r') : (p.last_status ? pill(p.last_status, p.last_status < 400 ? 'g' : 'a') : pill('—'))),
    h('td', { class: 'small dim' }, p.word_count ? fmt(p.word_count) + ' words' : '—'),
    h('td', { class: 'small dim nowrap' }, timeAgo(p.last_seen)),
    h('td', { class: 'nowrap', style: 'text-align:right' },
      btn('History', { size: 'sm', kind: 'quiet', icon: 'clock', onclick: () => pageHistoryModal(p.id) }),
      h('button', { class: 'icon-btn sm', title: 'Stop tracking', onclick: async () => { if (!await confirmBox({ title: 'Remove this page?', text: p.url, ok: 'Remove', danger: true })) return; await POST(`/api/pages/${p.id}/delete`); toast('Removed.'); go('competitor', c.id); } }, icon('trash', 15))));
  return h('div', {},
    card('Watched pages', 'Pick exact pages (and a CSS selector) to watch closely — e.g. a price block.',
      btn('Add watch', { size: 'sm', icon: 'plus', onclick: () => addWatchModal(c) }),
      h('div', {}, watches.length ? h('div', { class: 'tbl-wrap' }, h('table', { class: 't' }, h('thead', {}, h('tr', {}, h('th', {}, 'Page'), h('th', {}, 'Status'), h('th', {}, 'Size'), h('th', {}, 'Checked'), h('th', {}, ''))), h('tbody', {}, watches.map(row)))) : h('div', { class: 'card-b muted small' }, 'No manual watches yet. Add one to track a specific price or section.'))),
    h('div', { style: 'height:16px' }),
    card('Discovered pages', `${pages.length} page(s) found from their sitemap`, null,
      h('div', {}, pages.length ? h('div', { class: 'tbl-wrap', style: 'max-height:500px' }, h('table', { class: 't' }, h('thead', {}, h('tr', {}, h('th', {}, 'Page'), h('th', {}, 'Status'), h('th', {}, 'Size'), h('th', {}, 'Checked'), h('th', {}, ''))), h('tbody', {}, pages.map(row)))) : h('div', { class: 'card-b muted small' }, 'No pages discovered yet — run a scan.'))));
}
function tabTech(c) {
  if (!(c.tech || []).length) return emptyState('cpu', 'No technology detected yet', 'Run a scan to detect their stack.');
  const present = c.tech.filter(t => t.present), gone = c.tech.filter(t => !t.present);
  const byCat = {}; present.forEach(t => (byCat[t.category || 'Other'] ||= []).push(t));
  const cards = Object.entries(byCat).map(([cat, items]) =>
    card(cat, null, null, h('div', { class: 'card-b hstack', style: 'flex-wrap:wrap;gap:8px' }, items.map(t => h('span', { class: 'chip' }, icon('cpu', 13), t.name)))));
  return h('div', { class: 'grid', style: 'gap:16px' }, ...cards,
    gone.length ? card('No longer detected', null, null, h('div', { class: 'card-b hstack', style: 'flex-wrap:wrap;gap:8px' }, gone.map(t => h('span', { class: 'chip', style: 'opacity:.55' }, t.name)))) : null);
}
function tabScans(c) {
  if (!(c.scans || []).length) return emptyState('clock', 'No scans yet', 'Run a scan to see the log.');
  return h('div', { class: 'tbl-wrap' }, h('table', { class: 't' }, h('thead', {}, h('tr', {}, h('th', {}, 'When'), h('th', {}, 'Result'), h('th', { class: 'num' }, 'Pages'), h('th', { class: 'num' }, 'Changes'), h('th', { class: 'num' }, 'Took'))),
    h('tbody', {}, c.scans.map(s => h('tr', {}, h('td', { class: 'small' }, dt(s.ts)), h('td', {}, s.status === 'ok' ? pill('OK', 'g') : h('span', {}, pill('Error', 'r'), s.error ? h('div', { class: 'xs dim', style: 'max-width:360px' }, s.error) : null)), h('td', { class: 'num' }, fmt(s.pages_checked)), h('td', { class: 'num' }, fmt(s.changes_found)), h('td', { class: 'num small dim' }, dur(s.duration_ms)))))));
}

function tabProducts(c) {
  const prods = (c.products || []);
  if (!prods.length) return emptyState('tag', 'No products detected yet', 'RivalRadar reads prices & ratings from the structured data (schema.org) on their pages. If they publish it, products appear here after a scan.');
  const present = prods.filter(p => p.present), gone = prods.filter(p => !p.present);
  const row = p => h('tr', { style: p.present ? '' : 'opacity:.5' },
    h('td', {}, h('b', {}, p.name), h('div', { class: 'xs dim ellipsis', style: 'max-width:280px' }, p.url.replace(/^https?:\/\//, ''))),
    h('td', { class: 'num' }, p.price ? h('b', {}, (p.currency || '') + p.price) : '—'),
    h('td', {}, p.rating ? h('span', { class: 'pill a' }, '★ ' + p.rating + (p.review_count ? ' (' + fmt(p.review_count) + ')' : '')) : '—'),
    h('td', {}, p.availability ? pill(p.availability, p.availability.toLowerCase().includes('instock') ? 'g' : 'a') : '—'),
    h('td', { class: 'nowrap', style: 'text-align:right' }, btn('Price history', { size: 'sm', kind: 'quiet', icon: 'activity', onclick: () => priceHistoryModal(p) })));
  return h('div', {}, card('Products & prices', `${present.length} tracked · prices update every scan`, null,
    h('div', { class: 'tbl-wrap' }, h('table', { class: 't' }, h('thead', {}, h('tr', {}, h('th', {}, 'Product'), h('th', { class: 'num' }, 'Price'), h('th', {}, 'Rating'), h('th', {}, 'Stock'), h('th', {}, ''))),
      h('tbody', {}, [...present, ...gone].map(row))))));
}
async function priceHistoryModal(p) {
  const d = await GET(`/api/products/${p.id}/history`);
  const hist = d.history || [];
  let chart;
  if (hist.length < 2) chart = h('div', { class: 'muted small' }, 'Not enough price points yet — history builds up as prices change over scans.');
  else {
    const vals = hist.map(x => x.price), min = Math.min(...vals), max = Math.max(...vals), range = max - min || 1;
    const W = 460, H = 150, pad = 10;
    const pts = hist.map((x, i) => [pad + i / (hist.length - 1) * (W - 2 * pad), H - pad - (x.price - min) / range * (H - 2 * pad)]);
    const path = pts.map((pt, i) => (i ? 'L' : 'M') + pt[0].toFixed(1) + ',' + pt[1].toFixed(1)).join(' ');
    const svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" style="overflow:visible"><path d="${path}" fill="none" stroke="var(--brand)" stroke-width="2.5" stroke-linejoin="round"/>${pts.map(pt => `<circle cx="${pt[0].toFixed(1)}" cy="${pt[1].toFixed(1)}" r="3" fill="var(--brand)"/>`).join('')}</svg>`;
    chart = h('div', {}, h('div', { class: 'hstack', style: 'justify-content:space-between;margin-bottom:8px' }, pill('Low ' + (p.currency || '') + min, 'g'), pill('High ' + (p.currency || '') + max, 'r')), h('div', { html: svg }));
  }
  const rows = hist.slice().reverse().slice(0, 20).map(x => h('tr', {}, h('td', { class: 'small' }, dt(x.ts)), h('td', { class: 'num' }, (x.currency || '') + x.price)));
  modal({ title: p.name, icon: 'tag', wide: true, body: h('div', {}, h('div', { class: 'mb' }, chart),
    hist.length ? h('div', { class: 'tbl-wrap' }, h('table', { class: 't' }, h('thead', {}, h('tr', {}, h('th', {}, 'When'), h('th', { class: 'num' }, 'Price'))), h('tbody', {}, rows))) : null) });
}

function tabIntel(c) {
  const d = c.intel || {};
  const sec = d.security || {}, ssl = d.ssl || {}, dom = d.domain || {}, seo = d.seo || {}, contacts = d.contacts || {};
  const kv = (label, val) => h('div', { class: 'hstack', style: 'justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--line)' }, h('span', { class: 'muted small' }, label), h('b', { class: 'small' }, val));
  const socials = contacts.socials || {};
  const contactCard = card('Contacts & social', null, null, h('div', { class: 'card-b' },
    Object.keys(socials).length ? h('div', { class: 'hstack', style: 'flex-wrap:wrap;margin-bottom:10px' }, Object.entries(socials).map(([k, u]) => h('a', { class: 'chip', href: u, target: '_blank' }, k))) : null,
    (contacts.emails || []).length ? h('div', { class: 'small', style: 'margin-bottom:6px' }, icon('mail', 13), ' ' + contacts.emails.join(', ')) : null,
    (contacts.phones || []).length ? h('div', { class: 'small' }, '📞 ' + contacts.phones.join(', ')) : null,
    !Object.keys(socials).length && !(contacts.emails || []).length && !(contacts.phones || []).length ? h('div', { class: 'muted small' }, 'Nothing public found yet.') : null));
  const trustCard = card('Trust & tech', null, null, h('div', { class: 'card-b' },
    kv('Security headers', h('span', {}, pill(sec.grade || '—', sec.grade === 'A' || sec.grade === 'B' ? 'g' : sec.grade === 'C' ? 'a' : 'r'), ' ' + (sec.score != null ? sec.score + '%' : ''))),
    kv('SSL certificate', ssl.ok ? (ssl.days_left + ' days left' + (ssl.issuer ? ' · ' + ssl.issuer : '')) : '—'),
    kv('Domain age', dom.ok && dom.age_days != null ? Math.floor(dom.age_days / 365) + 'y ' + (dom.age_days % 365) + 'd' + (dom.registrar ? ' · ' + dom.registrar : '') : '—'),
    kv('Pages tracked', fmt(d.page_count || 0))));
  const promo = d.promo || {};
  const promoCard = card('Promotions', null, null, h('div', { class: 'card-b' },
    promo.active ? h('div', {}, banner('warn', 'Running a promotion right now'), h('div', { class: 'hstack', style: 'flex-wrap:wrap;margin-top:10px' }, (promo.terms || []).map(t => pill(t, 'r')), (promo.coupons || []).map(cp => h('span', { class: 'tag' }, cp)))) : h('div', { class: 'muted small' }, 'No active promotions detected.')));
  const seoCard = card('SEO (homepage)', seo.score != null ? 'Score ' + seo.score + '/100' : null, null, h('div', { class: 'card-b' },
    (seo.issues || []).length ? h('div', {}, seo.issues.map(([sev, msg]) => h('div', { class: 'hstack', style: 'padding:5px 0' }, pill(sev, sev === 'error' ? 'r' : sev === 'warn' ? 'a' : ''), h('span', { class: 'small' }, msg)))) : h('div', { class: 'ok small' }, 'No major issues.')));
  const focus = d.keyword_focus || [];
  const focusCard = card('Keyword focus', 'The terms they use most', null, h('div', { class: 'card-b hstack', style: 'flex-wrap:wrap;gap:7px' }, focus.length ? focus.slice(0, 24).map(k => h('span', { class: 'chip' }, k.term, h('b', { class: 'dim', style: 'margin-left:4px' }, k.n))) : h('span', { class: 'muted small' }, 'Run a scan to build this.')));
  const broken = d.broken || [];
  const brokenCard = broken.length ? card('Broken pages', broken.length + ' found', null, h('div', { class: 'card-b' }, broken.slice(0, 20).map(b => h('div', { class: 'hstack small', style: 'padding:4px 0' }, pill(b.status, 'r'), h('span', { class: 'ellipsis' }, b.url))))) : null;
  // keyword alerts manager
  const kwInput = h('input', { placeholder: 'e.g. hiring, acquired, new, free shipping', style: 'flex:1' });
  const kwList = h('div', { class: 'hstack', style: 'flex-wrap:wrap;gap:7px;margin-top:10px' }, (c.keywords || []).map(k => h('span', { class: 'chip' }, k.word, h('span', { style: 'cursor:pointer;display:inline-flex', onclick: async () => { await POST(`/api/keywords/${k.id}/delete`); toast('Removed.'); go('competitor', c.id); } }, icon('x', 12)))));
  const addKw = async () => { if (!kwInput.value.trim()) return; await POST(`/api/competitors/${c.id}/keywords`, { word: kwInput.value.trim() }); toast('Keyword added — you\'ll be alerted when it appears.'); go('competitor', c.id); };
  kwInput.addEventListener('keydown', e => { if (e.key === 'Enter') addKw(); });
  const kwCard = card('Keyword alerts', 'Get notified when any of these words appears on their site', null, h('div', { class: 'card-b' },
    h('div', { class: 'hstack' }, kwInput, btn('Add', { icon: 'plus', onclick: addKw })), kwList));
  return h('div', { class: 'grid g2', style: 'align-items:start' }, contactCard, trustCard, promoCard, seoCard, focusCard, kwCard, brokenCard);
}

function tabArticles(c) {
  const items = c.feed || [];
  if (!items.length) return emptyState('page', 'No articles found', 'If this competitor has a blog with an RSS feed, their new posts will show up here after a scan.');
  return card('Latest posts', `${items.length} tracked from their feed`, null, h('div', { class: 'feed' }, items.map(it =>
    h('div', { class: 'feed-item', onclick: () => it.link && window.open(it.link, '_blank') },
      h('span', { class: 'feed-ic', style: 'background:var(--sky-l);color:var(--sky)' }, icon('page', 15)),
      h('div', { class: 'fi-main' }, h('div', { class: 'fi-t ellipsis' }, it.title || it.link), h('div', { class: 'fi-sub' }, it.link)),
      h('span', { class: 'fi-when' }, it.published ? timeAgo(it.published) : timeAgo(it.ts))))));
}

function addWatchModal(c) {
  const url = h('input', { placeholder: c.base_url + '/pricing' });
  const sel = h('input', { placeholder: '.price, #stock (optional CSS selector)' });
  const label = h('input', { placeholder: 'e.g. Pro plan price' });
  const save = btn('Add watch', { kind: 'primary', icon: 'eye', onclick: async () => {
    if (!url.value.trim()) { url.focus(); return toast('Enter a page URL.', 'warn'); }
    save.disabled = true;
    const r = await POST(`/api/competitors/${c.id}/pages`, { url: url.value, kind: 'watch', selector: sel.value, label: label.value });
    if (!r.ok) { save.disabled = false; return toast(r.error, 'err'); }
    toast('Watch added — it checks on the next scan.', 'ok'); m.close(); go('competitor', c.id);
  } });
  const m = modal({ title: 'Watch a specific page', icon: 'eye', body: h('div', {},
    field('Page URL', url), field('CSS selector', sel, 'optional', 'Leave blank to watch the whole page. Add a selector to watch just one part (like a price). Tip: right-click the element → Inspect → Copy selector.'),
    field('Label', label, 'optional')),
    footer: [btn('Cancel', { onclick: () => m.close() }), h('span', { class: 'spacer' }), save] });
}
function editCompetitorModal(c) {
  const name = h('input', { value: c.name });
  const iv = h('select', {}, [['0', 'Use default schedule'], ['60', 'Every hour'], ['360', 'Every 6 hours'], ['720', 'Every 12 hours'], ['1440', 'Daily'], ['10080', 'Weekly']].map(([v, l]) => h('option', { value: v, selected: String(c.interval_min) === v }, l)));
  const notes = h('textarea', {}); notes.value = c.notes || '';
  const active = switchEl('Active', c.active);
  const save = btn('Save', { kind: 'primary', icon: 'check', onclick: async () => {
    await POST(`/api/competitors/${c.id}`, { name: name.value, interval_min: iv.value, notes: notes.value, active: active.checked ? '1' : '0' });
    toast('Saved.'); m.close(); go('competitor', c.id);
  } });
  const m = modal({ title: 'Competitor settings', icon: 'settings', body: h('div', {},
    field('Name', name), field('Check frequency', iv), field('Notes', notes), h('div', { class: 'fld' }, active.wrap)),
    footer: [btn('Cancel', { onclick: () => m.close() }), h('span', { class: 'spacer' }), save] });
}
function switchEl(label, on, sub) {
  const input = h('input', { type: 'checkbox' }); input.checked = !!on;
  const wrap = h('label', { class: 'sw' }, input, h('span', { class: 'tr' }), h('span', { class: 'sl' }, h('b', {}, label), sub ? h('span', {}, sub) : null));
  return { wrap, get checked() { return input.checked; }, el: input };
}

async function pageHistoryModal(pid) {
  const d = await GET(`/api/pages/${pid}/history`);
  const snaps = d.snapshots || [];
  const body = h('div', {});
  if (snaps.length < 1) body.append(h('div', { class: 'muted' }, 'No snapshots yet.'));
  else {
    const info = h('div', { class: 'small muted', style: 'margin-bottom:12px' }, 'Pick two snapshots to compare.');
    let a = snaps[Math.min(1, snaps.length - 1)]?.id, b = snaps[0]?.id;
    const selA = h('select', { onchange: e => a = +e.target.value }, snaps.map(s => h('option', { value: s.id, selected: s.id === a }, dt(s.ts))));
    const selB = h('select', { onchange: e => b = +e.target.value }, snaps.map(s => h('option', { value: s.id, selected: s.id === b }, dt(s.ts))));
    const out = h('div', { class: 'diff' }, 'Select two snapshots and press Compare.');
    const cmp = btn('Compare', { size: 'sm', icon: 'code', onclick: async () => {
      if (a === b) return toast('Pick two different snapshots.', 'warn');
      out.replaceChildren('Comparing…');
      const r = await GET(`/api/pages/${pid}/diff?a=${a}&b=${b}`);
      out.replaceChildren(...renderDiff(r));
    } });
    const rows = snaps.map(s => h('tr', {}, h('td', { class: 'small' }, dt(s.ts)), h('td', {}, pill(s.status_code, s.status_code < 400 ? 'g' : 'r')), h('td', { class: 'num' }, fmt(s.word_count)), h('td', { class: 'small ellipsis', style: 'max-width:240px' }, s.title || '—')));
    const thead = h('thead', {}, h('tr', {}, h('th', {}, 'When'), h('th', {}, 'Status'), h('th', { class: 'num' }, 'Words'), h('th', {}, 'Title')));
    const table = h('div', { class: 'tbl-wrap' }, h('table', { class: 't' }, thead, h('tbody', {}, rows)));
    const timeline = h('div', {}, h('div', { class: 'b small', style: 'margin:4px 0 8px' }, 'Snapshot timeline'), table);
    body.append(info, h('div', { class: 'row', style: 'margin-bottom:12px' }, field('Older', selA), field('Newer', selB)), h('div', { class: 'mb' }, cmp), timeline, out);
  }
  modal({ title: 'Page history', icon: 'clock', wide: true, body });
}
function renderDiff(r) {
  if (!r || (!r.added && !r.removed)) return [h('div', { class: 'muted' }, 'No textual differences between these snapshots.')];
  const lines = (r.sample || '').split('\n').map(l => h('div', { class: l.startsWith('+') ? 'add' : l.startsWith('-') ? 'del' : '' }, l));
  return [h('div', { class: 'hstack', style: 'margin-bottom:8px' }, pill('+' + r.added + ' added', 'g'), pill('−' + r.removed + ' removed', 'r')), h('div', { class: 'diff' }, lines)];
}

/* ================================================================ CHANGES */
const CHQ = { competitor_id: '', type: '', unseen: false, q: '', page: 0 };
VIEWS.changes = async function () {
  $('#ttl').textContent = 'Changes'; $('#tsub').textContent = 'Every change across all competitors';
  setTop(h('a', { class: 'btn', href: '/api/export/changes.csv' + (CHQ.competitor_id ? '?competitor_id=' + CHQ.competitor_id : '') }, icon('download', 16), 'Export'),
    btn('Mark all seen', { icon: 'check', onclick: async () => { await POST('/api/changes/seen', CHQ.competitor_id ? { competitor_id: CHQ.competitor_id } : {}); toast('Marked seen.'); loadState(); renderChanges(); } }));
  const v = $('#view');
  const comps = APP.state.competitors || [];
  const compSel = h('select', { style: 'width:auto', onchange: e => { CHQ.competitor_id = e.target.value; CHQ.page = 0; renderChanges(); } }, h('option', { value: '' }, 'All competitors'), comps.map(c => h('option', { value: c.id, selected: String(CHQ.competitor_id) === String(c.id) }, c.name)));
  const typeSel = h('select', { style: 'width:auto', onchange: e => { CHQ.type = e.target.value; CHQ.page = 0; renderChanges(); } }, h('option', { value: '' }, 'All types'), Object.entries(CT).map(([k, m]) => h('option', { value: k, selected: CHQ.type === k }, m.l)));
  const search = h('input', { placeholder: 'Search…', value: CHQ.q, style: 'width:200px', oninput: e => { CHQ.q = e.target.value; clearTimeout(APP._st); APP._st = setTimeout(() => { CHQ.page = 0; renderChanges(); }, 300); } });
  const uns = switchEl('Unseen only', CHQ.unseen); uns.el.addEventListener('change', () => { CHQ.unseen = uns.checked; CHQ.page = 0; renderChanges(); });
  const bar = h('div', { class: 'hstack', style: 'margin-bottom:16px;flex-wrap:wrap;gap:10px' }, h('span', { class: 'hstack', style: 'gap:6px' }, icon('search', 16), search), compSel, typeSel, h('span', { class: 'spacer' }), uns.wrap);
  const listBox = h('div');
  v.replaceChildren(bar, listBox);
  window.renderChanges = async function () {
    listBox.replaceChildren(h('div', { class: 'muted' }, 'Loading…'));
    const d = await GET(`/api/changes?competitor_id=${CHQ.competitor_id}&type=${CHQ.type}&unseen=${CHQ.unseen ? 1 : 0}&q=${encodeURIComponent(CHQ.q)}&page=${CHQ.page}&per=50`);
    if (!d.rows.length) { listBox.replaceChildren(emptyState('activity', 'No changes found', 'Try clearing the filters, or run a scan.')); return; }
    const pages = Math.ceil(d.total / d.per);
    listBox.replaceChildren(card(null, null, null, h('div', { class: 'card-b', style: 'padding-top:4px;padding-bottom:4px' }, h('div', { class: 'feed' }, d.rows.map(changeRow)))),
      pages > 1 ? h('div', { class: 'hstack', style: 'margin-top:14px;justify-content:center' },
        btn('Prev', { size: 'sm', disabled: CHQ.page <= 0, onclick: () => { CHQ.page--; renderChanges(); } }),
        h('span', { class: 'small muted' }, `Page ${CHQ.page + 1} of ${pages} · ${fmt(d.total)} changes`),
        btn('Next', { size: 'sm', disabled: CHQ.page >= pages - 1, onclick: () => { CHQ.page++; renderChanges(); } })) : null);
  };
  renderChanges();
};
async function changeModal(chid) {
  const c = await GET('/api/changes/' + chid);
  if (!c || c.error) return toast('Change not found.', 'err');
  if (!c.seen) POST('/api/changes/seen', { ids: chid }).then(loadState);
  const m = CT[c.type] || { l: c.type, c: 'b', ic: 'activity' };
  let detailEl;
  const det = c.detail || '';
  if (det.includes('Before:') || c.type === 'content') {
    const lines = det.split('\n').map(l => h('div', { class: l.startsWith('+') ? 'add' : l.startsWith('-') ? 'del' : l.startsWith('After') ? 'add' : l.startsWith('Before') ? 'del' : '' }, l));
    detailEl = det ? h('div', { class: 'diff' }, lines) : null;
  } else detailEl = det ? h('div', { class: 'diff' }, det) : null;
  const m2 = modal({ title: m.l, icon: m.ic, wide: true, body: h('div', {},
    h('div', { class: 'hstack', style: 'margin-bottom:14px' }, h('span', { class: 'feed-ic', style: `background:${COLORVAR[m.c]}22;color:${COLORVAR[m.c]}` }, icon(m.ic, 16)), h('div', {}, h('b', {}, c.comp_name), h('div', { class: 'xs dim' }, dt(c.ts)))),
    h('dl', { class: 'review', style: 'margin-bottom:16px' }, h('dt', {}, 'What'), h('dd', {}, c.summary), h('dt', {}, 'Page'), h('dd', {}, c.url ? h('a', { href: c.url, target: '_blank' }, c.url) : '—')),
    detailEl),
    footer: [c.url ? btn('Open page', { icon: 'external', onclick: () => window.open(c.url, '_blank') }) : null, h('span', { class: 'spacer' }), btn('Close', { onclick: () => m2.close() })] });
}

/* ================================================================ TECHNOLOGY */
VIEWS.tech = async function () {
  $('#ttl').textContent = 'Technology'; $('#tsub').textContent = 'What your competitors are built with';
  setTop();
  const v = $('#view'); v.replaceChildren(h('div', { class: 'muted' }, 'Loading…'));
  const d = await GET('/api/tech');
  if (!d.total) { v.replaceChildren(emptyState('cpu', 'No technology detected yet', 'Add competitors and run scans to map their stacks.')); return; }
  const cats = Object.entries(d.by_category).sort((a, b) => b[1].length - a[1].length);
  v.replaceChildren(h('div', { class: 'grid g2' }, cats.map(([cat, items]) => {
    const byTech = {}; items.forEach(t => (byTech[t.name] ||= []).push(t));
    return card(cat, Object.keys(byTech).length + ' technologies', null, h('div', { class: 'card-b' }, Object.entries(byTech).map(([name, uses]) =>
      h('div', { class: 'hstack', style: 'padding:9px 0;border-bottom:1px solid var(--line)' }, h('span', { class: 'feed-ic', style: 'background:var(--surface2)' }, icon('cpu', 14)),
        h('div', { style: 'flex:1' }, h('b', {}, name), h('div', { class: 'hstack', style: 'gap:5px;margin-top:4px;flex-wrap:wrap' }, uses.map(u => h('span', { class: 'chip', style: 'padding:2px 9px', onclick: () => go('competitor', u.competitor_id) }, h('span', { class: 'dot', style: `background:${u.comp_color}` }), u.comp_name)))),
        h('b', { class: 'dim' }, uses.length)))));
  })));
};

/* ================================================================ COMPARE */
VIEWS.compare = async function () {
  $('#ttl').textContent = 'Compare'; $('#tsub').textContent = 'Put competitors side by side';
  setTop();
  await loadState();
  const comps = APP.state.competitors || [];
  const v = $('#view');
  if (comps.length < 2) { v.replaceChildren(emptyState('dashboard', 'Add at least two competitors', 'Compare needs two or more competitors to line up.', btn('Add competitor', { kind: 'primary', icon: 'plus', onclick: addCompetitorModal }))); return; }
  if (!APP._cmp) APP._cmp = comps.slice(0, Math.min(4, comps.length)).map(c => c.id);
  const picker = h('div', { class: 'hstack', style: 'flex-wrap:wrap;gap:8px;margin-bottom:18px' }, comps.map(c => {
    const on = APP._cmp.includes(c.id);
    return h('div', { class: 'chip', style: 'cursor:pointer;' + (on ? 'border-color:' + c.color : 'opacity:.6'), onclick: () => { APP._cmp = on ? APP._cmp.filter(x => x !== c.id) : [...APP._cmp, c.id]; renderCmp(); } },
      h('span', { class: 'dot', style: 'background:' + c.color }), c.name, on ? icon('check', 13) : null);
  }));
  const out = h('div');
  v.replaceChildren(picker, out);
  window.renderCmp = async function () {
    picker.querySelectorAll('.chip').forEach((el, i) => { const on = APP._cmp.includes(comps[i].id); el.style.opacity = on ? '1' : '.6'; el.style.borderColor = on ? comps[i].color : ''; });
    if (!APP._cmp.length) { out.replaceChildren(h('div', { class: 'muted' }, 'Pick competitors above.')); return; }
    out.replaceChildren(h('div', { class: 'muted' }, 'Loading…'));
    const d = await GET('/api/compare?ids=' + APP._cmp.join(','));
    const cols = d.competitors || [];
    const money = (v, cur) => v == null ? '—' : (cols[0] && '') + v;
    const rows = [
      ['Domain', c => c.domain],
      ['Pages tracked', c => fmt(c.pages)],
      ['Products', c => fmt(c.products)],
      ['Lowest price', c => c.price_min != null ? c.price_min : '—'],
      ['Highest price', c => c.price_max != null ? c.price_max : '—'],
      ['Avg price', c => c.price_avg != null ? c.price_avg : '—'],
      ['Running promo', c => c.promo ? pill('Yes', 'r') : pill('No', 'g')],
      ['Security grade', c => pill(c.security, c.security === 'A' || c.security === 'B' ? 'g' : c.security === 'C' ? 'a' : 'r')],
      ['SSL days left', c => c.ssl_days != null ? c.ssl_days : '—'],
      ['Domain age', c => c.domain_age != null ? Math.floor(c.domain_age / 365) + 'y' : '—'],
      ['Tech count', c => fmt(c.tech.length)],
      ['Social channels', c => c.socials.length ? c.socials.join(', ') : '—'],
    ];
    const table = h('table', { class: 't' },
      h('thead', {}, h('tr', {}, h('th', {}, ''), cols.map(c => h('th', {}, h('span', { class: 'hstack' }, h('span', { class: 'dot', style: 'width:9px;height:9px;border-radius:50%;background:' + c.color }), c.name))))),
      h('tbody', {}, rows.map(([label, fn]) => h('tr', {}, h('td', {}, h('b', {}, label)), cols.map(c => h('td', {}, fn(c)))))));
    // tech matrix
    const allTech = [...new Set(cols.flatMap(c => c.tech))].sort();
    const techTable = allTech.length ? h('table', { class: 't', style: 'margin-top:20px' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Technology'), cols.map(c => h('th', {}, c.name)))),
      h('tbody', {}, allTech.map(t => h('tr', {}, h('td', {}, t), cols.map(c => h('td', {}, c.tech.includes(t) ? icon('check', 15) : h('span', { class: 'dim' }, '—'))))))) : null;
    out.replaceChildren(h('div', { class: 'tbl-wrap' }, table), techTable ? h('div', { class: 'tbl-wrap', style: 'margin-top:20px' }, techTable) : null);
  };
  renderCmp();
};

/* ================================================================ WEBHOOKS */
VIEWS.webhooks = async function () {
  $('#ttl').textContent = 'Alerts & webhooks'; $('#tsub').textContent = 'Get pushed the moment a competitor changes';
  setTop(btn('Add webhook', { kind: 'primary', icon: 'plus', onclick: () => webhookModal() }));
  const v = $('#view'); v.replaceChildren(h('div', { class: 'muted' }, 'Loading…'));
  const d = await GET('/api/webhooks');
  const hooks = d.webhooks || [];
  const list = hooks.length ? h('div', { class: 'tbl-wrap' }, h('table', { class: 't' },
    h('thead', {}, h('tr', {}, h('th', {}, 'Webhook'), h('th', {}, 'Events'), h('th', {}, 'Status'), h('th', {}, 'Last fired'), h('th', {}, ''))),
    h('tbody', {}, hooks.map(w => h('tr', {},
      h('td', {}, h('b', {}, w.label || 'Webhook'), h('div', { class: 'xs dim ellipsis', style: 'max-width:320px' }, w.url)),
      h('td', {}, h('span', { class: 'tag' }, w.events || 'all')),
      h('td', {}, w.active ? (w.last_status && w.last_status.startsWith('2') ? pill('OK ' + w.last_status, 'g') : (w.last_status ? pill(w.last_status, 'a') : pill('Active', 'b'))) : pill('Off')),
      h('td', { class: 'small dim' }, w.last_fired ? timeAgo(w.last_fired) : '—'),
      h('td', { class: 'nowrap', style: 'text-align:right' },
        btn('Test', { size: 'sm', kind: 'quiet', onclick: async () => { const r = await POST('/api/webhooks/test', { url: w.url, secret: w.secret }); toast(r.ok ? 'Test sent — got ' + r.status : 'Failed: ' + (r.error || r.status), r.ok ? 'ok' : 'err'); } }),
        btn('Edit', { size: 'sm', kind: 'quiet', icon: 'edit', onclick: () => webhookModal(w) }),
        h('button', { class: 'icon-btn sm', title: 'Delete', onclick: async () => { if (!await confirmBox({ title: 'Delete webhook?', text: w.url, ok: 'Delete', danger: true })) return; await POST(`/api/webhooks/${w.id}/delete`); toast('Deleted.'); render(); } }, icon('trash', 15))))))))
    : emptyState('link', 'No webhooks yet', 'Add a webhook URL (Zapier, Make, Slack, Discord, your own server) and RivalRadar will POST every change to it.', btn('Add webhook', { kind: 'primary', icon: 'plus', onclick: () => webhookModal() }));
  v.replaceChildren(
    banner('info', h('span', {}, 'Webhooks fire a JSON ', h('span', { class: 'tag' }, 'POST'), ' on every change, signed with an optional secret (', h('span', { class: 'tag' }, 'X-RivalRadar-Signature'), '). Prefer email? Set it up in Settings.')),
    h('div', { style: 'height:16px' }), card('Your webhooks', null, null, h('div', {}, list)));
};
function webhookModal(w) {
  w = w || {};
  const label = h('input', { value: w.label || '', placeholder: 'e.g. Slack #competitors' });
  const url = h('input', { value: w.url || '', placeholder: 'https://hooks.slack.com/…' });
  const events = h('input', { value: w.events || 'all', placeholder: 'all, or e.g. price,new_page,content' });
  const secret = h('input', { value: w.secret || '', placeholder: 'optional signing secret' });
  const save = btn(w.id ? 'Save' : 'Add', { kind: 'primary', icon: 'check', onclick: async () => {
    if (!url.value.startsWith('http')) { url.focus(); return toast('Enter a valid URL.', 'warn'); }
    const payload = { label: label.value, url: url.value, events: events.value || 'all', secret: secret.value };
    const r = w.id ? await POST(`/api/webhooks/${w.id}`, payload) : await POST('/api/webhooks', payload);
    if (!r.ok) return toast(r.error, 'err'); toast('Saved.'); m.close(); render();
  } });
  const m = modal({ title: w.id ? 'Edit webhook' : 'Add webhook', icon: 'link', body: h('div', {},
    field('Label', label), field('Webhook URL', url),
    field('Events', events, null, 'Comma-separated event types, or "all". Types: new_page, removed_page, content, title, meta, h1, status, tech_added, tech_removed, price.'),
    field('Signing secret', secret, 'optional', 'If set, each request includes an HMAC-SHA256 signature header you can verify.')),
    footer: [w.id ? btn('Send test', { onclick: async () => { const r = await POST('/api/webhooks/test', { url: url.value, secret: secret.value }); toast(r.ok ? 'Test sent — got ' + r.status : 'Failed: ' + (r.error || r.status), r.ok ? 'ok' : 'err'); } }) : null, h('span', { class: 'spacer' }), btn('Cancel', { onclick: () => m.close() }), save] });
}

/* ================================================================ SETTINGS */
VIEWS.settings = async function () {
  $('#ttl').textContent = 'Settings'; $('#tsub').textContent = 'Scanning, alerts and data';
  setTop();
  const s = APP.state.settings || {};
  const f = {};
  const mk = (k, v) => (f[k] = h('input', { value: v != null ? v : (s[k] || '') }));
  const sel = (k, opts) => (f[k] = h('select', {}, opts.map(([val, l]) => h('option', { value: val, selected: String(s[k]) === String(val) }, l))));

  const iv = sel('scan_interval_min', [['60', 'Every hour'], ['180', 'Every 3 hours'], ['360', 'Every 6 hours'], ['720', 'Every 12 hours'], ['1440', 'Daily'], ['10080', 'Weekly'], ['0', 'Manual only']]);
  const robots = switchEl('Respect robots.txt', s.respect_robots !== '0', 'Recommended — skips pages a site asks crawlers not to fetch');
  const timeout = mk('request_timeout'); timeout.type = 'number';
  const maxp = mk('max_pages_per_site'); maxp.type = 'number';
  const delay = mk('request_delay_ms'); delay.type = 'number';
  const keep = mk('keep_snapshots'); keep.type = 'number';
  const ua = mk('user_agent');
  const saveScan = btn('Save scanning settings', { kind: 'primary', icon: 'check', onclick: async () => {
    await POST('/api/settings', { scan_interval_min: iv.value, respect_robots: robots.checked ? '1' : '0', request_timeout: timeout.value, max_pages_per_site: maxp.value, request_delay_ms: delay.value, keep_snapshots: keep.value, user_agent: ua.value });
    toast('Saved.'); await loadState();
  } });

  const sh = mk('smtp_host'), sp = mk('smtp_port'), ssec = sel('smtp_security', [['starttls', 'STARTTLS'], ['ssl', 'SSL/TLS'], ['none', 'None']]);
  const su = mk('smtp_user'), spw = h('input', { type: 'password', placeholder: s.smtp_host ? '•••••• (unchanged)' : '' }), sfrom = mk('smtp_from'), alert = mk('alert_email');
  const saveEmail = btn('Save email alerts', { kind: 'primary', icon: 'mail', onclick: async () => {
    await POST('/api/settings', { smtp_host: sh.value, smtp_port: sp.value, smtp_security: ssec.value, smtp_user: su.value, smtp_pass: spw.value, smtp_from: sfrom.value, alert_email: alert.value });
    toast('Saved.'); await loadState();
  } });
  const testEmail = btn('Send test email', { onclick: async () => { const r = await POST('/api/settings/test-email'); toast(r.ok ? 'Test email sent.' : 'Failed: ' + (r.error || ''), r.ok ? 'ok' : 'err'); } });

  $('#view').replaceChildren(h('div', { class: 'grid g2', style: 'align-items:start' },
    h('div', {},
      card('Scanning', 'How RivalRadar checks competitor sites', null, h('div', { class: 'card-b' },
        field('Default check frequency', iv, null, 'Per-competitor frequency overrides this.'),
        h('div', { class: 'fld' }, robots.wrap),
        h('div', { class: 'row' }, field('Request timeout (s)', timeout), field('Delay between requests (ms)', delay)),
        h('div', { class: 'row' }, field('Max pages per site', maxp), field('Snapshots kept per page', keep)),
        field('User-Agent', ua, null, 'How RivalRadar identifies itself to the sites it checks.'),
        h('div', { style: 'margin-top:4px' }, saveScan)))),
    h('div', {},
      card('Email alerts', 'Optional — uses your own email account', null, h('div', { class: 'card-b' },
        field('Send alerts to', alert, 'optional', 'Leave blank to use webhooks / the in-app feed only.'),
        h('div', { class: 'row' }, field('SMTP host', sh), field('Port', sp)),
        field('Security', ssec), h('div', { class: 'row' }, field('Username', su), field('Password', spw)),
        field('From address', sfrom),
        h('div', { class: 'hstack', style: 'margin-top:4px' }, saveEmail, testEmail))),
      h('div', { style: 'height:16px' }),
      card('Danger zone', null, null, h('div', { class: 'card-b' },
        h('p', { class: 'small muted', style: 'margin:0 0 12px' }, 'Delete all competitors, pages, snapshots, changes and tech. Webhooks and settings are kept.'),
        btn('Delete all tracking data', { kind: 'danger', icon: 'trash', onclick: async () => {
          if (!await confirmBox({ title: 'Delete everything?', text: 'This permanently removes every competitor and all their history.', ok: 'Delete everything', danger: true, typeText: 'DELETE' })) return;
          const r = await POST('/api/data/clear', { confirm: 'DELETE' }); if (!r.ok) return toast(r.error, 'err'); toast('All data cleared.'); await loadState(); go('dashboard');
        } }))))));
};

/* ---------------------------------------------------------------- theme */
function currentTheme() { try { return localStorage.getItem('rr_theme') || 'dark'; } catch (e) { return 'dark'; } }
function applyTheme(t) { document.documentElement.setAttribute('data-theme', t); try { localStorage.setItem('rr_theme', t); } catch (e) {} }
function renderThemeBtn() {
  const t = currentTheme(), b = $('#themeBtn');
  if (!b) return;
  b.replaceChildren(icon(t === 'light' ? 'moon' : 'sun', 15), h('span', {}, t === 'light' ? 'Dark' : 'Light'));
}
function toggleTheme() { applyTheme(currentTheme() === 'light' ? 'dark' : 'light'); renderThemeBtn(); }

/* ---------------------------------------------------------------- boot */
$('#themeBtn').addEventListener('click', toggleTheme);
renderThemeBtn();
$('#menuBtn').addEventListener('click', () => toggleSide(!$('#side').classList.contains('open')));
window.addEventListener('hashchange', () => { parseHash(); render(); });
(async function () {
  parseHash();
  await loadState();
  render();
  if (APP.state.jobs && Object.keys(APP.state.jobs).length) startPolling();
})();
