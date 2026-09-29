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
from datetime import timedelta
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
) -> dict:
    where = ["1=1"]
    params: list[Any] = []

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
            f"SELECT * FROM requests WHERE {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ))

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_worker_stats() -> list[dict]:
    """Гурӯҳбандӣ аз рӯи user_id (на ном) — тағйири ном такрор насозад."""
    with _ro() as conn:
        rows = _rows(conn.execute(
            """
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
                   MAX(r.created_at)                                AS last_at
              FROM requests r
              LEFT JOIN employees e ON e.user_id = r.user_id
             GROUP BY r.user_id
             ORDER BY total DESC, name COLLATE NOCASE
            """
        ))
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


def export_rows() -> list[dict]:
    with _ro() as conn:
        return _rows(conn.execute("SELECT * FROM requests ORDER BY id DESC"))
