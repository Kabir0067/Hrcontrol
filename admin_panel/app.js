/* ═══════════════════════════════════════════════════════════════════════
   SoftClub HR Control — панели идоракунӣ (v4)
   Бе китобхонаи беруна. Телефон · планшет · компютер · Telegram Mini App.
   ═══════════════════════════════════════════════════════════════════════ */

(() => {
'use strict';

const API = '.';
const PAGE = 30;
const UNDO_MS = 5000;

/* ══════════════ Нигоҳдорӣ (localStorage метавонад манъ бошад) ══════════════ */

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (_) {} },
  del(k) { try { localStorage.removeItem(k); } catch (_) {} },
};

let token = store.get('sc_token');

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/* ══════════════ Нишонаҳо ══════════════ */

const ICON = {
  home: '<svg viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/></svg>',
  att: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="17" rx="2.5"/><path d="M8 2.5v3M16 2.5v3M3 9.5h18"/><path d="m8.5 15 2.5 2.5 4.5-5"/></svg>',
  req: '<svg viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="18" rx="2.5"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
  team: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.2"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 5.2a3.2 3.2 0 0 1 0 5.6M17.5 20a6.4 6.4 0 0 0-2-4.6"/></svg>',
  stats: '<svg viewBox="0 0 24 24"><path d="M4 20V11M10 20V4M16 20v-7M22 20H2"/></svg>',
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
  left: '<svg viewBox="0 0 24 24"><path d="m15 18-6-6 6-6"/></svg>',
  right: '<svg viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></svg>',
  edit: '<svg viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
  sun: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
  palm: '<svg viewBox="0 0 24 24"><path d="M12 22V11"/><path d="M12 11C9 7 5 7 3 9c3-1 6 0 9 2Z"/><path d="M12 11c3-4 7-4 9-2-3-1-6 0-9 2Z"/><path d="M12 11c-1-4-4-7-7-7 3 1 5 4 7 7Z"/><path d="M12 11c1-4 4-7 7-7-3 1-5 4-7 7Z"/></svg>',
  tg: '<svg viewBox="0 0 24 24"><path d="m21.5 3.5-19 7.3c-1 .4-1 1.8.1 2.1l4.6 1.5 1.8 5.6c.3.9 1.4 1.1 2 .4l2.6-2.7 4.9 3.6c.8.6 2 .2 2.2-.8L23 5c.2-1.1-.8-1.9-1.5-1.5Z"/><path d="m7.3 14.3 9.5-6.8"/></svg>',
};

/* ══════════════ Луғатҳо ══════════════ */

const TYPE = {
  late:            { label: 'Дер мекунад',     short: 'Дер',     color: 'var(--warn)',   pill: 'warn',   emoji: '🕰' },
  absent:          { label: 'Намеояд',         short: 'Намеояд', color: 'var(--danger)', pill: 'danger', emoji: '🌿' },
  at_work_waiting: { label: 'Ҷавоб мепурсад',  short: 'Ҷавоб',   color: 'var(--info)',   pill: 'info',   emoji: '☕' },
  leaving_early:   { label: 'Барвақт меравад', short: 'Барвақт', color: 'var(--violet)', pill: 'violet', emoji: '🌅' },
};
const TYPE_ORDER = ['late', 'absent', 'at_work_waiting', 'leaving_early'];

const STATUS = {
  pending:   { label: 'Интизори қарор',  pill: 'warn',   color: 'var(--warn)' },
  accepted:  { label: 'Иҷозат дода шуд', pill: 'ok',     color: 'var(--ok)' },
  rejected:  { label: 'Рад шуд',         pill: 'danger', color: 'var(--danger)' },
  cancelled: { label: 'Бекор шуд',       pill: 'muted',  color: 'var(--muted)' },
};
const STATUS_ORDER = ['pending', 'accepted', 'rejected', 'cancelled'];

// Ҳолатҳои давомот
const ATT = {
  on_time: { label: 'Сари вақт',   pill: 'ok',     color: 'var(--ok)' },
  late:    { label: 'Дер омад',    pill: 'warn',   color: 'var(--warn)' },
  absent:  { label: 'Наомад',      pill: 'danger', color: 'var(--danger)' },
  leave:   { label: 'Рухсатӣ',     pill: 'info',   color: 'var(--info)' },
  pending: { label: 'Ҷавоб надод', pill: 'muted',  color: 'var(--muted)' },
  none:    { label: 'Бе сабт',     pill: 'muted',  color: 'var(--surface-3)' },
};
const ATT_ORDER = ['on_time', 'late', 'absent', 'leave', 'pending'];
const SRC = { bot: 'Ҷавоби корманд', admin: 'Админ ислоҳ кард', request: 'Аз дархост' };

const WD = ['Дш', 'Сш', 'Чш', 'Пш', 'Ҷм', 'Шб', 'Яш'];
const WD_FULL = ['душанбе', 'сешанбе', 'чоршанбе', 'панҷшанбе', 'ҷумъа', 'шанбе', 'якшанбе'];
const MONTHS = ['январ', 'феврал', 'март', 'апрел', 'май', 'июн', 'июл', 'август', 'сентябр', 'октябр', 'ноябр', 'декабр'];
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

const VIEWS = [
  { id: 'home',     label: 'Асосӣ',     sub: 'Манзараи имрӯз' },
  { id: 'att',      label: 'Давомот',   sub: 'Кӣ кай ба кор омад' },
  { id: 'req',      label: 'Дархостҳо', sub: 'Муроҷиатҳои кормандон' },
  { id: 'team',     label: 'Кормандон', sub: 'Рӯйхат ва идоракунӣ' },
  { id: 'stats',    label: 'Омор',      sub: 'Таҳлили давомот ва дархостҳо' },
  { id: 'settings', label: 'Танзимот',  sub: 'Вақти корӣ, ворид шудан, маълумот', noTab: true },
];

const PERIODS = [
  ['wm', 'Моҳи кории ҷорӣ'], ['wm_prev', 'Моҳи кории гузашта'], ['today', 'Имрӯз'],
  ['week', 'Ҳамин ҳафта'], ['7', '7 рӯзи охир'], ['30', '30 рӯзи охир'],
  ['all', 'Ҳама вақт'], ['custom', 'Санаҳои дигар…'],
];

/* ══════════════ Ҳолат ══════════════ */

const S = {
  view: 'home',
  today: '',                          // санаи сервер (Душанбе), на санаи браузер
  schedule: null,
  pending: 0,
  workers: [],                        // барои select-и корманд
  req: {
    q: '', type: '', status: '', period: 'all', from: '', to: '', user_id: '', sort: 'new',
    items: [], total: 0, offset: 0, selecting: false, selected: new Set(), seq: 0,
  },
  att: { mode: 'day', day: '', period: '', filter: '', sort: 'name', dayData: null, month: null, seq: 0 },
  team: { q: '', show: 'active', sort: 'name', data: null, seq: 0 },
  stats: { tab: 'att', period: 'wm', from: '', to: '', data: null, seq: 0, sortKey: 'rate', sortDir: 1 },
  inited: {},
};

const known = new Map();              // id → дархост

/* ══════════════ Telegram Mini App ══════════════ */

// Танҳо дар дохили Telegram (initData холӣ нест); дар браузери оддӣ — null
const tgRaw = window.Telegram && window.Telegram.WebApp;
const tg = tgRaw && tgRaw.initData ? tgRaw : null;

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
  const color = name === 'dark' ? '#0B0F17' : '#F6F7F9';
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
const nameOf = (rec) => (rec && rec.alias) || shortName(rec && rec.name);

function initials(full) {
  const parts = shortName(full).split(/\s+/).filter(Boolean);
  return (parts.slice(0, 2).map((p) => p[0]).join('') || '?').toUpperCase();
}

const AV_COLORS = ['#4F46E5', '#7C3AED', '#DB2777', '#EA580C', '#059669', '#0891B2', '#CA8A04', '#DC2626', '#2563EB', '#9333EA', '#0D9488', '#65A30D'];
function avatar(name, id, cls = '') {
  const n = Math.abs(Number(id) || [...String(name)].reduce((a, c) => a + c.charCodeAt(0), 0));
  return `<div class="avatar ${cls}" style="background:${AV_COLORS[n % AV_COLORS.length]}">${esc(initials(name))}</div>`;
}

const p2 = (n) => String(n).padStart(2, '0');
function parseDate(v) {
  if (!v) return null;
  const s = String(v);
  const d = new Date(s.length === 10 ? s + 'T00:00:00' : s.replace(' ', 'T'));
  return isNaN(d.getTime()) ? null : d;
}
const ymd = (d) => `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
const todayYmd = () => S.today || ymd(new Date());
function addDays(iso, n) { const d = parseDate(iso); d.setDate(d.getDate() + n); return ymd(d); }
const wdOf = (iso) => (parseDate(iso).getDay() + 6) % 7;

function fmtDateTime(v) {
  const d = parseDate(v);
  if (!d) return '—';
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${p2(d.getHours())}:${p2(d.getMinutes())}`;
}
function fmtClock(v) { const d = parseDate(v); return d ? `${p2(d.getHours())}:${p2(d.getMinutes())}` : '—'; }
function fmtDateShort(v) { const d = parseDate(v); return d ? `${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)}` : '—'; }
function fmtDay(iso) { const d = parseDate(iso); return d ? `${d.getDate()} ${MONTHS[d.getMonth()]}, ${WD_FULL[(d.getDay() + 6) % 7]}` : '—'; }

function fmtRelative(v) {
  const d = parseDate(v);
  if (!d) return '—';
  const now = new Date();
  const diff = (now - d) / 60000;
  if (diff >= 0 && diff < 1) return 'ҳозир';
  if (diff >= 0 && diff < 60) return `${Math.floor(diff)} дақ пеш`;
  const t = todayYmd();
  if (ymd(d) === t) return `имрӯз, ${fmtClock(v)}`;
  if (ymd(d) === addDays(t, -1)) return `дирӯз, ${fmtClock(v)}`;
  const sameYear = d.getFullYear() === now.getFullYear();
  return `${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)}${sameYear ? '' : ' ' + d.getFullYear()}, ${fmtClock(v)}`;
}

function fmtMinutes(m) {
  m = Math.round(Number(m) || 0);
  if (m <= 0) return '—';
  if (m < 60) return `${m} дақ`;
  const h = Math.floor(m / 60), r = m % 60;
  return r ? `${h} соат ${r} дақ` : `${h} соат`;
}
function fmtHours(m) {
  m = Number(m) || 0;
  if (m <= 0) return '0';
  if (m < 60) return `${Math.round(m)} дақ`;
  const h = m / 60;
  return `${h >= 10 ? Math.round(h) : h.toFixed(1).replace('.0', '')} соат`;
}
const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
const pctText = (v) => (v == null ? '—' : `${v}%`);

let toastTimer = null;
let toastAction = null;
function toast(msg, kind = '', opts = {}) {
  const el = $('#toast');
  $('#toast-text').textContent = msg;
  el.className = 'toast' + (kind ? ` toast--${kind}` : '');
  const btn = $('#toast-action');
  toastAction = opts.onAction || null;
  btn.hidden = !opts.action;
  btn.textContent = opts.action || '';
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; toastAction = null; }, opts.duration || 2800);
}

function emptyState(title, note = '', icon = ICON.inbox) {
  return `<div class="empty">${icon}<b>${esc(title)}</b>${note ? `<span>${esc(note)}</span>` : ''}</div>`;
}
const skel = (n, cls = '') => Array.from({ length: n }, () => `<div class="skeleton ${cls}"></div>`).join('');

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

const pill = (text, kind = '', icon = '') => `<span class="pill ${kind ? 'pill--' + kind : ''}">${icon}${esc(text)}</span>`;
function typePill(t) { const m = TYPE[t] || { label: t, pill: '' }; return pill(`${m.emoji || ''} ${m.label}`, m.pill); }
function statusPill(s) { const m = STATUS[s] || { label: s, pill: '' }; return pill(m.label, m.pill); }
function attPill(s) { const m = ATT[s] || ATT.none; return `<span class="pill pill--${m.pill}"><i class="dot" style="background:${m.color}"></i>${esc(m.label)}</span>`; }

/* ══════════════ Давраҳо (моҳи корӣ: 5 → 4) ══════════════ */

function workMonth(offset = 0) {
  const [y, m, d] = todayYmd().split('-').map(Number);
  let yy = y, mm = m - (d < 5 ? 1 : 0) + offset;
  while (mm < 1) { mm += 12; yy -= 1; }
  while (mm > 12) { mm -= 12; yy += 1; }
  let ey = yy, em = mm + 1;
  if (em > 12) { em = 1; ey += 1; }
  return { key: `${yy}-${p2(mm)}`, start: `${yy}-${p2(mm)}-05`, end: `${ey}-${p2(em)}-04` };
}
function monthTitle(key) { const [y, m] = key.split('-').map(Number); return `${cap(MONTHS[m - 1])} ${y}`; }
const rangeText = (a, b) => `${fmtDateShort(a)} – ${fmtDateShort(b)}`;

function periodRange(period, from, to) {
  const t = todayYmd();
  switch (period) {
    case 'today': return { date_from: t, date_to: t };
    case 'week':  return { date_from: addDays(t, -wdOf(t)), date_to: t };
    case '7':     return { date_from: addDays(t, -6), date_to: t };
    case '30':    return { date_from: addDays(t, -29), date_to: t };
    case 'wm':    { const w = workMonth(0); return { date_from: w.start, date_to: w.end }; }
    case 'wm_prev': { const w = workMonth(-1); return { date_from: w.start, date_to: w.end }; }
    case 'custom': return { date_from: from || '', date_to: to || '' };
    default: return { date_from: '', date_to: '' };
  }
}

function periodLabel(period, from, to) {
  if (period === 'custom') {
    if (from && to) return rangeText(from, to);
    if (from) return `аз ${fmtDateShort(from)}`;
    if (to) return `то ${fmtDateShort(to)}`;
    return 'Ҳама вақт';
  }
  if (period === 'wm' || period === 'wm_prev') {
    const w = workMonth(period === 'wm' ? 0 : -1);
    return `${monthTitle(w.key)} (${rangeText(w.start, w.end)})`;
  }
  const found = PERIODS.find(([k]) => k === period);
  return found ? found[1] : '';
}

