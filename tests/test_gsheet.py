"""
Санҷиши Google Sheet: ҷадвали сохтагии корхона дар хотира (бе интернет ва бе Google).

Сохтори ҷадвал айнан мисли «Oficce Out»: сарлавҳа, «Номи Корманд / Телеграм id / Телефон /
Омадан (брнм) / Рафтан (брнм)», рӯзҳо (ҳар рӯз «Омад» / «Рафт»), «Натиҷа %».

    python tests/test_gsheet.py
"""
import asyncio
import base64
import copy
import hashlib
import json
import os
import random
import re
import sys
import tempfile
from datetime import date, datetime
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TMP = tempfile.mkdtemp()
os.environ.update({
    "BOT_TOKEN": "123456:TEST", "DB_PATH": os.path.join(TMP, "g.db"),
    "LOG_PATH": os.path.join(TMP, "g.log"), "GROUP_ID": "-100555", "BACKUP_DIR": os.path.join(TMP, "bk"),
    "GSHEET_ID": "BOOK", "GSHEET_KEY_FILE": os.path.join(TMP, "key.json"),
})
with open(os.path.join(TMP, "key.json"), "w", encoding="utf-8") as _fh:   # «калид» ҳаст (вале нодуруст)
    _fh.write("{}")
sys.path.insert(0, ROOT)

import logging                                   # noqa: E402
logging.disable(logging.CRITICAL)

import config as cfg                             # noqa: E402
import database as db                            # noqa: E402
import gsheet as gs                              # noqa: E402
import handlers                                  # noqa: E402
from telebot import types                        # noqa: E402
from telebot.async_telebot import AsyncTeleBot   # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))


CLOCK = {"now": datetime(2026, 11, 16, 8, 0)}       # 16.11.2026 — душанбе
cfg.now = lambda: CLOCK["now"]


def at(day: str, hm: str):
    CLOCK["now"] = datetime.strptime(f"{day} {hm}", "%Y-%m-%d %H:%M")


# ══════════════════════════════════════════════════════════════════════════
#  Ҷадвали сохтагӣ (Sheets API дар хотира)
# ══════════════════════════════════════════════════════════════════════════

