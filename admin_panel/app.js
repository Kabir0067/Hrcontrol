/* ═══════════════════════════════════════════════════════════════════════
   SoftClub HR Control — панели маъмурият
   Бе ягон китобхонаи беруна: графикҳо бо SVG-и худӣ кашида мешаванд.
   ═══════════════════════════════════════════════════════════════════════ */

(() => {
'use strict';

const API = '.';
const PAGE = 20;

let token = localStorage.getItem('sc_token');
let view = 'home';
let reqOffset = 0;
let reqTotal = 0;
let reqBusy = false;
let cache = { workers: null, stats: null, stats2: null };
const known = new Map();     // id → сабти дархост (барои панели тафсилот)

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const TYPE = {
  late:            { label: 'Дер мекунад',    color: 'var(--warn)',   key: 'warn' },
  absent:          { label: 'Намеояд',        color: 'var(--danger)', key: 'danger' },
  at_work_waiting: { label: 'Ҷавоб мепурсад', color: 'var(--info)',   key: 'info' },
  leaving_early:   { label: 'Барвақт меравад',color: 'var(--violet)', key: 'violet' },
};

const STATUS = {
  pending:   { label: 'Дар интизорӣ', color: 'var(--warn)' },
  accepted:  { label: 'Қабул',        color: 'var(--ok)' },
  rejected:  { label: 'Рад',          color: 'var(--danger)' },
  cancelled: { label: 'Бекор',        color: 'var(--text-3)' },
};

const VIEW_META = {
  home:   ['Хулоса',     'Манзараи умумӣ'],
  req:    ['Дархостҳо',  'Ҳамаи мурочиатҳо'],
  team:   ['Кормандон',  'Омори шахсӣ'],
  charts: ['Графикҳо',   'Таҳлили визуалӣ'],
};


/* ══════════════ Telegram Mini App ══════════════ */

const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

function initTelegram() {
  if (!tg) return;
  try {
    tg.ready();
    tg.expand();
    if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
  } catch (_) {}
}

function haptic(kind = 'light') {
  if (!tg || !tg.HapticFeedback) return;
  try {
    if (kind === 'ok' || kind === 'error' || kind === 'warning') {
      tg.HapticFeedback.notificationOccurred(kind === 'ok' ? 'success' : kind);
    } else {
      tg.HapticFeedback.impactOccurred(kind);
    }
  } catch (_) {}
}


/* ══════════════ Мавзӯъ ══════════════ */

function preferredTheme() {
  const saved = localStorage.getItem('sc_theme');
  if (saved === 'dark' || saved === 'light') return saved;
  if (tg && tg.colorScheme) return tg.colorScheme;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function applyTheme(name) {
  document.documentElement.dataset.theme = name;
  const meta = $('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', name === 'light' ? '#F4F6FA' : '#0B0F17');
  if (tg && tg.setHeaderColor) {
    try { tg.setHeaderColor(name === 'light' ? '#F4F6FA' : '#0B0F17'); } catch (_) {}
  }
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  localStorage.setItem('sc_theme', next);
  applyTheme(next);
  haptic('light');
  if (view === 'charts') renderCharts();
  if (view === 'home' && cache.stats) drawWeek(cache.stats.daily || []);
}


/* ══════════════ Ёрдамчиҳо ══════════════ */

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function shortName(full) {
  return String(full || '').split(' (@')[0].trim() || '—';
}

function initials(full) {
  const parts = shortName(full).split(/\s+/).filter(Boolean);
  return (parts.slice(0, 2).map((p) => p[0]).join('') || '?').toUpperCase();
}

function parseDate(value) {
  if (!value) return null;
  const d = new Date(String(value).replace(' ', 'T'));
  return isNaN(d.getTime()) ? null : d;
}

function fmtDateTime(value) {
  const d = parseDate(value);
  if (!d) return '—';
  const p = (n) => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} · ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function fmtDay(value) {
  const d = parseDate(value);
  if (!d) return '';
  const p = (n) => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}`;
}

function fmtMinutes(m) {
  m = Number(m) || 0;
  if (m <= 0) return '—';
  if (m < 60) return `${m} дақ`;
  const h = Math.floor(m / 60), r = m % 60;
  return r ? `${h} с ${r} дақ` : `${h} соат`;
}

function toast(message, kind = '') {
  const el = $('#toast');
  el.textContent = message;
  el.className = 'toast' + (kind ? ` toast--${kind}` : '');
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 2600);
}

function emptyState(title, note) {
  return `<div class="empty">
    <svg viewBox="0 0 24 24"><path d="M4 5h16v14H4z"/><path d="M8 10h8M8 14h5"/></svg>
    <b>${esc(title)}</b><span>${esc(note)}</span></div>`;
}

function skeletons(count, cls = 'skeleton--row') {
  return Array.from({ length: count }, () => `<div class="skeleton ${cls}"></div>`).join('');
}


/* ══════════════ API ══════════════ */

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(API + path, { ...options, headers });
  } catch (_) {
    toast('Алоқа бо сервер нест', 'danger');
    return null;
  }

  if (res.status === 401) { logout(); return null; }

  let data = null;
  try { data = await res.json(); } catch (_) { data = null; }

  if (!res.ok) {
    if (data && data.error) toast(data.error, 'danger');
    else toast(`Хатои сервер (${res.status})`, 'danger');
    return null;
  }
  return data;
}


/* ══════════════ Авторизатсия ══════════════ */

function showLogin() {
  $('#app').hidden = true;
  $('#login').hidden = false;
}

function showApp() {
  $('#login').hidden = true;
  $('#app').hidden = false;
  loadHome();
}

function logout() {
  token = null;
  localStorage.removeItem('sc_token');
  cache = { workers: null, stats: null, stats2: null };
  showLogin();
}

$('#login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const btn = $('#login-btn');
  const err = $('#login-error');

  btn.disabled = true;
  btn.firstElementChild.textContent = 'Санҷиш…';
  err.hidden = true;

  const data = await api('/api/login', {
    method: 'POST',
    body: JSON.stringify({
      login: $('#in-login').value.trim(),
      password: $('#in-pass').value,
    }),
  });

  btn.disabled = false;
  btn.firstElementChild.textContent = 'Даромадан';

  if (data && data.token) {
    token = data.token;
    localStorage.setItem('sc_token', token);
    haptic('ok');
    showApp();
  } else {
    err.textContent = 'Логин ё рамз нодуруст аст';
    err.hidden = false;
    haptic('error');
  }
});

$('#toggle-pass').addEventListener('click', () => {
  const input = $('#in-pass');
  input.type = input.type === 'password' ? 'text' : 'password';
});

$('#btn-logout').addEventListener('click', () => {
  haptic('light');
  logout();
});


/* ══════════════ Навигатсия ══════════════ */

function go(name) {
  if (!VIEW_META[name]) return;
  view = name;

  $$('.view').forEach((el) => el.classList.toggle('is-active', el.id === `view-${name}`));
  $$('.tab').forEach((el) => el.classList.toggle('is-active', el.dataset.view === name));
  $$('.pill').forEach((el) => el.classList.toggle('is-active', el.dataset.view === name));

  const [title, sub] = VIEW_META[name];
  $('#view-title').textContent = title;
  $('#view-sub').textContent = sub;
  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (name === 'home') loadHome();
  if (name === 'req') loadRequests(true);
  if (name === 'team') loadTeam();
  if (name === 'charts') loadCharts();
}

$$('.tab, .pill').forEach((btn) => btn.addEventListener('click', () => {
  haptic('light');
  go(btn.dataset.view);
}));

document.addEventListener('click', (event) => {
  const target = event.target.closest('[data-goto]');
  if (target) go(target.dataset.goto);
});

$('#btn-theme').addEventListener('click', toggleTheme);

$('#btn-refresh').addEventListener('click', async () => {
  haptic('light');
  cache = { workers: null, stats: null, stats2: null };
  const icon = $('#btn-refresh svg');
  icon.style.transition = 'transform .6s var(--ease)';
  icon.style.transform = 'rotate(360deg)';
  setTimeout(() => { icon.style.transform = ''; icon.style.transition = ''; }, 620);

  if (view === 'home') await loadHome();
  else if (view === 'req') await loadRequests(true);
  else if (view === 'team') await loadTeam();
  else await loadCharts();
  toast('Навсозӣ шуд', 'ok');
});


/* ══════════════ ХУЛОСА ══════════════ */

function statTile(label, value, sub, color) {
  return `<div class="stat" style="--c:${color}">
    <div class="stat__label"><span class="stat__dot"></span>${esc(label)}</div>
    <div class="stat__num">${value}</div>
    <div class="stat__sub">${esc(sub)}</div>
  </div>`;
}

async function loadHome() {
  const data = await api('/api/dashboard');
  if (!data) return;
  cache.stats = data;

  const rate = data.total ? Math.round((data.accepted / data.total) * 100) : 0;

  $('#home-stats').innerHTML =
    statTile('Ҳамагӣ', data.total ?? 0, `${data.people ?? 0} корманд`, 'var(--brand)') +
    statTile('Имрӯз', data.today ?? 0, `Ҳафта: ${data.week ?? 0}`, 'var(--info)') +
    statTile('Қабул', data.accepted ?? 0, `${rate}% аз ҳама`, 'var(--ok)') +
    statTile('Дар интизорӣ', data.pending ?? 0, `Рад: ${data.rejected ?? 0}`, 'var(--warn)');

  const daily = data.daily || [];
  const weekTotal = daily.reduce((sum, d) => sum + (d.count || 0), 0);
  $('#week-note').textContent = `${weekTotal} дархост`;
  drawWeek(daily);

  const recent = data.recent || [];
  $('#home-recent').className = 'list list--compact';
  $('#home-recent').innerHTML = recent.length
    ? recent.map(requestCard).join('')
    : emptyState('Ҳанӯз дархост нест', 'Ҳамин ки ҳамкорон менависанд, дар ин ҷо пайдо мешавад');
}


/* ══════════════ ДАРХОСТҲО ══════════════ */

function requestCard(rec) {
  known.set(rec.id, rec);
  const type = TYPE[rec.type] || { label: rec.type, color: 'var(--text-3)' };
  const status = STATUS[rec.status] || { label: rec.status, color: 'var(--text-3)' };

  const minutes = rec.minutes ? `<span class="chip chip--soft">${fmtMinutes(rec.minutes)}</span>` : '';

  return `<button class="rq" style="--c:${type.color}" data-req="${rec.id}">
    <div class="rq__top">
      <div class="rq__who">
        <div class="avatar">${esc(initials(rec.name))}</div>
        <div style="min-width:0">
          <div class="rq__name">${esc(shortName(rec.name))}</div>
          <div class="rq__id">#${rec.id}</div>
        </div>
      </div>
      <span class="chip chip--${rec.status}">${esc(status.label)}</span>
    </div>
    <div class="rq__meta">
      <span class="chip chip--${rec.type}">${esc(type.label)}</span>${minutes}
    </div>
    <div class="rq__reason">${esc(rec.reason)}</div>
    <div class="rq__foot">
      <span>${fmtDateTime(rec.created_at)}</span>
      ${rec.deadline_at ? `<span>то ${fmtDateTime(rec.deadline_at).split('· ')[1] || ''}</span>` : ''}
    </div>
  </button>`;
}

function filterQuery() {
  const params = new URLSearchParams();
  const type = $('#f-type').value;
  const status = $('#f-status').value;
  const from = $('#f-from').value;
  const to = $('#f-to').value;
  const search = $('#f-q').value.trim();

  if (type) params.set('type', type);
  if (status) params.set('status', status);
  if (from) params.set('date_from', from);
  if (to) params.set('date_to', to);
  if (search) params.set('q', search);

  $('#filter-dot').hidden = !(type || status || from || to);
  return params;
}

async function loadRequests(reset = false) {
  if (reqBusy) return;
  reqBusy = true;

  const list = $('#req-list');
  if (reset) {
    reqOffset = 0;
    list.innerHTML = skeletons(4);
  }

  const params = filterQuery();
  params.set('limit', PAGE);
  params.set('offset', reqOffset);

  const data = await api(`/api/requests?${params}`);
  reqBusy = false;
  if (!data) { if (reset) list.innerHTML = emptyState('Хато', 'Маълумот бор нашуд'); return; }

  reqTotal = data.total || 0;
  const html = (data.items || []).map(requestCard).join('');

  if (reset) {
    list.innerHTML = html || emptyState('Чизе ёфт нашуд', 'Филтрҳоро тағйир диҳед');
  } else {
    list.insertAdjacentHTML('beforeend', html);
  }

  reqOffset += (data.items || []).length;
  $('#btn-more').hidden = reqOffset >= reqTotal;
  $('#btn-more').textContent = `Боз нишон диҳед (${reqTotal - reqOffset})`;
}

$('#btn-more').addEventListener('click', () => loadRequests(false));

$('#btn-filters').addEventListener('click', () => {
  const box = $('#filters');
  box.hidden = !box.hidden;
  haptic('light');
});

$('#btn-reset').addEventListener('click', () => {
  ['f-type', 'f-status', 'f-from', 'f-to', 'f-q'].forEach((id) => { $(`#${id}`).value = ''; });
  loadRequests(true);
});

$('#btn-export').addEventListener('click', () => {
  const url = new URL(`${API}/api/export.csv`, location.href);
  url.searchParams.set('token', token);
  // Дар Telegram WebView `window.open` баста аст — тавассути SDK мекушоем.
  if (tg && tg.openLink) { try { tg.openLink(url.href); return; } catch (_) {} }
  window.open(url.href, '_blank');
});

['f-type', 'f-status', 'f-from', 'f-to'].forEach((id) =>
  $(`#${id}`).addEventListener('change', () => loadRequests(true)));

let searchTimer;
$('#f-q').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadRequests(true), 320);
});


