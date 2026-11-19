"""
Реҷаи «танҳо дархостҳо» (ATTENDANCE хомӯш — пешфарзи продакшн, қарори роҳбарият 19.11.2026):
бот дархостро ба роҳбарият мебарад ва ҷавобро меорад; давомот, «Ман омадам / Ман рафтам»,
«Реҷаи кори ман» ва Google Sheet нестанд — ҳозириро админ дар ҷадвал дастӣ мегузорад.

    python tests/test_requests_mode.py
"""
import asyncio
import os
import sys
import tempfile
from datetime import datetime
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TMP = tempfile.mkdtemp()
os.environ.pop("ATTENDANCE", None)
os.environ.update({
    "BOT_TOKEN": "123456:TEST", "DB_PATH": os.path.join(TMP, "r.db"),
    "LOG_PATH": os.path.join(TMP, "r.log"), "GROUP_ID": "-100555", "BACKUP_DIR": os.path.join(TMP, "bk"),
    "GSHEET_KEY_FILE": os.path.join(TMP, "key.json"),
})
with open(os.path.join(TMP, "key.json"), "w", encoding="utf-8") as fh:    # калид ҳаст — вале истифода намешавад
    fh.write("{}")
sys.path.insert(0, ROOT)

import logging                                   # noqa: E402
logging.disable(logging.CRITICAL)

import config as cfg                             # noqa: E402
import database as db                            # noqa: E402
import handlers                                  # noqa: E402
from telebot import types                        # noqa: E402
from telebot.async_telebot import AsyncTeleBot   # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))


CLOCK = {"now": datetime(2026, 11, 19, 9, 0)}
cfg.now = lambda: CLOCK["now"]


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

    async def get_chat_member(self, chat_id, user_id):
        return SimpleNamespace(status="member")

    def take(self):
        out, self.calls = self.calls, []
        return out


bot = FakeBot()
handlers.register_handlers(bot)
_n = {"n": 0}


def _id():
    _n["n"] += 1
    return _n["n"]


async def say(uid, text):
    n = _id()
    await bot.process_new_updates([types.Update.de_json({"update_id": n, "message": {
        "message_id": n, "date": 0, "chat": {"id": uid, "type": "private"},
        "from": {"id": uid, "is_bot": False, "first_name": "Ali"}, "text": text}})])
    return bot.take()


async def press(uid, data):
    n = _id()
    await bot.process_new_updates([types.Update.de_json({"update_id": n, "callback_query": {
        "id": str(n), "from": {"id": uid, "is_bot": False, "first_name": "Ali"}, "chat_instance": "x",
        "data": data, "message": {"message_id": 700, "date": 0, "chat": {"id": uid, "type": "private"},
                                  "text": "q"}}})])
    return bot.take()


def callbacks(markup):
    out = []
    for row in (markup.keyboard if markup else []):
        for b in row:
            out.append(b.get("callback_data") if isinstance(b, dict) else getattr(b, "callback_data", None))
    return out


def labels(markup):
    out = []
    for row in (markup.keyboard if markup else []):
        for b in row:
            out.append(b.get("text") if isinstance(b, dict) else getattr(b, "text", None))
    return out


U = 77


async def run():
    db.init_db()
    check("attendance is off by default (production)", cfg.ATTENDANCE is False)

    # ── клавиатура ва /start ───────────────────────────────────────────
    kb = labels(handlers._main_reply_kb())
    check("keyboard: only requests", "📝 Дархости нав" in kb and "📋 Дархостҳои ман" in kb
          and handlers.ARRIVE_BUTTON not in kb and handlers.LEFT_BUTTON not in kb and handlers.PLAN_BUTTON not in kb, kb)
    calls = await say(U, "/start")
    sent = [c for c in calls if c[0] == "send"]
    inline = [cb for c in sent for cb in callbacks(c[3]) if cb]
    check("/start offers the four request types", all(f"t:{k}" in inline for k in handlers.TYPE_ORDER), inline)
    check("/start has no arrive/leave/plan buttons", not any(cb.startswith("me:") for cb in inline))
    check("/start has no attendance status line", not any("Имрӯз омадед" in (c[2] or "") or "қайд нашудааст" in (c[2] or "")
                                                          for c in sent))
    help_text = handlers._help_text()
    check("help explains only requests", "Дархости нав" in help_text and "Ба кор омадед" not in help_text
          and "/reja" not in help_text)

    # ── тугмаҳои кӯҳна дар телефонҳо ───────────────────────────────────
    for old in (handlers.ARRIVE_BUTTON, handlers.LEFT_BUTTON, handlers.PLAN_BUTTON, "/reja"):
        calls = await say(U, old)
        sent = [c for c in calls if c[0] == "send"]
        new_kb = next((labels(c[3]) for c in sent if c[3] is not None and labels(c[3]) and "📝 Дархости нав" in labels(c[3])), [])
        check(f"old «{old}» → explained, new keyboard sent", any("дигар кор намекунад" in (c[2] or "") for c in sent)
              and new_kb and handlers.ARRIVE_BUTTON not in new_kb)
    check("old buttons record nothing", db.get_today_attendance(U) is None)
    calls = await press(U, "me:in")
    check("old inline «Ман омадам» does nothing", db.get_today_attendance(U) is None
          and any("дигар кор намекунад" in (c[2] or "") for c in calls))
    calls = await press(U, "att:y:1")
    check("old «Ба кор омадед?» buttons are switched off", any(c[0] == "answer" and "фаъол нест" in (c[2] or "") for c in calls))

    # ── саволи ҳаррӯза нест, ҳатто агар вақти кор гузошта бошад ─────────
    db.set_schedule(time="09:00", days=[0, 1, 2, 3, 4, 5])
    CLOCK["now"] = datetime(2026, 11, 19, 9, 5)
    check("schedule never enables the daily question", db.get_schedule()["enabled"] is False)
    check("nobody is asked", db.create_due_attendance() == [])
    check("no daily report to managers", db.daily_report_due() is None)
    await handlers.process_work_attendance(bot)
    check("attendance job sends nothing", not bot.take())

    # ── дархост ба роҳбарият кор мекунад ───────────────────────────────
    await press(U, "t:late")
    await press(U, "r:0")
    await press(U, "m:20")
    calls = await press(U, "f:send")
    group = [c for c in calls if c[0] == "send" and c[1] == cfg.GROUP_ID]
    check("request reaches the managers' group", len(group) == 1 and "Дер мекунад" in (group[0][2] or ""))
    check("…with approve / reject buttons", any(cb and cb.startswith("d:a:") for cb in callbacks(group[0][3])))
    check("request saved", db.get_user_requests(U, 1)[0]["type"] == "late")
    check("no attendance record from the request", db.get_today_attendance(U) is None)


asyncio.run(run())
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
