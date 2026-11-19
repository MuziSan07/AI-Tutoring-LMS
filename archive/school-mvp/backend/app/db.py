"""SQLite persistence layer.

The schema mirrors what will move to PostgreSQL in production (see README);
all access goes through the small helpers below so the swap is contained.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("TUTOR_DB", os.path.join(os.path.dirname(__file__), "..", "tutor.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'school',
    licence_seats INTEGER NOT NULL DEFAULT 0,
    licence_expires TEXT
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    org_id INTEGER REFERENCES orgs(id),
    role TEXT NOT NULL CHECK (role IN ('student','parent','teacher','school_admin','super_admin')),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    year_group INTEGER,
    pseudonym_id TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS parent_links (
    parent_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (parent_id, student_id)
);
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY,
    org_id INTEGER REFERENCES orgs(id),
    name TEXT NOT NULL,
    teacher_id INTEGER REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS class_members (
    class_id INTEGER REFERENCES classes(id) ON DELETE CASCADE,
    student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (class_id, student_id)
);
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY,
    student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL,
    ended_at TEXT,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    state_json TEXT NOT NULL DEFAULT '{}',
    summary TEXT,
    board_json TEXT NOT NULL DEFAULT '[]',
    student_drawing TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    board_json TEXT,
    meta_json TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY,
    student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL,
    question_json TEXT NOT NULL,
    answer TEXT NOT NULL,
    result TEXT NOT NULL,
    correct INTEGER NOT NULL,
    misconception TEXT,
    difficulty INTEGER NOT NULL,
    hints_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mastery (
    student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL,
    p_mastery REAL NOT NULL DEFAULT 0.2,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    last_practised TEXT,
    next_review TEXT,
    interval_days INTEGER NOT NULL DEFAULT 0,
    effective_method TEXT,
    PRIMARY KEY (student_id, topic_id)
);
CREATE TABLE IF NOT EXISTS misconceptions (
    student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL,
    code TEXT NOT NULL,
    description TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    last_seen TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (student_id, topic_id, code)
);
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY,
    teacher_id INTEGER REFERENCES users(id),
    student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL,
    note TEXT,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS safeguarding_flags (
    id INTEGER PRIMARY KEY,
    student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER,
    category TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    action TEXT NOT NULL,
    target TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS student_settings (
    student_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    daily_limit_minutes INTEGER NOT NULL DEFAULT 60,
    voice_enabled INTEGER NOT NULL DEFAULT 1,
    avatar_enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY,
    student_id INTEGER,
    lesson_id INTEGER,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def all_rows(sql: str, args: tuple = ()) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def one(sql: str, args: tuple = ()) -> dict | None:
    with connect() as conn:
        row = conn.execute(sql, args).fetchone()
        return dict(row) if row else None


def execute(sql: str, args: tuple = ()) -> int:
    """Run a write statement and return lastrowid."""
    with connect() as conn:
        cur = conn.execute(sql, args)
        return cur.lastrowid


def audit(user_id: int | None, action: str, target: str | None = None) -> None:
    execute(
        "INSERT INTO audit_log (user_id, action, target, created_at) VALUES (?,?,?,?)",
        (user_id, action, target, now_iso()),
    )


def dumps(obj) -> str:
    return json.dumps(obj, default=str)
