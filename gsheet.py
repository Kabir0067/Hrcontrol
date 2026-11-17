"""
SoftClub / Hrcontrol — синхронизатсия бо Google Sheet-и корхона («Oficce Out»).

Сохтори ҷадвал (аз они корхона; бот онро тағйир намедиҳад). Як варақ — як моҳ:
  сатри 1   — сарлавҳа: «Ҳузури Кормандон — November 2026»
  сатри 2–3 — «Номи Корманд» · «Телеграм id» · «Телефон» · «Омадан (брнм)» · «Рафтан (брнм)» ·
              рӯзҳо («1-Якшанбе» …; ҳар рӯз 2 сутун: «Омад» / «Рафт») · «Натиҷа %»
  сатри 4   — ҷудокунанда
  сатри 5…  — кормандон: як сатр — як корманд

Қоидаҳо:
  • корманд бо сутуни «Телеграм id» ба сатраш пайваст мешавад (аз панел ё худкор аз рӯи ном);
  • вақти омадан ҳамон рӯз ба шакли соат:дақиқа навишта мешавад, рангаш — мисли ҷадвали
    корхона: то 15 дақ. дер — сабз, то 30 — зард, зиёдтар — сурх; «Наомад», «Рухсатӣ»;
  • вақти рафтан (тугмаи «🚪 Аз кор рафтам») — дар сутуни «Рафт»;
  • бот танҳо ячейкаи холӣ ё ячейкаи худашро иваз мекунад — навиштаи дастии одамро ҳеҷ гоҳ;
  • ҳар моҳ варақи нав худкор сохта мешавад: нусхаи моҳи гузашта (ҳамон дизайн, кормандон,
    телефонҳо, вақтҳо), рӯзҳо ва рӯзҳои ҳафта — мутобиқи моҳи нав, ячейкаҳои рӯзҳо — холӣ;
  • «Омадан (брнм)» — вақте ки бот мепурсад «Ба кор омадед?» ва аз он дерӣ ҳисоб мешавад;
  • вобастагии нав нест: имзои RS256 барои Google бо Python-и тоза, HTTP — aiohttp.
"""

from __future__ import annotations

import asyncio
import base64
import calendar
import hashlib
import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from itertools import permutations
from urllib.parse import quote, urlencode

import config as cfg
import database as db

log = logging.getLogger("SoftClubBot")

API_ROOT = "https://sheets.googleapis.com/v4/spreadsheets"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
META_KEY = "hrcontrol_month"

# ── сохтори ҷадвал (индексҳо аз 0) ─────────────────────────────────────────
ROW_TITLE, ROW_DAYS, ROW_SUB, FIRST_ROW = 0, 1, 2, 4
C_NAME, C_TG, C_PHONE, C_IN, C_OUT, C_DAY0, C_RESULT = 0, 1, 2, 3, 4, 5, 67
DAYS_MAX = 31
MAX_ROWS = 400

MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
WEEKDAYS = ["Душанбе", "Сешанбе", "Чоршанбе", "Панҷшанбе", "Ҷумъа", "Шанбе", "Якшанбе"]
_WD_KEYS = {"душанбе": 0, "сешанбе": 1, "чоршанбе": 2, "чоршабе": 2, "панҷшанбе": 3,
            "панчшанбе": 3, "ҷумъа": 4, "чумъа": 4, "ҷума": 4, "шанбе": 5, "якшанбе": 6}

TEXT_ABSENT = "Наомад"
TEXT_LEAVE = "Рухсатӣ"

# Рангҳо — айнан аз ҷадвали корхона (фон, ҳарф)
GOOD = ("c8e6c9", "1b5e20")       # то 15 дақ. — сари вақт
WARN = ("fff9c4", "7a5800")       # 16–30 дақ. дер
BAD = ("ffcdd2", "b71c1c")        # зиёда аз 30 дақ. / наомад / барвақт рафт
INFO = ("cfe2f3", "0b5394")       # рухсатӣ
SUN_IN, SUN_OUT = "ffd0d0", "ffe0cc"           # якшанбе: «Омад» / «Рафт»
HEAD_WORK, HEAD_WEEKEND = "2e5fa3", "9e0000"    # сатри 2: рӯзи корӣ / шанбе-якшанбе
HEAD_SUB = {6: ("b71c1c", "b71c1c"), 5: ("9e0000", "9e0000"), 0: ("2e5fa3", "e65100")}
HEAD_SUB_DEFAULT = ("1565c0", "e65100")
TIME_FMT = {"type": "TIME", "pattern": "hh:mm"}

CELL_FIELDS = ",".join((
    "userEnteredValue",
    "userEnteredFormat.backgroundColor", "userEnteredFormat.backgroundColorStyle",
    "userEnteredFormat.horizontalAlignment", "userEnteredFormat.numberFormat",
    "userEnteredFormat.textFormat.foregroundColor", "userEnteredFormat.textFormat.foregroundColorStyle",
    "userEnteredFormat.textFormat.bold",
))
BG_FIELDS = "userEnteredFormat.backgroundColor,userEnteredFormat.backgroundColorStyle"


class SheetsError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


# ══════════════════════════════════════════════════════════════════════════
#  Ёрдамчиҳо
# ══════════════════════════════════════════════════════════════════════════

def col_name(index: int) -> str:
    """0 → A, 67 → BP."""
    name, index = "", index + 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def day_col(day: int, kind: str = "in") -> int:
    return C_DAY0 + 2 * (day - 1) + (1 if kind == "out" else 0)


def _rgb(hex6: str) -> dict:
    return {"red": int(hex6[0:2], 16) / 255, "green": int(hex6[2:4], 16) / 255,
            "blue": int(hex6[4:6], 16) / 255}


def _hex(color: dict | None) -> str:
    if not color:
        return ""
    return "%02x%02x%02x" % tuple(int(round(float(color.get(k, 0)) * 255)) for k in ("red", "green", "blue"))


def _bg(hex6: str) -> dict:
    c = _rgb(hex6)
    return {"backgroundColor": c, "backgroundColorStyle": {"rgbColor": c}}


def _get(rows: list, r: int, c: int):
    if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
        return rows[r][c]
    return None


def to_min(clock: str) -> int:
    hour, minute = clock.split(":")
    return int(hour) * 60 + int(minute)


def sheet_clock(value) -> str | None:
    """Қимати ячейка → "HH:MM" (вақт дар Sheets — қисми шабонарӯз ё матни "9:30")."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value < 0:
            return None
        minutes = int(round((float(value) % 1) * 1440)) % 1440
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})(?::\d{2})?\s*", str(value))
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def cell_key(value) -> str | None:
    """Шакли муқоисавии ячейка: вақт → "HH:MM", матн → худи матн, холӣ → None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).upper()
    if isinstance(value, (int, float)):
        return sheet_clock(value)
    text = str(value).strip()
    if not text:
        return None
    return sheet_clock(text) or text


def parse_tg(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float):
        value = int(value) if value.is_integer() else None
    if isinstance(value, int):
        return value if 0 < value < 10 ** 13 else None
    digits = re.sub(r"[\s ]", "", str(value))
    if re.fullmatch(r"\d{3,13}", digits):
        return int(digits)
    return None


def month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def shift_month(key: str, delta: int) -> str:
    y, m = (int(x) for x in key.split("-"))
    m += delta
    while m < 1:
        y, m = y - 1, m + 12
    while m > 12:
        y, m = y + 1, m - 12
    return f"{y:04d}-{m:02d}"


def month_days(key: str) -> int:
    y, m = (int(x) for x in key.split("-"))
    return calendar.monthrange(y, m)[1]


def month_title(key: str, style: str = "long") -> str:
    """«November 2026» (long) ё «November 26» (short — мисли ҷадвали корхона)."""
    y, m = (int(x) for x in key.split("-"))
    return f"{MONTHS_EN[m - 1]} {y % 100:02d}" if style == "short" else f"{MONTHS_EN[m - 1]} {y}"


