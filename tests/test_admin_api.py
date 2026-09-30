"""
Санҷиши API-и панел бо базаи муваққатӣ (бе Telegram).

    python tests/test_admin_api.py            # санҷишҳо
    python tests/test_admin_api.py --serve    # танҳо сервер бо маълумоти намунавӣ (порт 18901)
"""
import asyncio
import hashlib
import hmac
import json
import os
import random
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime, timedelta
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TMP = tempfile.mkdtemp()
os.environ.update({
    "BOT_TOKEN": "123456:TEST", "DB_PATH": os.path.join(TMP, "t.db"),
    "LOG_PATH": os.path.join(TMP, "t.log"), "ADMIN_LOGIN": "softclub",
    "ADMIN_PASS": "8520", "SECRET_KEY": "test-secret", "HTTP_HOST": "127.0.0.1",
    "HTTP_PORT": "18901", "BACKUP_DIR": os.path.join(TMP, "backups"), "ADMIN_IDS": "",
})
sys.path.insert(0, ROOT)

import logging                # noqa: E402
logging.disable(logging.WARNING)

import config as cfg          # noqa: E402
import database as db         # noqa: E402
import admin_server           # noqa: E402

NAMES = ["Ismoil Sufonqulzoda (@ismoil_121)", "Najibulloh (@NajibullohShamsudinov)",
         "Kabir Gafurov (@kabir0067)", "Мадина Раҳимова", "Фарҳод Каримов (@farhod_k)",
         "Сабина Алиева (@sabina)", "Шерзод Турсунов", "Нигора Юсупова (@nigora_y)"]
REASONS = {
    "late": ["Мушкилии нақлиёт", "Роҳбандӣ (пробка)", "Кори шахсӣ", "Аҳволам нағз нест", "Ба духтур рафтам"],
    "absent": ["Бемор шудам", "Кори оилавӣ", "Ба духтур меравам", "Сафари корӣ"],
    "at_work_waiting": ["Кори шахсӣ", "Ба банк / идора", "Хӯроки нисфирӯзӣ"],
    "leaving_early": ["Кори шахсӣ", "Меҳмон дорам", "Кори оилавӣ", "Аҳволам нағз нест"],
}
ABSENT = [("Бемор ҳастам", "пагоҳ меояд"), ("Кори оилавӣ", "баъди нисфирӯзӣ"),
          ("Ба духтур рафтам", "тақрибан соати 11:00"), ("Дар роҳ ҳастам", "тақрибан соати 09:40")]
# Одатҳои кормандон: (сари вақт, дер, наомад, бе ҷавоб)
HABITS = [(90, 6, 2, 2), (55, 35, 5, 5), (93, 4, 2, 1), (70, 10, 15, 5),
          (60, 30, 5, 5), (95, 3, 1, 1), (85, 10, 3, 2), (0, 0, 0, 0)]


