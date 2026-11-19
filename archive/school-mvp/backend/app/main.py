"""HTTP API for the AI tutoring platform MVP."""
import json
import os
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, curriculum, db, llm, memory, seed, tutor
from .auth import current_user, ensure_can_view_student, require_role

db.init_db()
seed.seed()
llm.warm_up()

app = FastAPI(title="Nova AI Tutor - MVP", version="0.1.0")


# ------------------------------------------------------------------ schemas

class Login(BaseModel):
    email: str
    password: str


class StartLesson(BaseModel):
    topic_id: str


class StudentMessage(BaseModel):
    text: str


class Drawing(BaseModel):
    image: str  # data URL of the student's whiteboard layer


class Assign(BaseModel):
    topic_id: str
    student_ids: list[int]
    note: str | None = None
    due_date: str | None = None


class Settings(BaseModel):
    daily_limit_minutes: int
    voice_enabled: bool
    avatar_enabled: bool


class FlagUpdate(BaseModel):
    status: str


# ------------------------------------------------------------------ helpers

def _student(student_id: int) -> dict:
    s = db.one("SELECT id, display_name, year_group, pseudonym_id, org_id FROM users WHERE id=? AND role='student'", (student_id,))
    if not s:
        raise HTTPException(404, "Student not found")
    return s


def _settings(student_id: int) -> dict:
    row = db.one("SELECT * FROM student_settings WHERE student_id=?", (student_id,))
    if not row:
        db.execute("INSERT INTO student_settings (student_id) VALUES (?)", (student_id,))
        row = db.one("SELECT * FROM student_settings WHERE student_id=?", (student_id,))
    return row


def student_progress(student_id: int) -> dict:
    """The individual progress profile shared by student, parent and teacher views."""
    mastery = memory.all_mastery(student_id)
    topics = []
    for tid in curriculum.TOPICS:
        m = mastery.get(tid)
        topics.append({**curriculum.public_topic(tid),
                       "p_mastery": round(m["p_mastery"], 2) if m else 0,
                       "evidence": m["evidence_count"] if m else 0,
                       "status": memory.status_label(m),
                       "next_review": m["next_review"] if m else None,
                       "last_practised": m["last_practised"] if m else None})
    lessons = db.all_rows("SELECT id, topic_id, status, started_at, duration_seconds, summary FROM lessons WHERE student_id=? ORDER BY started_at DESC",
                          (student_id,))
    for l in lessons:
        l["title"] = curriculum.topic(l["topic_id"])["title"]
    totals = db.one("SELECT COUNT(*) n, COALESCE(SUM(correct),0) c FROM attempts WHERE student_id=?", (student_id,))
    started = [t for t in topics if t["evidence"]]
    return {
        "student": _student(student_id),
        "topics": topics,
        "lessons": lessons,
        "misconceptions": memory.open_misconceptions(student_id),
        "recommendations": memory.recommendations(student_id),
        "revision": sorted([{"topic_id": t["id"], "title": t["title"], "due": t["next_review"]} for t in topics if t["next_review"]],
                           key=lambda r: r["due"]),
        "assignments": [{**a, "title": curriculum.topic(a["topic_id"])["title"]} for a in db.all_rows(
            "SELECT a.*, u.display_name teacher FROM assignments a LEFT JOIN users u ON u.id=a.teacher_id "
            "WHERE a.student_id=? ORDER BY a.status DESC, a.due_date", (student_id,))],
        "stats": {
            "lessons": len(lessons),
            "minutes": round(sum(l["duration_seconds"] for l in lessons) / 60),
            "minutes_today": memory.minutes_today(student_id),
            "questions": totals["n"], "accuracy": round(totals["c"] / totals["n"], 2) if totals["n"] else 0,
            "secure": sum(1 for t in topics if t["status"] == "Secure"),
            "strengths": [t["title"] for t in sorted(started, key=lambda t: -t["p_mastery"]) if t["p_mastery"] >= 0.6][:3],
            "weaknesses": [t["title"] for t in sorted(started, key=lambda t: t["p_mastery"]) if t["p_mastery"] < 0.6][:3],
        },
        "settings": _settings(student_id),
    }


# ------------------------------------------------------------------ auth & system