def title_style(title: str) -> str:
    return "short" if re.fullmatch(r"\s*[A-Za-z]+\s+\d{2}\s*", title or "") else "long"


_MONTH_STEMS = tuple(m.lower()[:3] for m in MONTHS_EN) + (
    "январ", "феврал", "март", "апрел", "май", "июн", "июл", "август", "сентябр", "октябр",
    "ноябр", "декабр", "солона")


def looks_like_month(title: str) -> bool:
    """Номи варақ ба номи моҳ монанд аст? (онро иваз намекунем — номгузории корхона)"""
    low = (title or "").lower()
    return any(re.search(r"(^|[^a-zа-яӣӯҳқғҷ])" + re.escape(stem), low) for stem in _MONTH_STEMS)


def day_label(key: str, day: int) -> str:
    y, m = (int(x) for x in key.split("-"))
    return f"{day}-{WEEKDAYS[date(y, m, day).weekday()]}"


def title_text(current: str, key: str) -> str:
    """«Ҳузури Кормандон — August 2026» → «Ҳузури Кормандон — November 2026»."""
    current = (current or "").strip()
    prefix = re.split(r"\s+[—–-]\s+", current, maxsplit=1)[0].strip() if current else ""
    return f"{prefix or 'Ҳузури Кормандон'} — {month_title(key)}"


def layout_ok(rows: list) -> bool:
    """Сохтори ҷадвали корхона: «Номи Корманд» … «Омад» / «Рафт»."""
    a2 = str(_get(rows, ROW_DAYS, C_NAME) or "").strip().lower()
    f3 = str(_get(rows, ROW_SUB, C_DAY0) or "").strip().lower()
    g3 = str(_get(rows, ROW_SUB, C_DAY0 + 1) or "").strip().lower()
    return a2.startswith("ном") and f3.startswith("омад") and g3.startswith("рафт")


def header_matches(rows: list, key: str) -> bool:
    """Сарлавҳаи рӯзҳо («1-Якшанбе» …) ба ҳамин моҳ мувофиқ аст? (як хатои чопӣ мебахшад)"""
    y, m = (int(x) for x in key.split("-"))
    dim = month_days(key)
    good = 0
    for d in range(1, DAYS_MAX + 1):
        label = str(_get(rows, ROW_DAYS, day_col(d)) or "").strip()
        if d > dim:
            if label:
                return False
            continue
        mt = re.fullmatch(r"(\d{1,2})\s*[-–—.]\s*(\S+)", label)
        if mt and int(mt.group(1)) == d and _WD_KEYS.get(mt.group(2).lower()) == date(y, m, d).weekday():
            good += 1
    return good >= dim - 1


def result_formula(row1: int, sep: str = ",") -> str:
    """«Натиҷа %» — ҳамон ҳисоби корхона, вале дуруст (дар шакли A1, на R1C1):

    омадан: то 15 дақ. — 1, то 30 — 0.5; рафтан: на барвақттар аз «Рафтан (брнм)» — 1;
    тақсим ба шумораи ячейкаҳои пур (бе «Рухсатӣ»). «Наомад» = 0.

    sep — ҷудокунандаи аргументҳо: "," (en) ё ";" (ru ва ғ.). Ададҳои касрӣ нест
    (1/2 ба ҷои 0.5), бинобар ин формула танҳо бо ҳамин аломат фарқ мекунад.
    """
    rng = f"F{row1}:BO{row1}"
    pin = f"IF(ISNUMBER($D{row1}),MOD($D{row1},1),TIMEVALUE($D{row1}))"
    pout = f"IF(ISNUMBER($E{row1}),MOD($E{row1},1),TIMEVALUE($E{row1}))"
    late = f"ROUND(({rng}-{pin})*1440)"
    text = (
        f'=IF($D{row1}="","",IFERROR(('
        f"SUMPRODUCT(ARRAYFORMULA(ISEVEN(COLUMN({rng}))*IFERROR(ISNUMBER({rng})*(({late}<=15)+1/2*({late}>15)*({late}<=30)),0)))"
        f"+SUMPRODUCT(ARRAYFORMULA(ISODD(COLUMN({rng}))*IFERROR(ISNUMBER({rng})*(ROUND(({rng}-{pout})*1440)>=0),0)))"
        f')/MAX(1,COUNTA({rng})-COUNTIF({rng},"{TEXT_LEAVE}")),""))'
    )
    return text if sep == "," else text.replace(",", sep)


def _is_our_formula(text: str) -> bool:
    return "ISEVEN(COLUMN(F" in text and "SUMPRODUCT" in text


def _is_company_formula(text: str) -> bool:
    """Формулаи «Натиҷа %»-и корхона (ҳамон ҳисоб, вале бо матни «Наомад» холӣ мешавад)."""
    return text.startswith("=IFERROR((IF(AND(") and 'TIMEVALUE("00:15")' in text


# Забонҳое, ки дар онҳо ададҳо бо вергул навишта мешаванд → аргументҳо бо «;»
_SEMICOLON_LOCALES = ("ru", "uk", "be", "kk", "ky", "uz", "tg", "az", "tr", "de", "fr", "es", "it",
                      "pt", "pl", "cs", "nl", "sv", "fi", "da", "nb", "hu", "ro", "bg", "sr", "hr")


def formula_sep(locale: str | None) -> str:
    lang = (locale or "en").split("_")[0].lower()
    return ";" if lang in _SEMICOLON_LOCALES else ","


# ── номҳо: «Кабир Ғафуров (@kabir)» ≈ «Kabir Ghaffurov» ───────────────────

_CYR = {"а": "a", "б": "b", "в": "v", "г": "g", "ғ": "gh", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
        "з": "z", "и": "i", "ӣ": "i", "й": "y", "к": "k", "қ": "q", "л": "l", "м": "m", "н": "n",
        "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ӯ": "u", "ф": "f", "х": "kh",
        "ҳ": "h", "ц": "ts", "ч": "ch", "ҷ": "j", "ш": "sh", "щ": "sh", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya"}
_SIMPLE = (("kh", "h"), ("gh", "g"), ("sh", "s"), ("ch", "c"), ("zh", "z"), ("ts", "c"),
           ("dj", "j"), ("yo", "e"), ("yu", "u"), ("ya", "a"), ("ye", "e"), ("x", "h"),
           ("q", "k"), ("w", "v"))


def name_tokens(text: str) -> list[str]:
    s = str(text or "").split(" (@")[0]
    s = unicodedata.normalize("NFKC", s).lower()
    s = "".join(_CYR.get(ch, ch) for ch in s)
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z]+", " ", s)
    for a, b in _SIMPLE:
        s = s.replace(a, b)
    s = re.sub(r"(.)\1+", r"\1", s)
    return [t for t in s.split() if len(t) >= 2]


def name_score(a: str, b: str) -> float:
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    whole = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    short, long_ = short[:4], long_[:6]
    # Ҳар калима танҳо бо як калимаи дигар ҷуфт мешавад (ном↔ном, насаб↔насаб)
    sim = [[SequenceMatcher(None, x, y).ratio() for y in long_] for x in short]
    per = max(sum(sim[i][j] for i, j in enumerate(perm)) for perm in permutations(range(len(long_)), len(short)))
    per /= len(short)
    if len(short) == 1 and len(long_) > 1:          # танҳо ном, бе насаб — эҳтиёт
        per *= 0.8
        whole *= 0.8
    return round(max(whole, per), 3)


def same_name(a: str, b: str) -> bool:
    return " ".join(str(a or "").split()).casefold() == " ".join(str(b or "").split()).casefold()


# ══════════════════════════════════════════════════════════════════════════
#  Google: калиди service account ва имзои RS256 (бе китобхонаи иловагӣ)
# ══════════════════════════════════════════════════════════════════════════

