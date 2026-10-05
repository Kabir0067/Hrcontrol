"""
SoftClub / Hrcontrol — мантиқи бот.

Таҷрибаи корбар:
  1. /start → интихоби вазъият (1 пахш)
  2. сабаб → тугмаҳои тайёр ё матни худӣ (1 пахш)
  3. вақт → тугмаҳои тайёр ё рақами худӣ (1 пахш)
  4. пешнамоиш → «Фиристодан»

Ҳеҷ гоҳ маҷбур намекунад матн нависад — вале ҳамеша имкон медиҳад.
"""

from __future__ import annotations

import html
import logging
from datetime import timedelta

from telebot.async_telebot import AsyncTeleBot
from telebot.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    LinkPreviewOptions,
    WebAppInfo,
)

import config as cfg
import database as db

log = logging.getLogger("SoftClubBot")

GROUP_ID = cfg.GROUP_ID
MINUTES_MAX = cfg.MINUTES_MAX


# ══════════════════════════════════════════════════════════════════════════
#  Луғати вазъиятҳо
# ══════════════════════════════════════════════════════════════════════════

TYPES: dict[str, dict] = {
    "late": {
        "emoji": "🕰",
        "self": "Дер мекунам",
        "third": "Дер мекунад",
        "ask_time": True,
        "reason_q": "Чаро дер мемонед? Интихоб кунед ё худатон нависед:",
        "time_q": "Тақрибан чанд дақиқа дер мемонед?",
        "time_word": "дер мекунад",
        "reasons": [
            "Мушкилии нақлиёт",
            "Роҳбандӣ (пробка)",
            "Кори шахсӣ",
            "Аҳволам нағз нест",
            "Ба духтур рафтам",
        ],
    },
    "absent": {
        "emoji": "🌿",
        "self": "Имрӯз намеоям",
        "third": "Имрӯз намеояд",
        "ask_time": False,
        "reason_q": "Чаро имрӯз намеоед? Интихоб кунед ё худатон нависед:",
        "time_q": None,
        "time_word": "",
        "reasons": [
            "Бемор шудам",
            "Кори оилавӣ",
            "Ба духтур меравам",
            "Сафари корӣ",
            "Ҳолати фавқулодда",
        ],
    },
    "at_work_waiting": {
        "emoji": "☕",
        "self": "Ҷавоб мегирам",
        "third": "Ҷавоб мепурсад",
        "ask_time": True,
        "reason_q": "Барои чӣ меравед? Интихоб кунед ё худатон нависед:",
        "time_q": "Чанд дақиқа лозим аст?",
        "time_word": "ҷавоб мепурсад",
        "reasons": [
            "Кори шахсӣ",
            "Ба банк / идора",
            "Ба духтур",
            "Кори оилавӣ",
            "Хӯроки нисфирӯзӣ",
        ],
    },
    "leaving_early": {
        "emoji": "🌅",
        "self": "Барвақт меравам",
        "third": "Барвақт меравад",
        "ask_time": True,
        "reason_q": "Чаро барвақт меравед? Интихоб кунед ё худатон нависед:",
        "time_q": "Баъди чанд дақиқа меравед?",
        "time_word": "барвақт меравад",
        "reasons": [
            "Кори шахсӣ",
            "Аҳволам нағз нест",
            "Кори оилавӣ",
            "Ба духтур",
            "Меҳмон дорам",
        ],
    },
}

TYPE_ORDER = ("late", "absent", "at_work_waiting", "leaving_early")

# Барои мутобиқат бо коди кӯҳна (admin_server ва ғ.)
TYPE_LABELS = {k: (v["emoji"], v["third"]) for k, v in TYPES.items()}

QUICK_MINUTES = [10, 15, 20, 30, 45, 60, 90, 120]
QUICK_EXTRA_MINUTES = [5, 10, 15, 20, 30, 45]

# Давомот: сабабҳо ва вақтҳои тайёр (корманд бояд ҳарчи камтар нависад)
ATT_REASONS = [
    "🚗 Дар роҳ ҳастам",
    "🤒 Бемор ҳастам",
    "🏥 Ба духтур рафтам",
    "👨‍👩‍👧 Кори оилавӣ",
    "📄 Кори шахсӣ",
]
ATT_ETA = [
    ("30", "30 дақиқа баъд"),
    ("60", "1 соат баъд"),
    ("120", "2 соат баъд"),
    ("noon", "Баъди нисфирӯзӣ"),
    ("today", "Имрӯз намеоям"),
    ("tomorrow", "Пагоҳ меоям"),
]
WEEKDAYS = ["душанбе", "сешанбе", "чоршанбе", "панҷшанбе", "ҷумъа", "шанбе", "якшанбе"]
MONTHS_GEN = ["январ", "феврал", "март", "апрел", "май", "июн", "июл", "август",
              "сентябр", "октябр", "ноябр", "декабр"]

STATUS_WORD = {
    "pending": "⏳ Интизори ҷавоб",
    "accepted": "✅ Иҷозат дода шуд",
    "rejected": "✋ Рад шуд",
    "cancelled": "🚫 Бекор шуд",
}


# ══════════════════════════════════════════════════════════════════════════
#  Ёрдамчиҳо
# ══════════════════════════════════════════════════════════════════════════

def _private(message) -> bool:
    """Фармонҳо танҳо дар чати шахсӣ кор мекунанд."""
    return getattr(message.chat, "type", None) == "private"


def _esc(value) -> str:
    """Ҳатмист: матни корбар бе escape parse_mode=HTML-ро вайрон мекунад."""
    return html.escape(str(value or ""), quote=False)


def _display_name(user) -> str:
    name = (user.first_name or "").strip()
    if user.last_name:
        name = f"{name} {user.last_name.strip()}".strip()
    name = name or "Ҳамкор"
    if user.username:
        return f"{name} (@{user.username})"
    return name


def _short_name(full: str) -> str:
    return full.split(" (@")[0].strip() or full


def _clock(value: str | None) -> str:
    dt = cfg.parse_dt(value)
    return dt.strftime("%H:%M") if dt else "—"


def _stamp(value: str | None) -> str:
    dt = cfg.parse_dt(value)
    return dt.strftime("%d.%m · %H:%M") if dt else "—"


def _human_minutes(minutes: int) -> str:
    if minutes <= 0:
        return "—"
    if minutes < 60:
        return f"{minutes} дақ."
    hours, rest = divmod(minutes, 60)
    return f"{hours} соат" if rest == 0 else f"{hours} соат {rest} дақ."


async def _safe(coro):
    """Ҳар садои Telegram метавонад хато диҳад — набояд ҳалқаро кушад."""
    try:
        return await coro
    except Exception as exc:
        text = str(exc)
        if "message is not modified" in text or "query is too old" in text:
            log.debug("Telegram API: %s", text)
        else:
            log.warning("Telegram API: %s", text[:300])
        return None


def _from_group(call: CallbackQuery) -> bool:
    """Қарори роҳбарият танҳо аз паёми гурӯҳи корӣ қабул мешавад."""
    return bool(call.message) and call.message.chat.id == GROUP_ID


# ══════════════════════════════════════════════════════════════════════════
#  Клавиатураҳо
# ══════════════════════════════════════════════════════════════════════════

def _main_reply_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, input_field_placeholder="Интихоб кунед…")
    kb.row(KeyboardButton("📝 Дархости нав"))
    kb.row(KeyboardButton("📋 Дархостҳои ман"), KeyboardButton("ℹ️ Кӯмак"))
    return kb


def _kb_types() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for key in TYPE_ORDER:
        meta = TYPES[key]
        kb.add(InlineKeyboardButton(f"{meta['emoji']}  {meta['self']}", callback_data=f"t:{key}"))
    return kb


def _kb_reasons(req_type: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    reasons = TYPES[req_type]["reasons"]
    buttons = [InlineKeyboardButton(r, callback_data=f"r:{i}") for i, r in enumerate(reasons)]
    for i in range(0, len(buttons), 2):
        kb.row(*buttons[i:i + 2])
    kb.row(InlineKeyboardButton("✍️ Худам менависам", callback_data="r:x"))
    kb.row(InlineKeyboardButton("‹ Бозгашт", callback_data="f:back_type"),
           InlineKeyboardButton("❌ Бекор", callback_data="f:cancel"))
    return kb


def _kb_minutes() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=4)
    buttons = [InlineKeyboardButton(str(m), callback_data=f"m:{m}") for m in QUICK_MINUTES]
    for i in range(0, len(buttons), 4):
        kb.row(*buttons[i:i + 4])
    kb.row(InlineKeyboardButton("✍️ Вақти дигар", callback_data="m:x"))
    kb.row(InlineKeyboardButton("‹ Бозгашт", callback_data="f:back_reason"),
           InlineKeyboardButton("❌ Бекор", callback_data="f:cancel"))
    return kb


