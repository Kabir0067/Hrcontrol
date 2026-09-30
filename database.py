"""
SoftClub / Hrcontrol — қабати база (SQLite).

Принсипҳо:
  • ҳамаи миграцияҳо идемпотентанд ва маълумоти мавҷударо нигоҳ медоранд;
  • ҳолати корбар (user_state) дар база нигоҳ дошта мешавад — restart-и бот
    равандҳои нотамомро вайрон намекунад;
  • оморҳо бо як-ду запрос ҳисоб мешаванд, на бо ҳалқаи N-запросӣ;
  • давомот: як корманд — як сабт дар як рӯз (UNIQUE), бинобар ин restart ё
    коркарди такрорӣ ҳеҷ гоҳ саволи дуюм намефиристад.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Iterator, Optional

import config as cfg

log = logging.getLogger("SoftClubBot")

DB_PATH = cfg.DB_PATH

REQ_TYPES = ("late", "absent", "at_work_waiting", "leaving_early")
REQ_STATUSES = ("pending", "accepted", "rejected", "cancelled")
ATT_STATUSES = ("pending", "present", "absent", "leave")
ATT_STATES = ("on_time", "late", "absent", "leave", "pending")

DEFAULT_WORK_DAYS = (0, 1, 2, 3, 4, 5)          # душанбе…шанбе; якшанбе — истироҳат


# ──────────────────────────────────────────────────────────────────────────
#  Пайвастшавӣ
# ──────────────────────────────────────────────────────────────────────────

def _lower(value):
    return value.lower() if isinstance(value, str) else value


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    # LIKE-и SQLite танҳо лотиниро бе фарқи ҳарф меҷӯяд; «Али» = «али» барои кириллӣ.
    conn.create_function("ulower", 1, _lower, deterministic=True)
    return conn


@contextmanager
def _tx() -> Iterator[sqlite3.Connection]:
    """Транзаксия бо commit/rollback ва пӯшидани кафолатнок."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def _ro() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def _rows(cur: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in cur]


# ──────────────────────────────────────────────────────────────────────────
#  Схема ва миграцияҳо
# ──────────────────────────────────────────────────────────────────────────

_ATTENDANCE_COLUMNS = """
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    work_date    TEXT    NOT NULL,
    scheduled_at TEXT    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'pending'
                         CHECK(status IN ('pending','present','absent','leave')),
    prompted_at  TEXT,
    reminded_at  TEXT,
    msg_id       INTEGER,
    arrived_at   TEXT,
    reason       TEXT,
    eta          TEXT,
    source       TEXT    NOT NULL DEFAULT 'bot',
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL,
    UNIQUE(user_id, work_date)
"""

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS requests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL,
    name             TEXT    NOT NULL,
    type             TEXT    NOT NULL CHECK(type IN ('late','absent','at_work_waiting','leaving_early')),
    reason           TEXT    NOT NULL,
    minutes          INTEGER NOT NULL DEFAULT 0,
    status           TEXT    NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected','cancelled')),
    group_msg_id     INTEGER,
    reminder_sent    INTEGER NOT NULL DEFAULT 0,
    worker_confirmed TEXT    DEFAULT NULL CHECK(worker_confirmed IN (NULL, 'yes', 'no')),
    created_at       TEXT    NOT NULL,
    deadline_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_requests_status   ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_reminder ON requests(status, reminder_sent, deadline_at);
CREATE INDEX IF NOT EXISTS idx_requests_user     ON requests(user_id);
CREATE INDEX IF NOT EXISTS idx_requests_created  ON requests(created_at);

CREATE TABLE IF NOT EXISTS arrival_checks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id    INTEGER NOT NULL REFERENCES requests(id),
    user_id       INTEGER NOT NULL,
    check_at      TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'pending'
                          CHECK(status IN ('pending','arrived','delayed','expired')),
    delay_reason  TEXT,
    extra_minutes INTEGER DEFAULT 0,
    asked         INTEGER NOT NULL DEFAULT 0,
    ask_msg_id    INTEGER,
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_checks_pending ON arrival_checks(status, asked, check_at);
CREATE INDEX IF NOT EXISTS idx_checks_user    ON arrival_checks(user_id, status);

CREATE TABLE IF NOT EXISTS user_states (
    user_id    INTEGER PRIMARY KEY,
    data       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
    user_id    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    username   TEXT,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    alias      TEXT,
    active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Давомоти ҳаррӯза. Аз дархостҳои «дер мекунам» ҷудо аст:
-- як корманд барои як рӯзи корӣ танҳо як сабт дорад.
CREATE TABLE IF NOT EXISTS attendance ({_ATTENDANCE_COLUMNS});

CREATE INDEX IF NOT EXISTS idx_attendance_period  ON attendance(work_date, user_id);
CREATE INDEX IF NOT EXISTS idx_attendance_pending ON attendance(status, prompted_at);

-- Рӯзҳои истироҳати иловагӣ (идҳо ва ғ.) — дар ин рӯзҳо савол намеравад.
CREATE TABLE IF NOT EXISTS days_off (
    work_date  TEXT PRIMARY KEY,
    title      TEXT,
    created_at TEXT NOT NULL
);
"""

# Сутунҳое, ки метавонанд дар базаи кӯҳна набошанд.
_EXTRA_COLUMNS = {
    "requests": {
        "decided_by":    "TEXT",
        "decided_at":    "TEXT",
        "worker_msg_id": "INTEGER",
        "confirmed_at":  "TEXT",
    },
    "employees": {
        "alias":  "TEXT",
        "active": "INTEGER NOT NULL DEFAULT 1",
    },
    "attendance": {
        "reminded_at": "TEXT",
        "msg_id":      "INTEGER",
        "source":      "TEXT NOT NULL DEFAULT 'bot'",
    },
}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _migrate_cancelled_status(conn: sqlite3.Connection) -> None:
    """Базаҳои хеле кӯҳна вазъияти 'cancelled'-ро дар CHECK надоштанд."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='requests'"
    ).fetchone()
    if not row or not row["sql"] or "'cancelled'" in row["sql"]:
        return

    log.info("🔧 Миграция: илова кардани вазъияти 'cancelled'…")
    cols = _table_columns(conn, "requests")
    keep = [c for c in (
        "id", "user_id", "name", "type", "reason", "minutes", "status",
        "group_msg_id", "reminder_sent", "worker_confirmed",
        "created_at", "deadline_at",
    ) if c in cols]
    col_list = ", ".join(keep)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.executescript(f"""
        CREATE TABLE requests_new (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            name             TEXT    NOT NULL,
            type             TEXT    NOT NULL CHECK(type IN ('late','absent','at_work_waiting','leaving_early')),
            reason           TEXT    NOT NULL,
            minutes          INTEGER NOT NULL DEFAULT 0,
            status           TEXT    NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected','cancelled')),
            group_msg_id     INTEGER,
            reminder_sent    INTEGER NOT NULL DEFAULT 0,
            worker_confirmed TEXT    DEFAULT NULL CHECK(worker_confirmed IN (NULL, 'yes', 'no')),
            created_at       TEXT    NOT NULL,
            deadline_at      TEXT
        );
        INSERT INTO requests_new ({col_list}) SELECT {col_list} FROM requests;
        DROP TABLE requests;
        ALTER TABLE requests_new RENAME TO requests;
    """)
    conn.execute("PRAGMA foreign_keys=ON")
    log.info("✅ Миграцияи 'cancelled' анҷом ёфт.")