def _der(buf: bytes, i: int) -> tuple[int, bytes, int]:
    tag = buf[i]
    length = buf[i + 1]
    i += 2
    if length & 0x80:
        n = length & 0x7F
        length = int.from_bytes(buf[i:i + n], "big")
        i += n
    return tag, buf[i:i + length], i + length


def _children(buf: bytes) -> list[tuple[int, bytes]]:
    out, i = [], 0
    while i < len(buf):
        tag, value, i = _der(buf, i)
        out.append((tag, value))
    return out


class RSAKey:
    """Калиди хусусии RSA аз PEM (PKCS#8 ё PKCS#1) — имзои RSASSA-PKCS1-v1_5 + SHA-256."""

    _SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")

    def __init__(self, pem: str):
        body = "".join(line.strip() for line in pem.strip().splitlines()
                       if line.strip() and not line.startswith("-----"))
        der = base64.b64decode(body)
        tag, seq, _ = _der(der, 0)
        if tag != 0x30:
            raise ValueError("калиди RSA нодуруст")
        items = _children(seq)
        if len(items) >= 3 and items[1][0] == 0x30 and items[2][0] == 0x04:      # PKCS#8
            tag, seq, _ = _der(items[2][1], 0)
            items = _children(seq)
        ints = [int.from_bytes(v, "big") for t, v in items if t == 0x02]
        if len(ints) < 9:
            raise ValueError("калиди RSA пурра нест")
        _, self.n, self.e, self.d, self.p, self.q, self.dp, self.dq, self.qi = ints[:9]
        self.size = (self.n.bit_length() + 7) // 8

    def sign(self, message: bytes) -> bytes:
        digest = self._SHA256_PREFIX + hashlib.sha256(message).digest()
        em = b"\x00\x01" + b"\xff" * (self.size - len(digest) - 3) + b"\x00" + digest
        m = int.from_bytes(em, "big")
        # CRT — ~4 маротиба тезтар; натиҷа ҳатман бо калиди кушода санҷида мешавад
        s1, s2 = pow(m, self.dp, self.p), pow(m, self.dq, self.q)
        s = s2 + ((self.qi * (s1 - s2)) % self.p) * self.q
        if pow(s, self.e, self.n) != m:
            s = pow(m, self.d, self.n)
            if pow(s, self.e, self.n) != m:
                raise ValueError("имзои RSA нодуруст шуд — калид вайрон аст")
        return s.to_bytes(self.size, "big")


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


class Credentials:
    def __init__(self, info: dict):
        if info.get("type") != "service_account" or not info.get("private_key"):
            raise ValueError("ин калиди service account нест")
        self.email = info.get("client_email", "")
        self.token_uri = info.get("token_uri") or TOKEN_URL
        self.key_id = info.get("private_key_id", "")
        self.key = RSAKey(info["private_key"])

    @classmethod
    def from_file(cls, path: str) -> "Credentials":
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh))

    def assertion(self) -> str:
        now = int(time.time())
        header = {"alg": "RS256", "typ": "JWT"}
        if self.key_id:
            header["kid"] = self.key_id
        payload = {"iss": self.email, "scope": SCOPE, "aud": self.token_uri,
                   "iat": now, "exp": now + 3600}
        unsigned = (_b64url(json.dumps(header, separators=(",", ":")).encode()) + "."
                    + _b64url(json.dumps(payload, separators=(",", ":")).encode()))
        return unsigned + "." + _b64url(self.key.sign(unsigned.encode()))


def _error_text(status: int, body: str, email: str) -> str:
    try:
        message = json.loads(body).get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        message = body[:200]
    if status == 403:
        return (f"Google иҷозат намедиҳад (403). Ҷадвалро ба {email or 'service account'} "
                "бо ҳуқуқи «Editor» дастрас кунед.")
    if status == 404:
        return "Ҷадвал ёфт нашуд (404) — GSHEET_ID-ро санҷед."
    return f"Google {status}: {message or 'хато'}"[:400]


