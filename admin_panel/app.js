/* ═══════════════════════════════════════════════════════════════════════
   SoftClub HR Control — панели маъмурият (v2)
   Бе китобхонаи беруна. Аввал телефон; ≥900px — менюи паҳлӯ.
   ═══════════════════════════════════════════════════════════════════════ */

(() => {
'use strict';

const API = '.';
const PAGE = 30;

/* ══════════════ Нигоҳдорӣ (localStorage метавонад манъ бошад) ══════════════ */

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (_) {} },
  del(k) { try { localStorage.removeItem(k); } catch (_) {} },
};

let token = store.get('sc_token');

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/* ══════════════ Луғатҳо ══════════════ */

const ICON = {
  home: '<svg viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/></svg>',
  req: '<svg viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
  team: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.2"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 5.2a3.2 3.2 0 0 1 0 5.6M17.5 20a6.4 6.4 0 0 0-2-4.6"/></svg>',
  stats: '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  settings: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="m5 12 5 5 9-10"/></svg>',
  clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  user: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
  inbox: '<svg viewBox="0 0 24 24"><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6Z"/></svg>',
  calendar: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>',
  trash: '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>',
  download: '<svg viewBox="0 0 24 24"><path d="M12 3v12m0 0-4-4m4 4 4-4"/><path d="M4 17v3h16v-3"/></svg>',
  select: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="m8 12 3 3 5-6"/></svg>',
  send: '<svg viewBox="0 0 24 24"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4Z"/></svg>',
  bulb: '<svg viewBox="0 0 24 24"><path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.3h6c0-1 .4-1.8 1-2.3A7 7 0 0 0 12 2Z"/></svg>',
  percent: '<svg viewBox="0 0 24 24"><path d="M19 5 5 19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></svg>',
  hourglass: '<svg viewBox="0 0 24 24"><path d="M6 2h12M6 22h12M7 2c0 6 10 6 10 10S7 16 7 22M17 2c0 6-10 6-10 10s10 4 10 10"/></svg>',
  bolt: '<svg viewBox="0 0 24 24"><path d="M13 2 3 14h9l-1 8 10-12h-9Z"/></svg>',
  alert: '<svg viewBox="0 0 24 24"><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
  lock: '<svg viewBox="0 0 24 24"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
};

const TYPE = {
  late:            { label: 'Дер мекунад',     short: 'Дер',      color: 'var(--warn)',   tag: 'warn',   emoji: '🕰' },
  absent:          { label: 'Намеояд',         short: 'Намеояд',  color: 'var(--danger)', tag: 'danger', emoji: '🌿' },
  at_work_waiting: { label: 'Ҷавоб мепурсад',  short: 'Ҷавоб',    color: 'var(--info)',   tag: 'info',   emoji: '☕' },
  leaving_early:   { label: 'Барвақт меравад', short: 'Барвақт',  color: 'var(--violet)', tag: 'violet', emoji: '🌅' },
};
const TYPE_ORDER = ['late', 'absent', 'at_work_waiting', 'leaving_early'];

const STATUS = {
  pending:   { label: 'Дар интизорӣ', tag: 'warn',   color: 'var(--warn)' },
  accepted:  { label: 'Иҷозат дода шуд', tag: 'ok', color: 'var(--ok)' },
  rejected:  { label: 'Рад шуд',      tag: 'danger', color: 'var(--danger)' },
  cancelled: { label: 'Бекор шуд',    tag: '',       color: 'var(--text-3)' },
};
const STATUS_ORDER = ['pending', 'accepted', 'rejected', 'cancelled'];

const WD = ['Дш', 'Сш', 'Чш', 'Пш', 'Ҷм', 'Шб', 'Яш'];
const WD_FULL = ['душанбе', 'сешанбе', 'чоршанбе', 'панҷшанбе', 'ҷумъа', 'шанбе', 'якшанбе'];
const MONTHS = ['январ', 'феврал', 'март', 'апрел', 'май', 'июн', 'июл', 'август', 'сентябр', 'октябр', 'ноябр', 'декабр'];

const VIEWS = [
  { id: 'home',     label: 'Асосӣ',      sub: 'Манзараи имрӯза' },
  { id: 'req',      label: 'Дархостҳо',  sub: 'Ҳамаи муроҷиатҳо' },
  { id: 'team',     label: 'Кормандон',  sub: 'Омори шахсӣ' },
  { id: 'stats',    label: 'Омор',       sub: 'Таҳлили муфассал' },
  { id: 'settings', label: 'Танзимот',   sub: 'Ҳисоб ва база' },
];

const PERIODS = [
  ['today', 'Имрӯз'], ['7', '7 рӯз'], ['30', '30 рӯз'], ['month', 'Ин моҳ'],
  ['prev', 'Моҳи гузашта'], ['all', 'Ҳама вақт'], ['custom', 'Санаҳо…'],
];

/* ══════════════ Ҳолат ══════════════ */

const S = {
  view: 'home',
  pending: 0,
  workers: [],                        // барои select-и корманд
  req: {
    q: '', type: '', status: '', period: 'all', from: '', to: '', user_id: '', sort: 'new',
    items: [], total: 0, offset: 0, busy: false, selecting: false, selected: new Set(), seq: 0,
  },
  team: { period: '30', from: '', to: '', q: '', sort: 'total', data: null, seq: 0 },
  stats: { period: '30', from: '', to: '', data: null, seq: 0 },
  inited: {},
};

const known = new Map();              // id → дархост

/* ══════════════ Telegram Mini App ══════════════ */

// Танҳо дар дохили Telegram (initData холӣ нест); дар браузери оддӣ — null
const tg = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData
  ? window.Telegram.WebApp : null;

function initTelegram() {
  if (!tg) return;
  try { tg.ready(); tg.expand(); } catch (_) {}
  try { if (tg.disableVerticalSwipes) tg.disableVerticalSwipes(); } catch (_) {}
  try { if (tg.BackButton) tg.BackButton.onClick(() => closeSheet()); } catch (_) {}
}

function haptic(kind = 'light') {
  if (!tg || !tg.HapticFeedback) return;
  try {
    if (['success', 'error', 'warning'].includes(kind)) tg.HapticFeedback.notificationOccurred(kind);
    else tg.HapticFeedback.impactOccurred(kind);
  } catch (_) {}
}

/* ══════════════ Мавзӯъ ══════════════ */

function preferredTheme() {
  const saved = store.get('sc_theme');
  if (saved === 'dark' || saved === 'light') return saved;
  if (tg && tg.colorScheme) return tg.colorScheme;
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(name) {
  document.documentElement.dataset.theme = name;
  const color = name === 'dark' ? '#0D1117' : '#F5F7FB';
  const meta = $('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', color);
  if (tg) {
    try { tg.setHeaderColor(color); tg.setBackgroundColor(color); } catch (_) {}
  }
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  store.set('sc_theme', next);
  applyTheme(next);
  haptic('light');
}

/* ══════════════ Ёрдамчиҳо ══════════════ */

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const shortName = (full) => String(full || '').split(' (@')[0].trim() || '—';
const usernameOf = (full) => { const m = String(full || '').match(/\(@([^)]+)\)/); return m ? m[1] : ''; };

function initials(full) {
  const parts = shortName(full).split(/\s+/).filter(Boolean);
  return (parts.slice(0, 2).map((p) => p[0]).join('') || '?').toUpperCase();
}

const AV_COLORS = ['#4361EE', '#7C3AED', '#DB2777', '#EA580C', '#059669', '#0891B2', '#CA8A04', '#DC2626', '#2563EB', '#9333EA'];
function avatar(name, id, cls = '') {
  const n = Math.abs(Number(id) || [...String(name)].reduce((a, c) => a + c.charCodeAt(0), 0));
  return `<div class="avatar ${cls}" style="background:${AV_COLORS[n % AV_COLORS.length]}">${esc(initials(name))}</div>`;
}

function parseDate(v) {
  if (!v) return null;
  const d = new Date(String(v).replace(' ', 'T'));
  return isNaN(d.getTime()) ? null : d;
}
const p2 = (n) => String(n).padStart(2, '0');
const ymd = (d) => `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
const todayYmd = () => ymd(new Date());

function fmtDateTime(v) {
  const d = parseDate(v);
  if (!d) return '—';
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${p2(d.getHours())}:${p2(d.getMinutes())}`;
}
function fmtClock(v) { const d = parseDate(v); return d ? `${p2(d.getHours())}:${p2(d.getMinutes())}` : '—'; }
function fmtDateShort(v) {
  const d = typeof v === 'string' ? parseDate(v.length === 10 ? v + 'T00:00:00' : v) : v;
  return d ? `${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)}` : '—';
}

function fmtRelative(v) {
  const d = parseDate(v);
  if (!d) return '—';
  const now = new Date();
  const diff = (now - d) / 60000;
  if (diff < 1) return 'ҳозир';
  if (diff < 60) return `${Math.floor(diff)} дақ пеш`;
  if (ymd(d) === ymd(now)) return `имрӯз, ${fmtClock(v)}`;
  const y = new Date(now); y.setDate(y.getDate() - 1);
  if (ymd(d) === ymd(y)) return `дирӯз, ${fmtClock(v)}`;
  const sameYear = d.getFullYear() === now.getFullYear();
  return `${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)}${sameYear ? '' : ' ' + d.getFullYear()}, ${fmtClock(v)}`;
}

function fmtMinutes(m) {
  m = Math.round(Number(m) || 0);
  if (m <= 0) return '—';
  if (m < 60) return `${m} дақ`;
  const h = Math.floor(m / 60), r = m % 60;
  return r ? `${h} с ${r} дақ` : `${h} соат`;
}
function fmtHours(m) {
  m = Number(m) || 0;
  if (m < 60) return `${Math.round(m)} дақ`;
  const h = m / 60;
  return `${h >= 10 ? Math.round(h) : h.toFixed(1).replace('.0', '')} соат`;
}
const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
const plural = (n, word) => `${n} ${word}`;

function toast(msg, kind = '') {
  const el = $('#toast');
  el.textContent = msg;
  el.className = 'toast' + (kind ? ` toast--${kind}` : '');
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 2800);
}

