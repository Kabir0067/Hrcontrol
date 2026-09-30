"""
SoftClub / Hrcontrol — қабати база (SQLite).

Принсипҳо:
  • ҳамаи миграцияҳо идемпотентанд ва маълумоти мавҷударо нигоҳ медоранд;
  • ҳолати корбар (user_state) дар база нигоҳ дошта мешавад — restart-и бот
    равандҳои нотамомро вайрон намекунад;
  • оморҳо бо як-ду запрос ҳисоб мешаванд, на бо ҳалқаи N-запросӣ.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Iterator, Optional

import config as cfg

log = logging.getLogger("SoftClubBot")

DB_PATH = cfg.DB_PATH

REQ_TYPES = ("late", "absent", "at_work_waiting", "leaving_early")
REQ_STATUSES = ("pending", "accepted", "rejected", "cancelled")


# ──────────────────────────────────────────────────────────────────────────
#  Пайвастшавӣ
# ──────────────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
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

_SCHEMA = """
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
    last_seen  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Сабти ҳозиршавии ҳаррӯза.  Аз дархостҳои «дер мекунам» ҷудо аст:
-- як корманд барои як рӯзи корӣ танҳо як сабт дорад.
CREATE TABLE IF NOT EXISTS attendance (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    name           TEXT    NOT NULL,
    work_date      TEXT    NOT NULL,
    scheduled_at   TEXT    NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'pending'
                         CHECK(status IN ('pending','present','absent')),
    prompted_at    TEXT,
    arrived_at     TEXT,
    reason         TEXT,
    eta            TEXT,
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL,
    UNIQUE(user_id, work_date)
);