class Client:
    """Sheets API v4 (танҳо он чизе, ки лозим аст)."""

    def __init__(self, creds: Credentials, spreadsheet_id: str):
        self.creds = creds
        self.sid = spreadsheet_id
        self._token = ""
        self._token_exp = 0.0
        self._session = None

    async def _sess(self):
        import aiohttp
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45))
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def token(self) -> str:
        if self._token and time.time() < self._token_exp - 300:
            return self._token
        session = await self._sess()
        data = {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": self.creds.assertion()}
        async with session.post(self.creds.token_uri, data=data) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise SheetsError(f"Google токен надод ({resp.status}): {body[:200]}", resp.status)
        payload = json.loads(body)
        self._token = payload["access_token"]
        self._token_exp = time.time() + int(payload.get("expires_in", 3600))
        return self._token

    async def call(self, method: str, path: str, params: dict | None = None,
                   body: dict | None = None) -> dict:
        import aiohttp
        from yarl import URL
        url = f"{API_ROOT}/{self.sid}{path}"
        if params:
            url += "?" + urlencode(params, quote_via=quote)
        for attempt in range(4):
            token = await self.token()
            session = await self._sess()
            try:
                async with session.request(method, URL(url, encoded=True), json=body,
                                           headers={"Authorization": f"Bearer {token}"}) as resp:
                    status, text = resp.status, await resp.text()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == 3:
                    raise SheetsError(f"Google дастрас нест: {exc or type(exc).__name__}") from exc
                await asyncio.sleep(2 ** attempt)
                continue
            if status == 200:
                return json.loads(text) if text else {}
            if status == 401 and attempt == 0:
                self._token = ""
                continue
            if status in (429, 500, 502, 503, 504) and attempt < 3:
                await asyncio.sleep(2 ** (attempt + 1))
                continue
            raise SheetsError(_error_text(status, text, self.creds.email), status)
        raise SheetsError("Google ҷавоб надод")

    @staticmethod
    def _a1(title: str, rng: str) -> str:
        return "'" + title.replace("'", "''") + "'!" + rng

    async def meta(self) -> dict:
        return await self.call("GET", "", {"fields": (
            "properties(locale),"
            "sheets(properties(sheetId,title,index,hidden,gridProperties(rowCount,columnCount)),"
            "developerMetadata(metadataId,metadataKey,metadataValue))")})

    async def values(self, title: str, rng: str, render: str = "UNFORMATTED_VALUE") -> list:
        data = await self.call("GET", "/values/" + quote(self._a1(title, rng), safe=""),
                               {"valueRenderOption": render, "dateTimeRenderOption": "SERIAL_NUMBER"})
        return data.get("values", [])

    async def grid(self, title: str, rng: str, fields: str) -> dict:
        return await self.call("GET", "", {"ranges": self._a1(title, rng), "fields": fields})

    async def batch(self, requests: list[dict]) -> list[dict]:
        replies: list[dict] = []
        for i in range(0, len(requests), 400):
            data = await self.call("POST", ":batchUpdate", body={"requests": requests[i:i + 400]})
            replies.extend(data.get("replies", []))
        return replies


# ══════════════════════════════════════════════════════════════════════════
#  Модели ҷадвал
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class Tab:
    sheet_id: int
    title: str
    index: int
    rows: int
    month: str | None = None
    meta_id: int | None = None
    hidden: bool = False


@dataclass
class Row:
    r: int                       # индекси сатр (0-асос)
    name: str
    tg: int | None
    plan_in: str | None
    plan_out: str | None
    cells: list = field(default_factory=list)

    def value(self, col: int):
        return self.cells[col] if col < len(self.cells) else None


def parse_rows(values: list) -> list[Row]:
    rows = []
    for r in range(FIRST_ROW, len(values)):
        line = values[r]
        name = str(_get(values, r, C_NAME) or "").strip()
        raw_tg = _get(values, r, C_TG)
        if not name and raw_tg in (None, ""):
            continue
        rows.append(Row(r, name, parse_tg(raw_tg), sheet_clock(_get(values, r, C_IN)),
                        sheet_clock(_get(values, r, C_OUT)), line))
    return rows


def desired_in(rec: dict | None, plan: str | None, past: bool) -> tuple[str, tuple] | None:
    """Ячейкаи «Омад»: (қимат, (фон, ҳарф)) ё None — бот чизе намехоҳад."""
    if not rec:
        return None
    status = rec.get("status")
    if status == "present":
        clock = db._clock(rec.get("arrived_at"))
        if not clock:
            return None
        plan = plan or db._clock(rec.get("scheduled_at"))
        late = to_min(clock) - to_min(plan) if plan else 0
        return clock, (GOOD if late <= 15 else WARN if late <= 30 else BAD)
    if status == "absent":
        return TEXT_ABSENT, BAD
    if status == "leave":
        return TEXT_LEAVE, INFO
    if status == "pending" and past:            # рӯз гузашт, «Омадам»-ро пахш накард
        return TEXT_ABSENT, BAD
    return None


def desired_out(rec: dict | None, plan: str | None) -> tuple[str, tuple] | None:
    if not rec or rec.get("status") != "present" or not rec.get("left_at"):
        return None
    clock = db._clock(rec["left_at"])
    if not clock:
        return None
    early = bool(plan) and to_min(clock) < to_min(plan)
    return clock, (BAD if early else GOOD)


def _range(sheet_id: int, r: int, c: int, r2: int | None = None, c2: int | None = None) -> dict:
    return {"sheetId": sheet_id, "startRowIndex": r, "endRowIndex": (r2 if r2 is not None else r + 1),
            "startColumnIndex": c, "endColumnIndex": (c2 if c2 is not None else c + 1)}


def _cell_data(value: str | None, colors: tuple | None, blank_bg: str = "ffffff") -> dict:
    if value is None:
        return {"userEnteredFormat": {**_bg(blank_bg), "numberFormat": TIME_FMT}}
    clock = sheet_clock(value) if re.fullmatch(r"\d{2}:\d{2}", value) else None
    uev = {"numberValue": to_min(clock) / 1440} if clock else {"stringValue": value}
    bg, fg = colors or GOOD
    fgc = _rgb(fg)
    return {"userEnteredValue": uev,
            "userEnteredFormat": {**_bg(bg), "horizontalAlignment": "CENTER", "numberFormat": TIME_FMT,
                                  "textFormat": {"foregroundColor": fgc, "foregroundColorStyle": {"rgbColor": fgc},
                                                 "bold": True}}}


def _write_cell(sheet_id: int, r: int, c: int, value: str | None, colors: tuple | None,
                blank_bg: str = "ffffff") -> dict:
    return {"updateCells": {"range": _range(sheet_id, r, c), "fields": CELL_FIELDS,
                            "rows": [{"values": [_cell_data(value, colors, blank_bg)]}]}}


def _text_cell(sheet_id: int, r: int, c: int, text: str | None) -> dict:
    cell = {"userEnteredValue": {"stringValue": text}} if text else {}
    return {"updateCells": {"range": _range(sheet_id, r, c), "fields": "userEnteredValue",
                            "rows": [{"values": [cell]}]}}


def _blank_bg(key: str, day: int, kind: str, stripe: str) -> str:
    y, m = (int(x) for x in key.split("-"))
    if day <= month_days(key) and date(y, m, day).weekday() == 6:
        return SUN_IN if kind == "in" else SUN_OUT
    return stripe


def header_requests(sheet_id: int, key: str) -> list[dict]:
    """Сатрҳои 2–3: «1-Якшанбе» … ва рангҳои рӯзҳо (шанбе/якшанбе — сурх) мисли ҷадвали корхона."""
    y, m = (int(x) for x in key.split("-"))
    dim = month_days(key)
    days_row, sub_row = [], []
    for d in range(1, DAYS_MAX + 1):
        if d <= dim:
            wd = date(y, m, d).weekday()
            label = f"{d}-{WEEKDAYS[wd]}"
            head = HEAD_WEEKEND if wd >= 5 else HEAD_WORK
            sub = HEAD_SUB.get(wd, HEAD_SUB_DEFAULT)
        else:
            label, head, sub = "", HEAD_WORK, HEAD_SUB_DEFAULT
        first = {"userEnteredFormat": _bg(head)}
        if label:
            first["userEnteredValue"] = {"stringValue": label}
        days_row += [first, {"userEnteredFormat": _bg(head)}]
        sub_row += [{"userEnteredFormat": _bg(sub[0])}, {"userEnteredFormat": _bg(sub[1])}]
    last = C_DAY0 + 2 * DAYS_MAX
    return [
        {"updateCells": {"range": _range(sheet_id, ROW_DAYS, C_DAY0, ROW_DAYS + 1, last),
                         "fields": "userEnteredValue," + BG_FIELDS, "rows": [{"values": days_row}]}},
        {"updateCells": {"range": _range(sheet_id, ROW_SUB, C_DAY0, ROW_SUB + 1, last),
                         "fields": BG_FIELDS, "rows": [{"values": sub_row}]}},
    ]


# ══════════════════════════════════════════════════════════════════════════
#  Синхронизатсия
# ══════════════════════════════════════════════════════════════════════════

STATE: dict = {
    "configured": False, "enabled": False, "running": False, "ok": None, "error": "",
    "email": "", "last_try": None, "last_ok": None, "last_write": None,
    "writes": 0, "last_writes": 0, "conflicts": 0, "tab": "", "month": "",
}


def _setting_on(key: str, default: str = "1") -> bool:
    return str(db.get_setting(key, default) or default) != "0"


def _no_autolink() -> set[int]:
    try:
        return {int(x) for x in json.loads(db.get_setting("gsheet_nolink", "[]") or "[]")}
    except (TypeError, ValueError):
        return set()


def _set_no_autolink(ids: set[int]) -> None:
    db.set_settings({"gsheet_nolink": json.dumps(sorted(ids))})


class Syncer:
    """Як ҷадвал (як филиал): варақҳои моҳҳо, навиштани давомот, пайвасти кормандон."""

    def __init__(self, client, spreadsheet_id: str, email: str = "", name: str = ""):
        self.client = client
        self.sid = spreadsheet_id
        self.email = email
        self.name = name or "Филиал"
        self.lock = asyncio.Lock()
        self.kicked = asyncio.Event()
        self.snapshot: dict | None = None
        self.title = ""                     # номи худи ҷадвал дар Google
        self._formulas_ok: set = set()
        self.locale = ""
        self._sep = ""                      # ҷудокунандае, ки дар ин ҷадвал санҷида шуд
        self._last_logged = ("", 0.0)
        self.status: dict = {"ok": None, "error": "", "last_try": None, "last_ok": None, "last_write": None,
                             "writes": 0, "last_writes": 0, "conflicts": 0, "tab": "", "month": ""}

    def _set(self, **values) -> None:
        self.status.update(values)
        STATE.update({k: v for k, v in values.items() if k in STATE})

    # ── варақҳои моҳҳо ────────────────────────────────────────────────

    async def tabs(self) -> list[Tab]:
        meta = await self.client.meta()
        props = meta.get("properties") or {}
        self.locale = props.get("locale") or self.locale
        self.title = props.get("title") or self.title
        out = []
        for sh in meta.get("sheets", []):
            p = sh.get("properties", {})
            tag = next((m for m in sh.get("developerMetadata", []) if m.get("metadataKey") == META_KEY), None)
            out.append(Tab(int(p.get("sheetId", 0)), p.get("title", ""), int(p.get("index", 0)),
                           int(p.get("gridProperties", {}).get("rowCount", 1000)),
                           tag.get("metadataValue") if tag else None,
                           tag.get("metadataId") if tag else None,
                           bool(p.get("hidden"))))
        return out

    async def ensure_month(self, key: str, create: bool = True) -> Tab | None:
        tabs = await self.tabs()
        mine = sorted((t for t in tabs if t.month == key), key=lambda t: t.index)
        if mine:
            return mine[0]
        titles = {month_title(key), month_title(key, "short")}
        # 1) варақи мавҷуда (намоён) бо номи ҳамин моҳ ё бо сарлавҳаҳои ҳамин моҳ.
        #    Варақҳои пинҳон — нусхаҳои кӯҳнаи корхона, ба онҳо даст намерасонем.
        for tab in sorted((t for t in tabs if t.month is None and not t.hidden),
                          key=lambda t: (t.title not in titles, t.index)):
            head = await self.client.values(tab.title, f"A1:{col_name(C_RESULT)}3")
            if layout_ok(head) and (tab.title in titles or header_matches(head, key)):
                await self._adopt(tab, key, head, tabs)
                return tab
        if not create:
            return None
        # 2) варақи нав — нусхаи моҳи охирин (ҳамон дизайн, кормандон, ID-ҳо ва вақтҳо)
        older = sorted((t for t in tabs if t.month and t.month < key), key=lambda t: t.month)
        source = older[-1] if older else None
        if source is None:
            for tab in sorted((t for t in tabs if not t.hidden), key=lambda t: t.index):
                if layout_ok(await self.client.values(tab.title, f"A1:{col_name(C_RESULT)}3")):
                    source = tab
                    break
        if source is None:
            raise SheetsError("Дар ҷадвал варақе бо сохтори «Номи Корманд / Телеграм id / Омад / Рафт» ёфт нашуд")
        return await self._create(source, key, tabs)

    def _meta_request(self, tab: Tab, key: str) -> dict:
        if tab.meta_id is not None:
            return {"updateDeveloperMetadata": {
                "dataFilters": [{"developerMetadataLookup": {"metadataId": tab.meta_id}}],
                "developerMetadata": {"metadataValue": key}, "fields": "metadataValue"}}
        return {"createDeveloperMetadata": {"developerMetadata": {
            "metadataKey": META_KEY, "metadataValue": key,
            "location": {"sheetId": tab.sheet_id}, "visibility": "DOCUMENT"}}}

    async def _adopt(self, tab: Tab, key: str, head: list, tabs: list[Tab]) -> None:
        """Варақи мавҷударо ҳамчун варақи ин моҳ қабул мекунад (дизайн ва маълумот — бетағйир).

        Номи варақро танҳо агар номи моҳ набошад («Лист1», «Sheet1») иваз мекунем;
        «November 26»-и корхона ҳамон тавр мемонад.
        """
        title = month_title(key)
        reqs = [self._meta_request(tab, key)]
        if not looks_like_month(tab.title) and title not in {t.title for t in tabs}:
            reqs.append({"updateSheetProperties": {"properties": {"sheetId": tab.sheet_id, "title": title},
                                                   "fields": "title"}})
        a1 = str(_get(head, ROW_TITLE, C_NAME) or "")
        if a1.strip() != title_text(a1, key):
            reqs.append(_text_cell(tab.sheet_id, ROW_TITLE, C_NAME, title_text(a1, key)))
        if not header_matches(head, key):
            reqs += header_requests(tab.sheet_id, key)
        await self.client.batch(reqs)
        log.info("📗 %s: варақи «%s» ҳамчун %s қабул шуд", self.name, tab.title, title)
        if any("updateSheetProperties" in r for r in reqs):
            tab.title = title
        tab.month = key

    async def _create(self, source: Tab, key: str, tabs: list[Tab]) -> Tab:
        title = month_title(key, title_style(source.title))
        if title in {t.title for t in tabs}:
            title = f"{title} (HR)"
        replies = await self.client.batch([{"duplicateSheet": {
            "sourceSheetId": source.sheet_id, "insertSheetIndex": source.index + 1, "newSheetName": title}}])
        props = replies[0]["duplicateSheet"]["properties"]
        new_id = int(props["sheetId"])
        fresh = next((t for t in await self.tabs() if t.sheet_id == new_id), None)
        tab = fresh or Tab(new_id, props.get("title", title), source.index + 1,
                           int(props.get("gridProperties", {}).get("rowCount", 1000)))
        values = await self.client.values(tab.title, f"A1:{col_name(C_RESULT)}{min(tab.rows, MAX_ROWS)}")
        rows = parse_rows(values)
        stripes = await self._stripes(tab, rows)
        reqs = [self._meta_request(tab, key),
                _text_cell(tab.sheet_id, ROW_TITLE, C_NAME, title_text(str(_get(values, 0, 0) or ""), key))]
        reqs += header_requests(tab.sheet_id, key)
        for row in rows:                       # рӯзҳо — холӣ (ранги сатр / якшанбе)
            stripe = stripes.get(row.r, "ffffff")
            cells = [_cell_data(None, None, _blank_bg(key, d, kind, stripe))
                     for d in range(1, DAYS_MAX + 1) for kind in ("in", "out")]
            reqs.append({"updateCells": {"range": _range(tab.sheet_id, row.r, C_DAY0, row.r + 1,
                                                         C_DAY0 + 2 * DAYS_MAX),
                                         "fields": CELL_FIELDS, "rows": [{"values": cells}]}})
        await self.client.batch(reqs)
        tab.month = key
        log.info("📗 %s: варақи нав «%s» сохта шуд (аз «%s», %d корманд)",
                 self.name, tab.title, source.title, len(rows))
        await self.ensure_formulas(tab, rows, force=True)
        return tab

    async def _stripes(self, tab: Tab, rows: list[Row]) -> dict[int, str]:
        """Ранги заминаи ҳар сатр (аз сутуни A) — барои катакҳои холӣ."""
        if not rows:
            return {}
        last = max(r.r for r in rows) + 1
        data = await self.client.grid(tab.title, f"A{FIRST_ROW + 1}:A{last}",
                                      "sheets(data(rowData(values(userEnteredFormat(backgroundColor)))))")
        try:
            row_data = data["sheets"][0]["data"][0].get("rowData", [])
        except (KeyError, IndexError):
            row_data = []
        out = {}
        for i, rd in enumerate(row_data):
            vals = rd.get("values") or [{}]
            out[FIRST_ROW + i] = _hex(vals[0].get("userEnteredFormat", {}).get("backgroundColor")) or "ffffff"
        return out

    async def ensure_formulas(self, tab: Tab, rows: list[Row], force: bool = False) -> None:
        """«Натиҷа %»: формулаи вайрон, холӣ ё формулаи корхона (ки бо «Наомад» холӣ мешавад)
        → ҳамон ҳисоб, вале ба матн тобовар. Формулаҳои дигарро намерасонем."""
        named = [r for r in rows if r.name]
        stamp = (tab.sheet_id, tuple(r.r for r in named))
        if not named or (not force and stamp in self._formulas_ok):
            return
        last = max(r.r for r in named) + 1
        current = await self.client.values(tab.title, f"{col_name(C_RESULT)}1:{col_name(C_RESULT)}{last}",
                                           render="FORMULA")
        first = self._sep or formula_sep(self.locale)
        variants = {result_formula(r.r + 1, x) for r in named for x in (",", ";")}

        def requests(sep: str, only: list[Row]) -> list[dict]:
            return [{"updateCells": {"range": _range(tab.sheet_id, row.r, C_RESULT), "fields": "userEnteredValue",
                                     "rows": [{"values": [{"userEnteredValue": {
                                         "formulaValue": result_formula(row.r + 1, sep)}}]}]}} for row in only]

        todo = []
        for row in named:
            have = str(_get(current, row.r, 0) or "")
            if have in variants:
                continue
            if not have or "R[0]C" in have or _is_our_formula(have) or _is_company_formula(have):
                todo.append(row)
        if todo:
            # Навиштан → санҷидан: агар Google формуларо нафаҳмид (#ERROR!) — ҷудокунандаи дигар
            for sep in (first, ";" if first == "," else ","):
                await self.client.batch(requests(sep, todo))
                shown = await self.client.values(
                    tab.title, f"{col_name(C_RESULT)}1:{col_name(C_RESULT)}{last}", render="FORMATTED_VALUE")
                if not any(str(_get(shown, row.r, 0) or "").startswith("#ERROR") for row in todo):
                    self._sep = sep
                    break
            else:
                self._sep = first
                log.warning("📗 «Натиҷа %%»: Google формуларо қабул накард (%s)", tab.title)
            log.info("📗 %s: «Натиҷа %%» дар %d сатр (%s, «%s»)", self.name, len(todo), tab.title, self._sep)
        self._formulas_ok.add(stamp)

    # ── ҳамоҳангсозӣ ───────────────────────────────────────────────────

    async def sync(self, apply_plans: bool = True) -> dict:
        async with self.lock:
            result = await self._sync()
        if apply_plans:
            db.sync_sheet_plans(result["plans"])
        return result

    async def _sync(self) -> dict:
        self._set(last_try=cfg.now_str())
        today = cfg.now().date()
        key = month_key(today)
        try:
            tab = await self.ensure_month(key, create=True)
            result = await self._sync_tab(tab, key, today, primary=True)
            if today.day <= 5:                  # охири моҳи гузашта (масалан, ислоҳи дертар)
                prev = await self.ensure_month(shift_month(key, -1), create=False)
                if prev is not None and prev.sheet_id != tab.sheet_id:
                    await self._sync_tab(prev, prev.month, today, primary=False)
        except Exception as exc:
            self._set(ok=False, error=(str(exc) if isinstance(exc, SheetsError)
                                       else f"{type(exc).__name__}: {exc}")[:400])
            raise
        self._set(ok=True, error="", last_ok=cfg.now_str(), tab=tab.title, month=key)
        return result

    def _autolink(self, rows: list[Row], emps: list[dict], links: dict[int, Row]) -> list[tuple[Row, int]]:
        """Пайвасти худкор — танҳо агар ном қариб айнан мувофиқ ва ягона бошад (ҳар ду тараф)."""
        blocked = _no_autolink()
        free = [r for r in rows if r.tg is None and r.name]
        # танҳо касоне, ки ҳанӯз дар ҳеҷ филиал нестанд (як корманд — як филиал)
        people = [e for e in emps if e["active"] and e["user_id"] not in links and e["user_id"] not in blocked
                  and not e.get("branch")]
        if not free or not people:
            return []
        score = {(e["user_id"], r.r): name_score(e["name"], r.name) for e in people for r in free}
        out = []
        for e in people:
            ranked = sorted(free, key=lambda r: -score[(e["user_id"], r.r)])
            best = ranked[0]
            s1 = score[(e["user_id"], best.r)]
            s2 = score[(e["user_id"], ranked[1].r)] if len(ranked) > 1 else 0.0
            if s1 < 0.88 or s1 - s2 < 0.08:
                continue
            rivals = sorted((score[(o["user_id"], best.r)] for o in people if o is not e), reverse=True)
            if rivals and s1 - rivals[0] < 0.08:
                continue
            out.append((best, e["user_id"]))
        used, unique = set(), []
        for row, uid in out:
            if row.r not in used:
                used.add(row.r)
                unique.append((row, uid))
        return unique

    def _since(self, today: date) -> str:
        key = f"gsheet_since:{self.sid}"
        since = db.get_setting(key)
        if not since:
            since = today.isoformat()
            db.set_settings({key: since})
        return since

    async def _sync_tab(self, tab: Tab, key: str, today: date, primary: bool) -> dict:
        values = await self.client.values(tab.title, f"A1:{col_name(C_RESULT)}{min(tab.rows, MAX_ROWS)}")
        if not layout_ok(values):
            raise SheetsError(f"Сохтори варақи «{tab.title}» иваз шудааст (сатрҳои 2–3) — бот ба он даст намезанад")
        rows = parse_rows(values)
        emps = db.employees_brief()
        by_id = {e["user_id"]: e for e in emps}

        links: dict[int, Row] = {}
        dups: set[int] = set()
        for row in rows:
            if row.tg:
                if row.tg in links:
                    dups.add(row.tg)
                else:
                    links[row.tg] = row
        for uid in dups:
            links.pop(uid, None)

        # Пешфарз — хомӯш: корманд танҳо аз рӯи «Телеграм id» пайваст мешавад
        if primary and _setting_on("gsheet_autolink", "0"):
            found = self._autolink(rows, emps, links)
            if found:
                await self.client.batch([_text_cell(tab.sheet_id, row.r, C_TG, str(uid)) for row, uid in found])
                for row, uid in found:
                    row.tg = uid
                    links[uid] = row
                    log.info("📗 Пайвасти худкор: «%s» ↔ %s", row.name, by_id[uid]["name"])

        plans = {uid: (row.plan_in, row.plan_out, row.name, self.sid) for uid, row in links.items() if uid in by_id}
        if primary:
            await self.ensure_formulas(tab, rows)

        since_txt = self._since(today)
        since = datetime.strptime(since_txt, cfg.DATE_FMT).date()
        y, m = (int(x) for x in key.split("-"))
        start = max(date(y, m, 1), since)
        end = min(date(y, m, month_days(key)), today)

        writes, put, drop, clears = [], [], [], []
        conflicts = 0
        if start <= end:
            recs = {(r["user_id"], r["work_date"]): r for r in db.attendance_between(start.isoformat(), end.isoformat())}
            tab_key = f"{self.sid}:{tab.sheet_id}"
            owned = db.sheet_owned(tab_key, start.isoformat(), end.isoformat())
            for uid, row in links.items():
                if uid not in by_id:
                    continue
                d = start
                while d <= end:
                    iso = d.isoformat()
                    rec = recs.get((uid, iso))
                    for kind, want in (("in", desired_in(rec, row.plan_in, d < today)),
                                       ("out", desired_out(rec, row.plan_out))):
                        col = day_col(d.day, kind)
                        cur = cell_key(row.value(col))
                        mine = owned.get((uid, iso, kind))
                        wanted = want[0] if want else None
                        if wanted is None:
                            if mine is not None:
                                if cur == mine:
                                    clears.append((row, d.day, kind, col))
                                drop.append((uid, iso, kind))
                            continue
                        if cur == wanted:
                            if mine != wanted:
                                put.append((uid, iso, kind, wanted))
                            continue
                        if cur is None or (mine is not None and cur == mine):
                            writes.append(_write_cell(tab.sheet_id, row.r, col, wanted, want[1]))
                            put.append((uid, iso, kind, wanted))
                        else:                    # одам дастӣ навиштааст — ба он даст намерасонем
                            conflicts += 1
                            if mine is not None:
                                drop.append((uid, iso, kind))
                    d += timedelta(days=1)
            if clears:
                stripes = await self._stripes(tab, rows)
                for row, day, kind, col in clears:
                    writes.append(_write_cell(tab.sheet_id, row.r, col, None, None,
                                              _blank_bg(key, day, kind, stripes.get(row.r, "ffffff"))))
            if writes:
                await self.client.batch(writes)
                self.status["writes"] += len(writes)
                STATE["writes"] += len(writes)
                self._set(last_write=cfg.now_str())
                log.info("📗 %s «%s»: %d катак навишта шуд", self.name, tab.title, len(writes))
            if put or drop:
                db.sheet_own_apply(tab_key, put, drop)

        if primary:
            self._set(last_writes=len(writes), conflicts=conflicts)
            self.snapshot = {
                "tab": tab.title, "month": key, "sheet_id": tab.sheet_id, "since": since_txt,
                "rows": [{"row": r.r + 1, "name": r.name, "tg": r.tg, "plan_in": r.plan_in,
                          "plan_out": r.plan_out, "dup": bool(r.tg and r.tg in dups),
                          "user_id": r.tg if (r.tg in by_id and r.tg not in dups) else None}
                         for r in rows],
                "at": cfg.now_str(),
            }
        return {"tab": tab.title, "writes": len(writes), "conflicts": conflicts, "plans": plans}

    # ── амалҳои панел ──────────────────────────────────────────────────

    async def link(self, row1: int, name: str, user_id: int | None, resync: bool = True) -> None:
        async with self.lock:
            key = month_key(cfg.now().date())
            tab = await self.ensure_month(key, create=True)
            values = await self.client.values(tab.title, f"A1:B{min(tab.rows, MAX_ROWS)}")
            r = int(row1) - 1
            if r < FIRST_ROW or r >= len(values) or not same_name(_get(values, r, C_NAME), name):
                raise SheetsError("Ҷадвал ҳозир иваз шуд — саҳифаро нав кунед ва аз нав интихоб кунед")
            reqs = []
            blocked = _no_autolink()
            if user_id:
                for i in range(FIRST_ROW, len(values)):
                    if i != r and parse_tg(_get(values, i, C_TG)) == user_id:
                        reqs.append(_text_cell(tab.sheet_id, i, C_TG, None))
                reqs.append(_text_cell(tab.sheet_id, r, C_TG, str(int(user_id))))
                blocked.discard(int(user_id))
            else:
                old = parse_tg(_get(values, r, C_TG))
                reqs.append(_text_cell(tab.sheet_id, r, C_TG, None))
                if old:
                    blocked.add(old)               # худкор боз пайваст накунад
            await self.client.batch(reqs)
            _set_no_autolink(blocked)
            log.info("📗 %s: сатри %d («%s») → %s", self.name, row1, name, user_id or "—")
            if resync:
                result = await self._sync()
        if resync:
            db.sync_sheet_plans(result["plans"])

    async def unlink_user(self, user_id: int) -> bool:
        """ID-и корманд аз ин ҷадвал (варақи ҷорӣ) тоза мешавад — ҳангоми гузариш ба филиали дигар."""
        async with self.lock:
            tab = await self.ensure_month(month_key(cfg.now().date()), create=True)
            values = await self.client.values(tab.title, f"A1:B{min(tab.rows, MAX_ROWS)}")
            reqs = [_text_cell(tab.sheet_id, i, C_TG, None) for i in range(FIRST_ROW, len(values))
                    if parse_tg(_get(values, i, C_TG)) == user_id]
            if reqs:
                await self.client.batch(reqs)
            return bool(reqs)

    async def set_plan(self, user_id: int, plan_in: str | None, plan_out: str | None) -> bool:
        """Вақти кор аз панел → «Омадан / Рафтан (брнм)» дар варақи ҷорӣ ва моҳҳои баъдӣ.

        Моҳи нав аз варақи охирин нусха мешавад, бинобар ин вақт барои ҳамеша мемонад.
        """
        async with self.lock:
            key = month_key(cfg.now().date())
            await self.ensure_month(key, create=True)
            tabs = [t for t in await self.tabs() if t.month and t.month >= key]
            found = False
            for tab in sorted(tabs, key=lambda t: t.month):
                values = await self.client.values(tab.title, f"A1:B{min(tab.rows, MAX_ROWS)}")
                reqs = []
                for i in range(FIRST_ROW, len(values)):
                    if parse_tg(_get(values, i, C_TG)) == user_id:
                        if plan_in is not None:
                            reqs.append(_text_cell(tab.sheet_id, i, C_IN, plan_in))
                        if plan_out is not None:
                            reqs.append(_text_cell(tab.sheet_id, i, C_OUT, plan_out))
                if reqs:
                    await self.client.batch(reqs)
                    found = True
            if found:
                log.info("📗 %s: вақти корманди %s дар ҷадвал → %s–%s", self.name, user_id, plan_in, plan_out)
            return found

    # ── ҳалқаи фонӣ (як ҷадвал; Manager ҳамин корро барои ҳама мекунад) ──

    def _log_error(self, text: str) -> None:
        prev, at = self._last_logged
        if text != prev or time.time() - at > 600:
            log.warning("📗 Google Sheet: %s", text)
            self._last_logged = (text, time.time())

    async def loop(self) -> None:
        await _run_loop(self, self.sync)


async def _run_loop(owner, sync) -> None:
    """Ҳар 5 сония: давомот иваз шуд ё GSHEET_INTERVAL гузашт → ҳамоҳангсозӣ (хато → backoff)."""
    STATE["running"] = True
    last_full, last_fp, backoff, next_try = 0.0, None, 0.0, 0.0
    try:
        while True:
            enabled = _setting_on("gsheet_enabled")
            STATE["enabled"] = enabled
            if enabled:
                now = time.monotonic()
                floor = shift_month(month_key(cfg.now().date()), -1) + "-01"
                try:
                    fp = db.attendance_fingerprint(floor)
                    due = owner.kicked.is_set() or fp != last_fp or now - last_full >= cfg.GSHEET_INTERVAL
                    if due and now >= next_try:
                        owner.kicked.clear()
                        await sync()
                        last_fp, last_full, backoff = fp, time.monotonic(), 0.0
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    text = str(exc) if isinstance(exc, SheetsError) else f"{type(exc).__name__}: {exc}"
                    STATE.update(ok=False, error=text[:400])
                    backoff = min(300.0, backoff * 2 or 15.0)
                    next_try = time.monotonic() + backoff
                    owner._log_error(text)
                    if not isinstance(exc, SheetsError):
                        log.debug("Google Sheet", exc_info=True)
            try:
                await asyncio.wait_for(owner.kicked.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
    finally:
        STATE["running"] = False


# ══════════════════════════════════════════════════════════════════════════
#  Филиалҳо (ҳар филиал — ҷадвали худ, сохтор якхела)
# ══════════════════════════════════════════════════════════════════════════

def sheet_url(sid: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sid}/edit"


def parse_sheet_id(text: str) -> str | None:
    text = (text or "").strip()
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})", text)
    if m:
        return m.group(1)
    return text if re.fullmatch(r"[A-Za-z0-9_-]{20,}", text) else None