def seed(n=240):
    db.init_db()
    rnd = random.Random(7)
    now = datetime.now()
    with db._tx() as conn:
        for i, name in enumerate(NAMES):
            uid = 1000 + i
            conn.execute("INSERT OR REPLACE INTO employees (user_id, name, username, first_seen, last_seen, active) "
                         "VALUES (?,?,?,?,?,?)",
                         (uid, name, name.split("(@")[1][:-1] if "(@" in name else None,
                          (now - timedelta(days=80)).strftime(cfg.DT_FMT), now.strftime(cfg.DT_FMT),
                          0 if i == 7 else 1))
        for k in range(n):
            i = rnd.choices(range(len(NAMES)), weights=[8, 6, 3, 5, 4, 2, 2, 1])[0]
            t = rnd.choices(list(REASONS), weights=[6, 2, 3, 2])[0]
            created = now - timedelta(days=rnd.randint(0, 75), hours=rnd.randint(0, 9), minutes=rnd.randint(0, 59))
            created = created.replace(hour=rnd.choice([7, 8, 8, 8, 9, 9, 10, 12, 13, 15, 16, 17]))
            if created > now:
                created -= timedelta(days=1)
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

        # Давомот: 60 рӯзи охир, бе якшанбе; имрӯз — танҳо қисман
        for back in range(60, -1, -1):
            day = (now - timedelta(days=back)).date()
            if day.weekday() == 6:
                continue
            for i, name in enumerate(NAMES):
                if i == 7:
                    continue
                if i == 6 and 12 <= back <= 17:
                    st, arr, reason, eta = "leave", None, "Рухсатии меҳнатӣ", None
                else:
                    st = rnd.choices(["on", "late", "absent", "pending"], weights=HABITS[i])[0]
                    reason = eta = arr = None
                    if st == "on":
                        arr = datetime.combine(day, datetime.min.time()).replace(hour=8, minute=rnd.randint(5, 39))
                    elif st == "late":
                        arr = datetime.combine(day, datetime.min.time()).replace(hour=8, minute=41) \
                            + timedelta(minutes=rnd.choice([3, 7, 12, 18, 25, 40, 55, 80]))
                    elif st == "absent":
                        reason, eta = rnd.choice(ABSENT)
                    if back == 0 and i in (2, 5):
                        st, arr = "pending", None                     # имрӯз ҳанӯз ҷавоб надодаанд
                    st = {"on": "present", "late": "present"}.get(st, st)
                stamp = f"{day} 08:30:00"
                conn.execute(
                    """INSERT INTO attendance (user_id, name, work_date, scheduled_at, status, prompted_at,
                       arrived_at, reason, eta, source, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (1000 + i, name, day.isoformat(), stamp, st, stamp,
                     arr.strftime(cfg.DT_FMT) if arr else None, reason, eta,
                     "admin" if st == "leave" else "bot", stamp, stamp))
    db.set_schedule(time="08:30", days=[0, 1, 2, 3, 4, 5], grace=10, report=True)


results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))


def signed_init_data(user_id: int, token: str = "123456:TEST", age: int = 0) -> str:
    data = {"auth_date": str(int(time.time()) - age), "query_id": "AAHtest",
            "user": json.dumps({"id": user_id, "first_name": "Роҳбар"}, ensure_ascii=False)}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(data)


class FakeTgBot:
    last_poll_ok = time.time()
    conflict_at = 0.0

    async def get_chat_member(self, chat_id, user_id):
        return SimpleNamespace(status="administrator" if user_id == 777 else "member")


async def run_tests():
    from aiohttp.test_utils import TestClient, TestServer
    admin_server.set_bot(FakeTgBot())
    app = admin_server.build_app()
    async with TestClient(TestServer(app)) as c:
        r = await c.get("/")
        html = await r.text()
        check("index served with build version", r.status == 200 and "__BUILD__" not in html and cfg.BUILD in html)

        r = await c.post("/api/login", json={"login": "softclub", "password": "bad"})
        check("login wrong password → 401", r.status == 401)
        r = await c.post("/api/login", json={"login": "softclub", "password": "8520"})
        tok = (await r.json())["token"]
        check("login with .env password", r.status == 200)
        H = {"Authorization": f"Bearer {tok}"}

        # ── вуруд аз Telegram
        r = await c.post("/api/login/telegram", json={"init_data": signed_init_data(777)})
        j = await r.json()
        check("telegram login for group admin", r.status == 200 and j.get("token"))
        tg_tok = j.get("token")
        r = await c.get("/api/account", headers={"Authorization": f"Bearer {tg_tok}"})
        check("telegram session works", r.status == 200 and (await r.json())["via"] == "telegram")
        r = await c.post("/api/login/telegram", json={"init_data": signed_init_data(888)})
        check("telegram login refused for non-admin", r.status == 403)
        r = await c.post("/api/login/telegram", json={"init_data": signed_init_data(777, token="999:OTHER")})
        check("telegram login refused for forged signature", r.status == 401)
        r = await c.post("/api/login/telegram", json={"init_data": signed_init_data(777, age=2 * 86400)})
        check("telegram login refused for stale init data", r.status == 401)
        admin_server._login_hits.clear()

        # ── саҳифаи асосӣ
        r = await c.get("/api/overview", headers=H)
        o = await r.json()
        check("overview", r.status == 200 and o["today"]["schedule"]["time"] == "08:30"
              and o["requests"]["pending"] >= 3 and len(o["week_attendance"]) == 7, o.get("today", {}).get("summary"))
        check("overview pending list", len(o["pending"]) >= 3 and all(p["status"] == "pending" for p in o["pending"]))

        # ── омор
        r = await c.get("/api/analytics", headers=H)
        a = await r.json()
        check("analytics all-time", r.status == 200 and a["summary"]["total"] == 240, a["summary"]["total"])
        check("analytics reasons merged & sorted", a["reasons"][0]["count"] >= a["reasons"][-1]["count"])
        check("analytics weekday/hours sums", sum(a["weekday"]) == 240 and sum(a["hours"]) == 240)
        check("analytics daily series continuous", len(a["daily"]) >= 70)
        check("analytics includes attendance", a["attendance"]["summary"]["days"] > 300
              and a["attendance"]["summary"]["rate"] is not None)
        check("attendance workers ranked", len(a["attendance"]["workers"]) == 7)

        today = datetime.now().strftime("%Y-%m-%d")
        week = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
        r = await c.get(f"/api/analytics?date_from={week}&date_to={today}", headers=H)
        a7 = await r.json()
        check("analytics period filter", 0 < a7["summary"]["total"] < 240 and len(a7["daily"]) == 7)
        check("attendance period filter", 0 < a7["attendance"]["summary"]["days"] < a["attendance"]["summary"]["days"])

        # ── дархостҳо
        r = await c.get("/api/requests?type=late&status=accepted&sort=minutes&limit=5", headers=H)
        d = await r.json()
        check("requests filter+sort", all(x["type"] == "late" and x["status"] == "accepted" for x in d["items"])
              and d["items"][0]["minutes"] >= d["items"][-1]["minutes"])
        r = await c.get("/api/requests?user_id=1000&limit=500", headers=H)
        d = await r.json()
        check("requests by worker", d["total"] > 0 and all(x["user_id"] == 1000 for x in d["items"]))
        r = await c.get("/api/requests?q=нақлиёт", headers=H)
        check("requests search", (await r.json())["total"] > 0)
        r = await c.get("/api/requests?q=МАДИНА", headers=H)
        check("cyrillic search is case-insensitive", (await r.json())["total"] > 0)

        r = await c.get("/api/workers/1000", headers=H)
        w = await r.json()
        check("worker detail", r.status == 200 and w["summary"]["total"] == d["total"] and w["reasons"]
              and w["attendance"]["summary"]["days"] > 0)
        r = await c.get("/api/workers/999999", headers=H)
        check("worker detail 404", r.status == 404)

        # ── кормандон
        r = await c.get("/api/employees", headers=H)
        emps = await r.json()
        check("employees list", r.status == 200 and len(emps) == 8 and "month" in emps[0])
        check("inactive employee flagged", any(e["user_id"] == 1007 and not e["active"] for e in emps))
        r = await c.post("/api/employees/1003", headers=H, json={"alias": "Мадина Р."})
        check("rename employee", r.status == 200 and (await r.json())["employee"]["display"] == "Мадина Р.")
        r = await c.get("/api/requests?q=Мадина Р.", headers=H)
        check("alias searchable in requests", (await r.json())["total"] > 0)
        r = await c.post("/api/employees/1006", headers=H, json={"active": False})
        check("deactivate employee", r.status == 200 and not db.get_employee(1006)["active"])
        r = await c.post("/api/employees/5555", headers=H, json={"active": False})
        check("unknown employee 404", r.status == 404)

        # ── вақти кории алоҳида
        r = await c.post("/api/employees/1001", headers=H, json={"work_time": "14:00", "work_days": [0, 1, 2, 3, 4]})
        j = await r.json()
        check("personal work time saved", r.status == 200 and j["employee"]["schedule"]["time"] == "14:00"
              and j["employee"]["schedule"]["days"] == [0, 1, 2, 3, 4] and j["employee"]["schedule"]["custom"])
        r = await c.post("/api/employees/1001", headers=H, json={"work_time": "25:00"})
        check("personal work time validated", r.status == 400)
        r = await c.post("/api/employees/1001", headers=H, json={"work_days": []})
        check("personal work days need one day", r.status == 400)
        r = await c.get("/api/work-schedule", headers=H)
        check("schedule reports custom count", (await r.json())["custom_count"] == 1)
        emps = await (await c.get("/api/employees", headers=H)).json()
        e1001 = next(e for e in emps if e["user_id"] == 1001)
        check("employees list carries schedule", e1001["schedule"]["time"] == "14:00" and e1001["work_days"] == [0, 1, 2, 3, 4])
        mon = await (await c.get("/api/attendance/month", headers=H)).json()
        check("month employee start", next(e for e in mon["employees"] if e["user_id"] == 1001)["start"] == "14:00")
        w = await (await c.get("/api/workers/1001", headers=H)).json()
        check("worker detail carries schedule", w["schedule"]["custom"] and w["work_time"] == "14:00")
        r = await c.get(f"/api/attendance.csv?token={tok}")
        check("CSV has own start column", "Оғози кор" in await r.text())
        r = await c.post("/api/employees/1001", headers=H, json={"work_time": None, "work_days": None})
        check("personal schedule reset", not (await r.json())["employee"]["schedule"]["custom"])

        # ── вақти корӣ
        r = await c.get("/api/work-schedule", headers=H)
        check("work schedule read", (await r.json())["time"] == "08:30")
        r = await c.post("/api/work-schedule", headers=H, json={"time": "08:45", "days": [0, 1, 2, 3, 4], "grace": 15, "report": False})
        j = await r.json()
        check("work schedule saved", r.status == 200 and j["time"] == "08:45" and j["days"] == [0, 1, 2, 3, 4]
              and j["grace"] == 15 and j["report"] is False)
        r = await c.post("/api/work-schedule", headers=H, json={"time": "25:99"})
        check("work schedule validates time", r.status == 400)
        r = await c.post("/api/work-schedule", headers=H, json={"days": []})
        check("work schedule needs a day", r.status == 400)
        r = await c.post("/api/work-schedule", headers=H, json={"time": ""})
        check("work schedule can be cleared", (await r.json())["enabled"] is False)
        await c.post("/api/work-schedule", headers=H, json={"time": "08:30", "days": [0, 1, 2, 3, 4, 5], "grace": 10, "report": True})

        # ── давомот
        r = await c.get("/api/attendance/day", headers=H)
        day = await r.json()
        check("attendance today", r.status == 200 and day["date"] == today and day["summary"]["total"] >= 6)
        r = await c.get("/api/attendance/month", headers=H)
        mon = await r.json()
        check("attendance month 5→4", r.status == 200 and mon["period"]["start"].endswith("-05")
              and mon["period"]["end"].endswith("-04") and mon["employees"])
        r = await c.get(f"/api/attendance/month?period={mon['period']['prev']}", headers=H)
        prev = await r.json()
        check("previous work month", prev["period"]["key"] == mon["period"]["prev"] and prev["period"]["next"] == mon["period"]["key"])
        r = await c.get("/api/attendance/month?period=2026-13", headers=H)
        check("bad period rejected", r.status == 400)
        r = await c.get("/api/attendance/month?user_id=1001", headers=H)
        check("month for one employee", [e["user_id"] for e in (await r.json())["employees"]] == [1001])
        r = await c.get("/api/attendance", headers=H)
        check("legacy /api/attendance", r.status == 200 and (await r.json())["period"]["start"].endswith("-05"))

        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        r = await c.post("/api/attendance", headers=H, json={"user_id": 1000, "date": yesterday, "status": "present", "time": "09:12"})
        j = await r.json()
        check("admin sets present (late)", r.status == 200 and j["cell"]["s"] == "late" and j["cell"]["t"] == "09:12")
        r = await c.post("/api/attendance", headers=H, json={"user_id": 1000, "date": yesterday, "status": "absent", "reason": "Бемор", "eta": "пагоҳ"})
        j = await r.json()
        check("admin sets absent", j["cell"]["s"] == "absent" and j["cell"]["reason"] == "Бемор")
        future = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        r = await c.post("/api/attendance", headers=H, json={"user_id": 1001, "date": future, "status": "present"})
        check("future present refused", r.status == 400)
        r = await c.post("/api/attendance", headers=H, json={"user_id": 1001, "date": future, "status": "leave", "reason": "Рухсатӣ"})
        leave = await r.json()
        check("future leave allowed", r.status == 200 and leave["cell"]["s"] == "leave")
        r = await c.delete(f"/api/attendance/{leave['cell']['id']}", headers=H)
        check("delete attendance record", r.status == 200 and db.get_attendance(leave["cell"]["id"]) is None)
        r = await c.delete("/api/attendance/999999", headers=H)
        check("delete missing record 404", r.status == 404)
        r = await c.post("/api/attendance", headers=H, json={"user_id": 1000, "date": yesterday, "status": "bogus"})
        check("bad status rejected", r.status == 400)

        r = await c.post("/api/days-off", headers=H, json={"date": future, "off": True, "title": "Наврӯз"})
        check("day off set", r.status == 200 and db.get_days_off(future, future) == {future: "Наврӯз"})
        r = await c.post("/api/days-off", headers=H, json={"date": future, "off": False})
        check("day off removed", db.get_days_off(future, future) == {})

        r = await c.get(f"/api/attendance.csv?token={tok}")
        body = await r.text()
        check("attendance CSV (matrix + list)", r.status == 200 and "Корманд" in body and "Сари вақт" in body
              and "Шартҳо" in body and body.startswith("﻿"))

        r = await c.get("/api/export.csv?type=absent", headers=H)
        body = await r.text()
        check("csv export filtered", r.status == 200 and "Намеояд" in body and "Дер мекунад" not in body)
        r = await c.get(f"/api/export.csv?token={tok}")
        check("csv export via ?token=", r.status == 200)
        r = await c.get(f"/api/backup.db?token={tok}")
        raw = await r.read()
        check("db backup download", r.status == 200 and raw[:15] == b"SQLite format 3")

        # ── нест кардан (бе рамз)
        first = (await (await c.get("/api/requests?limit=3", headers=H)).json())["items"]
        r = await c.delete(f"/api/requests/{first[0]['id']}", headers=H)
        check("delete one", r.status == 200 and db.get_request(first[0]["id"]) is None)
        r = await c.post("/api/requests/delete", headers=H, json={"ids": [first[1]["id"], first[2]["id"]]})
        check("delete selected (2)", (await r.json())["deleted"] == 2)
        many = [x["id"] for x in (await (await c.get("/api/requests?limit=30", headers=H)).json())["items"]]
        r = await c.post("/api/requests/delete", headers=H, json={"ids": many})
        check("delete many without password", r.status == 200)
        r = await c.post("/api/requests/delete", headers=H, json={"filters": {"type": "absent"}})
        j = await r.json()
        check("delete by filter", r.status == 200 and j["deleted"] > 0 and j["backup"])
        cnt = (await (await c.get("/api/requests?type=absent", headers=H)).json())["total"]
        check("filtered really gone", cnt == 0)
        r = await c.post("/api/workers/1007/delete", headers=H, json={})
        check("delete worker (no password)", r.status == 200 and db.get_worker_detail(1007) is None
              and db.get_employee(1007) is None)

        # ── иваз кардани логин/рамз: танҳо логини нав + рамзи нав × 2
        r = await c.post("/api/account", headers=H, json={"new_login": "admin", "new_password": "Secret123", "new_password_confirm": "different"})
        check("account change requires repeated password", r.status == 400)
        r = await c.post("/api/account", headers=H, json={"new_login": "admin", "new_password": "12345", "new_password_confirm": "12345"})
        check("account weak password rejected", r.status == 400)
        r = await c.post("/api/account", headers=H, json={"new_login": "admin", "new_password": "Secret123", "new_password_confirm": "Secret123"})
        j = await r.json()
        check("account change ok (no current password needed)", r.status == 200 and j["token"])
        r = await c.get("/api/overview", headers=H)
        check("old token invalidated after change", r.status == 401)
        H = {"Authorization": f"Bearer {j['token']}"}
        check("new token works", (await c.get("/api/overview", headers=H)).status == 200)
        r = await c.post("/api/login", json={"login": "softclub", "password": "8520"})
        check("old credentials rejected", r.status == 401)
        r = await c.post("/api/login", json={"login": "admin", "password": "Secret123"})
        check("new credentials work", r.status == 200)
        H = {"Authorization": f"Bearer {(await r.json())['token']}"}
        acc = await (await c.get("/api/account", headers=H)).json()
        check("account info", acc["login"] == "admin" and acc["source"] == "panel")

        # ── тозакунӣ (бе калимаи тасдиқ)
        old = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        r = await c.post("/api/wipe", headers=H, json={"before": old})
        rem = (await (await c.get("/api/requests?limit=500", headers=H)).json())["items"]
        m = await (await c.get("/api/attendance/stats", headers=H)).json()
        check("wipe before date (requests + attendance)", r.status == 200
              and all(x["created_at"][:10] > old for x in rem)
              and all(d["date"] > old for d in m["daily"] if any(d[k] for k in ("on_time", "late", "absent", "leave", "pending"))))
        r = await c.post("/api/wipe", headers=H, json={"scope": "all"})
        a = await (await c.get("/api/analytics", headers=H)).json()
        check("wipe all", r.status == 200 and a["summary"]["total"] == 0 and a["daily"] == []
              and a["attendance"]["summary"]["days"] == 0)
        check("settings survive wipe", db.get_setting("admin_login") == "admin" and db.get_schedule()["time"] == "08:30")
        b = await (await c.get("/api/backups", headers=H)).json()
        check("auto backups created", len(b["items"]) >= 3)
        o = await (await c.get("/api/overview", headers=H)).json()
        check("overview on empty db", o["requests"]["total"] == 0 and o["today"]["summary"]["total"] == 0)
        r = await c.get("/api/health")
        h = await r.json()
        check("health", r.status == 200 and h["ok"] and h["version"] == cfg.VERSION and "conflict" in h["polling"])


async def serve():
    from aiohttp import web
    admin_server.set_bot(FakeTgBot())
    app = admin_server.build_app()

    async def dev_login(request):                  # танҳо барои скриншотҳои санҷишӣ
        tok = admin_server._make_jwt({"user": "softclub", "role": "admin"})
        view = request.query.get("view", "home")
        theme = request.query.get("theme", "light")
        return web.Response(content_type="text/html", text=(
            f"<script>localStorage.setItem('sc_token','{tok}');localStorage.setItem('sc_view','{view}');"
            f"localStorage.setItem('sc_theme','{theme}');location.replace('/#{view}');</script>"))
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