/* ══════════════ КОРМАНДОН ══════════════ */

async function loadTeam() {
  const box = $('#team-list');
  if (!cache.workers) box.innerHTML = skeletons(3, '');

  const data = cache.workers || await api('/api/workers');
  if (!data) { box.innerHTML = emptyState('Хато', 'Маълумот бор нашуд'); return; }
  cache.workers = data;

  if (!data.length) {
    box.innerHTML = emptyState('Корманд нест', 'Ҳанӯз касе дархост нафиристодааст');
    return;
  }

  box.innerHTML = data.map((w) => {
    const rate = w.total ? Math.round((w.accepted / w.total) * 100) : 0;
    return `<div class="member">
      <div class="member__top">
        <div class="avatar">${esc(initials(w.name))}</div>
        <div style="min-width:0;flex:1">
          <div class="member__name">${esc(shortName(w.name))}</div>
          <div class="member__sub">Охирин: ${fmtDateTime(w.last_at)}</div>
        </div>
        <div class="member__total"><b>${w.total}</b><span>дархост</span></div>
      </div>

      <div class="member__grid">
        <div class="mstat" style="--c:var(--warn)"><b>${w.late || 0}</b><span>Дер</span></div>
        <div class="mstat" style="--c:var(--danger)"><b>${w.absent || 0}</b><span>Ғоиб</span></div>
        <div class="mstat" style="--c:var(--info)"><b>${w.at_work_waiting || 0}</b><span>Ҷавоб</span></div>
        <div class="mstat" style="--c:var(--violet)"><b>${w.leaving_early || 0}</b><span>Барвақт</span></div>
      </div>

      <div class="meter">
        <div class="meter__row"><span>Сатҳи қабул</span><b>${rate}%</b></div>
        <div class="meter__track"><div class="meter__fill" style="width:${rate}%"></div></div>
      </div>
    </div>`;
  }).join('');
}


