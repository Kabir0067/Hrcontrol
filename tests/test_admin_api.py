"""
Санҷиши API-и панел бо базаи муваққатӣ (бе Telegram).

    python tests/test_admin_api.py            # санҷишҳо
    python tests/test_admin_api.py --serve    # танҳо сервер бо маълумоти намунавӣ (порт 18901)
"""
import asyncio
import os
import random
import sys
import tempfile
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TMP = tempfile.mkdtemp()
os.environ.update({
    "BOT_TOKEN": "123456:TEST", "DB_PATH": os.path.join(TMP, "t.db"),
    "LOG_PATH": os.path.join(TMP, "t.log"), "ADMIN_LOGIN": "softclub",
    "ADMIN_PASS": "8520", "SECRET_KEY": "test-secret", "HTTP_HOST": "127.0.0.1",
    "HTTP_PORT": "18901",
})
sys.path.insert(0, ROOT)

import config as cfg          # noqa: E402
import database as db         # noqa: E402
import admin_server           # noqa: E402

admin_server.BACKUP_DIR = os.path.join(TMP, "backups")

NAMES = ["Ismoil Sufonqulzoda (@ismoil_121)", "Najibulloh (@NajibullohShamsudinov)",
         "Kabir Gafurov (@kabir0067)", "Мадина Раҳимова", "Фарҳод Каримов (@farhod_k)",
         "Сабина Алиева (@sabina)", "Шерзод Турсунов", "Нигора Юсупова (@nigora_y)"]
REASONS = {
    "late": ["Мушкилии нақлиёт", "Роҳбандӣ (пробка)", "Кори шахсӣ", "Аҳволам нағз нест", "Ба духтур рафтам"],
    "absent": ["Бемор шудам", "Кори оилавӣ", "Ба духтур меравам", "Сафари корӣ"],
    "at_work_waiting": ["Кори шахсӣ", "Ба банк / идора", "Хӯроки нисфирӯзӣ"],
    "leaving_early": ["Кори шахсӣ", "Меҳмон дорам", "Кори оилавӣ", "Аҳволам нағз нест"],
}