def _cidx(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


class FakeBook:
    def __init__(self):
        self.sheets = {}
        self.next_id = 500
        self.next_meta = 1
        self.writes = 0
        self.fail = None
        self.locale = "ru_RU"
        self.sep = ";"                 # Google-и ru_RU формулаи бо «,»-ро намефаҳмад → #ERROR!

    def add(self, sid, title, index):
        self.sheets[sid] = {"title": title, "index": index, "cells": {}, "meta": []}
        return self.sheets[sid]

    def by_title(self, title):
        return next(s for s in self.sheets.values() if s["title"] == title)

    def put(self, title, r, c, v=None, f=None, bg=None):
        cell = self.by_title(title)["cells"].setdefault((r, c), {})
        cell.update(v=v, f=f)
        if bg:
            cell["bg"] = bg

    def cell(self, title, r, c):
        return self.by_title(title)["cells"].get((r, c), {})


class FakeClient:
    def __init__(self, book: FakeBook):
        self.book = book

    def _check(self):
        if self.book.fail:
            raise gs.SheetsError(self.book.fail, 503)

    async def meta(self):
        self._check()
        return {"properties": {"locale": self.book.locale},
                "sheets": [{"properties": {"sheetId": sid, "title": s["title"], "index": s["index"],
                                           "hidden": s.get("hidden", False),
                                           "gridProperties": {"rowCount": 1000, "columnCount": 68}},
                            "developerMetadata": s["meta"]} for sid, s in self.book.sheets.items()]}

    @staticmethod
    def _parse(rng):
        m = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", rng)
        return int(m.group(2)) - 1, _cidx(m.group(1)), int(m.group(4)) - 1, _cidx(m.group(3))

    async def values(self, title, rng, render="UNFORMATTED_VALUE"):
        self._check()
        sheet = self.book.by_title(title)
        r1, c1, r2, c2 = self._parse(rng)
        out = []
        for r in range(r1, r2 + 1):
            row = []
            for c in range(c1, c2 + 1):
                cell = sheet["cells"].get((r, c), {})
                v = cell.get("f") if render == "FORMULA" and cell.get("f") else cell.get("v")
                if render == "FORMATTED_VALUE" and cell.get("f"):
                    other = "," if self.book.sep == ";" else ";"
                    v = "#ERROR!" if ("R[0]C" in cell["f"] or other in cell["f"].replace('","', "")) else "50%"
                row.append("" if v is None else v)
            while row and row[-1] == "":
                row.pop()
            out.append(row)
        while out and not out[-1]:
            out.pop()
        return out

    async def grid(self, title, rng, fields):
        sheet = self.book.by_title(title)
        r1, c1, r2, c2 = self._parse(rng)
        rows = []
        for r in range(r1, r2 + 1):
            bg = sheet["cells"].get((r, c1), {}).get("bg")
            rows.append({"values": [{"userEnteredFormat": {"backgroundColor": gs._rgb(bg)} if bg else {}}]})
        return {"sheets": [{"data": [{"rowData": rows}]}]}

    async def batch(self, requests):
        self._check()
        replies = []
        for req in requests:
            (kind, body), = req.items()
            replies.append(getattr(self, "_" + kind)(body) or {})
        return replies

    # ── амалҳо ──
    def _duplicateSheet(self, b):
        src = self.book.sheets[b["sourceSheetId"]]
        sid = self.book.next_id
        self.book.next_id += 1
        for s in self.book.sheets.values():
            if s["index"] >= b["insertSheetIndex"]:
                s["index"] += 1
        new = {"title": b["newSheetName"], "index": b["insertSheetIndex"],
               "cells": copy.deepcopy(src["cells"]), "meta": []}
        for m in src["meta"]:                      # бадтарин ҳолат: Google metadata-ро ҳам нусха мекунад
            new["meta"].append({**m, "metadataId": self.book.next_meta})
            self.book.next_meta += 1
        self.book.sheets[sid] = new
        return {"duplicateSheet": {"properties": {"sheetId": sid, "title": new["title"]}}}

    def _updateCells(self, b):
        rg, fields = b["range"], b["fields"]
        sheet = self.book.sheets[rg["sheetId"]]
        for i, row in enumerate(b["rows"]):
            for j, data in enumerate(row["values"]):
                cell = sheet["cells"].setdefault((rg["startRowIndex"] + i, rg["startColumnIndex"] + j), {})
                if "userEnteredValue" in fields.split(","):
                    uev = data.get("userEnteredValue") or {}
                    cell["f"] = uev.get("formulaValue")
                    cell["v"] = uev.get("numberValue", uev.get("stringValue"))
                fmt = data.get("userEnteredFormat", {})
                if "userEnteredFormat.backgroundColor" in fields:
                    cell["bg"] = gs._hex(fmt.get("backgroundColor")) or None
                if "textFormat.foregroundColor" in fields:
                    cell["fg"] = gs._hex(fmt.get("textFormat", {}).get("foregroundColor")) or None
                    cell["bold"] = fmt.get("textFormat", {}).get("bold")
                self.book.writes += 1

    def _createDeveloperMetadata(self, b):
        md = b["developerMetadata"]
        sheet = self.book.sheets[md["location"]["sheetId"]]
        sheet["meta"].append({"metadataId": self.book.next_meta, "metadataKey": md["metadataKey"],
                              "metadataValue": md["metadataValue"]})
        self.book.next_meta += 1

    def _updateDeveloperMetadata(self, b):
        mid = b["dataFilters"][0]["developerMetadataLookup"]["metadataId"]
        for s in self.book.sheets.values():
            for m in s["meta"]:
                if m["metadataId"] == mid:
                    m["metadataValue"] = b["developerMetadata"]["metadataValue"]

    def _updateSheetProperties(self, b):
        self.book.sheets[b["properties"]["sheetId"]]["title"] = b["properties"]["title"]

    def _deleteSheet(self, b):
        self.book.sheets.pop(b["sheetId"])

    async def close(self):
        pass


BROKEN = ('=IFERROR((IF(AND(R[0]C[-62]<>"",R[0]C[-62]-TIMEVALUE(R[0]C3)<=TIMEVALUE("00:15")),1,0))'
          '/MAX(1,IF(R[0]C[-1]<>"",1,0)),"")')
T = lambda hm: int(hm[:2]) / 24 + int(hm[3:]) / 1440      # noqa: E731

#        ном                  телефон       омадан        рафтан      ранги сатр
STAFF = [("Masafi Begimadov", "988201294", T("10:00"), "20:00", "ebf3fb"),
         ("Hakim Jumaev", "93 103 1413", T("10:00"), "20:00", "ffffff"),
         ("Kabir Ghaffurov", "00 688 0067", "14:00", "20:00", "ebf3fb"),
         ("Gholib Kabirov", "00 216 0010", "09:00", "14:00", "ffffff"),
         ("Sharifzoda Farida ", "988948189", T("09:30"), T("18:30"), "ebf3fb")]
R_MASAFI, R_HAKIM, R_KABIR, R_GHOLIB, R_FARIDA = 4, 5, 6, 7, 8


def book_cell_text(book, title, r, c):
    v = book.cell(title, r, c).get("v")
    return None if v is None else str(v)


def build_book() -> FakeBook:
    book = FakeBook()
    book.add(0, "Лист1", 0)
    t = "Лист1"
    book.put(t, 0, 0, "Ҳузури Кормандон — August 2026")
    book.put(t, 1, 0, "Номи Корманд")
    book.put(t, 2, 1, "Телеграм id")
    book.put(t, 1, 2, "Телефон")
    book.put(t, 1, 3, "Омадан\n(брнм)")
    book.put(t, 1, 4, "Рафтан\n(брнм)")
    book.put(t, 1, 67, "Натиҷа %")
    for d in range(1, 31):
        label = gs.day_label("2026-11", d)
        book.put(t, 1, gs.day_col(d), "4-Чоршабе" if d == 4 else label)       # хатои чопии корхона
    for d in range(1, 32):
        book.put(t, 2, gs.day_col(d), "Омад")
        book.put(t, 2, gs.day_col(d, "out"), "Рафт")
    for i, (name, phone, pin, pout, stripe) in enumerate(STAFF):
        r = 4 + i
        book.put(t, r, 0, name, bg=stripe)
        book.put(t, r, 2, phone)
        book.put(t, r, 3, pin)
        book.put(t, r, 4, pout)
        book.put(t, r, 67, None, f=BROKEN)
    book.put(t, R_HAKIM, gs.day_col(16), T("10:00"))         # навиштаи дастии корхона (16 ноябр)
    book.put(t, R_MASAFI, gs.day_col(2), T("10:00"))
    return book


# ══════════════════════════════════════════════════════════════════════════
#  Бот (барои тугмаи «🚪 Аз кор рафтам»)
# ══════════════════════════════════════════════════════════════════════════

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


def _upd():
    _n["n"] += 1
    return _n["n"]


async def press(uid, data):
    n = _upd()
    await bot.process_new_updates([types.Update.de_json({"update_id": n, "callback_query": {
        "id": str(n), "from": {"id": uid, "is_bot": False, "first_name": "X"}, "chat_instance": "x",
        "data": data, "message": {"message_id": 700, "date": 0, "chat": {"id": uid, "type": "private"},
                                  "text": "q"}}})])
    return bot.take()


async def say(uid, text):
    n = _upd()
    await bot.process_new_updates([types.Update.de_json({"update_id": n, "message": {
        "message_id": n, "date": 0, "chat": {"id": uid, "type": "private"},
        "from": {"id": uid, "is_bot": False, "first_name": "X"}, "text": text}})])
    return bot.take()


def buttons(markup):
    return [b.callback_data for row in (markup.keyboard if markup else []) for b in row]


# ══════════════════════════════════════════════════════════════════════════
#  RSA (калиди санҷишӣ бо Python-и тоза)
# ══════════════════════════════════════════════════════════════════════════

def _is_prime(n, rnd):
    if n < 4:
        return n in (2, 3)
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d, s = d // 2, s + 1
    for _ in range(16):
        x = pow(rnd.randrange(2, n - 2), d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(bits, rnd):
    while True:
        n = rnd.getrandbits(bits) | (1 << (bits - 1)) | 1
        if _is_prime(n, rnd):
            return n


def _der_len(n):
    if n < 128:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _tlv(tag, body):
    return bytes([tag]) + _der_len(len(body)) + body


def _der_int(x):
    return _tlv(0x02, x.to_bytes(x.bit_length() // 8 + 1, "big"))


def make_pem(rnd):
    e = 65537
    while True:
        p, q = _prime(512, rnd), _prime(512, rnd)
        phi = (p - 1) * (q - 1)
        if p != q and phi % e:
            break
    n, d = p * q, pow(e, -1, phi)
    pkcs1 = _tlv(0x30, b"".join(_der_int(x) for x in (0, n, e, d, p, q, d % (p - 1), d % (q - 1), pow(q, -1, p))))
    algo = _tlv(0x30, bytes.fromhex("06092a864886f70d0101010500"))
    pkcs8 = _tlv(0x30, _der_int(0) + algo + _tlv(0x04, pkcs1))
    b64 = base64.b64encode(pkcs8).decode()
    pem = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(b64[i:i + 64] for i in range(0, len(b64), 64)) \
          + "\n-----END PRIVATE KEY-----\n"
    return pem, n, e


# ══════════════════════════════════════════════════════════════════════════
#  Санҷишҳо
# ══════════════════════════════════════════════════════════════════════════

K, H, F, A, G = 101, 102, 103, 104, 105


async def run():
    db.init_db()
    for uid, name in ((K, "Кабир Ғафуров (@kabir_0067)"), (H, "Hakim Jumaev (@hakim)"),
                      (F, "Фарида Шарифзода"), (A, "Алӣ Валиев"), (G, "Gholib")):
        db.touch_employee(uid, name, None)
    db.set_schedule(time="09:00", days=[0, 1, 2, 3, 4, 5], grace=10, report=False)

    # ── ёрдамчиҳо ──────────────────────────────────────────────────────
    check("column names", gs.col_name(0) == "A" and gs.col_name(67) == "BP" and gs.col_name(5) == "F")
    check("day columns", gs.day_col(1) == 5 and gs.day_col(1, "out") == 6 and gs.day_col(31) == 65)
    check("sheet clock from serial", gs.sheet_clock(0.4166666666666667) == "10:00"
          and gs.sheet_clock(0.3958333333333333) == "09:30")
    check("sheet clock from text", gs.sheet_clock("9:30") == "09:30" and gs.sheet_clock("14:00:00") == "14:00"
          and gs.sheet_clock("Наомад") is None)
    check("telegram id parsing", gs.parse_tg("6075185878") == 6075185878 and gs.parse_tg(6075185878.0) == 6075185878
          and gs.parse_tg("") is None and gs.parse_tg("abc") is None)
    check("title keeps the company prefix",
          gs.title_text("Ҳузури Кормандон — August 2026", "2026-11") == "Ҳузури Кормандон — November 2026")
    check("day labels", gs.day_label("2026-11", 1) == "1-Якшанбе" and gs.day_label("2026-12", 1) == "1-Сешанбе")
    f5 = gs.result_formula(5)
    check("result formula is A1 (not R1C1) and uses D/E", "R[0]C" not in f5 and "$D5" in f5 and "$E5" in f5
          and "F5:BO5" in f5 and f5.startswith("=IF($D5"))
    s_k = gs.name_score("Кабир Ғафуров (@kabir_0067)", "Kabir Ghaffurov")
    check("name match: Cyrillic ↔ Latin", s_k >= 0.88, s_k)
    check("name match: order swapped", gs.name_score("Фарида Шарифзода", "Sharifzoda Farida ") >= 0.88)
    check("name match: different people are far",
          gs.name_score("Кабир Ғафуров", "Gholib Kabirov") < 0.7, gs.name_score("Кабир Ғафуров", "Gholib Kabirov"))
    check("name match: first name only is not enough", gs.name_score("Gholib", "Gholib Kabirov") < 0.88)

    # ── RSA / JWT ──────────────────────────────────────────────────────
    pem, n, e = make_pem(random.Random(42))
    key = gs.RSAKey(pem)
    sig = key.sign(b"hello")
    em = pow(int.from_bytes(sig, "big"), e, n).to_bytes(key.size, "big")
    check("RSA PKCS#8 parsed", key.n == n and key.e == e)
    check("RS256 signature verifies", em.startswith(b"\x00\x01\xff") and em.endswith(hashlib.sha256(b"hello").digest()))
    creds = gs.Credentials({"type": "service_account", "private_key": pem, "client_email": "bot@x.iam",
                            "token_uri": "https://oauth2.googleapis.com/token", "private_key_id": "k1"})
    jwt = creds.assertion().split(".")
    claims = json.loads(base64.urlsafe_b64decode(jwt[1] + "=" * (-len(jwt[1]) % 4)))
    check("JWT claims", claims["iss"] == "bot@x.iam" and claims["scope"].endswith("/spreadsheets")
          and claims["exp"] - claims["iat"] == 3600)
    check("403 explains what to share", "bot@x.iam" in gs._error_text(403, "{}", "bot@x.iam")
          and "Editor" in gs._error_text(403, "{}", "bot@x.iam"))

    # ── пешфарз: танҳо аз рӯи «Телеграм id» (номҳои Telegram ғайрирасмӣ) ──
    at("2026-11-16", "07:00")
    book0 = build_book()
    s0 = gs.Syncer(FakeClient(book0), "BOOK0", "bot@x.iam")
    await s0.sync()
    check("default: no name-based linking", all(book0.cell("November 2026", r, 1).get("v") is None for r in range(4, 9)))
    book0.put("November 2026", R_HAKIM, 1, float(H))          # корхона ID-ро дастӣ (ҳамчун рақам) навишт
    book0.put("November 2026", R_FARIDA, 1, f" {F} ")          # ё ҳамчун матн бо фосила
    await s0.sync()
    check("typed Telegram id links the row", db.emp_schedule(db.get_employee(H), db.get_schedule())["time"] == "10:00"
          and db.emp_schedule(db.get_employee(F), db.get_schedule())["time"] == "09:30")
    check("official sheet name becomes the display name",
          db.get_employee(H)["display"] == "Hakim Jumaev" and db.get_employee(F)["display"] == "Sharifzoda Farida")
    check("Telegram name kept separately", db.get_employee(F)["name"] == "Фарида Шарифзода")
    names = {e["user_id"]: e for e in db.list_employees()}
    check("panel lists the official name", names[F]["alias"] == "Sharifzoda Farida")
    db.update_employee(F, alias="Фарида (менеҷер)")
    check("name set in the panel still wins", db.get_employee(F)["display"] == "Фарида (менеҷер)")
    db.update_employee(F, alias="")
    db.sync_sheet_plans({})                                    # ҷадвали санҷишии аввал дигар нест
    db.set_settings({"gsheet_autolink": "1"})                  # барои санҷишҳои поён

    # ── синхронизатсияи аввал: «Лист1» → November 2026 ────────────────
    book = build_book()
    sync = gs.Syncer(FakeClient(book), "BOOK", "bot@x.iam")
    gs._SYNCER = sync
    at("2026-11-16", "08:00")
    await sync.sync()
    nov = book.sheets[0]
    check("existing sheet adopted (not copied)", len(book.sheets) == 1)
    check("tab tagged as 2026-11", [m["metadataValue"] for m in nov["meta"]] == ["2026-11"])
    check("tab renamed to the month", nov["title"] == "November 2026")
    check("title row fixed", book.cell("November 2026", 0, 0)["v"] == "Ҳузури Кормандон — November 2026")
    check("day headers untouched (already November)", book.cell("November 2026", 1, gs.day_col(4))["v"] == "4-Чоршабе")
    check("broken «Натиҷа %» formulas replaced",
          all(book.cell("November 2026", r, 67)["f"] == gs.result_formula(r + 1, ";") for r in range(4, 9)))
    tg = lambda r: book.cell("November 2026", r, 1).get("v")           # noqa: E731
    check("autolink Cyrillic Telegram name → row", tg(R_KABIR) == str(K), tg(R_KABIR))
    check("autolink exact name", tg(R_HAKIM) == str(H))
    check("autolink swapped order", tg(R_FARIDA) == str(F))
    check("no autolink for first-name-only / strangers", tg(R_GHOLIB) is None and tg(R_MASAFI) is None)
    check("locale-aware separator chosen («;» for ru_RU)", sync._sep == ";")
    check("sync start date remembered", db.get_setting("gsheet_since:BOOK") == "2026-11-16")
    emp_k = db.get_employee(K)
    sch_k = db.emp_schedule(emp_k, db.get_schedule())
    check("planned time from sheet (14:00) → bot schedule", sch_k["time"] == "14:00" and sch_k["source"] == "sheet")
    check("planned leave stored", sch_k["sheet_leave"] == "20:00")
    check("serial time in sheet works too", db.emp_schedule(db.get_employee(H), db.get_schedule())["time"] == "10:00")
    check("unlinked keeps the global time", db.emp_schedule(db.get_employee(A), db.get_schedule())["time"] == "09:00")
    check("first sync writes no attendance cells", gs.STATE["last_writes"] == 0)

    # ── бот мепурсад дар вақти ҷадвал ────────────────────────────────
    at("2026-11-16", "09:01")
    due = {r["user_id"] for r in db.create_due_attendance()}
    check("not in the sheet → not asked; sheet people wait for their own time",
          A not in due and H not in due and K not in due, due)
    at("2026-11-16", "10:01")
    due = {r["user_id"]: r for r in db.create_due_attendance()}
    check("Hakim asked at his 10:00", H in due and due[H]["scheduled_at"] == "2026-11-16 10:00:00")
    check("Farida asked at her 09:30", db.get_today_attendance(F)["scheduled_at"] == "2026-11-16 09:30:00")
    check("attendance uses the official name", db.get_today_attendance(F)["name"] == "Sharifzoda Farida")
    at("2026-11-16", "10:07")
    db.set_attendance_present(db.get_today_attendance(H)["id"])
    db.set_attendance_absent(db.get_today_attendance(F)["id"], "Бемор", "пагоҳ")
    await sync.sync()
    hakim16 = book.cell("November 2026", R_HAKIM, gs.day_col(16))
    check("manual company entry is never overwritten", hakim16["v"] == T("10:00"), hakim16)
    check("conflict counted", gs.STATE["conflicts"] == 1)
    far16 = book.cell("November 2026", R_FARIDA, gs.day_col(16))
    check("absent → «Наомад» in red", far16["v"] == gs.TEXT_ABSENT and far16["bg"] == gs.BAD[0]
          and far16["fg"] == gs.BAD[1] and far16["bold"] is True)

    at("2026-11-16", "14:40")
    db.create_due_attendance()
    rec_k = db.get_today_attendance(K)
    check("Kabir asked at 14:00", rec_k["scheduled_at"] == "2026-11-16 14:00:00")
    db.set_attendance_present(rec_k["id"])
    await sync.sync()
    k16 = book.cell("November 2026", R_KABIR, gs.day_col(16))
    check("arrival written as time hh:mm", abs(k16["v"] - T("14:40")) < 1e-9)
    check("40 min late → red (company rule >30)", k16["bg"] == gs.BAD[0])

    db.admin_set_attendance(K, "2026-11-16", "present", clock="14:20")
    await sync.sync()
    k16 = book.cell("November 2026", R_KABIR, gs.day_col(16))
    check("admin fix propagates (our cell)", abs(k16["v"] - T("14:20")) < 1e-9 and k16["bg"] == gs.WARN[0])
    db.admin_set_attendance(K, "2026-11-16", "present", clock="14:10")
    await sync.sync()
    check("≤15 min → green", book.cell("November 2026", R_KABIR, gs.day_col(16))["bg"] == gs.GOOD[0])

    # ── «🚪 Аз кор рафтам» ───────────────────────────────────────────────
    at("2026-11-16", "15:00")
    calls = await press(K, f"att:y:{rec_k['id']}")
    check("already-present answer handled", any("аллакай" in (c[2] or "") for c in calls))
    at("2026-11-16", "19:00")
    calls = await press(K, f"att:out:{rec_k['id']}")
    rec = db.get_attendance(rec_k["id"])
    check("leave button records time", rec["left_at"] == "2026-11-16 19:00:00")
    check("leave confirmation shown", any("19:00" in (c[2] or "") and "рафтед" in (c[2] or "") for c in calls))
    calls = await say(K, handlers.LEFT_BUTTON)
    check("second press keeps the first time", db.get_attendance(rec_k["id"])["left_at"].endswith("19:00:00")
          and any("қайд шуда буд" in (c[2] or "") for c in calls))
    calls = await say(A, handlers.LEFT_BUTTON)
    check("cannot leave without arrival", any("қайд нашудааст" in (c[2] or "") for c in calls)
          and (db.get_today_attendance(A) or {}).get("left_at") is None)
    await sync.sync()
    out16 = book.cell("November 2026", R_KABIR, gs.day_col(16, "out"))
    check("leave written to «Рафт»", abs(out16["v"] - T("19:00")) < 1e-9)
    check("left before planned 20:00 → red", out16["bg"] == gs.BAD[0])
    db.admin_set_attendance(K, "2026-11-16", "present", clock="14:10", left="20:05")
    await sync.sync()
    check("admin leave fix → green", book.cell("November 2026", R_KABIR, gs.day_col(16, "out"))["bg"] == gs.GOOD[0])
    try:
        db.admin_set_attendance(K, "2026-11-16", "present", clock="14:10", left="13:00")
        ok = False
    except ValueError:
        ok = True
    check("leave before arrival rejected", ok)
    cell = db.admin_set_attendance(K, "2026-11-16", "present", clock="14:10")
    check("edit without «left» keeps leave time", cell["out"] == "20:05")

    # дархост ба гурӯҳ — бо номи расмӣ
    at("2026-11-16", "19:10")
    await press(F, "t:leaving_early")
    await press(F, "r:0")
    await press(F, "m:10")
    calls = await press(F, "f:send")
    group = [c[2] or "" for c in calls if c[0] == "send" and c[1] == cfg.GROUP_ID]
    check("request to managers shows the official name", any("Sharifzoda Farida" in t for t in group), group[:1])

    # «✅ Ман омадам» — бе интизори савол, як бор дар рӯз
    at("2026-11-17", "09:02")
    due = {r["user_id"] for r in db.create_due_attendance()}
    check("employee outside the sheet gets no daily question", A not in due)
    calls = await say(A, handlers.ARRIVE_BUTTON)
    rec_a = db.get_today_attendance(A)
    check("«Ман омадам» records the arrival time", rec_a and rec_a["status"] == "present"
          and rec_a["arrived_at"].endswith("09:02:00"))
    check("arrival message offers the leave button", any(f"att:out:{rec_a['id']}" in buttons(c[3]) for c in calls))
    at("2026-11-17", "09:40")
    calls = await say(A, handlers.ARRIVE_BUTTON)
    check("«Ман омадам» only once a day", db.get_today_attendance(A)["arrived_at"].endswith("09:02:00")
          and any("як бор" in (c[2] or "") for c in calls))
    keyboard = handlers._main_reply_kb()
    labels = [b["text"] if isinstance(b, dict) else b.text for row in keyboard.keyboard for b in row]
    check("reply keyboard has both buttons", handlers.ARRIVE_BUTTON in labels and handlers.LEFT_BUTTON in labels)

    # ── одам дастӣ иваз кард → бот даст намезанад ──────────────────────
    book.put("November 2026", R_KABIR, gs.day_col(16), T("14:05"))
    db.admin_set_attendance(K, "2026-11-16", "present", clock="14:30", left="20:05")
    await sync.sync()
    check("human edit wins over later DB change",
          abs(book.cell("November 2026", R_KABIR, gs.day_col(16))["v"] - T("14:05")) < 1e-9)
    book.put("November 2026", R_KABIR, gs.day_col(16), None)
    await sync.sync()
    check("human cleared the cell → bot fills it again",
          abs(book.cell("November 2026", R_KABIR, gs.day_col(16))["v"] - T("14:30")) < 1e-9)

    # ── нест кардани сабт → ячейкаи бот тоза мешавад ────────────────
    farida_rec = next(r for r in db.attendance_between("2026-11-16", "2026-11-16") if r["user_id"] == F)
    db.delete_attendance(farida_rec["id"])
    await sync.sync()
    far16 = book.cell("November 2026", R_FARIDA, gs.day_col(16))
    check("deleted record → our cell cleared", far16.get("v") is None and far16.get("f") is None)
    check("cleared cell gets the row colour back", far16["bg"] == "ebf3fb" and far16.get("fg") is None)

    # ── «бе ҷавоб» → рӯзи дигар «Наомад» ──────────────────────────────
    at("2026-11-17", "09:31")
    db.create_due_attendance()
    await sync.sync()
    check("pending today → nothing yet", book.cell("November 2026", R_FARIDA, gs.day_col(17)).get("v") is None)
    at("2026-11-18", "08:00")
    await sync.sync()
    check("no answer by the next day → «Наомад»",
          book.cell("November 2026", R_FARIDA, gs.day_col(17)).get("v") == gs.TEXT_ABSENT)

    # ── пеш аз оғози синхронизатсия — даст намерасонем ──────────────────
    db.admin_set_attendance(H, "2026-11-14", "present", clock="10:00")
    await sync.sync()
    check("days before the start date are never touched",
          book.cell("November 2026", R_HAKIM, gs.day_col(14)).get("v") is None)

    # ── моҳи нав: 1 декабр ─────────────────────────────────────────────
    at("2026-12-01", "08:00")
    await sync.sync()
    dec = next((s for s in book.sheets.values() if s["title"] == "December 2026"), None)
    check("new month tab created", dec is not None and len(book.sheets) == 2)
    check("new month goes right after the previous one", dec and dec["index"] == 1)
    check("tags: Dec=2026-12, Nov stays 2026-11",
          dec and [m["metadataValue"] for m in dec["meta"]] == ["2026-12"]
          and [m["metadataValue"] for m in nov["meta"]] == ["2026-11"])
    D_ = "December 2026"
    check("title for December", book.cell(D_, 0, 0)["v"] == "Ҳузури Кормандон — December 2026")
    check("day 1 = Сешанбе, day 31 = Панҷшанбе",
          book.cell(D_, 1, gs.day_col(1))["v"] == "1-Сешанбе" and book.cell(D_, 1, gs.day_col(31))["v"] == "31-Панҷшанбе")
    check("weekend header colours", book.cell(D_, 1, gs.day_col(5))["bg"] == gs.HEAD_WEEKEND
          and book.cell(D_, 1, gs.day_col(1))["bg"] == gs.HEAD_WORK
          and book.cell(D_, 2, gs.day_col(6))["bg"] == gs.HEAD_SUB[6][0])
    check("employees, ids, phones and times copied",
          book.cell(D_, R_KABIR, 0)["v"] == "Kabir Ghaffurov" and book.cell(D_, R_KABIR, 1)["v"] == str(K)
          and book.cell(D_, R_KABIR, 2)["v"] == "00 688 0067" and book.cell(D_, R_KABIR, 3)["v"] == "14:00")
    check("all day cells empty in the new month",
          all(book.cell(D_, r, c).get("v") is None for r in range(4, 9) for c in range(5, 67)))
    check("Sunday (6 Dec) pink, weekday = row colour",
          book.cell(D_, R_HAKIM, gs.day_col(6))["bg"] == gs.SUN_IN
          and book.cell(D_, R_HAKIM, gs.day_col(6, "out"))["bg"] == gs.SUN_OUT
          and book.cell(D_, R_HAKIM, gs.day_col(1))["bg"] == "ffffff"
          and book.cell(D_, R_KABIR, gs.day_col(1))["bg"] == "ebf3fb")
    check("result formulas in the new month", all(book.cell(D_, r, 67)["f"] == gs.result_formula(r + 1, ";")
                                                  for r in range(4, 9)))
    check("November data kept", abs(book.cell("November 2026", R_KABIR, gs.day_col(16))["v"] - T("14:30")) < 1e-9)

    at("2026-12-01", "10:03")
    db.create_due_attendance()
    db.set_attendance_present(db.get_today_attendance(H)["id"])
    await sync.sync()
    check("December arrival goes to the December tab",
          abs(book.cell(D_, R_HAKIM, gs.day_col(1))["v"] - T("10:03")) < 1e-9
          and book.cell("November 2026", R_HAKIM, gs.day_col(1)).get("v") is None)
    db.admin_set_attendance(K, "2026-11-30", "present", clock="14:00")
    await sync.sync()
    check("first days of a month still fix the previous month",
          abs(book.cell("November 2026", R_KABIR, gs.day_col(30))["v"] - T("14:00")) < 1e-9)
    tabs_before = len(book.sheets)
    await sync.sync()
    check("idempotent: no new tabs, no writes", len(book.sheets) == tabs_before and gs.STATE["last_writes"] == 0)

    # ── пайвасти дастӣ аз панел ────────────────────────────────────────
    state = gs.panel_state()
    check("panel: one branch with its rows", len(state["books"]) == 1 and state["books"][0]["total"] == 5
          and state["books"][0]["linked"] == 3)
    check("panel lists unlinked bot users", {u["user_id"] for u in state["unlinked"]} == {A, G})
    await sync.link(R_GHOLIB + 1, "Gholib Kabirov", G)
    check("manual link writes the Telegram id", book.cell(D_, R_GHOLIB, 1)["v"] == str(G))
    await sync.link(R_KABIR + 1, "Kabir Ghaffurov", None)
    check("unlink clears the id", book.cell(D_, R_KABIR, 1).get("v") is None)
    await sync.sync()
    check("unlinked person is not auto-linked back", book.cell(D_, R_KABIR, 1).get("v") is None)
    check("unlinked → bot uses the global time again",
          db.emp_schedule(db.get_employee(K), db.get_schedule())["time"] == "09:00")
    await sync.link(R_KABIR + 1, "Kabir Ghaffurov", K)
    check("relink works", book.cell(D_, R_KABIR, 1)["v"] == str(K))
    await sync.link(R_GHOLIB + 1, "Gholib Kabirov", K)
    check("one person = one row (old row cleared)",
          book.cell(D_, R_GHOLIB, 1)["v"] == str(K) and book.cell(D_, R_KABIR, 1).get("v") is None)
    try:
        await sync.link(R_GHOLIB + 1, "Someone Else", K)
        ok = False
    except gs.SheetsError:
        ok = True
    check("stale panel (row moved) is refused", ok)
    await sync.link(R_KABIR + 1, "Kabir Ghaffurov", K)

    # забони ҷадвал нодуруст муайян шуд → пас аз санҷиш ҷудокунандаи дигар
    book2 = build_book()
    book2.locale = "en_US"           # Google гуфт en, вале ҷадвал «;» мехоҳад
    s2 = gs.Syncer(FakeClient(book2), "BOOK2", "bot@x.iam")
    tab2 = (await s2.tabs())[0]
    rows2 = gs.parse_rows(await s2.client.values(tab2.title, "A1:BP400"))
    await s2.ensure_formulas(tab2, rows2, force=True)
    check("wrong guess → verified and retried with the other separator",
          s2._sep == ";" and book2.cell("Лист1", 4, 67)["f"] == gs.result_formula(5, ";"))
    check("en formula has no decimals (1/2 instead of 0.5)", "0.5" not in gs.result_formula(5) and "1/2" in gs.result_formula(5))
    check("ru formula differs only by «;»", gs.result_formula(5, ";") == gs.result_formula(5).replace(",", ";"))

    db.set_settings({"gsheet_times": "0"})
    check("sheet times can be switched off", db.emp_schedule(db.get_employee(K), db.get_schedule())["time"] == "09:00")
    db.set_settings({"gsheet_times": "1"})

    # ── ҳимоя ──────────────────────────────────────────────────────────
    book.put(D_, 2, gs.day_col(1), "X")
    writes = book.writes
    try:
        await sync.sync()
        ok = False
    except gs.SheetsError as exc:
        ok = "Сохтор" in str(exc)
    check("changed layout → stop, no writes", ok and book.writes == writes)
    book.put(D_, 2, gs.day_col(1), "Омад")

    # wipe: ҷадвал тоза намешавад
    db.wipe("requests")
    await sync.sync()
    check("wiping the database never clears the sheet",
          abs(book.cell(D_, R_HAKIM, gs.day_col(1))["v"] - T("10:03")) < 1e-9)

    # ҳалқаи фонӣ: хатои Google → ҳолат; баъд барқарор
    book.fail = "Google 503: test"
    sync2 = gs.Syncer(FakeClient(book), "BOOK", "bot@x.iam")
    task = asyncio.create_task(sync2.loop())
    for _ in range(50):
        await asyncio.sleep(0.02)
        if gs.STATE["ok"] is False:
            break
    check("loop reports Google errors without crashing", gs.STATE["ok"] is False and "503" in gs.STATE["error"]
          and not task.done())
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    book.fail = None
    await sync.sync()
    check("recovers after the error", gs.STATE["ok"] is True and gs.STATE["error"] == "")

    # ── ду филиал (Manager) ────────────────────────────────────────────
    at("2026-11-18", "08:00")
    gs._SYNCER = None
    bookA, bookB = build_book(), build_book()
    bookB.sheets[0]["title"] = "November 26"                 # номи варақи корхона — бетағйир мемонад
    hidden = bookB.add(9, "November 2026", 1)                # нусхаи кӯҳнаи пинҳон
    hidden["hidden"] = True
    hidden["cells"] = copy.deepcopy(bookB.sheets[0]["cells"])
    company = '=IFERROR((IF(AND(F5<>"",F5-TIMEVALUE($D5)<=TIMEVALUE("00:15")),1,0))/MAX(1,IF(F5<>"",1,0)),"")'
    bookB.put("November 26", R_MASAFI, 67, None, f=company)
    bookB.locale = "en_US"
    bookB.sep = ","
    M2 = 7001
    db.touch_employee(M2, "Масафи (@masafi)", "masafi")
    bookA.put("Лист1", R_HAKIM, 1, str(H))
    bookB.put("November 26", R_MASAFI, 1, str(M2))
    db.set_settings({"gsheet_books": json.dumps([{"id": "SHEET_PROFSOYUZ_0000000001", "name": "Профсоюз"}, {"id": "SHEET_FILIAL_2_00000000002", "name": "Филиали 2"}])})
    clients = {"SHEET_PROFSOYUZ_0000000001": FakeClient(bookA), "SHEET_FILIAL_2_00000000002": FakeClient(bookB)}
    mgr = gs.Manager(None, client_factory=lambda sid: clients[sid])
    gs._MANAGER = mgr
    await mgr.sync_all()
    check("two branches: employee gets the branch of his sheet",
          db.get_employee(M2)["branch"] == "SHEET_FILIAL_2_00000000002" and db.get_employee(H)["branch"] == "SHEET_PROFSOYUZ_0000000001")
    check("company tab name «November 26» kept", bookB.sheets[0]["title"] == "November 26"
          and [m["metadataValue"] for m in bookB.sheets[0]["meta"]] == ["2026-11"])
    check("hidden old tabs are never touched", hidden["meta"] == [] and hidden["title"] == "November 2026")
    check("company «Натиҷа %» formula made text-safe",
          bookB.cell("November 26", R_MASAFI, 67)["f"] == gs.result_formula(R_MASAFI + 1, ","))
    state = gs.panel_state()
    check("panel shows both branches", [b["name"] for b in state["books"]] == ["Профсоюз", "Филиали 2"]
          and [b["linked"] for b in state["books"]] == [1, 1])
    check("employees carry their branch in the panel",
          next(e for e in state["employees"] if e["user_id"] == M2)["branch"] == "SHEET_FILIAL_2_00000000002")
    sch = db.get_schedule()
    check("only sheet employees are asked", db.emp_schedule(db.get_employee(M2), sch)["asked"]
          and not db.emp_schedule(db.get_employee(A), sch)["asked"])

    bookB.fail = "Google 503: B"
    try:
        await mgr.sync_all()
        ok = False
    except gs.SheetsError as exc:
        ok = "Филиали 2" in str(exc)
    check("one branch down → error names it", ok)
    check("…and its employees keep their times and branch", db.get_employee(M2)["branch"] == "SHEET_FILIAL_2_00000000002"
          and db.get_employee(M2)["sheet_time"] == "10:00" and db.get_employee(H)["branch"] == "SHEET_PROFSOYUZ_0000000001")
    bookB.fail = None

    ok = await gs.set_plan(M2, "11:00", "19:00")
    check("time changed in the panel → written to the sheet", ok
          and book_cell_text(bookB, "November 26", R_MASAFI, 3) == "11:00"
          and book_cell_text(bookB, "November 26", R_MASAFI, 4) == "19:00")
    check("…and the bot uses it at once", db.get_employee(M2)["sheet_time"] == "11:00")
    check("employee outside the sheets → nothing to write", await gs.set_plan(A, "12:00", None) is False)

    at("2026-12-01", "08:00")
    await mgr.sync_all()
    decB = next((t for t in bookB.sheets.values() if t["title"] == "December 26"), None)
    check("next month named like the company tabs («December 26»)", decB is not None)
    check("…placed right after «November 26»", decB and decB["index"] == bookB.sheets[0]["index"] + 1)
    check("…and the panel time is kept for the new month",
          decB and book_cell_text(bookB, "December 26", R_MASAFI, 3) == "11:00")
    check("…hidden «December»-like tabs untouched", hidden["meta"] == [])

    await gs.link(R_MASAFI + 1, "Masafi Begimadov", M2, "SHEET_PROFSOYUZ_0000000001")
    check("moving a person to another branch clears the old row",
          book_cell_text(bookB, "December 26", R_MASAFI, 1) is None
          and book_cell_text(bookA, "December 2026", R_MASAFI, 1) == str(M2)
          and db.get_employee(M2)["branch"] == "SHEET_PROFSOYUZ_0000000001")
    gs._MANAGER = None
    db.set_settings({"gsheet_books": json.dumps([{"id": "SHEET_PROFSOYUZ_0000000001", "name": "Профсоюз"}])})

    try:
        await gs.sync_now()
        ok = False
    except gs.SheetsError:
        ok = True
    check("sync_now without config → clear error", ok)
    check("broken key file → not configured", gs.build() is None and "Калиди" in gs.STATE["error"])
    check("sheet id from a link", gs.parse_sheet_id("https://docs.google.com/spreadsheets/d/1KH-HbN9XfbxkFRWC8ozwOjM3JJhvYEtp8bzlHNwjBCo/edit?gid=0") == "1KH-HbN9XfbxkFRWC8ozwOjM3JJhvYEtp8bzlHNwjBCo"
          and gs.parse_sheet_id("bad") is None)
    check("month title styles", gs.month_title("2026-12", "short") == "December 26"
          and gs.title_style("November 26") == "short" and gs.title_style("November 2026") == "long")
    check("month-like names are kept", gs.looks_like_month("November 26") and gs.looks_like_month("Октябр")
          and not gs.looks_like_month("Лист1"))


asyncio.run(run())
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