function emptyState(title, note = '', icon = ICON.inbox) {
  return `<div class="empty">${icon}<b>${esc(title)}</b>${note ? `<span>${esc(note)}</span>` : ''}</div>`;
}
const skel = (n, cls = '') => Array.from({ length: n }, () => `<div class="skeleton ${cls}"></div>`).join('');

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

function typeTag(t) {
  const m = TYPE[t] || { label: t, tag: '' };
  return `<span class="tag tag--${m.tag}">${m.emoji || ''} ${esc(m.label)}</span>`;
}
function statusTag(s) {
  const m = STATUS[s] || { label: s, tag: '' };
  return `<span class="tag tag--${m.tag}">${esc(m.label)}</span>`;
}

/* ══════════════ Давраҳо ══════════════ */

function periodRange(period, from, to) {
  const now = new Date();
  const d = (x) => ymd(x);
  const back = (n) => { const x = new Date(now); x.setDate(x.getDate() - n); return x; };
  switch (period) {
    case 'today': return { date_from: d(now), date_to: d(now) };
    case '7':     return { date_from: d(back(6)), date_to: d(now) };
    case '30':    return { date_from: d(back(29)), date_to: d(now) };
    case 'month': return { date_from: d(new Date(now.getFullYear(), now.getMonth(), 1)), date_to: d(now) };
    case 'prev': {
      const a = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const b = new Date(now.getFullYear(), now.getMonth(), 0);
      return { date_from: d(a), date_to: d(b) };
    }
    case 'custom': return { date_from: from || '', date_to: to || '' };
    default: return { date_from: '', date_to: '' };
  }
}

function periodLabel(period, from, to) {
  if (period === 'custom') {
    if (from && to) return `${fmtDateShort(from)} — ${fmtDateShort(to)}`;
    if (from) return `аз ${fmtDateShort(from)}`;
    if (to) return `то ${fmtDateShort(to)}`;
    return 'Ҳама вақт';
  }
  const found = PERIODS.find(([k]) => k === period);
  return found ? found[1] : '';
}

function periodChips(scope, st) {
  return `<div class="chips" data-period="${scope}">
    ${PERIODS.map(([k, l]) => `<button class="chip${st.period === k ? ' is-active' : ''}" data-p="${k}">${l}</button>`).join('')}
  </div>
  <div class="custom-range" data-range="${scope}" ${st.period === 'custom' ? '' : 'hidden'}>
    <input type="date" class="input" data-from value="${esc(st.from)}" aria-label="Аз сана">
    <input type="date" class="input" data-to value="${esc(st.to)}" aria-label="То сана">
  </div>`;
}

function bindPeriod(root, scope, st, reload) {
  const chips = $(`[data-period="${scope}"]`, root);
  const range = $(`[data-range="${scope}"]`, root);
  chips.addEventListener('click', (e) => {
    const b = e.target.closest('[data-p]');
    if (!b) return;
    st.period = b.dataset.p;
    $$('.chip', chips).forEach((c) => c.classList.toggle('is-active', c === b));
    range.hidden = st.period !== 'custom';
    haptic('light');
    if (st.period !== 'custom' || st.from || st.to) reload();
  });
  range.addEventListener('change', () => {
    st.from = $('[data-from]', range).value;
    st.to = $('[data-to]', range).value;
    reload();
  });
}

/* ══════════════ API ══════════════ */

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(API + path, { cache: 'no-store', ...options, headers });
  } catch (_) {
    toast('Алоқа бо сервер нест. Интернетро санҷед.', 'danger');
    return null;
  }
  if (res.status === 401 && !path.startsWith('/api/login')) {
    logout(true);
    return null;
  }
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = (data && data.error) || `Хатои сервер (${res.status})`;
    if (!options.quiet) toast(msg, 'danger');
    return options.raw ? { error: msg, status: res.status } : null;
  }
  return data;
}

const post = (path, body, extra = {}) => api(path, { method: 'POST', body: JSON.stringify(body || {}), ...extra });

function qs(obj) {
  const p = new URLSearchParams();
  Object.entries(obj).forEach(([k, v]) => { if (v !== '' && v != null) p.set(k, v); });
  return p.toString();
}

function download(path) {
  const url = new URL(API + path, location.href);
  url.searchParams.set('token', token || '');
  if (tg && tg.openLink) {
    try { tg.openLink(url.href); return; } catch (_) {}
  }
  const a = document.createElement('a');
  a.href = url.href;
  a.rel = 'noopener';
  a.download = '';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/* ══════════════ Вуруд / баромад ══════════════ */

function showLogin() {
  $('#app').hidden = true;
  $('#login').hidden = false;
  setTimeout(() => { const i = $('#in-login'); if (i && !i.value) i.focus(); }, 50);
}

function showApp() {
  $('#login').hidden = true;
  $('#app').hidden = false;
  go(S.view, true);
  refreshPending();
}

function logout(expired = false) {
  token = null;
  store.del('sc_token');
  S.inited = {};
  closeSheet();
  showLogin();
  if (expired) toast('Сессия тамом шуд — аз нав ворид шавед');
}

async function doLogin(e) {
  e.preventDefault();
  const login = $('#in-login').value.trim();
  const password = $('#in-pass').value;
  const errBox = $('#login-error');
  errBox.hidden = true;
  if (!login || !password) {
    errBox.textContent = 'Логин ва рамзро ворид кунед';
    errBox.hidden = false;
    return;
  }
  const btn = $('#login-btn');
  btn.classList.add('is-loading');
  btn.textContent = 'Санҷиш…';
  const res = await api('/api/login', { method: 'POST', body: JSON.stringify({ login, password }), raw: true, quiet: true });
  btn.classList.remove('is-loading');
  btn.textContent = 'Даромадан';
  if (!res || res.error) {
    errBox.textContent = (res && res.error) || 'Алоқа бо сервер нест';
    errBox.hidden = false;
    haptic('error');
    return;
  }
  token = res.token;
  store.set('sc_token', token);
  $('#in-pass').value = '';
  haptic('success');
  showApp();
}

/* ══════════════ Навигатсия ══════════════ */

function buildNav() {
  const tab = (v) => `<button class="tab" data-view="${v.id}">${ICON[v.id]}<span>${v.label}</span>${v.id === 'req' ? '<b class="badge-dot" data-badge hidden></b>' : ''}</button>`;
  const side = (v) => `<button class="side__link" data-view="${v.id}">${ICON[v.id]}<span>${v.label}</span>${v.id === 'req' ? '<b class="badge-dot" data-badge hidden></b>' : ''}</button>`;
  $('#tabbar').innerHTML = VIEWS.map(tab).join('');
  $('#side-nav').innerHTML = VIEWS.map(side).join('');
}

function go(name, force = false) {
  if (!VIEWS.find((v) => v.id === name)) name = 'home';
  const changed = S.view !== name;
  S.view = name;
  store.set('sc_view', name);
  const meta = VIEWS.find((v) => v.id === name);
  $('#view-title').textContent = meta.label;
  $('#view-sub').textContent = meta.sub;
  $$('[data-view]').forEach((b) => b.classList.toggle('is-active', b.dataset.view === name));
  $$('.view').forEach((v) => v.classList.toggle('is-active', v.id === `view-${name}`));
  if (name !== 'req') setSelecting(false);
  if (changed) window.scrollTo({ top: 0 });

  const loaders = { home: loadHome, req: initRequests, team: initTeam, stats: initStats, settings: initSettings };
  if (force || changed || !S.inited[name]) loaders[name]();
}

function refreshCurrent() {
  haptic('light');
  S.inited[S.view] = false;
  if (S.view === 'req') loadRequests(true);
  else if (S.view === 'team') loadTeam();
  else if (S.view === 'stats') loadStats();
  else go(S.view, true);
  refreshPending();
}

async function refreshPending() {
  const data = await api('/api/requests?status=pending&limit=1', { quiet: true });
  if (!data) return;
  S.pending = data.total || 0;
  $$('[data-badge]').forEach((b) => { b.hidden = !S.pending; b.textContent = S.pending > 99 ? '99+' : S.pending; });
}

/* ══════════════ Графикҳо (HTML/SVG) ══════════════ */

function colsChart(days, opts = {}) {
  if (!days || !days.length) return emptyState('Маълумот нест');
  const max = Math.max(1, ...days.map((d) => d.count));
  const n = days.length;
  const step = n <= 8 ? 1 : n <= 16 ? 2 : n <= 35 ? 5 : n <= 70 ? 10 : 30;
  const showNums = n <= 16;
  const today = todayYmd();
  const cols = days.map((d) => {
    const h = d.count ? Math.max(4, (100 * d.count) / max) : 0;
    const segs = TYPE_ORDER.map((t) => {
      const c = (d.by_type && d.by_type[t]) || 0;
      return c ? `<i style="height:${(100 * c) / (d.count || 1)}%;background:${TYPE[t].color}"></i>` : '';
    }).join('');
    const title = `${fmtDateShort(d.date)}: ${d.count}`;
    return `<div class="col${d.date === today ? ' is-today' : ''}" title="${esc(title)}">
      ${showNums && d.count ? `<span class="col__n" style="bottom:calc(${h}% + 4px)">${d.count}</span>` : ''}
      <div class="col__bar" style="height:${h}%">${segs}</div></div>`;
  }).join('');
  const axis = days.map((d, i) => {
    const dt = parseDate(d.date + 'T00:00:00');
    const label = opts.weekday ? WD[(dt.getDay() + 6) % 7] : `${dt.getDate()}.${p2(dt.getMonth() + 1)}`;
    return `<span>${i % step === 0 || i === n - 1 ? label : ''}</span>`;
  }).join('');
  return `<div class="cols" style="height:${opts.height || ''}">${cols}</div><div class="axis">${axis}</div>${opts.legend === false ? '' : typeLegend()}`;
}

function simpleCols(values, labels, color = 'var(--brand)', highlight = -1) {
  const max = Math.max(1, ...values);
  const cols = values.map((v, i) => {
    const h = v ? Math.max(4, (100 * v) / max) : 0;
    return `<div class="col${i === highlight ? ' is-today' : ''}" title="${esc(labels[i])}: ${v}">
      ${v ? `<span class="col__n" style="bottom:calc(${h}% + 4px)">${v}</span>` : ''}
      <div class="col__bar" style="height:${h}%"><i style="height:100%;background:${color}"></i></div></div>`;
  }).join('');
  return `<div class="cols" style="height:150px">${cols}</div><div class="axis">${labels.map((l) => `<span>${esc(l)}</span>`).join('')}</div>`;
}

function typeLegend() {
  return `<div class="legend">${TYPE_ORDER.map((t) => `<span><i style="background:${TYPE[t].color}"></i>${TYPE[t].label}</span>`).join('')}</div>`;
}

function donut(segments, centerValue, centerLabel) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  const R = 15.915;                                    // дарозии давра = 100
  let offset = 0;
  const arcs = total ? segments.filter((s) => s.value).map((s) => {
    const len = (100 * s.value) / total;
    const gap = segments.filter((x) => x.value).length > 1 ? 0.6 : 0;
    const arc = `<circle cx="21" cy="21" r="${R}" fill="none" stroke="${s.color}" stroke-width="5.2"
      stroke-dasharray="${Math.max(0, len - gap)} ${100 - Math.max(0, len - gap)}" stroke-dashoffset="${-offset}"/>`;
    offset += len;
    return arc;
  }).join('') : '';
  const list = segments.map((s) => `<div class="dlist__row"><i style="background:${s.color}"></i>
      <span>${esc(s.label)}</span><b>${s.value}</b><em>${pct(s.value, total)}%</em></div>`).join('');
  return `<div class="donut-wrap">
    <div class="donut"><svg viewBox="0 0 42 42"><circle cx="21" cy="21" r="${R}" fill="none" stroke="var(--surface-3)" stroke-width="5.2"/>${arcs}</svg>
      <div class="donut__c"><div><b>${esc(centerValue)}</b><small>${esc(centerLabel)}</small></div></div></div>
    <div class="dlist">${list}</div></div>`;
}