def seed(n=240):
    db.init_db()
    rnd = random.Random(7)
    now = datetime.now()
    with db._tx() as conn:
        for i, name in enumerate(NAMES):
            uid = 1000 + i
            conn.execute("INSERT OR REPLACE INTO employees VALUES (?,?,?,?,?)",
                         (uid, name.split(" (@")[0], name.split("(@")[1][:-1] if "(@" in name else None,
                          (now - timedelta(days=80)).strftime(cfg.DT_FMT), now.strftime(cfg.DT_FMT)))
        for k in range(n):
            i = rnd.choices(range(len(NAMES)), weights=[8, 6, 3, 5, 4, 2, 2, 1])[0]
            t = rnd.choices(list(REASONS), weights=[6, 2, 3, 2])[0]
            created = now - timedelta(days=rnd.randint(0, 75), hours=rnd.randint(0, 9), minutes=rnd.randint(0, 59))
            created = created.replace(hour=rnd.choice([7, 8, 8, 8, 9, 9, 10, 12, 13, 15, 16, 17]))
            minutes = 0 if t == "absent" else rnd.choice([10, 15, 20, 30, 45, 60, 90])
            status = rnd.choices(["accepted", "rejected", "pending", "cancelled"], weights=[70, 12, 6, 5])[0]
            if k < 3:
                status, created = "pending", now - timedelta(minutes=5 + k * 7)
            decided = created + timedelta(minutes=rnd.randint(1, 40)) if status in ("accepted", "rejected") else None
            conn.execute(
                """INSERT INTO requests (user_id, name, type, reason, minutes, status, reminder_sent,
                   worker_confirmed, created_at, deadline_at, decided_by, decided_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (1000 + i, NAMES[i], t, rnd.choice(REASONS[t]) if rnd.random() > .1 else "Тӯй дорам <b>", minutes,
                 status, 1, rnd.choice([None, "yes", "no"]) if status == "accepted" else None,
                 created.strftime(cfg.DT_FMT),
                 (created + timedelta(minutes=minutes)).strftime(cfg.DT_FMT) if minutes else None,
                 rnd.choice(["Директор (@boss)", "HR Мадина"]) if decided else None,
                 decided.strftime(cfg.DT_FMT) if decided else None))


results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))


async def run_tests():
    from aiohttp.test_utils import TestClient, TestServer
    app = admin_server.build_app()
    async with TestClient(TestServer(app)) as c:
        r = await c.post("/api/login", json={"login": "softclub", "password": "bad"})
        check("login wrong password → 401", r.status == 401)
        r = await c.post("/api/login", json={"login": "softclub", "password": "8520"})
        tok = (await r.json())["token"]
        check("login with .env password", r.status == 200)
        H = {"Authorization": f"Bearer {tok}"}

        r = await c.get("/api/analytics", headers=H)
        a = await r.json()
        check("analytics all-time", r.status == 200 and a["summary"]["total"] == 240, a["summary"]["total"])
        check("analytics reasons merged & sorted", a["reasons"][0]["count"] >= a["reasons"][-1]["count"])
        check("analytics weekday/hours sums", sum(a["weekday"]) == 240 and sum(a["hours"]) == 240)
        check("analytics daily series continuous", len(a["daily"]) >= 70)
        check("analytics workers have top_reason", all(w["top_reason"] for w in a["workers"]))
        check("analytics avg response computed", a["summary"]["avg_response_min"] is not None)

        today = datetime.now().strftime("%Y-%m-%d")
        week = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
        r = await c.get(f"/api/analytics?date_from={week}&date_to={today}", headers=H)
        a7 = await r.json()
        check("analytics period filter", 0 < a7["summary"]["total"] < 240 and len(a7["daily"]) == 7)

        r = await c.get("/api/requests?type=late&status=accepted&sort=minutes&limit=5", headers=H)
        d = await r.json()
        check("requests filter+sort", all(x["type"] == "late" and x["status"] == "accepted" for x in d["items"])
              and d["items"][0]["minutes"] >= d["items"][-1]["minutes"])
        r = await c.get("/api/requests?user_id=1000&limit=500", headers=H)
        d = await r.json()
        check("requests by worker", d["total"] > 0 and all(x["user_id"] == 1000 for x in d["items"]))
        r = await c.get("/api/requests?q=нақлиёт", headers=H)
        check("requests search", (await r.json())["total"] > 0)

        r = await c.get("/api/workers/1000", headers=H)
        w = await r.json()
        check("worker detail", r.status == 200 and w["summary"]["total"] == d["total"] and w["reasons"])
        r = await c.get("/api/workers/999999", headers=H)
        check("worker detail 404", r.status == 404)

        r = await c.get("/api/export.csv?type=absent", headers=H)
        body = await r.text()
        check("csv export filtered", r.status == 200 and "Намеояд" in body and "Дер мекунад" not in body)
        r = await c.get(f"/api/export.csv?token={tok}")
        check("csv export via ?token=", r.status == 200)
        r = await c.get(f"/api/backup.db?token={tok}")
        raw = await r.read()
        check("db backup download", r.status == 200 and raw[:15] == b"SQLite format 3")

        # ── вақти корӣ ва ҳозиршавӣ (даври корӣ 5 → 4)
        r = await c.post("/api/work-schedule", headers=H, json={"time": "08:30"})
        check("work schedule saved", r.status == 200 and (await r.json())["time"] == "08:30")
        r = await c.post("/api/work-schedule", headers=H, json={"time": "25:99"})
        check("work schedule validates time", r.status == 400)
        due = db.create_due_attendance()
        # Ҳангоми иҷрои тест баъди 08:30 ҳамаи кормандони seed бояд сабт шаванд;
        # агар тест пеш аз он оғоз шавад, ин функсия қасдан чизе намефиристад.
        if due:
            check("daily attendance created once", len(due) == len(NAMES))
            check("attendance present recorded", db.set_attendance_present(due[0]["id"]))
            check("attendance absent recorded", db.set_attendance_absent(due[1]["id"], "Бемор", "Пагоҳ"))
            for item in due:
                db.mark_attendance_prompted(item["id"])
            check("daily attendance never duplicates", db.create_due_attendance() == [])
        r = await c.get("/api/attendance", headers=H)
        attendance = await r.json()
        check("attendance report has work-month 5→4", r.status == 200 and
              attendance["period"]["start"].endswith("-05") and attendance["period"]["end"].endswith("-04"))

        # ── нест кардан
        first = (await (await c.get("/api/requests?limit=3", headers=H)).json())["items"]
        r = await c.delete(f"/api/requests/{first[0]['id']}", headers=H)
        check("delete one", r.status == 200 and db.get_request(first[0]["id"]) is None)
        r = await c.post("/api/requests/delete", headers=H, json={"ids": [first[1]["id"], first[2]["id"]]})
        check("delete selected (2)", (await r.json())["deleted"] == 2)
        many = [x["id"] for x in (await (await c.get("/api/requests?limit=30", headers=H)).json())["items"]]
        r = await c.post("/api/requests/delete", headers=H, json={"ids": many})
        check("delete >20 without password", r.status == 200)
        r = await c.post("/api/requests/delete", headers=H, json={"filters": {"type": "absent"}})
        j = await r.json()
        check("delete by filter", r.status == 200 and j["deleted"] > 0 and j["backup"])
        cnt = (await (await c.get("/api/requests?type=absent", headers=H)).json())["total"]
        check("filtered really gone", cnt == 0)
        r = await c.post("/api/workers/1007/delete", headers=H, json={})
        check("delete worker", r.status == 200 and (await (await c.get("/api/workers/1007", headers=H)).read()) and
              db.get_worker_detail(1007) is None)

        # ── иваз кардани логин/рамз
        r = await c.post("/api/account", headers=H, json={"new_login": "admin", "new_password": "Secret123", "new_password_confirm": "different"})
        check("account change requires repeated password", r.status == 400)
        r = await c.post("/api/account", headers=H, json={"new_login": "admin", "new_password": "12345", "new_password_confirm": "12345"})
        check("account weak password rejected", r.status == 400)
        r = await c.post("/api/account", headers=H, json={"new_login": "admin", "new_password": "Secret123", "new_password_confirm": "Secret123"})
        j = await r.json()
        check("account change ok", r.status == 200 and j["token"])
        r = await c.get("/api/dashboard", headers=H)
        check("old token invalidated after change", r.status == 401)
        H = {"Authorization": f"Bearer {j['token']}"}
        check("new token works", (await c.get("/api/dashboard", headers=H)).status == 200)
        r = await c.post("/api/login", json={"login": "softclub", "password": "8520"})
        check("old credentials rejected", r.status == 401)
        r = await c.post("/api/login", json={"login": "admin", "password": "Secret123"})
        check("new credentials work", r.status == 200)
        H = {"Authorization": f"Bearer {(await r.json())['token']}"}
        acc = await (await c.get("/api/account", headers=H)).json()
        check("account info", acc["login"] == "admin" and acc["source"] == "panel")

        # ── тозакунӣ
        r = await c.post("/api/wipe", headers=H, json={"scope": "requests", "confirm": "no"})
        check("wipe needs confirm word", r.status == 400)
        old = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        r = await c.post("/api/wipe", headers=H, json={"before": old, "confirm": "ТОЗА"})
        j = await r.json()
        rem = (await (await c.get("/api/requests", headers=H)).json())["items"]
        check("wipe before date", r.status == 200 and all(x["created_at"][:10] > old for x in rem))
        r = await c.post("/api/wipe", headers=H, json={"scope": "all", "confirm": "тоза"})
        a = await (await c.get("/api/analytics", headers=H)).json()
        check("wipe all", r.status == 200 and a["summary"]["total"] == 0 and a["daily"] == [])
        check("settings survive wipe", db.get_setting("admin_login") == "admin")
        b = await (await c.get("/api/backups", headers=H)).json()
        check("auto backups created", len(b["items"]) >= 3)
        a = await (await c.get("/api/dashboard", headers=H)).json()
        check("dashboard on empty db", a["total"] == 0)


async def serve():
    from aiohttp import web
    app = admin_server.build_app()

    async def dev_login(request):                  # танҳо барои скриншотҳои санҷишӣ
        tok = admin_server._make_jwt({"user": "softclub", "role": "admin"})
        view = request.query.get("view", "home")
        theme = request.query.get("theme", "light")
        return web.Response(content_type="text/html", text=(
            f"<script>localStorage.setItem('sc_token','{tok}');localStorage.setItem('sc_view','{view}');"
            f"localStorage.setItem('sc_theme','{theme}');location.replace('/');</script>"))
    app.router.add_get("/__dev_login", dev_login)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 18901).start()
    print("serving http://127.0.0.1:18901/", flush=True)
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    seed()
    if "--serve" in sys.argv:
        asyncio.run(serve())
    else:
        asyncio.run(run_tests())
        print(f"\n{sum(results)}/{len(results)} passed")
        sys.exit(0 if all(results) else 1)