def _kb_extra_minutes() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(str(m), callback_data=f"am:{m}") for m in QUICK_EXTRA_MINUTES]
    for i in range(0, len(buttons), 3):
        kb.row(*buttons[i:i + 3])
    kb.row(InlineKeyboardButton("✍️ Вақти дигар", callback_data="am:x"))
    return kb


def _kb_confirm() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Фиристодан", callback_data="f:send"))
    kb.row(InlineKeyboardButton("✏️ Аз нав", callback_data="f:back_type"),
           InlineKeyboardButton("❌ Бекор", callback_data="f:cancel"))
    return kb


def _kb_cancel_only() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ Бекор кардан", callback_data="f:cancel"))
    return kb


# Префикси «att:» — ҷудо аз «w:» (ёдовариҳои дархост), вагарна ҷавоби давомот
# ба handler-и нодуруст меафтод.

def _kb_att_prompt(attendance_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(
        InlineKeyboardButton("✅ Омадам", callback_data=f"att:y:{attendance_id}"),
        InlineKeyboardButton("❌ Наомадам", callback_data=f"att:n:{attendance_id}"),
    )
    return kb


def _kb_att_reasons(attendance_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(r, callback_data=f"atr:{i}") for i, r in enumerate(ATT_REASONS)]
    for i in range(0, len(buttons), 2):
        kb.row(*buttons[i:i + 2])
    kb.row(InlineKeyboardButton("✍️ Сабаби дигар", callback_data="atr:x"))
    kb.row(InlineKeyboardButton("‹ Бозгашт", callback_data=f"att:back:{attendance_id}"))
    return kb


def _kb_att_eta(attendance_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(label, callback_data=f"ate:{key}") for key, label in ATT_ETA]
    for i in range(0, len(buttons), 2):
        kb.row(*buttons[i:i + 2])
    kb.row(InlineKeyboardButton("✍️ Худам менависам", callback_data="ate:x"))
    kb.row(InlineKeyboardButton("‹ Бозгашт", callback_data=f"att:back:{attendance_id}"))
    return kb


def _kb_att_back(attendance_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("‹ Бозгашт", callback_data=f"att:back:{attendance_id}"))
    return kb


def _kb_att_arrived(attendance_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Ман омадам", callback_data=f"att:arr:{attendance_id}"))
    return kb


def _kb_admin_decision(req_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton("✅ Иҷозат", callback_data=f"d:a:{req_id}"),
           InlineKeyboardButton("✋ Рад кардан", callback_data=f"d:r:{req_id}"))
    return kb


def _kb_admin_after(req_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💬 Паём ба корманд", callback_data=f"fb:{req_id}"))
    return kb


# ══════════════════════════════════════════════════════════════════════════
#  Матнҳо
# ══════════════════════════════════════════════════════════════════════════

def _welcome(first_name: str) -> str:
    return (
        f"👋 Салом, <b>{_esc(first_name)}</b>!\n\n"
        "Ин боти кории <b>SoftClub</b> аст.\n"
        "Агар дер монед, наоед ё ҷавоб пурсед — ҳамин ҷо нависед.\n"
        "Роҳбарият зуд мебинад ва ҷавобаш ҳам ҳамин ҷо меояд. 👇"
    )


def _preview(req_type: str, reason: str, minutes: int) -> str:
    meta = TYPES[req_type]
    lines = [
        "🔎 <b>Дархости шумо</b>",
        "",
        f"{meta['emoji']} <b>{meta['self']}</b>",
        f"📝 {_esc(reason)}",
    ]
    if minutes > 0:
        until = (cfg.now() + timedelta(minutes=minutes)).strftime("%H:%M")
        lines.append(f"⏳ {_human_minutes(minutes)} · то соати <b>{until}</b>")
    lines += ["", "<i>Ҳамааш дуруст?</i>"]
    return "\n".join(lines)


def _group_text(rec: dict) -> str:
    meta = TYPES.get(rec["type"], {"emoji": "📋", "third": "Дархост"})
    status = rec.get("status", "pending")

    lines = [
        f"🔔 <b>Дархост</b> · <code>#{rec['id']}</code>",
        "",
        f"👤 <b>{_esc(rec['name'])}</b>",
    ]

    row = f"{meta['emoji']} {meta['third']}"
    if rec.get("minutes"):
        row += f" — <b>{_human_minutes(rec['minutes'])}</b>"
        if rec.get("deadline_at"):
            row += f" · то <b>{_clock(rec['deadline_at'])}</b>"
    lines.append(row)

    lines.append(f"📝 <i>{_esc(rec['reason'])}</i>")
    lines.append(f"🕒 {_stamp(rec.get('created_at'))}")
    lines.append("")

    if status == "pending":
        lines.append("⏳ <i>Ҷавобро интизорем…</i>")
    else:
        head = STATUS_WORD.get(status, status)
        if status == "cancelled":
            lines.append(f"🚫 <b>Корманд худаш бекор кард</b> · {_clock(rec.get('decided_at')) if rec.get('decided_at') else ''}".rstrip(" ·"))
        else:
            who = _short_name(rec.get("decided_by") or "")
            tail = f" · {_esc(who)}" if who else ""
            lines.append(f"<b>{head}</b>{tail}")

    confirmed = rec.get("worker_confirmed")
    if confirmed == "yes":
        lines.append("✅ Корманд гуфт: ҳамааш хуб")
    elif confirmed == "no":
        lines.append("⚠️ Корманд гуфт: ҳанӯз мушкил дорад")

    return "\n".join(lines)


def _worker_receipt(rec: dict) -> str:
    meta = TYPES.get(rec["type"], {"emoji": "📋", "self": "Дархост"})
    lines = [
        "✅ <b>Дархост фиристода шуд</b>",
        "",
        f"{meta['emoji']} {meta['self']}",
        f"📝 {_esc(rec['reason'])}",
    ]
    if rec.get("minutes"):
        lines.append(f"⏳ {_human_minutes(rec['minutes'])} · то <b>{_clock(rec.get('deadline_at'))}</b>")
    lines += [
        f"🔖 Рақам: <code>#{rec['id']}</code>",
        "",
        "<i>Вақте роҳбарият ҷавоб диҳад, ба шумо хабар медиҳам.</i>",
    ]
    return "\n".join(lines)


def _help_text() -> str:
    return (
        "ℹ️ <b>Бот чӣ кор мекунад</b>\n\n"
        "<b>1. Давомот</b>\n"
        "Ҳар рӯзи корӣ, вақте кор сар мешавад, бот мепурсад: «Ба кор омадед?»\n"
        "• <b>✅ Омадам</b> — вақти омадан қайд мешавад\n"
        "• <b>❌ Наомадам</b> — мегӯед чаро ва кай меоед\n"
        "Рӯзи якшанбе савол намеояд.\n\n"
        "<b>2. Дархост ба роҳбарият</b>\n"
        "«📝 Дархости нав»-ро пахш кунед ва интихоб кунед:\n"
        "🕰 <b>Дер мекунам</b> — каме дертар меоям\n"
        "🌿 <b>Имрӯз намеоям</b> — имрӯз омада наметавонам\n"
        "☕ <b>Ҷавоб мегирам</b> — бояд каме равам ва баргардам\n"
        "🌅 <b>Барвақт меравам</b> — имрӯз пештар меравам\n\n"
        "Сабабро интихоб кунед ё худатон нависед. "
        "Ҷавоби роҳбарият ҳамин ҷо меояд.\n\n"
        "<b>Ёдовариҳо</b>\n"
        f"• {cfg.REMINDER_LEAD} дақиқа пеш аз тамоми вақт хабар медиҳам\n"
        "• Агар «Дер мекунам» фиристед, дар вақти гуфтаатон мепурсам, ки расидед ё не\n\n"
        "<b>Фармонҳо</b>\n"
        "/start — оғоз\n"
        "/holat — дархостҳои ман\n"
        "/bekor — бекор кардан\n"
        "/help — ҳамин дастур\n\n"
        "<i>То ҷавоби роҳбарият дархостро бекор карда метавонед.</i>"
    )


def _my_requests_text(rows: list[dict]) -> str:
    if not rows:
        return (
            "📋 <b>Дархостҳои ман</b>\n\n"
            "Ҳоло дархост надоред.\n"
            "«📝 Дархости нав»-ро пахш кунед."
        )
    lines = ["📋 <b>Дархостҳои охирини шумо</b>", ""]
    for rec in rows:
        meta = TYPES.get(rec["type"], {"emoji": "📋", "third": "Дархост"})
        lines.append(
            f"<code>#{rec['id']}</code> {meta['emoji']} {meta['third']}"
            + (f" · {_human_minutes(rec['minutes'])}" if rec.get("minutes") else "")
        )
        lines.append(f"    {STATUS_WORD.get(rec['status'], rec['status'])} · {_stamp(rec['created_at'])}")
        lines.append("")
    return "\n".join(lines).strip()


# ── Давомот ─────────────────────────────────────────────────────────────

def _date_words(day: str | None = None) -> str:
    """«30 сентябр, сешанбе»"""
    d = cfg.parse_dt(day) if day else cfg.now()
    d = d or cfg.now()
    return f"{d.day} {MONTHS_GEN[d.month - 1]}, {WEEKDAYS[d.weekday()]}"


def _late_note(rec: dict) -> str:
    """«(17 дақ. дер)» ё холӣ — нисбат ба вақти оғози кор ва муҳлати иловагӣ."""
    arrived, planned = cfg.parse_dt(rec.get("arrived_at")), cfg.parse_dt(rec.get("scheduled_at"))
    if not arrived or not planned:
        return ""
    late = int((arrived - planned).total_seconds() // 60)
    if late <= db.get_schedule()["grace"]:
        return ""
    return f" ({_human_minutes(late)} дер)"


def _att_prompt_text(name: str, clock: str, reminder: bool = False) -> str:
    first = _esc(_short_name(name).split()[0]) if name else ""
    if reminder:
        return (
            "⏰ <b>Ёдоварӣ</b>\n\n"
            f"{first}, шумо ҳанӯз ҷавоб надодед.\n"
            "<b>Ба кор омадед?</b>"
        )
    return (
        f"☀️ <b>Рӯз ба хайр, {first}!</b>\n\n"
        f"Вақти кор шуд — соати {clock}.\n"
        "<b>Ба кор омадед?</b>"
    )


def _att_eta_text(key: str) -> str:
    now = cfg.now()
    if key.isdigit():
        return f"тақрибан соати {(now + timedelta(minutes=int(key))).strftime('%H:%M')}"
    return {
        "noon": "баъди нисфирӯзӣ",
        "today": "имрӯз намеояд",
        "tomorrow": "пагоҳ меояд",
    }.get(key, key)


def _att_group_absent(rec: dict) -> str:
    return (
        f"🔴 <b>{_esc(_short_name(rec['name']))}</b> ҳанӯз ба кор наомадааст\n"
        f"📝 Сабаб: <i>{_esc(rec.get('reason') or '—')}</i>\n"
        f"🕐 Кай меояд: <b>{_esc(rec.get('eta') or '—')}</b>"
    )


def daily_report_text(day: dict) -> str:
    """Ҳисоботи давомоти рӯз барои гурӯҳи роҳбарият."""
    groups: dict[str, list[dict]] = {k: [] for k in ("on_time", "late", "absent", "leave", "pending")}
    for item in day["items"]:
        cell = item.get("cell")
        if cell and cell["s"] in groups:
            groups[cell["s"]].append({**item, **cell})

    def names(rows, fmt, limit=25):
        out = [fmt(r) for r in rows[:limit]]
        if len(rows) > limit:
            out.append(f"   … ва боз {len(rows) - limit} нафар")
        return out

    s = day["summary"]
    lines = [
        f"📋 <b>Давомоти имрӯз</b> · {_date_words(day['date'])}",
        f"Оғози кор: <b>{day['schedule']['time']}</b>"
        + (" (баъзеҳо вақти дигар доранд)" if any(it.get("custom") for it in day["items"]) else ""),
        "",
        f"✅ Сари вақт омаданд: <b>{s['on_time']}</b>",
    ]
    if groups["late"]:
        lines.append(f"⏰ Дер омаданд: <b>{len(groups['late'])}</b>")
        lines += names(sorted(groups["late"], key=lambda r: -r["late"]), lambda r:
                       f"   • {_esc(_short_name(r['name']))} — {r['t']} (+{_human_minutes(r['late'])})")
    if groups["absent"]:
        lines.append(f"🔴 Наомаданд: <b>{len(groups['absent'])}</b>")
        lines += names(groups["absent"], lambda r:
                       f"   • {_esc(_short_name(r['name']))} — {_esc(r['reason'] or 'сабаб нагуфт')}"
                       + (f" · {_esc(r['eta'])}" if r["eta"] else ""))
    if groups["leave"]:
        lines.append(f"🌴 Дар рухсатӣ: <b>{len(groups['leave'])}</b>")
        lines += names(groups["leave"], lambda r: f"   • {_esc(_short_name(r['name']))}")
    if groups["pending"]:
        lines.append(f"❔ Ҷавоб надоданд: <b>{len(groups['pending'])}</b>")
        lines.append("   " + ", ".join(_esc(_short_name(r["name"])) for r in groups["pending"][:40]))
    # Онҳое, ки вақти кориашон баъдтар сар мешавад (масалан, аз 14:00)
    now_clock = cfg.now().strftime("%H:%M")
    later = sorted((it for it in day["items"] if not it.get("cell") and it.get("active")
                    and it.get("works") and (it.get("start") or "") > now_clock),
                   key=lambda it: it["start"])
    if later:
        lines.append(f"🕑 Кори онҳо дертар сар мешавад: <b>{len(later)}</b>")
        lines += names(later, lambda r: f"   • {_esc(_short_name(r['name']))} — аз {r['start']}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
#  Амалҳои муштарак (бот + панели веб онҳоро истифода мебаранд)
# ══════════════════════════════════════════════════════════════════════════

async def apply_decision(bot: AsyncTeleBot, req_id: int, decision: str, admin_name: str) -> tuple[bool, str]:
    """
    Қарори роҳбарият. Ҳам аз тугмаи гурӯҳ, ҳам аз панели веб даъват мешавад.
    Бармегардонад: (муваффақ, паём).
    """
    rec = db.get_request(req_id)
    if rec is None:
        return False, "Дархост ёфт нашуд."

    if rec["status"] != "pending":
        return False, f"Ба ин дархост аллакай ҷавоб дода шуд: {STATUS_WORD.get(rec['status'], rec['status'])}"

    if not db.update_status(req_id, decision, admin_name):
        return False, "Каси дигар ҳозир ба ин дархост ҷавоб дод."

    rec = db.get_request(req_id) or rec

    # 1. Паёми гурӯҳро нав мекунем
    if rec.get("group_msg_id"):
        await _safe(bot.edit_message_text(
            _group_text(rec), chat_id=GROUP_ID, message_id=rec["group_msg_id"],
            reply_markup=_kb_admin_after(req_id),
        ))

    # 2. Тугмаи «бекор кардан»-ро аз паёми ҳамкор мегирем
    if rec.get("worker_msg_id"):
        await _safe(bot.edit_message_reply_markup(
            chat_id=rec["user_id"], message_id=rec["worker_msg_id"], reply_markup=None,
        ))

    # 3. Ба ҳамкор хабар медиҳем
    await _safe(bot.send_message(rec["user_id"], _decision_text(rec, decision, admin_name)))

    # 4. Барои «дер мекунам» — санҷиши омадан таъин мекунем
    if decision == "accepted" and rec["type"] == "late" and rec.get("deadline_at"):
        try:
            db.create_arrival_check(req_id, rec["user_id"], rec["deadline_at"])
        except Exception as exc:
            log.error("❌ Arrival check сохта нашуд (#%d): %s", req_id, exc)

    return True, "Иҷозат дода шуд" if decision == "accepted" else "Рад карда шуд"


def _decision_text(rec: dict, decision: str, admin_name: str) -> str:
    who = _esc(_short_name(admin_name))

    if decision == "rejected":
        return (
            "✋ <b>Дархост рад шуд</b>\n\n"
            f"<b>{who}</b> ба дархости <code>#{rec['id']}</code> иҷозат надод.\n"
            "Барои тафсилот бо роҳбарият гап занед."
        )

    lines = [
        "🎉 <b>Иҷозат дода шуд!</b>",
        "",
        f"<b>{who}</b> дархости <code>#{rec['id']}</code>-ро қабул кард.",
    ]

    req_type = rec["type"]
    until = _clock(rec.get("deadline_at"))

    if req_type == "absent":
        lines += ["", "🌿 Роҳбарият медонад, ки имрӯз намеоед.", "Ҳамааш хуб шавад! 🙏"]
    elif rec.get("minutes") and rec.get("deadline_at"):
        if req_type == "late":
            lines += ["", f"🕰 Интизорем, ки то соати <b>{until}</b> меоед.",
                      "🔔 Ҳамон вақт мепурсам, ки расидед ё не."]
        elif req_type == "leaving_early":
            lines += ["", f"🌅 Соати <b>{until}</b> метавонед равед.",
                      f"🔔 {cfg.REMINDER_LEAD} дақиқа пеш хабар медиҳам."]
        elif req_type == "at_work_waiting":
            lines += ["", f"☕ То соати <b>{until}</b> вақт доред ({_human_minutes(rec['minutes'])}).",
                      f"🔔 {cfg.REMINDER_LEAD} дақиқа пеш хабар медиҳам."]

    return "\n".join(lines)


async def send_worker_message(bot: AsyncTeleBot, req_id: int, text: str, admin_name: str) -> tuple[bool, str]:
    """Паёми озод аз роҳбарият ба ҳамкор (аз гурӯҳ ё аз панели веб)."""
    rec = db.get_request(req_id)
    if not rec:
        return False, "Дархост ёфт нашуд."

    body = (
        "💬 <b>Паём аз роҳбарият</b>\n\n"
        f"👤 <b>{_esc(_short_name(admin_name))}</b>\n\n"
        f"{_esc(text)}"
    )
    ok = await _safe(bot.send_message(rec["user_id"], body))
    if ok is None:
        return False, "Паём нарасид — шояд корманд ботро бастааст."
    return True, "Паём фиристода шуд"


# ══════════════════════════════════════════════════════════════════════════
#  Ба қайд гирифтани handler-ҳо
# ══════════════════════════════════════════════════════════════════════════

def register_handlers(bot: AsyncTeleBot) -> None:

    # ── дохилиҳо ────────────────────────────────────────────────────────

    async def show_menu(chat_id: int, user, greet: bool = True) -> None:
        db.touch_employee(user.id, _display_name(user), user.username)
        if greet:
            await _safe(bot.send_message(
                chat_id, _welcome(user.first_name or "ҳамкор"), reply_markup=_main_reply_kb()))
        await _safe(bot.send_message(
            chat_id, "<b>Чӣ хабар?</b>\nЯке аз инҳоро интихоб кунед:",
            reply_markup=_kb_types()))

    async def ask_reason(chat_id: int, req_type: str, message_id: int | None = None) -> None:
        meta = TYPES[req_type]
        text = f"{meta['emoji']} <b>{meta['self']}</b>\n\n{meta['reason_q']}"
        if message_id:
            edited = await _safe(bot.edit_message_text(
                text, chat_id=chat_id, message_id=message_id, reply_markup=_kb_reasons(req_type)))
            if edited is not None:
                return
        await _safe(bot.send_message(chat_id, text, reply_markup=_kb_reasons(req_type)))

    async def ask_minutes(chat_id: int, req_type: str, message_id: int | None = None) -> None:
        meta = TYPES[req_type]
        text = (
            f"{meta['emoji']} <b>{meta['self']}</b>\n\n"
            f"⏳ {meta['time_q']}\n"
            "<i>Дақиқаро интихоб кунед:</i>"
        )
        if message_id:
            edited = await _safe(bot.edit_message_text(
                text, chat_id=chat_id, message_id=message_id, reply_markup=_kb_minutes()))
            if edited is not None:
                return
        await _safe(bot.send_message(chat_id, text, reply_markup=_kb_minutes()))

    async def ask_confirm(chat_id: int, state: dict, message_id: int | None = None) -> None:
        text = _preview(state["type"], state["reason"], state.get("minutes", 0))
        if message_id:
            edited = await _safe(bot.edit_message_text(
                text, chat_id=chat_id, message_id=message_id, reply_markup=_kb_confirm()))
            if edited is not None:
                return
        await _safe(bot.send_message(chat_id, text, reply_markup=_kb_confirm()))

    async def advance_after_reason(chat_id: int, user_id: int, state: dict,
                                   message_id: int | None = None) -> None:
        if TYPES[state["type"]]["ask_time"]:
            state["step"] = "minutes"
            db.set_state(user_id, state)
            await ask_minutes(chat_id, state["type"], message_id)
        else:
            state["step"] = "confirm"
            state["minutes"] = 0
            db.set_state(user_id, state)
            await ask_confirm(chat_id, state, message_id)

    async def submit(chat_id: int, user, state: dict) -> None:
        req_type = state["type"]
        reason = state.get("reason", "—")
        minutes = int(state.get("minutes", 0))
        name = _display_name(user)

        db.touch_employee(user.id, name, user.username)
        req_id = db.add_request(user.id, name, req_type, reason, minutes)
        rec = db.get_request(req_id)
        if not rec:
            await _safe(bot.send_message(chat_id, "⚠️ Хато шуд. Боз як бор кӯшиш кунед."))
            return

        sent = await _safe(bot.send_message(
            GROUP_ID, _group_text(rec), reply_markup=_kb_admin_decision(req_id)))

        if sent is None:
            db.cancel_request(req_id)
            await _safe(bot.send_message(
                chat_id,
                "⚠️ <b>Дархост ба роҳбарият нарасид</b>\n\n"
                "Бот ба гурӯҳи роҳбарият навишта натавонист. Ба барномасоз хабар диҳед.",
            ))
            log.error("❌ Ба гурӯҳ %s фиристода нашуд (дархост #%d)", GROUP_ID, req_id)
            return

        db.update_group_msg_id(req_id, sent.message_id)
        rec = db.get_request(req_id) or rec

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Бекор кардани дархост", callback_data=f"c:{req_id}"))
        receipt = await _safe(bot.send_message(chat_id, _worker_receipt(rec), reply_markup=kb))
        if receipt is not None:
            db.update_worker_msg_id(req_id, receipt.message_id)

        # «Намеоям / дер мекунам» → давомоти имрӯз худкор «наомад» бо ҳамин сабаб;
        # саволи субҳ (агар фиристода шуда бошад) дигар лозим нест.
        try:
            att = db.attendance_from_request(user.id, req_type, reason, rec.get("deadline_at"))
        except Exception as exc:
            att = None
            log.error("Давомот аз дархост #%d сабт нашуд: %s", req_id, exc)
        if att and att.get("msg_id"):
            await _safe(bot.edit_message_text(
                "📝 <b>Қайд шуд.</b>\n\nСабабро аз дархостатон гирифтем. "
                "Вақте ба кор омадед, тугмаи поёнро пахш кунед.",
                chat_id=user.id, message_id=att["msg_id"],
                reply_markup=_kb_att_arrived(att["id"]),
            ))

    # ── фармонҳо ────────────────────────────────────────────────────────

    @bot.message_handler(commands=["start"], func=_private)
    async def cmd_start(message: Message):
        db.clear_state(message.from_user.id)
        await show_menu(message.chat.id, message.from_user)

    @bot.message_handler(commands=["help"], func=_private)
    async def cmd_help(message: Message):
        await _safe(bot.send_message(message.chat.id, _help_text(), reply_markup=_main_reply_kb()))

    @bot.message_handler(commands=["holat", "status", "my"], func=_private)
    async def cmd_status(message: Message):
        rows = db.get_user_requests(message.from_user.id, 5)
        await _safe(bot.send_message(message.chat.id, _my_requests_text(rows)))

    @bot.message_handler(commands=["bekor", "cancel"], func=_private)
    async def cmd_cancel(message: Message):
        had = db.clear_state(message.from_user.id)
        text = ("❌ Бекор шуд." if had
                else "ℹ️ Ҳозир ягон кори нотамом нест.")
        await _safe(bot.send_message(message.chat.id, f"{text}\n\nБарои сар кардан /start-ро пахш кунед."))

    @bot.message_handler(commands=["admin", "panel"], func=_private)
    async def cmd_admin(message: Message):
        db.clear_state(message.from_user.id)
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("📱 Кушодан дар Telegram", web_app=WebAppInfo(url=cfg.WEBAPP_URL)))
        kb.add(InlineKeyboardButton("🌐 Кушодан дар браузер", url=cfg.WEBAPP_URL))
        await _safe(bot.send_message(
            message.chat.id,
            "🔐 <b>Панели идора</b>\n\n"
            "Давомот, дархостҳо, кормандон ва омор — дар як ҷо.\n\n"
            "📱 <b>Telegram</b> — ҳамин ҷо мекушояд.\n"
            "🌐 <b>Браузер</b> — барои компютер ва планшет.\n\n"
            f"<i>Суроға: {_esc(cfg.WEBAPP_URL)}</i>",
            reply_markup=kb,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        ))

    # ── тугмаҳо: интихоби вазъият ───────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("t:") or c.data.startswith("type_"))
    async def cb_type(call: CallbackQuery):
        req_type = call.data.split(":", 1)[1] if call.data.startswith("t:") else call.data[5:]
        if req_type not in TYPES:
            await _safe(bot.answer_callback_query(call.id, "Чунин интихоб нест"))
            return

        open_reqs = db.get_open_requests(call.from_user.id)
        if len(open_reqs) >= cfg.MAX_OPEN_REQUESTS:
            rec = open_reqs[0]
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("❌ Дархости пешинаро бекор кардан",
                                        callback_data=f"c:{rec['id']}"))
            await _safe(bot.answer_callback_query(call.id, "Дархости бе ҷавоб доред"))
            await _safe(bot.send_message(
                call.message.chat.id,
                f"⏳ <b>Дархости <code>#{rec['id']}</code> ҳанӯз ҷавоб нагирифтааст.</b>\n\n"
                "Интизор шавед ё онро бекор кунед.",
                reply_markup=kb,
            ))
            return

        db.set_state(call.from_user.id, {"step": "reason", "type": req_type})
        await _safe(bot.answer_callback_query(call.id))
        await ask_reason(call.message.chat.id, req_type, call.message.message_id)

    # ── тугмаҳо: сабаб ──────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("r:"))
    async def cb_reason(call: CallbackQuery):
        state = db.get_state(call.from_user.id)
        if not state or state.get("step") != "reason":
            await _safe(bot.answer_callback_query(call.id, "Ин кор тамом шуд. /start-ро пахш кунед"))
            return

        choice = call.data.split(":", 1)[1]
        await _safe(bot.answer_callback_query(call.id))

        if choice == "x":
            state["step"] = "reason_text"
            db.set_state(call.from_user.id, state)
            await _safe(bot.edit_message_text(
                "✍️ <b>Сабабро кӯтоҳ нависед:</b>",
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                reply_markup=_kb_cancel_only(),
            ))
            return

        try:
            state["reason"] = TYPES[state["type"]]["reasons"][int(choice)]
        except (ValueError, IndexError, KeyError):
            await _safe(bot.answer_callback_query(call.id, "Сабаб ёфт нашуд"))
            return

        await advance_after_reason(call.message.chat.id, call.from_user.id,
                                   state, call.message.message_id)

    # ── тугмаҳо: дақиқа ─────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("m:"))
    async def cb_minutes(call: CallbackQuery):
        state = db.get_state(call.from_user.id)
        if not state or state.get("step") != "minutes":
            await _safe(bot.answer_callback_query(call.id, "Ин кор тамом шуд. /start-ро пахш кунед"))
            return

        choice = call.data.split(":", 1)[1]
        await _safe(bot.answer_callback_query(call.id))

        if choice == "x":
            state["step"] = "minutes_text"
            db.set_state(call.from_user.id, state)
            await _safe(bot.edit_message_text(
                f"✍️ <b>Чанд дақиқа?</b>\n<i>Танҳо рақам нависед (1–{MINUTES_MAX}).</i>",
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                reply_markup=_kb_cancel_only(),
            ))
            return

        state["minutes"] = int(choice)
        state["step"] = "confirm"
        db.set_state(call.from_user.id, state)
        await ask_confirm(call.message.chat.id, state, call.message.message_id)

    # ── тугмаҳо: идоракунии раванд ──────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("f:") or c.data == "cancel_flow")
    async def cb_flow(call: CallbackQuery):
        action = call.data.split(":", 1)[1] if call.data.startswith("f:") else "cancel"
        uid = call.from_user.id
        chat_id = call.message.chat.id
        mid = call.message.message_id

        if action == "cancel":
            db.clear_state(uid)
            await _safe(bot.answer_callback_query(call.id, "❌ Бекор шуд"))
            await _safe(bot.edit_message_text(
                "❌ <b>Бекор шуд.</b>\n\nБарои дархости нав /start-ро пахш кунед.",
                chat_id=chat_id, message_id=mid,
            ))
            return

        if action == "back_type":
            db.clear_state(uid)
            await _safe(bot.answer_callback_query(call.id))
            await _safe(bot.edit_message_text(
                "<b>Интихоб кунед:</b>",
                chat_id=chat_id, message_id=mid, reply_markup=_kb_types(),
            ))
            return

        state = db.get_state(uid)
        if not state:
            await _safe(bot.answer_callback_query(call.id, "Ин кор тамом шуд. /start-ро пахш кунед"))
            return

        if action == "back_reason":
            state["step"] = "reason"
            state.pop("minutes", None)
            db.set_state(uid, state)
            await _safe(bot.answer_callback_query(call.id))
            await ask_reason(chat_id, state["type"], mid)
            return

        if action == "send":
            if state.get("step") != "confirm":
                await _safe(bot.answer_callback_query(call.id, "Ҳанӯз тамом нашуд"))
                return
            db.clear_state(uid)
            await _safe(bot.answer_callback_query(call.id, "📤 Фиристода шуд"))
            await _safe(bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=mid, reply_markup=None))
            await submit(chat_id, call.from_user, state)

    # ── бекор кардани дархости фиристодашуда ────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("c:") or c.data.startswith("cancel_req_"))
    async def cb_cancel_request(call: CallbackQuery):
        raw = call.data.split(":", 1)[1] if call.data.startswith("c:") else call.data[len("cancel_req_"):]
        try:
            req_id = int(raw)
        except ValueError:
            await _safe(bot.answer_callback_query(call.id, "Дархост ёфт нашуд"))
            return

        rec = db.get_request(req_id)
        if not rec:
            await _safe(bot.answer_callback_query(call.id, "Дархост ёфт нашуд"))
            return

        if rec["user_id"] != call.from_user.id:
            await _safe(bot.answer_callback_query(call.id, "Ин дархости шумо нест"))
            return

        if not db.cancel_request(req_id):
            await _safe(bot.answer_callback_query(
                call.id, f"Аллакай: {STATUS_WORD.get(rec['status'], rec['status'])}"))
            return

        await _safe(bot.answer_callback_query(call.id, "✅ Бекор шуд"))
        await _safe(bot.edit_message_text(
            f"🚫 <b>Дархости <code>#{req_id}</code> бекор карда шуд.</b>\n\n"
            "Роҳбарият дигар онро намебинад.\nБарои дархости нав /start-ро пахш кунед.",
            chat_id=call.message.chat.id, message_id=call.message.message_id,
        ))

        rec = db.get_request(req_id)
        if rec and rec.get("group_msg_id"):
            await _safe(bot.edit_message_text(
                _group_text(rec), chat_id=GROUP_ID,
                message_id=rec["group_msg_id"], reply_markup=None,
            ))

    # ── қарори роҳбарият ────────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("d:") or c.data.startswith("accept_") or c.data.startswith("reject_")
    )
    async def cb_decision(call: CallbackQuery):
        if not _from_group(call):
            await _safe(bot.answer_callback_query(call.id, "Танҳо дар гурӯҳи роҳбарият"))
            return

        if call.data.startswith("d:"):
            _, action, raw = call.data.split(":", 2)
            decision = "accepted" if action == "a" else "rejected"
        else:
            action, raw = call.data.split("_", 1)
            decision = "accepted" if action == "accept" else "rejected"

        try:
            req_id = int(raw)
        except ValueError:
            await _safe(bot.answer_callback_query(call.id, "Дархост ёфт нашуд"))
            return

        ok, msg = await apply_decision(bot, req_id, decision, _display_name(call.from_user))
        await _safe(bot.answer_callback_query(call.id, msg[:200]))

        if not ok:
            rec = db.get_request(req_id)
            if rec and rec.get("group_msg_id"):
                await _safe(bot.edit_message_text(
                    _group_text(rec), chat_id=GROUP_ID, message_id=rec["group_msg_id"],
                    reply_markup=_kb_admin_after(req_id) if rec["status"] != "cancelled" else None,
                ))

    # ── паём аз роҳбарият ба ҳамкор ─────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("fb:") or c.data.startswith("feedback_"))
    async def cb_feedback(call: CallbackQuery):
        if not _from_group(call):
            await _safe(bot.answer_callback_query(call.id, "Танҳо дар гурӯҳи роҳбарият"))
            return

        raw = call.data.split(":", 1)[1] if call.data.startswith("fb:") else call.data[len("feedback_"):]
        try:
            req_id = int(raw)
        except ValueError:
            await _safe(bot.answer_callback_query(call.id, "Дархост ёфт нашуд"))
            return

        rec = db.get_request(req_id)
        if not rec:
            await _safe(bot.answer_callback_query(call.id, "Дархост ёфт нашуд"))
            return

        db.set_state(call.from_user.id, {
            "step": "admin_feedback",
            "req_id": req_id,
            "worker_id": rec["user_id"],
            "worker_name": rec["name"],
        })
        await _safe(bot.answer_callback_query(call.id, "✍️ Паёматонро ба гурӯҳ нависед"))
        await _safe(bot.send_message(
            GROUP_ID,
            f"✍️ <b>{_esc(_short_name(_display_name(call.from_user)))}</b>, "
            f"паёматонро ба <b>{_esc(_short_name(rec['name']))}</b> нависед.\n"
            "<i>Паёми навбатии шумо дар ин гурӯҳ ба ӯ меравад.</i>",
        ))

    # ── тасдиқи ҳамкор баъди ёдоварӣ ────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("w:") or c.data.startswith("confirm_yes_") or c.data.startswith("confirm_no_")
    )
    async def cb_worker_confirm(call: CallbackQuery):
        if call.data.startswith("w:"):
            _, answer_key, raw = call.data.split(":", 2)
            answer = "yes" if answer_key == "y" else "no"
        else:
            parts = call.data.split("_")
            answer, raw = parts[1], parts[2]

        try:
            req_id = int(raw)
        except (ValueError, IndexError):
            await _safe(bot.answer_callback_query(call.id, "Дархост ёфт нашуд"))
            return

        rec = db.get_request(req_id)
        if not rec:
            await _safe(bot.answer_callback_query(call.id, "Дархост ёфт нашуд"))
            return

        if not db.update_worker_confirmation(req_id, answer):
            await _safe(bot.answer_callback_query(call.id, "Шумо аллакай ҷавоб додед"))
            return

        rec = db.get_request(req_id) or rec
        name = _esc(_short_name(rec["name"]))
        clock = cfg.now().strftime("%H:%M")

        if answer == "yes":
            await _safe(bot.answer_callback_query(call.id, "✅ Раҳмат!"))
            await _safe(bot.edit_message_text(
                "✨ <b>Ташаккур!</b>\n\nКори хуб! 🎉",
                chat_id=call.message.chat.id, message_id=call.message.message_id,
            ))
            await _safe(bot.send_message(
                GROUP_ID,
                f"✅ <b>{name}</b> тасдиқ кард, ки ҳамааш хуб аст.\n"
                f"<code>#{req_id}</code> · {clock}",
            ))
        else:
            await _safe(bot.answer_callback_query(call.id, "💬 Қабул шуд"))
            await _safe(bot.edit_message_text(
                "💬 <b>Фаҳмидем.</b>\n\nРоҳбарият огоҳ шуд ва бо шумо гап мезанад.",
                chat_id=call.message.chat.id, message_id=call.message.message_id,
            ))
            await _safe(bot.send_message(
                GROUP_ID,
                f"⚠️ <b>{name}</b> мегӯяд, ки ҳанӯз мушкил дорад.\n"
                f"<code>#{req_id}</code> · {clock}",
            ))

        if rec.get("group_msg_id"):
            await _safe(bot.edit_message_text(
                _group_text(rec), chat_id=GROUP_ID, message_id=rec["group_msg_id"],
                reply_markup=_kb_admin_after(req_id),
            ))

    # ── давомот: «Ба кор омадед?» ────────────────────────────────────────
    #   att:y:{id}    — омадам
    #   att:n:{id}    — наомадам → сабаб → кай меояд
    #   att:arr:{id}  — баъдтар омадам (пас аз «наомадам» ё дархост)
    #   att:back:{id} — бозгашт ба саволи аввал

    async def _att_record(call: CallbackQuery, attendance_id: int) -> dict | None:
        rec = db.get_attendance(attendance_id)
        if not rec or rec["user_id"] != call.from_user.id:
            await _safe(bot.answer_callback_query(call.id, "Ин савол барои шумо нест"))
            return None
        if rec["work_date"] != cfg.today_str():
            await _safe(bot.answer_callback_query(call.id, "Ин савол барои рӯзи дигар буд"))
            await _safe(bot.edit_message_reply_markup(
                chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None))
            return None
        return rec

    @bot.callback_query_handler(func=lambda c: c.data.startswith("att:"))
    async def cb_attendance(call: CallbackQuery):
        try:
            _, action, raw_id = call.data.split(":", 2)
            attendance_id = int(raw_id)
        except (TypeError, ValueError):
            await _safe(bot.answer_callback_query(call.id, "Хатогӣ. /start-ро пахш кунед"))
            return
        rec = await _att_record(call, attendance_id)
        if rec is None:
            return
        chat_id, mid = call.message.chat.id, call.message.message_id

        if action == "back":
            db.clear_state(call.from_user.id)
            if rec["status"] != "pending":
                await _safe(bot.answer_callback_query(call.id, "Ҷавоби шумо аллакай қайд шудааст"))
                await _safe(bot.edit_message_reply_markup(chat_id=chat_id, message_id=mid, reply_markup=None))
                return
            await _safe(bot.answer_callback_query(call.id))
            await _safe(bot.edit_message_text(
                _att_prompt_text(rec["name"], _clock(rec["scheduled_at"])),
                chat_id=chat_id, message_id=mid, reply_markup=_kb_att_prompt(attendance_id)))
            return

        if action in ("y", "arr"):
            was_absent = rec["status"] == "absent"
            if rec["status"] == "present":
                await _safe(bot.answer_callback_query(call.id, "Омадани шумо аллакай қайд шудааст"))
                await _safe(bot.edit_message_reply_markup(chat_id=chat_id, message_id=mid, reply_markup=None))
                return
            if rec["status"] == "leave" or not db.set_attendance_present(attendance_id):
                await _safe(bot.answer_callback_query(call.id, "Ҷавоби шумо аллакай қайд шудааст"))
                return
            db.clear_state(call.from_user.id)
            rec = db.get_attendance(attendance_id) or rec
            clock = _clock(rec["arrived_at"])
            late = _late_note(rec)
            await _safe(bot.answer_callback_query(call.id, "✅ Қайд шуд"))
            await _safe(bot.edit_message_text(
                f"✅ <b>Қайд шуд.</b> Соати <b>{clock}</b> омадед{late}.\n\nКори хуб! ☀️",
                chat_id=chat_id, message_id=mid))
            if was_absent:
                await _safe(bot.send_message(
                    GROUP_ID,
                    f"🟢 <b>{_esc(_short_name(rec['name']))}</b> ба кор омад — <b>{clock}</b>{late}"))
            return

        if action == "n":
            if rec["status"] != "pending":
                await _safe(bot.answer_callback_query(call.id, "Ҷавоби шумо аллакай қайд шудааст"))
                return
            db.set_state(call.from_user.id, {"step": "att_reason", "attendance_id": attendance_id})
            await _safe(bot.answer_callback_query(call.id))
            await _safe(bot.edit_message_text(
                "📝 <b>Чаро наомадед?</b>\n\nИнтихоб кунед ё худатон нависед:",
                chat_id=chat_id, message_id=mid, reply_markup=_kb_att_reasons(attendance_id)))
            return

        await _safe(bot.answer_callback_query(call.id))

    @bot.callback_query_handler(func=lambda c: c.data.startswith("atr:"))
    async def cb_att_reason(call: CallbackQuery):
        state = db.get_state(call.from_user.id)
        if not state or state.get("step") not in ("att_reason", "att_reason_text"):
            await _safe(bot.answer_callback_query(call.id, "Ин савол дигар фаъол нест"))
            return
        choice = call.data.split(":", 1)[1]
        await _safe(bot.answer_callback_query(call.id))
        if choice == "x":
            state["step"] = "att_reason_text"
            db.set_state(call.from_user.id, state)
            await _safe(bot.edit_message_text(
                "✍️ <b>Сабабро кӯтоҳ нависед:</b>",
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                reply_markup=_kb_att_back(state["attendance_id"])))
            return
        try:
            reason = ATT_REASONS[int(choice)].split(" ", 1)[1]
        except (ValueError, IndexError):
            return
        state.update(step="att_eta", reason=reason)
        db.set_state(call.from_user.id, state)
        await _ask_att_eta(call.message.chat.id, state, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ate:"))
    async def cb_att_eta(call: CallbackQuery):
        state = db.get_state(call.from_user.id)
        if not state or state.get("step") not in ("att_eta", "att_eta_text"):
            await _safe(bot.answer_callback_query(call.id, "Ин савол дигар фаъол нест"))
            return
        choice = call.data.split(":", 1)[1]
        await _safe(bot.answer_callback_query(call.id))
        if choice == "x":
            state["step"] = "att_eta_text"
            db.set_state(call.from_user.id, state)
            await _safe(bot.edit_message_text(
                "✍️ <b>Кай меоед?</b>\n<i>Масалан: соати 10:30, баъди дарс, пагоҳ</i>",
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                reply_markup=_kb_att_back(state["attendance_id"])))
            return
        await _safe(bot.edit_message_reply_markup(
            chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None))
        await _finish_att_absence(call.message.chat.id, call.from_user.id, state, _att_eta_text(choice))

    async def _ask_att_eta(chat_id: int, state: dict, message_id: int | None = None) -> None:
        text = (f"📝 Сабаб: <i>{_esc(state['reason'])}</i>\n\n"
                "🕐 <b>Кай ба кор меоед?</b>")
        kb = _kb_att_eta(state["attendance_id"])
        if message_id:
            edited = await _safe(bot.edit_message_text(
                text, chat_id=chat_id, message_id=message_id, reply_markup=kb))
            if edited is not None:
                return
        await _safe(bot.send_message(chat_id, text, reply_markup=kb))

    async def _finish_att_absence(chat_id: int, user_id: int, state: dict, eta: str) -> None:
        db.clear_state(user_id)
        attendance_id = int(state.get("attendance_id", 0))
        rec = db.get_attendance(attendance_id)
        if (not rec or rec["user_id"] != user_id or rec["work_date"] != cfg.today_str()
                or not db.set_attendance_absent(attendance_id, state.get("reason", "—"), eta)):
            await _safe(bot.send_message(chat_id, "ℹ️ Ин савол дигар фаъол нест."))
            return
        rec = db.get_attendance(attendance_id) or rec
        await _safe(bot.send_message(
            chat_id,
            "🙏 <b>Ташаккур, ки хабар додед.</b> Роҳбарият огоҳ шуд.\n\n"
            f"📝 Сабаб: <i>{_esc(rec['reason'])}</i>\n"
            f"🕐 Кай меоед: <b>{_esc(rec['eta'])}</b>\n\n"
            "Вақте ба кор омадед, тугмаи поёнро пахш кунед 👇",
            reply_markup=_kb_att_arrived(attendance_id)))
        await _safe(bot.send_message(GROUP_ID, _att_group_absent(rec)))

    # ── санҷиши омадан аз дархости «дер мекунам» ─────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("a:") or c.data.startswith("arrival_arrived_") or c.data.startswith("arrival_notyet_")
    )
    async def cb_arrival(call: CallbackQuery):
        if call.data.startswith("a:"):
            _, answer_key, raw = call.data.split(":", 2)
            arrived = answer_key == "y"
        elif call.data.startswith("arrival_arrived_"):
            arrived, raw = True, call.data[len("arrival_arrived_"):]
        else:
            arrived, raw = False, call.data[len("arrival_notyet_"):]

        try:
            check_id = int(raw)
        except ValueError:
            await _safe(bot.answer_callback_query(call.id, "Ёфт нашуд"))
            return

        check = db.get_arrival_check(check_id)
        if not check:
            await _safe(bot.answer_callback_query(call.id, "Ёфт нашуд"))
            return
        if check["status"] != "pending":
            await _safe(bot.answer_callback_query(call.id, "Шумо аллакай ҷавоб додед"))
            return

        name = _esc(_short_name(check["name"]))
        clock = cfg.now().strftime("%H:%M")

        if arrived:
            if not db.set_check_arrived(check_id):
                await _safe(bot.answer_callback_query(call.id, "Шумо аллакай ҷавоб додед"))
                return
            db.update_worker_confirmation(check["request_id"], "yes")
            try:                                  # давомоти имрӯз: «омад» бо вақти воқеӣ
                db.attendance_mark_arrived(call.from_user.id)
            except Exception as exc:
                log.error("Давомот (arrival #%d): %s", check_id, exc)
            await _safe(bot.answer_callback_query(call.id, "✅ Хуш омадед!"))
            await _safe(bot.edit_message_text(
                f"🎉 <b>Хуш омадед!</b>\n\n"
                f"Роҳбарият медонад, ки соати <b>{clock}</b> расидед.\n"
                "Кори хуб! ✨",
                chat_id=call.message.chat.id, message_id=call.message.message_id,
            ))
            await _safe(bot.send_message(
                GROUP_ID,
                f"🎉 <b>{name}</b> ба кор расид.\n"
                f"🕰 Соати <b>{clock}</b> · дархост <code>#{check['request_id']}</code>",
            ))
            return

        db.set_state(call.from_user.id, {
            "step": "arrival_reason",
            "check_id": check_id,
            "request_id": check["request_id"],
        })
        await _safe(bot.answer_callback_query(call.id))
        await _safe(bot.edit_message_text(
            "✍️ <b>Хуб.</b>\n\nЧаро боз дер мемонед? Кӯтоҳ нависед:",
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            reply_markup=_kb_cancel_only(),
        ))

    @bot.callback_query_handler(func=lambda c: c.data.startswith("am:"))
    async def cb_arrival_minutes(call: CallbackQuery):
        state = db.get_state(call.from_user.id)
        if not state or state.get("step") != "arrival_minutes":
            await _safe(bot.answer_callback_query(call.id, "Ин раванд тамом шудааст"))
            return

        choice = call.data.split(":", 1)[1]
        await _safe(bot.answer_callback_query(call.id))

        if choice == "x":
            state["step"] = "arrival_minutes_text"
            db.set_state(call.from_user.id, state)
            await _safe(bot.edit_message_text(
                "✍️ <b>Боз чанд дақиқа?</b>\n<i>Танҳо рақам нависед.</i>",
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                reply_markup=_kb_cancel_only(),
            ))
            return

        await _safe(bot.edit_message_reply_markup(
            chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None))
        await _finish_arrival_delay(bot, call.message.chat.id, call.from_user, state, int(choice))

    # ── матни озод дар чати шахсӣ ───────────────────────────────────────

    @bot.message_handler(func=lambda m: m.chat.type == "private", content_types=["text"])
    async def private_text(message: Message):
        uid = message.from_user.id
        text = (message.text or "").strip()
        state = db.get_state(uid)
        step = (state or {}).get("step")

        # тугмаҳои клавиатураи доимӣ
        if text.startswith("📝"):
            db.clear_state(uid)
            await _safe(bot.send_message(message.chat.id, "<b>Интихоб кунед:</b>",
                                         reply_markup=_kb_types()))
            return
        if text.startswith("📋"):
            await _safe(bot.send_message(message.chat.id,
                                         _my_requests_text(db.get_user_requests(uid, 5))))
            return
        if text.startswith("ℹ️"):
            await _safe(bot.send_message(message.chat.id, _help_text()))
            return

        if step == "reason_text":
            state["reason"] = text[:400]
            await advance_after_reason(message.chat.id, uid, state)
            return

        if step == "minutes_text":
            minutes = _parse_minutes(text)
            if minutes is None:
                await _safe(bot.send_message(
                    message.chat.id,
                    f"💡 Танҳо рақам нависед — аз 1 то {MINUTES_MAX} (масалан: 20).",
                    reply_markup=_kb_cancel_only(),
                ))
                return
            state["minutes"] = minutes
            state["step"] = "confirm"
            db.set_state(uid, state)
            await ask_confirm(message.chat.id, state)
            return

        if step == "arrival_reason":
            state["delay_reason"] = text[:400]
            state["step"] = "arrival_minutes"
            db.set_state(uid, state)
            await _safe(bot.send_message(
                message.chat.id,
                "⏳ <b>Боз чанд дақиқа пас мерасед?</b>",
                reply_markup=_kb_extra_minutes(),
            ))
            return

        if step == "arrival_minutes_text":
            minutes = _parse_minutes(text)
            if minutes is None:
                await _safe(bot.send_message(
                    message.chat.id,
                    f"💡 Танҳо рақам нависед — аз 1 то {MINUTES_MAX}.",
                    reply_markup=_kb_cancel_only(),
                ))
                return
            await _finish_arrival_delay(bot, message.chat.id, message.from_user, state, minutes)
            return

        # Давомот: сабабро метавон ҳам бо тугма, ҳам бо матн гуфт
        if step in ("att_reason", "att_reason_text", "att_eta", "att_eta_text") and not text:
            return

        if step in ("att_reason", "att_reason_text"):
            state.update(step="att_eta", reason=text[:1000])
            db.set_state(uid, state)
            await _ask_att_eta(message.chat.id, state)
            return

        if step in ("att_eta", "att_eta_text"):
            await _finish_att_absence(message.chat.id, uid, state, text[:300])
            return

        if step in ("reason", "minutes", "confirm", "arrival_minutes"):
            await _safe(bot.send_message(
                message.chat.id,
                "💡 Аз тугмаҳои боло интихоб кунед.\n"
                "Барои аз нав сар кардан — /bekor.",
            ))
            return

        # ҳолати оддӣ — менюи мухтасар, на матни пурраи хушомадед
        await _safe(bot.send_message(
            message.chat.id,
            "🤖 Барои дархост яке аз инҳоро интихоб кунед:",
            reply_markup=_kb_types(),
        ))

    # ── матн дар гурӯҳ: паёми роҳбарият ─────────────────────────────────

    @bot.message_handler(
        func=lambda m: m.chat.id == GROUP_ID and bool(m.from_user), content_types=["text"]
    )
    async def group_text(message: Message):
        state = db.get_state(message.from_user.id)
        if not state or state.get("step") != "admin_feedback":
            return

        db.clear_state(message.from_user.id)
        ok, note = await send_worker_message(
            bot, state["req_id"], message.text or "", _display_name(message.from_user)
        )
        worker = _esc(_short_name(state.get("worker_name", "ҳамкор")))
        await _safe(bot.send_message(
            GROUP_ID,
            f"✅ Паём ба <b>{worker}</b> расид ✉️" if ok else f"⚠️ {note}",
        ))

    log.info("✅ Handler-ҳо ба қайд гирифта шуданд")


