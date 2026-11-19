"""Demo data: one school, a class, a parent, admins and students with history.

All accounts use the password in DEMO_PASSWORD. These are fictional test users.
"""
import random
import uuid
from datetime import date, datetime, timedelta, timezone

from . import auth, curriculum, db, memory

DEMO_PASSWORD = "demo1234"


def _ago(days: float, hours: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days, hours=hours)).isoformat(timespec="seconds")


def _user(org_id, role, email, name, year=None) -> int:
    return db.execute(
        "INSERT INTO users (org_id, role, email, password_hash, display_name, year_group, pseudonym_id, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (org_id, role, email, auth.hash_password(DEMO_PASSWORD), name, year, "stu_" + uuid.uuid4().hex[:10] if role == "student" else "usr_" + uuid.uuid4().hex[:10], _ago(40)))


def _history(student_id: int, topic_id: str, days_ago: float, results: list[tuple[int, bool, str | None]], minutes: int) -> int:
    """Create a completed past lesson from (difficulty, correct, misconception) tuples."""
    started = _ago(days_ago)
    lesson_id = db.execute(
        "INSERT INTO lessons (student_id, topic_id, status, started_at, last_active_at, ended_at, duration_seconds) VALUES (?,?,?,?,?,?,?)",
        (student_id, topic_id, "completed", started, started, started, minutes * 60))
    memory.get_mastery(student_id, topic_id)
    for i, (d, ok, mc) in enumerate(results):
        q = curriculum.generate_question(topic_id, d, seed=student_id * 7919 + lesson_id * 31 + i)
        answer = q["answer"] if ok else next((m["answer"] for m in q["misconceptions"] if m["code"] == mc), "0")
        db.execute(
            "INSERT INTO attempts (student_id, lesson_id, topic_id, question_json, answer, result, correct, misconception, difficulty, hints_used, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (student_id, lesson_id, topic_id, db.dumps(q), answer, "correct" if ok else "incorrect", int(ok), mc, d, 0, started))
        memory.record_evidence(student_id, topic_id, ok, assisted=False)
        if mc:
            memory.record_misconception(student_id, topic_id, mc, curriculum.MISCONCEPTIONS[mc])
    summary, stats = memory.summarise_lesson(lesson_id)
    db.execute("UPDATE lessons SET summary=?, board_json=? WHERE id=?", (summary, db.dumps([
        {"type": "title", "content": curriculum.topic(topic_id)["title"]}, {"type": "text", "content": summary}]), lesson_id))
    db.execute("UPDATE mastery SET last_practised=? WHERE student_id=? AND topic_id=?", (started, student_id, topic_id))
    return lesson_id


def _review(student_id: int, topic_id: str, due_in_days: int, interval: int) -> None:
    db.execute("UPDATE mastery SET next_review=?, interval_days=? WHERE student_id=? AND topic_id=?",
               ((date.today() + timedelta(days=due_in_days)).isoformat(), interval, student_id, topic_id))


def seed() -> None:
    if db.one("SELECT 1 FROM users LIMIT 1"):
        return
    org = db.execute("INSERT INTO orgs (name, kind, licence_seats, licence_expires) VALUES (?,?,?,?)",
                     ("Oakfield Academy (demo)", "school", 250, (date.today() + timedelta(days=300)).isoformat()))
    _user(None, "super_admin", "super@demo.platform", "Platform Admin")
    _user(org, "school_admin", "admin@demo.school", "Priya Shah")
    teacher = _user(org, "teacher", "teacher@demo.school", "James Wright")
    parent = _user(org, "parent", "parent@demo.school", "Sarah Clarke")
    amelia = _user(org, "student", "amelia@demo.school", "Amelia Clarke", 8)
    db.execute("INSERT INTO parent_links VALUES (?,?)", (parent, amelia))
    class_id = db.execute("INSERT INTO classes (org_id, name, teacher_id) VALUES (?,?,?)", (org, "8M Maths", teacher))

    # Amelia - the SOW memory example: fractions, fine with same denominators,
    # subtraction with different denominators was difficult.
    _history(amelia, "fractions-add", 2, [(1, True, None), (1, True, None), (1, True, None), (2, True, None),
                                           (3, False, "add_across"), (3, False, "add_across"), (3, True, None), (3, False, "numerators_not_scaled")], 18)
    _review(amelia, "fractions-add", 0, 1)
    _history(amelia, "expanding-brackets", 5, [(1, True, None), (1, True, None), (2, True, None), (2, True, None),
                                                (3, True, None), (3, True, None)], 15)
    _review(amelia, "expanding-brackets", 4, 7)

    rng = random.Random(42)
    classmates = [("Leo Patel", 8), ("Maya Okafor", 8), ("Noah Williams", 8), ("Isla Hughes", 8),
                  ("Zain Ahmed", 8), ("Grace Evans", 8), ("Oliver Bennett", 8)]
    students = [amelia]
    pool = list(curriculum.TOPICS)
    mc_by_topic = {
        "fractions-add": "add_across", "fractions-multiply": "forgot_reciprocal", "expanding-brackets": "partial_distribution",
        "linear-equations": "inverse_sign", "percentages": "change_only", "pythagoras": "forgot_sqrt", "straight-line-graphs": "confused_m_c"}
    for name, year in classmates:
        sid = _user(org, "student", name.split()[0].lower() + "@demo.school", name, year)
        students.append(sid)
        for k, tid in enumerate(rng.sample(pool, rng.randint(2, 4))):
            skill = rng.random()
            results = []
            for i in range(rng.randint(5, 9)):
                d = 1 + min(2, i // 3)
                ok = rng.random() < 0.35 + skill * 0.6
                results.append((d, ok, None if ok or rng.random() < 0.4 else mc_by_topic[tid]))
            _history(sid, tid, rng.uniform(1, 14), results, rng.randint(10, 30))
            _review(sid, tid, rng.randint(-2, 6), rng.randint(1, 7))
    for sid in students:
        db.execute("INSERT INTO class_members VALUES (?,?)", (class_id, sid))
        db.execute("INSERT INTO student_settings (student_id) VALUES (?)", (sid,))

    db.execute("INSERT INTO assignments (teacher_id, student_id, topic_id, note, due_date, created_at) VALUES (?,?,?,?,?,?)",
               (teacher, amelia, "linear-equations", "Homework: complete a lesson on linear equations",
                (date.today() + timedelta(days=3)).isoformat(), _ago(1)))
    db.audit(None, "demo_data_seeded", f"org:{org}")