def get_books() -> list[dict]:
    """[{id, name}] — аз панел; набошад — GSHEET_ID-и пешфарз."""
    raw = db.get_setting("gsheet_books")
    if raw is None:
        return [{"id": cfg.GSHEET_ID, "name": cfg.GSHEET_NAME}] if cfg.GSHEET_ID else []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and parse_sheet_id(str(item.get("id", ""))):
            out.append({"id": str(item["id"]), "name": str(item.get("name") or "Филиал")[:60]})
        elif isinstance(item, str) and parse_sheet_id(item):
            out.append({"id": item, "name": "Филиал"})
    return out


def save_books(books: list[dict]) -> None:
    db.set_settings({"gsheet_books": json.dumps(
        [{"id": b["id"], "name": b["name"]} for b in books], ensure_ascii=False)})


class Manager:
    """Ҳамаи ҷадвалҳо (филиалҳо) бо як калиди Google ва як ҳалқа."""

    def __init__(self, creds: Credentials, client_factory=None):
        self.creds = creds
        self.email = creds.email if creds else ""
        self._factory = client_factory or (lambda sid: Client(creds, sid))
        self.syncers: dict[str, Syncer] = {}
        self.lock = asyncio.Lock()
        self.kicked = asyncio.Event()
        self._last_logged = ("", 0.0)

    def syncer(self, book: dict) -> Syncer:
        s = self.syncers.get(book["id"])
        if s is None:
            s = Syncer(self._factory(book["id"]), book["id"], self.email, book.get("name", ""))
            self.syncers[book["id"]] = s
        s.name = book.get("name") or s.name
        return s

    def _log_error(self, text: str) -> None:
        prev, at = self._last_logged
        if text != prev or time.time() - at > 600:
            log.warning("📗 Google Sheet: %s", text)
            self._last_logged = (text, time.time())

    async def sync_all(self) -> dict:
        async with self.lock:
            books = get_books()
            plans: dict[int, tuple] = {}
            failed, errors = set(), []
            total = {"writes": 0, "conflicts": 0, "books": len(books)}
            STATE["last_try"] = cfg.now_str()
            for book in books:
                s = self.syncer(book)
                try:
                    async with s.lock:
                        result = await s._sync()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    failed.add(book["id"])
                    errors.append(f"{s.name}: {s.status.get('error') or exc}")
                    continue
                for uid, plan in result["plans"].items():
                    plans.setdefault(uid, plan)        # як корманд дар ду филиал → аввалин
                total["writes"] += result["writes"]
                total["conflicts"] += result["conflicts"]
            db.sync_sheet_plans(plans, keep_branches=failed)
            ids = {b["id"] for b in books}
            for sid in [k for k in self.syncers if k not in ids]:
                gone = self.syncers.pop(sid)
                try:
                    await gone.client.close()
                except Exception:
                    pass
            if errors:
                STATE.update(ok=False, error="; ".join(errors)[:400])
                raise SheetsError(STATE["error"])
            STATE.update(ok=True, error="", last_ok=cfg.now_str(), last_writes=total["writes"],
                         conflicts=total["conflicts"])
            return total

    async def loop(self) -> None:
        await _run_loop(self, self.sync_all)

    async def close(self) -> None:
        for s in self.syncers.values():
            try:
                await s.client.close()
            except Exception:
                pass