# ══════════════════════════════════════════════════════════════════════════
#  Ёрдамчиҳои дохилӣ
# ══════════════════════════════════════════════════════════════════════════

def _parse_minutes(text: str) -> int | None:
    digits = "".join(ch for ch in (text or "") if ch.isdigit())
    if not digits or len(digits) > 5:
        return None
    try:
        value = int(digits)
    except ValueError:
        return None
    return value if 0 < value <= MINUTES_MAX else None


async def _finish_arrival_delay(bot: AsyncTeleBot, chat_id: int, user,
                                state: dict, extra_min: int) -> None:
    db.clear_state(user.id)

    check_id = state["check_id"]
    request_id = state["request_id"]
    reason = state.get("delay_reason", "Номаълум")

    if not db.set_check_delayed(check_id, reason, extra_min):
        await _safe(bot.send_message(chat_id, "ℹ️ Ин савол аллакай ҷавоб гирифтааст."))
        return

    new_at = cfg.plus_minutes(extra_min)
    db.create_arrival_check(request_id, user.id, new_at)
    new_clock = _clock(new_at)

    check = db.get_arrival_check(check_id)
    name = _esc(_short_name(check["name"] if check else _display_name(user)))

    await _safe(bot.send_message(
        GROUP_ID,
        f"⏳ <b>{name}</b> боз каме дер мекунад.\n\n"
        f"📝 <i>{_esc(reason)}</i>\n"
        f"🕰 Вақти нав: <b>{new_clock}</b> (+{_human_minutes(extra_min)})\n"
        f"<code>#{request_id}</code>",
    ))

    await _safe(bot.send_message(
        chat_id,
        f"✨ <b>Ташаккур!</b>\n\n"
        f"Ба роҳбарият хабар додам.\n"
        f"⏳ Соати <b>{new_clock}</b> бори дигар мепурсам.\nРоҳи сафед! 🚶",
    ))