/* ══════════════ ГРАФИКҲО (SVG-и худӣ) ══════════════ */

const SVG_NS = 'http://www.w3.org/2000/svg';

function svgEl(name, attrs = {}) {
  const el = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  return el;
}

/* Барои он ки матн ва кунҷҳо каҷ нашаванд, viewBox бо паҳнои воқеии
   контейнер сохта мешавад — 1:1, бе кашидан. */
function hostWidth(host) {
  const w = host.clientWidth || host.getBoundingClientRect().width || 300;
  return Math.max(260, Math.round(w));
}

/* ── Диаграммаи сутунӣ ── */
function barChart(host, points, accent = 'var(--brand)') {
  host.innerHTML = '';
  if (!points.length) { host.innerHTML = emptyState('Маълумот нест', ''); return; }

  const W = hostWidth(host), H = 150;
  const padL = 4, padR = 4, padT = 18, padB = 20;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const max = Math.max(1, ...points.map((p) => p.value));

  const svg = svgEl('svg', {
    class: 'chart', viewBox: `0 0 ${W} ${H}`,
    preserveAspectRatio: 'xMidYMid meet', role: 'img',
  });
  svg.style.height = `${H}px`;

  // хатҳои роҳнамо
  for (let i = 0; i <= 2; i++) {
    const y = padT + (innerH / 2) * i;
    svg.appendChild(svgEl('line', { class: 'grid', x1: padL, x2: W - padR, y1: y, y2: y }));
  }

  const step = innerW / points.length;
  const barW = Math.max(6, Math.min(26, step * 0.56));

  points.forEach((point, index) => {
    const cx = padL + step * index + step / 2;
    const h = point.value > 0 ? Math.max(3, (point.value / max) * innerH) : 0;
    const y = padT + innerH - h;

    if (h > 0) {
      const rect = svgEl('rect', {
        x: cx - barW / 2, y, width: barW, height: h,
        rx: Math.min(5, barW / 2), fill: accent,
      });
      svg.appendChild(rect);

      const val = svgEl('text', {
        x: cx, y: y - 5, 'text-anchor': 'middle', class: 'val',
      });
      val.textContent = point.value;
      svg.appendChild(val);
    }

    if (points.length <= 16 || index % 2 === 0) {
      const label = svgEl('text', {
        x: cx, y: H - 6, 'text-anchor': 'middle',
      });
      label.textContent = point.label;
      svg.appendChild(label);
    }
  });

  host.appendChild(svg);
}

