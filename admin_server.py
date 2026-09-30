"""
SoftClub / Hrcontrol — сервери панели маъмурият (aiohttp).

Хусусиятҳо:
  • /api/health — бе авторизатсия, барои мониторинг ва nginx;
  • JWT-и дуруст + маҳдудкунии кӯшишҳои вуруд;
  • вуруди худкор аз Telegram Mini App (initData + админи гурӯҳи роҳбарият);
  • логин/рамзи панел аз худи панел иваз мешавад (дар база, бо PBKDF2);
    пас аз иваз ҳамаи сессияҳои кӯҳна беэътибор мешаванд;
  • давомот: вақти корӣ, ҷадвали рӯз ва моҳи корӣ (5 → 4), ислоҳи дастӣ, CSV;
  • нест кардан бе рамз — вале ҳамеша пас аз нусхаи эҳтиётии худкор;
  • омори муфассал ва экспорти CSV.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import glob
import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets
import time
import urllib.parse
from collections import defaultdict

from aiohttp import web

import config as cfg
import database as db

log = logging.getLogger("SoftClubBot")

STATIC_DIR = cfg.STATIC_DIR
STARTED_AT = time.time()
BACKUP_DIR = cfg.BACKUP_DIR
BACKUP_KEEP = cfg.BACKUP_KEEP

# Telegram user_id-ҳое, ки бе рамз ба панел медароянд (ғайр аз админҳои гурӯҳ).
ADMIN_IDS = {int(x) for x in re.findall(r"-?\d+", os.environ.get("ADMIN_IDS", ""))}
_tg_admin_cache: dict[int, tuple[float, bool]] = {}

# ip → [timestamp, …] барои маҳдудкунии вуруд
_login_hits: dict[str, list[float]] = defaultdict(list)

# Аз main.py гузошта мешавад, то панел тавонад қарор қабул кунад.
BOT = None

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def set_bot(bot) -> None:
    global BOT
    BOT = bot


# ══════════════════════════════════════════════════════════════════════════
#  Логин ва рамз
# ══════════════════════════════════════════════════════════════════════════
#  Манбаъ: аввал база (агар аз панел иваз шуда бошад), вагарна .env.

_PBKDF2_ROUNDS = 240_000


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def _check_hash(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(dk.hex(), digest)
    except (ValueError, TypeError):
        return False


def _admin_login() -> str:
    return db.get_setting("admin_login") or cfg.ADMIN_LOGIN


def _token_version() -> str:
    return db.get_setting("token_version", "0") or "0"


def _verify_credentials(login: str, password: str) -> bool:
    login_ok = hmac.compare_digest(login.encode(), _admin_login().encode())
    stored = db.get_setting("admin_pass_hash")
    if stored:
        pass_ok = _check_hash(password, stored)
    else:
        # Рамзи холӣ = вуруди ҳама бо сатри холӣ — ҳеҷ гоҳ.
        pass_ok = bool(cfg.ADMIN_PASS) and hmac.compare_digest(
            password.encode(), cfg.ADMIN_PASS.encode())
    return login_ok and pass_ok


def _password_configured() -> bool:
    return bool(db.get_setting("admin_pass_hash") or cfg.ADMIN_PASS)


# ══════════════════════════════════════════════════════════════════════════
#  JWT
# ══════════════════════════════════════════════════════════════════════════

def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _make_jwt(payload: dict) -> str:
    header = _b64e(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = {**payload, "tv": _token_version(),
               "iat": int(time.time()), "exp": int(time.time()) + cfg.TOKEN_TTL}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(cfg.SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64e(sig)}"


def _verify_jwt(token: str) -> dict | None:
    try:
        header, body, signature = token.split(".")
    except (ValueError, AttributeError):
        return None
    try:
        expected = _b64e(hmac.new(
            cfg.SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256
        ).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_b64d(body))
        if float(payload.get("exp", 0)) < time.time():
            return None
        if str(payload.get("tv", "0")) != _token_version():   # рамз иваз шуд
            return None
        return payload
    except Exception:
        return None


def _auth(request: web.Request) -> dict | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return _verify_jwt(header[7:])
    token = request.query.get("token")
    return _verify_jwt(token) if token else None


def _client_ip(request: web.Request) -> str:
    """
    IP-и воқеии мизоҷ.

    Ба X-Forwarded-For бовар намекунем: мизоҷ онро худаш навишта метавонад
    (nginx танҳо илова мекунад) ва бо ҳар дархост IP-и «нав» нишон дода,
    маҳдудкунии кӯшишҳои вурудро мегузаронд. Паси nginx (пайваст аз localhost)
    X-Real-IP-ро мегирем — онро nginx худаш аз $remote_addr мегузорад.
    """
    remote = request.remote or "?"
    if remote in ("127.0.0.1", "::1"):
        real = request.headers.get("X-Real-IP", "").strip()
        if real:
            return real
    return remote


def _rate_limited(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _login_hits[ip] if now - t < cfg.LOGIN_WINDOW]
    _login_hits[ip] = hits
    return len(hits) >= cfg.LOGIN_MAX_TRIES


# ══════════════════════════════════════════════════════════════════════════
#  Ёрдамчиҳо
# ══════════════════════════════════════════════════════════════════════════

def _json(data, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, dumps=lambda o: json.dumps(o, ensure_ascii=False))


def _err(message: str, status: int = 400) -> web.Response:
    return _json({"error": message}, status)


def _guard(handler):
    """Декоратор: талаби токен + гирифтани хатоҳои ғайричашмдошт."""
    async def wrapper(request: web.Request) -> web.Response:
        if not _auth(request):
            return _err("Unauthorized", 401)
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except (ValueError, TypeError) as exc:
            return _err(f"Маълумоти нодуруст: {exc}", 400)
        except Exception as exc:                    # pragma: no cover
            log.exception("API %s: %s", request.path, exc)
            return _err("Хатои дохилии сервер", 500)
    wrapper.__name__ = getattr(handler, "__name__", "guarded")
    return wrapper


def _date(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if _DATE_RE.match(value) else None


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _filters(q) -> dict:
    """Филтрҳои умумии дархостҳо аз query ё JSON."""
    return {
        "req_type": q.get("type") or None,
        "status": q.get("status") or None,
        "date_from": _date(q.get("date_from")),
        "date_to": _date(q.get("date_to")),
        "search": (q.get("q") or "").strip() or None,
        "user_id": _int(q.get("user_id")) or None,
    }


async def _body(request: web.Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        raise ValueError("JSON лозим аст")
    if not isinstance(data, dict):
        raise ValueError("JSON-объект лозим аст")
    return data


def _make_backup(tag: str) -> str | None:
    """Нусхаи худкор пеш аз ҳар нест кардан (номи файл ё None)."""
    path = db.make_backup(tag, BACKUP_DIR)
    return os.path.basename(path) if path else None


def _check_init_data(init_data: str) -> dict | None:
    """Санҷиши имзои initData-и Telegram Mini App (HMAC-SHA256 бо токени бот)."""
    if not init_data or not cfg.BOT_TOKEN:
        return None
    try:
        pairs = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received = pairs.pop("hash", "")
    if not received:
        return None
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", cfg.BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return None
    try:
        if time.time() - int(pairs.get("auth_date", "0")) > 86400:      # 24 соат
            return None
        user = json.loads(pairs.get("user", "{}"))
    except (TypeError, ValueError):
        return None
    return user if isinstance(user, dict) and user.get("id") else None


async def _is_tg_admin(user_id: int) -> bool:
    """Админ = дар ADMIN_IDS ё админ/соҳиби гурӯҳи роҳбарият (кэш 5 дақиқа)."""
    if user_id in ADMIN_IDS:
        return True
    hit = _tg_admin_cache.get(user_id)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    ok = False
    if BOT is not None:
        try:
            member = await BOT.get_chat_member(cfg.GROUP_ID, user_id)
            ok = getattr(member, "status", "") in ("creator", "administrator")
        except Exception as exc:
            log.info("Telegram-вуруд: санҷиши %s дар гурӯҳ нашуд (%s)", user_id, exc)
    _tg_admin_cache[user_id] = (time.time(), ok)
    return ok


# ══════════════════════════════════════════════════════════════════════════
#  Endpoint-ҳо: умумӣ
# ══════════════════════════════════════════════════════════════════════════

async def handle_health(request: web.Request) -> web.Response:
    """
    /api/health          — 200, агар база кор кунад (барои панел ва nginx).
    /api/health?strict=1 — ғайр аз ин, polling-и Telegram бояд зинда бошад;
                           watchdog маҳз ҳаминро месанҷад.
    """
    state = db.healthcheck()
    now = time.time()
    uptime = int(now - STARTED_AT)

    last_poll = float(getattr(BOT, "last_poll_ok", 0) or 0)
    poll_age = int(now - last_poll) if last_poll else None
    conflict = float(getattr(BOT, "conflict_at", 0) or 0)
    conflict_age = int(now - conflict) if conflict else None
    polling_ok = (
        (poll_age is not None and poll_age <= cfg.POLL_STALE_SEC)
        or (last_poll == 0 and uptime <= cfg.POLL_STALE_SEC)      # ҳанӯз оғоз мешавад
    )

    db_ok = bool(state.get("ok"))
    strict = request.query.get("strict", "").lower() in ("1", "true", "yes")
    healthy = db_ok and (polling_ok or not strict)

    return _json({
        "ok": healthy,
        "app": cfg.APP_NAME,
        "version": cfg.VERSION,
        "build": cfg.BUILD,
        "uptime": uptime,
        "time": cfg.now_str(),
        "tz": cfg.TZ_NAME,
        "bot": BOT is not None,
        "polling": {"ok": polling_ok, "last_update_age": poll_age,
                    "conflict": conflict_age is not None and conflict_age < 900,
                    "conflict_age": conflict_age},
        "db": state,
    }, 200 if healthy else 503)


async def handle_login(request: web.Request) -> web.Response:
    ip = _client_ip(request)
    if _rate_limited(ip):
        return _err("Кӯшишҳо зиёданд. Пас аз чанд дақиқа кӯшиш кунед.", 429)

    if not _password_configured():
        log.error("🔒 ADMIN_PASS дар .env гузошта нашудааст — вуруд ба панел баста аст")
        return _err("Панел танзим нашудааст (ADMIN_PASS)", 503)

    try:
        data = await request.json()
    except Exception:
        return _err("Маълумоти нодуруст")

    login = str(data.get("login", "")).strip()
    password = str(data.get("password", ""))

    if not _verify_credentials(login, password):
        _login_hits[ip].append(time.time())
        log.warning("🔒 Кӯшиши нодурусти вуруд аз %s", ip)
        return _err("Логин ё рамз нодуруст аст", 401)

    _login_hits.pop(ip, None)
    log.info("🔓 Вуруд ба панел аз %s", ip)
    return _json({"token": _make_jwt({"user": login, "role": "admin"}), "user": login})


async def handle_login_telegram(request: web.Request) -> web.Response:
    """Вуруд бе рамз аз дохили Telegram — танҳо барои админҳои гурӯҳи роҳбарият."""
    ip = _client_ip(request)
    if _rate_limited(ip):
        return _err("Кӯшишҳо зиёданд. Пас аз чанд дақиқа кӯшиш кунед.", 429)
    try:
        data = await request.json()
    except Exception:
        return _err("Маълумоти нодуруст")
    user = _check_init_data(str((data or {}).get("init_data", "")))
    if not user:
        _login_hits[ip].append(time.time())
        return _err("Telegram тасдиқ нашуд", 401)
    uid = int(user["id"])
    if not await _is_tg_admin(uid):
        log.info("🔒 Telegram-вуруд рад шуд: %s (%s)", uid, user.get("first_name"))
        return _err("Шумо админи гурӯҳи роҳбарият нестед — бо логин ва рамз ворид шавед", 403)
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or str(uid)
    log.info("🔓 Вуруд ба панел аз Telegram: %s (%s)", name, uid)
    return _json({"token": _make_jwt({"user": f"tg:{uid}", "name": name, "role": "admin"}),
                  "user": name})


@_guard
async def handle_account(request: web.Request) -> web.Response:
    who = _auth(request) or {}
    return _json({
        "login": _admin_login(),
        "source": "panel" if db.get_setting("admin_pass_hash") else "env",
        "changed_at": db.get_setting("admin_changed_at"),
        "me": who.get("name") or who.get("user"),
        "via": "telegram" if str(who.get("user", "")).startswith("tg:") else "password",
    })


@_guard
async def handle_account_update(request: web.Request) -> web.Response:
    data = await _body(request)
    new_login = str(data.get("new_login", "")).strip() or _admin_login()
    new_password = str(data.get("new_password", ""))
    password_confirm = str(data.get("new_password_confirm", ""))

    if not re.fullmatch(r"[A-Za-z0-9_.@\-]{3,32}", new_login):
        return _err("Логин: 3–32 аломат (ҳарфи лотинӣ, рақам, _ . @ -)")
    if not new_password:
        return _err("Рамзи навро ворид кунед")
    if new_password != password_confirm:
        return _err("Ду рамзи нав якхела нестанд")
    if len(new_password) < 6:
        return _err("Рамзи нав бояд ақаллан 6 аломат бошад")
    if new_password.isdigit() and len(new_password) < 8:
        return _err("Рамзи танҳо рақамӣ бояд ақаллан 8 аломат бошад")

    values = {
        "admin_login": new_login,
        "admin_changed_at": cfg.now_str(),
        # Ҳамаи токенҳои кӯҳна (дигар телефонҳо/браузерҳо) беэътибор мешаванд
        "token_version": secrets.token_hex(6),
    }
    values["admin_pass_hash"] = _hash_password(new_password)

    db.set_settings(values)
    log.warning("🔐 Логин/рамзи панел иваз шуд (логин: %s, аз %s)", new_login, _client_ip(request))
    return _json({
        "ok": True,
        "login": new_login,
        "token": _make_jwt({"user": new_login, "role": "admin"}),
        "message": "Маълумоти вуруд иваз шуд. Дигар дастгоҳҳо бояд аз нав ворид шаванд.",
    })


# ══════════════════════════════════════════════════════════════════════════
#  Endpoint-ҳо: маълумот
# ══════════════════════════════════════════════════════════════════════════

@_guard
async def handle_dashboard(request: web.Request) -> web.Response:
    summary = db.get_summary()
    summary["daily"] = db.get_daily_stats(7)
    return _json(summary)


@_guard
async def handle_requests(request: web.Request) -> web.Response:
    q = request.query
    return _json(db.query_requests(
        **_filters(q),
        limit=_int(q.get("limit"), 30) or 30,
        offset=_int(q.get("offset"), 0),
        sort=q.get("sort") or None,
    ))


@_guard
async def handle_request_one(request: web.Request) -> web.Response:
    rec = db.get_request(_int(request.match_info["req_id"]))
    if not rec:
        return _err("Дархост ёфт нашуд", 404)
    return _json(rec)


@_guard
async def handle_workers(request: web.Request) -> web.Response:
    q = request.query
    return _json(db.get_worker_stats(_date(q.get("date_from")), _date(q.get("date_to"))))


@_guard
async def handle_worker_detail(request: web.Request) -> web.Response:
    q = request.query
    data = db.get_worker_detail(_int(request.match_info["user_id"]),
                                _date(q.get("date_from")), _date(q.get("date_to")))
    if not data:
        return _err("Корманд ёфт нашуд", 404)
    return _json(data)


@_guard
async def handle_stats(request: web.Request) -> web.Response:
    days = _int(request.query.get("days"), 14) or 14
    return _json({
        "daily": db.get_daily_stats(days),
        "workers": db.get_worker_stats(),
        "summary": db.get_summary(),
    })


@_guard
async def handle_analytics(request: web.Request) -> web.Response:
    q = request.query
    return _json(db.get_analytics(_date(q.get("date_from")), _date(q.get("date_to"))))


@_guard
async def handle_overview(request: web.Request) -> web.Response:
    return _json(db.get_overview())


# ── Вақти корӣ ва давомот ──────────────────────────────────────────────

@_guard
async def handle_work_schedule(request: web.Request) -> web.Response:
    return _json(db.get_schedule())


@_guard
async def handle_work_schedule_update(request: web.Request) -> web.Response:
    data = await _body(request)
    kwargs: dict = {}
    if "time" in data:
        value = str(data.get("time") or "").strip()
        if value and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            return _err("Вақтро ба шакли 08:30 нависед")
        kwargs["time"] = value
    if "days" in data:
        days = data.get("days")
        if not isinstance(days, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in days):
            return _err("Рӯзҳои корӣ нодурустанд")
        if not days:
            return _err("Ақаллан як рӯзи кориро интихоб кунед")
        kwargs["days"] = days
    if "grace" in data:
        grace = _int(data.get("grace"), -1)
        if not 0 <= grace <= 120:
            return _err("Муҳлат бояд аз 0 то 120 дақиқа бошад")
        kwargs["grace"] = grace
    if "report" in data:
        kwargs["report"] = bool(data.get("report"))
    sch = db.set_schedule(**kwargs)
    if "time" in kwargs:
        message = (f"Вақти корӣ: {sch['time']}. Кормандон ҳар рӯзи корӣ савол мегиранд"
                   if sch["time"] else "Саволи ҳаррӯза хомӯш шуд")
    else:
        message = "Сабт шуд"
    return _json({"ok": True, **sch, "message": message})


def _period(q) -> str | None:
    period = (q.get("period") or "").strip()
    if period and not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", period):
        raise ValueError("моҳи корӣ нодуруст аст")
    return period or None


@_guard
async def handle_attendance(request: web.Request) -> web.Response:
    return _json(db.get_attendance_month(_period(request.query),
                                         _int(request.query.get("user_id")) or None))


@_guard
async def handle_attendance_day(request: web.Request) -> web.Response:
    return _json(db.get_attendance_day(_date(request.query.get("date"))))


@_guard
async def handle_attendance_stats(request: web.Request) -> web.Response:
    q = request.query
    return _json(db.get_attendance_stats(_date(q.get("date_from")), _date(q.get("date_to")),
                                         _int(q.get("user_id")) or None))


@_guard
async def handle_attendance_set(request: web.Request) -> web.Response:
    data = await _body(request)
    day = _date(data.get("date"))
    if not day:
        return _err("Санаро интихоб кунед")
    status = str(data.get("status", ""))
    if day > cfg.today_str() and status != "leave":
        return _err("Барои рӯзҳои оянда танҳо «рухсатӣ» гузоштан мумкин аст")
    cell = db.admin_set_attendance(
        _int(data.get("user_id")), day, status,
        clock=data.get("time"), reason=data.get("reason"), eta=data.get("eta"))
    return _json({"ok": True, "cell": cell, "message": "Сабт шуд"})


@_guard
async def handle_attendance_delete(request: web.Request) -> web.Response:
    if not db.delete_attendance(_int(request.match_info["att_id"])):
        return _err("Сабт ёфт нашуд", 404)
    return _json({"ok": True, "message": "Сабт нест шуд"})


@_guard
async def handle_day_off(request: web.Request) -> web.Response:
    data = await _body(request)
    day = _date(data.get("date"))
    if not day:
        return _err("Санаро интихоб кунед")
    off = bool(data.get("off"))
    db.set_day_off(day, off, str(data.get("title") or ""))
    return _json({"ok": True, "message": "Рӯзи истироҳат шуд" if off else "Рӯзи корӣ шуд"})


# ── Кормандон ──────────────────────────────────────────────────────────

@_guard
async def handle_employees(request: web.Request) -> web.Response:
    return _json(db.list_employees())


@_guard
async def handle_employee_update(request: web.Request) -> web.Response:
    data = await _body(request)
    uid = _int(request.match_info["user_id"])
    if not db.get_employee(uid):
        return _err("Корманд ёфт нашуд", 404)
    alias = str(data["alias"]) if "alias" in data and data["alias"] is not None else None
    active = bool(data["active"]) if "active" in data else None
    db.update_employee(uid, alias=alias, active=active)
    return _json({"ok": True, "employee": db.get_employee(uid), "message": "Сабт шуд"})


@_guard
async def handle_decision(request: web.Request) -> web.Response:
    if BOT is None:
        return _err("Бот дастрас нест", 503)

    req_id = _int(request.match_info["req_id"])
    payload = await _body(request)
    decision = payload.get("decision")
    if decision not in ("accepted", "rejected"):
        return _err("Қарори номаълум")

    import handlers
    ok, note = await handlers.apply_decision(BOT, req_id, decision, "Панели маъмурият")
    return _json({"ok": ok, "message": note}, 200 if ok else 409)


@_guard
async def handle_message(request: web.Request) -> web.Response:
    if BOT is None:
        return _err("Бот дастрас нест", 503)

    req_id = _int(request.match_info["req_id"])
    payload = await _body(request)
    text = str(payload.get("text", "")).strip()
    if not text:
        return _err("Матн холӣ аст")

    import handlers
    ok, note = await handlers.send_worker_message(BOT, req_id, text[:2000], "Панели маъмурият")
    return _json({"ok": ok, "message": note}, 200 if ok else 409)


# ══════════════════════════════════════════════════════════════════════════
#  Endpoint-ҳо: нест кардан
# ══════════════════════════════════════════════════════════════════════════

@_guard
async def handle_request_delete(request: web.Request) -> web.Response:
    req_id = _int(request.match_info["req_id"])
    if not db.get_request(req_id):
        return _err("Дархост ёфт нашуд", 404)
    removed = db.delete_requests([req_id])
    return _json({"ok": True, "deleted": removed, "message": f"Дархости #{req_id} нест шуд"})


@_guard
async def handle_requests_delete(request: web.Request) -> web.Response:
    """{"ids": [...]} — интихобшудаҳо; {"filters": {...}, "password": …} — ҳама аз рӯи филтр."""
    data = await _body(request)
    ids = data.get("ids")

    if isinstance(ids, list) and ids:
        ids = [_int(i) for i in ids if _int(i) > 0][:5000]
        backup = _make_backup("selected") if len(ids) > 1 else None
        removed = db.delete_requests(ids)
        return _json({"ok": True, "deleted": removed, "backup": backup,
                      "message": f"{removed} дархост нест шуд"})

    if isinstance(data.get("filters"), dict):
        backup = _make_backup("filtered")
        removed = db.delete_filtered(**_filters(data["filters"]))
        return _json({"ok": True, "deleted": removed, "backup": backup,
                      "message": f"{removed} дархост нест шуд"})

    return _err("Чизе интихоб нашудааст")


@_guard
async def handle_worker_delete(request: web.Request) -> web.Response:
    backup = _make_backup("worker")
    result = db.delete_worker(_int(request.match_info["user_id"]))
    return _json({"ok": True, **result, "backup": backup,
                  "message": "Корманд ва ҳамаи маълумоташ нест шуд"})


@_guard
async def handle_wipe(request: web.Request) -> web.Response:
    """Бе рамз ва бе калимаи тасдиқ — панел худаш як бор мепурсад; нусха ҳатмист."""
    data = await _body(request)
    scope = "all" if data.get("scope") == "all" else "requests"
    before = _date(data.get("before"))
    backup = _make_backup("wipe")
    if not backup:
        return _err("Нусхаи эҳтиётӣ сохта нашуд — тозакунӣ бекор шуд", 500)
    counts = db.wipe(scope, before)
    return _json({"ok": True, "counts": counts, "backup": backup,
                  "message": f"Тоза шуд: {counts.get('requests', 0)} дархост, "
                             f"{counts.get('attendance', 0)} сабти давомот"})


@_guard
async def handle_backups(request: web.Request) -> web.Response:
    items = []
    for path in sorted(glob.glob(os.path.join(BACKUP_DIR, "softclub_*.db")), reverse=True):
        try:
            items.append({"name": os.path.basename(path), "size": os.path.getsize(path),
                          "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))})
        except OSError:
            continue
    return _json({"items": items, "keep": BACKUP_KEEP})


@_guard
async def handle_backup_download(request: web.Request) -> web.Response:
    """Нусхаи ҳозираи база барои боргирӣ."""
    buf_path = os.path.join(BACKUP_DIR, ".download.db")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    await asyncio.to_thread(db.backup_to, buf_path)
    with open(buf_path, "rb") as fh:
        body = fh.read()
    try:
        os.remove(buf_path)
    except OSError:
        pass
    return web.Response(body=body, headers={
        "Content-Type": "application/octet-stream",
        "Content-Disposition": f'attachment; filename="softclub-{cfg.today_str()}.db"',
        "Cache-Control": "no-store",
    })


# ══════════════════════════════════════════════════════════════════════════
#  Экспорт ва статика
# ══════════════════════════════════════════════════════════════════════════

_TYPE_TG = {"late": "Дер мекунад", "absent": "Намеояд",
            "at_work_waiting": "Ҷавоб мепурсад", "leaving_early": "Барвақт меравад"}
_STATUS_TG = {"pending": "Дар интизорӣ", "accepted": "Иҷозат", "rejected": "Рад",
              "cancelled": "Бекор"}


@_guard
async def handle_export(request: web.Request) -> web.Response:
    rows = db.export_rows(**_filters(request.query))
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n", delimiter=";")
    writer.writerow(["№", "Корманд", "Навъ", "Сабаб", "Дақиқа", "Вазъият",
                     "Қарор кард", "Тасдиқи корманд", "Сана", "Мӯҳлат"])
    for r in rows:
        writer.writerow([
            r["id"], r.get("alias") or r["name"], _TYPE_TG.get(r["type"], r["type"]), r["reason"],
            r["minutes"] or "", _STATUS_TG.get(r["status"], r["status"]),
            r.get("decided_by") or "",
            {"yes": "Бале", "no": "Не"}.get(r.get("worker_confirmed") or "", ""),
            r["created_at"], r.get("deadline_at") or "",
        ])

    body = "﻿" + buf.getvalue()          # BOM — то Excel кириллро дуруст кушояд
    return web.Response(
        body=body.encode("utf-8"),
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": f'attachment; filename="softclub-{cfg.today_str()}.csv"',
            "Cache-Control": "no-store",
        },
    )


_WD_SHORT = ["Дш", "Сш", "Чш", "Пш", "Ҷм", "Шб", "Яш"]
_STATE_TG = {"on_time": "Сари вақт", "late": "Дер омад", "absent": "Наомад",
             "leave": "Рухсатӣ", "pending": "Ҷавоб надод"}


def _csv_response(buf: io.StringIO, name: str) -> web.Response:
    return web.Response(
        body=("﻿" + buf.getvalue()).encode("utf-8"),     # BOM — Excel кириллро дуруст мекушояд
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )


@_guard
async def handle_attendance_export(request: web.Request) -> web.Response:
    """Ҷадвали моҳи корӣ: сатр — корманд, сутун — рӯз; дар поён — рӯйхати муфассал."""
    data = db.get_attendance_month(_period(request.query))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n", delimiter=";")
    days = data["days"]
    w.writerow([f"Давомот: {data['period']['start']} — {data['period']['end']}",
                f"Оғози кор: {data['schedule']['time'] or '—'}"])
    w.writerow(["Корманд"] + [f"{d['date'][8:10]}.{d['date'][5:7]} {_WD_SHORT[d['wd']]}" for d in days]
               + ["Омад", "Сари вақт", "Дер", "Наомад", "Рухсатӣ", "Ҷавоб надод",
                  "Дерӣ (дақ.)", "Давомот %", "Миёнаи омадан"])
    for emp in data["employees"]:
        row = [emp["name"]]
        for d in days:
            cell = emp["cells"].get(d["date"])
            if cell:
                row.append({"on_time": cell["t"], "late": f"{cell['t']} (+{cell['late']})",
                            "absent": "Н", "leave": "Р", "pending": "?"}.get(cell["s"], ""))
            else:
                row.append("—" if not d["workday"] else "")
        s = emp["summary"]
        row += [s["present"], s["on_time"], s["late"], s["absent"], s["leave"], s["pending"],
                s["late_minutes"], "" if s["rate"] is None else s["rate"], s["avg_arrival"] or ""]
        w.writerow(row)
    w.writerow([])
    w.writerow(["Шартҳо: 08:25 — сари вақт; 08:47 (+17) — дер (дақиқа); Н — наомад; "
                "Р — рухсатӣ; ? — ҷавоб надод; — — рӯзи истироҳат"])
    w.writerow([])
    w.writerow(["Сана", "Корманд", "Ҳолат", "Вақти омадан", "Дер (дақ.)", "Сабаб", "Кай меояд", "Манбаъ"])
    for emp in data["employees"]:
        for day, cell in sorted(emp["cells"].items()):
            w.writerow([day, emp["name"], _STATE_TG.get(cell["s"], cell["s"]), cell["t"],
                        cell["late"] or "", cell["reason"], cell["eta"],
                        {"bot": "бот", "admin": "админ", "request": "дархост"}.get(cell["src"], cell["src"])])
    return _csv_response(buf, f"davomot-{data['period']['key']}.csv")


async def handle_index(request: web.Request) -> web.Response:
    """index.html бо рақами версия дар ?v= — браузер ҳеҷ гоҳ JS/CSS-и кӯҳнаро нигоҳ намедорад."""
    path = os.path.join(STATIC_DIR, "index.html")
    try:
        stamp = max(int(os.path.getmtime(os.path.join(STATIC_DIR, f)))
                    for f in ("index.html", "app.js", "style.css")
                    if os.path.exists(os.path.join(STATIC_DIR, f)))
        with open(path, encoding="utf-8") as fh:
            html_text = fh.read().replace("__BUILD__", f"{cfg.BUILD}.{stamp}")
    except (OSError, ValueError):
        return web.Response(text="admin_panel/index.html ёфт нашуд", status=500)
    return web.Response(text=html_text, content_type="text/html", headers={
        "Cache-Control": "no-store, must-revalidate",
        "X-Content-Type-Options": "nosniff",
    })


@web.middleware
async def security_headers(request: web.Request, handler):
    try:
        response = await handler(request)
    except web.HTTPException:
        raise
    except Exception as exc:                        # pragma: no cover
        log.exception("HTTP %s: %s", request.path, exc)
        return _err("Хатои дохилии сервер", 500)

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# ══════════════════════════════════════════════════════════════════════════
#  Оғоз
# ══════════════════════════════════════════════════════════════════════════

def build_app() -> web.Application:
    app = web.Application(middlewares=[security_headers], client_max_size=2 * 1024 * 1024)
    r = app.router

    r.add_get("/api/health", handle_health)
    r.add_post("/api/login", handle_login)
    r.add_post("/api/login/telegram", handle_login_telegram)
    r.add_get("/api/account", handle_account)
    r.add_post("/api/account", handle_account_update)

    r.add_get("/api/overview", handle_overview)
    r.add_get("/api/dashboard", handle_dashboard)
    r.add_get("/api/analytics", handle_analytics)
    r.add_get("/api/stats", handle_stats)
    r.add_get("/api/export.csv", handle_export)

    r.add_get("/api/work-schedule", handle_work_schedule)
    r.add_post("/api/work-schedule", handle_work_schedule_update)
    r.add_get("/api/attendance", handle_attendance)
    r.add_get("/api/attendance/month", handle_attendance)
    r.add_get("/api/attendance/day", handle_attendance_day)
    r.add_get("/api/attendance/stats", handle_attendance_stats)
    r.add_get("/api/attendance.csv", handle_attendance_export)
    r.add_post("/api/attendance", handle_attendance_set)
    r.add_delete("/api/attendance/{att_id:\\d+}", handle_attendance_delete)
    r.add_post("/api/days-off", handle_day_off)

    r.add_get("/api/employees", handle_employees)
    r.add_post("/api/employees/{user_id:\\d+}", handle_employee_update)

    r.add_get("/api/requests", handle_requests)
    r.add_post("/api/requests/delete", handle_requests_delete)
    r.add_get("/api/requests/{req_id:\\d+}", handle_request_one)
    r.add_delete("/api/requests/{req_id:\\d+}", handle_request_delete)
    r.add_post("/api/requests/{req_id:\\d+}/decision", handle_decision)
    r.add_post("/api/requests/{req_id:\\d+}/message", handle_message)

    r.add_get("/api/workers", handle_workers)
    r.add_get("/api/workers/{user_id:\\d+}", handle_worker_detail)
    r.add_post("/api/workers/{user_id:\\d+}/delete", handle_worker_delete)

    r.add_post("/api/wipe", handle_wipe)
    r.add_get("/api/backups", handle_backups)
    r.add_get("/api/backup.db", handle_backup_download)

    r.add_get("/", handle_index)
    r.add_get("/index.html", handle_index)
    if os.path.isdir(STATIC_DIR):
        r.add_static("/static/", path=STATIC_DIR, name="static")

    return app


async def start_admin_server(bot=None) -> None:
    """
    Серверро мебардорад ва то бекор шудан кор мекунад.

    Агар порт банд бошад — бот намемирад, балки ҳар 30 сония аз нав кӯшиш мекунад.
    """
    if bot is not None:
        set_bot(bot)

    runner = web.AppRunner(build_app(), access_log=None)
    await runner.setup()

    try:
        while True:
            site = web.TCPSite(runner, cfg.HTTP_HOST, cfg.HTTP_PORT, reuse_address=True)
            try:
                await site.start()
            except OSError as exc:
                log.error("🌐 Порт %s:%s банд аст (%s). Пас аз 30 сония аз нав…",
                          cfg.HTTP_HOST, cfg.HTTP_PORT, exc)
                await asyncio.sleep(30)
                continue

            log.info("🌐 Панел: http://%s:%s  →  %s",
                     cfg.HTTP_HOST, cfg.HTTP_PORT, cfg.WEBAPP_URL)
            while True:
                await asyncio.sleep(3600)
    finally:
        await runner.cleanup()
