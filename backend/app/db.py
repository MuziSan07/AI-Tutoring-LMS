"""SQLite persistence layer for the LMS.

The schema mirrors what will move to PostgreSQL in production (see README);
all access goes through the small helpers below so the swap is contained.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("TUTOR_DB", os.path.join(os.path.dirname(__file__), "..", "lms.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('learner','instructor','admin')),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    headline TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
-- What the AI tutor knows about how each learner wants to learn
CREATE TABLE IF NOT EXISTS learner_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    goal TEXT,
    experience TEXT NOT NULL DEFAULT 'beginner',
    interests_json TEXT NOT NULL DEFAULT '[]',
    style TEXT NOT NULL DEFAULT 'examples',
    weekly_goal_minutes INTEGER NOT NULL DEFAULT 120,
    voice_enabled INTEGER NOT NULL DEFAULT 1,
    avatar_enabled INTEGER NOT NULL DEFAULT 1,
    onboarded INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    subtitle TEXT,
    description TEXT,
    category TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'Beginner',
    colour TEXT NOT NULL DEFAULT '#4f46e5',
    icon TEXT NOT NULL DEFAULT '📘',
    outcomes_json TEXT NOT NULL DEFAULT '[]',
    instructor_id INTEGER REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS modules (
    id INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY,
    module_id INTEGER REFERENCES modules(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('article','video','quiz','assignment')),
    content_md TEXT NOT NULL DEFAULT '',
    video_url TEXT,
    duration_min INTEGER NOT NULL DEFAULT 5,
    concepts_json TEXT NOT NULL DEFAULT '[]',
    quiz_json TEXT,
    rubric_json TEXT,
    position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS enrollments (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    enrolled_at TEXT NOT NULL,
    completed_at TEXT,
    last_lesson_id INTEGER,
    last_active_at TEXT,
    PRIMARY KEY (user_id, course_id)
);
CREATE TABLE IF NOT EXISTS lesson_progress (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'started',
    best_score REAL,
    seconds_spent INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, lesson_id)
);
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    answers_json TEXT NOT NULL,
    results_json TEXT NOT NULL,
    score REAL NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    auto_feedback_json TEXT,
    grade TEXT,
    instructor_feedback TEXT,
    status TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','graded')),
    created_at TEXT NOT NULL,
    graded_at TEXT
);
-- Evidence-based mastery of each concept a course teaches
CREATE TABLE IF NOT EXISTS concept_mastery (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    concept TEXT NOT NULL,
    p_mastery REAL NOT NULL DEFAULT 0.2,
    evidence INTEGER NOT NULL DEFAULT 0,
    correct INTEGER NOT NULL DEFAULT 0,
    next_review TEXT,
    interval_days INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, course_id, concept)
);
CREATE TABLE IF NOT EXISTS notes (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, lesson_id)
);
CREATE TABLE IF NOT EXISTS discussions (
    id INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES discussions(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    body TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, course_id)
);
CREATE TABLE IF NOT EXISTS certificates (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    issued_at TEXT NOT NULL,
    UNIQUE (user_id, course_id)
);
CREATE TABLE IF NOT EXISTS tutor_conversations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    practice_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tutor_messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER REFERENCES tutor_conversations(id) ON DELETE CASCADE,
    lesson_id INTEGER,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    meta_json TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    seconds INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS moderation_flags (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
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
CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    course_id INTEGER,
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


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


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


def loads(text: str | None, default=None):
    return json.loads(text) if text else default