/* ── Диаграммаи хаттӣ ── */
function lineChart(host, points, accent = 'var(--brand)') {
  host.innerHTML = '';
  if (points.length < 2) { barChart(host, points, accent); return; }

  const W = hostWidth(host), H = 150;
  const padL = 6, padR = 6, padT = 14, padB = 20;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const max = Math.max(1, ...points.map((p) => p.value));

  const svg = svgEl('svg', {
    class: 'chart', viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet',
  });
  svg.style.height = `${H}px`;

  for (let i = 0; i <= 2; i++) {
    const y = padT + (innerH / 2) * i;
    svg.appendChild(svgEl('line', { class: 'grid', x1: padL, x2: W - padR, y1: y, y2: y }));
  }

  const step = innerW / (points.length - 1);
  const xy = points.map((p, i) => [padL + step * i, padT + innerH - (p.value / max) * innerH]);

  const gradId = 'g' + Math.random().toString(36).slice(2, 8);
  const defs = svgEl('defs');
  const grad = svgEl('linearGradient', { id: gradId, x1: 0, y1: 0, x2: 0, y2: 1 });
  const s1 = svgEl('stop', { offset: '0%',   'stop-color': accent, 'stop-opacity': '.30' });
  const s2 = svgEl('stop', { offset: '100%', 'stop-color': accent, 'stop-opacity': '0' });
  grad.append(s1, s2); defs.appendChild(grad); svg.appendChild(defs);

  const line = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const area = `${line} L${xy[xy.length - 1][0].toFixed(1)} ${padT + innerH} L${xy[0][0].toFixed(1)} ${padT + innerH} Z`;

  svg.appendChild(svgEl('path', { d: area, fill: `url(#${gradId})` }));
  const stroke = svgEl('path', {
    d: line, fill: 'none', stroke: accent, 'stroke-width': 2.4,
    'stroke-linecap': 'round', 'stroke-linejoin': 'round',
  });
  svg.appendChild(stroke);

  xy.forEach(([x, y], i) => {
    if (points[i].value > 0) {
      svg.appendChild(svgEl('circle', {
        cx: x, cy: y, r: 3, fill: 'var(--surface)', stroke: accent, 'stroke-width': 2,
      }));
    }
    if (points.length <= 16 || i % 3 === 0) {
      const label = svgEl('text', { x, y: H - 6, 'text-anchor': 'middle' });
      label.textContent = points[i].label;
      svg.appendChild(label);
    }
  });

  host.appendChild(svg);
}