@app.post("/api/auth/login")
def login(body: Login):
    user = db.one("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),))
    if not user or not auth.check_password(body.password, user["password_hash"]):
        db.audit(None, "login_failed", body.email[:80])
        raise HTTPException(401, "Email or password is incorrect")
    db.audit(user["id"], "login")
    user.pop("password_hash")
    return {"token": auth.make_token(user["id"]), "user": user}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return user


@app.get("/api/system/status")
def system_status():
    return {"llm": llm.status(), "content_version": curriculum.CONTENT_VERSION, "math_verification": "SymPy"}


@app.get("/api/curriculum")
def get_curriculum(user=Depends(current_user)):
    return {"subjects": curriculum.SUBJECTS, "topics": [curriculum.public_topic(t) for t in curriculum.TOPICS]}


# ------------------------------------------------------------------ student

@app.get("/api/student/dashboard")
def student_dashboard(user=Depends(current_user)):
    require_role(user, "student")
    return student_progress(user["id"])


@app.post("/api/lessons/start")
def start_lesson(body: StartLesson, user=Depends(current_user)):
    require_role(user, "student")
    if body.topic_id not in curriculum.TOPICS:
        raise HTTPException(404, "Unknown topic")
    limit = _settings(user["id"])["daily_limit_minutes"]
    if limit and memory.minutes_today(user["id"]) >= limit:
        raise HTTPException(429, f"You've reached today's learning limit of {limit} minutes set by your parent or carer. Great effort - see you tomorrow!")
    lesson_id, turns, progress = tutor.start_lesson(user, body.topic_id)
    lesson = db.one("SELECT board_json FROM lessons WHERE id=?", (lesson_id,))
    return {"lesson_id": lesson_id, "topic": curriculum.public_topic(body.topic_id), "turns": turns, "progress": progress,
            "board": json.loads(lesson["board_json"]), "settings": _settings(user["id"])}


@app.post("/api/lessons/{lesson_id}/message")
def lesson_message(lesson_id: int, body: StudentMessage, user=Depends(current_user)):
    require_role(user, "student")
    text = body.text.strip()[:500]
    if not text:
        raise HTTPException(400, "Empty message")
    try:
        turns, progress = tutor.handle_message(user, lesson_id, text)
    except LookupError:
        raise HTTPException(404, "Lesson not found")
    return {"turns": turns, "progress": progress}


@app.post("/api/lessons/{lesson_id}/drawing")
def save_drawing(lesson_id: int, body: Drawing, user=Depends(current_user)):
    require_role(user, "student")
    if len(body.image) > 2_000_000:
        raise HTTPException(413, "Drawing too large")
    db.execute("UPDATE lessons SET student_drawing=? WHERE id=? AND student_id=?", (body.image, lesson_id, user["id"]))
    return {"ok": True}


@app.post("/api/lessons/{lesson_id}/end")
def end_lesson(lesson_id: int, user=Depends(current_user)):
    require_role(user, "student")
    try:
        return tutor.end_lesson(user, lesson_id)
    except LookupError:
        raise HTTPException(404, "Lesson not found")


@app.get("/api/lessons/{lesson_id}")
def lesson_detail(lesson_id: int, user=Depends(current_user)):
    lesson = db.one("SELECT * FROM lessons WHERE id=?", (lesson_id,))
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    ensure_can_view_student(user, lesson["student_id"])
    messages = db.all_rows("SELECT role, text, board_json, created_at FROM messages WHERE lesson_id=? ORDER BY id", (lesson_id,))
    attempts = db.all_rows("SELECT answer, result, correct, misconception, difficulty, hints_used, question_json, created_at FROM attempts WHERE lesson_id=? ORDER BY id",
                           (lesson_id,))
    for a in attempts:
        q = json.loads(a.pop("question_json"))
        a["question"] = q["prompt"]
        a["expected"] = q["answer_latex"]
    return {"lesson": {**{k: v for k, v in lesson.items() if k not in ("state_json",)},
                       "board_json": json.loads(lesson["board_json"]),
                       "title": curriculum.topic(lesson["topic_id"])["title"]},
            "messages": [{**m, "board_json": json.loads(m["board_json"]) if m["board_json"] else []} for m in messages],
            "attempts": attempts}


@app.put("/api/student/settings")
def student_settings(body: Settings, user=Depends(current_user)):
    require_role(user, "student")
    db.execute("UPDATE student_settings SET voice_enabled=?, avatar_enabled=? WHERE student_id=?",
               (int(body.voice_enabled), int(body.avatar_enabled), user["id"]))
    return _settings(user["id"])


# ------------------------------------------------------------------ parent

@app.get("/api/parent/overview")
def parent_overview(user=Depends(current_user)):
    require_role(user, "parent")
    children = db.all_rows("SELECT student_id FROM parent_links WHERE parent_id=?", (user["id"],))
    for c in children:
        db.audit(user["id"], "viewed_student_record", f"student:{c['student_id']}")
    return {"children": [student_progress(c["student_id"]) for c in children]}


@app.put("/api/parent/settings/{student_id}")
def parent_settings(student_id: int, body: Settings, user=Depends(current_user)):
    require_role(user, "parent")
    ensure_can_view_student(user, student_id)
    _settings(student_id)
    db.execute("UPDATE student_settings SET daily_limit_minutes=?, voice_enabled=?, avatar_enabled=? WHERE student_id=?",
               (max(0, min(600, body.daily_limit_minutes)), int(body.voice_enabled), int(body.avatar_enabled), student_id))
    db.audit(user["id"], "updated_usage_controls", f"student:{student_id}")
    return _settings(student_id)


# ------------------------------------------------------------------ teacher

@app.get("/api/teacher/overview")
def teacher_overview(user=Depends(current_user)):
    require_role(user, "teacher")
    classes = db.all_rows("SELECT * FROM classes WHERE teacher_id=?", (user["id"],))
    out = []
    for c in classes:
        students = db.all_rows("SELECT u.id, u.display_name, u.year_group FROM class_members cm JOIN users u ON u.id=cm.student_id "
                               "WHERE cm.class_id=? ORDER BY u.display_name", (c["id"],))
        ids = [s["id"] for s in students]
        marks = ",".join("?" * len(ids)) or "NULL"
        for s in students:
            m = memory.all_mastery(s["id"])
            s["mastery"] = {tid: {"p": round(m[tid]["p_mastery"], 2), "status": memory.status_label(m[tid])} for tid in m}
            last = db.one("SELECT MAX(last_active_at) t FROM lessons WHERE student_id=?", (s["id"],))
            s["last_active"] = last["t"]
            s["open_misconceptions"] = len(memory.open_misconceptions(s["id"]))
        difficulties = db.all_rows(
            f"SELECT topic_id, code, description, COUNT(*) students, SUM(count) occurrences FROM misconceptions "
            f"WHERE student_id IN ({marks}) AND resolved=0 GROUP BY topic_id, code ORDER BY students DESC, occurrences DESC", tuple(ids))
        for d in difficulties:
            d["topic"] = curriculum.topic(d["topic_id"])["title"]
        results = db.all_rows(
            f"SELECT a.topic_id, COUNT(*) n, SUM(a.correct) c FROM attempts a WHERE a.student_id IN ({marks}) GROUP BY a.topic_id", tuple(ids))
        assignments = db.all_rows(
            f"SELECT a.*, u.display_name student FROM assignments a JOIN users u ON u.id=a.student_id WHERE a.student_id IN ({marks}) "
            "ORDER BY a.created_at DESC LIMIT 30", tuple(ids))
        for a in assignments:
            a["topic"] = curriculum.topic(a["topic_id"])["title"]
        out.append({"class": c, "students": students, "difficulties": difficulties[:8],
                    "exercise_results": [{**r, "topic": curriculum.topic(r["topic_id"])["title"],
                                          "accuracy": round(r["c"] / r["n"], 2)} for r in results],
                    "assignments": assignments})
    db.audit(user["id"], "viewed_class_overview")
    return {"classes": out, "topics": [curriculum.public_topic(t) for t in curriculum.TOPICS]}


@app.get("/api/students/{student_id}/progress")
def get_student_progress(student_id: int, user=Depends(current_user)):
    ensure_can_view_student(user, student_id)
    return student_progress(student_id)


@app.post("/api/teacher/assign")
def assign(body: Assign, user=Depends(current_user)):
    require_role(user, "teacher")
    if body.topic_id not in curriculum.TOPICS:
        raise HTTPException(404, "Unknown topic")
    for sid in body.student_ids:
        ensure_can_view_student(user, sid)
        db.execute("INSERT INTO assignments (teacher_id, student_id, topic_id, note, due_date, created_at) VALUES (?,?,?,?,?,?)",
                   (user["id"], sid, body.topic_id, body.note, body.due_date, db.now_iso()))
    db.audit(user["id"], "assigned_activity", f"{body.topic_id} -> {len(body.student_ids)} students")
    return {"assigned": len(body.student_ids)}


# ------------------------------------------------------------------ school / platform admin

@app.get("/api/admin/overview")
def admin_overview(user=Depends(current_user)):
    require_role(user, "school_admin", "super_admin")
    scope = "" if user["role"] == "super_admin" else " AND u.org_id = ?"
    args = () if user["role"] == "super_admin" else (user["org_id"],)
    orgs = db.all_rows("SELECT * FROM orgs" + ("" if user["role"] == "super_admin" else " WHERE id=?"), args)
    users = db.all_rows(f"SELECT u.id, u.role, u.display_name, u.email, u.year_group, u.pseudonym_id, u.created_at FROM users u WHERE 1=1{scope} "
                        "ORDER BY u.role, u.display_name", args)
    usage = db.one(f"SELECT COUNT(DISTINCT l.student_id) active, COUNT(*) lessons, COALESCE(SUM(l.duration_seconds),0) secs "
                   f"FROM lessons l JOIN users u ON u.id=l.student_id WHERE l.started_at >= date('now','-30 day'){scope}", args)
    daily = db.all_rows(f"SELECT substr(l.started_at,1,10) day, COUNT(*) lessons, SUM(l.duration_seconds)/60 minutes FROM lessons l "
                        f"JOIN users u ON u.id=l.student_id WHERE l.started_at >= date('now','-14 day'){scope} GROUP BY day ORDER BY day", args)
    perf = db.all_rows(f"SELECT a.topic_id, COUNT(*) n, SUM(a.correct) c, COUNT(DISTINCT a.student_id) students FROM attempts a "
                       f"JOIN users u ON u.id=a.student_id WHERE 1=1{scope} GROUP BY a.topic_id", args)
    flags = db.all_rows(f"SELECT f.*, u.pseudonym_id, u.display_name FROM safeguarding_flags f JOIN users u ON u.id=f.student_id "
                        f"WHERE 1=1{scope} ORDER BY f.created_at DESC", args)
    audit = db.all_rows(f"SELECT a.*, u.display_name, u.role FROM audit_log a LEFT JOIN users u ON u.id=a.user_id "
                        f"WHERE (u.id IS NULL OR 1=1{scope}) ORDER BY a.id DESC LIMIT 40", args)
    ai = db.all_rows(f"SELECT l.provider, l.model, COUNT(*) calls, SUM(l.input_tokens) input_tokens, SUM(l.output_tokens) output_tokens, "
                     f"SUM(l.cost_usd) cost_usd, AVG(l.latency_ms) avg_latency_ms, COUNT(DISTINCT l.student_id) students "
                     f"FROM llm_usage l LEFT JOIN users u ON u.id=l.student_id WHERE 1=1{scope} GROUP BY l.provider, l.model", args)
    db.audit(user["id"], "viewed_admin_overview")
    return {
        "orgs": orgs, "users": users,
        "usage": {"active_students_30d": usage["active"], "lessons_30d": usage["lessons"], "tutoring_minutes_30d": round(usage["secs"] / 60),
                  "registered_students": sum(1 for u in users if u["role"] == "student")},
        "daily": daily,
        "performance": [{**p, "topic": curriculum.topic(p["topic_id"])["title"], "accuracy": round(p["c"] / p["n"], 2)} for p in perf],
        "flags": flags, "audit": audit, "ai_usage": ai, "llm": llm.status(),
    }


@app.put("/api/admin/flags/{flag_id}")
def update_flag(flag_id: int, body: FlagUpdate, user=Depends(current_user)):
    require_role(user, "school_admin", "super_admin")
    flag = db.one("SELECT * FROM safeguarding_flags WHERE id=?", (flag_id,))
    if not flag:
        raise HTTPException(404, "Flag not found")
    ensure_can_view_student(user, flag["student_id"])
    db.execute("UPDATE safeguarding_flags SET status=? WHERE id=?", (body.status, flag_id))
    db.audit(user["id"], f"safeguarding_flag_{body.status}", f"flag:{flag_id}")
    return {"ok": True}


@app.get("/api/students/{student_id}/export")
def export_student(student_id: int, user=Depends(current_user)):
    """Learning profile export (UK GDPR right of access / portability)."""
    ensure_can_view_student(user, student_id)
    if user["role"] == "teacher":
        raise HTTPException(403, "Exports are available to the student, parent or school administrator")
    db.audit(user["id"], "exported_learning_profile", f"student:{student_id}")
    data = student_progress(student_id)
    data["attempts"] = db.all_rows("SELECT topic_id, answer, result, misconception, difficulty, hints_used, created_at FROM attempts WHERE student_id=?",
                                   (student_id,))
    data["exported_at"] = db.now_iso()
    return data


@app.delete("/api/students/{student_id}/learning-data")
def delete_learning_data(student_id: int, user=Depends(current_user)):
    """Right to erasure: removes the learning record but keeps the account shell."""
    require_role(user, "school_admin", "super_admin")
    ensure_can_view_student(user, student_id)
    for table in ("attempts", "lessons", "mastery", "misconceptions", "assignments"):
        db.execute(f"DELETE FROM {table} WHERE student_id=?", (student_id,))
    db.audit(user["id"], "deleted_learning_data", f"student:{student_id}")
    return {"deleted": True}


# ------------------------------------------------------------------ frontend

DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        target = os.path.join(DIST, path)
        if path and os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(os.path.join(DIST, "index.html"))