_MANAGER: Manager | None = None
_SYNCER: Syncer | None = None           # танҳо барои санҷишҳо (як ҷадвал)


def kick() -> None:
    """Тағйирот шуд — ҳарчи зудтар ҳамоҳанг кунем (аз панел/бот)."""
    if _MANAGER is not None:
        _MANAGER.kicked.set()
    elif _SYNCER is not None:
        _SYNCER.kicked.set()


def build() -> Manager | None:
    STATE["configured"] = False
    if not os.path.isfile(cfg.GSHEET_KEY_FILE):
        STATE["error"] = "Калиди Google (service account) дар сервер нест"
        return None
    try:
        creds = Credentials.from_file(cfg.GSHEET_KEY_FILE)
    except Exception as exc:
        STATE["error"] = f"Калиди Google хонда нашуд: {exc}"
        return None
    STATE.update(configured=True, email=creds.email, error="")
    return Manager(creds)


async def run_forever() -> None:
    """Зерсистемаи «sheets» (main.py). Агар калид набошад — ҳар 5 дақиқа аз нав месанҷад."""
    global _MANAGER
    while True:
        manager = build()
        if manager is None:
            await asyncio.sleep(300)
            continue
        _MANAGER = manager
        log.info("📗 Google Sheet: %d филиал (%s)", len(get_books()), manager.email)
        try:
            await manager.loop()
        finally:
            _MANAGER = None
            await manager.close()