function hbars(items, opts = {}) {
  if (!items.length) return emptyState(opts.empty || 'Маълумот нест');
  const max = Math.max(1, ...items.map((i) => i.value));
  return `<div class="hbars">${items.map((it) => {
    const w = (100 * it.value) / max;
    const track = it.segments
      ? it.segments.filter((s) => s.value).map((s) => `<i style="width:${(w * s.value) / (it.value || 1)}%;background:${s.color}"></i>`).join('')
      : `<i style="width:${w}%;background:${it.color || 'var(--brand)'}"></i>`;
    return `<div class="hbar">
      <div class="hbar__top"><span class="hbar__label" title="${esc(it.label)}">${esc(it.label)}</span>
        <span class="hbar__val"><b>${it.value}</b>${it.extra ? ` · ${esc(it.extra)}` : ''}</span></div>
      <div class="hbar__track">${track}</div>
      ${it.sub ? `<div class="hbar__sub">${esc(it.sub)}</div>` : ''}</div>`;
  }).join('')}</div>`;
}

function typeStackbar(obj, cls = '') {
  const total = TYPE_ORDER.reduce((a, t) => a + (obj[t] || 0), 0);
  if (!total) return `<div class="stackbar ${cls}"></div>`;
  return `<div class="stackbar ${cls}">${TYPE_ORDER.map((t) => obj[t]
    ? `<i style="width:${(100 * obj[t]) / total}%;background:${TYPE[t].color}" title="${TYPE[t].label}: ${obj[t]}"></i>` : '').join('')}</div>`;
}

function kpi(label, value, sub, icon, tone = '', action = '') {
  const tag = action ? 'button' : 'div';
  return `<${tag} class="kpi ${tone ? 'kpi--' + tone : ''}" ${action}>
    <div class="kpi__top"><span class="kpi__label">${esc(label)}</span><span class="kpi__ico">${icon}</span></div>
    <div class="kpi__value">${esc(value)}</div>
    ${sub ? `<div class="kpi__sub">${esc(sub)}</div>` : ''}</${tag}>`;
}

function reasonItems(reasons, limit = 12) {
  const total = reasons.reduce((a, r) => a + r.count, 0);
  return reasons.slice(0, limit).map((r) => ({
    label: r.reason,
    value: r.count,
    extra: `${pct(r.count, total)}%`,
    segments: TYPE_ORDER.map((t) => ({ value: r.by_type[t] || 0, color: TYPE[t].color })),
    sub: TYPE_ORDER.filter((t) => r.by_type[t]).map((t) => `${TYPE[t].short} ${r.by_type[t]}`).join(' · ')
      + (r.minutes ? ` · ${fmtHours(r.minutes)}` : ''),
  }));
}

/* ══════════════ Карточкаи дархост ══════════════ */

function requestCard(rec, opts = {}) {
  known.set(rec.id, rec);
  const sel = S.req.selected.has(rec.id);
  const minutes = rec.minutes ? `<span class="tag">${ICON.clock.replace('<svg', '<svg style="width:13px;height:13px"')} ${fmtMinutes(rec.minutes)}</span>` : '';
  const quick = opts.quick && rec.status === 'pending' ? `<div class="rq__quick">
      <button class="btn btn--soft-ok btn--sm" data-decide="accepted" data-id="${rec.id}">${ICON.check} Иҷозат</button>
      <button class="btn btn--soft-danger btn--sm" data-decide="rejected" data-id="${rec.id}">${ICON.x} Рад</button></div>` : '';
  return `<div class="rq${sel ? ' is-selected' : ''}" role="button" tabindex="0" data-rid="${rec.id}">
    <span class="rq__check">${ICON.check}</span>
    ${avatar(rec.name, rec.user_id)}
    <div class="rq__main">
      <div class="rq__top"><span class="rq__name">${esc(shortName(rec.name))}</span><span class="rq__id">#${rec.id}</span></div>
      <div class="rq__meta">${typeTag(rec.type)}${minutes}</div>
      <div class="rq__reason">${esc(rec.reason)}</div>
      <div class="rq__meta">${statusTag(rec.status)}<span class="rq__time">${esc(fmtRelative(rec.created_at))}</span></div>
      ${quick}
    </div></div>`;
}

function bindCards(root) {
  root.addEventListener('click', async (e) => {
    const dec = e.target.closest('[data-decide]');
    if (dec) {
      e.stopPropagation();
      await decide(Number(dec.dataset.id), dec.dataset.decide, dec);
      return;
    }
    const card = e.target.closest('[data-rid]');
    if (!card) return;
    const id = Number(card.dataset.rid);
    if (S.req.selecting && root.id === 'req-list') {
      toggleSelect(id, card);
      return;
    }
    openRequest(id);
  });
  root.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.matches('[data-rid]')) e.target.click();
  });
}

async function decide(id, decision, btn) {
  if (btn) btn.classList.add('is-loading');
  const res = await post(`/api/requests/${id}/decision`, { decision }, { raw: true });
  if (btn) btn.classList.remove('is-loading');
  if (!res || res.error) { haptic('error'); return false; }
  haptic('success');
  toast(decision === 'accepted' ? '✅ Иҷозат дода шуд — ба корманд хабар рафт' : '✋ Рад карда шуд — ба корманд хабар рафт', 'ok');
  S.inited = { settings: S.inited.settings };
  refreshPending();
  if (S.view === 'home') loadHome();
  if (S.view === 'req') loadRequests(true);
  return true;
}

/* ══════════════ АСОСӢ ══════════════ */

async function loadHome() {
  S.inited.home = true;
  const root = $('#view-home');
  const now = new Date();
  const hour = now.getHours();
  const hello = hour < 12 ? 'Субҳ ба хайр' : hour < 18 ? 'Рӯз ба хайр' : 'Шом ба хайр';
  if (!root.dataset.built) {
    root.innerHTML = `
      <div class="hello"><h2>${hello} 👋</h2><p>${WD_FULL[(now.getDay() + 6) % 7]}, ${now.getDate()} ${MONTHS[now.getMonth()]}</p></div>
      <div class="kpis" id="home-kpis">${skel(4, 'skeleton--sm')}</div>
      <div class="grid-2">
        <div class="card" id="home-pending-card">
          <div class="card__head"><h2>Интизори қарор</h2><span class="card__note" id="home-pending-n"></span><button class="linkbtn" data-goto-pending>Ҳама ›</button></div>
          <div class="card__body"><div class="list" id="home-pending">${skel(2)}</div></div>
        </div>
        <div class="card">
          <div class="card__head"><h2>7 рӯзи охир</h2><span class="card__note" id="home-week-note"></span></div>
          <div class="card__body" id="home-week">${skel(1)}</div>
        </div>
        <div class="card span-2">
          <div class="card__head"><h2>Дархостҳои охирин</h2><button class="linkbtn" data-goto="req">Ҳама ›</button></div>
          <div class="card__body"><div class="list" id="home-recent">${skel(3)}</div></div>
        </div>
      </div>`;
    root.dataset.built = '1';
    bindCards($('#home-pending'));
    bindCards($('#home-recent'));
  }
  if (!root.dataset.bound) {
    root.dataset.bound = '1';
    root.addEventListener('click', (e) => {
      if (e.target.closest('[data-goto-pending]')) { openRequestsWith({ status: 'pending' }); return; }
      const g = e.target.closest('[data-goto]');
      if (g) go(g.dataset.goto);
      const k = e.target.closest('[data-kpi]');
      if (!k) return;
      const key = k.dataset.kpi;
      if (key === 'pending') openRequestsWith({ status: 'pending' });
      else if (key === 'week') {
        const now = new Date();
        const monday = new Date(now); monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
        openRequestsWith({ period: 'custom', date_from: ymd(monday), date_to: ymd(now) });
      } else openRequestsWith({ period: key, date_from: '' });
    });
  }

  const [dash, pending] = await Promise.all([
    api('/api/dashboard'),
    api('/api/requests?status=pending&limit=20&sort=old'),
  ]);
  if (!dash) return;

  $('#home-kpis').innerHTML = [
    kpi('Имрӯз', dash.today, 'дархости нав', ICON.calendar, 'info', 'data-kpi="today"'),
    kpi('Интизори қарор', dash.pending, dash.pending ? 'ҷавоб диҳед' : 'ҳамааш ҳал шуд', ICON.hourglass, dash.pending ? 'warn' : 'ok', 'data-kpi="pending"'),
    kpi('Ин ҳафта', dash.week, 'аз душанбе', ICON.stats, '', 'data-kpi="week"'),
    kpi('Ин моҳ', dash.month, `ҳамагӣ ${dash.total} · ${dash.people} нафар`, ICON.team, 'violet', 'data-kpi="month"'),
  ].join('');

  const items = (pending && pending.items) || [];
  $('#home-pending-n').textContent = items.length ? `${pending.total} адад` : '';
  $('#home-pending').innerHTML = items.length
    ? items.slice(0, 5).map((r) => requestCard(r, { quick: true })).join('')
      + (items.length > 5 ? `<button class="btn btn--ghost btn--block" data-goto-pending>Боз ${(pending.total || items.length) - 5} дархости интизор ›</button>` : '')
    : emptyState('Ҳамаи дархостҳо ҳал шудаанд', 'Дархости интизори қарор нест', ICON.check);

  const week = dash.daily || [];
  const weekTotal = week.reduce((a, d) => a + d.count, 0);
  $('#home-week-note').textContent = `${weekTotal} дархост`;
  $('#home-week').innerHTML = colsChart(week, { weekday: true });

  const recent = dash.recent || [];
  $('#home-recent').innerHTML = recent.length
    ? recent.slice(0, 8).map((r) => requestCard(r)).join('')
    : emptyState('Ҳанӯз дархост нест', 'Вақте кормандон дархост фиристанд, ин ҷо пайдо мешавад');
}

