"""
Санҷиши пурраи давомот: бот → база → ҳисобот (бе Telegram-и воқеӣ).

Навсозиҳои Telegram (callback/матн) аз роҳи диспетчери худи telebot мегузаранд,
бинобар ин тартиби handler-ҳо (масалан, бархӯрди префиксҳо) ҳам санҷида мешавад.

    python tests/test_attendance.py
"""
import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TMP = tempfile.mkdtemp()
os.environ.update({
    "BOT_TOKEN": "123456:TEST", "DB_PATH": os.path.join(TMP, "a.db"),
    "LOG_PATH": os.path.join(TMP, "a.log"), "GROUP_ID": "-100555", "BACKUP_DIR": os.path.join(TMP, "bk"),
})
sys.path.insert(0, ROOT)

import logging                                   # noqa: E402
logging.disable(logging.CRITICAL)

import config as cfg                             # noqa: E402
import database as db                            # noqa: E402
import handlers                                  # noqa: E402
from telebot import types                        # noqa: E402
from telebot.async_telebot import AsyncTeleBot   # noqa: E402

GROUP = cfg.GROUP_ID
results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))


# ── вақти идорашаванда ────────────────────────────────────────────────────
CLOCK = {"now": datetime(2026, 9, 28, 8, 0)}      # 28.09.2026 — душанбе
cfg.now = lambda: CLOCK["now"]


def at(day: str, hm: str):
    CLOCK["now"] = datetime.strptime(f"{day} {hm}", "%Y-%m-%d %H:%M")


# ── боти сохта: ҳамаи даъватҳо сабт мешаванд ─────────────────────────────
class FakeBot(AsyncTeleBot):
    def __init__(self):
        super().__init__("123456:TEST", parse_mode="HTML")
        self.calls = []
        self._mid = 1000

    def _msg(self):
        self._mid += 1
        return SimpleNamespace(message_id=self._mid)

    async def send_message(self, chat_id, text, **kw):
        self.calls.append(("send", chat_id, text, kw.get("reply_markup")))
        return self._msg()

    async def edit_message_text(self, text, chat_id=None, message_id=None, **kw):
        self.calls.append(("edit", chat_id, text, kw.get("reply_markup")))
        return True

    async def edit_message_reply_markup(self, chat_id=None, message_id=None, reply_markup=None, **kw):
        self.calls.append(("markup", chat_id, None, reply_markup))
        return True

    async def answer_callback_query(self, callback_query_id, text=None, **kw):
        self.calls.append(("answer", None, text, None))
        return True

    async def send_document(self, chat_id, document, **kw):
        self.calls.append(("doc", chat_id, kw.get("caption"), None))
        return self._msg()

    def take(self):
        out, self.calls = self.calls, []
        return out


bot = FakeBot()
handlers.register_handlers(bot)
_uid = {"n": 0}


def _next():
    _uid["n"] += 1
    return _uid["n"]


def user(uid, name="Ali"):
    return {"id": uid, "is_bot": False, "first_name": name}


async def press(uid, data, msg_id=500):
    n = _next()
    upd = types.Update.de_json({"update_id": n, "callback_query": {
        "id": str(n), "from": user(uid), "chat_instance": "x", "data": data,
        "message": {"message_id": msg_id, "date": 0, "chat": {"id": uid, "type": "private"}, "text": "q"}}})
    await bot.process_new_updates([upd])
    return bot.take()


async def say(uid, text, name="Ali"):
    n = _next()
    upd = types.Update.de_json({"update_id": n, "message": {
        "message_id": n, "date": 0, "chat": {"id": uid, "type": "private"}, "from": user(uid, name), "text": text}})
    await bot.process_new_updates([upd])
    return bot.take()


def texts(calls, kind=None, chat=None):
    return [c[2] or "" for c in calls if (kind is None or c[0] == kind) and (chat is None or c[1] == chat)]


def buttons(markup):
    if not markup:
        return []
    return [b.callback_data for row in markup.keyboard for b in row]


A, B, C, D, E = 11, 22, 33, 44, 55


