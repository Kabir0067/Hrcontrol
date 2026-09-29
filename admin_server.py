"""
SoftClub / Hrcontrol — сервери панели маъмурият (aiohttp).

Хусусиятҳо:
  • /api/health — бе авторизатсия, барои мониторинг ва nginx;
  • JWT-и дуруст (padding-и base64 ислоҳшуда) + маҳдудкунии кӯшишҳои вуруд;
  • оморҳо дар база ҳисоб мешаванд (тез);
  • аз панел метавон дархостро тасдиқ/рад кард ва ба ҳамкор паём фиристод;
  • экспорти CSV;
  • статикаи панел бо кэши дуруст.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import time
from collections import defaultdict

from aiohttp import web

import config as cfg
import database as db

log = logging.getLogger("SoftClubBot")

STATIC_DIR = cfg.STATIC_DIR
STARTED_AT = time.time()

# ip → [timestamp, …] барои маҳдудкунии вуруд
_login_hits: dict[str, list[float]] = defaultdict(list)

# Аз main.py гузошта мешавад, то панел тавонад қарор қабул кунад.
BOT = None


def set_bot(bot) -> None:
    global BOT
    BOT = bot


# ══════════════════════════════════════════════════════════════════════════
#  JWT
# ══════════════════════════════════════════════════════════════════════════

def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _make_jwt(payload: dict) -> str:
    header = _b64e(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = {**payload, "iat": int(time.time()), "exp": int(time.time()) + cfg.TOKEN_TTL}
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
        except Exception as exc:                    # pragma: no cover
            log.exception("API %s: %s", request.path, exc)
            return _err("Хатои дохилии сервер", 500)
    wrapper.__name__ = getattr(handler, "__name__", "guarded")
    return wrapper


# ══════════════════════════════════════════════════════════════════════════
#  Endpoint-ҳо
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
        "polling": {"ok": polling_ok, "last_update_age": poll_age},
        "db": state,
    }, 200 if healthy else 503)


async def handle_login(request: web.Request) -> web.Response:
    ip = _client_ip(request)
    now = time.time()
    hits = [t for t in _login_hits[ip] if now - t < cfg.LOGIN_WINDOW]
    _login_hits[ip] = hits

    if len(hits) >= cfg.LOGIN_MAX_TRIES:
        return _err("Кӯшишҳо зиёданд. Пас аз чанд дақиқа кӯшиш кунед.", 429)

    if not cfg.ADMIN_PASS:
        # Рамзи холӣ = вуруди ҳама бо сатри холӣ. Ҳеҷ гоҳ иҷозат намедиҳем.
        log.error("🔒 ADMIN_PASS дар .env гузошта нашудааст — вуруд ба панел баста аст")
        return _err("Панел танзим нашудааст (ADMIN_PASS)", 503)

    try:
        data = await request.json()
    except Exception:
        return _err("Маълумоти нодуруст")

    login = str(data.get("login", "")).strip()
    password = str(data.get("password", "")).strip()

    ok = (hmac.compare_digest(login, cfg.ADMIN_LOGIN)
          and hmac.compare_digest(password, cfg.ADMIN_PASS))

    if not ok:
        _login_hits[ip].append(now)
        log.warning("🔒 Кӯшиши нодурусти вуруд аз %s", ip)
        return _err("Логин ё рамз нодуруст аст", 401)

    _login_hits.pop(ip, None)
    return _json({"token": _make_jwt({"user": login, "role": "admin"}), "user": login})


@_guard
async def handle_dashboard(request: web.Request) -> web.Response:
    summary = db.get_summary()
    summary["daily"] = db.get_daily_stats(7)
    return _json(summary)


@_guard
async def handle_requests(request: web.Request) -> web.Response:
    q = request.query
    return _json(db.query_requests(
        req_type=q.get("type") or None,
        status=q.get("status") or None,
        date_from=q.get("date_from") or None,
        date_to=q.get("date_to") or None,
        search=(q.get("q") or "").strip() or None,
        limit=int(q.get("limit", 50) or 50),
        offset=int(q.get("offset", 0) or 0),
    ))


@_guard
async def handle_workers(request: web.Request) -> web.Response:
    return _json(db.get_worker_stats())


@_guard
async def handle_stats(request: web.Request) -> web.Response:
    days = int(request.query.get("days", 14) or 14)
    return _json({
        "daily": db.get_daily_stats(days),
        "workers": db.get_worker_stats(),
        "summary": db.get_summary(),
    })


@_guard
async def handle_decision(request: web.Request) -> web.Response:
    if BOT is None:
        return _err("Бот дастрас нест", 503)

    try:
        req_id = int(request.match_info["req_id"])
        payload = await request.json()
    except Exception:
        return _err("Маълумоти нодуруст")

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

    try:
        req_id = int(request.match_info["req_id"])
        payload = await request.json()
    except Exception:
        return _err("Маълумоти нодуруст")

    text = str(payload.get("text", "")).strip()
    if not text:
        return _err("Матн холӣ аст")

    import handlers
    ok, note = await handlers.send_worker_message(BOT, req_id, text[:2000], "Панели маъмурият")
    return _json({"ok": ok, "message": note}, 200 if ok else 409)


@_guard
async def handle_export(request: web.Request) -> web.Response:
    rows = db.export_rows()
    buf = io.StringIO()
    columns = ["id", "user_id", "name", "type", "reason", "minutes", "status",
               "worker_confirmed", "decided_by", "created_at", "deadline_at"]
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    body = "﻿" + buf.getvalue()          # BOM — то Excel кириллро дуруст кушояд
    return web.Response(
        body=body.encode("utf-8"),
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": f'attachment; filename="softclub-{cfg.today_str()}.csv"',
        },
    )


async def handle_index(request: web.Request) -> web.Response:
    path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.isfile(path):
        return web.Response(text="admin_panel/index.html ёфт нашуд", status=500)
    return web.FileResponse(path, headers={
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
    return response


# ══════════════════════════════════════════════════════════════════════════
#  Оғоз
# ══════════════════════════════════════════════════════════════════════════

def build_app() -> web.Application:
    app = web.Application(middlewares=[security_headers])
    r = app.router

    r.add_get("/api/health", handle_health)
    r.add_post("/api/login", handle_login)
    r.add_get("/api/dashboard", handle_dashboard)
    r.add_get("/api/requests", handle_requests)
    r.add_get("/api/workers", handle_workers)
    r.add_get("/api/stats", handle_stats)
    r.add_get("/api/export.csv", handle_export)
    r.add_post("/api/requests/{req_id}/decision", handle_decision)
    r.add_post("/api/requests/{req_id}/message", handle_message)

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