function openRequestsWith(filters) {
  Object.assign(S.req, { q: '', type: '', status: '', period: 'all', from: '', to: '', user_id: '', sort: 'new' }, filters);
  if (filters.date_from !== undefined) {
    S.req.period = filters.period || 'custom';
    if (S.req.period === 'custom') { S.req.from = filters.date_from; S.req.to = filters.date_to; }
  }
  S.inited.req = false;
  $('#view-req').dataset.built = '';
  go('req', true);
}

/* ══════════════ ДАРХОСТҲО ══════════════ */

async function ensureWorkers() {
  if (S.workers.length) return S.workers;
  const data = await api('/api/workers', { quiet: true });
  S.workers = (data || []).map((w) => ({ id: w.user_id, name: shortName(w.name), total: w.total }))
    .sort((a, b) => a.name.localeCompare(b.name));
  return S.workers;
}

async function initRequests() {
  S.inited.req = true;
  const root = $('#view-req');
  const st = S.req;
  if (!root.dataset.built) {
    root.innerHTML = `
      <div class="toolbar">
        <label class="search">${ICON.search}
          <input id="rq-q" type="search" placeholder="Ном ё сабабро ҷустуҷӯ кунед…" autocomplete="off" value="${esc(st.q)}">
          <button class="search__clear" id="rq-clear" aria-label="Тоза" ${st.q ? '' : 'hidden'}>${ICON.x}</button>
        </label>
      </div>
      <div class="chips" id="rq-types">
        <button class="chip" data-t="">Ҳама навъҳо</button>
        ${TYPE_ORDER.map((t) => `<button class="chip" data-t="${t}"><span class="cdot" style="background:${TYPE[t].color}"></span>${TYPE[t].label}</button>`).join('')}
      </div>
      <div class="chips" id="rq-status">
        <button class="chip" data-s="">Ҳама вазъиятҳо</button>
        ${STATUS_ORDER.map((s) => `<button class="chip" data-s="${s}">${STATUS[s].label}</button>`).join('')}
      </div>
      ${periodChips('req', st)}
      <div class="toolbar__row">
        <select class="input" id="rq-user" aria-label="Корманд"><option value="">Ҳама кормандон</option></select>
        <select class="input" id="rq-sort" aria-label="Тартиб">
          <option value="new">↓ Аввал навҳо</option>
          <option value="old">↑ Аввал кӯҳнаҳо</option>
          <option value="minutes">⏳ Аз рӯи вақт</option>
          <option value="name">А–Я аз рӯи ном</option>
        </select>
      </div>
      <div class="resultbar">
        <span id="rq-count">…</span>
        <div class="resultbar__actions">
          <button class="btn btn--ghost btn--sm" id="rq-reset" hidden>${ICON.x} Филтрҳо</button>
          <button class="btn btn--ghost btn--sm" id="rq-select">${ICON.select} Интихоб</button>
          <button class="btn btn--ghost btn--sm" id="rq-export">${ICON.download} CSV</button>
          <button class="btn btn--soft-danger btn--sm" id="rq-delall" title="Нест кардани ҳамаи ёфтшудаҳо">${ICON.trash}</button>
        </div>
      </div>
      <div class="list" id="req-list"></div>
      <button class="btn btn--ghost btn--block" id="rq-more" hidden>Боз нишон диҳед</button>`;
    root.dataset.built = '1';

    const reload = () => loadRequests(true);
    const qInput = $('#rq-q');
    qInput.addEventListener('input', debounce(() => {
      st.q = qInput.value.trim();
      $('#rq-clear').hidden = !st.q;
      reload();
    }, 350));
    $('#rq-clear').addEventListener('click', (e) => { e.preventDefault(); qInput.value = ''; st.q = ''; $('#rq-clear').hidden = true; reload(); });
    $('#rq-types').addEventListener('click', (e) => { const b = e.target.closest('[data-t]'); if (!b) return; st.type = b.dataset.t; syncReqChips(); haptic('light'); reload(); });
    $('#rq-status').addEventListener('click', (e) => { const b = e.target.closest('[data-s]'); if (!b) return; st.status = b.dataset.s; syncReqChips(); haptic('light'); reload(); });
    bindPeriod(root, 'req', st, reload);
    $('#rq-user').addEventListener('change', (e) => { st.user_id = e.target.value; reload(); });
    $('#rq-sort').addEventListener('change', (e) => { st.sort = e.target.value; reload(); });
    $('#rq-more').addEventListener('click', () => loadRequests(false));
    $('#rq-reset').addEventListener('click', () => openRequestsWith({}));
    $('#rq-select').addEventListener('click', () => setSelecting(!st.selecting));
    $('#rq-export').addEventListener('click', () => download(`/api/export.csv?${qs(reqFilters())}`));
    $('#rq-delall').addEventListener('click', deleteFiltered);
    bindCards($('#req-list'));
  }
  syncReqChips();
  const workers = await ensureWorkers();
  const sel = $('#rq-user');
  sel.innerHTML = '<option value="">Ҳама кормандон</option>' +
    workers.map((w) => `<option value="${w.id}">${esc(w.name)} (${w.total})</option>`).join('');
  sel.value = st.user_id || '';
  $('#rq-sort').value = st.sort;
  loadRequests(true);
}

function syncReqChips() {
  $$('#rq-types .chip').forEach((c) => c.classList.toggle('is-active', c.dataset.t === S.req.type));
  $$('#rq-status .chip').forEach((c) => c.classList.toggle('is-active', c.dataset.s === S.req.status));
  const chips = $('[data-period="req"]');
  if (chips) $$('.chip', chips).forEach((c) => c.classList.toggle('is-active', c.dataset.p === S.req.period));
  const range = $('[data-range="req"]');
  if (range) {
    range.hidden = S.req.period !== 'custom';
    $('[data-from]', range).value = S.req.from || '';
    $('[data-to]', range).value = S.req.to || '';
  }
}

function reqFilters() {
  const st = S.req;
  return { q: st.q, type: st.type, status: st.status, user_id: st.user_id, ...periodRange(st.period, st.from, st.to) };
}

function hasFilters() {
  const st = S.req;
  return Boolean(st.q || st.type || st.status || st.user_id || (st.period !== 'all' && (st.period !== 'custom' || st.from || st.to)));
}

async function loadRequests(reset) {
  const st = S.req;
  if (reset) { st.offset = 0; st.items = []; }
  const seq = ++st.seq;
  const list = $('#req-list');
  if (reset) list.innerHTML = skel(4);
  $('#rq-more').hidden = true;
  const data = await api(`/api/requests?${qs({ ...reqFilters(), sort: st.sort, limit: PAGE, offset: st.offset })}`);
  if (seq !== st.seq) return;                       // ҷавоби кӯҳна
  if (!data) { list.innerHTML = emptyState('Бор нашуд', 'Навсозӣ кунед'); return; }
  st.total = data.total;
  st.items = reset ? data.items : st.items.concat(data.items);
  st.offset = st.items.length;
  $('#rq-count').innerHTML = `Ёфт шуд: <b>${st.total}</b>`;
  $('#rq-reset').hidden = !hasFilters();
  $('#rq-delall').hidden = !st.total;
  list.classList.toggle('is-selecting', st.selecting);
  list.innerHTML = st.items.length
    ? st.items.map((r) => requestCard(r)).join('')
    : emptyState('Чизе ёфт нашуд', hasFilters() ? 'Филтрҳоро иваз кунед ё тоза намоед' : 'Ҳанӯз дархост нест', ICON.search);
  $('#rq-more').hidden = st.items.length >= st.total;
  if (!$('#rq-more').hidden) $('#rq-more').textContent = `Боз нишон диҳед (${st.total - st.items.length})`;
  updateSelbar();
}

/* ── Интихоб ва нест кардан ── */

function setSelecting(on) {
  S.req.selecting = on;
  if (!on) S.req.selected.clear();
  const list = $('#req-list');
  if (list) {
    list.classList.toggle('is-selecting', on);
    $$('.rq', list).forEach((c) => c.classList.remove('is-selected'));
  }
  const b = $('#rq-select');
  if (b) b.classList.toggle('btn--soft', on);
  updateSelbar();
}