/* ── Диаграммаи ҳалқавӣ ── */
function donutChart(host, segments) {
  host.innerHTML = '';
  const items = segments.filter((s) => s.value > 0);
  const total = items.reduce((sum, s) => sum + s.value, 0);

  if (!total) { host.innerHTML = emptyState('Маълумот нест', ''); return; }

  const size = 190, r = 72, cx = size / 2, cy = size / 2, width = 22;
  const circ = 2 * Math.PI * r;

  const wrap = document.createElement('div');
  wrap.className = 'donut-wrap';

  const svg = svgEl('svg', { class: 'chart', viewBox: `0 0 ${size} ${size}` });
  svg.style.maxWidth = '190px';
  svg.style.height = 'auto';

  svg.appendChild(svgEl('circle', {
    cx, cy, r, fill: 'none', stroke: 'var(--surface-3)', 'stroke-width': width,
  }));

  let offset = 0;
  items.forEach((item) => {
    const fraction = item.value / total;
    const arc = svgEl('circle', {
      cx, cy, r, fill: 'none',
      stroke: item.color, 'stroke-width': width, 'stroke-linecap': 'butt',
      'stroke-dasharray': `${(circ * fraction).toFixed(2)} ${circ.toFixed(2)}`,
      'stroke-dashoffset': (-offset).toFixed(2),
      transform: `rotate(-90 ${cx} ${cy})`,
    });
    svg.appendChild(arc);
    offset += circ * fraction;
  });

  const num = svgEl('text', {
    x: cx, y: cy - 2, 'text-anchor': 'middle',
    style: 'font-size:30px;font-weight:750;fill:var(--text)',
  });
  num.textContent = total;
  svg.appendChild(num);

  const cap = svgEl('text', {
    x: cx, y: cy + 17, 'text-anchor': 'middle',
    style: 'font-size:11px;fill:var(--text-3)',
  });
  cap.textContent = 'ҳамагӣ';
  svg.appendChild(cap);

  wrap.appendChild(svg);

  const legend = document.createElement('div');
  legend.className = 'legend';
  legend.innerHTML = items.map((item) => {
    const pct = Math.round((item.value / total) * 100);
    return `<div class="legend__item">
      <span class="legend__sw" style="background:${item.color}"></span>
      <span class="legend__name">${esc(item.label)}</span>
      <span class="legend__val">${item.value} · ${pct}%</span>
    </div>`;
  }).join('');

  host.appendChild(wrap);
  host.appendChild(legend);
}

