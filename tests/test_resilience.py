"""Offline checks for the shutdown / supervise / health fixes (no Telegram needed)."""
import asyncio
import os
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
tmp = tempfile.mkdtemp()
os.environ.update({
    "BOT_TOKEN": "123456:TEST_TOKEN_NOT_REAL",
    "DB_PATH": os.path.join(tmp, "t.db"),
    "LOG_PATH": os.path.join(tmp, "t.log"),
    "ADMIN_PASS": "",
    "SECRET_KEY": "",
    "POLL_STALE_SEC": "300",
})
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import main            # noqa: E402
import config as cfg   # noqa: E402
import admin_server    # noqa: E402
import database as db  # noqa: E402

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


async def swallow_cancel():
    """Behaves like telebot.infinity_polling: eats CancelledError and returns."""
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        return


async def t_supervise_cancel_swallowed():
    main._stopping = False
    task = asyncio.create_task(main.supervise("x", swallow_cancel))
    await asyncio.sleep(0.05)
    task.cancel()
    _, pending = await asyncio.wait([task], timeout=3)
    check("supervise exits when lib swallows cancel (cancelling())", not pending)
    for t in pending:
        t.cancel()


async def t_supervise_flag():
    main._stopping = False
    task = asyncio.create_task(main.supervise("y", swallow_cancel))
    await asyncio.sleep(0.05)
    main._stopping = True
    task.cancel()
    _, pending = await asyncio.wait([task], timeout=3)
    check("supervise exits with _stopping flag", not pending)
    main._stopping = False


async def t_supervise_restarts_on_crash():
    main._stopping = False
    calls = {"n": 0}

    async def crashy():
        calls["n"] += 1
        raise RuntimeError("boom")

    orig_sleep = asyncio.sleep

    async def fast_sleep(d, *a, **k):
        await orig_sleep(0)

    asyncio.sleep = fast_sleep
    try:
        task = asyncio.create_task(main.supervise("z", crashy))
        for _ in range(50):
            await orig_sleep(0)
        main._stopping = True
        _, pending = await asyncio.wait([task], timeout=3)
    finally:
        asyncio.sleep = orig_sleep
        main._stopping = False
    check("supervise restarts a crashing subsystem (%d runs)" % calls["n"], calls["n"] >= 3)
    check("supervise stops after crashes when stopping", not pending)


async def t_connect_retry():
    stop = asyncio.Event()
    n = {"c": 0}

    class Me:
        username, id = "test_bot", 1

    async def flaky():
        n["c"] += 1
        if n["c"] < 3:
            raise ConnectionError("network down")
        return Me()

    main.bot.get_me = flaky
    orig_wait_for = asyncio.wait_for

    async def fast_wait_for(aw, timeout):
        return await orig_wait_for(aw, 0.01)

    asyncio.wait_for = fast_wait_for
    try:
        ok = await main.connect_telegram(stop)
    finally:
        asyncio.wait_for = orig_wait_for
    check("connect_telegram retries network errors then succeeds", ok and n["c"] == 3)

    from telebot.asyncio_helper import ApiTelegramException

    async def bad_token():
        raise ApiTelegramException("getMe", None, {"error_code": 401, "description": "Unauthorized"})

    main.bot.get_me = bad_token
    ok = await main.connect_telegram(stop)
    check("connect_telegram gives up on 401 (invalid token)", ok is False)

    async def never():
        raise ConnectionError("down")

    main.bot.get_me = never
    stop2 = asyncio.Event()
    t = asyncio.create_task(main.connect_telegram(stop2))
    await asyncio.sleep(0.05)
    stop2.set()
    _, pending = await asyncio.wait([t], timeout=2)
    check("connect_telegram stops promptly on SIGTERM while waiting", not pending)


class FakeReq:
    def __init__(self, query=None, remote="127.0.0.1", headers=None):
        self.query = query or {}
        self.remote = remote
        self.headers = headers or {}
        self.path = "/api/health"


async def t_health_and_login():
    db.init_db()
    admin_server.set_bot(main.bot)
    import json as _j

    main.bot.last_poll_ok = time.time()
    r = await admin_server.handle_health(FakeReq({"strict": "1"}))
    body = _j.loads(r.body)
    check("health strict=200 when polling fresh", r.status == 200 and body["polling"]["ok"])

    main.bot.last_poll_ok = time.time() - 1000
    r = await admin_server.handle_health(FakeReq({"strict": "1"}))
    check("health strict=503 when polling stale", r.status == 503)
    r = await admin_server.handle_health(FakeReq({}))
    check("health non-strict stays 200 for panel", r.status == 200)

    main.bot.last_poll_ok = 0
    r = await admin_server.handle_health(FakeReq({"strict": "1"}))
    check("health strict ok during startup grace", r.status == 200)

    check("client ip ignores spoofed X-Forwarded-For",
          admin_server._client_ip(FakeReq(remote="127.0.0.1",
                                          headers={"X-Forwarded-For": "1.2.3.4", "X-Real-IP": "9.9.9.9"})) == "9.9.9.9")
    check("client ip direct connection = remote",
          admin_server._client_ip(FakeReq(remote="5.5.5.5", headers={"X-Real-IP": "9.9.9.9"})) == "5.5.5.5")

    class LoginReq(FakeReq):
        async def json(self):
            return {"login": cfg.ADMIN_LOGIN, "password": ""}

    r = await admin_server.handle_login(LoginReq())
    check("login refused when ADMIN_PASS empty (no empty-password login)", r.status == 503)
    check("SECRET_KEY random when unset", len(cfg.SECRET_KEY) == 64)


async def t_restore_missing_db():
    """База нест шуд → пеш аз init_db аз нусхаи охирин барқарор мешавад, на холӣ."""
    db.init_db()
    db.touch_employee(42, "Санҷиш", None)
    path = db.make_backup("daily")
    check("backup file created", path and os.path.exists(path))
    for ext in ("", "-wal", "-shm"):
        try:
            os.remove(db.DB_PATH + ext)
        except OSError:
            pass
    restored = db.restore_if_missing()
    db.init_db()
    check("missing DB restored from newest backup", restored == path and db.get_employee(42) is not None)
    check("restore is a no-op when DB exists", db.restore_if_missing() is None)


async def run():
    await t_restore_missing_db()
    await t_supervise_cancel_swallowed()
    await t_supervise_flag()
    await t_supervise_restarts_on_crash()
    await t_connect_retry()
    await t_health_and_login()


asyncio.run(run())
bad = [n for n, ok in results if not ok]
print("\n%d/%d passed" % (len(results) - len(bad), len(results)))
sys.exit(1 if bad else 0)