function toggleSelect(id, card) {
  const set = S.req.selected;
  if (set.has(id)) set.delete(id); else set.add(id);
  card.classList.toggle('is-selected', set.has(id));
  haptic('light');
  updateSelbar();
}

function updateSelbar() {
  const bar = $('#selbar');
  bar.hidden = !(S.req.selecting && S.view === 'req');
  $('#sel-count').textContent = `${S.req.selected.size} интихоб`;
}

async function deleteSelected() {
  const ids = [...S.req.selected];
  if (!ids.length) { toast('Аввал дархостҳоро интихоб кунед'); return; }
  const needPass = ids.length > 20;
  const ok = await confirmDialog({
    title: `${ids.length} дархост нест карда шавад?`,
    text: 'Ин амал бозгашт надорад. Пеш аз нест кардан нусхаи эҳтиётии база худкор сохта мешавад.',
    okText: 'Нест кардан', danger: true, password: needPass,
  });
  if (!ok) return;
  const res = await post('/api/requests/delete', { ids, password: ok.password });
  if (!res) return;
  haptic('success');
  toast(res.message, 'ok');
  setSelecting(false);
  afterDataChange();
}

async function deleteFiltered() {
  const st = S.req;
  if (!st.total) return;
  const ok = await confirmDialog({
    title: `Ҳамаи ${st.total} дархости ёфтшуда нест шавад?`,
    text: hasFilters()
      ? 'Ҳамаи дархостҳое, ки ба филтрҳои ҷорӣ мувофиқанд, нест мешаванд. Нусхаи эҳтиётӣ худкор сохта мешавад.'
      : 'Филтр интихоб нашудааст — ҲАМАИ дархостҳо нест мешаванд! Нусхаи эҳтиётӣ худкор сохта мешавад.',
    okText: 'Нест кардан', danger: true, password: true,
  });
  if (!ok) return;
  const res = await post('/api/requests/delete', { filters: reqFilters(), password: ok.password });
  if (!res) return;
  haptic('success');
  toast(res.message, 'ok');
  afterDataChange();
}

function afterDataChange() {
  S.workers = [];
  S.team.data = null;
  S.stats.data = null;
  S.inited = { settings: S.inited.settings };
  $('#view-home').dataset.built = '';
  refreshPending();
  go(S.view, true);
}

/* ══════════════ Тафсилоти дархост ══════════════ */

async function openRequest(id) {
  let rec = known.get(id);
  if (!rec) rec = await api(`/api/requests/${id}`);
  if (!rec) return;
  const t = TYPE[rec.type] || { label: rec.type };
  const confirmed = { yes: '✅ Бале, ҳамааш хуб', no: '⚠️ Не / ҷавоб надод' }[rec.worker_confirmed] || '—';
  const rows = [
    ['Навъ', `${t.emoji || ''} ${t.label}`],
    rec.minutes ? ['Вақт', `${fmtMinutes(rec.minutes)}${rec.deadline_at ? ` · то ${fmtClock(rec.deadline_at)}` : ''}`] : null,
    ['Фиристода шуд', fmtDateTime(rec.created_at)],
    ['Вазъият', STATUS[rec.status] ? STATUS[rec.status].label : rec.status],
    rec.decided_by ? ['Қарор кард', shortName(rec.decided_by)] : null,
    rec.decided_at && rec.status !== 'pending' ? ['Вақти қарор', fmtDateTime(rec.decided_at)] : null,
    rec.status === 'accepted' && rec.minutes ? ['Тасдиқи корманд', confirmed] : null,
  ].filter(Boolean);
  const uname = usernameOf(rec.name);

  openSheet(`
    <div class="detail-head">${avatar(rec.name, rec.user_id, 'avatar--lg')}
      <div><b>${esc(shortName(rec.name))}</b><small>${uname ? '@' + esc(uname) + ' · ' : ''}Дархост #${rec.id}</small></div></div>
    <div class="rq__meta">${typeTag(rec.type)}${statusTag(rec.status)}</div>
    <div class="quote">${esc(rec.reason)}</div>
    <div class="info">${rows.map(([k, v]) => `<div class="info__row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')}</div>
    ${rec.status === 'pending' ? `<div class="sheet__actions">
      <button class="btn btn--ok btn--lg" data-sd="accepted">${ICON.check} Иҷозат</button>
      <button class="btn btn--danger btn--lg" data-sd="rejected">${ICON.x} Рад</button></div>` : ''}
    <div class="section-title">Паём ба корманд</div>
    <div class="field"><textarea id="sh-msg" maxlength="2000" placeholder="Масалан: Хуб, фардо барвақттар биёед"></textarea></div>
    <button class="btn btn--soft btn--block" id="sh-send">${ICON.send} Фиристодан ба Telegram</button>
    <div class="sheet__actions">
      <button class="btn btn--ghost" id="sh-worker">${ICON.user} Корманд</button>
      <button class="btn btn--soft-danger" id="sh-del">${ICON.trash} Нест кардан</button>
    </div>`);

  $$('[data-sd]').forEach((b) => b.addEventListener('click', async () => {
    if (await decide(rec.id, b.dataset.sd, b)) closeSheet();
  }));
  $('#sh-send').addEventListener('click', async () => {
    const text = $('#sh-msg').value.trim();
    if (!text) { toast('Матни паёмро нависед'); return; }
    const btn = $('#sh-send');
    btn.classList.add('is-loading');
    const res = await post(`/api/requests/${rec.id}/message`, { text });
    btn.classList.remove('is-loading');
    if (res) { haptic('success'); toast('✉️ Паём ба корманд фиристода шуд', 'ok'); $('#sh-msg').value = ''; }
  });
  $('#sh-worker').addEventListener('click', () => openWorker(rec.user_id));
  $('#sh-del').addEventListener('click', async () => {
    const ok = await confirmDialog({
      title: `Дархости #${rec.id} нест шавад?`,
      text: `${shortName(rec.name)} · ${t.label}. Ин амал бозгашт надорад.`,
      okText: 'Нест кардан', danger: true,
    });
    if (!ok) return;
    const res = await api(`/api/requests/${rec.id}`, { method: 'DELETE' });
    if (!res) return;
    known.delete(rec.id);
    haptic('success');
    toast(res.message, 'ok');
    closeSheet();
    afterDataChange();
  });
}

/* ══════════════ КОРМАНДОН ══════════════ */

function initTeam() {
  S.inited.team = true;
  const root = $('#view-team');
  const st = S.team;
  if (!root.dataset.built) {
    root.innerHTML = `
      <div class="toolbar">
        <label class="search">${ICON.search}<input id="tm-q" type="search" placeholder="Ҷустуҷӯи корманд…" autocomplete="off"></label>
      </div>
      ${periodChips('team', st)}
      <div class="toolbar__row">
        <select class="input" id="tm-sort" aria-label="Тартиб">
          <option value="total">Бештарин дархост</option>
          <option value="late">Бештар дер мекунад</option>
          <option value="late_minutes">Бештарин дақиқаи дерӣ</option>
          <option value="absent">Бештар намеояд</option>
          <option value="rejected">Бештар рад шуда</option>
          <option value="name">А–Я аз рӯи ном</option>
          <option value="last">Охирин фаъолият</option>
        </select>
        <div class="resultbar" id="tm-count" style="justify-content:flex-end"></div>
      </div>
      <div class="people" id="tm-list">${skel(4)}</div>`;
    root.dataset.built = '1';
    $('#tm-q').addEventListener('input', debounce((e) => { st.q = e.target.value.trim().toLowerCase(); renderTeam(); }, 200));
    $('#tm-sort').addEventListener('change', (e) => { st.sort = e.target.value; renderTeam(); });
    bindPeriod(root, 'team', st, loadTeam);
    $('#tm-list').addEventListener('click', (e) => {
      const c = e.target.closest('[data-uid]');
      if (c) openWorker(Number(c.dataset.uid));
    });
  }
  loadTeam();
}

async function loadTeam() {
  const st = S.team;
  const seq = ++st.seq;
  $('#tm-list').innerHTML = skel(4);
  const data = await api(`/api/workers?${qs(periodRange(st.period, st.from, st.to))}`);
  if (seq !== st.seq) return;
  st.data = data || [];
  renderTeam();
}

function renderTeam() {
  const st = S.team;
  let rows = (st.data || []).slice();
  if (st.q) rows = rows.filter((w) => String(w.name || '').toLowerCase().includes(st.q) || String(w.username || '').toLowerCase().includes(st.q));
  const by = {
    total: (a, b) => b.total - a.total,
    late: (a, b) => b.late - a.late || b.total - a.total,
    late_minutes: (a, b) => b.late_minutes - a.late_minutes,
    absent: (a, b) => b.absent - a.absent || b.total - a.total,
    rejected: (a, b) => b.rejected - a.rejected || b.total - a.total,
    name: (a, b) => shortName(a.name).localeCompare(shortName(b.name)),
    last: (a, b) => String(b.last_at).localeCompare(String(a.last_at)),
  }[st.sort] || ((a, b) => b.total - a.total);
  rows.sort(by);

  $('#tm-count').innerHTML = `<span><b>${rows.length}</b> нафар · ${esc(periodLabel(st.period, st.from, st.to))}</span>`;
  $('#tm-list').innerHTML = rows.length ? rows.map((w, i) => `
    <button class="person" data-uid="${w.user_id}">
      <div class="person__head">
        <span class="rank">${i + 1}</span>
        ${avatar(w.name, w.user_id)}
        <div class="person__who"><b>${esc(shortName(w.name))}</b><small>${w.username ? '@' + esc(w.username) + ' · ' : ''}охирин: ${esc(fmtRelative(w.last_at))}</small></div>
        <div class="person__total"><b>${w.total}</b><small>дархост</small></div>
      </div>
      ${typeStackbar({ late: w.late, absent: w.absent, at_work_waiting: w.at_work_waiting, leaving_early: w.leaving_early })}
      <div class="person__nums">
        <div class="person__num"><b style="color:var(--warn)">${w.late}</b><small>Дер</small></div>
        <div class="person__num"><b style="color:var(--danger)">${w.absent}</b><small>Намеояд</small></div>
        <div class="person__num"><b style="color:var(--info)">${w.at_work_waiting}</b><small>Ҷавоб</small></div>
        <div class="person__num"><b style="color:var(--violet)">${w.leaving_early}</b><small>Барвақт</small></div>
      </div>
      <div class="person__foot">
        ${w.late_minutes ? `<span>${ICON.clock} дерӣ: ${fmtHours(w.late_minutes)}</span>` : ''}
        ${w.accept_rate != null ? `<span>${ICON.percent} иҷозат: ${w.accept_rate}%</span>` : ''}
        ${w.top_reason ? `<span>${ICON.bulb} ${esc(w.top_reason)}${w.top_reason_count > 1 ? ` ×${w.top_reason_count}` : ''}</span>` : ''}
      </div>
    </button>`).join('')
    : emptyState(st.q ? 'Корманд ёфт нашуд' : 'Дар ин давра дархост нест', st.q ? 'Номи дигарро санҷед' : 'Давраи дигарро интихоб кунед', ICON.team);
}