# ══════════════════════════════════════════════════════════════════════════
#  Ҳалқаҳои фонӣ
# ══════════════════════════════════════════════════════════════════════════

async def send_reminders(bot: AsyncTeleBot) -> None:
    for rec in db.get_pending_reminders():
        req_id = rec["id"]
        deadline = cfg.parse_dt(rec.get("deadline_at"))
        remaining = max(0, int((deadline - cfg.now()).total_seconds() // 60)) if deadline else 0
        meta = TYPES.get(rec["type"], {"emoji": "🔔", "third": "дархост"})

        questions = {
            "late": "Ба кор расидед?",
            "at_work_waiting": "Коратонро тамом кардед?",
            "leaving_early": "Аз кор рафтед?",
        }

        if remaining > 0:
            timing = f"⏳ <b>{remaining} дақиқа</b> монд."
        else:
            timing = f"⏳ Вақт расид (<b>{_clock(rec.get('deadline_at'))}</b>)."

        text = (
            f"🔔 <b>Ёдоварӣ</b> · <code>#{req_id}</code>\n\n"
            f"{meta['emoji']} {meta.get('third', '')} — {_human_minutes(rec['minutes'])}\n"
            f"{timing}\n\n"
            f"<b>{questions.get(rec['type'], 'Ҳамааш хуб аст?')}</b>"
        )

        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("✅ Бале", callback_data=f"w:y:{req_id}"),
               InlineKeyboardButton("💬 Не, ҳанӯз не", callback_data=f"w:n:{req_id}"))

        sent = await _safe(bot.send_message(rec["user_id"], text, reply_markup=kb))
        # Ҳатто агар ҳамкор ботро баста бошад — бори дуюм намефиристем.
        db.mark_reminder_sent(req_id)
        if sent is not None:
            log.info("🔔 Ёдоварӣ → %s (#%d)", rec["name"], req_id)


async def notify_overdue(bot: AsyncTeleBot) -> None:
    for rec in db.get_overdue_unconfirmed():
        # «Дер мекунам» бо arrival check санҷида мешавад — ин ҷо намебояд.
        if rec["type"] == "late":
            db.update_worker_confirmation(rec["id"], "no")
            continue

        if not db.update_worker_confirmation(rec["id"], "no"):
            continue

        meta = TYPES.get(rec["type"], {"emoji": "📋", "third": "дархост"})
        await _safe(bot.send_message(
            GROUP_ID,
            f"⏰ <b>Ҷавоб надод</b>\n\n"
            f"👤 <b>{_esc(_short_name(rec['name']))}</b>\n"
            f"{meta['emoji']} {meta['third']} · <code>#{rec['id']}</code>\n"
            f"Вақташ ({_clock(rec.get('deadline_at'))}) гузашт.",
        ))
        await _safe(bot.send_message(
            rec["user_id"],
            "💬 <b>Вақт тамом шуд.</b>\n\n"
            "Лутфан ба паёми боло ҷавоб диҳед. Ташаккур!",
        ))


async def process_arrival_checks(bot: AsyncTeleBot) -> None:
    for check in db.get_pending_arrival_checks():
        check_id = check["id"]

        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("✅ Бале, расидам", callback_data=f"a:y:{check_id}"),
               InlineKeyboardButton("⏳ Ҳанӯз не", callback_data=f"a:n:{check_id}"))

        sent = await _safe(bot.send_message(
            check["user_id"],
            "🔔 <b>Вақт расид</b>\n\n"
            f"Мувофиқи дархости <code>#{check['request_id']}</code> шумо бояд ҳозир дар кор бошед.\n\n"
            "<b>Расидед?</b>",
            reply_markup=kb,
        ))

        if sent is None:
            # Корбар дастрас нест — такрор намекунем, вале дар гурӯҳ хабар медиҳем.
            db.mark_check_asked(check_id, 0)
            await _safe(bot.send_message(
                GROUP_ID,
                f"⚠️ Ба <b>{_esc(_short_name(check['name']))}</b> паём фиристода нашуд "
                f"(<code>#{check['request_id']}</code>) — шояд ботро бастааст.",
            ))
            continue

        db.mark_check_asked(check_id, sent.message_id)
        log.info("🔔 Arrival check #%d → %s", check_id, check["name"])