async def run():
    db.init_db()
    for uid, name in ((A, "Алӣ Раҳимов"), (B, "Бону Каримова"), (C, "Сино Азизов"),
                      (D, "Роҳбар (@boss)"), (E, "Эраҷ Назаров")):
        db.touch_employee(uid, name, None)
    db.update_employee(D, active=False)                       # роҳбар савол намегирад

    # ── ҷадвал ────────────────────────────────────────────────────────────
    check("schedule off by default", not db.get_schedule()["enabled"])
    at("2026-09-28", "08:40")
    check("nothing when schedule off", db.create_due_attendance() == [])
    db.set_schedule(time="08:30", days=[0, 1, 2, 3, 4, 5], grace=10, report=True)
    sch = db.get_schedule()
    check("schedule saved", sch["time"] == "08:30" and sch["days"] == [0, 1, 2, 3, 4, 5] and sch["grace"] == 10)

    at("2026-09-28", "08:25")
    check("no prompts before start time", db.create_due_attendance() == [])

    # ── саволи субҳ ───────────────────────────────────────────────────────
    at("2026-09-28", "08:31")
    await handlers.process_work_attendance(bot)
    calls = bot.take()
    sent = [c for c in calls if c[0] == "send"]
    check("prompt sent to every active employee (not inactive)", sorted(c[1] for c in sent) == [A, B, C, E],
          [c[1] for c in sent])
    check("prompt has att: buttons", all(buttons(c[3])[0].startswith("att:y:") for c in sent))
    check("prompt text greets and asks", "Шумо ба кор омадед?" in sent[0][2] and "08:30" in sent[0][2])
    await handlers.process_work_attendance(bot)
    check("second tick sends nothing (no duplicates)", not bot.take())
    rec_a = db.get_today_attendance(A)
    rec_b = db.get_today_attendance(B)
    rec_c = db.get_today_attendance(C)
    check("inactive employee has no record", db.get_today_attendance(D) is None)
    check("prompt msg_id stored", rec_a["msg_id"] and rec_a["prompted_at"])

    # ── «Омадам» (бархӯрди префикси w: санҷида мешавад) ───────────────────
    at("2026-09-28", "08:36")
    calls = await press(A, f"att:y:{rec_a['id']}")
    rec = db.get_attendance(rec_a["id"])
    check("'Омадам' → present with time", rec["status"] == "present" and rec["arrived_at"].endswith("08:36:00"))
    check("employee sees confirmation", any("08:36" in t for t in texts(calls, "edit")))
    check("no group spam for on-time arrival", not texts(calls, "send", GROUP))
    calls = await press(A, f"att:y:{rec_a['id']}")
    check("double press is harmless", db.get_attendance(rec_a["id"])["arrived_at"].endswith("08:36:00"))
    check("state on_time within grace", db.att_state(db.get_attendance(rec_a["id"]), 10) == "on_time")

    # ── «Наомадам» → сабаб (тугма) → вақт (тугма) ─────────────────────────
    calls = await press(B, f"att:n:{rec_b['id']}")
    check("'Наомадам' asks reason with buttons", any(b.startswith("atr:") for c in calls for b in buttons(c[3])))
    calls = await press(B, "atr:1")
    check("reason chosen → asks ETA", any(b.startswith("ate:") for c in calls for b in buttons(c[3])))
    calls = await press(B, "ate:60")
    rec = db.get_attendance(rec_b["id"])
    check("absent saved with reason & eta", rec["status"] == "absent" and rec["reason"] == "Бемор ҳастам"
          and "09:36" in rec["eta"], rec)
    check("group informed about absence", any("Бону" in t and "Бемор" in t for t in texts(calls, "send", GROUP)))
    check("employee gets 'Ман омадам' button", any("att:arr:" in b for c in calls for b in buttons(c[3])))

    # ── баъдтар омад ──────────────────────────────────────────────────────
    at("2026-09-28", "09:50")
    calls = await press(B, f"att:arr:{rec_b['id']}")
    rec = db.get_attendance(rec_b["id"])
    check("late arrival after absence → present", rec["status"] == "present" and rec["arrived_at"].endswith("09:50:00"))
    check("late arrival reason kept", rec["reason"] == "Бемор ҳастам")
    check("group told about arrival with lateness", any("ба кор омад" in t and "дер" in t for t in texts(calls, "send", GROUP)))
    check("state late", db.att_state(rec, 10) == "late")

    # ── матни худӣ ────────────────────────────────────────────────────────
    rec_e = db.get_today_attendance(E)
    await press(E, f"att:n:{rec_e['id']}")
    calls = await say(E, "Мошинам вайрон шуд")
    check("typed reason accepted → asks ETA", any(b.startswith("ate:") for c in calls for b in buttons(c[3])))
    calls = await say(E, "соати 11")
    rec = db.get_attendance(rec_e["id"])
    check("typed eta saved", rec["status"] == "absent" and rec["reason"] == "Мошинам вайрон шуд" and rec["eta"] == "соати 11")

    # ── «Бозгашт» ────────────────────────────────────────────────────────
    calls = await press(C, f"att:n:{rec_c['id']}")
    calls = await press(C, f"att:back:{rec_c['id']}")
    check("back returns to the question", any(f"att:y:{rec_c['id']}" in buttons(c[3]) for c in calls))
    check("back keeps pending", db.get_attendance(rec_c["id"])["status"] == "pending")

    # ── бегонагон ────────────────────────────────────────────────────────
    calls = await press(A, f"att:y:{rec_c['id']}")
    check("cannot answer someone else's question", db.get_attendance(rec_c["id"])["status"] == "pending"
          and any("барои шумо нест" in (t or "") for t in texts(calls, "answer")))

    # ── ёдоварӣ ──────────────────────────────────────────────────────────
    at("2026-09-28", "08:55")
    await handlers.remind_attendance(bot)
    check("no reminder before ATTENDANCE_REMIND", not bot.take())
    at("2026-09-28", "09:05")
    await handlers.remind_attendance(bot)
    calls = bot.take()
    check("one reminder to the silent one", [c[1] for c in calls if c[0] == "send"] == [C])
    await handlers.remind_attendance(bot)
    check("reminder only once", not bot.take())

    # ── ҳисоботи рӯз ─────────────────────────────────────────────────────
    at("2026-09-28", "09:20")
    await handlers.send_daily_report(bot)
    check("no report before start+60", not bot.take())
    at("2026-09-28", "09:31")
    await handlers.send_daily_report(bot)
    calls = bot.take()
    rep = texts(calls, "send", GROUP)
    check("daily report sent to group", len(rep) == 1 and "Давомоти имрӯз" in rep[0], rep)
    check("report lists late / absent / silent", rep and "Дер омаданд" in rep[0] and "Наомаданд" in rep[0]
          and "Ҷавоб надоданд" in rep[0] and "Сино" in rep[0])
    await handlers.send_daily_report(bot)
    check("report only once per day", not bot.take())

    # ── рӯзи дигар: саволи дирӯза кор намекунад ──────────────────────────
    at("2026-09-29", "08:31")
    calls = await press(C, f"att:y:{rec_c['id']}")
    check("yesterday's question is closed", db.get_attendance(rec_c["id"])["status"] == "pending"
          and any("рӯзи дигар" in (t or "") for t in texts(calls, "answer")))

    # ── дархости «намеоям» пеш аз оғози кор ─────────────────────────────
    at("2026-09-29", "07:50")
    db.set_state(E, {"step": "confirm", "type": "absent", "reason": "Тӯй дорам", "minutes": 0})
    calls = await press(E, "f:send")
    check("request sent to group", any("Тӯй дорам" in t for t in texts(calls, "send", GROUP)))
    rec = db.get_today_attendance(E)
    check("absent request → attendance absent (source=request)", rec and rec["status"] == "absent"
          and rec["source"] == "request" and rec["reason"] == "Тӯй дорам")
    at("2026-09-29", "08:31")
    await handlers.process_work_attendance(bot)
    calls = bot.take()
    check("no morning question for someone who already reported", E not in [c[1] for c in calls if c[0] == "send"])
    check("others still asked", sorted(c[1] for c in calls if c[0] == "send") == [A, B, C])

    # ── дархости «дер мекунам» пас аз савол → санҷиши омадан → «омад» ─────
    at("2026-09-29", "08:35")
    db.set_state(C, {"step": "confirm", "type": "late", "reason": "Роҳбандӣ", "minutes": 20})
    calls = await press(C, "f:send")
    rec = db.get_today_attendance(C)
    check("late request marks today's attendance absent+eta", rec["status"] == "absent" and "08:55" in rec["eta"])
    check("morning question buttons replaced", any("att:arr:" in b for c in calls for b in buttons(c[3])))
    req = db.get_user_requests(C, 1)[0]
    ok, _ = await handlers.apply_decision(bot, req["id"], "accepted", "Роҳбар")
    bot.take()
    at("2026-09-29", "08:56")
    await handlers.process_arrival_checks(bot)
    calls = bot.take()
    check_id = db.get_active_check_for_user(C)["id"]
    calls = await press(C, f"a:y:{check_id}")
    rec = db.get_today_attendance(C)
    check("arrival check 'расидам' → attendance present", rec["status"] == "present" and rec["arrived_at"].endswith("08:56:00"))

    # ── ёдовариҳои дархост (префикси w:) ҳанӯз кор мекунанд ──────────────
    at("2026-09-29", "10:00")
    db.set_state(A, {"step": "confirm", "type": "leaving_early", "reason": "Кори шахсӣ", "minutes": 30})
    await press(A, "f:send")
    req = db.get_user_requests(A, 1)[0]
    await handlers.apply_decision(bot, req["id"], "accepted", "Роҳбар")
    bot.take()
    at("2026-09-29", "10:28")
    await handlers.send_reminders(bot)
    bot.take()
    calls = await press(A, f"w:y:{req['id']}")
    check("request reminder 'w:y' still handled by request flow", db.get_request(req["id"])["worker_confirmed"] == "yes")

    # ── якшанбе, ид ва тиреза ───────────────────────────────────────────
    at("2026-10-04", "08:40")                                # якшанбе
    check("no prompts on Sunday", db.create_due_attendance() == [])
    db.set_day_off("2026-10-05", True, "Иди санҷишӣ")
    at("2026-10-05", "08:40")
    check("no prompts on a day off", db.create_due_attendance() == [])
    at("2026-10-06", "13:00")                                 # 270 дақ пас аз оғоз
    check("no prompts after ATTENDANCE_WINDOW (bot was down)", db.create_due_attendance() == [])
    at("2026-10-06", "10:00")
    check("prompts inside window after downtime", len(db.create_due_attendance()) == 4)

    # ── ислоҳи дастӣ ────────────────────────────────────────────────────
    cell = db.admin_set_attendance(D, "2026-09-28", "present", clock="08:50")
    check("admin can mark even inactive employee", cell["s"] == "late" and cell["t"] == "08:50" and cell["src"] == "admin")
    cell = db.admin_set_attendance(D, "2026-09-28", "leave", reason="Рухсатии меҳнатӣ")
    check("admin sets leave", cell["s"] == "leave" and cell["t"] == "")
    check("delete record", db.delete_attendance(cell["id"]) and db.get_attendance(cell["id"]) is None)

    # ── моҳи корӣ 5 → 4 ─────────────────────────────────────────────────
    at("2026-10-03", "12:00")
    check("work period on 3 Oct = 5 Sep..4 Oct", db.work_period() == ("2026-09-05", "2026-10-04"))
    at("2026-10-05", "12:00")
    check("work period on 5 Oct = 5 Oct..4 Nov", db.work_period() == ("2026-10-05", "2026-11-04"))
    check("explicit period 2026-12 wraps year", db.work_period("2026-12") == ("2026-12-05", "2027-01-04"))
    at("2026-09-30", "12:00")
    m = db.get_attendance_month()
    check("month has 30 days (5 Sep – 4 Oct)", len(m["days"]) == 30 and m["period"]["key"] == "2026-09")
    check("month next=None for current", m["period"]["next"] is None and m["period"]["prev"] == "2026-08")
    alee = next(e for e in m["employees"] if e["user_id"] == A)
    check("employee summary counts", alee["summary"]["on_time"] >= 1 and alee["summary"]["rate"] is not None)
    sunday = next(d for d in m["days"] if d["date"] == "2026-09-27")
    check("Sunday is not a workday", not sunday["workday"] and sunday["weekend"])
    day = db.get_attendance_day("2026-09-28")
    check("day view summary", day["summary"]["on_time"] == 1 and day["summary"]["late"] == 1
          and day["summary"]["absent"] == 1 and day["summary"]["pending"] == 1, day["summary"])
    stats = db.get_attendance_stats("2026-09-05", "2026-10-04")
    check("stats histogram & workers", sum(stats["hist"]["values"]) == stats["summary"]["present"] and stats["workers"])

    # ── нусхаи ҳаррӯза ─────────────────────────────────────────────────
    await handlers.daily_backup(bot)
    files = os.listdir(cfg.BACKUP_DIR)
    check("daily backup created", any(f.endswith("_daily.db") for f in files), files)
    await handlers.daily_backup(bot)
    check("daily backup once per day", len(os.listdir(cfg.BACKUP_DIR)) == len(files))


asyncio.run(run())
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