async function openWorker(uid) {
  const st = S.team;
  const range = S.view === 'team' ? periodRange(st.period, st.from, st.to) : { date_from: '', date_to: '' };
  const label = S.view === 'team' ? periodLabel(st.period, st.from, st.to) : 'Ҳама вақт';
  openSheet(skel(3));
  const d = await api(`/api/workers/${uid}?${qs(range)}`);
  if (!d) { closeSheet(); return; }
  const s = d.summary;
  const typeRows = TYPE_ORDER.map((t) => ({
    label: `${TYPE[t].emoji} ${TYPE[t].label}`, value: d.by_type[t].count, color: TYPE[t].color,
    extra: d.by_type[t].minutes ? fmtHours(d.by_type[t].minutes) : '',
  }));
  const wdMax = d.weekday.indexOf(Math.max(...d.weekday));

  const insights = [];
  if (s.total) {
    const topType = TYPE_ORDER.slice().sort((a, b) => d.by_type[b].count - d.by_type[a].count)[0];
    insights.push(`Аксаран: <b>${TYPE[topType].label.toLowerCase()}</b> (${pct(d.by_type[topType].count, s.total)}%)`);
    if (d.reasons[0]) insights.push(`Сабаби асосӣ: <b>${esc(d.reasons[0].reason)}</b> — ${d.reasons[0].count} бор`);
    if (Math.max(...d.weekday) > 0) insights.push(`Рӯзи бештар: <b>${WD_FULL[wdMax]}</b> (${d.weekday[wdMax]} дархост)`);
    if (s.late_minutes) insights.push(`Ҳамагӣ дер кардааст: <b>${fmtHours(s.late_minutes)}</b>`);
    if (d.extra_delays) insights.push(`Пас аз мӯҳлат боз дер кард: <b>${d.extra_delays} бор</b>`);
  }

  $('#sheet-body').innerHTML = `
    <div class="detail-head">${avatar(d.name, d.user_id, 'avatar--lg')}
      <div><b>${esc(shortName(d.name))}</b><small>${d.username ? '@' + esc(d.username) + ' · ' : ''}${esc(label)}</small></div></div>
    <div class="split">
      <div class="mini"><b>${s.total}</b><small>дархост</small></div>
      <div class="mini"><b>${s.accept_rate != null ? s.accept_rate + '%' : '—'}</b><small>иҷозат гирифт</small></div>
      <div class="mini"><b>${fmtHours(s.late_minutes)}</b><small>ҳамагӣ дерӣ</small></div>
      <div class="mini"><b>${s.avg_minutes ? fmtMinutes(s.avg_minutes) : '—'}</b><small>миёна дар як дархост</small></div>
    </div>
    ${insights.length ? `<div class="insights">${insights.map((t) => `<div class="insight">${ICON.bulb}<span>${t}</span></div>`).join('')}</div>` : ''}
    <div class="section-title">Навъҳо</div>
    ${hbars(typeRows)}
    <div class="section-title">Сабабҳо</div>
    ${hbars(reasonItems(d.reasons, 10), { empty: 'Сабаб нест' })}
    <div class="section-title">Рӯзҳои ҳафта</div>
    ${simpleCols(d.weekday, WD, 'var(--brand)', Math.max(...d.weekday) ? wdMax : -1)}
    <div class="section-title">Дархостҳо (${d.items.length})</div>
    <div class="list" id="wk-items">${d.items.slice(0, 15).map((r) => requestCard(r)).join('') || emptyState('Дархост нест')}</div>
    ${d.items.length > 15 ? `<button class="btn btn--ghost btn--block" id="wk-all">Ҳамаи ${d.items.length} дархост ›</button>` : ''}
    <div class="sheet__actions">
      <button class="btn btn--ghost" id="wk-req">${ICON.req} Дар «Дархостҳо»</button>
      <button class="btn btn--soft-danger" id="wk-del">${ICON.trash} Нест кардан</button>
    </div>
    <small class="muted">Аввалин бор: ${esc(fmtDateTime(d.first_seen))} · Охирин: ${esc(fmtDateTime(d.last_seen))}</small>`;

  const goReq = () => { closeSheet(); openRequestsWith({ user_id: String(d.user_id) }); };
  $('#wk-req').addEventListener('click', goReq);
  const all = $('#wk-all');
  if (all) all.addEventListener('click', goReq);
  $('#wk-items').addEventListener('click', (e) => {
    const c = e.target.closest('[data-rid]');
    if (c) openRequest(Number(c.dataset.rid));
  });
  $('#wk-del').addEventListener('click', async () => {
    const ok = await confirmDialog({
      title: `Ҳамаи маълумоти ${shortName(d.name)} нест шавад?`,
      text: 'Ҳамаи дархостҳо ва омори ин корманд (барои ҳама вақт) нест мешаванд. Нусхаи эҳтиётӣ худкор сохта мешавад.',
      okText: 'Нест кардан', danger: true, password: true,
    });
    if (!ok) return;
    const res = await post(`/api/workers/${d.user_id}/delete`, { password: ok.password });
    if (!res) return;
    haptic('success');
    toast(res.message, 'ok');
    closeSheet();
    afterDataChange();
  });
}

/* ══════════════ ОМОР ══════════════ */

function initStats() {
  S.inited.stats = true;
  const root = $('#view-stats');
  const st = S.stats;
  if (!root.dataset.built) {
    root.innerHTML = `
      ${periodChips('stats', st)}
      <div class="resultbar"><span id="st-label"></span>
        <div class="resultbar__actions"><button class="btn btn--ghost btn--sm" id="st-export">${ICON.download} CSV</button></div></div>
      <div id="st-body" class="grid">${skel(4)}</div>`;
    root.dataset.built = '1';
    bindPeriod(root, 'stats', st, loadStats);
    $('#st-export').addEventListener('click', () => download(`/api/export.csv?${qs(periodRange(st.period, st.from, st.to))}`));
    root.addEventListener('click', (e) => {
      const w = e.target.closest('[data-uid]');
      if (w) { openWorker(Number(w.dataset.uid)); return; }
      const g = e.target.closest('[data-goto]');
      if (g) go(g.dataset.goto);
      const r = e.target.closest('[data-reason]');
      if (r) openRequestsWith({ q: r.dataset.reason, ...(st.period === 'all' ? {} : { period: st.period, from: st.from, to: st.to }) });
    });
  }
  loadStats();
}

async function loadStats() {
  const st = S.stats;
  const seq = ++st.seq;
  $('#st-body').innerHTML = skel(4);
  $('#st-label').innerHTML = `Давра: <b>${esc(periodLabel(st.period, st.from, st.to))}</b>`;
  const d = await api(`/api/analytics?${qs(periodRange(st.period, st.from, st.to))}`);
  if (seq !== st.seq) return;
  if (!d) { $('#st-body').innerHTML = emptyState('Бор нашуд'); return; }
  st.data = d;
  renderStats(d);
}

