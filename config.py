"""
SoftClub / Hrcontrol — ягона манбаи танзимот.

Ҳама танзимот аз муҳити система (environment) ё файли `.env` хонда мешаванд.
Агар чизе набошад — қимати пешфарз кор мекунад, бинобар ин деплой ҳеҷ гоҳ
бинобар набудани `.env` намемирад.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

APP_NAME = "SoftClub HR Control"
VERSION = "3.0.0"
BUILD = "2026081502"          # барои cache-busting дар панел


# ──────────────────────────────────────────────────────────────────────────
#  .env loader (бе ягон вобастагии беруна)
# ──────────────────────────────────────────────────────────────────────────

def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in raw_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            os.environ.setdefault(key, val)


_load_dotenv(BASE_DIR / ".env")


def _s(key: str, default: str) -> str:
    val = os.environ.get(key)
    return val.strip() if val and val.strip() else default


def _i(key: str, default: int) -> int:
    try:
        return int(str(os.environ.get(key, "")).strip())
    except (TypeError, ValueError):
        return default


def _b(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on", "ҳа", "ha")


# ──────────────────────────────────────────────────────────────────────────
#  Telegram
# ──────────────────────────────────────────────────────────────────────────

BOT_TOKEN = _s("BOT_TOKEN", "")
GROUP_ID = _i("GROUP_ID", -1003933020249)

# URL-и Mini App. Telegram ҳатман https талаб мекунад.
WEBAPP_URL = _s("WEBAPP_URL", "https://test.softclub.tj/hrcontrol/")


# ──────────────────────────────────────────────────────────────────────────
#  Панели маъмурият
# ──────────────────────────────────────────────────────────────────────────

ADMIN_LOGIN = _s("ADMIN_LOGIN", "softclub")
ADMIN_PASS = _s("ADMIN_PASS", "")
SECRET_KEY = _s("SECRET_KEY", "")

HTTP_HOST = _s("HTTP_HOST", "0.0.0.0")
HTTP_PORT = _i("HTTP_PORT", 8901)

TOKEN_TTL = _i("TOKEN_TTL", 7 * 86400)          # 7 рӯз
LOGIN_MAX_TRIES = _i("LOGIN_MAX_TRIES", 8)      # дар як тиреза
LOGIN_WINDOW = _i("LOGIN_WINDOW", 300)          # сония


# ──────────────────────────────────────────────────────────────────────────
#  Мантиқи корӣ
# ──────────────────────────────────────────────────────────────────────────

MINUTES_MAX = _i("MINUTES_MAX", 720)            # 12 соат
REMINDER_LEAD = _i("REMINDER_LEAD", 3)          # чанд дақиқа пеш огоҳ кунад

# Дархостҳое, ки мӯҳлаташон аз ин зиёдтар гузаштааст, «кӯҳна» ҳисоб мешаванд.
# Ин муҳофизат аст: пас аз деплой ё хомӯшии дароз бот набояд ба ҳама
# ёдовариҳои таърихиро якбора фиристад.
STALE_AFTER = _i("STALE_AFTER", 180)            # дақиқа

LOOP_INTERVAL = _i("LOOP_INTERVAL", 20)         # сония, тикери фонӣ
STATE_TTL = _i("STATE_TTL", 3600)               # ҳолати нотамоми корбар (сония)
MAX_OPEN_REQUESTS = _i("MAX_OPEN_REQUESTS", 1)  # чанд дархости "pending" ҳамзамон


# ──────────────────────────────────────────────────────────────────────────
#  Роҳҳо ва logging
# ──────────────────────────────────────────────────────────────────────────

DB_PATH = _s("DB_PATH", str(BASE_DIR / "softclub.db"))
STATIC_DIR = str(BASE_DIR / "admin_panel")
LOG_PATH = _s("LOG_PATH", str(BASE_DIR / "bot.log"))
LOG_LEVEL = _s("LOG_LEVEL", "INFO").upper()
LOG_MAX_BYTES = _i("LOG_MAX_BYTES", 5 * 1024 * 1024)
LOG_BACKUPS = _i("LOG_BACKUPS", 3)


# ──────────────────────────────────────────────────────────────────────────
#  Вақт — ҳамеша бо вақти маҳаллӣ (Душанбе), на UTC-и сервер
# ──────────────────────────────────────────────────────────────────────────

TZ_NAME = _s("TZ_NAME", "Asia/Dushanbe")

try:                                            # pragma: no cover
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(TZ_NAME)
except Exception:                               # tzdata насбнашуда (масалан Windows)
    TZ = timezone(timedelta(hours=5))

DT_FMT = "%Y-%m-%d %H:%M:%S"
DATE_FMT = "%Y-%m-%d"


def now() -> datetime:
    """Вақти ҷории маҳаллӣ (naive) — мувофиқи формати базаи мавҷуда."""
    return datetime.now(TZ).replace(tzinfo=None)


def now_str() -> str:
    return now().strftime(DT_FMT)


def today_str() -> str:
    return now().strftime(DATE_FMT)


def to_str(dt: datetime) -> str:
    return dt.strftime(DT_FMT)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in (DT_FMT, "%Y-%m-%dT%H:%M:%S", DATE_FMT):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


def plus_minutes(minutes: int) -> str:
    return to_str(now() + timedelta(minutes=minutes))