# ══════════════════════════════════════════════════════════════════════════
#  Барои панел
# ══════════════════════════════════════════════════════════════════════════

def _pairs() -> list[tuple[dict, Syncer | None]]:
    if _MANAGER is not None:
        return [(b, _MANAGER.syncer(b)) for b in get_books()]
    if _SYNCER is not None:
        return [({"id": _SYNCER.sid, "name": _SYNCER.name}, _SYNCER)]
    return [(b, None) for b in get_books()]


def _syncer_for(book_id: str | None) -> Syncer:
    for book, s in _pairs():
        if s is not None and (book_id is None or book["id"] == book_id):
            return s
    raise SheetsError(STATE.get("error") or "Ҷадвали Google пайваст нест")


def panel_state() -> dict:
    emps = db.employees_brief()
    by_id = {e["user_id"]: e for e in emps}
    linked: set[int] = set()
    books = []
    for book, s in _pairs():
        snap = s.snapshot if s else None
        rows = []
        for r in (snap or {}).get("rows", []):
            item = dict(r)
            emp = by_id.get(r["user_id"]) if r["user_id"] else None
            item["employee"] = emp["name"] if emp else None
            item["unknown"] = bool(r["tg"]) and not emp and not r["dup"]
            if emp:
                linked.add(emp["user_id"])
            rows.append(item)
        status = dict(s.status) if s else {"ok": None, "error": STATE.get("error") or ""}
        named = [r for r in rows if r["name"]]
        books.append({
            "id": book["id"], "name": book["name"], "title": s.title if s else "",
            "url": sheet_url(book["id"]), "status": status,
            "tab": (snap or {}).get("tab"), "month": (snap or {}).get("month"),
            "since": (snap or {}).get("since") or db.get_setting(f"gsheet_since:{book['id']}"),
            "rows": rows, "total": len(named), "linked": sum(1 for r in named if r["user_id"]),
        })
    unlinked = [{"user_id": e["user_id"], "name": e["name"], "tg_name": e["tg_name"], "username": e["username"]}
                for e in emps if e["active"] and e["user_id"] not in linked]
    return {
        "configured": STATE["configured"],
        "enabled": _setting_on("gsheet_enabled"),
        "times": _setting_on("gsheet_times"),
        "only": _setting_on("gsheet_only"),
        "autolink": _setting_on("gsheet_autolink", "0"),
        "email": STATE["email"],
        "status": {k: STATE[k] for k in ("ok", "error", "running", "last_try", "last_ok", "last_write",
                                         "writes", "last_writes", "conflicts")},
        "books": books,
        "unlinked": unlinked,
        "employees": [{"user_id": e["user_id"], "name": e["name"], "tg_name": e["tg_name"],
                       "username": e["username"], "active": bool(e["active"]), "branch": e.get("branch")}
                      for e in emps],
    }