function renderStats(d) {
  const s = d.summary;
  const body = $('#st-body');
  if (!s.total) {
    body.innerHTML = `<div class="card"><div class="card__body">${emptyState('Дар ин давра дархост нест', 'Давраи дигарро интихоб кунед', ICON.stats)}</div></div>`;
    return;
  }
  const bt = d.by_type;
  const topType = TYPE_ORDER.slice().sort((a, b) => bt[b].count - bt[a].count)[0];
  const wdMax = d.weekday.indexOf(Math.max(...d.weekday));
  const hMax = d.hours.indexOf(Math.max(...d.hours));
  const topWorker = d.workers[0];
  const lateLeader = d.workers.slice().sort((a, b) => b.late_minutes - a.late_minutes)[0];

  const insights = [
    `Бештар дархостҳо — <b>${TYPE[topType].label.toLowerCase()}</b>: ${bt[topType].count} (${pct(bt[topType].count, s.total)}%)`,
    d.reasons[0] ? `Сабаби маъмултарин: <b>${esc(d.reasons[0].reason)}</b> — ${d.reasons[0].count} бор (${pct(d.reasons[0].count, s.total)}%)` : '',
    Math.max(...d.weekday) ? `Рӯзи серкортарин: <b>${WD_FULL[wdMax]}</b> (${d.weekday[wdMax]} дархост)` : '',
    Math.max(...d.hours) ? `Бештар соати <b>${p2(hMax)}:00–${p2(hMax + 1)}:00</b> менависанд` : '',
    topWorker ? `Фаъолтарин: <b>${esc(shortName(topWorker.name))}</b> — ${topWorker.total} дархост` : '',
    lateLeader && lateLeader.late_minutes ? `Бештар дер кардааст: <b>${esc(shortName(lateLeader.name))}</b> — ${fmtHours(lateLeader.late_minutes)}` : '',
  ].filter(Boolean);

  const statusItems = STATUS_ORDER.map((k) => ({
    label: STATUS[k].label, value: d.by_status[k] || 0, color: STATUS[k].color, extra: `${pct(d.by_status[k] || 0, s.total)}%`,
  }));

  const workersRows = d.workers.slice(0, 12).map((w, i) => `
    <button class="person" data-uid="${w.user_id}" style="box-shadow:none">
      <div class="person__head"><span class="rank">${i + 1}</span>${avatar(w.name, w.user_id)}
        <div class="person__who"><b>${esc(shortName(w.name))}</b>
          <small>Дер ${w.late} · Намеояд ${w.absent} · Ҷавоб ${w.at_work_waiting} · Барвақт ${w.leaving_early}</small></div>
        <div class="person__total"><b>${w.total}</b><small>${w.late_minutes ? fmtHours(w.late_minutes) : 'дархост'}</small></div></div>
      ${typeStackbar({ late: w.late, absent: w.absent, at_work_waiting: w.at_work_waiting, leaving_early: w.leaving_early })}
    </button>`).join('');

  const hourMax = Math.max(1, ...d.hours);
  const heat = d.hours.map((v, h) => {
    const a = v ? 0.15 + (0.85 * v) / hourMax : 0;
    return `<div class="heat__cell" title="${p2(h)}:00 — ${v}" style="${v ? `background:color-mix(in srgb, var(--brand) ${Math.round(a * 100)}%, var(--surface-2));color:${a > 0.55 ? '#fff' : 'var(--text)'}` : ''}">${v || ''}<small>${h}</small></div>`;
  }).join('');

  const arr = d.arrivals || {};
  body.innerHTML = `
    <div class="kpis">
      ${kpi('Ҳамагӣ дархост', s.total, `${s.people} корманд`, ICON.req, 'info')}
      ${kpi('Иҷозат дода шуд', s.accept_rate != null ? s.accept_rate + '%' : '—', `${s.accepted} иҷозат · ${s.rejected} рад`, ICON.percent, 'ok')}
      ${kpi('Вақти миёнаи ҷавоб', s.avg_response_min != null ? fmtMinutes(Math.max(1, s.avg_response_min)) : '—', 'аз фиристодан то қарор', ICON.bolt, 'violet')}
      ${kpi('Ҳамагӣ дерӣ', fmtHours(s.late_minutes), `миёна ${s.avg_minutes ? fmtMinutes(s.avg_minutes) : '—'} дар як дархост`, ICON.clock, 'warn')}
    </div>

    <div class="card"><div class="card__head"><h2>Хулосаҳо</h2></div>
      <div class="card__body"><div class="insights">${insights.map((t) => `<div class="insight">${ICON.bulb}<span>${t}</span></div>`).join('')}</div></div></div>

    <div class="grid-2">
      <div class="card"><div class="card__head"><h2>Аз рӯи навъ</h2></div>
        <div class="card__body">${donut(TYPE_ORDER.map((t) => ({ label: TYPE[t].label, value: bt[t].count, color: TYPE[t].color })), s.total, 'дархост')}
          <div class="split" style="margin-top:14px">
            ${TYPE_ORDER.filter((t) => bt[t].minutes).map((t) => `<div class="mini"><b>${fmtHours(bt[t].minutes)}</b><small>${TYPE[t].label.toLowerCase()}</small></div>`).join('')}
          </div></div></div>

      <div class="card"><div class="card__head"><h2>Қарорҳо</h2><span class="card__note">${s.pending ? s.pending + ' интизор' : ''}</span></div>
        <div class="card__body">${hbars(statusItems)}
          <div class="split" style="margin-top:14px">
            <div class="mini"><b>${s.confirmed_yes}</b><small>корманд тасдиқ кард</small></div>
            <div class="mini"><b>${s.confirmed_no}</b><small>ҷавоб надод / «не»</small></div>
            <div class="mini"><b>${arr.arrived || 0}</b><small>сари вақт расид</small></div>
            <div class="mini"><b>${arr.delayed || 0}</b><small>боз дер кард</small></div>
          </div></div></div>

      <div class="card span-2"><div class="card__head"><h2>Динамика</h2><span class="card__note">${d.daily.length} рӯз</span></div>
        <div class="card__body">${colsChart(d.daily)}</div></div>

      <div class="card"><div class="card__head"><h2>Сабабҳои асосӣ</h2><span class="card__note">${d.reasons.length} хел</span></div>
        <div class="card__body" id="st-reasons">${hbars(reasonItems(d.reasons, 12))}</div></div>

      <div class="card"><div class="card__head"><h2>Рӯзҳои ҳафта</h2></div>
        <div class="card__body">${simpleCols(d.weekday, WD, 'var(--brand)', Math.max(...d.weekday) ? wdMax : -1)}</div>
        <div class="card__head" style="padding-top:4px"><h2>Соатҳои рӯз</h2></div>
        <div class="card__body"><div class="heat">${heat}</div></div></div>

      <div class="card span-2"><div class="card__head"><h2>Рейтинги кормандон</h2><button class="linkbtn" data-goto="team">Ҳама ›</button></div>
        <div class="card__body"><div class="people">${workersRows}</div></div></div>

      ${d.deciders.length ? `<div class="card span-2"><div class="card__head"><h2>Кӣ қарор қабул кард</h2></div>
        <div class="card__body">${hbars(d.deciders.map((x) => ({
          label: shortName(x.name), value: x.total,
          segments: [{ value: x.accepted, color: 'var(--ok)' }, { value: x.rejected, color: 'var(--danger)' }],
          extra: `${x.accepted} ✓ · ${x.rejected} ✗`,
        })))}</div></div>` : ''}
    </div>`;

  // Сабаб → дархостҳои бо ҳамин сабаб
  $$('#st-reasons .hbar').forEach((el, i) => {
    const r = d.reasons[i];
    if (!r) return;
    el.dataset.reason = r.reason;
    el.style.cursor = 'pointer';
  });
}

/* ══════════════ ТАНЗИМОТ ══════════════ */

async function initSettings() {
  S.inited.settings = true;
  const root = $('#view-settings');
  root.innerHTML = skel(3);
  const [acc, health, backups] = await Promise.all([
    api('/api/account'), api('/api/health', { quiet: true }), api('/api/backups', { quiet: true }),
  ]);
  if (!acc) return;
  const theme = document.documentElement.dataset.theme;
  const poll = health && health.polling;
  const upH = health ? Math.floor(health.uptime / 3600) : 0;
  const upM = health ? Math.floor((health.uptime % 3600) / 60) : 0;
  const bList = (backups && backups.items) || [];

  root.innerHTML = `
    <div class="grid-2">
      <div class="card">
        <div class="card__head"><h2>🔐 Логин ва рамз</h2></div>
        <div class="card__body">
          <form class="stack" id="acc-form" autocomplete="off">
            <dl class="kv">
              <dt>Логини ҷорӣ</dt><dd>${esc(acc.login)}</dd>
              <dt>Охирин иваз</dt><dd>${acc.changed_at ? esc(fmtDateTime(acc.changed_at)) : 'ҳеҷ гоҳ'}</dd>
            </dl>
            ${acc.source === 'env' ? `<div class="alert alert--warn">Рамзи ҳозира аз файли танзимот аст. Онро ба рамзи нав ва боэътимод иваз кунед.</div>` : ''}
            <label class="field"><span class="field__label">Логини нав</span>
              <input id="acc-login" type="text" autocapitalize="none" autocorrect="off" spellcheck="false" value="${esc(acc.login)}" autocomplete="off"></label>
            <label class="field"><span class="field__label">Рамзи нав</span>
              <span class="field__wrap"><input id="acc-new" type="password" autocomplete="new-password" placeholder="ақаллан 6 аломат">
              <button type="button" class="field__eye" data-eye="acc-new" aria-label="Нишон додан">${ICON.lock}</button></span>
              <span class="field__hint">Холӣ монед, агар танҳо логинро иваз мекунед</span></label>
            <label class="field"><span class="field__label">Рамзи нав — такрор</span>
              <input id="acc-new2" type="password" autocomplete="new-password"></label>
            <label class="field"><span class="field__label">Рамзи ҷорӣ (барои тасдиқ)</span>
              <span class="field__wrap"><input id="acc-cur" type="password" autocomplete="current-password" required>
              <button type="button" class="field__eye" data-eye="acc-cur" aria-label="Нишон додан">${ICON.lock}</button></span></label>
            <div id="acc-err" class="alert alert--danger" hidden></div>
            <button class="btn btn--primary btn--block" type="submit" id="acc-save">Сабт кардан</button>
          </form>
        </div>
      </div>

      <div class="stack">
        <div class="card">
          <div class="card__head"><h2>💾 Маълумот</h2></div>
          <div class="card__body--flush">
            <div class="setting-row"><div class="setting-row__text"><b>Нусхаи база</b><small>Файли пурраи .db — барои нигоҳдорӣ</small></div>
              <button class="btn btn--ghost btn--sm" id="set-backup">${ICON.download}</button></div>
            <div class="setting-row"><div class="setting-row__text"><b>Экспорт ба Excel (CSV)</b><small>Ҳамаи дархостҳо</small></div>
              <button class="btn btn--ghost btn--sm" id="set-csv">${ICON.download}</button></div>
            <div class="setting-row"><div class="setting-row__text"><b>Нусхаҳои худкор</b>
              <small>${bList.length ? `${bList.length} адад · охирин: ${esc(bList[0].time)}` : 'Ҳанӯз нест — пеш аз ҳар нест кардан сохта мешавад'}</small></div></div>
          </div>
        </div>

        <div class="card">
          <div class="card__head"><h2>⚙️ Система</h2></div>
          <div class="card__body--flush">
            <div class="setting-row"><div class="setting-row__text"><b>Бот</b>
              <small><span class="status-dot" style="background:${poll && poll.ok ? 'var(--ok)' : 'var(--danger)'}"></span>${poll && poll.ok ? 'Кор мекунад' : 'Ҷавоб намедиҳад'}${health ? ` · ${upH} с ${upM} дақ бе таваққуф` : ''}</small></div></div>
            <div class="setting-row"><div class="setting-row__text"><b>Мавзӯъ</b><small>${theme === 'dark' ? 'Торик' : 'Равшан'}</small></div>
              <button class="btn btn--ghost btn--sm" data-action="theme">Иваз</button></div>
            <div class="setting-row"><div class="setting-row__text"><b>Версия</b><small>${esc(health ? `${health.version} (${health.build})` : '—')} · ${esc(health ? health.tz : '')}</small></div></div>
            <div class="setting-row"><div class="setting-row__text"><b>Баромадан</b><small>Аз ин дастгоҳ</small></div>
              <button class="btn btn--soft-danger btn--sm" data-action="logout">Баромадан</button></div>
          </div>
        </div>
      </div>

      <div class="card danger-zone span-2">
        <div class="card__head"><h2>⚠️ Тоза кардани база</h2></div>
        <div class="card__body stack">
          <p class="sheet__text" style="margin:0">Ҳар амал рамзро талаб мекунад ва пеш аз он нусхаи эҳтиётӣ худкор сохта мешавад. Логин ва рамз нест намешаванд.</p>
          <div class="setting-row" style="padding:0;border:0;flex-wrap:wrap">
            <div class="setting-row__text"><b>Дархостҳои кӯҳна</b><small>Ҳама дархостҳо то санаи интихобшуда (дохил)</small></div>
            <div style="display:flex;gap:8px;flex:1 1 260px">
              <input type="date" class="input" id="wipe-before" style="min-height:40px;flex:1" aria-label="То сана">
              <button class="btn btn--soft-danger btn--sm" id="wipe-old">Нест</button>
            </div>
          </div>
          <div class="grid-2">
            <button class="btn btn--soft-danger btn--block" id="wipe-req">${ICON.trash} Ҳамаи дархостҳо</button>
            <button class="btn btn--danger btn--block" id="wipe-all">${ICON.alert} Тозакунии пурра</button>
          </div>
        </div>
      </div>
    </div>`;

  bindEyes(root);
  $('#acc-form').addEventListener('submit', saveAccount);
  $('#set-backup').addEventListener('click', () => download('/api/backup.db'));
  $('#set-csv').addEventListener('click', () => download('/api/export.csv'));
  $('#wipe-old').addEventListener('click', () => {
    const before = $('#wipe-before').value;
    if (!before) { toast('Санаро интихоб кунед'); $('#wipe-before').focus(); return; }
    doWipe('requests', before);
  });
  $('#wipe-req').addEventListener('click', () => doWipe('requests'));
  $('#wipe-all').addEventListener('click', () => doWipe('all'));
}