function drawWeek(daily) {
  barChart($('#chart-week'),
    daily.map((d) => ({ label: fmtDay(d.date), value: d.count || 0 })),
    'var(--brand)');
}

async function loadCharts() {
  const data = cache.stats2 || await api('/api/stats?days=14');
  if (!data) return;
  cache.stats2 = data;
  renderCharts();
}

function renderCharts() {
  const data = cache.stats2;
  if (!data) return;
  const summary = data.summary || {};
  const daily = data.daily || [];

  donutChart($('#chart-type'), Object.entries(TYPE).map(([key, meta]) => ({
    label: meta.label,
    value: (summary.by_type || {})[key] || 0,
    color: meta.color,
  })));

  donutChart($('#chart-status'), Object.entries(STATUS).map(([key, meta]) => ({
    label: meta.label,
    value: summary[key] || 0,
    color: meta.color,
  })));

  const total = daily.reduce((sum, d) => sum + (d.count || 0), 0);
  $('#trend-note').textContent = `${total} дархост`;
  lineChart($('#chart-trend'),
    daily.map((d) => ({ label: fmtDay(d.date), value: d.count || 0 })),
    'var(--violet)');
}


/* ══════════════ Тафсилоти дархост ══════════════ */

let sheetRec = null;

function openSheet(rec) {
  sheetRec = rec;
  const type = TYPE[rec.type] || { label: rec.type, color: 'var(--text-3)' };
  const status = STATUS[rec.status] || { label: rec.status };

  const confirmedText = rec.worker_confirmed === 'yes' ? '✅ Тасдиқ кард'
    : rec.worker_confirmed === 'no' ? '⚠️ Мушкилӣ дорад' : '—';

  const rows = [
    ['Вазъият', `<span class="chip chip--${rec.status}">${esc(status.label)}</span>`],
    ['Навъ', `<span class="chip chip--${rec.type}">${esc(type.label)}</span>`],
    ['Сабаб', esc(rec.reason)],
    ['Муддат', fmtMinutes(rec.minutes)],
    ['Фиристода шуд', fmtDateTime(rec.created_at)],
  ];
  if (rec.deadline_at) rows.push(['Мӯҳлат', fmtDateTime(rec.deadline_at)]);
  if (rec.decided_by) rows.push(['Қарор аз', esc(shortName(rec.decided_by))]);
  if (rec.decided_at) rows.push(['Вақти қарор', fmtDateTime(rec.decided_at)]);
  rows.push(['Ҷавоби ҳамкор', confirmedText]);

  const actions = rec.status === 'pending'
    ? `<div class="row">
         <button class="btn btn--ok" data-act="accepted">✅ Иҷозат</button>
         <button class="btn btn--danger" data-act="rejected">✋ Рад кардан</button>
       </div>`
    : '';

  $('#sheet-body').innerHTML = `
    <div class="detail">
      <div class="detail__head">
        <div class="avatar" style="background:${type.color}22;color:${type.color}">${esc(initials(rec.name))}</div>
        <div style="min-width:0">
          <div class="detail__name">${esc(shortName(rec.name))}</div>
          <div class="detail__id">Дархост #${rec.id}</div>
        </div>
      </div>
      <div class="kv">
        ${rows.map(([k, v]) => `<div class="kv__row"><span class="kv__k">${esc(k)}</span><span class="kv__v">${v}</span></div>`).join('')}
      </div>
    </div>
    <div class="sheet__actions">
      ${actions}
      <textarea class="msgbox" id="sheet-msg" placeholder="Паём ба ҳамкор навишта, тугмаи зерро пахш кунед…"></textarea>
      <button class="btn btn--ghost btn--block" data-act="message">💬 Фиристодани паём</button>
    </div>`;

  $('#sheet').hidden = false;
  document.body.style.overflow = 'hidden';
  haptic('light');
}