function periodPicker(scope, st) {
  return `<select class="select" data-period="${scope}" aria-label="Давра">
      ${PERIODS.map(([k, l]) => `<option value="${k}"${st.period === k ? ' selected' : ''}>${l}</option>`).join('')}
    </select>`;
}
function rangeInputs(scope, st) {
  return `<div class="filters__range" data-range="${scope}" ${st.period === 'custom' ? '' : 'hidden'}>
    <input type="date" class="input" data-from value="${esc(st.from)}" aria-label="Аз сана">
    <input type="date" class="input" data-to value="${esc(st.to)}" aria-label="То сана">
  </div>`;
}
function bindPeriod(root, scope, st, reload) {
  const sel = $(`[data-period="${scope}"]`, root);
  const range = $(`[data-range="${scope}"]`, root);
  sel.addEventListener('change', () => {
    st.period = sel.value;
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
    if (!options.quiet) toast('Алоқа бо сервер нест. Интернетро санҷед.', 'danger');
    return options.raw ? { error: 'Алоқа бо сервер нест' } : null;
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

/* ══════════════ Нест кардан бо «Бозгардондан» ══════════════
   Амал дарҳол дар экран иҷро мешавад, ба сервер — пас аз 5 сония.
   Дар ин муддат тугмаи «Бозгардондан» ҳамаашро бекор мекунад. */

const pendingDeletes = new Map();

function deferDelete(key, { text, apply, revert, commit, done }) {
  if (pendingDeletes.has(key)) return;
  apply();
  haptic('medium');
  const entry = { finished: false };
  entry.flush = async () => {
    if (entry.finished) return;
    entry.finished = true;
    clearTimeout(entry.timer);
    pendingDeletes.delete(key);
    const ok = await commit();
    if (!ok) { revert(); toast('Нест нашуд — аз нав кӯшиш кунед', 'danger'); return; }
    if (done) done();
  };
  entry.undo = () => {
    if (entry.finished) return;
    entry.finished = true;
    clearTimeout(entry.timer);
    pendingDeletes.delete(key);
    revert();
    haptic('light');
    toast('Бозгардонида шуд');
  };
  entry.timer = setTimeout(entry.flush, UNDO_MS);
  pendingDeletes.set(key, entry);
  toast(text, '', { action: 'Бозгардондан', onAction: entry.undo, duration: UNDO_MS });
}

function flushDeletes() { [...pendingDeletes.values()].forEach((e) => e.flush()); }

/* ══════════════ Вуруд / баромад ══════════════ */

function showLogin() {
  $('#app').hidden = true;
  $('#login').hidden = false;
  setTimeout(() => { const i = $('#in-login'); if (i && !i.value && !tg) i.focus(); }, 50);
}

function showApp() {
  $('#login').hidden = true;
  $('#app').hidden = false;
  go(S.view, true);
  refreshPending();
}

function logout(expired = false) {
  flushDeletes();
  token = null;
  store.del('sc_token');
  S.inited = {};
  $$('.view').forEach((v) => { v.innerHTML = ''; delete v.dataset.built; });
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
    errBox.textContent = 'Логин ва рамзро нависед';
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

/** Дар дохили Telegram — вуруд бе рамз (барои админҳои гурӯҳи роҳбарият). */
async function tryTelegramLogin() {
  if (!tg || !tg.initData) return false;
  $('#login-tg').hidden = false;
  const res = await api('/api/login/telegram', { method: 'POST', body: JSON.stringify({ init_data: tg.initData }), raw: true, quiet: true });
  $('#login-tg').hidden = true;
  if (res && res.token) {
    token = res.token;
    store.set('sc_token', token);
    haptic('success');
    return true;
  }
  if (res && res.status === 403) {
    const box = $('#login-error');
    box.className = 'alert alert--info';
    box.textContent = 'Барои вуруди худкор бояд админи гурӯҳи роҳбарият бошед. Бо логин ва рамз ворид шавед.';
    box.hidden = false;
  }
  return false;
}

/* ══════════════ Навигатсия ══════════════ */

function buildNav() {
  const badge = (v) => (v.id === 'req' ? '<b class="badge-dot" data-badge hidden></b>' : '');
  $('#tabbar').innerHTML = VIEWS.filter((v) => !v.noTab).map((v) =>
    `<button class="tab" data-view="${v.id}">${ICON[v.id]}<span>${v.label}</span>${badge(v)}</button>`).join('');
  $('#side-nav').innerHTML = VIEWS.map((v) =>
    `<button class="side__link" data-view="${v.id}" title="${v.label}">${ICON[v.id]}<span>${v.label}</span>${badge(v)}</button>`).join('');
}

function go(name, force = false) {
  if (!VIEWS.find((v) => v.id === name)) name = 'home';
  const changed = S.view !== name;
  S.view = name;
  store.set('sc_view', name);
  if (location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
  const meta = VIEWS.find((v) => v.id === name);
  $('#view-title').textContent = meta.label;
  $('#view-sub').textContent = meta.sub;
  $$('[data-view]').forEach((b) => b.classList.toggle('is-active', b.dataset.view === name));
  $$('.view').forEach((v) => v.classList.toggle('is-active', v.id === `view-${name}`));
  if (name !== 'req') setSelecting(false);
  if (changed) window.scrollTo({ top: 0 });

  const loaders = { home: loadHome, att: initAtt, req: initRequests, team: initTeam, stats: initStats, settings: initSettings };
  if (force || changed || !S.inited[name]) loaders[name]();
}

function refreshCurrent() {
  haptic('light');
  const btn = $('[data-action="refresh"]');
  btn.classList.add('is-spinning');
  setTimeout(() => btn.classList.remove('is-spinning'), 700);
  S.workers = [];
  if (S.view === 'req') loadRequests(true);
  else if (S.view === 'att') loadAtt();
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

/** Пас аз ҳар тағйир — кэшҳо тоза, намуди ҷорӣ аз нав. */
function afterDataChange(reload = true) {
  S.workers = [];
  S.team.data = null;
  S.stats.data = null;
  S.inited = {};
  refreshPending();
  if (reload) go(S.view, true);
}

/* ══════════════ Графикҳо (HTML/SVG, бе китобхона) ══════════════ */

/** Сутунҳои қабат-қабат. keys: [{key, color, label}] */
function stackCols(series, keys, opts = {}) {
  if (!series || !series.length) return emptyState(opts.empty || 'Маълумот нест', '', ICON.stats);
  const total = (d) => keys.reduce((a, k) => a + (d[k.key] || 0), 0);
  const max = Math.max(1, ...series.map(total));
  const n = series.length;
  const step = n <= 10 ? 1 : n <= 20 ? 2 : n <= 40 ? 5 : n <= 80 ? 10 : 30;
  const showNums = n <= 16;
  const today = todayYmd();
  const cols = series.map((d) => {
    const t = total(d);
    const h = t ? Math.max(4, (100 * t) / max) : 0;
    const segs = keys.map((k) => (d[k.key] ? `<i style="height:${(100 * d[k.key]) / t}%;background:${k.color}"></i>` : '')).join('');
    const tip = `${fmtDateShort(d.date)}: ` + keys.filter((k) => d[k.key]).map((k) => `${k.label} ${d[k.key]}`).join(', ');
    return `<div class="col${d.date === today ? ' is-today' : ''}" title="${esc(t ? tip : fmtDateShort(d.date))}">
      ${showNums && t ? `<span class="col__n" style="bottom:calc(${h}% + 4px)">${t}</span>` : ''}
      <div class="col__bar" style="height:${h}%">${segs}</div></div>`;
  }).join('');
  const axis = series.map((d, i) => {
    const dt = parseDate(d.date);
    const label = opts.weekday ? WD[(dt.getDay() + 6) % 7] : `${dt.getDate()}.${p2(dt.getMonth() + 1)}`;
    return `<span>${i % step === 0 || i === n - 1 ? label : ''}</span>`;
  }).join('');
  const legend = opts.legend === false ? '' : `<div class="legend chart-legend">${keys.map((k) => `<span><i style="background:${k.color}"></i>${esc(k.label)}</span>`).join('')}</div>`;
  return `<div class="cols" style="${opts.height ? `height:${opts.height}px` : ''}">${cols}</div><div class="axis">${axis}</div>${legend}`;
}

const ATT_KEYS = ATT_ORDER.map((k) => ({ key: k, color: ATT[k].color, label: ATT[k].label }));
const TYPE_KEYS = TYPE_ORDER.map((k) => ({ key: k, color: TYPE[k].color, label: TYPE[k].label }));
const flatTypes = (days) => (days || []).map((d) => ({ date: d.date, ...(d.by_type || {}) }));

function simpleCols(values, labels, colors, opts = {}) {
  const max = Math.max(1, ...values);
  const cols = values.map((v, i) => {
    const h = v ? Math.max(4, (100 * v) / max) : 0;
    const color = Array.isArray(colors) ? colors[i] : colors;
    return `<div class="col${i === opts.highlight ? ' is-mark' : ''}" title="${esc(labels[i])}: ${v}">
      ${v ? `<span class="col__n" style="bottom:calc(${h}% + 4px)">${v}</span>` : ''}
      <div class="col__bar" style="height:${h}%"><i style="height:100%;background:${color}"></i></div></div>`;
  }).join('');
  return `<div class="cols" style="height:${opts.height || 150}px">${cols}</div>
    <div class="axis">${labels.map((l) => `<span>${esc(l)}</span>`).join('')}</div>`;
}

function donut(segments, centerValue, centerLabel) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  const R = 15.915;
  let offset = 0;
  const live = segments.filter((s) => s.value);
  const arcs = total ? live.map((s) => {
    const len = (100 * s.value) / total;
    const gap = live.length > 1 ? 0.8 : 0;
    const arc = `<circle cx="21" cy="21" r="${R}" fill="none" stroke="${s.color}" stroke-width="5.4"
      stroke-dasharray="${Math.max(0, len - gap)} ${100 - Math.max(0, len - gap)}" stroke-dashoffset="${-offset}"/>`;
    offset += len;
    return arc;
  }).join('') : '';
  const list = segments.map((s) => `<div class="dlist__row"><i style="background:${s.color}"></i>
      <span>${esc(s.label)}</span><b>${s.value}</b><em>${pct(s.value, total)}%</em></div>`).join('');
  return `<div class="donut-wrap">
    <div class="donut"><svg viewBox="0 0 42 42"><circle cx="21" cy="21" r="${R}" fill="none" stroke="var(--surface-2)" stroke-width="5.4"/>${arcs}</svg>
      <div class="donut__c"><div><b>${esc(centerValue)}</b><small>${esc(centerLabel)}</small></div></div></div>
    <div class="dlist">${list}</div></div>`;
}

function ring(segments, big, small) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  const C = 2 * Math.PI * 42;
  let offset = 0;
  const arcs = total ? segments.filter((s) => s.value).map((s) => {
    const len = (C * s.value) / total;
    const arc = `<circle cx="50" cy="50" r="42" stroke="${s.color}" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-offset}"/>`;
    offset += len;
    return arc;
  }).join('') : '';
  return `<div class="ring"><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="42" stroke="var(--surface-2)"/>${arcs}</svg>
    <div class="ring__c"><div><b>${esc(big)}</b><small>${esc(small)}</small></div></div></div>`;
}

function hbars(items, opts = {}) {
  if (!items.length) return emptyState(opts.empty || 'Маълумот нест');
  const max = Math.max(1, ...items.map((i) => i.value));
  return `<div class="hbars">${items.map((it, idx) => {
    const w = (100 * it.value) / max;
    const track = it.segments
      ? it.segments.filter((s) => s.value).map((s) => `<i style="width:${(w * s.value) / (it.value || 1)}%;background:${s.color}"></i>`).join('')
      : `<i style="width:${w}%;background:${it.color || 'var(--brand)'}"></i>`;
    return `<div class="hbar${opts.link ? ' is-link' : ''}" data-idx="${idx}">
      <div class="hbar__top"><span class="hbar__label" title="${esc(it.label)}">${esc(it.label)}</span>
        <span class="hbar__val"><b>${it.value}</b>${it.extra ? ` · ${esc(it.extra)}` : ''}</span></div>
      <div class="hbar__track">${track}</div>
      ${it.sub ? `<div class="hbar__sub">${esc(it.sub)}</div>` : ''}</div>`;
  }).join('')}</div>`;
}

function typeStackbar(obj) {
  const total = TYPE_ORDER.reduce((a, t) => a + (obj[t] || 0), 0);
  if (!total) return '<div class="stackbar"></div>';
  return `<div class="stackbar">${TYPE_ORDER.map((t) => obj[t]
    ? `<i style="width:${(100 * obj[t]) / total}%;background:${TYPE[t].color}" title="${TYPE[t].label}: ${obj[t]}"></i>` : '').join('')}</div>`;
}

function kpi(label, value, sub, icon, tone = '', attrs = '') {
  const tag = attrs ? 'button' : 'div';
  return `<${tag} class="kpi ${tone ? 'kpi--' + tone : ''}" ${attrs}>
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
  const minutes = rec.minutes ? pill(fmtMinutes(rec.minutes), '', ICON.clock) : '';
  const quick = opts.quick && rec.status === 'pending' ? `<div class="rq__quick">
      <button class="btn btn--soft-ok btn--sm" data-decide="accepted" data-id="${rec.id}">${ICON.check} Иҷозат</button>
      <button class="btn btn--soft-danger btn--sm" data-decide="rejected" data-id="${rec.id}">${ICON.x} Рад</button></div>` : '';
  const del = opts.del === false ? '' : `<button class="rq__del" data-del="${rec.id}" aria-label="Нест кардан" title="Нест кардан">${ICON.trash}</button>`;
  return `<div class="rq${sel ? ' is-selected' : ''}" role="button" tabindex="0" data-rid="${rec.id}">
    <span class="rq__check">${ICON.check}</span>
    ${avatar(nameOf(rec), rec.user_id)}
    <div class="rq__main">
      <div class="rq__top"><span class="rq__name">${esc(nameOf(rec))}</span><span class="rq__id">#${rec.id}</span><span class="rq__time">${esc(fmtRelative(rec.created_at))}</span></div>
      <div class="rq__meta">${typePill(rec.type)}${minutes}${opts.hideStatus ? '' : statusPill(rec.status)}</div>
      <div class="rq__reason">${esc(rec.reason)}</div>
      ${quick}
    </div>
    ${del}</div>`;
}

function bindCards(root) {
  root.addEventListener('click', async (e) => {
    const dec = e.target.closest('[data-decide]');
    if (dec) {
      e.stopPropagation();
      await decide(Number(dec.dataset.id), dec.dataset.decide, dec);
      return;
    }
    const del = e.target.closest('[data-del]');
    if (del) {
      e.stopPropagation();
      deleteRequestUndo(Number(del.dataset.del));
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

/** Нест кардани як дархост — бе савол, бо «Бозгардондан». */
function deleteRequestUndo(id) {
  const cards = $$(`[data-rid="${id}"]`);
  const holders = cards.map((c) => ({ el: c, parent: c.parentNode, next: c.nextSibling }));
  deferDelete(`req:${id}`, {
    text: `Дархости #${id} нест шуд`,
    apply: () => {
      cards.forEach((c) => c.remove());
      if (S.view === 'req') { S.req.total = Math.max(0, S.req.total - 1); updateReqCount(); }
    },
    revert: () => {
      holders.forEach((h) => { if (h.parent) h.parent.insertBefore(h.el, h.next && h.next.parentNode === h.parent ? h.next : null); });
      if (S.view === 'req') { S.req.total += 1; updateReqCount(); }
    },
    commit: async () => Boolean(await api(`/api/requests/${id}`, { method: 'DELETE', keepalive: true, quiet: true })),
    done: () => {
      known.delete(id);
      S.req.items = S.req.items.filter((r) => r.id !== id);
      S.team.data = null; S.stats.data = null; S.workers = [];
      S.inited.home = false; S.inited.stats = false; S.inited.team = false;
      refreshPending();
    },
  });
}

async function decide(id, decision, btn) {
  if (btn) btn.classList.add('is-loading');
  const res = await post(`/api/requests/${id}/decision`, { decision }, { raw: true });
  if (btn) btn.classList.remove('is-loading');
  if (!res || res.error) { haptic('error'); return false; }
  haptic('success');
  toast(decision === 'accepted' ? 'Иҷозат дода шуд — ба корманд хабар рафт' : 'Рад карда шуд — ба корманд хабар рафт', 'ok');
  afterDataChange(false);
  if (S.view === 'home') loadHome();
  if (S.view === 'req') loadRequests(true);
  return true;
}

/* ══════════════ АСОСӢ ══════════════ */

async function loadHome() {
  S.inited.home = true;
  const root = $('#view-home');
  if (!root.dataset.built) {
    root.innerHTML = `
      <div class="hello" id="home-hello"></div>
      <div id="home-schedule"></div>
      <div class="grid grid-21 grid--start">
        <div class="card" id="home-today">${skel(1, 'skeleton--lg')}</div>
        <div class="stack">
          <div class="kpis kpis--2" id="home-kpis">${skel(4, 'skeleton--sm')}</div>
          <div class="card">
            <div class="card__head"><h2>Давомот · 7 рӯз</h2></div>
            <div class="card__body" id="home-week-att">${skel(1)}</div>
          </div>
        </div>
      </div>
      <div class="grid grid-21 grid--start">
        <div class="card">
          <div class="card__head"><h2>Интизори қарор</h2><span class="card__note" id="home-pending-n"></span><span class="spacer"></span><button class="linkbtn" data-goto-pending>Ҳама ›</button></div>
          <div class="card__body--flush"><div class="list" id="home-pending">${skel(2)}</div></div>
        </div>
        <div class="card">
          <div class="card__head"><h2>Дархостҳо · 7 рӯз</h2><span class="card__note" id="home-week-note"></span></div>
          <div class="card__body" id="home-week">${skel(1)}</div>
        </div>
      </div>
      <div class="card">
        <div class="card__head"><h2>Дархостҳои охирин</h2><span class="spacer"></span><button class="linkbtn" data-goto="req">Ҳама ›</button></div>
        <div class="card__body--flush"><div class="list" id="home-recent">${skel(3)}</div></div>
      </div>`;
    root.dataset.built = '1';
    bindCards($('#home-pending'));
    bindCards($('#home-recent'));
    root.addEventListener('click', (e) => {
      if (e.target.closest('[data-goto-pending]')) { openRequestsWith({ status: 'pending' }); return; }
      if (e.target.closest('[data-open-schedule]')) { openSchedule(); return; }
      const g = e.target.closest('[data-goto]');
      if (g) { go(g.dataset.goto); return; }
      const f = e.target.closest('[data-att-filter]');
      if (f) { S.att.mode = 'day'; S.att.day = todayYmd(); S.att.filter = f.dataset.attFilter; go('att', true); return; }
      const a = e.target.closest('[data-att-edit]');
      if (a) { const it = (S.homeAway || [])[Number(a.dataset.attEdit)]; if (it) openAttEdit(it.user_id, it.name, todayYmd(), it.cell); return; }
      const k = e.target.closest('[data-kpi]');
      if (!k) return;
      const key = k.dataset.kpi;
      if (key === 'pending') openRequestsWith({ status: 'pending' });
      else if (key === 'today') openRequestsWith({ period: 'today' });
      else { S.att.mode = 'day'; S.att.day = todayYmd(); S.att.filter = key; go('att', true); }
    });
  }

  const d = await api('/api/overview');
  if (!d) return;
  S.schedule = d.today.schedule;
  const day = d.today;
  const sm = day.summary;
  const hour = new Date().getHours();
  const hello = hour < 11 ? 'Субҳ ба хайр' : hour < 17 ? 'Рӯз ба хайр' : 'Шом ба хайр';
  $('#home-hello').innerHTML = `<div><h2>${hello}!</h2><p>${esc(cap(fmtDay(day.date)))}${S.schedule.enabled ? ` · оғози кор ${esc(S.schedule.time)}` : ''}</p></div>`;

  $('#home-schedule').innerHTML = S.schedule.enabled ? '' : `
    <div class="card card--accent"><div class="schedule-bar schedule-bar--off">
      <div class="schedule-bar__ico">${ICON.clock}</div>
      <div class="schedule-bar__text"><b>Вақти оғози кор муқаррар нашудааст</b>
        <small>Вақтро гузоред — бот ҳар рӯзи корӣ аз кормандон мепурсад «Ба кор омадед?» ва давомот худкор сабт мешавад.</small></div>
      <button class="btn btn--primary" data-open-schedule>Муқаррар кардан</button></div></div>`;

  // Давомоти имрӯз
  const present = sm.on_time + sm.late;
  const expected = sm.total - sm.leave - sm.none;
  let todayBody;
  if (!S.schedule.enabled && !sm.total) {
    todayBody = emptyState('Давомот ҳоло фаъол нест', 'Пас аз муқаррар кардани вақти корӣ ин ҷо дида мешавад, ки кӣ кай омад.', ICON.att);
  } else if (!day.workday && !(sm.total - sm.none)) {
    todayBody = emptyState(day.off ? `Имрӯз ид аст: ${day.off}` : 'Имрӯз рӯзи истироҳат аст', 'Бот имрӯз савол намефиристад.', ICON.palm);
  } else if (!(sm.total - sm.none)) {
    todayBody = emptyState('Ҳанӯз савол нарафтааст', `Соати ${S.schedule.time} бот аз кормандон мепурсад.`, ICON.clock);
  } else {
    const rows = [...ATT_ORDER, 'none'].filter((k) => sm[k] || ['on_time', 'late', 'absent', 'pending'].includes(k)).map((k) =>
      `<button class="lg-row" data-att-filter="${k}"><i class="dot" style="background:${ATT[k].color}"></i>${ATT[k].label}<b>${sm[k] || 0}</b></button>`).join('');
    todayBody = `<div class="today">
      ${ring(ATT_ORDER.map((k) => ({ value: sm[k] || 0, color: ATT[k].color })), `${present}/${expected > 0 ? expected : sm.total}`, 'омаданд')}
      <div class="today__legend">${rows}</div></div>`;
  }
  const away = day.items.filter((it) => it.cell && ['absent', 'pending'].includes(it.cell.s));
  S.homeAway = away;
  const awayList = away.length ? `
    <div class="section-title" style="margin:4px 16px 0">Ҳанӯз дар кор нестанд · ${away.length}</div>
    <div class="list">${away.map((it, i) => `
      <button class="item" data-att-edit="${i}">
        ${avatar(it.name, it.user_id, 'avatar--sm')}
        <div class="item__main"><div class="item__name">${esc(shortName(it.name))}</div>
          <div class="item__sub">${it.cell.s === 'absent' ? esc([it.cell.reason, it.cell.eta && 'меояд: ' + it.cell.eta].filter(Boolean).join(' · ') || 'сабаб нагуфт') : 'ба савол ҷавоб надод'}</div></div>
        ${attPill(it.cell.s)}</button>`).join('')}</div>` : '';
  $('#home-today').innerHTML = `<div class="card__head"><h2>Давомоти имрӯз</h2><span class="spacer"></span><button class="linkbtn" data-att-filter="">Ҷадвал ›</button></div>
    <div class="card__body">${todayBody}</div>${awayList}`;

  // KPI
  const r = d.requests;
  $('#home-kpis').innerHTML = [
    kpi('Интизори қарор', r.pending, r.pending ? 'ҷавоб диҳед' : 'ҳамааш ҳал шуд', ICON.hourglass, r.pending ? 'warn' : 'ok', 'data-kpi="pending"'),
    kpi('Дархостҳои имрӯз', r.today, `дар моҳи корӣ: ${r.month}`, ICON.req, 'brand', 'data-kpi="today"'),
    kpi('Дер омаданд', sm.late, sm.late ? 'имрӯз' : 'имрӯз ҳеҷ кас', ICON.clock, 'warn', 'data-kpi="late"'),
    kpi('Наомаданд', sm.absent, sm.pending ? `${sm.pending} нафар ҷавоб надод` : 'имрӯз', ICON.alert, 'danger', 'data-kpi="absent"'),
  ].join('');

  // Интизори қарор
  const items = d.pending || [];
  $('#home-pending-n').textContent = items.length ? `${r.pending}` : '';
  $('#home-pending').innerHTML = items.length
    ? items.slice(0, 5).map((x) => requestCard(x, { quick: true, hideStatus: true, del: false })).join('')
      + (items.length > 5 ? `<div class="card__body"><button class="btn btn--ghost btn--block" data-goto-pending>Боз ${r.pending - 5} дархост ›</button></div>` : '')
    : emptyState('Ҳамаи дархостҳо ҳал шудаанд', 'Дархосте нест, ки ҷавоб интизор бошад', ICON.check);

  // 7 рӯз
  $('#home-week-att').innerHTML = stackCols(d.week_attendance, ATT_KEYS, { weekday: true, empty: 'Ҳанӯз давомот нест' });
  const week = d.week_requests || [];
  $('#home-week-note').textContent = `${week.reduce((a, x) => a + x.count, 0)} дархост`;
  $('#home-week').innerHTML = stackCols(flatTypes(week), TYPE_KEYS, { weekday: true, empty: 'Дархост нест' });

  const recent = r.recent || [];
  $('#home-recent').innerHTML = recent.length
    ? recent.slice(0, 6).map((x) => requestCard(x)).join('')
    : emptyState('Ҳанӯз дархост нест', 'Вақте кормандон дархост фиристанд, ин ҷо пайдо мешавад');
}

function openRequestsWith(filters) {
  Object.assign(S.req, { q: '', type: '', status: '', period: 'all', from: '', to: '', user_id: '', sort: 'new' }, filters);
  S.inited.req = false;
  const root = $('#view-req');
  root.innerHTML = '';
  delete root.dataset.built;
  go('req', true);
}

/* ══════════════ ВАҚТИ КОРӢ ══════════════ */

function scheduleBar(sch) {
  if (!sch || !sch.enabled) {
    return `<div class="card card--accent"><div class="schedule-bar schedule-bar--off">
      <div class="schedule-bar__ico">${ICON.clock}</div>
      <div class="schedule-bar__text"><b>Вақти оғози кор муқаррар нашудааст</b>
        <small>Бе он бот аз кормандон намепурсад, ки ба кор омаданд ё не.</small></div>
      <button class="btn btn--primary" data-open-schedule>Муқаррар кардан</button></div></div>`;
  }
  return `<div class="card"><div class="schedule-bar">
    <div class="schedule-bar__ico">${ICON.clock}</div>
    <div class="schedule-bar__text"><b>Оғози кор: ${esc(sch.time)}</b>
      <small>${esc(sch.days.map((d) => WD[d]).join(' · '))} · то ${sch.grace} дақ — сари вақт${sch.report ? ' · ҳисобот ба гурӯҳ' : ''}</small></div>
    <button class="btn btn--ghost btn--sm" data-open-schedule aria-label="Тағйир додан">${ICON.edit}<span class="hide-phone">Тағйир додан</span></button></div></div>`;
}

async function openSchedule() {
  const sch = S.schedule || (await api('/api/work-schedule')) || { time: '', days: [0, 1, 2, 3, 4, 5], grace: 10, report: true };
  const days = new Set(sch.days);
  openSheet(`
    <div class="sheet__title">Вақти корӣ</div>
    <p class="sheet__text">Дар ин вақт бот аз ҳар корманд мепурсад: <b>«Ба кор омадед?»</b>
      Ҷавобҳо ба ҷадвали давомот сабт мешаванд. Касе, ки наомадааст, сабаб ва вақти омаданашро менависад.</p>
    <label class="field"><span class="field__label">Оғози кор</span>
      <input id="sc-time" class="input" type="time" value="${esc(sch.time || '08:00')}" required></label>
    <div class="field"><span class="field__label">Рӯзҳои корӣ</span>
      <div class="daychips" id="sc-days">${WD.map((w, i) => `<button type="button" data-d="${i}" class="${days.has(i) ? 'is-on' : ''}">${w}</button>`).join('')}</div>
      <span class="field__hint">Дар рӯзҳои дигар (масалан, якшанбе) савол намеравад.</span></div>
    <label class="field"><span class="field__label">Дер ҳисоб мешавад, агар омадан аз</span>
      <select id="sc-grace" class="select">${[0, 5, 10, 15, 20, 30].map((g) => `<option value="${g}"${sch.grace === g ? ' selected' : ''}>${g ? `${g} дақиқа дертар бошад` : 'вақти оғоз дертар бошад'}</option>`).join('')}</select></label>
    <div class="setting" style="padding:4px 0">
      <div class="setting__text"><b>Ҳисоботи рӯз ба гурӯҳ</b><small>Як соат пас аз оғози кор: кӣ омад, кӣ дер кард, кӣ наомад</small></div>
      <label class="switch"><input type="checkbox" id="sc-report" ${sch.report ? 'checked' : ''}><span></span></label></div>
    <div id="sc-err" class="alert alert--danger" hidden></div>
    <div class="sheet__actions">
      ${sch.enabled ? '<button class="btn btn--ghost btn--lg" id="sc-off">Хомӯш кардан</button>' : ''}
      <button class="btn btn--primary btn--lg" id="sc-save">Сабт кардан</button>
    </div>`);
  $('#sc-days').addEventListener('click', (e) => {
    const b = e.target.closest('[data-d]');
    if (!b) return;
    const d = Number(b.dataset.d);
    if (days.has(d)) days.delete(d); else days.add(d);
    b.classList.toggle('is-on', days.has(d));
    haptic('light');
  });
  const save = async (time) => {
    const err = $('#sc-err');
    err.hidden = true;
    if (time && !days.size) { err.textContent = 'Ақаллан як рӯзи кориро интихоб кунед'; err.hidden = false; return; }
    const res = await post('/api/work-schedule', {
      time, days: [...days].sort(), grace: Number($('#sc-grace').value), report: $('#sc-report').checked,
    }, { raw: true, quiet: true });
    if (!res || res.error) { err.textContent = (res && res.error) || 'Сабт нашуд'; err.hidden = false; haptic('error'); return; }
    S.schedule = { time: res.time, days: res.days, grace: res.grace, report: res.report, enabled: res.enabled };
    haptic('success');
    closeSheet();
    toast(res.message, 'ok');
    afterDataChange();
  };
  $('#sc-save').addEventListener('click', () => {
    const t = $('#sc-time').value;
    if (!t) { $('#sc-err').textContent = 'Вақтро нависед'; $('#sc-err').hidden = false; return; }
    save(t);
  });
  const off = $('#sc-off');
  if (off) off.addEventListener('click', async () => {
    if (await confirmDialog({ title: 'Саволи ҳаррӯза хомӯш шавад?', text: 'Бот дигар аз кормандон намепурсад, ки ба кор омаданд ё не. Давомоти сабтшуда нигоҳ дошта мешавад.', okText: 'Хомӯш кардан', danger: true })) save('');
  });
}

/* ══════════════ ДАВОМОТ ══════════════ */

function initAtt() {
  S.inited.att = true;
  const root = $('#view-att');
  const st = S.att;
  if (!root.dataset.built) {
    root.innerHTML = `
      <div id="att-schedule"></div>
      <div class="toolbar">
        <div class="seg" id="att-mode">
          <button data-m="day">Рӯз</button>
          <button data-m="month">Моҳи корӣ</button>
        </div>
        <div class="toolbar__group" id="att-nav"></div>
      </div>
      <div id="att-body" class="grid">${skel(3)}</div>`;
    root.dataset.built = '1';
    root.addEventListener('click', onAttClick);
    root.addEventListener('change', (e) => {
      if (e.target.id === 'att-day-input' && e.target.value) { st.day = e.target.value; loadAtt(); }
      if (e.target.id === 'att-sort') { st.sort = e.target.value; renderAttMonth(); }
    });
  }
  loadAtt();
}

function onAttClick(e) {
  const st = S.att;
  if (e.target.closest('[data-open-schedule]')) { openSchedule(); return; }
  const m = e.target.closest('[data-m]');
  if (m) { st.mode = m.dataset.m; haptic('light'); loadAtt(); return; }
  const nav = e.target.closest('[data-nav]');
  if (nav) {
    const v = nav.dataset.nav;
    if (st.mode === 'day') st.day = v === 'today' ? todayYmd() : v;
    else st.period = v === 'now' ? '' : v;
    haptic('light');
    loadAtt();
    return;
  }
  if (e.target.closest('[data-att-csv]')) { download(`/api/attendance.csv?${qs({ period: st.period || workMonth(0).key })}`); return; }
  const f = e.target.closest('[data-filter]');
  if (f) { st.filter = f.dataset.filter; renderAttDay(); return; }
  const off = e.target.closest('[data-dayoff]');
  if (off) { toggleDayOff(off.dataset.dayoff, off.dataset.off === '1'); return; }
  const row = e.target.closest('[data-att-row]');
  if (row) {
    const it = st.dayData.items[Number(row.dataset.attRow)];
    openAttEdit(it.user_id, it.name, st.dayData.date, it.cell);
    return;
  }
  const cell = e.target.closest('[data-cell]');
  if (cell) {
    const [uid, date] = cell.dataset.cell.split('|');
    const emp = st.month.employees.find((x) => String(x.user_id) === uid);
    if (emp) openAttEdit(emp.user_id, emp.name, date, emp.cells[date] || null);
    return;
  }
  const person = e.target.closest('[data-uid]');
  if (person) { openEmployee(Number(person.dataset.uid)); return; }
  const day = e.target.closest('[data-goday]');
  if (day) { st.mode = 'day'; st.day = day.dataset.goday; loadAtt(); }
}

async function loadAtt() {
  const st = S.att;
  $$('#att-mode [data-m]').forEach((b) => b.classList.toggle('is-active', b.dataset.m === st.mode));
  const seq = ++st.seq;
  $('#att-body').innerHTML = skel(3);
  if (st.mode === 'day') {
    const d = await api(`/api/attendance/day?${qs({ date: st.day || todayYmd() })}`);
    if (seq !== st.seq || !d) return;
    st.dayData = d;
    st.day = d.date;
    S.schedule = d.schedule;
    renderAttDay();
  } else {
    const d = await api(`/api/attendance/month?${qs({ period: st.period })}`);
    if (seq !== st.seq || !d) return;
    st.month = d;
    S.schedule = d.schedule;
    renderAttMonth();
  }
  $('#att-schedule').innerHTML = scheduleBar(S.schedule);
}

function renderAttDay() {
  const st = S.att;
  const d = st.dayData;
  const isToday = d.date === todayYmd();
  $('#att-nav').innerHTML = `
    <div class="nav-date">
      <button class="iconbtn" data-nav="${d.prev}" aria-label="Рӯзи пеш">${ICON.left}</button>
      <label class="nav-date__label">${esc(isToday ? 'Имрӯз' : cap(fmtDay(d.date)).split(',')[0])}
        <small>${esc(isToday ? fmtDay(d.date) : WD_FULL[d.wd])}</small>
        <input type="date" id="att-day-input" value="${d.date}" max="${todayYmd()}" aria-label="Сана"></label>
      <button class="iconbtn" data-nav="${d.next || ''}" ${d.next ? '' : 'disabled style="opacity:.4"'} aria-label="Рӯзи баъд">${ICON.right}</button>
      ${isToday ? '' : '<button class="btn btn--ghost btn--sm" data-nav="today">Имрӯз</button>'}
    </div>
    <button class="btn btn--ghost btn--sm" data-att-csv title="Боргирӣ барои Excel">${ICON.download}<span class="hide-phone">CSV</span></button>`;

  const sm = d.summary;
  const filters = [['', 'Ҳама', sm.total], ...ATT_ORDER.map((k) => [k, ATT[k].label, sm[k]]), ['none', 'Бе сабт', sm.none]]
    .filter(([k, , n]) => k === '' || n);
  if (st.filter && !filters.find(([k]) => k === st.filter)) st.filter = '';
  const list = d.items
    .map((it, i) => ({ it, i }))
    .filter(({ it }) => !st.filter || (it.cell ? it.cell.s : 'none') === st.filter)
    .sort((a, b) => {
      const order = ['absent', 'pending', 'late', 'on_time', 'leave', undefined];
      const sa = a.it.cell ? a.it.cell.s : undefined, sb = b.it.cell ? b.it.cell.s : undefined;
      return order.indexOf(sa) - order.indexOf(sb) || shortName(a.it.name).localeCompare(shortName(b.it.name));
    });

  let banner = '';
  if (d.off) banner = `<div class="alert alert--info">🌴 <b>${esc(d.off || 'Рӯзи истироҳат')}</b> — дар ин рӯз савол намеравад.</div>`;
  else if (d.weekend) banner = `<div class="alert alert--info">🌴 ${cap(WD_FULL[d.wd])} — рӯзи истироҳат. Бот савол намефиристад.</div>`;

  const rows = list.map(({ it, i }) => {
    const c = it.cell;
    let sub = '';
    if (c && c.s === 'absent') sub = [c.reason, c.eta && `меояд: ${c.eta}`].filter(Boolean).join(' · ') || 'сабаб нагуфт';
    else if (c && c.s === 'leave') sub = c.reason || 'рухсатӣ';
    else if (c && c.s === 'pending') sub = 'ба савол ҷавоб надод';
    else if (c && c.reason) sub = c.reason;
    else if (!c) sub = it.active ? (d.future ? '' : 'савол нагирифт') : 'савол намегирад';
    const time = c && c.t
      ? `<span class="item__time">${c.t}</span>${c.late ? pill(`дер ${fmtMinutes(c.late)}`, 'warn') : pill('сари вақт', 'ok')}`
      : attPill(c ? c.s : 'none');
    return `<button class="item" data-att-row="${i}">
      ${avatar(it.name, it.user_id, it.active ? '' : 'is-off')}
      <div class="item__main"><div class="item__name">${esc(shortName(it.name))}</div>
        ${sub ? `<div class="item__sub">${esc(sub)}</div>` : ''}</div>
      <div class="item__end">${time}</div></button>`;
  }).join('');

  const canOff = !d.weekend && d.date >= addDays(todayYmd(), -60);
  $('#att-body').innerHTML = `
    ${banner}
    <div class="chips">${filters.map(([k, l, n]) => `<button class="chip${st.filter === k ? ' is-active' : ''}" data-filter="${k}">${k ? `<i class="dot" style="background:${ATT[k].color}"></i>` : ''}${esc(l)} <b>${n}</b></button>`).join('')}</div>
    <div class="card"><div class="list">${rows || emptyState(sm.total ? 'Дар ин гурӯҳ касе нест' : 'Кормандон ҳоло нестанд', sm.total ? '' : 'Корманд пас аз пахши /start дар бот ба рӯйхат илова мешавад', ICON.team)}</div></div>
    ${canOff ? `<div class="row-flex" style="justify-content:center">
      <button class="btn btn--link" data-dayoff="${d.date}" data-off="${d.off ? '0' : '1'}">${d.off ? 'Ин рӯзро рӯзи корӣ кардан' : 'Ин рӯзро рӯзи истироҳат (ид) эълон кардан'}</button></div>` : ''}`;
}

async function toggleDayOff(date, off) {
  let title = '';
  if (off) {
    const res = await promptDialog({ title: 'Рӯзи истироҳат', text: `${cap(fmtDay(date))} — дар ин рӯз бот савол намефиристад.`, label: 'Ном (ихтиёрӣ)', placeholder: 'Масалан: Наврӯз', okText: 'Эълон кардан' });
    if (res === null) return;
    title = res;
  }
  const r = await post('/api/days-off', { date, off, title });
  if (!r) return;
  toast(r.message, 'ok');
  loadAtt();
}

function monthCell(emp, day) {
  const c = emp.cells[day.date];
  const key = `${emp.user_id}|${day.date}`;
  if (c) {
    const txt = { on_time: ICON.check, late: c.late >= 100 ? `${Math.floor(c.late / 60)}с` : `+${c.late}`, absent: 'Н', leave: 'Р', pending: '?' }[c.s] || '';
    const tip = `${shortName(emp.name)} · ${fmtDay(day.date)}: ${ATT[c.s].label}${c.t ? ' ' + c.t : ''}${c.late ? ` (+${c.late} дақ)` : ''}${c.reason ? ' · ' + c.reason : ''}`;
    return `<button class="mc mc--${c.s}" data-cell="${key}" title="${esc(tip)}">${txt}</button>`;
  }
  if (day.future) return '<span class="mc mc--future"></span>';
  if (!day.workday) return '';
  return `<button class="mc mc--none" data-cell="${key}" title="${esc(`${shortName(emp.name)} · ${fmtDay(day.date)}: сабт нест`)}">·</button>`;
}

function sortedEmployees(list, sort) {
  const by = {
    name: (a, b) => shortName(a.name).localeCompare(shortName(b.name)),
    rate: (a, b) => (a.summary.rate ?? 101) - (b.summary.rate ?? 101) || shortName(a.name).localeCompare(shortName(b.name)),
    late: (a, b) => b.summary.late - a.summary.late || b.summary.late_minutes - a.summary.late_minutes,
    absent: (a, b) => b.summary.absent - a.summary.absent || b.summary.pending - a.summary.pending,
  }[sort] || (() => 0);
  return list.slice().sort(by);
}

function renderAttMonth() {
  const st = S.att;
  const d = st.month;
  const p = d.period;
  const isNow = p.key === workMonth(0).key;
  $('#att-nav').innerHTML = `
    <div class="nav-date">
      <button class="iconbtn" data-nav="${p.prev}" aria-label="Моҳи пеш">${ICON.left}</button>
      <div class="nav-date__label">${esc(monthTitle(p.key))}<small>${esc(rangeText(p.start, p.end))}</small></div>
      <button class="iconbtn" data-nav="${p.next || ''}" ${p.next ? '' : 'disabled style="opacity:.4"'} aria-label="Моҳи баъд">${ICON.right}</button>
      ${isNow ? '' : '<button class="btn btn--ghost btn--sm" data-nav="now">Ҷорӣ</button>'}
    </div>
    <button class="btn btn--ghost btn--sm" data-att-csv title="Боргирӣ барои Excel">${ICON.download}<span class="hide-phone">Excel (CSV)</span></button>`;

  const t = d.totals;
  const emps = sortedEmployees(d.employees, st.sort);
  const legend = `<div class="legend">
    <span><i style="background:var(--ok-soft);box-shadow:inset 0 0 0 1px var(--ok)"></i>Сари вақт</span>
    <span><i style="background:var(--warn-soft);box-shadow:inset 0 0 0 1px var(--warn)"></i>Дер (+дақиқа)</span>
    <span><i style="background:var(--danger-soft);box-shadow:inset 0 0 0 1px var(--danger)"></i>Н — наомад</span>
    <span><i style="background:var(--info-soft);box-shadow:inset 0 0 0 1px var(--info)"></i>Р — рухсатӣ</span>
    <span><i style="box-shadow:inset 0 0 0 1.5px var(--border-2)"></i>? — ҷавоб надод</span>
    <span><i style="background-image:repeating-linear-gradient(135deg,transparent 0 3px,var(--border-2) 3px 4px)"></i>Истироҳат</span></div>`;

  const head = `<tr><th class="m-name">Корманд</th>${d.days.map((day) => `<th class="m-day${day.workday ? '' : ' is-off'}${day.today ? ' is-today' : ''}" title="${esc(fmtDay(day.date) + (day.off ? ' · ' + day.off : ''))}"><button class="m-person" style="display:block;text-align:center;color:inherit" data-goday="${day.date}"><b>${Number(day.date.slice(8))}</b><small>${WD[day.wd]}</small></button></th>`).join('')}
    <th class="m-sum">Давомот</th><th class="m-sum">Дер</th><th class="m-sum">Наомад</th></tr>`;
  const body = emps.map((e) => `<tr>
    <td class="m-name"><button class="m-person" data-uid="${e.user_id}">${avatar(e.name, e.user_id, 'avatar--sm' + (e.active ? '' : ' is-off'))}<span style="min-width:0"><b>${esc(shortName(e.name))}</b><small>${e.summary.rate != null ? `${e.summary.rate}%` : ''}${e.summary.avg_arrival ? ` · миёна ${e.summary.avg_arrival}` : ''}${e.active ? '' : ' · савол намегирад'}</small></span></button></td>
    ${d.days.map((day) => `<td class="${!day.workday && !e.cells[day.date] ? 'm-off' : ''}">${monthCell(e, day)}</td>`).join('')}
    <td class="m-sum">${pctText(e.summary.rate)}<small>${e.summary.present} рӯз</small></td>
    <td class="m-sum" style="color:${e.summary.late ? 'var(--warn-text)' : 'inherit'}">${e.summary.late}<small>${e.summary.late_minutes ? fmtHours(e.summary.late_minutes) : '—'}</small></td>
    <td class="m-sum" style="color:${e.summary.absent ? 'var(--danger-text)' : 'inherit'}">${e.summary.absent}<small>${e.summary.pending ? e.summary.pending + ' бе ҷавоб' : ''}</small></td></tr>`).join('');
  const foot = `<tr><td class="m-name">Омаданд</td>${d.days.map((day) => { const b = d.by_day[day.date] || {}; const n = (b.on_time || 0) + (b.late || 0); return `<td>${n || ''}</td>`; }).join('')}<td></td><td></td><td></td></tr>`;

  const cards = emps.map((e) => `
    <button class="person" data-uid="${e.user_id}">
      <div class="person__head">${avatar(e.name, e.user_id, e.active ? '' : 'is-off')}
        <div class="person__who"><b>${esc(shortName(e.name))}</b><small>${e.summary.avg_arrival ? 'Миёнаи омадан: ' + e.summary.avg_arrival : (e.active ? 'Ҳанӯз сабт нест' : 'Савол намегирад')}</small></div>
        <div class="person__score"><b>${pctText(e.summary.rate)}</b><small>давомот</small></div></div>
      <div class="strip">${d.days.map((day) => { const c = e.cells[day.date]; const s = c ? c.s : day.future ? 'future' : !day.workday ? 'off' : 'none'; return `<i class="s-${s}${day.today ? ' is-today' : ''}"></i>`; }).join('')}</div>
      <div class="person__nums">${pill(`Сари вақт ${e.summary.on_time}`, 'ok')}${e.summary.late ? pill(`Дер ${e.summary.late} · ${fmtHours(e.summary.late_minutes)}`, 'warn') : ''}${e.summary.absent ? pill(`Наомад ${e.summary.absent}`, 'danger') : ''}${e.summary.leave ? pill(`Рухсатӣ ${e.summary.leave}`, 'info') : ''}${e.summary.pending ? pill(`Бе ҷавоб ${e.summary.pending}`, 'muted') : ''}</div>
    </button>`).join('');

  $('#att-body').innerHTML = `
    <div class="kpis">
      ${kpi('Давомот', pctText(t.rate), `${t.present} рӯз омаданд`, ICON.att, 'ok')}
      ${kpi('Сари вақт', pctText(t.punctuality), `${t.on_time} сари вақт · ${t.late} дер`, ICON.check, 'brand')}
      ${kpi('Миёнаи омадан', t.avg_arrival || '—', S.schedule && S.schedule.enabled ? `оғози кор ${S.schedule.time}` : '', ICON.clock, 'info')}
      ${kpi('Ҳамагӣ дерӣ', fmtHours(t.late_minutes), t.late ? `${t.late} бор дер омаданд` : 'касе дер накард', ICON.hourglass, 'warn')}
    </div>
    <div class="card">
      <div class="card__head"><h2>Ҷадвали давомот</h2><span class="card__note">${emps.length} корманд</span><span class="spacer"></span>
        <select class="select" id="att-sort" style="width:auto;min-height:36px;font-size:14px">
          <option value="name"${st.sort === 'name' ? ' selected' : ''}>Аз рӯи ном</option>
          <option value="rate"${st.sort === 'rate' ? ' selected' : ''}>Давомоти паст</option>
          <option value="late"${st.sort === 'late' ? ' selected' : ''}>Бештар дер</option>
          <option value="absent"${st.sort === 'absent' ? ' selected' : ''}>Бештар наомад</option>
        </select></div>
      <div class="card__body" style="padding-top:10px">${legend}</div>
      ${emps.length ? `
        <div class="matrix-wrap hide-phone"><table class="matrix"><thead>${head}</thead><tbody>${body}</tbody><tfoot>${foot}</tfoot></table></div>
        <div class="list only-phone" style="border-top:1px solid var(--border)">${cards}</div>`
        : `<div class="card__body">${emptyState('Кормандон ҳоло нестанд', 'Корманд пас аз пахши /start дар бот ба рӯйхат илова мешавад', ICON.team)}</div>`}
    </div>`;
}

/** Ислоҳи дастии давомот (як корманд, як рӯз). */
function openAttEdit(userId, name, date, cell, onDone) {
  const future = date > todayYmd();
  let mode = cell ? (cell.s === 'on_time' || cell.s === 'late' ? 'present' : cell.s === 'pending' ? 'present' : cell.s) : (future ? 'leave' : 'present');
  if (future) mode = 'leave';
  const sch = S.schedule || {};
  const rows = cell ? [
    ['Ҳолат', ATT[cell.s].label],
    cell.t ? ['Вақти омадан', cell.t + (cell.late ? ` (+${fmtMinutes(cell.late)})` : '')] : null,
    cell.sched && cell.sched !== '00:00' ? ['Оғози кор', cell.sched] : null,
    cell.reason ? ['Сабаб', cell.reason] : null,
    cell.eta ? ['Кай меояд', cell.eta] : null,
    ['Манбаъ', SRC[cell.src] || cell.src],
  ].filter(Boolean) : [];

  openSheet(`
    <div class="detail-head">${avatar(name, userId, 'avatar--lg')}
      <div><b>${esc(shortName(name))}</b><small>${esc(cap(fmtDay(date)))}</small></div></div>
    ${cell ? `<div class="info">${rows.map(([k, v]) => `<div class="info__row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')}</div>`
      : `<div class="alert alert--info">${future ? 'Барои рӯзи оянда метавонед рухсатӣ гузоред.' : 'Барои ин рӯз сабт нест. Метавонед дастӣ илова кунед.'}</div>`}
    <div class="section-title">${cell ? 'Ислоҳ кардан' : 'Илова кардан'}</div>
    <div class="choice" id="ae-choice">
      <button data-mode="present" ${future ? 'disabled style="opacity:.4"' : ''}><i class="dot" style="background:var(--ok)"></i>Омад</button>
      <button data-mode="absent" ${future ? 'disabled style="opacity:.4"' : ''}><i class="dot" style="background:var(--danger)"></i>Наомад</button>
      <button data-mode="leave"><i class="dot" style="background:var(--info)"></i>Рухсатӣ</button>
    </div>
    <div id="ae-fields" class="stack"></div>
    <div id="ae-err" class="alert alert--danger" hidden></div>
    <button class="btn btn--primary btn--lg btn--block" id="ae-save">Сабт кардан</button>
    ${cell ? `<div class="row-flex" style="justify-content:space-between">
      <button class="btn btn--link" id="ae-worker">${ICON.user} Профили корманд</button>
      <button class="btn btn--link" id="ae-del" style="color:var(--danger-text)">${ICON.trash} Нест кардани сабт</button></div>`
      : `<button class="btn btn--link" id="ae-worker">${ICON.user} Профили корманд</button>`}`);

  const fields = () => {
    const f = $('#ae-fields');
    $$('#ae-choice [data-mode]').forEach((b) => b.classList.toggle('is-active', b.dataset.mode === mode));
    if (mode === 'present') {
      f.innerHTML = `<label class="field"><span class="field__label">Вақти омадан</span>
        <input class="input" id="ae-time" type="time" value="${esc((cell && cell.t) || sch.time || '08:00')}"></label>`;
    } else if (mode === 'absent') {
      f.innerHTML = `<label class="field"><span class="field__label">Сабаб</span>
          <input class="input" id="ae-reason" type="text" maxlength="300" value="${esc((cell && cell.reason) || '')}" placeholder="Масалан: бемор аст"></label>
        <label class="field"><span class="field__label">Кай меояд</span>
          <input class="input" id="ae-eta" type="text" maxlength="120" value="${esc((cell && cell.eta) || '')}" placeholder="Масалан: пагоҳ"></label>`;
    } else {
      f.innerHTML = `<label class="field"><span class="field__label">Шарҳ (ихтиёрӣ)</span>
        <input class="input" id="ae-reason" type="text" maxlength="300" value="${esc((cell && cell.s === 'leave' && cell.reason) || '')}" placeholder="Масалан: рухсатии меҳнатӣ, беморӣ бо варақа"></label>`;
    }
  };
  fields();
  $('#ae-choice').addEventListener('click', (e) => {
    const b = e.target.closest('[data-mode]');
    if (!b || b.disabled) return;
    mode = b.dataset.mode;
    haptic('light');
    fields();
  });
  $('#ae-save').addEventListener('click', async () => {
    const body = { user_id: userId, date, status: mode };
    if (mode === 'present') body.time = $('#ae-time').value;
    if ($('#ae-reason')) body.reason = $('#ae-reason').value.trim();
    if ($('#ae-eta')) body.eta = $('#ae-eta').value.trim();
    const btn = $('#ae-save');
    btn.classList.add('is-loading');
    const res = await post('/api/attendance', body, { raw: true, quiet: true });
    btn.classList.remove('is-loading');
    if (!res || res.error) { const err = $('#ae-err'); err.textContent = (res && res.error) || 'Сабт нашуд'; err.hidden = false; haptic('error'); return; }
    haptic('success');
    closeSheet();
    toast('Сабт шуд', 'ok');
    if (onDone) onDone(); else refreshAttViews();
  });
  $('#ae-worker').addEventListener('click', () => openEmployee(userId));
  const del = $('#ae-del');
  if (del) del.addEventListener('click', () => {
    closeSheet();
    deferDelete(`att:${cell.id}`, {
      text: 'Сабти давомот нест шуд',
      apply: () => {},
      revert: () => {},
      commit: async () => Boolean(await api(`/api/attendance/${cell.id}`, { method: 'DELETE', keepalive: true, quiet: true })),
      done: () => { if (onDone) onDone(); else refreshAttViews(); },
    });
  });
}

function refreshAttViews() {
  S.stats.data = null;
  S.team.data = null;
  S.inited.home = false; S.inited.stats = false; S.inited.team = false;
  if (S.view === 'att') loadAtt();
  else if (S.view === 'home') loadHome();
  else go(S.view, true);
}

/* ══════════════ ДАРХОСТҲО ══════════════ */

async function ensureWorkers() {
  if (S.workers.length) return S.workers;
  const data = await api('/api/employees', { quiet: true });
  S.workers = (data || []).map((w) => ({ id: w.user_id, name: w.alias || shortName(w.name), total: w.requests }))
    .sort((a, b) => a.name.localeCompare(b.name));
  return S.workers;
}

async function initRequests() {
  S.inited.req = true;
  const root = $('#view-req');
  const st = S.req;
  if (!root.dataset.built) {
    root.innerHTML = `
      <div class="card"><div class="card__body filters">
        <div class="filters__top">
          <label class="search">${ICON.search}
            <input id="rq-q" class="input" type="search" placeholder="Ҷустуҷӯ: ном ё сабаб…" autocomplete="off" value="${esc(st.q)}">
            <button class="search__clear" id="rq-clear" aria-label="Тоза кардан" ${st.q ? '' : 'hidden'}>${ICON.x}</button>
          </label>
          <button class="btn btn--ghost only-phone" id="rq-ftoggle" type="button">Филтрҳо<b class="badge-inline" id="rq-fcount" hidden></b></button>
        </div>
        <div class="filters__row">
          ${periodPicker('req', st)}
          <select class="select" id="rq-type" aria-label="Навъ"><option value="">Ҳама навъҳо</option>${TYPE_ORDER.map((t) => `<option value="${t}">${TYPE[t].emoji} ${TYPE[t].label}</option>`).join('')}</select>
          <select class="select" id="rq-status" aria-label="Ҳолат"><option value="">Ҳама ҳолатҳо</option>${STATUS_ORDER.map((s) => `<option value="${s}">${STATUS[s].label}</option>`).join('')}</select>
          <select class="select" id="rq-user" aria-label="Корманд"><option value="">Ҳама кормандон</option></select>
          <select class="select" id="rq-sort" aria-label="Тартиб">
            <option value="new">Аввал навҳо</option><option value="old">Аввал кӯҳнаҳо</option>
            <option value="minutes">Аз рӯи вақт</option><option value="name">Аз рӯи ном</option>
          </select>
        </div>
        ${rangeInputs('req', st)}
      </div></div>
      <div class="resultbar">
        <span id="rq-count">…</span>
        <div class="resultbar__actions">
          <button class="btn btn--ghost btn--sm" id="rq-reset" hidden>${ICON.x} Тоза кардани филтрҳо</button>
          <button class="btn btn--ghost btn--sm" id="rq-select">${ICON.select} Интихоб</button>
          <button class="btn btn--ghost btn--sm" id="rq-export" title="Боргирӣ барои Excel">${ICON.download} CSV</button>
          <button class="btn btn--soft-danger btn--sm" id="rq-delall" title="Нест кардани ҳамаи ёфтшудаҳо" aria-label="Нест кардани ҳамаи ёфтшудаҳо">${ICON.trash}<span class="hide-phone">Ҳамаи ёфтшудаҳо</span></button>
        </div>
      </div>
      <div class="card"><div class="list" id="req-list"></div></div>
      <button class="btn btn--ghost btn--block" id="rq-more" hidden>Боз нишон додан</button>`;
    root.dataset.built = '1';

    const reload = () => loadRequests(true);
    const qInput = $('#rq-q');
    qInput.addEventListener('input', debounce(() => {
      st.q = qInput.value.trim();
      $('#rq-clear').hidden = !st.q;
      reload();
    }, 350));
    $('#rq-clear').addEventListener('click', (e) => { e.preventDefault(); qInput.value = ''; st.q = ''; $('#rq-clear').hidden = true; reload(); });
    $('#rq-type').addEventListener('change', (e) => { st.type = e.target.value; reload(); });
    $('#rq-status').addEventListener('change', (e) => { st.status = e.target.value; reload(); });
    $('#rq-user').addEventListener('change', (e) => { st.user_id = e.target.value; reload(); });
    $('#rq-sort').addEventListener('change', (e) => { st.sort = e.target.value; reload(); });
    bindPeriod(root, 'req', st, reload);
    $('#rq-more').addEventListener('click', () => loadRequests(false));
    $('#rq-ftoggle').addEventListener('click', () => { $('#view-req .filters').classList.toggle('is-open'); haptic('light'); });
    $('#rq-reset').addEventListener('click', () => openRequestsWith({}));
    $('#rq-select').addEventListener('click', () => setSelecting(!st.selecting));
    $('#rq-export').addEventListener('click', () => download(`/api/export.csv?${qs(reqFilters())}`));
    $('#rq-delall').addEventListener('click', deleteFiltered);
    bindCards($('#req-list'));
  }
  $('#rq-type').value = st.type;
  $('#rq-status').value = st.status;
  $('#rq-sort').value = st.sort;
  $('[data-period="req"]').value = st.period;
  loadRequests(true);
  const workers = await ensureWorkers();
  const sel = $('#rq-user');
  sel.innerHTML = '<option value="">Ҳама кормандон</option>' +
    workers.map((w) => `<option value="${w.id}">${esc(w.name)}${w.total ? ` (${w.total})` : ''}</option>`).join('');
  sel.value = st.user_id || '';
}

function reqFilters() {
  const st = S.req;
  return { q: st.q, type: st.type, status: st.status, user_id: st.user_id, ...periodRange(st.period, st.from, st.to) };
}

function hasFilters() {
  const st = S.req;
  return Boolean(st.q || st.type || st.status || st.user_id || (st.period !== 'all' && (st.period !== 'custom' || st.from || st.to)));
}

function updateReqCount() {
  const el = $('#rq-count');
  if (el) el.innerHTML = `Ёфт шуд: <b>${S.req.total}</b>${S.req.period !== 'all' ? ` · ${esc(periodLabel(S.req.period, S.req.from, S.req.to))}` : ''}`;
  const del = $('#rq-delall');
  if (del) del.hidden = !S.req.total;
}

async function loadRequests(reset) {
  const st = S.req;
  if (reset) { st.offset = 0; st.items = []; }
  const seq = ++st.seq;
  const list = $('#req-list');
  if (reset) list.innerHTML = skel(4);
  $('#rq-more').hidden = true;
  const data = await api(`/api/requests?${qs({ ...reqFilters(), sort: st.sort, limit: PAGE, offset: st.offset })}`);
  if (seq !== st.seq) return;
  if (!data) { list.innerHTML = emptyState('Бор нашуд', 'Навсозӣ кунед'); return; }
  st.total = data.total;
  st.items = reset ? data.items : st.items.concat(data.items);
  st.offset = st.items.length;
  updateReqCount();
  $('#rq-reset').hidden = !hasFilters();
  const nf = [st.type, st.status, st.user_id, st.period !== 'all' ? 1 : '', st.sort !== 'new' ? 1 : ''].filter(Boolean).length;
  $('#rq-fcount').hidden = !nf;
  $('#rq-fcount').textContent = nf;
  list.classList.toggle('is-selecting', st.selecting);
  list.innerHTML = st.items.length
    ? st.items.map((r) => requestCard(r, { quick: true })).join('')
    : emptyState('Чизе ёфт нашуд', hasFilters() ? 'Филтрҳоро иваз кунед ё тоза намоед' : 'Ҳанӯз дархост нест', ICON.search);
  $('#rq-more').hidden = st.items.length >= st.total;
  if (!$('#rq-more').hidden) $('#rq-more').textContent = `Боз нишон додан (${st.total - st.items.length})`;
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
  if (b) { b.classList.toggle('btn--soft', on); b.innerHTML = on ? `${ICON.x} Бекор` : `${ICON.select} Интихоб`; }
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
  $('#sel-count').textContent = `${S.req.selected.size} интихоб шуд`;
}

async function deleteSelected() {
  const ids = [...S.req.selected];
  if (!ids.length) { toast('Аввал дархостҳоро интихоб кунед'); return; }
  const ok = await confirmDialog({
    title: `${ids.length} дархост нест карда шавад?`,
    text: 'Пеш аз нест кардан нусхаи эҳтиётии база худкор сохта мешавад.',
    okText: 'Нест кардан', danger: true,
  });
  if (!ok) return;
  const res = await post('/api/requests/delete', { ids });
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
      ? 'Ҳамаи дархостҳое, ки ба филтрҳои ҳозира мувофиқанд, нест мешаванд. Нусхаи эҳтиётӣ худкор сохта мешавад.'
      : 'Филтр интихоб нашудааст — ҲАМАИ дархостҳо нест мешаванд. Нусхаи эҳтиётӣ худкор сохта мешавад.',
    okText: 'Нест кардан', danger: true,
  });
  if (!ok) return;
  const res = await post('/api/requests/delete', { filters: reqFilters() });
  if (!res) return;
  haptic('success');
  toast(res.message, 'ok');
  afterDataChange();
}

/* ══════════════ Тафсилоти дархост ══════════════ */

async function openRequest(id) {
  let rec = known.get(id);
  if (!rec) rec = await api(`/api/requests/${id}`);
  if (!rec) return;
  const confirmed = { yes: 'Бале, ҳамааш хуб', no: 'Не / ҷавоб надод' }[rec.worker_confirmed] || '—';
  const rows = [
    rec.minutes ? ['Вақт', `${fmtMinutes(rec.minutes)}${rec.deadline_at ? ` · то ${fmtClock(rec.deadline_at)}` : ''}`] : null,
    ['Фиристода шуд', fmtDateTime(rec.created_at)],
    rec.decided_by ? ['Қарор кард', shortName(rec.decided_by)] : null,
    rec.decided_at && rec.status !== 'pending' ? ['Вақти қарор', fmtDateTime(rec.decided_at)] : null,
    rec.status === 'accepted' && rec.minutes && rec.type !== 'absent' ? ['Тасдиқи корманд', confirmed] : null,
  ].filter(Boolean);
  const uname = usernameOf(rec.name);

  openSheet(`
    <div class="detail-head">${avatar(nameOf(rec), rec.user_id, 'avatar--lg')}
      <div><b>${esc(nameOf(rec))}</b><small>${uname ? '@' + esc(uname) + ' · ' : ''}дархости #${rec.id}</small></div></div>
    <div class="rq__meta">${typePill(rec.type)}${statusPill(rec.status)}</div>
    <div class="quote">${esc(rec.reason)}</div>
    <div class="info">${rows.map(([k, v]) => `<div class="info__row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')}</div>
    ${rec.status === 'pending' ? `<div class="sheet__actions">
      <button class="btn btn--ok btn--lg" data-sd="accepted">${ICON.check} Иҷозат додан</button>
      <button class="btn btn--danger btn--lg" data-sd="rejected">${ICON.x} Рад кардан</button></div>` : ''}
    <div class="section-title">Паём ба корманд</div>
    <div class="field"><textarea id="sh-msg" maxlength="2000" placeholder="Масалан: Хуб, пагоҳ барвақттар биёед"></textarea></div>
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
    if (res) { haptic('success'); toast('Паём ба корманд фиристода шуд', 'ok'); $('#sh-msg').value = ''; }
  });
  $('#sh-worker').addEventListener('click', () => openEmployee(rec.user_id));
  $('#sh-del').addEventListener('click', () => { closeSheet(); deleteRequestUndo(rec.id); });
}

/* ══════════════ КОРМАНДОН ══════════════ */

function initTeam() {
  S.inited.team = true;
  const root = $('#view-team');
  const st = S.team;
  if (!root.dataset.built) {
    root.innerHTML = `
      <div class="toolbar">
        <label class="search" style="flex:1;min-width:220px">${ICON.search}<input id="tm-q" class="input" type="search" placeholder="Ҷустуҷӯи корманд…" autocomplete="off"></label>
        <div class="toolbar__group">
          <div class="seg" id="tm-show">
            <button data-show="active">Фаъол</button><button data-show="off">Хомӯш</button><button data-show="all">Ҳама</button>
          </div>
          <select class="select" id="tm-sort" style="width:auto">
            <option value="name">Аз рӯи ном</option>
            <option value="rate">Давомоти паст</option>
            <option value="late">Бештар дер</option>
            <option value="requests">Бештар дархост</option>
            <option value="last">Охирин фаъолият</option>
          </select>
        </div>
      </div>
      <div class="alert alert--info small">Корманд худкор илова мешавад, вақте дар бот /start-ро пахш мекунад. Барои он ки аз касе (масалан, роҳбар) савол наравад, дар профилаш «Саволи ҳаррӯза»-ро хомӯш кунед.</div>
      <div class="resultbar"><span id="tm-count"></span><span class="muted small">${esc(`Давомот — дар моҳи кории ҷорӣ (${rangeText(workMonth(0).start, workMonth(0).end)})`)}</span></div>
      <div class="card"><div class="list" id="tm-list">${skel(4)}</div></div>`;
    root.dataset.built = '1';
    $('#tm-q').addEventListener('input', debounce((e) => { st.q = e.target.value.trim().toLowerCase(); renderTeam(); }, 200));
    $('#tm-sort').addEventListener('change', (e) => { st.sort = e.target.value; renderTeam(); });
    $('#tm-show').addEventListener('click', (e) => { const b = e.target.closest('[data-show]'); if (!b) return; st.show = b.dataset.show; renderTeam(); });
    $('#tm-list').addEventListener('click', (e) => {
      const c = e.target.closest('[data-uid]');
      if (c) openEmployee(Number(c.dataset.uid));
    });
  }
  $('#tm-sort').value = st.sort;
  loadTeam();
}

async function loadTeam() {
  const st = S.team;
  const seq = ++st.seq;
  if (!st.data) $('#tm-list').innerHTML = skel(4);
  const data = await api('/api/employees');
  if (seq !== st.seq) return;
  st.data = data || [];
  renderTeam();
}

function renderTeam() {
  const st = S.team;
  $$('#tm-show [data-show]').forEach((b) => b.classList.toggle('is-active', b.dataset.show === st.show));
  let rows = (st.data || []).slice();
  const counts = { active: rows.filter((w) => w.active).length, off: rows.filter((w) => !w.active).length };
  if (st.show === 'active') rows = rows.filter((w) => w.active);
  if (st.show === 'off') rows = rows.filter((w) => !w.active);
  if (st.q) rows = rows.filter((w) => [w.display, w.name, w.username].some((x) => String(x || '').toLowerCase().includes(st.q)));
  const by = {
    name: (a, b) => a.display.localeCompare(b.display),
    rate: (a, b) => (a.month.rate ?? 101) - (b.month.rate ?? 101),
    late: (a, b) => b.month.late - a.month.late || b.month.late_minutes - a.month.late_minutes,
    requests: (a, b) => b.requests - a.requests,
    last: (a, b) => String(b.last_seen).localeCompare(String(a.last_seen)),
  }[st.sort];
  rows.sort(by);
  $('#tm-count').innerHTML = `<b>${counts.active}</b> фаъол${counts.off ? ` · ${counts.off} хомӯш` : ''}`;
  $('#tm-list').innerHTML = rows.length ? rows.map((w) => {
    const m = w.month;
    return `<button class="person" data-uid="${w.user_id}">
      <div class="person__head">${avatar(w.display, w.user_id, w.active ? '' : 'is-off')}
        <div class="person__who"><b>${esc(w.alias || shortName(w.display))}</b>
          <small>${w.username ? '@' + esc(w.username) + ' · ' : ''}охирин бор: ${esc(fmtRelative(w.last_seen))}</small></div>
        <div class="person__score"><b>${pctText(m.rate)}</b><small>давомот</small></div></div>
      <div class="person__nums">
        ${w.active ? '' : pill('Савол намегирад', 'muted')}
        ${m.present ? pill(`Омад ${m.present}`, 'ok') : ''}
        ${m.late ? pill(`Дер ${m.late}`, 'warn') : ''}
        ${m.absent ? pill(`Наомад ${m.absent}`, 'danger') : ''}
        ${w.requests ? pill(`Дархост ${w.requests}`, 'brand') : ''}
        ${w.pending ? pill(`${w.pending} интизори қарор`, 'warn') : ''}
        ${!m.days && !w.requests && w.active ? '<span class="muted small">Ҳанӯз маълумот нест</span>' : ''}
      </div></button>`;
  }).join('')
    : emptyState(st.q ? 'Корманд ёфт нашуд' : 'Ин ҷо ҳоло касе нест', st.q ? 'Номи дигарро санҷед' : 'Корманд пас аз пахши /start дар бот пайдо мешавад', ICON.team);
}

async function openEmployee(uid, period = '') {
  openSheet(skel(3), { wide: true });
  const [d, m] = await Promise.all([
    api(`/api/workers/${uid}`),
    api(`/api/attendance/month?${qs({ user_id: uid, period })}`),
  ]);
  if (!d || !m) { closeSheet(); return; }
  const emp = m.employees.find((e) => e.user_id === uid) || { cells: {}, summary: {} };
  const s = emp.summary;
  const p = m.period;
  const r = d.summary;
  const hasEmployee = Boolean(d.first_seen);

  // Тақвим аз душанбе
  const lead = m.days.length ? m.days[0].wd : 0;
  const cal = WD.map((w) => `<div class="cal__wd">${w}</div>`).join('')
    + Array.from({ length: lead }, () => '<div class="cal__d is-empty"></div>').join('')
    + m.days.map((day) => {
      const c = emp.cells[day.date];
      const state = c ? c.s : day.future ? 'future' : !day.workday ? 'off' : 'none';
      const sub = c ? (c.t || { absent: 'Н', leave: 'Р', pending: '?' }[c.s] || '') : '';
      const clickable = c || (!day.future && day.workday) || day.future;
      return `<button class="cal__d s-${state}${day.today ? ' is-today' : ''}" ${clickable ? `data-cal="${day.date}"` : 'disabled'} title="${esc(fmtDay(day.date) + (c ? ' · ' + ATT[c.s].label : ''))}"><b>${Number(day.date.slice(8))}</b>${sub ? `<small>${esc(sub)}</small>` : ''}</button>`;
    }).join('');

  const typeRows = TYPE_ORDER.map((t) => ({
    label: `${TYPE[t].emoji} ${TYPE[t].label}`, value: d.by_type[t].count, color: TYPE[t].color,
    extra: d.by_type[t].minutes ? fmtHours(d.by_type[t].minutes) : '',
  }));

  $('#sheet-body').innerHTML = `
    <div class="detail-head">${avatar(d.name, d.user_id, 'avatar--lg' + (d.active ? '' : ' is-off'))}
      <div style="min-width:0"><b>${esc(shortName(d.name))}</b>
        <small>${d.username ? '@' + esc(d.username) + ' · ' : ''}${d.alias ? 'дар Telegram: ' + esc(shortName(d.tg_name)) : (d.first_seen ? 'аз ' + esc(fmtDateShort(d.first_seen)) : '')}</small></div></div>
    ${hasEmployee ? `<div class="card" style="border-radius:12px">
      <div class="setting"><div class="setting__text"><b>Саволи ҳаррӯзаи давомот</b><small>${d.active ? 'Ҳар рӯзи корӣ мепурсад «Ба кор омадед?»' : 'Хомӯш — ба ӯ савол намеравад'}</small></div>
        <label class="switch"><input type="checkbox" id="emp-active" ${d.active ? 'checked' : ''}><span></span></label></div>
      <div class="setting"><div class="setting__text"><b>Номи намоишӣ</b><small>${d.alias ? esc(d.alias) : 'Аз Telegram гирифта мешавад'}</small></div>
        <button class="btn btn--ghost btn--sm" id="emp-rename">${ICON.edit} Иваз</button></div></div>` : '<div class="alert alert--warn">Корманд аз рӯйхат нест шудааст — танҳо сабтҳои кӯҳна мондаанд.</div>'}

    <div class="section-title">Давомот</div>
    <div class="toolbar">
      <div class="nav-date">
        <button class="iconbtn" data-emp-period="${p.prev}" aria-label="Моҳи пеш">${ICON.left}</button>
        <div class="nav-date__label">${esc(monthTitle(p.key))}<small>${esc(rangeText(p.start, p.end))}</small></div>
        <button class="iconbtn" data-emp-period="${p.next || ''}" ${p.next ? '' : 'disabled style="opacity:.4"'} aria-label="Моҳи баъд">${ICON.right}</button>
      </div>
    </div>
    <div class="split split--4">
      <div class="mini"><b>${pctText(s.rate)}</b><small>давомот</small></div>
      <div class="mini"><b>${pctText(s.punctuality)}</b><small>сари вақт</small></div>
      <div class="mini"><b>${esc(s.avg_arrival || '—')}</b><small>миёнаи омадан</small></div>
      <div class="mini"><b>${fmtHours(s.late_minutes)}</b><small>ҳамагӣ дерӣ (${s.late || 0} бор)</small></div>
    </div>
    <div class="cal" id="emp-cal">${cal}</div>
    <div class="legend"><span><i style="background:var(--ok-soft)"></i>Сари вақт</span><span><i style="background:var(--warn-soft)"></i>Дер</span><span><i style="background:var(--danger-soft)"></i>Наомад</span><span><i style="background:var(--info-soft)"></i>Рухсатӣ</span><span><i style="box-shadow:inset 0 0 0 1.5px var(--border-2)"></i>Бе ҷавоб</span></div>

    <div class="section-title">Дархостҳо · ҳама вақт</div>
    ${r.total ? `<div class="split split--4">
      <div class="mini"><b>${r.total}</b><small>дархост</small></div>
      <div class="mini"><b>${pctText(r.accept_rate)}</b><small>иҷозат гирифт</small></div>
      <div class="mini"><b>${fmtHours(r.late_minutes)}</b><small>бо дархости «дер»</small></div>
      <div class="mini"><b>${r.pending}</b><small>интизори қарор</small></div>
    </div>
    ${hbars(typeRows)}
    ${d.reasons.length ? `<div class="section-title">Сабабҳои асосӣ</div>${hbars(reasonItems(d.reasons, 6))}` : ''}
    <div class="card" style="border-radius:12px"><div class="list" id="emp-items">${d.items.slice(0, 8).map((x) => requestCard({ ...x, alias: d.alias }, { del: false })).join('')}</div></div>
    ${d.items.length > 8 ? `<button class="btn btn--ghost btn--block" id="emp-all">Ҳамаи ${d.items.length} дархост ›</button>` : ''}`
    : emptyState('Дархост нафиристодааст', '', ICON.req)}

    <div class="sheet__actions" style="margin-top:6px">
      ${r.total ? `<button class="btn btn--ghost" id="emp-req">${ICON.req} Дархостҳо</button>` : ''}
      <button class="btn btn--soft-danger" id="emp-del">${ICON.trash} Нест кардани корманд</button>
    </div>`;

  const reopen = (per) => openEmployee(uid, per);
  $$('[data-emp-period]').forEach((b) => b.addEventListener('click', () => { if (b.dataset.empPeriod) reopen(b.dataset.empPeriod); }));
  $('#emp-cal').addEventListener('click', (e) => {
    const b = e.target.closest('[data-cal]');
    if (!b) return;
    const date = b.dataset.cal;
    openAttEdit(uid, d.name, date, emp.cells[date] || null, () => { refreshAttViewsQuiet(); reopen(p.key); });
  });
  const act = $('#emp-active');
  if (act) act.addEventListener('change', async () => {
    const res = await post(`/api/employees/${uid}`, { active: act.checked });
    if (!res) { act.checked = !act.checked; return; }
    haptic('success');
    toast(act.checked ? 'Акнун ба ӯ саволи давомот меравад' : 'Дигар ба ӯ савол намеравад', 'ok');
    refreshAttViewsQuiet();
    reopen(p.key);
  });
  const ren = $('#emp-rename');
  if (ren) ren.addEventListener('click', async () => {
    const value = await promptDialog({ title: 'Номи намоишӣ', text: 'Дар панел ва ҳисоботҳо ҳамин ном нишон дода мешавад. Холӣ гузоред — номи Telegram истифода мешавад.', label: 'Ном', value: d.alias || '', placeholder: shortName(d.tg_name), okText: 'Сабт кардан' });
    if (value === null) { reopen(p.key); return; }
    const res = await post(`/api/employees/${uid}`, { alias: value });
    if (res) { toast('Ном сабт шуд', 'ok'); S.workers = []; refreshAttViewsQuiet(); }
    reopen(p.key);
  });
  const items = $('#emp-items');
  if (items) items.addEventListener('click', (e) => { const c = e.target.closest('[data-rid]'); if (c) openRequest(Number(c.dataset.rid)); });
  const goReq = () => { closeSheet(); openRequestsWith({ user_id: String(uid) }); };
  if ($('#emp-req')) $('#emp-req').addEventListener('click', goReq);
  if ($('#emp-all')) $('#emp-all').addEventListener('click', goReq);
  $('#emp-del').addEventListener('click', async () => {
    const ok = await confirmDialog({
      title: `${shortName(d.name)} нест карда шавад?`,
      text: 'Корманд аз рӯйхат, ҳамаи дархостҳо ва давомоти ӯ нест мешаванд. Нусхаи эҳтиётии база худкор сохта мешавад. Агар ӯ боз /start-ро пахш кунад, аз нав илова мешавад.',
      okText: 'Нест кардан', danger: true,
    });
    if (!ok) { reopen(p.key); return; }
    const res = await post(`/api/workers/${uid}/delete`, {});
    if (!res) return;
    haptic('success');
    toast(res.message, 'ok');
    afterDataChange();
  });
}

/** Кэшҳоро тоза мекунад ва намуди ҷориро дар паси sheet нав мекунад. */
function refreshAttViewsQuiet() {
  S.stats.data = null;
  S.team.data = null;
  S.workers = [];
  S.inited.home = false; S.inited.stats = false;
  if (S.view === 'att') loadAtt();
  else if (S.view === 'team') loadTeam();
  else if (S.view === 'home') loadHome();
}

/* ══════════════ ОМОР ══════════════ */

function initStats() {
  S.inited.stats = true;
  const root = $('#view-stats');
  const st = S.stats;
  if (!root.dataset.built) {
    root.innerHTML = `
      <div class="toolbar">
        <div class="seg" id="st-tab"><button data-tab="att">Давомот</button><button data-tab="req">Дархостҳо</button></div>
        <div class="toolbar__group">
          <div style="min-width:210px">${periodPicker('stats', st)}</div>
          <button class="btn btn--ghost btn--sm" id="st-export">${ICON.download} CSV</button>
        </div>
      </div>
      ${rangeInputs('stats', st)}
      <div class="resultbar"><span id="st-label"></span></div>
      <div id="st-body" class="grid">${skel(4)}</div>`;
    root.dataset.built = '1';
    bindPeriod(root, 'stats', st, loadStats);
    $('#st-tab').addEventListener('click', (e) => { const b = e.target.closest('[data-tab]'); if (!b) return; st.tab = b.dataset.tab; haptic('light'); renderStats(); });
    $('#st-export').addEventListener('click', () => {
      if (st.tab === 'att') {
        const range = periodRange(st.period, st.from, st.to);
        const key = (range.date_from || todayYmd()).slice(0, 7);
        const start = range.date_from || workMonth(0).start;
        const k = Number(start.slice(8)) >= 5 ? key : (() => { const [y, m] = key.split('-').map(Number); return m === 1 ? `${y - 1}-12` : `${y}-${p2(m - 1)}`; })();
        download(`/api/attendance.csv?${qs({ period: k })}`);
      } else download(`/api/export.csv?${qs(periodRange(st.period, st.from, st.to))}`);
    });
    root.addEventListener('click', (e) => {
      const th = e.target.closest('[data-sort]');
      if (th) { const k = th.dataset.sort; st.sortDir = st.sortKey === k ? -st.sortDir : (k === 'name' ? 1 : (k === 'rate' || k === 'punctuality' ? 1 : -1)); st.sortKey = k; renderStats(); return; }
      const w = e.target.closest('[data-uid]');
      if (w) { openEmployee(Number(w.dataset.uid)); return; }
      const g = e.target.closest('[data-goto]');
      if (g) { go(g.dataset.goto); return; }
      const r = e.target.closest('#st-reasons [data-idx]');
      if (r && st.data) {
        const reason = st.data.reasons[Number(r.dataset.idx)];
        if (reason) openRequestsWith({ q: reason.reason, period: st.period, from: st.from, to: st.to });
      }
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
  if (!d) { $('#st-body').innerHTML = emptyState('Бор нашуд', 'Навсозӣ кунед'); return; }
  st.data = d;
  renderStats();
}

function renderStats() {
  const st = S.stats;
  $$('#st-tab [data-tab]').forEach((b) => b.classList.toggle('is-active', b.dataset.tab === st.tab));
  if (!st.data) return;
  if (st.tab === 'att') renderAttStats(st.data.attendance);
  else renderReqStats(st.data);
}

function renderAttStats(a) {
  const st = S.stats;
  const body = $('#st-body');
  const s = a.summary;
  if (!s.days) {
    body.innerHTML = `<div class="card"><div class="card__body">${emptyState('Дар ин давра давомот нест', a.schedule.enabled ? 'Давраи дигарро интихоб кунед' : 'Аввал дар «Давомот» вақти оғози кориро муқаррар кунед', ICON.att)}</div></div>`;
    return;
  }
  const workers = a.workers.slice();
  const dir = st.sortDir;
  const key = st.sortKey;
  workers.sort((x, y) => {
    if (key === 'name') return dir * shortName(x.name).localeCompare(shortName(y.name));
    const vx = x[key] ?? (key === 'avg_arrival' ? '99:99' : -1), vy = y[key] ?? (key === 'avg_arrival' ? '99:99' : -1);
    return dir * (vx > vy ? 1 : vx < vy ? -1 : 0);
  });
  const worstLate = a.workers.slice().sort((x, y) => y.late_minutes - x.late_minutes)[0];
  const worstAbs = a.workers.slice().sort((x, y) => y.absent - x.absent)[0];
  const best = a.workers.filter((w) => w.present >= 3).sort((x, y) => (y.punctuality ?? 0) - (x.punctuality ?? 0) || x.late_minutes - y.late_minutes)[0];
  const wl = a.weekday_late;
  const wlMax = Math.max(...wl);
  const insights = [
    s.rate != null ? `Давомоти умумӣ: <b>${s.rate}%</b> — аз ${s.present + s.absent + s.pending} рӯзи пурсидашуда ${s.present} рӯз омаданд` : '',
    s.punctuality != null ? `Сари вақт: <b>${s.punctuality}%</b> ҳолатҳо; ${s.late} бор дер омаданд (ҳамагӣ ${fmtHours(s.late_minutes)})` : '',
    best ? `Аз ҳама бонизомтар: <b>${esc(shortName(best.name))}</b> — ${pctText(best.punctuality)} сари вақт` : '',
    worstLate && worstLate.late_minutes ? `Бештар дер кардааст: <b>${esc(shortName(worstLate.name))}</b> — ${worstLate.late} бор, ${fmtHours(worstLate.late_minutes)}` : '',
    worstAbs && worstAbs.absent ? `Бештар наомадааст: <b>${esc(shortName(worstAbs.name))}</b> — ${worstAbs.absent} рӯз` : '',
    wlMax ? `Бештар рӯзи <b>${WD_FULL[wl.indexOf(wlMax)]}</b> дер меоянд (${wlMax} бор)` : '',
    s.pending ? `${s.pending} бор ба саволи бот ҷавоб надоданд` : '',
  ].filter(Boolean);

  const h = a.hist;
  const [sh, sm] = (h.start || '00:00').split(':').map(Number);
  const histLabels = h.edges.map((e, i) => {
    if (!h.start) return i === h.edges.length - 1 ? `+${e}` : String(e);
    const mins = sh * 60 + sm + e;
    const lbl = `${p2(Math.floor(((mins % 1440) + 1440) % 1440 / 60))}:${p2(((mins % 60) + 60) % 60)}`;
    return i === h.edges.length - 1 ? lbl + '+' : lbl;
  });
  const histColors = h.edges.map((e) => (e + 10 <= h.grace || e < 0 ? 'var(--ok)' : e < h.grace ? 'var(--warn)' : 'var(--warn)'));
  const zeroIdx = h.edges.indexOf(0);

  const th = (k, label, cls = '') => `<th class="sortable${cls}${key === k ? ' is-sorted' : ''}" data-sort="${k}">${label}${key === k ? (dir > 0 ? ' ↑' : ' ↓') : ''}</th>`;
  const bar = (v, color) => v == null ? '' : `<span class="bar-inline"><i style="width:${v}%;background:${color}"></i></span>`;

  body.innerHTML = `
    <div class="kpis">
      ${kpi('Давомот', pctText(s.rate), `${s.present} рӯз омаданд`, ICON.att, 'ok')}
      ${kpi('Сари вақт', pctText(s.punctuality), `${s.on_time} сари вақт · ${s.late} дер`, ICON.check, 'brand')}
      ${kpi('Миёнаи омадан', s.avg_arrival || '—', a.schedule.enabled ? `оғози кор ${a.schedule.time}` : '', ICON.clock, 'info')}
      ${kpi('Ҳамагӣ дерӣ', fmtHours(s.late_minutes), `${s.absent} наомад · ${s.leave} рухсатӣ`, ICON.hourglass, 'warn')}
    </div>
    ${insights.length ? `<div class="card"><div class="card__head"><h2>Хулосаҳо</h2></div>
      <div class="card__body"><div class="insights">${insights.map((t) => `<div class="insight">${ICON.bulb}<span>${t}</span></div>`).join('')}</div></div></div>` : ''}
    <div class="card"><div class="card__head"><h2>Давомот аз рӯи рӯзҳо</h2><span class="card__note">${a.daily.length} рӯз</span></div>
      <div class="card__body">${stackCols(a.daily, ATT_KEYS)}</div></div>
    <div class="grid grid-2">
      <div class="card"><div class="card__head"><h2>Вақти омадан</h2><span class="card__note">${a.schedule.enabled ? `оғози кор ${esc(a.schedule.time)} · сари вақт то +${h.grace} дақ` : ''}</span></div>
        <div class="card__body">${h.values.some(Boolean) ? simpleCols(h.values, histLabels, histColors, { highlight: zeroIdx, height: 160 }) : emptyState('Ҳанӯз вақти омадан сабт нашудааст')}</div></div>
      <div class="card"><div class="card__head"><h2>Дер омадан аз рӯи рӯзҳои ҳафта</h2></div>
        <div class="card__body">${wlMax ? simpleCols(wl, WD, 'var(--warn)', { highlight: wl.indexOf(wlMax), height: 160 }) : emptyState('Касе дер накардааст', '', ICON.check)}</div></div>
    </div>
    <div class="card"><div class="card__head"><h2>Кормандон</h2><span class="card__note">сутунро пахш кунед — тартиб иваз мешавад</span></div>
      <div class="table-wrap"><table class="table">
        <thead><tr>${th('name', 'Корманд')}${th('rate', 'Давомот', ' num')}${th('punctuality', 'Сари вақт', ' num')}${th('late', 'Дер', ' num')}${th('late_minutes', 'Дерӣ', ' num')}${th('absent', 'Наомад', ' num')}${th('pending', 'Бе ҷавоб', ' num')}${th('avg_arrival', 'Миёнаи омадан', ' num')}</tr></thead>
        <tbody>${workers.map((w) => `<tr data-uid="${w.user_id}">
          <td><div class="who">${avatar(w.name, w.user_id, 'avatar--sm')}<b>${esc(shortName(w.name))}</b></div></td>
          <td class="num">${pctText(w.rate)}${bar(w.rate, 'var(--ok)')}</td>
          <td class="num">${pctText(w.punctuality)}${bar(w.punctuality, 'var(--brand)')}</td>
          <td class="num" style="color:${w.late ? 'var(--warn-text)' : 'inherit'}">${w.late}</td>
          <td class="num">${w.late_minutes ? fmtHours(w.late_minutes) : '—'}</td>
          <td class="num" style="color:${w.absent ? 'var(--danger-text)' : 'inherit'}">${w.absent}</td>
          <td class="num">${w.pending || '—'}</td>
          <td class="num">${esc(w.avg_arrival || '—')}</td></tr>`).join('')}</tbody></table></div></div>`;
}

function renderReqStats(d) {
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
    `Бештар — <b>${TYPE[topType].label.toLowerCase()}</b>: ${bt[topType].count} дархост (${pct(bt[topType].count, s.total)}%)`,
    d.reasons[0] ? `Сабаби маъмултарин: <b>${esc(d.reasons[0].reason)}</b> — ${d.reasons[0].count} бор` : '',
    Math.max(...d.weekday) ? `Бештар рӯзи <b>${WD_FULL[wdMax]}</b> дархост мефиристанд (${d.weekday[wdMax]})` : '',
    Math.max(...d.hours) ? `Вақти серкортарин: <b>${p2(hMax)}:00–${p2(hMax + 1)}:00</b>` : '',
    topWorker ? `Бештар дархост: <b>${esc(shortName(topWorker.name))}</b> — ${topWorker.total}` : '',
    lateLeader && lateLeader.late_minutes ? `Бештар «дер мекунам»: <b>${esc(shortName(lateLeader.name))}</b> — ${fmtHours(lateLeader.late_minutes)}` : '',
  ].filter(Boolean);

  const statusItems = STATUS_ORDER.map((k) => ({
    label: STATUS[k].label, value: d.by_status[k] || 0, color: STATUS[k].color, extra: `${pct(d.by_status[k] || 0, s.total)}%`,
  }));
  const workersRows = d.workers.slice(0, 12).map((w, i) => `
    <button class="person" data-uid="${w.user_id}">
      <div class="person__head"><span class="muted" style="width:18px;text-align:center;font-weight:700">${i + 1}</span>${avatar(w.name, w.user_id, 'avatar--sm')}
        <div class="person__who"><b>${esc(shortName(w.name))}</b>
          <small>Дер ${w.late} · Намеояд ${w.absent} · Ҷавоб ${w.at_work_waiting} · Барвақт ${w.leaving_early}</small></div>
        <div class="person__score"><b>${w.total}</b><small>${w.late_minutes ? fmtHours(w.late_minutes) : 'дархост'}</small></div></div>
      ${typeStackbar({ late: w.late, absent: w.absent, at_work_waiting: w.at_work_waiting, leaving_early: w.leaving_early })}
    </button>`).join('');
  const hourMax = Math.max(1, ...d.hours.slice(6, 22));
  const heat = d.hours.slice(6, 22).map((v, i) => {
    const hh = i + 6;
    const a = v ? 0.18 + (0.82 * v) / hourMax : 0;
    return `<div class="heat__cell" title="${p2(hh)}:00 — ${v}" style="${v ? `background:color-mix(in srgb, var(--brand) ${Math.round(a * 100)}%, var(--surface-2));color:${a > 0.55 ? '#fff' : 'var(--text)'}` : ''}">${v || ''}<small>${hh}</small></div>`;
  }).join('');
  const arr = d.arrivals || {};

  body.innerHTML = `
    <div class="kpis">
      ${kpi('Ҳамагӣ дархост', s.total, `${s.people} корманд`, ICON.req, 'brand')}
      ${kpi('Иҷозат гирифтанд', pctText(s.accept_rate), `${s.accepted} иҷозат · ${s.rejected} рад`, ICON.percent, 'ok')}
      ${kpi('Вақти миёнаи ҷавоб', s.avg_response_min != null ? fmtMinutes(Math.max(1, s.avg_response_min)) : '—', 'аз дархост то қарор', ICON.bolt, 'violet')}
      ${kpi('Вақти «дер мекунам»', fmtHours(s.late_minutes), `миёна ${s.avg_minutes ? fmtMinutes(s.avg_minutes) : '—'} дар як дархост`, ICON.clock, 'warn')}
    </div>
    <div class="card"><div class="card__head"><h2>Хулосаҳо</h2></div>
      <div class="card__body"><div class="insights">${insights.map((t) => `<div class="insight">${ICON.bulb}<span>${t}</span></div>`).join('')}</div></div></div>
    <div class="grid grid-2">
      <div class="card"><div class="card__head"><h2>Аз рӯи навъ</h2></div>
        <div class="card__body">${donut(TYPE_ORDER.map((t) => ({ label: TYPE[t].label, value: bt[t].count, color: TYPE[t].color })), s.total, 'дархост')}</div></div>
      <div class="card"><div class="card__head"><h2>Қарорҳо</h2><span class="card__note">${s.pending ? s.pending + ' интизор' : ''}</span></div>
        <div class="card__body">${hbars(statusItems)}
          <div class="split" style="margin-top:14px">
            <div class="mini"><b>${arr.arrived || 0}</b><small>дар вақти гуфтааш расид</small></div>
            <div class="mini"><b>${arr.delayed || 0}</b><small>боз дер кард</small></div>
          </div></div></div>
      <div class="card span-2"><div class="card__head"><h2>Дархостҳо аз рӯи рӯзҳо</h2><span class="card__note">${d.daily.length} рӯз</span></div>
        <div class="card__body">${stackCols(flatTypes(d.daily), TYPE_KEYS)}</div></div>
      <div class="card"><div class="card__head"><h2>Сабабҳои асосӣ</h2><span class="card__note">пахш кунед — дархостҳо</span></div>
        <div class="card__body" id="st-reasons">${hbars(reasonItems(d.reasons, 10), { link: true })}</div></div>
      <div class="card"><div class="card__head"><h2>Рӯзҳои ҳафта</h2></div>
        <div class="card__body">${simpleCols(d.weekday, WD, 'var(--brand)', { highlight: Math.max(...d.weekday) ? wdMax : -1 })}</div>
        <div class="card__head" style="padding-top:0"><h2>Соатҳои рӯз</h2></div>
        <div class="card__body"><div class="heat">${heat}</div></div></div>
      <div class="card span-2"><div class="card__head"><h2>Кормандон</h2><span class="spacer"></span><button class="linkbtn" data-goto="team">Ҳама ›</button></div>
        <div class="list">${workersRows}</div></div>
      ${d.deciders.length ? `<div class="card span-2"><div class="card__head"><h2>Кӣ қарор қабул кард</h2></div>
        <div class="card__body">${hbars(d.deciders.map((x) => ({
          label: shortName(x.name), value: x.total,
          segments: [{ value: x.accepted, color: 'var(--ok)' }, { value: x.rejected, color: 'var(--danger)' }],
          extra: `${x.accepted} иҷозат · ${x.rejected} рад`,
        })))}</div></div>` : ''}
    </div>`;
}

/* ══════════════ ТАНЗИМОТ ══════════════ */

async function initSettings() {
  S.inited.settings = true;
  const root = $('#view-settings');
  root.innerHTML = skel(3);
  const [acc, health, backups, sch] = await Promise.all([
    api('/api/account'), api('/api/health', { quiet: true }), api('/api/backups', { quiet: true }), api('/api/work-schedule', { quiet: true }),
  ]);
  if (!acc) return;
  if (sch) S.schedule = sch;
  const theme = document.documentElement.dataset.theme;
  const poll = health && health.polling;
  const upD = health ? Math.floor(health.uptime / 86400) : 0;
  const upH = health ? Math.floor((health.uptime % 86400) / 3600) : 0;
  const upM = health ? Math.floor((health.uptime % 3600) / 60) : 0;
  const uptime = upD ? `${upD} рӯз ${upH} соат` : `${upH} соат ${upM} дақ`;
  const bList = (backups && backups.items) || [];
  const botOk = poll && poll.ok && !poll.conflict;

  root.innerHTML = `
    <div class="grid grid-2">
      <div class="card">
        <div class="card__head"><h2>Вақти корӣ</h2></div>
        <div class="card__body--flush">
          <div class="setting"><div class="setting__text"><b>${S.schedule && S.schedule.enabled ? 'Оғози кор: ' + esc(S.schedule.time) : 'Хомӯш'}</b>
            <small>${S.schedule && S.schedule.enabled ? esc(`${S.schedule.days.map((x) => WD[x]).join(' · ')} · дер — баъди ${S.schedule.grace} дақ · ҳисобот ба гурӯҳ: ${S.schedule.report ? 'бале' : 'не'}`) : 'Бот аз кормандон намепурсад, ки ба кор омаданд ё не'}</small></div>
            <button class="btn btn--primary btn--sm" data-open-schedule>${S.schedule && S.schedule.enabled ? 'Тағйир додан' : 'Муқаррар кардан'}</button></div>
        </div>
      </div>

      <div class="card">
        <div class="card__head"><h2>Логин ва рамз</h2><span class="card__note">ҳозир: ${esc(acc.login)}</span></div>
        <div class="card__body">
          <form class="stack" id="acc-form" autocomplete="off">
            <label class="field"><span class="field__label">Логини нав</span>
              <input id="acc-login" type="text" autocapitalize="none" autocorrect="off" spellcheck="false" value="${esc(acc.login)}" autocomplete="off"></label>
            <label class="field"><span class="field__label">Рамзи нав</span>
              <span class="field__wrap"><input id="acc-new" type="password" autocomplete="new-password" placeholder="ақаллан 6 аломат">
              <button type="button" class="field__eye" data-eye="acc-new" aria-label="Нишон додан">${ICON.lock}</button></span></label>
            <label class="field"><span class="field__label">Рамзи нав — бори дигар</span>
              <input id="acc-new2" type="password" autocomplete="new-password"></label>
            <div id="acc-err" class="alert alert--danger" hidden></div>
            <button class="btn btn--primary btn--block" type="submit" id="acc-save">Сабт кардан</button>
            <span class="field__hint">Пас аз иваз дар дигар телефону компютерҳо бояд аз нав ворид шавед.</span>
          </form>
        </div>
      </div>

      <div class="card">
        <div class="card__head"><h2>Панел дар Telegram</h2></div>
        <div class="card__body stack">
          <p class="sheet__text">Дар бот фармони <b>/admin</b>-ро фиристед — ду тугма меояд: <b>«Кушодан дар Telegram»</b> ва <b>«Кушодан дар браузер»</b>.</p>
          <p class="sheet__text">Админҳои гурӯҳи роҳбарият дар дохили Telegram <b>бе рамз</b> ворид мешаванд.</p>
          ${acc.via === 'telegram' ? `<div class="alert alert--ok">Шумо ҳоло бо Telegram ворид шудаед: ${esc(acc.me || '')}</div>` : ''}
        </div>
      </div>

      <div class="card">
        <div class="card__head"><h2>Маълумот</h2></div>
        <div class="card__body--flush">
          <div class="setting"><div class="setting__text"><b>Нусхаи база</b><small>Файли пурраи .db барои нигоҳдорӣ</small></div>
            <button class="btn btn--ghost btn--sm" id="set-backup">${ICON.download} Боргирӣ</button></div>
          <div class="setting"><div class="setting__text"><b>Давомот ба Excel</b><small>Моҳи кории ҷорӣ (CSV)</small></div>
            <button class="btn btn--ghost btn--sm" id="set-att-csv">${ICON.download} CSV</button></div>
          <div class="setting"><div class="setting__text"><b>Дархостҳо ба Excel</b><small>Ҳамаи дархостҳо (CSV)</small></div>
            <button class="btn btn--ghost btn--sm" id="set-csv">${ICON.download} CSV</button></div>
          <div class="setting"><div class="setting__text"><b>Нусхаҳои худкор</b>
            <small>${bList.length ? `${bList.length} адад · охирин: ${esc(bList[0].time)}` : 'Ҳар рӯз ва пеш аз ҳар нест кардан сохта мешавад'}</small></div></div>
        </div>
      </div>

      <div class="card">
        <div class="card__head"><h2>Система</h2></div>
        <div class="card__body--flush">
          <div class="setting"><div class="setting__text"><b>Бот</b>
            <small><span class="status-dot" style="background:${botOk ? 'var(--ok)' : 'var(--danger)'}"></span>${poll && poll.conflict ? 'Ҳамин бот дар ҷои дигар ҳам оғоз шудааст — нусхаи дигарро хомӯш кунед' : botOk ? `Кор мекунад · ${uptime} бе таваққуф` : 'Ҷавоб намедиҳад — худаш аз нав оғоз мешавад'}</small></div></div>
          <div class="setting"><div class="setting__text"><b>Мавзӯъ</b><small>${theme === 'dark' ? 'Торик' : 'Равшан'}</small></div>
            <button class="btn btn--ghost btn--sm" data-action="theme">${theme === 'dark' ? ICON.sun + ' Равшан' : 'Торик'}</button></div>
          <div class="setting"><div class="setting__text"><b>Версия</b><small>${esc(health ? `${health.version} · ${health.tz}` : '—')}</small></div></div>
          <div class="setting"><div class="setting__text"><b>Баромадан</b><small>Аз ҳамин дастгоҳ</small></div>
            <button class="btn btn--soft-danger btn--sm" data-action="logout">Баромадан</button></div>
        </div>
      </div>

      <div class="card danger-zone span-2">
        <div class="card__head"><h2>Тоза кардани база</h2></div>
        <div class="card__body stack">
          <p class="sheet__text">Пеш аз ҳар тозакунӣ нусхаи эҳтиётии база худкор сохта мешавад. Логин, рамз ва вақти корӣ нест намешаванд.</p>
          <div class="setting" style="padding:0;flex-wrap:wrap">
            <div class="setting__text"><b>Маълумоти кӯҳна</b><small>Дархостҳо ва давомот то санаи интихобшуда (бо ҳамон рӯз)</small></div>
            <div class="row-flex" style="flex:1 1 260px;flex-wrap:nowrap">
              <input type="date" class="input" id="wipe-before" max="${todayYmd()}" aria-label="То сана">
              <button class="btn btn--soft-danger" id="wipe-old">Нест кардан</button>
            </div>
          </div>
          <div class="grid grid-2">
            <button class="btn btn--soft-danger btn--block" id="wipe-req">${ICON.trash} Ҳамаи дархостҳо ва давомот</button>
            <button class="btn btn--danger btn--block" id="wipe-all">${ICON.alert} Тозакунии пурра (бо кормандон)</button>
          </div>
        </div>
      </div>
    </div>`;

  bindEyes(root);
  root.querySelector('[data-open-schedule]').addEventListener('click', openSchedule);
  $('#acc-form').addEventListener('submit', saveAccount);
  $('#set-backup').addEventListener('click', () => download('/api/backup.db'));
  $('#set-csv').addEventListener('click', () => download('/api/export.csv'));
  $('#set-att-csv').addEventListener('click', () => download(`/api/attendance.csv?period=${workMonth(0).key}`));
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
  const fail = (m) => { err.textContent = m; err.hidden = false; haptic('error'); };
  if (!/^[A-Za-z0-9_.@-]{3,32}$/.test(newLogin)) return fail('Логин: 3–32 аломат — ҳарфи лотинӣ, рақам ва _ . @ -');
  if (!p1) return fail('Рамзи навро нависед');
  if (p1.length < 6) return fail('Рамз бояд ақаллан 6 аломат бошад');
  if (/^\d+$/.test(p1) && p1.length < 8) return fail('Рамзи танҳо аз рақамҳо бояд ақаллан 8 аломат бошад');
  if (p1 !== p2v) return fail('Рамзҳо якхела нестанд');
  const btn = $('#acc-save');
  btn.classList.add('is-loading');
  const res = await post('/api/account', { new_login: newLogin, new_password: p1, new_password_confirm: p2v }, { raw: true, quiet: true });
  btn.classList.remove('is-loading');
  if (!res || res.error) return fail((res && res.error) || 'Алоқа нест');
  token = res.token;
  store.set('sc_token', token);
  haptic('success');
  toast('Логин ва рамз иваз шуданд', 'ok');
  initSettings();
}

async function doWipe(scope, before) {
  const text = before
    ? `Ҳамаи дархостҳо ва давомот то ${fmtDateShort(before)} (бо ҳамон рӯз) нест мешаванд.`
    : scope === 'all'
      ? 'ҲАМАИ дархостҳо, давомот ва рӯйхати кормандон нест мешаванд. Рақамгузорӣ аз #1 сар мешавад.'
      : 'ҲАМАИ дархостҳо ва давомот нест мешаванд. Рӯйхати кормандон мемонад.';
  const ok = await confirmDialog({
    title: before ? 'Нест кардани маълумоти кӯҳна' : scope === 'all' ? 'Тозакунии пурраи база' : 'Нест кардани ҳамаи дархостҳо ва давомот',
    text: text + ' Нусхаи эҳтиётӣ худкор сохта мешавад.',
    okText: 'Ҳа, тоза кунед', danger: true,
  });
  if (!ok) return;
  const res = await post('/api/wipe', { scope, before: before || '' });
  if (!res) return;
  haptic('success');
  toast(res.message, 'ok');
  afterDataChange();
}

/* ══════════════ Sheet, тасдиқ ва ворид кардан ══════════════ */

function openSheet(html, opts = {}) {
  const sheet = $('#sheet');
  if (sheet._resolve) { const r = sheet._resolve; sheet._resolve = null; r(null); }
  $('#sheet-body').innerHTML = html;
  sheet.classList.toggle('sheet--wide', Boolean(opts.wide));
  sheet.hidden = false;
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

/** Як саволи оддӣ: ҳа/не. Бармегардонад true ё null. */
function confirmDialog({ title, text, okText = 'Тасдиқ', danger = false }) {
  return new Promise((resolve) => {
    openSheet(`
      <div class="sheet__title">${esc(title)}</div>
      <p class="sheet__text">${esc(text)}</p>
      <div class="sheet__actions">
        <button class="btn btn--ghost btn--lg" id="cf-no">Бекор</button>
        <button class="btn ${danger ? 'btn--danger' : 'btn--primary'} btn--lg" id="cf-yes">${esc(okText)}</button>
      </div>`);
    const sheet = $('#sheet');
    sheet._resolve = resolve;
    if (danger) haptic('warning');
    $('#cf-no').addEventListener('click', () => closeSheet());
    $('#cf-yes').addEventListener('click', () => { sheet._resolve = null; closeSheet(); resolve(true); });
    setTimeout(() => { const b = $('#cf-yes'); if (b) b.focus(); }, 60);
  });
}

/** Як майдони матн. Бармегардонад матн ё null (бекор). */
function promptDialog({ title, text = '', label = '', value = '', placeholder = '', okText = 'Сабт кардан' }) {
  return new Promise((resolve) => {
    openSheet(`
      <div class="sheet__title">${esc(title)}</div>
      ${text ? `<p class="sheet__text">${esc(text)}</p>` : ''}
      <label class="field"><span class="field__label">${esc(label)}</span>
        <input class="input" id="pr-in" type="text" maxlength="80" value="${esc(value)}" placeholder="${esc(placeholder)}"></label>
      <div class="sheet__actions">
        <button class="btn btn--ghost btn--lg" id="pr-no">Бекор</button>
        <button class="btn btn--primary btn--lg" id="pr-yes">${esc(okText)}</button>
      </div>`);
    const sheet = $('#sheet');
    sheet._resolve = resolve;
    const input = $('#pr-in');
    const ok = () => { const v = input.value.trim(); sheet._resolve = null; closeSheet(); resolve(v); };
    $('#pr-no').addEventListener('click', () => closeSheet());
    $('#pr-yes').addEventListener('click', ok);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') ok(); });
    setTimeout(() => input.focus(), 80);
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
    const vb = e.target.closest('[data-view-btn]');
    if (vb) { haptic('light'); go(vb.dataset.viewBtn); return; }
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
  $('#toast-action').addEventListener('click', () => {
    const fn = toastAction;
    toastAction = null;
    $('#toast').hidden = true;
    if (fn) fn();
  });
  $$('[data-close]').forEach((el) => el.addEventListener('click', closeSheet));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });
  window.addEventListener('scroll', () => {
    $('.topbar').classList.toggle('is-scrolled', window.scrollY > 4);
  }, { passive: true });
  window.addEventListener('hashchange', () => {
    const name = location.hash.slice(1);
    if (token && name && name !== S.view && VIEWS.find((x) => x.id === name)) go(name);
  });
  $('#login-form').addEventListener('submit', doLogin);
  bindEyes($('#login'));
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { flushDeletes(); return; }
    if (token && !$('#app').hidden) refreshPending();
  });
  window.addEventListener('pagehide', flushDeletes);
}

async function boot() {
  initTelegram();
  applyTheme(preferredTheme());
  buildNav();
  bindGlobal();
  const fromHash = location.hash.slice(1);
  const saved = fromHash || store.get('sc_view');
  if (saved && VIEWS.find((v) => v.id === saved)) S.view = saved;

  try {
    const h = await (await fetch(`${API}/api/health`, { cache: 'no-store' })).json();
    if (h && h.time) S.today = h.time.slice(0, 10);
    $('#login-foot').textContent = `SoftClub HR Control · v${h.version}`;
  } catch (_) {}

  if (!token && tg) await tryTelegramLogin();
  if (!token) { showLogin(); return; }
  showApp();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();

})();