async function saveAccount(e) {
  e.preventDefault();
  const err = $('#acc-err');
  err.hidden = true;
  const newLogin = $('#acc-login').value.trim();
  const p1 = $('#acc-new').value;
  const p2v = $('#acc-new2').value;
  const cur = $('#acc-cur').value;
  const fail = (m) => { err.textContent = m; err.hidden = false; haptic('error'); };
  if (!cur) return fail('Рамзи ҷориро барои тасдиқ ворид кунед');
  if (!/^[A-Za-z0-9_.@-]{3,32}$/.test(newLogin)) return fail('Логин: 3–32 аломат (ҳарфи лотинӣ, рақам, _ . @ -)');
  if (p1 && p1.length < 6) return fail('Рамзи нав бояд ақаллан 6 аломат бошад');
  if (p1 && /^\d+$/.test(p1) && p1.length < 8) return fail('Рамзи танҳо рақамӣ бояд ақаллан 8 аломат бошад');
  if (p1 !== p2v) return fail('Рамзҳои нав мувофиқ нестанд');
  const btn = $('#acc-save');
  btn.classList.add('is-loading');
  const res = await post('/api/account', { current_password: cur, new_login: newLogin, new_password: p1 }, { raw: true, quiet: true });
  btn.classList.remove('is-loading');
  if (!res || res.error) return fail((res && res.error) || 'Алоқа нест');
  token = res.token;
  store.set('sc_token', token);
  haptic('success');
  toast('✅ ' + res.message, 'ok');
  initSettings();
}

async function doWipe(scope, before) {
  const text = before
    ? `Ҳамаи дархостҳое, ки то ${fmtDateShort(before)} (дохил) фиристода шудаанд, нест мешаванд.`
    : scope === 'all'
      ? 'ҲАМАИ дархостҳо, рӯйхати кормандон ва ҳолатҳои бот нест мешаванд. Рақамгузорӣ аз #1 сар мешавад.'
      : 'ҲАМАИ дархостҳо ва омор нест мешаванд. Рӯйхати кормандон мемонад.';
  const ok = await confirmDialog({
    title: before ? 'Нест кардани дархостҳои кӯҳна' : scope === 'all' ? 'Тозакунии пурраи база' : 'Нест кардани ҳамаи дархостҳо',
    text: text + ' Нусхаи эҳтиётӣ худкор сохта мешавад.',
    okText: 'Тоза кардан', danger: true, password: true, word: 'ТОЗА',
  });
  if (!ok) return;
  const res = await post('/api/wipe', { scope, before: before || '', password: ok.password, confirm: ok.word });
  if (!res) return;
  haptic('success');
  toast(`✅ ${res.message}`, 'ok');
  afterDataChange();
}

/* ══════════════ Sheet ва тасдиқ ══════════════ */

function openSheet(html) {
  $('#sheet-body').innerHTML = html;
  $('#sheet').hidden = false;
  document.body.style.overflow = 'hidden';
  $('#sheet-body').scrollTop = 0;
  if (tg && tg.BackButton) { try { tg.BackButton.show(); } catch (_) {} }
}

function closeSheet() {
  const sheet = $('#sheet');
  if (sheet.hidden) return;
  sheet.hidden = true;
  document.body.style.overflow = '';
  if (sheet._resolve) { const r = sheet._resolve; sheet._resolve = null; r(null); }
  if (tg && tg.BackButton) { try { tg.BackButton.hide(); } catch (_) {} }
}

/** Бармегардонад {password, word} ё null. */
function confirmDialog({ title, text, okText = 'Тасдиқ', danger = false, password = false, word = '' }) {
  return new Promise((resolve) => {
    const sheet = $('#sheet');
    if (sheet._resolve) { const r = sheet._resolve; sheet._resolve = null; r(null); }
    openSheet(`
      <div class="sheet__title">${esc(title)}</div>
      <p class="sheet__text">${esc(text)}</p>
      ${password ? `<label class="field"><span class="field__label">Рамзи панел</span>
        <span class="field__wrap"><input id="cf-pass" type="password" autocomplete="current-password">
        <button type="button" class="field__eye" data-eye="cf-pass" aria-label="Нишон додан">${ICON.lock}</button></span></label>` : ''}
      ${word ? `<label class="field"><span class="field__label">Барои тасдиқ <b>${esc(word)}</b> нависед</span>
        <input id="cf-word" type="text" autocapitalize="characters" autocomplete="off" spellcheck="false"></label>` : ''}
      <div id="cf-err" class="alert alert--danger" hidden></div>
      <div class="sheet__actions">
        <button class="btn btn--ghost btn--lg" id="cf-no">Бекор</button>
        <button class="btn ${danger ? 'btn--danger' : 'btn--primary'} btn--lg" id="cf-yes">${esc(okText)}</button>
      </div>`);
    sheet._resolve = resolve;
    bindEyes($('#sheet-body'));
    const first = $('#cf-pass') || $('#cf-word');
    if (first) setTimeout(() => first.focus(), 80);
    if (danger) haptic('warning');
    $('#cf-no').addEventListener('click', () => closeSheet());
    const submit = () => {
      const pass = $('#cf-pass') ? $('#cf-pass').value : '';
      const w = $('#cf-word') ? $('#cf-word').value.trim().toUpperCase() : '';
      const err = $('#cf-err');
      if (password && !pass) { err.textContent = 'Рамзро ворид кунед'; err.hidden = false; return; }
      if (word && w !== word) { err.textContent = `Калимаи ${word}-ро дуруст нависед`; err.hidden = false; return; }
      sheet._resolve = null;
      closeSheet();
      resolve({ password: pass, word: w });
    };
    $('#cf-yes').addEventListener('click', submit);
    $$('#sheet-body input').forEach((i) => i.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); }));
  });
}

function bindEyes(root) {
  $$('[data-eye]', root).forEach((b) => b.addEventListener('click', () => {
    const input = document.getElementById(b.dataset.eye);
    if (input) input.type = input.type === 'password' ? 'text' : 'password';
  }));
}

/* ══════════════ Оғоз ══════════════ */

function bindGlobal() {
  document.addEventListener('click', (e) => {
    const v = e.target.closest('[data-view]');
    if (v && (v.closest('#tabbar') || v.closest('#side-nav'))) { haptic('light'); go(v.dataset.view); return; }
    const a = e.target.closest('[data-action]');
    if (!a) return;
    const act = a.dataset.action;
    if (act === 'theme') { toggleTheme(); if (S.view === 'settings') initSettings(); }
    else if (act === 'refresh') refreshCurrent();
    else if (act === 'logout') logout();
    else if (act === 'sel-cancel') setSelecting(false);
    else if (act === 'sel-delete') deleteSelected();
    else if (act === 'sel-all') {
      S.req.items.forEach((r) => S.req.selected.add(r.id));
      $$('#req-list .rq').forEach((c) => c.classList.add('is-selected'));
      updateSelbar();
    }
  });
  $$('[data-close]').forEach((el) => el.addEventListener('click', closeSheet));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });
  window.addEventListener('scroll', () => {
    $('.topbar').classList.toggle('is-scrolled', window.scrollY > 4);
  }, { passive: true });
  $('#login-form').addEventListener('submit', doLogin);
  bindEyes($('#login'));
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && token && !$('#app').hidden) refreshPending();
  });
}

function boot() {
  initTelegram();
  applyTheme(preferredTheme());
  buildNav();
  bindGlobal();
  const saved = store.get('sc_view');
  if (saved && VIEWS.find((v) => v.id === saved)) S.view = saved;

  fetch(`${API}/api/health`, { cache: 'no-store' }).then((r) => r.json()).then((h) => {
    $('#login-foot').textContent = `SoftClub HR Control · v${h.version}`;
  }).catch(() => {});

  if (!token) { showLogin(); return; }
  showApp();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();

})();