CREATE INDEX IF NOT EXISTS idx_attendance_period ON attendance(work_date, user_id);
CREATE INDEX IF NOT EXISTS idx_attendance_pending ON attendance(status, prompted_at);
"""

# Сутунҳое, ки метавонанд дар базаи кӯҳна набошанд.
_EXTRA_COLUMNS = {
    "requests": {
        "decided_by":    "TEXT",
        "decided_at":    "TEXT",
        "worker_msg_id": "INTEGER",
        "confirmed_at":  "TEXT",
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


# ─────────────────────────────────────────────────────────────────────────────
# Ҳозиршавии ҳаррӯза (вақти корӣ аз админка)
# ─────────────────────────────────────────────────────────────────────────────

def get_work_start_time() -> str:
    """Вақти оғози кор дар шакли HH:MM, ё сатри холӣ агар огоҳӣ хомӯш бошад."""
    value = (get_setting("work_start_time", "") or "").strip()
    return value if len(value) == 5 and value[2] == ":" else ""


def set_work_start_time(value: str) -> None:
    """Сатри холӣ огоҳии автоматиро хомӯш мекунад."""
    set_settings({"work_start_time": value})


def create_due_attendance() -> list[dict]:
    """Сабтҳои имрӯзаро месозад ва танҳо онҳоеро бармегардонад, ки ҳанӯз пурсида нашудаанд.

    UNIQUE(user_id, work_date) ин амалро барои restart ва чанд даъвати ҳамзамон
    бехатар мекунад. Якшанбе (weekday == 6) рӯзи истироҳат аст.
    """
    start_time = get_work_start_time()
    now = cfg.now()
    if not start_time or now.weekday() == 6:
        return []
    try:
        hour, minute = (int(x) for x in start_time.split(":"))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except (TypeError, ValueError):
        return []
    if now < scheduled:
        return []

    day = now.strftime(cfg.DATE_FMT)
    scheduled_at = cfg.to_str(scheduled)
    stamp = cfg.now_str()
    with _tx() as conn:
        employees = _rows(conn.execute(
            "SELECT user_id, name FROM employees ORDER BY name COLLATE NOCASE"
        ))
        for employee in employees:
            conn.execute(
                """
                INSERT OR IGNORE INTO attendance
                    (user_id, name, work_date, scheduled_at, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', ?, ?)
                """,
                (employee["user_id"], employee["name"], day, scheduled_at, stamp, stamp),
            )
        rows = _rows(conn.execute(
            """
            SELECT * FROM attendance
             WHERE work_date = ? AND status = 'pending' AND prompted_at IS NULL
             ORDER BY id
            """, (day,)
        ))
    return rows


def mark_attendance_prompted(attendance_id: int) -> bool:
    with _tx() as conn:
        cur = conn.execute(
            """UPDATE attendance SET prompted_at = ?, updated_at = ?
                 WHERE id = ? AND prompted_at IS NULL""",
            (cfg.now_str(), cfg.now_str(), attendance_id),
        )
        return cur.rowcount > 0


def get_attendance(attendance_id: int) -> Optional[dict]:
    with _ro() as conn:
        row = conn.execute("SELECT * FROM attendance WHERE id = ?", (attendance_id,)).fetchone()
    return dict(row) if row else None


def set_attendance_present(attendance_id: int) -> bool:
    stamp = cfg.now_str()
    with _tx() as conn:
        cur = conn.execute(
            """UPDATE attendance SET status = 'present', arrived_at = ?, updated_at = ?
                 WHERE id = ? AND status = 'pending'""",
            (stamp, stamp, attendance_id),
        )
        return cur.rowcount > 0


def set_attendance_absent(attendance_id: int, reason: str, eta: str) -> bool:
    with _tx() as conn:
        cur = conn.execute(
            """UPDATE attendance SET status = 'absent', reason = ?, eta = ?, updated_at = ?
                 WHERE id = ? AND status = 'pending'""",
            (reason.strip()[:1000], eta.strip()[:300], cfg.now_str(), attendance_id),
        )
        return cur.rowcount > 0


def work_period(anchor: str | None = None) -> tuple[str, str]:
    """Моҳи корӣ: аз рӯзи 5 то рӯзи 4-уми моҳи баъдӣ."""
    try:
        source = datetime.strptime(anchor, "%Y-%m").date() if anchor else cfg.now().date()
    except (TypeError, ValueError):
        source = cfg.now().date()
    start = date(source.year, source.month, 5)
    if not anchor and source.day < 5:
        start = date(source.year - 1, 12, 5) if source.month == 1 else date(source.year, source.month - 1, 5)
    if anchor:
        # anchor ҳамеша моҳи оғози давр аст, масалан 2026-09 → 05.09–04.10
        start = date(source.year, source.month, 5)
    next_month = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 5)
    end = next_month - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def get_attendance_report(period: str | None = None) -> dict:
    start, end = work_period(period)
    with _ro() as conn:
        rows = _rows(conn.execute(
            """SELECT * FROM attendance WHERE work_date >= ? AND work_date <= ?
                 ORDER BY work_date DESC, name COLLATE NOCASE""", (start, end)
        ))
        employees = _rows(conn.execute(
            "SELECT user_id, name FROM employees ORDER BY name COLLATE NOCASE"
        ))
    by_user: dict[int, dict] = {
        e["user_id"]: {**e, "present": 0, "absent": 0, "pending": 0, "records": []}
        for e in employees
    }
    for row in rows:
        item = by_user.setdefault(row["user_id"], {
            "user_id": row["user_id"], "name": row["name"], "present": 0,
            "absent": 0, "pending": 0, "records": [],
        })
        item[row["status"]] = item.get(row["status"], 0) + 1
        item["records"].append(row)
    totals = {state: sum(1 for r in rows if r["status"] == state) for state in ("present", "absent", "pending")}
    return {
        "period": {"start": start, "end": end},
        "schedule": get_work_start_time(),
        "summary": {"employees": len(employees), "records": len(rows), **totals},
        "workers": list(by_user.values()),
        "records": rows,
    }


# ──────────────────────────────────────────────────────────────────────────
#  Оморҳо (барои панели маъмурият)
# ──────────────────────────────────────────────────────────────────────────

def get_summary() -> dict:
    now = cfg.now()
    today = now.strftime("%Y-%m-%d 00:00:00")
    week = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d 00:00:00")
    month = now.strftime("%Y-%m-01 00:00:00")

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
        recent = _rows(conn.execute("SELECT * FROM requests ORDER BY id DESC LIMIT 10"))
        people = conn.execute(
            "SELECT COUNT(DISTINCT user_id) c FROM requests"
        ).fetchone()["c"]

    data = dict(row)
    data["by_type"] = {t: by_type.get(t, 0) for t in REQ_TYPES}
    data["recent"] = recent
    data["people"] = people
    return data


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
    where = ["1=1"]
    params: list[Any] = []

    if user_id:
        where.append("user_id = ?")
        params.append(int(user_id))

    if req_type in REQ_TYPES:
        where.append("type = ?")
        params.append(req_type)
    if status in REQ_STATUSES:
        where.append("status = ?")
        params.append(status)
    if date_from:
        where.append("created_at >= ?")
        params.append(f"{date_from} 00:00:00")
    if date_to:
        where.append("created_at <= ?")
        params.append(f"{date_to} 23:59:59")
    if search:
        where.append("(name LIKE ? OR reason LIKE ?)")
        needle = f"%{search}%"
        params += [needle, needle]

    clause = " AND ".join(where)
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))

    with _ro() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) c FROM requests WHERE {clause}", params
        ).fetchone()["c"]
        items = _rows(conn.execute(
            f"SELECT * FROM requests WHERE {clause} ORDER BY {_SORTS.get(sort or '', 'id DESC')} "
            "LIMIT ? OFFSET ?",
            params + [limit, offset],
        ))

    return {"items": items, "total": total, "limit": limit, "offset": offset}


_SORTS = {
    "new": "id DESC",
    "old": "id ASC",
    "minutes": "minutes DESC, id DESC",
    "name": "name COLLATE NOCASE, id DESC",
}


def _filter_clause(
    req_type: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    user_id: int | None = None,
) -> tuple[str, list[Any]]:
    """Ҳамон филтрҳое, ки query_requests дорад — барои экспорт ва нест кардан."""
    where = ["1=1"]
    params: list[Any] = []
    if user_id:
        where.append("user_id = ?")
        params.append(int(user_id))
    if req_type in REQ_TYPES:
        where.append("type = ?")
        params.append(req_type)
    if status in REQ_STATUSES:
        where.append("status = ?")
        params.append(status)
    if date_from:
        where.append("created_at >= ?")
        params.append(f"{date_from} 00:00:00")
    if date_to:
        where.append("created_at <= ?")
        params.append(f"{date_to} 23:59:59")
    if search:
        where.append("(name LIKE ? OR reason LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    return " AND ".join(where), params


def get_worker_stats(date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """Гурӯҳбандӣ аз рӯи user_id (на ном) — тағйири ном такрор насозад."""
    clause, params = _range_clause(date_from, date_to, "r.created_at")
    with _ro() as conn:
        rows = _rows(conn.execute(
            f"""
            SELECT r.user_id,
                   COALESCE(e.name, MAX(r.name))                    AS name,
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
        return _rows(conn.execute(f"SELECT * FROM requests WHERE {clause} ORDER BY id DESC", params))


# ──────────────────────────────────────────────────────────────────────────
#  Танзимот (логин/рамзи панел ва ғ.)
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
        ids = [r["id"] for r in conn.execute(f"SELECT id FROM requests WHERE {clause}", params)]
    return delete_requests(ids)


def delete_worker(user_id: int) -> dict:
    """Ҳамаи маълумоти як корманд."""
    with _ro() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM requests WHERE user_id = ?", (user_id,))]
    removed = delete_requests(ids)
    with _tx() as conn:
        conn.execute("DELETE FROM arrival_checks WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM attendance WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        emp = conn.execute("DELETE FROM employees WHERE user_id = ?", (user_id,)).rowcount or 0
    log.warning("🗑 Маълумоти корманд %s нест шуд (%d дархост)", user_id, removed)
    return {"requests": removed, "employee": emp}


def wipe(scope: str = "requests", before: str | None = None) -> dict:
    """
    scope="requests" — ҳамаи дархостҳо (ё танҳо то санаи `before`);
    scope="all"      — ғайр аз ин кормандон ва ҳолатҳо; рақамгузорӣ аз #1.
    Танзимот (логин/рамз) ҳеҷ гоҳ нест намешаванд.
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
                    "DELETE FROM sqlite_sequence WHERE name IN ('requests', 'arrival_checks')")
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
    }


def _daily_series(rows, start: str | None, end: str | None) -> list[dict]:
    from datetime import datetime as _dt
    if not start or not end:
        return []
    try:
        a = _dt.strptime(start[:10], "%Y-%m-%d")
        b = _dt.strptime(end[:10], "%Y-%m-%d")
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
        emp = conn.execute("SELECT * FROM employees WHERE user_id = ?", (user_id,)).fetchone()
        any_req = conn.execute(
            "SELECT name FROM requests WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)).fetchone()
        if not emp and not any_req:
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

    return {
        "user_id": int(user_id),
        "name": emp["name"] if emp else any_req["name"],
        "username": emp["username"] if emp else None,
        "first_seen": emp["first_seen"] if emp else None,
        "last_seen": emp["last_seen"] if emp else None,
        "summary": summary,
        "by_type": by_type,
        "reasons": reasons,
        "weekday": weekday,
        "extra_delays": delays,
        "items": items,
    }