def _migrate_attendance_status(conn: sqlite3.Connection) -> None:
    """Версияи аввали ҷадвали attendance вазъияти 'leave' (рухсатӣ) надошт."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='attendance'"
    ).fetchone()
    if not row or not row["sql"] or "'leave'" in row["sql"]:
        return

    log.info("🔧 Миграция: ҷадвали давомот (вазъияти 'leave')…")
    new_cols = {
        "id", "user_id", "name", "work_date", "scheduled_at", "status", "prompted_at",
        "reminded_at", "msg_id", "arrived_at", "reason", "eta", "source",
        "created_at", "updated_at",
    }
    keep = ", ".join(sorted(_table_columns(conn, "attendance") & new_cols))
    conn.execute(f"CREATE TABLE attendance_new ({_ATTENDANCE_COLUMNS})")
    conn.execute(f"INSERT INTO attendance_new ({keep}) SELECT {keep} FROM attendance")
    conn.execute("DROP TABLE attendance")
    conn.execute("ALTER TABLE attendance_new RENAME TO attendance")
    log.info("✅ Миграцияи давомот анҷом ёфт.")


def _migrate_columns(conn: sqlite3.Connection) -> None:
    for table, columns in _EXTRA_COLUMNS.items():
        existing = _table_columns(conn, table)
        if not existing:
            continue
        for col, decl in columns.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
                log.info("🔧 Сутуни нав: %s.%s", table, col)


def init_db() -> None:
    with _tx() as conn:
        _migrate_cancelled_status(conn)
        _migrate_columns(conn)
        _migrate_attendance_status(conn)
        conn.executescript(_SCHEMA)
        _migrate_columns(conn)
    log.info("✅ База тайёр: %s", DB_PATH)


def healthcheck() -> dict:
    """Барои /api/health — санҷиши зинда будани база."""
    try:
        with _ro() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"]
        return {"ok": True, "requests": total}
    except Exception as exc:                       # pragma: no cover
        return {"ok": False, "error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────
#  Ҳолати корбар (устувор ба restart)
# ──────────────────────────────────────────────────────────────────────────

def get_state(user_id: int) -> Optional[dict]:
    with _ro() as conn:
        row = conn.execute(
            "SELECT data, updated_at FROM user_states WHERE user_id = ?", (user_id,)
        ).fetchone()
    if not row:
        return None

    updated = cfg.parse_dt(row["updated_at"])
    if updated and (cfg.now() - updated).total_seconds() > cfg.STATE_TTL:
        clear_state(user_id)
        return None

    try:
        data = json.loads(row["data"])
        return data if isinstance(data, dict) else None
    except (ValueError, TypeError):
        clear_state(user_id)
        return None


def set_state(user_id: int, data: dict) -> None:
    payload = json.dumps(data, ensure_ascii=False)
    with _tx() as conn:
        conn.execute(
            """
            INSERT INTO user_states (user_id, data, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET data = excluded.data,
                                               updated_at = excluded.updated_at
            """,
            (user_id, payload, cfg.now_str()),
        )


def clear_state(user_id: int) -> Optional[dict]:
    previous = None
    with _tx() as conn:
        row = conn.execute(
            "SELECT data FROM user_states WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            try:
                previous = json.loads(row["data"])
            except (ValueError, TypeError):
                previous = None
            conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
    return previous


def purge_stale_states() -> int:
    cutoff = cfg.to_str(cfg.now() - timedelta(seconds=cfg.STATE_TTL))
    with _tx() as conn:
        cur = conn.execute("DELETE FROM user_states WHERE updated_at < ?", (cutoff,))
        return cur.rowcount or 0


# ──────────────────────────────────────────────────────────────────────────
#  Кормандон
# ──────────────────────────────────────────────────────────────────────────

# Номе, ки админ гузоштааст, аз номи Telegram афзалият дорад.
_EMP_NAME = "COALESCE(NULLIF(TRIM(e.alias), ''), e.name)"


def touch_employee(user_id: int, name: str, username: str | None) -> None:
    stamp = cfg.now_str()
    with _tx() as conn:
        conn.execute(
            """
            INSERT INTO employees (user_id, name, username, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET name      = excluded.name,
                                               username  = excluded.username,
                                               last_seen = excluded.last_seen
            """,
            (user_id, name, username, stamp, stamp),
        )


def get_employee(user_id: int) -> Optional[dict]:
    with _ro() as conn:
        row = conn.execute(
            f"SELECT e.*, {_EMP_NAME} AS display FROM employees e WHERE e.user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def list_employees() -> list[dict]:
    """Ҳамаи кормандон бо шумораи дархостҳо ва давомоти моҳи кории ҷорӣ."""
    start, end = work_period()
    with _ro() as conn:
        rows = _rows(conn.execute(
            f"""
            SELECT e.user_id, e.name, e.username, e.alias, e.active,
                   e.first_seen, e.last_seen, {_EMP_NAME} AS display,
                   (SELECT COUNT(*) FROM requests r WHERE r.user_id = e.user_id) AS requests,
                   (SELECT COUNT(*) FROM requests r WHERE r.user_id = e.user_id
                                                     AND r.status = 'pending') AS pending
              FROM employees e
             ORDER BY e.active DESC, display COLLATE NOCASE
            """
        ))
        att = conn.execute(
            "SELECT * FROM attendance WHERE work_date >= ? AND work_date <= ?", (start, end)
        ).fetchall()
    grace = get_schedule()["grace"]
    per: dict[int, list[dict]] = {}
    for rec in att:
        per.setdefault(rec["user_id"], []).append(_cell(dict(rec), grace))
    for row in rows:
        row["active"] = bool(row["active"])
        row["month"] = _summarize(per.get(row["user_id"], []))
    return rows


def update_employee(user_id: int, alias: str | None = None, active: bool | None = None) -> bool:
    sets, params = [], []
    if alias is not None:
        sets.append("alias = ?")
        params.append(alias.strip()[:80] or None)
    if active is not None:
        sets.append("active = ?")
        params.append(1 if active else 0)
    if not sets:
        return False
    with _tx() as conn:
        cur = conn.execute(f"UPDATE employees SET {', '.join(sets)} WHERE user_id = ?",
                           params + [int(user_id)])
        changed = cur.rowcount > 0
    if changed:
        log.info("👤 Корманд %s навсозӣ шуд (%s)", user_id, ", ".join(sets))
    return changed


# ──────────────────────────────────────────────────────────────────────────
#  Дархостҳо
# ──────────────────────────────────────────────────────────────────────────

def add_request(user_id: int, name: str, req_type: str, reason: str, minutes: int) -> int:
    created_at = cfg.now_str()
    deadline_at = cfg.plus_minutes(minutes) if minutes > 0 else None

    with _tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO requests
                (user_id, name, type, reason, minutes, status,
                 reminder_sent, created_at, deadline_at)
            VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?)
            """,
            (user_id, name, req_type, reason, minutes, created_at, deadline_at),
        )
        req_id = int(cur.lastrowid)

    log.info("📝 Дархости #%d аз %s (%s, %d дақ.)", req_id, name, req_type, minutes)
    return req_id


def get_request(req_id: int) -> Optional[dict]:
    with _ro() as conn:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    return dict(row) if row else None


def update_status(req_id: int, status: str, decided_by: str | None = None) -> bool:
    """Танҳо аз 'pending' иваз мешавад — муҳофизат аз ду бор пахш кардан."""
    with _tx() as conn:
        cur = conn.execute(
            """
            UPDATE requests
               SET status = ?, decided_by = ?, decided_at = ?
             WHERE id = ? AND status = 'pending'
            """,
            (status, decided_by, cfg.now_str(), req_id),
        )
        changed = cur.rowcount > 0
    if changed:
        log.info("🔄 Дархост #%d → %s (%s)", req_id, status, decided_by or "—")
    return changed


def cancel_request(req_id: int) -> bool:
    with _tx() as conn:
        cur = conn.execute(
            "UPDATE requests SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
            (req_id,),
        )
        changed = cur.rowcount > 0
    if changed:
        log.info("🚫 Дархост #%d аз ҷониби ҳамкор бекор шуд", req_id)
    return changed


def update_group_msg_id(req_id: int, msg_id: int) -> None:
    with _tx() as conn:
        conn.execute("UPDATE requests SET group_msg_id = ? WHERE id = ?", (msg_id, req_id))


def update_worker_msg_id(req_id: int, msg_id: int) -> None:
    with _tx() as conn:
        conn.execute("UPDATE requests SET worker_msg_id = ? WHERE id = ?", (msg_id, req_id))


def get_open_requests(user_id: int) -> list[dict]:
    with _ro() as conn:
        return _rows(conn.execute(
            "SELECT * FROM requests WHERE user_id = ? AND status = 'pending' ORDER BY id DESC",
            (user_id,),
        ))


def get_user_requests(user_id: int, limit: int = 5) -> list[dict]:
    with _ro() as conn:
        return _rows(conn.execute(
            "SELECT * FROM requests WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ))


def mark_reminder_sent(req_id: int) -> None:
    with _tx() as conn:
        conn.execute("UPDATE requests SET reminder_sent = 1 WHERE id = ?", (req_id,))


def update_worker_confirmation(req_id: int, answer: str) -> bool:
    with _tx() as conn:
        cur = conn.execute(
            """
            UPDATE requests SET worker_confirmed = ?, confirmed_at = ?
             WHERE id = ? AND worker_confirmed IS NULL
            """,
            (answer, cfg.now_str(), req_id),
        )
        return cur.rowcount > 0


def _stale_floor() -> str:
    """Кӯҳнатар аз ин — сарфи назар мешавад (муҳофизат аз спами таърихӣ)."""
    return cfg.to_str(cfg.now() - timedelta(minutes=cfg.STALE_AFTER))


def get_pending_reminders() -> list[dict]:
    """
    Дархостҳое, ки вақташон қариб тамом мешавад.

    Тирезаи васеъ (то `STALE_AFTER` дақиқа қафо) — агар бот чанд дақиқа хомӯш
    буда бошад, ёдоварӣ ҳамон вақти баргаштан меравад, на ин ки гум шавад.
    Вале сабтҳои хеле кӯҳна ба ҳеҷ ваҷҳ ба навбат намеафтанд.
    """
    with _ro() as conn:
        return _rows(conn.execute(
            """
            SELECT * FROM requests
             WHERE status = 'accepted'
               AND reminder_sent = 0
               AND deadline_at IS NOT NULL
               AND deadline_at <= ?
               AND deadline_at >= ?
             ORDER BY deadline_at
            """,
            (cfg.plus_minutes(cfg.REMINDER_LEAD), _stale_floor()),
        ))


def get_overdue_unconfirmed() -> list[dict]:
    with _ro() as conn:
        return _rows(conn.execute(
            """
            SELECT * FROM requests
             WHERE status = 'accepted'
               AND reminder_sent = 1
               AND worker_confirmed IS NULL
               AND deadline_at IS NOT NULL
               AND deadline_at < ?
               AND deadline_at >= ?
             ORDER BY deadline_at
            """,
            (cfg.now_str(), _stale_floor()),
        ))


# ──────────────────────────────────────────────────────────────────────────
#  Санҷиши омадан (arrival checks)
# ──────────────────────────────────────────────────────────────────────────

def create_arrival_check(request_id: int, user_id: int, check_at: str) -> int:
    with _tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO arrival_checks
                (request_id, user_id, check_at, status, asked, created_at)
            VALUES (?, ?, ?, 'pending', 0, ?)
            """,
            (request_id, user_id, check_at, cfg.now_str()),
        )
        check_id = int(cur.lastrowid)
    log.info("🔄 Arrival check #%d (дархост #%d, %s)", check_id, request_id, check_at)
    return check_id


_CHECK_JOIN = """
    SELECT ac.*, r.name, r.type, r.reason, r.minutes AS orig_minutes
      FROM arrival_checks ac
      JOIN requests r ON r.id = ac.request_id
"""


def get_pending_arrival_checks() -> list[dict]:
    with _ro() as conn:
        return _rows(conn.execute(
            _CHECK_JOIN + """
             WHERE ac.status = 'pending' AND ac.asked = 0
               AND ac.check_at <= ? AND ac.check_at >= ?
               AND r.status = 'accepted'
             ORDER BY ac.check_at
            """,
            (cfg.now_str(), _stale_floor()),
        ))


def get_arrival_check(check_id: int) -> Optional[dict]:
    with _ro() as conn:
        row = conn.execute(_CHECK_JOIN + " WHERE ac.id = ?", (check_id,)).fetchone()
    return dict(row) if row else None


def get_active_check_for_user(user_id: int) -> Optional[dict]:
    with _ro() as conn:
        row = conn.execute(
            _CHECK_JOIN + """
             WHERE ac.user_id = ? AND ac.status = 'pending' AND ac.asked = 1
             ORDER BY ac.id DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def mark_check_asked(check_id: int, msg_id: int) -> None:
    with _tx() as conn:
        conn.execute(
            "UPDATE arrival_checks SET asked = 1, ask_msg_id = ? WHERE id = ?",
            (msg_id, check_id),
        )


def set_check_arrived(check_id: int) -> bool:
    with _tx() as conn:
        cur = conn.execute(
            "UPDATE arrival_checks SET status = 'arrived' WHERE id = ? AND status = 'pending'",
            (check_id,),
        )
        return cur.rowcount > 0


def set_check_delayed(check_id: int, reason: str, extra_minutes: int) -> bool:
    with _tx() as conn:
        cur = conn.execute(
            """
            UPDATE arrival_checks
               SET status = 'delayed', delay_reason = ?, extra_minutes = ?
             WHERE id = ? AND status = 'pending'
            """,
            (reason, extra_minutes, check_id),
        )
        return cur.rowcount > 0


# ──────────────────────────────────────────────────────────────────────────
#  Танзимот (логин/рамзи панел, вақти корӣ ва ғ.)
# ──────────────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str | None = None) -> str | None:
    with _ro() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_settings(values: dict[str, str]) -> None:
    stamp = cfg.now_str()
    with _tx() as conn:
        for key, value in values.items():
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                               updated_at = excluded.updated_at
                """,
                (key, str(value), stamp),
            )


# ──────────────────────────────────────────────────────────────────────────
#  Вақти корӣ ва моҳи корӣ
# ──────────────────────────────────────────────────────────────────────────

def _valid_clock(value: str | None) -> str:
    value = (value or "").strip()
    try:
        hour, minute = (int(x) for x in value.split(":"))
    except (TypeError, ValueError):
        return ""
    if len(value) == 5 and 0 <= hour < 24 and 0 <= minute < 60:
        return value
    return ""


def get_schedule() -> dict:
    """{time: "08:30" | "", days: [0..6], grace: 10, report: True, enabled: bool}"""
    with _ro() as conn:
        raw = {r["key"]: r["value"] for r in conn.execute(
            "SELECT key, value FROM settings WHERE key IN "
            "('work_start_time', 'work_days', 'work_grace', 'daily_report')")}
    time_ = _valid_clock(raw.get("work_start_time"))
    try:
        days = sorted({int(x) for x in str(raw["work_days"]).split(",") if x.strip() != ""
                       and 0 <= int(x) <= 6})
    except (KeyError, ValueError):
        days = list(DEFAULT_WORK_DAYS)
    try:
        grace = max(0, min(int(raw.get("work_grace", cfg.DEFAULT_GRACE)), 120))
    except (TypeError, ValueError):
        grace = cfg.DEFAULT_GRACE
    report = str(raw.get("daily_report", "1")) != "0"
    return {"time": time_, "days": days, "grace": grace, "report": report,
            "enabled": bool(time_)}


def set_schedule(time: str | None = None, days: Iterable[int] | None = None,
                 grace: int | None = None, report: bool | None = None) -> dict:
    values: dict[str, str] = {}
    if time is not None:
        values["work_start_time"] = _valid_clock(time)
    if days is not None:
        values["work_days"] = ",".join(str(d) for d in sorted({int(d) for d in days if 0 <= int(d) <= 6}))
    if grace is not None:
        values["work_grace"] = str(max(0, min(int(grace), 120)))
    if report is not None:
        values["daily_report"] = "1" if report else "0"
    if values:
        set_settings(values)
        log.info("🕐 Вақти корӣ навсозӣ шуд: %s", values)
    return get_schedule()


# Мутобиқат бо версияи қаблӣ
def get_work_start_time() -> str:
    return get_schedule()["time"]


def set_work_start_time(value: str) -> None:
    set_schedule(time=value)


def work_period(anchor: str | None = None) -> tuple[str, str]:
    """Моҳи корӣ: аз рӯзи 5 то рӯзи 4-уми моҳи баъдӣ. anchor = "YYYY-MM" (моҳи оғоз)."""
    start = None
    if anchor:
        try:
            src = datetime.strptime(anchor, "%Y-%m").date()
            start = date(src.year, src.month, 5)
        except (TypeError, ValueError):
            start = None
    if start is None:
        today = cfg.now().date()
        if today.day >= 5:
            start = date(today.year, today.month, 5)
        elif today.month == 1:
            start = date(today.year - 1, 12, 5)
        else:
            start = date(today.year, today.month - 1, 5)
    nxt = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 5)
    return start.isoformat(), (nxt - timedelta(days=1)).isoformat()


def _shift_month(key: str, delta: int) -> str:
    y, m = (int(x) for x in key.split("-"))
    m += delta
    while m < 1:
        y, m = y - 1, m + 12
    while m > 12:
        y, m = y + 1, m - 12
    return f"{y:04d}-{m:02d}"


def get_days_off(date_from: str, date_to: str) -> dict[str, str]:
    with _ro() as conn:
        return {r["work_date"]: r["title"] or "" for r in conn.execute(
            "SELECT work_date, title FROM days_off WHERE work_date >= ? AND work_date <= ?",
            (date_from, date_to))}


def set_day_off(work_date: str, off: bool, title: str = "") -> None:
    with _tx() as conn:
        if off:
            conn.execute(
                """INSERT INTO days_off (work_date, title, created_at) VALUES (?, ?, ?)
                   ON CONFLICT(work_date) DO UPDATE SET title = excluded.title""",
                (work_date, title.strip()[:80], cfg.now_str()))
        else:
            conn.execute("DELETE FROM days_off WHERE work_date = ?", (work_date,))
    log.info("📅 %s: %s", work_date, f"рӯзи истироҳат ({title})" if off else "рӯзи корӣ")


def is_workday(day: date, schedule: dict | None = None, offs: dict | None = None) -> bool:
    schedule = schedule or get_schedule()
    iso = day.isoformat()
    if offs is None:
        offs = get_days_off(iso, iso)
    return day.weekday() in schedule["days"] and iso not in offs


def _scheduled_for(day: str, clock: str) -> str:
    return f"{day} {clock or '00:00'}:00"


# ──────────────────────────────────────────────────────────────────────────
#  Давомот: ҳисоби ҳолат
# ──────────────────────────────────────────────────────────────────────────

def _clock(value: str | None) -> str:
    dt = cfg.parse_dt(value)
    return dt.strftime("%H:%M") if dt else ""


def _late_minutes(rec: dict) -> int:
    arrived = cfg.parse_dt(rec.get("arrived_at"))
    planned = cfg.parse_dt(rec.get("scheduled_at"))
    if not arrived or not planned:
        return 0
    return max(0, int((arrived - planned).total_seconds() // 60))


def att_state(rec: dict, grace: int) -> str:
    """on_time · late · absent · leave · pending"""
    if rec["status"] == "present":
        return "late" if _late_minutes(rec) > grace else "on_time"
    return rec["status"]


def _cell(rec: dict, grace: int) -> dict:
    state = att_state(rec, grace)
    return {
        "id": rec["id"],
        "date": rec["work_date"],
        "s": state,
        "t": _clock(rec.get("arrived_at")),
        "late": _late_minutes(rec) if state == "late" else 0,
        "reason": rec.get("reason") or "",
        "eta": rec.get("eta") or "",
        "src": rec.get("source") or "bot",
        "sched": _clock(rec.get("scheduled_at")),
    }


def _summarize(cells: list[dict]) -> dict:
    s = {k: 0 for k in ATT_STATES}
    s["late_minutes"] = 0
    arrivals = []
    for c in cells:
        s[c["s"]] = s.get(c["s"], 0) + 1
        s["late_minutes"] += c["late"]
        if c["t"]:
            h, m = (int(x) for x in c["t"].split(":"))
            arrivals.append(h * 60 + m)
    present = s["on_time"] + s["late"]
    asked = present + s["absent"] + s["pending"]
    s["present"] = present
    s["days"] = len(cells)
    s["rate"] = round(100 * present / asked) if asked else None
    s["punctuality"] = round(100 * s["on_time"] / present) if present else None
    if arrivals:
        avg = round(sum(arrivals) / len(arrivals))
        s["avg_arrival"] = f"{avg // 60:02d}:{avg % 60:02d}"
    else:
        s["avg_arrival"] = None
    return s


# ──────────────────────────────────────────────────────────────────────────
#  Давомот: бот
# ──────────────────────────────────────────────────────────────────────────

def create_due_attendance() -> list[dict]:
    """Сабтҳои имрӯзаро месозад ва онҳоеро бармегардонад, ки бояд пурсида шаванд.

    • UNIQUE(user_id, work_date) — restart ё чанд даъвати ҳамзамон бехатар;
    • танҳо рӯзҳои корӣ (якшанбе ва идҳо — не);
    • танҳо дар тирезаи ATTENDANCE_WINDOW пас аз оғози кор;
    • кормандоне, ки имрӯз «намеоям/дер мекунам» фиристодаанд, савол намегиранд —
      сабабашон аз дархост гирифта мешавад.
    """
    sch = get_schedule()
    now = cfg.now()
    if not sch["enabled"] or not is_workday(now.date(), sch):
        return []
    hour, minute = (int(x) for x in sch["time"].split(":"))
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now < scheduled or now - scheduled > timedelta(minutes=cfg.ATTENDANCE_WINDOW):
        return []

    day = now.strftime(cfg.DATE_FMT)
    scheduled_at = cfg.to_str(scheduled)
    stamp = cfg.now_str()
    with _tx() as conn:
        employees = _rows(conn.execute(
            f"SELECT e.user_id, {_EMP_NAME} AS name FROM employees e WHERE e.active = 1"))
        for emp in employees:
            conn.execute(
                """
                INSERT OR IGNORE INTO attendance
                    (user_id, name, work_date, scheduled_at, status, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', 'bot', ?, ?)
                """,
                (emp["user_id"], emp["name"], day, scheduled_at, stamp, stamp),
            )
        # Дархостҳои имрӯзаи «намеоям / дер мекунам» — савол лозим нест
        for req in conn.execute(
            """SELECT user_id, type, reason, deadline_at FROM requests
                WHERE created_at >= ? AND type IN ('absent', 'late')
                  AND status IN ('pending', 'accepted') ORDER BY id""",
            (f"{day} 00:00:00",),
        ):
            conn.execute(
                """UPDATE attendance
                      SET status = 'absent', reason = ?, eta = ?, source = 'request',
                          prompted_at = ?, updated_at = ?
                    WHERE user_id = ? AND work_date = ? AND status = 'pending'
                      AND prompted_at IS NULL""",
                (req["reason"], _request_eta(req["type"], req["deadline_at"]),
                 stamp, stamp, req["user_id"], day),
            )
        rows = _rows(conn.execute(
            """SELECT * FROM attendance
                WHERE work_date = ? AND status = 'pending' AND prompted_at IS NULL
                ORDER BY id""",
            (day,),
        ))
    return rows


def _request_eta(req_type: str, deadline_at: str | None) -> str:
    if req_type == "absent":
        return "Имрӯз намеояд"
    clock = _clock(deadline_at)
    return f"то соати {clock}" if clock else ""


def mark_attendance_prompted(attendance_id: int, msg_id: int | None = None) -> bool:
    """True танҳо барои даъвати аввал — ҳимоя аз саволи дукарата."""
    stamp = cfg.now_str()
    with _tx() as conn:
        cur = conn.execute(
            """UPDATE attendance SET prompted_at = ?, msg_id = ?, updated_at = ?
                WHERE id = ? AND prompted_at IS NULL""",
            (stamp, msg_id, stamp, attendance_id),
        )
        return cur.rowcount > 0


def set_attendance_msg(attendance_id: int, msg_id: int) -> None:
    with _tx() as conn:
        conn.execute("UPDATE attendance SET msg_id = ? WHERE id = ?", (msg_id, attendance_id))


def get_attendance_to_remind() -> list[dict]:
    """Онҳое, ки савол гирифтанд, вале ATTENDANCE_REMIND дақиқа ҷавоб надоданд (як бор)."""
    cutoff = cfg.to_str(cfg.now() - timedelta(minutes=cfg.ATTENDANCE_REMIND))
    with _ro() as conn:
        return _rows(conn.execute(
            """SELECT * FROM attendance
                WHERE work_date = ? AND status = 'pending' AND msg_id IS NOT NULL
                  AND reminded_at IS NULL AND prompted_at IS NOT NULL AND prompted_at <= ?
                ORDER BY id""",
            (cfg.today_str(), cutoff),
        ))


def mark_attendance_reminded(attendance_id: int) -> None:
    with _tx() as conn:
        conn.execute("UPDATE attendance SET reminded_at = ? WHERE id = ?",
                     (cfg.now_str(), attendance_id))


def get_attendance(attendance_id: int) -> Optional[dict]:
    with _ro() as conn:
        row = conn.execute("SELECT * FROM attendance WHERE id = ?", (attendance_id,)).fetchone()
    return dict(row) if row else None


def get_today_attendance(user_id: int) -> Optional[dict]:
    with _ro() as conn:
        row = conn.execute("SELECT * FROM attendance WHERE user_id = ? AND work_date = ?",
                           (user_id, cfg.today_str())).fetchone()
    return dict(row) if row else None


def set_attendance_present(attendance_id: int) -> bool:
    """Омадан сабт мешавад (аз «интизорӣ» ё «наомад» — масалан, дертар омад)."""
    stamp = cfg.now_str()
    with _tx() as conn:
        cur = conn.execute(
            """UPDATE attendance SET status = 'present', arrived_at = ?, updated_at = ?
                WHERE id = ? AND status IN ('pending', 'absent')""",
            (stamp, stamp, attendance_id),
        )
        return cur.rowcount > 0


def set_attendance_absent(attendance_id: int, reason: str, eta: str) -> bool:
    with _tx() as conn:
        cur = conn.execute(
            """UPDATE attendance SET status = 'absent', reason = ?, eta = ?, updated_at = ?
                WHERE id = ? AND status IN ('pending', 'absent')""",
            (reason.strip()[:1000], eta.strip()[:300], cfg.now_str(), attendance_id),
        )
        return cur.rowcount > 0


def attendance_from_request(user_id: int, req_type: str, reason: str,
                            deadline_at: str | None) -> Optional[dict]:
    """Корманд «намеоям / дер мекунам» фиристод → давомоти имрӯз «наомад» бо сабаб.

    Бармегардонад сабти навсозишуда (барои пок кардани тугмаҳои саволи субҳ) ё None.
    """
    if req_type not in ("absent", "late"):
        return None
    sch = get_schedule()
    today = cfg.now().date()
    if not sch["enabled"] or not is_workday(today, sch):
        return None
    emp = get_employee(user_id)
    if not emp or not emp["active"]:
        return None

    day = today.isoformat()
    stamp = cfg.now_str()
    eta = _request_eta(req_type, deadline_at)
    with _tx() as conn:
        row = conn.execute("SELECT * FROM attendance WHERE user_id = ? AND work_date = ?",
                           (user_id, day)).fetchone()
        if row is None:
            conn.execute(
                """INSERT INTO attendance
                       (user_id, name, work_date, scheduled_at, status, prompted_at,
                        reason, eta, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'absent', ?, ?, ?, 'request', ?, ?)""",
                (user_id, emp["display"], day, _scheduled_for(day, sch["time"]), stamp,
                 reason[:1000], eta, stamp, stamp),
            )
        elif row["status"] == "pending":
            conn.execute(
                """UPDATE attendance SET status = 'absent', reason = ?, eta = ?,
                          source = 'request', prompted_at = COALESCE(prompted_at, ?),
                          updated_at = ?
                    WHERE id = ?""",
                (reason[:1000], eta, stamp, stamp, row["id"]),
            )
        else:
            return None
        rec = conn.execute("SELECT * FROM attendance WHERE user_id = ? AND work_date = ?",
                           (user_id, day)).fetchone()
    return dict(rec) if rec else None


def attendance_mark_arrived(user_id: int) -> Optional[dict]:
    """Корманд тасдиқ кард, ки расид (аз санҷиши «дер мекунам» ё тугмаи «Омадам»)."""
    rec = get_today_attendance(user_id)
    if not rec or rec["status"] not in ("pending", "absent"):
        return None
    if not set_attendance_present(rec["id"]):
        return None
    return get_attendance(rec["id"])


def daily_report_due() -> Optional[str]:
    """Санаи имрӯз, агар вақти ҳисоботи рӯз ба гурӯҳ расида бошад ва ҳанӯз нарафта бошад."""
    sch = get_schedule()
    now = cfg.now()
    if not sch["enabled"] or not sch["report"] or not is_workday(now.date(), sch):
        return None
    hour, minute = (int(x) for x in sch["time"].split(":"))
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0) \
        + timedelta(minutes=cfg.DAILY_REPORT_AFTER)
    day = now.strftime(cfg.DATE_FMT)
    if now < due or get_setting("daily_report_sent") == day:
        return None
    with _ro() as conn:
        has = conn.execute("SELECT 1 FROM attendance WHERE work_date = ? LIMIT 1", (day,)).fetchone()
    if not has:
        return None
    return day


# ──────────────────────────────────────────────────────────────────────────
#  Давомот: панели маъмурият
# ──────────────────────────────────────────────────────────────────────────

def _day_info(d: date, sch: dict, offs: dict[str, str], today: date) -> dict:
    iso = d.isoformat()
    return {
        "date": iso,
        "wd": d.weekday(),
        "workday": d.weekday() in sch["days"] and iso not in offs,
        "off": offs.get(iso),
        "weekend": d.weekday() not in sch["days"],
        "today": d == today,
        "future": d > today,
    }


def _people(conn, user_ids_with_records: set[int], user_id: int | None = None) -> list[dict]:
    where = "e.active = 1"
    params: list[Any] = []
    if user_ids_with_records:
        marks = ",".join("?" * len(user_ids_with_records))
        where = f"(e.active = 1 OR e.user_id IN ({marks}))"
        params = list(user_ids_with_records)
    if user_id:
        where = "e.user_id = ?"
        params = [int(user_id)]
    return _rows(conn.execute(
        f"""SELECT e.user_id, {_EMP_NAME} AS name, e.username, e.active
              FROM employees e WHERE {where} ORDER BY name COLLATE NOCASE""", params))


def get_attendance_day(day: str | None = None) -> dict:
    today = cfg.now().date()
    try:
        d = datetime.strptime(day, cfg.DATE_FMT).date() if day else today
    except (TypeError, ValueError):
        d = today
    iso = d.isoformat()
    sch = get_schedule()
    offs = get_days_off(iso, iso)
    with _ro() as conn:
        recs = {r["user_id"]: dict(r) for r in conn.execute(
            "SELECT * FROM attendance WHERE work_date = ?", (iso,))}
        people = _people(conn, set(recs))
    known = {p["user_id"] for p in people}
    for uid, rec in recs.items():                   # сабт ҳаст, вале корманд нест шудааст
        if uid not in known:
            people.append({"user_id": uid, "name": rec["name"], "username": None, "active": 0})

    items, summary = [], {k: 0 for k in ATT_STATES}
    summary["none"] = 0
    for p in people:
        rec = recs.get(p["user_id"])
        cell = _cell(rec, sch["grace"]) if rec else None
        summary[cell["s"] if cell else "none"] += 1
        items.append({**p, "active": bool(p["active"]), "cell": cell})
    summary["total"] = len(items)
    summary["present"] = summary["on_time"] + summary["late"]

    return {
        **_day_info(d, sch, offs, today),
        "schedule": sch,
        "prev": (d - timedelta(days=1)).isoformat(),
        "next": (d + timedelta(days=1)).isoformat() if d < today else None,
        "summary": summary,
        "items": items,
    }


def get_attendance_month(period: str | None = None, user_id: int | None = None) -> dict:
    start, end = work_period(period)
    key = start[:7]
    today = cfg.now().date()
    sch = get_schedule()
    offs = get_days_off(start, end)

    a = datetime.strptime(start, cfg.DATE_FMT).date()
    b = datetime.strptime(end, cfg.DATE_FMT).date()
    days, d = [], a
    while d <= b:
        days.append(_day_info(d, sch, offs, today))
        d += timedelta(days=1)

    where, params = "work_date >= ? AND work_date <= ?", [start, end]
    if user_id:
        where += " AND user_id = ?"
        params.append(int(user_id))
    with _ro() as conn:
        recs = _rows(conn.execute(f"SELECT * FROM attendance WHERE {where} ORDER BY work_date", params))
        people = _people(conn, {r["user_id"] for r in recs}, user_id)

    known = {p["user_id"] for p in people}
    for rec in recs:
        if rec["user_id"] not in known:
            people.append({"user_id": rec["user_id"], "name": rec["name"], "username": None, "active": 0})
            known.add(rec["user_id"])

    cells: dict[int, dict[str, dict]] = {}
    by_day: dict[str, dict] = {x["date"]: {k: 0 for k in ATT_STATES} for x in days}
    for rec in recs:
        cell = _cell(rec, sch["grace"])
        cells.setdefault(rec["user_id"], {})[rec["work_date"]] = cell
        if rec["work_date"] in by_day:
            by_day[rec["work_date"]][cell["s"]] += 1

    employees = []
    all_cells: list[dict] = []
    for p in people:
        mine = cells.get(p["user_id"], {})
        all_cells.extend(mine.values())
        employees.append({**p, "active": bool(p["active"]), "cells": mine,
                          "summary": _summarize(list(mine.values()))})

    next_key = _shift_month(key, 1)
    return {
        "period": {"key": key, "start": start, "end": end, "prev": _shift_month(key, -1),
                   "next": next_key if f"{next_key}-05" <= today.isoformat() else None},
        "schedule": sch,
        "days": days,
        "by_day": by_day,
        "employees": employees,
        "totals": _summarize(all_cells),
    }


def get_attendance_stats(date_from: str | None = None, date_to: str | None = None,
                         user_id: int | None = None) -> dict:
    """Омори давомот барои саҳифаи «Омор»."""
    where, params = ["1=1"], []
    if date_from:
        where.append("work_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("work_date <= ?")
        params.append(date_to)
    if user_id:
        where.append("user_id = ?")
        params.append(int(user_id))
    sch = get_schedule()
    grace = sch["grace"]
    with _ro() as conn:
        recs = _rows(conn.execute(
            f"SELECT * FROM attendance WHERE {' AND '.join(where)} ORDER BY work_date", params))
        names = {r["user_id"]: r["name"] for r in conn.execute(
            f"SELECT e.user_id, {_EMP_NAME} AS name FROM employees e")}

    cells = [_cell(r, grace) for r in recs]
    per: dict[int, list[dict]] = {}
    for rec, cell in zip(recs, cells):
        per.setdefault(rec["user_id"], []).append(cell)

    workers = []
    for uid, items in per.items():
        last_name = next((r["name"] for r in reversed(recs) if r["user_id"] == uid), "—")
        workers.append({"user_id": uid, "name": names.get(uid, last_name), **_summarize(items)})
    workers.sort(key=lambda w: (-(w["late"] + w["absent"]), -w["late_minutes"], w["name"]))

    daily: dict[str, dict] = {}
    if recs:
        a = datetime.strptime(date_from or recs[0]["work_date"], cfg.DATE_FMT).date()
        b = datetime.strptime(date_to or recs[-1]["work_date"], cfg.DATE_FMT).date()
        b = min(b, cfg.now().date())
        if (b - a).days > 366:
            a = b - timedelta(days=366)
        d = a
        while d <= b:
            daily[d.isoformat()] = {"date": d.isoformat(), **{k: 0 for k in ATT_STATES}}
            d += timedelta(days=1)
    weekday_late = [0] * 7
    for rec, cell in zip(recs, cells):
        if rec["work_date"] in daily:
            daily[rec["work_date"]][cell["s"]] += 1
        if cell["s"] == "late":
            weekday_late[datetime.strptime(rec["work_date"], cfg.DATE_FMT).weekday()] += 1

    # Вақти омадан нисбат ба оғози кор: қадами 10 дақиқа, аз −40 то +80
    edges = list(range(-40, 81, 10))
    hist = [0] * len(edges)
    for rec in recs:
        if rec["status"] != "present":
            continue
        arrived, planned = cfg.parse_dt(rec["arrived_at"]), cfg.parse_dt(rec["scheduled_at"])
        if not arrived or not planned:
            continue
        offset = (arrived - planned).total_seconds() / 60
        idx = 0
        for i, edge in enumerate(edges):
            if offset >= edge:
                idx = i
        hist[idx] += 1

    return {
        "summary": _summarize(cells),
        "daily": list(daily.values()),
        "workers": workers,
        "weekday_late": weekday_late,
        "hist": {"edges": edges, "values": hist, "grace": grace, "start": sch["time"]},
        "schedule": sch,
    }


def admin_set_attendance(user_id: int, work_date: str, status: str,
                         clock: str | None = None, reason: str | None = None,
                         eta: str | None = None) -> dict:
    """Ислоҳи дастии давомот аз панел (омад / наомад / рухсатӣ)."""
    if status not in ("present", "absent", "leave"):
        raise ValueError("Вазъияти номаълум")
    datetime.strptime(work_date, cfg.DATE_FMT)
    emp = get_employee(user_id)
    sch = get_schedule()
    stamp = cfg.now_str()
    with _tx() as conn:
        row = conn.execute("SELECT * FROM attendance WHERE user_id = ? AND work_date = ?",
                           (user_id, work_date)).fetchone()
        if row is None and not emp:
            raise ValueError("Корманд ёфт нашуд")
        scheduled_at = row["scheduled_at"] if row else _scheduled_for(
            work_date, sch["time"] or _valid_clock(clock) or "09:00")
        arrived_at = None
        if status == "present":
            clock = _valid_clock(clock) or (scheduled_at[11:16] if scheduled_at else "09:00")
            arrived_at = f"{work_date} {clock}:00"
        values = (status, arrived_at, (reason or "").strip()[:1000] or None,
                  (eta or "").strip()[:300] or None, stamp)
        if row is None:
            conn.execute(
                """INSERT INTO attendance
                       (user_id, name, work_date, scheduled_at, status, arrived_at, reason, eta,
                        source, prompted_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'admin', ?, ?, ?)""",
                (user_id, emp["display"], work_date, scheduled_at, *values[:4], stamp, stamp, stamp),
            )
        else:
            conn.execute(
                """UPDATE attendance SET status = ?, arrived_at = ?, reason = ?, eta = ?,
                          updated_at = ?, source = 'admin' WHERE id = ?""",
                (*values, row["id"]),
            )
        rec = dict(conn.execute("SELECT * FROM attendance WHERE user_id = ? AND work_date = ?",
                                (user_id, work_date)).fetchone())
    log.info("✏️ Давомот ислоҳ шуд: %s · %s → %s", user_id, work_date, status)
    return _cell(rec, sch["grace"])


def delete_attendance(attendance_id: int) -> bool:
    with _tx() as conn:
        removed = conn.execute("DELETE FROM attendance WHERE id = ?", (attendance_id,)).rowcount > 0
    if removed:
        log.warning("🗑 Сабти давомот #%d нест шуд", attendance_id)
    return removed


# Мутобиқат бо версияи қаблӣ (тестҳо)
def get_attendance_report(period: str | None = None) -> dict:
    return get_attendance_month(period)


# ──────────────────────────────────────────────────────────────────────────
#  Оморҳо (барои панели маъмурият)
# ──────────────────────────────────────────────────────────────────────────

def get_summary() -> dict:
    now = cfg.now()
    today = now.strftime("%Y-%m-%d 00:00:00")
    week = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d 00:00:00")
    month = f"{work_period()[0]} 00:00:00"

    with _ro() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)                                        AS total,
                   COALESCE(SUM(created_at >= ?), 0)               AS today,
                   COALESCE(SUM(created_at >= ?), 0)               AS week,
                   COALESCE(SUM(created_at >= ?), 0)               AS month,
                   COALESCE(SUM(status = 'accepted'), 0)           AS accepted,
                   COALESCE(SUM(status = 'rejected'), 0)           AS rejected,
                   COALESCE(SUM(status = 'pending'), 0)            AS pending,
                   COALESCE(SUM(status = 'cancelled'), 0)          AS cancelled
              FROM requests
            """,
            (today, week, month),
        ).fetchone()

        by_type = {r["type"]: r["c"] for r in conn.execute(
            "SELECT type, COUNT(*) c FROM requests GROUP BY type"
        )}
        recent = _rows(conn.execute(
            f"""SELECT r.*, NULLIF(TRIM(e.alias), '') AS alias
                  FROM requests r LEFT JOIN employees e ON e.user_id = r.user_id
                 ORDER BY r.id DESC LIMIT 10"""))
        people = conn.execute(
            "SELECT COUNT(DISTINCT user_id) c FROM requests"
        ).fetchone()["c"]

    data = dict(row)
    data["by_type"] = {t: by_type.get(t, 0) for t in REQ_TYPES}
    data["recent"] = recent
    data["people"] = people
    return data


def get_overview() -> dict:
    """Саҳифаи «Асосӣ»: давомоти имрӯз + дархостҳо + ҳафтаи охир."""
    today = cfg.now().date()
    week_from = (today - timedelta(days=6)).isoformat()
    summary = get_summary()
    day = get_attendance_day(today.isoformat())
    week = get_attendance_stats(week_from, today.isoformat())
    with _ro() as conn:
        pending = _rows(conn.execute(
            """SELECT r.*, NULLIF(TRIM(e.alias), '') AS alias
                 FROM requests r LEFT JOIN employees e ON e.user_id = r.user_id
                WHERE r.status = 'pending' ORDER BY r.id LIMIT 20"""))
        employees = conn.execute("SELECT COUNT(*) c FROM employees WHERE active = 1").fetchone()["c"]
    return {
        "requests": summary,
        "pending": pending,
        "today": day,
        "week_attendance": week["daily"],
        "week_requests": get_daily_stats(7),
        "employees": employees,
        "period": dict(zip(("start", "end"), work_period())),
    }


def _filter_clause(
    req_type: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    user_id: int | None = None,
) -> tuple[str, list[Any]]:
    """Филтрҳои дархостҳо (ҷадвал бо тахаллуси `r`) — барои рӯйхат, экспорт ва нест кардан."""
    where = ["1=1"]
    params: list[Any] = []
    if user_id:
        where.append("r.user_id = ?")
        params.append(int(user_id))
    if req_type in REQ_TYPES:
        where.append("r.type = ?")
        params.append(req_type)
    if status in REQ_STATUSES:
        where.append("r.status = ?")
        params.append(status)
    if date_from:
        where.append("r.created_at >= ?")
        params.append(f"{date_from} 00:00:00")
    if date_to:
        where.append("r.created_at <= ?")
        params.append(f"{date_to} 23:59:59")
    if search:
        needle = f"%{search.lower()}%"
        where.append("(ulower(r.name) LIKE ? OR ulower(r.reason) LIKE ? OR "
                     "r.user_id IN (SELECT user_id FROM employees WHERE ulower(alias) LIKE ?))")
        params += [needle, needle, needle]
    return " AND ".join(where), params


_SORTS = {
    "new": "r.id DESC",
    "old": "r.id ASC",
    "minutes": "r.minutes DESC, r.id DESC",
    "name": "COALESCE(NULLIF(TRIM(e.alias), ''), r.name) COLLATE NOCASE, r.id DESC",
}


def query_requests(
    req_type: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user_id: int | None = None,
    sort: str | None = None,
) -> dict:
    clause, params = _filter_clause(req_type, status, date_from, date_to, search, user_id)
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))

    with _ro() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) c FROM requests r WHERE {clause}", params
        ).fetchone()["c"]
        items = _rows(conn.execute(
            f"""SELECT r.*, NULLIF(TRIM(e.alias), '') AS alias
                  FROM requests r LEFT JOIN employees e ON e.user_id = r.user_id
                 WHERE {clause} ORDER BY {_SORTS.get(sort or '', 'r.id DESC')}
                 LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ))

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_worker_stats(date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """Гурӯҳбандӣ аз рӯи user_id (на ном) — тағйири ном такрор насозад."""
    clause, params = _range_clause(date_from, date_to, "r.created_at")
    with _ro() as conn:
        rows = _rows(conn.execute(
            f"""
            SELECT r.user_id,
                   COALESCE(NULLIF(TRIM(e.alias), ''), e.name, MAX(r.name)) AS name,
                   COUNT(*)                                         AS total,
                   COALESCE(SUM(r.type = 'late'), 0)                AS late,
                   COALESCE(SUM(r.type = 'absent'), 0)              AS absent,
                   COALESCE(SUM(r.type = 'leaving_early'), 0)       AS leaving_early,
                   COALESCE(SUM(r.type = 'at_work_waiting'), 0)     AS at_work_waiting,
                   COALESCE(SUM(r.status = 'accepted'), 0)          AS accepted,
                   COALESCE(SUM(r.status = 'rejected'), 0)          AS rejected,
                   COALESCE(SUM(r.status = 'pending'), 0)           AS pending,
                   COALESCE(SUM(r.status = 'cancelled'), 0)         AS cancelled,
                   COALESCE(SUM(r.minutes), 0)                      AS total_minutes,
                   MAX(r.created_at)                                AS last_at,
                   COALESCE(SUM(CASE WHEN r.type = 'late' THEN r.minutes END), 0) AS late_minutes,
                   e.username                                       AS username
              FROM requests r
              LEFT JOIN employees e ON e.user_id = r.user_id
             WHERE {clause}
             GROUP BY r.user_id
             ORDER BY total DESC, name COLLATE NOCASE
            """,
            params,
        ))
        top = {}
        for r in conn.execute(
            f"""
            SELECT r.user_id, r.reason, COUNT(*) c FROM requests r
             WHERE {clause} GROUP BY r.user_id, r.reason ORDER BY c DESC
            """,
            params,
        ):
            top.setdefault(r["user_id"], (r["reason"], r["c"]))

    for row in rows:
        decided = row["accepted"] + row["rejected"]
        row["accept_rate"] = round(100 * row["accepted"] / decided) if decided else None
        reason = top.get(row["user_id"])
        row["top_reason"] = reason[0] if reason else None
        row["top_reason_count"] = reason[1] if reason else 0
    return rows


def get_daily_stats(days: int = 7) -> list[dict]:
    days = max(1, min(int(days), 90))
    start = (cfg.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    with _ro() as conn:
        rows = conn.execute(
            """
            SELECT substr(created_at, 1, 10) AS d, type, COUNT(*) c
              FROM requests
             WHERE substr(created_at, 1, 10) >= ?
             GROUP BY d, type
            """,
            (start,),
        ).fetchall()

    buckets: dict[str, dict] = {}
    for i in range(days - 1, -1, -1):
        key = (cfg.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        buckets[key] = {"date": key, "count": 0, "by_type": {}}

    for r in rows:
        bucket = buckets.get(r["d"])
        if bucket is None:
            continue
        bucket["count"] += r["c"]
        bucket["by_type"][r["type"]] = r["c"]

    return list(buckets.values())


def export_rows(**filters) -> list[dict]:
    clause, params = _filter_clause(**filters)
    with _ro() as conn:
        return _rows(conn.execute(
            f"""SELECT r.*, NULLIF(TRIM(e.alias), '') AS alias
                  FROM requests r LEFT JOIN employees e ON e.user_id = r.user_id
                 WHERE {clause} ORDER BY r.id DESC""", params))


# ──────────────────────────────────────────────────────────────────────────
#  Нест кардан ва нусхаи эҳтиётӣ
# ──────────────────────────────────────────────────────────────────────────

def _chunks(ids: list[int], size: int = 500) -> Iterator[list[int]]:
    for i in range(0, len(ids), size):
        yield ids[i:i + size]


def delete_requests(ids: Iterable[int]) -> int:
    """Дархостҳо ва санҷишҳои омадани онҳоро нест мекунад."""
    ids = sorted({int(i) for i in ids})
    if not ids:
        return 0
    removed = 0
    with _tx() as conn:
        for part in _chunks(ids):
            marks = ",".join("?" * len(part))
            conn.execute(f"DELETE FROM arrival_checks WHERE request_id IN ({marks})", part)
            removed += conn.execute(f"DELETE FROM requests WHERE id IN ({marks})", part).rowcount or 0
    log.warning("🗑 Аз панел нест шуд: %d дархост (%s)", removed,
                ", ".join(f"#{i}" for i in ids[:20]) + (" …" if len(ids) > 20 else ""))
    return removed


def delete_filtered(**filters) -> int:
    clause, params = _filter_clause(**filters)
    with _ro() as conn:
        ids = [r["id"] for r in conn.execute(f"SELECT r.id FROM requests r WHERE {clause}", params)]
    return delete_requests(ids)


def delete_worker(user_id: int) -> dict:
    """Ҳамаи маълумоти як корманд."""
    with _ro() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM requests WHERE user_id = ?", (user_id,))]
    removed = delete_requests(ids)
    with _tx() as conn:
        conn.execute("DELETE FROM arrival_checks WHERE user_id = ?", (user_id,))
        att = conn.execute("DELETE FROM attendance WHERE user_id = ?", (user_id,)).rowcount or 0
        conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        emp = conn.execute("DELETE FROM employees WHERE user_id = ?", (user_id,)).rowcount or 0
    log.warning("🗑 Маълумоти корманд %s нест шуд (%d дархост, %d давомот)", user_id, removed, att)
    return {"requests": removed, "attendance": att, "employee": emp}


def wipe(scope: str = "requests", before: str | None = None) -> dict:
    """
    scope="requests" — ҳамаи дархостҳо ва давомот (ё танҳо то санаи `before`);
    scope="all"      — ғайр аз ин кормандон ва ҳолатҳо; рақамгузорӣ аз #1.
    Танзимот (логин/рамз, вақти корӣ, идҳо) ҳеҷ гоҳ нест намешаванд.
    """
    counts = {}
    with _tx() as conn:
        if before:
            stamp = f"{before} 23:59:59"
            conn.execute(
                "DELETE FROM arrival_checks WHERE request_id IN "
                "(SELECT id FROM requests WHERE created_at <= ?)", (stamp,))
            counts["requests"] = conn.execute(
                "DELETE FROM requests WHERE created_at <= ?", (stamp,)).rowcount or 0
            counts["attendance"] = conn.execute(
                "DELETE FROM attendance WHERE work_date <= ?", (before,)).rowcount or 0
        else:
            conn.execute("DELETE FROM arrival_checks")
            counts["requests"] = conn.execute("DELETE FROM requests").rowcount or 0
            counts["attendance"] = conn.execute("DELETE FROM attendance").rowcount or 0
            if scope == "all":
                counts["employees"] = conn.execute("DELETE FROM employees").rowcount or 0
                conn.execute("DELETE FROM user_states")
                conn.execute(
                    "DELETE FROM sqlite_sequence WHERE name IN ('requests', 'arrival_checks', 'attendance')")
    log.warning("🧨 Тозакунии база аз панел: scope=%s before=%s → %s", scope, before, counts)
    return counts


def backup_to(path: str) -> str:
    """Нусхаи пурраи база (SQLite backup API — ҳатто ҳангоми кор бехатар)."""
    src = _connect()
    try:
        dst = sqlite3.connect(path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return path


def restore_if_missing() -> str | None:
    """Агар файли база нест (ё холӣ) бошад — аз навтарин нусхаи эҳтиётӣ барқарор мекунад.

    Пеш аз init_db даъват мешавад: бе ин, пас аз нест шудани база бот ором
    базаи холии нав месохт ва ҳамаи таърих «гум» мешуд. Ҷойҳои ҷустуҷӯ:
    BACKUP_DIR ва RESTORE_DIRS (бо «:» ҷудо, масалан /var/backups/hrcontrol/db).
    """
    if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 0:
        # Файл ҳаст — вале оё ин базаи мост? Агар базаро ҳангоми кори бот нест
        # кунанд, SQLite файли холии нав месозад (бе ҷадвалҳо) — онро ҳам «нест» мешуморем.
        try:
            probe = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
            try:
                ok = probe.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='requests'").fetchone()
            finally:
                probe.close()
        except sqlite3.Error:
            ok = None
        if ok:
            return None
    dirs = [cfg.BACKUP_DIR] + [d for d in os.environ.get("RESTORE_DIRS", "").split(":") if d.strip()]
    candidates = []
    for directory in dirs:
        for path in glob.glob(os.path.join(directory, "softclub_*.db")):
            try:
                with open(path, "rb") as fh:
                    if fh.read(16) == b"SQLite format 3\x00":
                        candidates.append(path)
            except OSError:
                continue
    if not candidates:
        return None
    newest = max(candidates, key=os.path.getmtime)
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    if os.path.exists(DB_PATH):                       # файли холӣ/бегонаро нест намекунем — канор мегузорем
        os.replace(DB_PATH, f"{DB_PATH}.broken-{cfg.now().strftime('%Y%m%d_%H%M%S')}")
    for ext in ("-wal", "-shm"):
        try:
            os.remove(DB_PATH + ext)
        except OSError:
            pass
    shutil.copy2(newest, DB_PATH)
    log.warning("♻️ База набуд — аз нусхаи эҳтиётӣ барқарор шуд: %s", newest)
    return newest


def make_backup(tag: str, directory: str | None = None) -> str | None:
    """Нусхаи худкор (ҳаррӯза ва пеш аз ҳар нест кардан).

    Нусхаҳои ҳаррӯза ва дигарҳо ҷудо давр мезананд, то нест кардани зиёд
    нусхаҳои ҳаррӯзаро «пахш» накунад. Хато бот/панелро намекушад.
    """
    directory = directory or cfg.BACKUP_DIR
    try:
        os.makedirs(directory, exist_ok=True)
        stamp = cfg.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(directory, f"softclub_{stamp}_{tag}.db")
        backup_to(path)
        files = sorted(glob.glob(os.path.join(directory, "softclub_*.db")))
        daily = [f for f in files if f.endswith("_daily.db")]
        other = [f for f in files if not f.endswith("_daily.db")]
        keep = max(5, cfg.BACKUP_KEEP // 2)
        for extra in daily[:-keep] + other[:-keep]:
            try:
                os.remove(extra)
            except OSError:
                pass
        log.info("💾 Нусхаи эҳтиётӣ: %s", path)
        return path
    except Exception as exc:
        log.error("💾 Нусхаи эҳтиётӣ сохта нашуд: %s", exc)
        return None


# ──────────────────────────────────────────────────────────────────────────
#  Таҳлил (саҳифаи «Омор» ва тафсилоти корманд)
# ──────────────────────────────────────────────────────────────────────────

def _range_clause(date_from: str | None, date_to: str | None,
                  col: str = "created_at") -> tuple[str, list[Any]]:
    where, params = ["1=1"], []
    if date_from:
        where.append(f"{col} >= ?")
        params.append(f"{date_from} 00:00:00")
    if date_to:
        where.append(f"{col} <= ?")
        params.append(f"{date_to} 23:59:59")
    return " AND ".join(where), params


def _normalize_reason(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip(" .,!").capitalize() or "—"


def _reason_table(rows) -> list[dict]:
    merged: dict[str, dict] = {}
    for r in rows:
        key = _normalize_reason(r["reason"])
        item = merged.setdefault(key, {"reason": key, "count": 0, "minutes": 0, "by_type": {}})
        item["count"] += r["c"]
        item["minutes"] += r["m"] or 0
        item["by_type"][r["type"]] = item["by_type"].get(r["type"], 0) + r["c"]
    return sorted(merged.values(), key=lambda x: (-x["count"], x["reason"]))


def _period_summary(conn, clause: str, params: list[Any]) -> dict:
    row = conn.execute(
        f"""
        SELECT COUNT(*)                                          AS total,
               COUNT(DISTINCT user_id)                           AS people,
               COALESCE(SUM(status = 'accepted'), 0)             AS accepted,
               COALESCE(SUM(status = 'rejected'), 0)             AS rejected,
               COALESCE(SUM(status = 'pending'), 0)              AS pending,
               COALESCE(SUM(status = 'cancelled'), 0)            AS cancelled,
               COALESCE(SUM(minutes), 0)                         AS minutes,
               COALESCE(SUM(CASE WHEN type = 'late' THEN minutes END), 0) AS late_minutes,
               COALESCE(ROUND(AVG(NULLIF(minutes, 0))), 0)       AS avg_minutes,
               COALESCE(SUM(worker_confirmed = 'yes'), 0)        AS confirmed_yes,
               COALESCE(SUM(worker_confirmed = 'no'), 0)         AS confirmed_no,
               ROUND(AVG(CASE WHEN decided_at IS NOT NULL AND status IN ('accepted','rejected')
                              THEN (julianday(decided_at) - julianday(created_at)) * 1440 END), 1)
                                                                 AS avg_response_min
          FROM requests WHERE {clause}
        """,
        params,
    ).fetchone()
    data = dict(row)
    decided = data["accepted"] + data["rejected"]
    data["accept_rate"] = round(100 * data["accepted"] / decided) if decided else None
    return data


def get_analytics(date_from: str | None = None, date_to: str | None = None) -> dict:
    clause, params = _range_clause(date_from, date_to)

    with _ro() as conn:
        summary = _period_summary(conn, clause, params)

        by_type = {t: {"count": 0, "minutes": 0, "accepted": 0} for t in REQ_TYPES}
        for r in conn.execute(
            f"""SELECT type, COUNT(*) c, COALESCE(SUM(minutes),0) m,
                       COALESCE(SUM(status='accepted'),0) a
                  FROM requests WHERE {clause} GROUP BY type""", params):
            by_type[r["type"]] = {"count": r["c"], "minutes": r["m"], "accepted": r["a"]}

        by_status = {s: 0 for s in REQ_STATUSES}
        for r in conn.execute(
            f"SELECT status, COUNT(*) c FROM requests WHERE {clause} GROUP BY status", params):
            by_status[r["status"]] = r["c"]

        reasons = _reason_table(conn.execute(
            f"""SELECT reason, type, COUNT(*) c, COALESCE(SUM(minutes),0) m
                  FROM requests WHERE {clause} GROUP BY reason, type""", params))

        weekday = [0] * 7                                  # 0 = душанбе
        for r in conn.execute(
            f"""SELECT CAST(strftime('%w', created_at) AS INTEGER) d, COUNT(*) c
                  FROM requests WHERE {clause} GROUP BY d""", params):
            weekday[(r["d"] + 6) % 7] = r["c"]

        hours = [0] * 24
        for r in conn.execute(
            f"""SELECT CAST(strftime('%H', created_at) AS INTEGER) h, COUNT(*) c
                  FROM requests WHERE {clause} GROUP BY h""", params):
            if r["h"] is not None and 0 <= r["h"] < 24:
                hours[r["h"]] = r["c"]

        day_rows = conn.execute(
            f"""SELECT substr(created_at, 1, 10) d, type, COUNT(*) c
                  FROM requests WHERE {clause} GROUP BY d, type ORDER BY d""", params).fetchall()

        deciders = _rows(conn.execute(
            f"""SELECT COALESCE(decided_by, '—') AS name, COUNT(*) AS total,
                       COALESCE(SUM(status='accepted'),0) AS accepted,
                       COALESCE(SUM(status='rejected'),0) AS rejected
                  FROM requests WHERE {clause} AND status IN ('accepted','rejected')
                 GROUP BY decided_by ORDER BY total DESC LIMIT 10""", params))

        arrivals = dict(conn.execute(
            f"""SELECT COALESCE(SUM(ac.status='arrived'),0) arrived,
                       COALESCE(SUM(ac.status='delayed'),0) delayed,
                       COALESCE(SUM(ac.status='pending'),0) waiting
                  FROM arrival_checks ac JOIN requests r ON r.id = ac.request_id
                 WHERE {clause.replace('created_at', 'r.created_at')}""", params).fetchone())

        span = conn.execute(
            f"SELECT MIN(substr(created_at,1,10)) a, MAX(substr(created_at,1,10)) b "
            f"FROM requests WHERE {clause}", params).fetchone()

    daily = _daily_series(day_rows, date_from or span["a"], date_to or span["b"])

    return {
        "range": {"from": date_from, "to": date_to,
                  "first": span["a"], "last": span["b"]},
        "summary": summary,
        "by_type": by_type,
        "by_status": by_status,
        "reasons": reasons[:40],
        "weekday": weekday,
        "hours": hours,
        "daily": daily,
        "deciders": deciders,
        "arrivals": arrivals,
        "workers": get_worker_stats(date_from, date_to),
        "attendance": get_attendance_stats(date_from, date_to),
    }


def _daily_series(rows, start: str | None, end: str | None) -> list[dict]:
    if not start or not end:
        return []
    try:
        a = datetime.strptime(start[:10], "%Y-%m-%d")
        b = datetime.strptime(end[:10], "%Y-%m-%d")
    except ValueError:
        return []
    if b < a:
        a, b = b, a
    if (b - a).days > 366:                          # ҳадди аксар як сол
        a = b - timedelta(days=366)
    buckets: dict[str, dict] = {}
    d = a
    while d <= b:
        key = d.strftime("%Y-%m-%d")
        buckets[key] = {"date": key, "count": 0, "by_type": {}}
        d += timedelta(days=1)
    for r in rows:
        item = buckets.get(r["d"])
        if item is not None:
            item["count"] += r["c"]
            item["by_type"][r["type"]] = item["by_type"].get(r["type"], 0) + r["c"]
    return list(buckets.values())


def get_worker_detail(user_id: int, date_from: str | None = None,
                      date_to: str | None = None) -> Optional[dict]:
    clause, params = _range_clause(date_from, date_to)
    clause = f"user_id = ? AND {clause}"
    params = [int(user_id)] + params

    with _ro() as conn:
        emp = conn.execute(
            f"SELECT e.*, {_EMP_NAME} AS display FROM employees e WHERE e.user_id = ?",
            (user_id,)).fetchone()
        any_req = conn.execute(
            "SELECT name FROM requests WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)).fetchone()
        any_att = conn.execute(
            "SELECT name FROM attendance WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)).fetchone()
        if not emp and not any_req and not any_att:
            return None

        summary = _period_summary(conn, clause, params)
        by_type = {t: {"count": 0, "minutes": 0} for t in REQ_TYPES}
        for r in conn.execute(
            f"""SELECT type, COUNT(*) c, COALESCE(SUM(minutes),0) m
                  FROM requests WHERE {clause} GROUP BY type""", params):
            by_type[r["type"]] = {"count": r["c"], "minutes": r["m"]}
        reasons = _reason_table(conn.execute(
            f"""SELECT reason, type, COUNT(*) c, COALESCE(SUM(minutes),0) m
                  FROM requests WHERE {clause} GROUP BY reason, type""", params))
        weekday = [0] * 7
        for r in conn.execute(
            f"""SELECT CAST(strftime('%w', created_at) AS INTEGER) d, COUNT(*) c
                  FROM requests WHERE {clause} GROUP BY d""", params):
            weekday[(r["d"] + 6) % 7] = r["c"]
        items = _rows(conn.execute(
            f"SELECT * FROM requests WHERE {clause} ORDER BY id DESC LIMIT 300", params))
        delays = conn.execute(
            "SELECT COUNT(*) c FROM arrival_checks WHERE user_id = ? AND status = 'delayed'",
            (user_id,)).fetchone()["c"]

    fallback = (any_req or any_att)["name"] if (any_req or any_att) else "—"
    return {
        "user_id": int(user_id),
        "name": emp["display"] if emp else fallback,
        "tg_name": emp["name"] if emp else fallback,
        "alias": emp["alias"] if emp else None,
        "active": bool(emp["active"]) if emp else False,
        "username": emp["username"] if emp else None,
        "first_seen": emp["first_seen"] if emp else None,
        "last_seen": emp["last_seen"] if emp else None,
        "summary": summary,
        "by_type": by_type,
        "reasons": reasons,
        "weekday": weekday,
        "extra_delays": delays,
        "items": items,
        "attendance": get_attendance_stats(date_from, date_to, user_id),
    }