async def sync_now() -> dict:
    if _MANAGER is not None:
        return await asyncio.wait_for(_MANAGER.sync_all(), timeout=150)
    if _SYNCER is not None:
        return await asyncio.wait_for(_SYNCER.sync(), timeout=90)
    raise SheetsError(STATE.get("error") or "Ҷадвали Google пайваст нест")


async def link(row: int, name: str, user_id: int | None, book_id: str | None = None) -> None:
    s = _syncer_for(book_id)
    if _MANAGER is None:
        await asyncio.wait_for(s.link(row, name, user_id), timeout=90)
        return
    if user_id:                                 # як корманд — як филиал: аз филиали дигар тоза мекунем
        for book, other in _pairs():
            if other is not None and other is not s:
                try:
                    await other.unlink_user(int(user_id))
                except SheetsError:
                    pass
    await asyncio.wait_for(s.link(row, name, user_id, resync=False), timeout=90)
    await sync_now()


async def set_plan(user_id: int, plan_in: str | None, plan_out: str | None) -> bool:
    """Вақти кории корманд аз панел → ҷадвали филиали ӯ. False — корманд дар ҷадвал нест."""
    emp = db.get_employee(user_id)
    if not emp or not emp.get("branch"):
        return False
    s = _syncer_for(emp["branch"])
    ok = await asyncio.wait_for(s.set_plan(int(user_id), plan_in, plan_out), timeout=90)
    if ok:
        try:
            await sync_now()
        except SheetsError:
            pass
    return ok


async def check_book(text: str) -> dict:
    """Ҷадвали нави филиалро месанҷад: дастрасӣ ва сохтор. Бармегардонад {id, title, tab}."""
    sid = parse_sheet_id(text)
    if not sid:
        raise SheetsError("Суроғаи ҷадвал нодуруст аст — суроғаи пурраи docs.google.com/spreadsheets/d/… -ро гузоред")
    if _MANAGER is None:
        raise SheetsError(STATE.get("error") or "Калиди Google дар сервер нест")
    s = Syncer(_MANAGER._factory(sid), sid, _MANAGER.email)
    try:
        tabs = await s.tabs()
        for tab in sorted((t for t in tabs if not t.hidden), key=lambda t: -t.index):
            if layout_ok(await s.client.values(tab.title, f"A1:{col_name(C_RESULT)}3")):
                return {"id": sid, "title": s.title, "tab": tab.title}
        raise SheetsError("Дар ин ҷадвал варақе бо сохтори «Номи Корманд / Телеграм id / Омад / Рафт» нест")
    finally:
        await s.client.close()