async def process_work_attendance(bot: AsyncTeleBot) -> None:
    """Мувофиқи вақти кори аз панел гузошташуда аз ҳар корманд мепурсад.

    Сабт пеш аз фиристодан сохта мешавад (UNIQUE дар база), бинобар ин restart-и
    бот ё коркарди такрорӣ саволи дуюм намефиристад. Якшанбе ва идҳо — не.
    """
    for record in db.create_due_attendance():
        # Аввал қайд мекунем, баъд мефиристем: агар бот ҳамин лаҳза афтад,
        # корманд ду бор савол намегирад (беҳтар як бор кам, то ду бор зиёд).
        if not db.mark_attendance_prompted(record["id"]):
            continue
        sent = await _safe(bot.send_message(
            record["user_id"],
            _att_prompt_text(record["name"], _clock(record["scheduled_at"])),
            reply_markup=_kb_att_prompt(record["id"]),
        ))
        if sent is None:
            log.warning("📋 Саволи давомот ба %s нарасид (шояд ботро бастааст)", record["name"])
            continue
        db.set_attendance_msg(record["id"], sent.message_id)
        log.info("📋 Саволи давомот #%d → %s", record["id"], record["name"])


async def remind_attendance(bot: AsyncTeleBot) -> None:
    """Як ёдоварӣ ба онҳое, ки ба саволи субҳ ҷавоб надоданд."""
    for record in db.get_attendance_to_remind():
        db.mark_attendance_reminded(record["id"])
        await _safe(bot.send_message(
            record["user_id"],
            _att_prompt_text(record["name"], _clock(record["scheduled_at"]), reminder=True),
            reply_markup=_kb_att_prompt(record["id"]),
        ))


