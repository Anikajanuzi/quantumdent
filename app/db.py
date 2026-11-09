"""SQLite storage. Suitable for local development and small single-server deployments.
For production with several app instances, move to PostgreSQL (schema is portable)."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ref              TEXT NOT NULL UNIQUE,
    idempotency_key  TEXT NOT NULL UNIQUE,
    patient_name     TEXT NOT NULL,
    patient_email    TEXT NOT NULL,
    patient_phone    TEXT NOT NULL,
    specialist_id    TEXT NOT NULL,
    reason           TEXT NOT NULL,
    preferred_date   TEXT NOT NULL,
    preferred_time   TEXT NOT NULL,
    message          TEXT NOT NULL DEFAULT '',
    traveling        INTEGER NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'pending',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contact_messages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ref              TEXT NOT NULL UNIQUE,
    idempotency_key  TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    email            TEXT NOT NULL,
    subject          TEXT NOT NULL,
    message          TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS email_attempts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_ref       TEXT NOT NULL,
    kind             TEXT NOT NULL,
    recipient        TEXT NOT NULL,
    status           TEXT NOT NULL,
    attempts         INTEGER NOT NULL DEFAULT 0,
    last_error       TEXT NOT NULL DEFAULT '',
    message_id       TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    UNIQUE (source_ref, kind, recipient)
);
CREATE INDEX IF NOT EXISTS idx_attempts_ref ON email_attempts(source_ref);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)

    @contextmanager
    def tx(self):
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def query(self, sql: str, params=()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params=()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # ---------- appointments ----------
    def find_appointment_by_key(self, key: str) -> dict | None:
        return self.one("SELECT * FROM appointments WHERE idempotency_key = ?", (key,))

    def get_appointment(self, ref: str) -> dict | None:
        return self.one("SELECT * FROM appointments WHERE ref = ?", (ref,))

    def insert_appointment(self, rec: dict) -> tuple[dict, bool]:
        """Insert unless the idempotency key already exists. Returns (row, created)."""
        with self.tx() as c:
            existing = c.execute(
                "SELECT * FROM appointments WHERE idempotency_key = ?", (rec["idempotency_key"],)
            ).fetchone()
            if existing:
                return dict(existing), False
            ts = now_iso()
            c.execute(
                """INSERT INTO appointments (ref, idempotency_key, patient_name, patient_email,
                   patient_phone, specialist_id, reason, preferred_date, preferred_time, message,
                   traveling, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?, 'pending', ?, ?)""",
                (rec["ref"], rec["idempotency_key"], rec["patient_name"], rec["patient_email"],
                 rec["patient_phone"], rec["specialist_id"], rec["reason"], rec["preferred_date"],
                 rec["preferred_time"], rec.get("message", ""), int(rec.get("traveling", False)), ts, ts),
            )
            row = c.execute("SELECT * FROM appointments WHERE ref = ?", (rec["ref"],)).fetchone()
            return dict(row), True

    def list_appointments(self, limit: int = 200) -> list[dict]:
        return self.query("SELECT * FROM appointments ORDER BY id DESC LIMIT ?", (limit,))

    def set_appointment_status(self, ref: str, status: str) -> bool:
        with self.tx() as c:
            cur = c.execute("UPDATE appointments SET status = ?, updated_at = ? WHERE ref = ?",
                            (status, now_iso(), ref))
            return cur.rowcount > 0

    # ---------- contact ----------
    def insert_contact(self, rec: dict) -> tuple[dict, bool]:
        with self.tx() as c:
            existing = c.execute("SELECT * FROM contact_messages WHERE idempotency_key = ?",
                                 (rec["idempotency_key"],)).fetchone()
            if existing:
                return dict(existing), False
            c.execute(
                """INSERT INTO contact_messages (ref, idempotency_key, name, email, subject, message, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (rec["ref"], rec["idempotency_key"], rec["name"], rec["email"], rec["subject"],
                 rec["message"], now_iso()),
            )
            return dict(c.execute("SELECT * FROM contact_messages WHERE ref = ?", (rec["ref"],)).fetchone()), True

    def list_contacts(self, limit: int = 200) -> list[dict]:
        return self.query("SELECT * FROM contact_messages ORDER BY id DESC LIMIT ?", (limit,))

    def get_contact(self, ref: str) -> dict | None:
        return self.one("SELECT * FROM contact_messages WHERE ref = ?", (ref,))

    # ---------- email attempts ----------
    def claim_email(self, source_ref: str, kind: str, recipient: str) -> dict | None:
        """Reserve an email slot. Returns the row if it should be sent now, or None if it has
        already been accepted / is in flight (prevents duplicate sends on retries)."""
        with self.tx() as c:
            row = c.execute(
                "SELECT * FROM email_attempts WHERE source_ref=? AND kind=? AND recipient=?",
                (source_ref, kind, recipient)).fetchone()
            ts = now_iso()
            if row is None:
                c.execute(
                    """INSERT INTO email_attempts (source_ref, kind, recipient, status, attempts, created_at, updated_at)
                       VALUES (?,?,?, 'sending', 1, ?, ?)""", (source_ref, kind, recipient, ts, ts))
            else:
                if row["status"] in ("accepted", "outbox", "sending"):
                    return None
                c.execute("UPDATE email_attempts SET status='sending', attempts=attempts+1, updated_at=? WHERE id=?",
                          (ts, row["id"]))
            return dict(c.execute(
                "SELECT * FROM email_attempts WHERE source_ref=? AND kind=? AND recipient=?",
                (source_ref, kind, recipient)).fetchone())

    def finish_email(self, attempt_id: int, status: str, error: str = "", message_id: str = "") -> None:
        with self.tx() as c:
            c.execute("UPDATE email_attempts SET status=?, last_error=?, message_id=?, updated_at=? WHERE id=?",
                      (status, error[:500], message_id, now_iso(), attempt_id))

    def email_attempts_for(self, source_ref: str) -> list[dict]:
        return self.query("SELECT * FROM email_attempts WHERE source_ref=? ORDER BY id", (source_ref,))

    def recent_email_attempts(self, limit: int = 100) -> list[dict]:
        return self.query("SELECT * FROM email_attempts ORDER BY updated_at DESC, id DESC LIMIT ?", (limit,))