function closeSheet() {
  $('#sheet').hidden = true;
  document.body.style.overflow = '';
  sheetRec = null;
}

$('#sheet').addEventListener('click', async (event) => {
  if (event.target.closest('[data-close]')) { closeSheet(); return; }

  const btn = event.target.closest('[data-act]');
  if (!btn || !sheetRec) return;

  const action = btn.dataset.act;
  btn.disabled = true;

  if (action === 'message') {
    const text = $('#sheet-msg').value.trim();
    if (!text) { toast('Аввал матн нависед', 'danger'); btn.disabled = false; return; }
    const res = await api(`/api/requests/${sheetRec.id}/message`, {
      method: 'POST', body: JSON.stringify({ text }),
    });
    btn.disabled = false;
    if (res && res.ok) { toast('Паём фиристода шуд', 'ok'); haptic('ok'); $('#sheet-msg').value = ''; }
    return;
  }

  const res = await api(`/api/requests/${sheetRec.id}/decision`, {
    method: 'POST', body: JSON.stringify({ decision: action }),
  });
  btn.disabled = false;

  if (res && res.ok) {
    toast(res.message || 'Иҷро шуд', 'ok');
    haptic('ok');
    closeSheet();
    cache = { workers: null, stats: null, stats2: null };
    if (view === 'req') loadRequests(true); else loadHome();
  }
});

document.addEventListener('click', (event) => {
  const card = event.target.closest('[data-req]');
  if (!card) return;
  const rec = known.get(Number(card.dataset.req));
  if (rec) openSheet(rec);
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !$('#sheet').hidden) closeSheet();
});


/* ══════════════ Оғоз ══════════════ */

initTelegram();
applyTheme(preferredTheme());

if (tg) {
  try { tg.onEvent('themeChanged', () => {
    if (!localStorage.getItem('sc_theme')) applyTheme(tg.colorScheme || 'dark');
  }); } catch (_) {}
}

window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => {
  if (!localStorage.getItem('sc_theme')) applyTheme(e.matches ? 'light' : 'dark');
});

// Графикҳо дар пиксели воқеӣ кашида мешаванд — ҳангоми тағйири андоза аз нав.
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (view === 'home' && cache.stats) drawWeek(cache.stats.daily || []);
    if (view === 'charts') renderCharts();
  }, 220);
});

(async function boot() {
  if (!token) { showLogin(); return; }
  const ping = await api('/api/dashboard');
  if (ping) { $('#login').hidden = true; $('#app').hidden = false; go('home'); }
  else showLogin();
})();

// версия дар поёни экрани вуруд
fetch(`${API}/api/health`).then((r) => r.json()).then((h) => {
  $('#login-foot').textContent = `SoftClub HR Control · v${h.version}`;
}).catch(() => {});

})();