async def send_daily_report(bot: AsyncTeleBot) -> None:
    """Ҳисоботи давомоти рӯз — як бор ба гурӯҳи роҳбарият."""
    day = db.daily_report_due()
    if not day:
        return
    db.set_settings({"daily_report_sent": day})
    data = db.get_attendance_day(day)
    if not data["items"]:
        return
    await _safe(bot.send_message(GROUP_ID, daily_report_text(data)))
    log.info("📋 Ҳисоботи давомоти %s ба гурӯҳ фиристода шуд", day)


async def daily_backup(bot: AsyncTeleBot) -> None:
    """Нусхаи ҳаррӯзаи база (дар оғоз ва пас аз нисфи шаб) + ихтиёрӣ ба Telegram."""
    today = cfg.today_str()
    if db.get_setting("daily_backup") == today:
        return
    db.set_settings({"daily_backup": today})
    path = db.make_backup("daily")
    if path and cfg.BACKUP_CHAT_ID:
        try:
            with open(path, "rb") as fh:
                await bot.send_document(
                    cfg.BACKUP_CHAT_ID, fh,
                    caption=f"💾 Нусхаи база · {today}", disable_notification=True)
        except Exception as exc:
            log.warning("💾 Нусха ба Telegram нарафт: %s", exc)


async def housekeeping() -> None:
    """Тоза кардани ҳолатҳои фаромӯшшуда."""
    try:
        removed = db.purge_stale_states()
        if removed:
            log.info("🧹 %d ҳолати кӯҳна тоза шуд", removed)
    except Exception as exc:
        log.warning("housekeeping: %s", exc)
