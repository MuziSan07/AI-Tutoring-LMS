"""HTTP API for Nova Academy - an LMS for digital courses with personalised AI tutors."""
import json
import os
import re

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, db, learning, llm, seed, tutor
from .auth import STAFF, current_user, ensure_self_or_staff, require_role
from .seed_content import CATEGORIES

db.init_db()
seed.seed()
llm.warm_up()

app = FastAPI(title="Nova Academy", version="0.2.0")


# ------------------------------------------------------------------ schemas

class Login(BaseModel):
    email: str
    password: str


class Register(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: str = Field(max_length=120)
    password: str = Field(min_length=8, max_length=128)


class Profile(BaseModel):
    goal: str | None = None
    experience: str = "beginner"
    interests: list[str] = []
    style: str = "examples"
    weekly_goal_minutes: int = 120
    voice_enabled: bool = True
    avatar_enabled: bool = True


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    body: str | None = Field(default=None, max_length=1000)


class QuizIn(BaseModel):
    answers: list


class TextIn(BaseModel):
    body: str = Field(min_length=1, max_length=20000)


class PostIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    parent_id: int | None = None


class Heartbeat(BaseModel):
    seconds: int


class TutorIn(BaseModel):
    text: str | None = None
    action: str | None = None
    lesson_id: int | None = None


class CourseIn(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    category: str | None = None
    level: str | None = None
    colour: str | None = None
    icon: str | None = None
    outcomes: list[str] | None = None
    status: str | None = None


class TitleIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class LessonNew(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    kind: str


class LessonIn(BaseModel):
    title: str | None = None
    kind: str | None = None
    content_md: str | None = None
    video_url: str | None = None
    duration_min: int | None = None
    concepts: list[str] | None = None
    quiz: list[dict] | None = None
    rubric: list[dict] | None = None


class MoveIn(BaseModel):
    type: str
    id: int
    direction: str


class GradeIn(BaseModel):
    grade: str = Field(min_length=1, max_length=20)
    feedback: str = Field(default="", max_length=4000)


class UserAdmin(BaseModel):
    role: str | None = None
    active: bool | None = None


class StatusIn(BaseModel):
    status: str


# ------------------------------------------------------------------ helpers

def _course_or_404(course_id: int, user: dict | None = None) -> dict:
    c = learning.course(course_id)
    if not c or (c["status"] != "published" and (not user or user["role"] not in STAFF)):
        raise HTTPException(404, "Course not found")
    return c


def _lesson_for_learner(lesson_id: int, user: dict) -> dict:
    l = learning.lesson(lesson_id)
    if not l:
        raise HTTPException(404, "Lesson not found")
    if user["role"] not in STAFF and not learning.is_enrolled(user["id"], l["course_id"]):
        raise HTTPException(403, "Enrol in the course to access its lessons")
    return l


def _touch_course(course_id: int) -> None:
    db.execute("UPDATE courses SET updated_at=? WHERE id=?", (db.now_iso(), course_id))


def _slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "course"
    slug, n = base, 2
    while db.one("SELECT 1 FROM courses WHERE slug=?", (slug,)):
        slug, n = f"{base}-{n}", n + 1
    return slug


# ------------------------------------------------------------------ auth & system

@app.post("/api/auth/login")
def login(body: Login):
    user = db.one("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),))
    if not user or not auth.check_password(body.password, user["password_hash"]):
        db.audit(None, "login_failed", body.email[:80])
        raise HTTPException(401, "Email or password is incorrect")
    if not user["active"]:
        raise HTTPException(403, "This account has been deactivated")
    db.audit(user["id"], "login")
    return {"token": auth.make_token(user["id"]), "user": auth.public_user(user)}


@app.post("/api/auth/register")
def register(body: Register):
    email = body.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Please enter a valid email address")
    if db.one("SELECT 1 FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "An account with this email already exists")
    uid = db.execute("INSERT INTO users (role, email, password_hash, display_name, created_at) VALUES ('learner',?,?,?,?)",
                     (email, auth.hash_password(body.password), body.name.strip(), db.now_iso()))
    learning.profile(uid)
    db.audit(uid, "registered")
    user = db.one("SELECT * FROM users WHERE id=?", (uid,))
    return {"token": auth.make_token(uid), "user": auth.public_user(user)}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return {**user, "profile": learning.profile(user["id"]) if user["role"] == "learner" else None}


@app.get("/api/system/status")
def system_status():
    return {"llm": llm.status(), "categories": CATEGORIES}


# ------------------------------------------------------------------ profile

@app.get("/api/profile")
def get_profile(user=Depends(current_user)):
    return learning.profile(user["id"])


@app.put("/api/profile")
def put_profile(body: Profile, user=Depends(current_user)):
    if body.style not in tutor.STYLE_GUIDE or body.experience not in ("beginner", "intermediate", "advanced"):
        raise HTTPException(400, "Unknown learning style or experience level")
    learning.profile(user["id"])
    db.execute("UPDATE learner_profiles SET goal=?, experience=?, interests_json=?, style=?, weekly_goal_minutes=?, voice_enabled=?, "
               "avatar_enabled=?, onboarded=1 WHERE user_id=?",
               (body.goal, body.experience, db.dumps([i for i in body.interests if i in CATEGORIES]), body.style,
                max(15, min(1200, body.weekly_goal_minutes)), int(body.voice_enabled), int(body.avatar_enabled), user["id"]))
    return learning.profile(user["id"])


# ------------------------------------------------------------------ catalogue

@app.get("/api/courses")
def catalogue(q: str = "", category: str = "", level: str = "", user=Depends(current_user)):
    rows = db.all_rows("SELECT * FROM courses WHERE status='published' ORDER BY title")
    out = []
    for c in rows:
        text = f"{c['title']} {c['subtitle']} {c['description']} {c['category']}".lower()
        if q and not all(w in text for w in q.lower().split()):
            continue
        if (category and c["category"] != category) or (level and c["level"] != level):
            continue
        c["outcomes"] = db.loads(c.pop("outcomes_json"), [])
        out.append(learning.course_card(c, user["id"]))
    return out


@app.get("/api/courses/{slug}")
def course_page(slug: str, user=Depends(current_user)):
    c = learning.course_by_slug(slug)
    if not c:
        raise HTTPException(404, "Course not found")
    _course_or_404(c["id"], user)
    tree = learning.course_tree(c["id"], user["id"])
    card = learning.course_card(c, user["id"])
    reviews = db.all_rows("SELECT r.rating, r.body, r.created_at, u.display_name FROM reviews r JOIN users u ON u.id=r.user_id "
                          "WHERE r.course_id=? ORDER BY r.created_at DESC LIMIT 20", (c["id"],))
    mine = db.one("SELECT rating, body FROM reviews WHERE user_id=? AND course_id=?", (user["id"], c["id"]))
    return {**tree, **card, "description": c["description"], "outcomes": c["outcomes"], "review_list": reviews, "my_review": mine}


@app.post("/api/courses/{course_id}/enrol")
def enrol(course_id: int, user=Depends(current_user)):
    _course_or_404(course_id, user)
    learning.enrol(user["id"], course_id)
    db.audit(user["id"], "enrolled", f"course:{course_id}")
    return learning.progress_of(user["id"], course_id)


@app.post("/api/courses/{course_id}/review")
def review(course_id: int, body: ReviewIn, user=Depends(current_user)):
    if not learning.is_enrolled(user["id"], course_id):
        raise HTTPException(403, "Enrol in the course before reviewing it")
    db.execute("INSERT INTO reviews (user_id, course_id, rating, body, created_at) VALUES (?,?,?,?,?) "
               "ON CONFLICT(user_id, course_id) DO UPDATE SET rating=excluded.rating, body=excluded.body, created_at=excluded.created_at",
               (user["id"], course_id, body.rating, (body.body or "").strip() or None, db.now_iso()))
    return {"ok": True}


# ------------------------------------------------------------------ learner home

@app.get("/api/learner/home")
def learner_home(user=Depends(current_user)):
    prof = learning.profile(user["id"])
    enrolled = db.all_rows("SELECT * FROM enrollments WHERE user_id=? ORDER BY last_active_at DESC", (user["id"],))
    in_progress, completed = [], []
    for e in enrolled:
        c = learning.course(e["course_id"])
        card = learning.course_card(c, user["id"])
        card["weak"] = learning.weak_concepts(user["id"], c["id"])[:2]
        (completed if e["completed_at"] else in_progress).append(card)
    return {
        "profile": prof, "streak": learning.streak(user["id"]),
        "week_minutes": learning.minutes_this_week(user["id"]), "week_goal": prof["weekly_goal_minutes"],
        "in_progress": in_progress, "completed": completed,
        "reviews_due": learning.reviews_due(user["id"])[:5],
        "recommended": learning.recommended_courses(user["id"]),
        "certificates": db.one("SELECT COUNT(*) n FROM certificates WHERE user_id=?", (user["id"],))["n"],
    }


@app.get("/api/learner/certificates")
def my_certificates(user=Depends(current_user)):
    return db.all_rows("SELECT ce.code, ce.issued_at, c.title, c.colour, c.icon FROM certificates ce JOIN courses c ON c.id=ce.course_id "
                       "WHERE ce.user_id=? ORDER BY ce.issued_at DESC", (user["id"],))


@app.get("/api/certificates/{code}")
def verify_certificate(code: str):
    """Public verification - anyone with the code can confirm a certificate is genuine."""
    row = db.one("SELECT ce.code, ce.issued_at, c.title course, c.colour, c.icon, u.display_name learner, i.display_name instructor "
                 "FROM certificates ce JOIN courses c ON c.id=ce.course_id JOIN users u ON u.id=ce.user_id LEFT JOIN users i ON i.id=c.instructor_id "
                 "WHERE ce.code=?", (code.upper(),))
    if not row:
        raise HTTPException(404, "No certificate with this code")
    row["minutes"] = db.one("SELECT COALESCE(SUM(l.duration_min),0) m FROM lessons l JOIN modules m ON m.id=l.module_id JOIN courses c ON c.id=m.course_id "
                            "WHERE c.title=?", (row["course"],))["m"]
    return row


# ------------------------------------------------------------------ learning

@app.get("/api/learn/{course_id}")
def learn(course_id: int, user=Depends(current_user)):
    _course_or_404(course_id, user)
    if user["role"] not in STAFF and not learning.is_enrolled(user["id"], course_id):
        raise HTTPException(403, "Enrol in the course first")
    tree = learning.course_tree(course_id, user["id"])
    cert = db.one("SELECT code FROM certificates WHERE user_id=? AND course_id=?", (user["id"], course_id))
    return {**tree, "progress": learning.progress_of(user["id"], course_id), "concepts": learning.concepts_of(user["id"], course_id),
            "certificate": cert["code"] if cert else None, "profile": learning.profile(user["id"])}


@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: int, user=Depends(current_user)):
    l = _lesson_for_learner(lesson_id, user)
    order = learning.lessons_of(l["course_id"])
    idx = next(i for i, x in enumerate(order) if x["id"] == lesson_id)
    attempt = db.one("SELECT score, passed, results_json, answers_json, created_at FROM quiz_attempts WHERE user_id=? AND lesson_id=? ORDER BY id DESC LIMIT 1",
                     (user["id"], lesson_id))
    if attempt:
        attempt["results"] = db.loads(attempt.pop("results_json"))
        attempt["answers"] = db.loads(attempt.pop("answers_json"))
    submission = db.one("SELECT * FROM submissions WHERE user_id=? AND lesson_id=? ORDER BY id DESC LIMIT 1", (user["id"], lesson_id))
    if submission:
        submission["auto_feedback"] = db.loads(submission.pop("auto_feedback_json"), [])
    posts = db.all_rows("SELECT d.id, d.parent_id, d.body, d.created_at, u.display_name, u.role FROM discussions d JOIN users u ON u.id=d.user_id "
                        "WHERE d.lesson_id=? AND d.hidden=0 ORDER BY d.created_at", (lesson_id,))
    note = db.one("SELECT body FROM notes WHERE user_id=? AND lesson_id=?", (user["id"], lesson_id))
    progress = db.one("SELECT status FROM lesson_progress WHERE user_id=? AND lesson_id=?", (user["id"], lesson_id))
    return {
        "id": l["id"], "course_id": l["course_id"], "module_title": l["module_title"], "title": l["title"], "kind": l["kind"],
        "content_md": l["content_md"], "video_url": l["video_url"], "duration_min": l["duration_min"],
        "concepts": [{"concept": c, "label": learning.concept_label(c)} for c in l["concepts"]],
        "quiz": learning.learner_quiz(l["quiz"]), "rubric": [{"criterion": r["criterion"]} for r in l["rubric"] or []],
        "status": progress["status"] if progress else "not_started",
        "last_attempt": attempt, "submission": submission, "discussion": posts, "note": note["body"] if note else "",
        "prev_id": order[idx - 1]["id"] if idx > 0 else None, "next_id": order[idx + 1]["id"] if idx + 1 < len(order) else None,
        "position": idx + 1, "total": len(order),
    }


@app.post("/api/lessons/{lesson_id}/complete")
def complete(lesson_id: int, user=Depends(current_user)):
    l = _lesson_for_learner(lesson_id, user)
    if l["kind"] not in ("article", "video"):
        raise HTTPException(400, "Quizzes and assignments are completed by submitting them")
    cert = learning.complete_lesson(user["id"], l)
    return {"progress": learning.progress_of(user["id"], l["course_id"]), "certificate": cert}


@app.post("/api/lessons/{lesson_id}/heartbeat")
def heartbeat(lesson_id: int, body: Heartbeat, user=Depends(current_user)):
    l = _lesson_for_learner(lesson_id, user)
    learning.track_time(user["id"], l["course_id"], lesson_id, body.seconds)
    return {"ok": True}


@app.post("/api/lessons/{lesson_id}/quiz")
def quiz(lesson_id: int, body: QuizIn, user=Depends(current_user)):
    l = _lesson_for_learner(lesson_id, user)
    if l["kind"] != "quiz":
        raise HTTPException(400, "This lesson is not a quiz")
    result = learning.submit_quiz(user["id"], l, body.answers)
    result["progress"] = learning.progress_of(user["id"], l["course_id"])
    return result


@app.post("/api/lessons/{lesson_id}/submit")
def submit(lesson_id: int, body: TextIn, user=Depends(current_user)):
    l = _lesson_for_learner(lesson_id, user)
    if l["kind"] != "assignment":
        raise HTTPException(400, "This lesson is not an assignment")
    feedback = learning.rubric_check(body.body, l["rubric"] or [])
    db.execute("INSERT INTO submissions (user_id, lesson_id, body, auto_feedback_json, created_at) VALUES (?,?,?,?,?)",
               (user["id"], lesson_id, body.body, db.dumps(feedback), db.now_iso()))
    cert = learning.complete_lesson(user["id"], l)
    return {"auto_feedback": feedback, "progress": learning.progress_of(user["id"], l["course_id"]), "certificate": cert}


@app.put("/api/lessons/{lesson_id}/note")
def save_note(lesson_id: int, body: TextIn, user=Depends(current_user)):
    _lesson_for_learner(lesson_id, user)
    db.execute("INSERT INTO notes (user_id, lesson_id, body, updated_at) VALUES (?,?,?,?) "
               "ON CONFLICT(user_id, lesson_id) DO UPDATE SET body=excluded.body, updated_at=excluded.updated_at",
               (user["id"], lesson_id, body.body, db.now_iso()))
    return {"ok": True}


@app.post("/api/lessons/{lesson_id}/discussion")
def post_discussion(lesson_id: int, body: PostIn, user=Depends(current_user)):
    from . import safety
    l = _lesson_for_learner(lesson_id, user)
    concern = safety.screen(body.body)
    if concern and concern["category"] != "personal_data":
        db.execute("INSERT INTO moderation_flags (user_id, source, category, excerpt, created_at) VALUES (?,?,?,?,?)",
                   (user["id"], f"discussion:lesson:{lesson_id}", concern["category"], body.body[:200], db.now_iso()))
        raise HTTPException(400, concern["reply"])
    if concern:
        raise HTTPException(400, concern["reply"])
    db.execute("INSERT INTO discussions (course_id, lesson_id, user_id, parent_id, body, created_at) VALUES (?,?,?,?,?,?)",
               (l["course_id"], lesson_id, user["id"], body.parent_id, body.body.strip(), db.now_iso()))
    return {"ok": True}


# ------------------------------------------------------------------ AI tutor

@app.get("/api/tutor/{course_id}")
def tutor_history(course_id: int, lesson_id: int | None = None, user=Depends(current_user)):
    _course_or_404(course_id, user)
    msgs = tutor.history(user["id"], course_id)
    return {"messages": msgs, "greeting": tutor.greeting(user, course_id, lesson_id), "llm": llm.status(),
            "weak": learning.weak_concepts(user["id"], course_id)[:3]}


@app.post("/api/tutor/{course_id}/message")
def tutor_message(course_id: int, body: TutorIn, user=Depends(current_user)):
    _course_or_404(course_id, user)
    if user["role"] not in STAFF and not learning.is_enrolled(user["id"], course_id):
        raise HTTPException(403, "Enrol in the course to use its tutor")
    if body.action not in (None, "quiz_me", "explain_simple", "example"):
        raise HTTPException(400, "Unknown action")

    def events():
        for ev in tutor.respond(user, course_id, body.lesson_id, body.text or "", body.action):
            yield json.dumps(ev) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")


# ------------------------------------------------------------------ content studio (instructor / admin)

@app.get("/api/studio/courses")
def studio_courses(user=Depends(current_user)):
    require_role(user, *STAFF)
    out = []
    for c in db.all_rows("SELECT * FROM courses WHERE status != 'archived' ORDER BY updated_at DESC"):
        c["outcomes"] = db.loads(c.pop("outcomes_json"), [])
        card = learning.course_card(c)
        done = db.one("SELECT COUNT(*) n FROM enrollments WHERE course_id=? AND completed_at IS NOT NULL", (c["id"],))["n"]
        card.update(completion_rate=round(done / card["learners"], 2) if card["learners"] else 0, updated_at=c["updated_at"],
                    pending=db.one("SELECT COUNT(*) n FROM submissions s JOIN lessons l ON l.id=s.lesson_id JOIN modules m ON m.id=l.module_id "
                                   "WHERE m.course_id=? AND s.status='submitted'", (c["id"],))["n"])
        out.append(card)
    return out


@app.post("/api/studio/courses")
def studio_create(body: TitleIn, user=Depends(current_user)):
    require_role(user, *STAFF)
    now = db.now_iso()
    cid = db.execute("INSERT INTO courses (slug, title, subtitle, description, category, instructor_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                     (_slugify(body.title), body.title, "", "", CATEGORIES[0], user["id"], now, now))
    db.execute("INSERT INTO modules (course_id, title, position) VALUES (?,?,1)", (cid, "Module 1"))
    db.audit(user["id"], "course_created", f"course:{cid}")
    return {"id": cid}


@app.get("/api/studio/courses/{course_id}")
def studio_course(course_id: int, user=Depends(current_user)):
    require_role(user, *STAFF)
    c = learning.course(course_id)
    if not c:
        raise HTTPException(404, "Course not found")
    modules = db.all_rows("SELECT * FROM modules WHERE course_id=? ORDER BY position", (course_id,))
    by_module = {}
    for l in learning.lessons_of(course_id):
        by_module.setdefault(l["module_id"], []).append(l)
    for m in modules:
        m["lessons"] = by_module.get(m["id"], [])
    return {**c, "modules": modules, "categories": CATEGORIES}


@app.put("/api/studio/courses/{course_id}")
def studio_update(course_id: int, body: CourseIn, user=Depends(current_user)):
    require_role(user, *STAFF)
    c = learning.course(course_id)
    if not c:
        raise HTTPException(404, "Course not found")
    data = body.model_dump(exclude_none=True)
    if "status" in data and data["status"] not in ("draft", "published", "archived"):
        raise HTTPException(400, "Unknown status")
    if data.get("status") == "published" and not learning.lessons_of(course_id):
        raise HTTPException(400, "Add at least one lesson before publishing")
    if "outcomes" in data:
        data["outcomes_json"] = db.dumps(data.pop("outcomes"))
    for k, v in data.items():
        db.execute(f"UPDATE courses SET {k}=? WHERE id=?", (v, course_id))
    db.execute("UPDATE courses SET version=version+1, updated_at=? WHERE id=?", (db.now_iso(), course_id))
    db.audit(user["id"], "course_updated" if "status" not in data else f"course_{data['status']}", f"course:{course_id}")
    return learning.course(course_id)


@app.post("/api/studio/courses/{course_id}/modules")
def studio_add_module(course_id: int, body: TitleIn, user=Depends(current_user)):
    require_role(user, *STAFF)
    pos = db.one("SELECT COALESCE(MAX(position),0)+1 p FROM modules WHERE course_id=?", (course_id,))["p"]
    mid = db.execute("INSERT INTO modules (course_id, title, position) VALUES (?,?,?)", (course_id, body.title, pos))
    _touch_course(course_id)
    return {"id": mid}


@app.put("/api/studio/modules/{module_id}")
def studio_rename_module(module_id: int, body: TitleIn, user=Depends(current_user)):
    require_role(user, *STAFF)
    m = db.one("SELECT * FROM modules WHERE id=?", (module_id,))
    db.execute("UPDATE modules SET title=? WHERE id=?", (body.title, module_id))
    _touch_course(m["course_id"])
    return {"ok": True}


@app.delete("/api/studio/modules/{module_id}")
def studio_delete_module(module_id: int, user=Depends(current_user)):
    require_role(user, *STAFF)
    m = db.one("SELECT * FROM modules WHERE id=?", (module_id,))
    if not m:
        raise HTTPException(404, "Module not found")
    db.execute("DELETE FROM modules WHERE id=?", (module_id,))
    _touch_course(m["course_id"])
    db.audit(user["id"], "module_deleted", f"module:{module_id}")
    return {"ok": True}


@app.post("/api/studio/modules/{module_id}/lessons")
def studio_add_lesson(module_id: int, body: LessonNew, user=Depends(current_user)):
    require_role(user, *STAFF)
    if body.kind not in ("article", "video", "quiz", "assignment"):
        raise HTTPException(400, "Unknown lesson type")
    m = db.one("SELECT * FROM modules WHERE id=?", (module_id,))
    pos = db.one("SELECT COALESCE(MAX(position),0)+1 p FROM lessons WHERE module_id=?", (module_id,))["p"]
    quiz = db.dumps([]) if body.kind == "quiz" else None
    rubric = db.dumps([]) if body.kind == "assignment" else None
    lid = db.execute("INSERT INTO lessons (module_id, title, kind, quiz_json, rubric_json, position) VALUES (?,?,?,?,?,?)",
                     (module_id, body.title, body.kind, quiz, rubric, pos))
    _touch_course(m["course_id"])
    return {"id": lid}


@app.put("/api/studio/lessons/{lesson_id}")
def studio_update_lesson(lesson_id: int, body: LessonIn, user=Depends(current_user)):
    require_role(user, *STAFF)
    l = learning.lesson(lesson_id)
    if not l:
        raise HTTPException(404, "Lesson not found")
    data = body.model_dump(exclude_none=True)
    if "quiz" in data:
        for q in data["quiz"]:
            if q.get("type") == "choice" and not (0 <= int(q.get("answer", -1)) < len(q.get("options") or [])):
                raise HTTPException(400, f"Question '{q.get('q', '')[:40]}' needs a correct option selected")
            if q.get("type") == "short" and not q.get("accept"):
                raise HTTPException(400, f"Question '{q.get('q', '')[:40]}' needs at least one accepted answer")
        data["quiz_json"] = db.dumps(data.pop("quiz"))
    if "rubric" in data:
        data["rubric_json"] = db.dumps(data.pop("rubric"))
    if "concepts" in data:
        data["concepts_json"] = db.dumps([re.sub(r"[^a-z0-9-]", "", c.lower().replace(" ", "-")) for c in data.pop("concepts") if c.strip()])
    for k, v in data.items():
        db.execute(f"UPDATE lessons SET {k}=? WHERE id=?", (v, lesson_id))
    _touch_course(l["course_id"])
    return learning.lesson(lesson_id)


@app.delete("/api/studio/lessons/{lesson_id}")
def studio_delete_lesson(lesson_id: int, user=Depends(current_user)):
    require_role(user, *STAFF)
    l = learning.lesson(lesson_id)
    if not l:
        raise HTTPException(404, "Lesson not found")
    db.execute("DELETE FROM lessons WHERE id=?", (lesson_id,))
    _touch_course(l["course_id"])
    db.audit(user["id"], "lesson_deleted", f"lesson:{lesson_id}")
    return {"ok": True}


@app.post("/api/studio/move")
def studio_move(body: MoveIn, user=Depends(current_user)):
    require_role(user, *STAFF)
    table, parent = {"module": ("modules", "course_id"), "lesson": ("lessons", "module_id")}[body.type]
    item = db.one(f"SELECT * FROM {table} WHERE id=?", (body.id,))
    op, order = ("<", "DESC") if body.direction == "up" else (">", "ASC")
    other = db.one(f"SELECT * FROM {table} WHERE {parent}=? AND position {op} ? ORDER BY position {order} LIMIT 1",
                   (item[parent], item["position"]))
    if other:
        db.execute(f"UPDATE {table} SET position=? WHERE id=?", (other["position"], item["id"]))
        db.execute(f"UPDATE {table} SET position=? WHERE id=?", (item["position"], other["id"]))
    cid = item["course_id"] if table == "modules" else db.one("SELECT course_id FROM modules WHERE id=?", (item["module_id"],))["course_id"]
    _touch_course(cid)
    return {"ok": True}


@app.get("/api/studio/courses/{course_id}/analytics")
def studio_analytics(course_id: int, user=Depends(current_user)):
    require_role(user, *STAFF)
    c = learning.course(course_id)
    lessons = learning.lessons_of(course_id)
    learners = db.all_rows("SELECT e.*, u.display_name FROM enrollments e JOIN users u ON u.id=e.user_id WHERE e.course_id=?", (course_id,))
    funnel = []
    for l in lessons:
        n = db.one("SELECT COUNT(*) n FROM lesson_progress WHERE lesson_id=? AND status='completed'", (l["id"],))["n"]
        t = db.one("SELECT COALESCE(AVG(seconds_spent),0) s FROM lesson_progress WHERE lesson_id=?", (l["id"],))["s"]
        funnel.append({"lesson_id": l["id"], "title": l["title"], "kind": l["kind"], "completed": n, "avg_minutes": round(t / 60, 1)})
    questions = []
    for l in [x for x in lessons if x["kind"] == "quiz"]:
        attempts = db.all_rows("SELECT results_json FROM quiz_attempts WHERE lesson_id=?", (l["id"],))
        for i, q in enumerate(l["quiz"] or []):
            marks = [db.loads(a["results_json"])[i]["correct"] for a in attempts if len(db.loads(a["results_json"])) > i]
            if marks:
                questions.append({"lesson": l["title"], "q": q["q"], "concept": learning.concept_label(q["concept"]),
                                  "attempts": len(marks), "correct_rate": round(sum(marks) / len(marks), 2)})
    questions.sort(key=lambda q: q["correct_rate"])
    concepts = db.all_rows("SELECT concept, AVG(p_mastery) p, COUNT(*) learners FROM concept_mastery WHERE course_id=? GROUP BY concept ORDER BY p",
                           (course_id,))
    for cp in concepts:
        cp["label"], cp["p"] = learning.concept_label(cp["concept"]), round(cp["p"], 2)
    asked = db.all_rows("SELECT tm.text, tm.created_at FROM tutor_messages tm JOIN tutor_conversations tc ON tc.id=tm.conversation_id "
                        "WHERE tc.course_id=? AND tm.role='learner' AND tm.meta_json LIKE '%\"kind\": \"question\"%' "
                        "ORDER BY tm.created_at DESC LIMIT 15", (course_id,))
    unanswered = db.all_rows("SELECT d.id, d.body, d.created_at, d.lesson_id, l.title lesson, u.display_name FROM discussions d JOIN lessons l ON l.id=d.lesson_id "
                             "JOIN users u ON u.id=d.user_id WHERE d.course_id=? AND d.parent_id IS NULL AND d.hidden=0 AND NOT EXISTS "
                             "(SELECT 1 FROM discussions r JOIN users ru ON ru.id=r.user_id WHERE r.parent_id=d.id AND ru.role IN ('instructor','admin')) "
                             "ORDER BY d.created_at DESC", (course_id,))
    rating = db.one("SELECT AVG(rating) avg, COUNT(*) n FROM reviews WHERE course_id=?", (course_id,))
    progress = [learning.progress_of(e["user_id"], course_id)["percent"] for e in learners]
    return {
        "course": {"id": c["id"], "title": c["title"], "status": c["status"]},
        "learners": len(learners), "completed": sum(1 for e in learners if e["completed_at"]),
        "avg_progress": round(sum(progress) / len(progress)) if progress else 0,
        "active_7d": sum(1 for e in learners if (e["last_active_at"] or "") >= _days_ago_iso(7)),
        "rating": round(rating["avg"], 1) if rating["avg"] else None, "reviews": rating["n"],
        "funnel": funnel, "hardest_questions": questions[:6], "concepts": concepts, "tutor_questions": asked, "unanswered": unanswered,
        "roster": sorted([{"user_id": e["user_id"], "name": e["display_name"], "percent": learning.progress_of(e["user_id"], course_id)["percent"],
                           "last_active": e["last_active_at"], "completed": bool(e["completed_at"]),
                           "weak": [w["label"] for w in learning.weak_concepts(e["user_id"], course_id)[:2]]} for e in learners],
                         key=lambda r: r["percent"]),
    }


def _days_ago_iso(days: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


@app.get("/api/studio/submissions")
def studio_submissions(status: str = "submitted", user=Depends(current_user)):
    require_role(user, *STAFF)
    rows = db.all_rows("SELECT s.*, u.display_name learner, l.title lesson, c.title course, l.rubric_json FROM submissions s "
                       "JOIN users u ON u.id=s.user_id JOIN lessons l ON l.id=s.lesson_id JOIN modules m ON m.id=l.module_id "
                       "JOIN courses c ON c.id=m.course_id WHERE s.status=? ORDER BY s.created_at", (status,))
    for r in rows:
        r["auto_feedback"] = db.loads(r.pop("auto_feedback_json"), [])
        r.pop("rubric_json")
    return rows


@app.put("/api/studio/submissions/{submission_id}")
def studio_grade(submission_id: int, body: GradeIn, user=Depends(current_user)):
    require_role(user, *STAFF)
    db.execute("UPDATE submissions SET grade=?, instructor_feedback=?, status='graded', graded_at=? WHERE id=?",
               (body.grade, body.feedback, db.now_iso(), submission_id))
    db.audit(user["id"], "submission_graded", f"submission:{submission_id}")
    return {"ok": True}


@app.put("/api/studio/discussions/{post_id}/hide")
def studio_hide_post(post_id: int, user=Depends(current_user)):
    require_role(user, *STAFF)
    db.execute("UPDATE discussions SET hidden=1 WHERE id=?", (post_id,))
    db.audit(user["id"], "discussion_hidden", f"post:{post_id}")
    return {"ok": True}


@app.get("/api/users/{user_id}/record")
def learner_record(user_id: int, user=Depends(current_user)):
    ensure_self_or_staff(user, user_id)
    u = db.one("SELECT id, display_name, email, created_at FROM users WHERE id=?", (user_id,))
    courses = []
    for e in db.all_rows("SELECT * FROM enrollments WHERE user_id=?", (user_id,)):
        c = learning.course(e["course_id"])
        courses.append({"title": c["title"], "progress": learning.progress_of(user_id, c["id"]),
                        "concepts": learning.concepts_of(user_id, c["id"])})
    return {"user": u, "profile": learning.profile(user_id), "courses": courses, "streak": learning.streak(user_id)}


# ------------------------------------------------------------------ admin

@app.get("/api/admin/overview")
def admin_overview(user=Depends(current_user)):
    require_role(user, "admin")
    count = lambda sql, args=(): db.one(sql, args)["n"]
    users = db.all_rows("SELECT id, role, email, display_name, active, created_at FROM users ORDER BY role, display_name")
    daily = db.all_rows("SELECT day, COUNT(DISTINCT user_id) learners, SUM(seconds)/60 minutes FROM activity WHERE day >= date('now','-20 day') GROUP BY day ORDER BY day")
    top = db.all_rows("SELECT c.id, c.title, c.icon, COUNT(e.user_id) learners, SUM(CASE WHEN e.completed_at IS NOT NULL THEN 1 ELSE 0 END) completed "
                      "FROM courses c LEFT JOIN enrollments e ON e.course_id=c.id WHERE c.status='published' GROUP BY c.id ORDER BY learners DESC")
    ai = db.all_rows("SELECT provider, model, COUNT(*) calls, SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens, SUM(cost_usd) cost_usd, "
                     "AVG(latency_ms) avg_latency_ms, COUNT(DISTINCT user_id) learners FROM llm_usage GROUP BY provider, model")
    tutor_turns = count("SELECT COUNT(*) n FROM tutor_messages WHERE role='learner'")
    flags = db.all_rows("SELECT f.*, u.display_name, u.email FROM moderation_flags f JOIN users u ON u.id=f.user_id ORDER BY f.created_at DESC")
    audit = db.all_rows("SELECT a.*, u.display_name, u.role FROM audit_log a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 50")
    db.audit(user["id"], "viewed_admin_overview")
    return {
        "stats": {"learners": count("SELECT COUNT(*) n FROM users WHERE role='learner'"),
                  "active_7d": count("SELECT COUNT(DISTINCT user_id) n FROM activity WHERE day >= date('now','-7 day')"),
                  "enrolments": count("SELECT COUNT(*) n FROM enrollments"),
                  "completions": count("SELECT COUNT(*) n FROM enrollments WHERE completed_at IS NOT NULL"),
                  "certificates": count("SELECT COUNT(*) n FROM certificates"),
                  "minutes_30d": round(count("SELECT COALESCE(SUM(seconds),0) n FROM activity WHERE day >= date('now','-30 day')") / 60),
                  "courses": count("SELECT COUNT(*) n FROM courses WHERE status='published'"), "tutor_questions": tutor_turns},
        "daily": daily, "top_courses": top, "ai_usage": ai, "llm": llm.status(), "flags": flags, "audit": audit, "users": users,
    }


@app.put("/api/admin/users/{user_id}")
def admin_user(user_id: int, body: UserAdmin, user=Depends(current_user)):
    require_role(user, "admin")
    if user_id == user["id"]:
        raise HTTPException(400, "You can't change your own role or status")
    if body.role is not None:
        if body.role not in ("learner", "instructor", "admin"):
            raise HTTPException(400, "Unknown role")
        db.execute("UPDATE users SET role=? WHERE id=?", (body.role, user_id))
        db.audit(user["id"], f"role_changed_to_{body.role}", f"user:{user_id}")
    if body.active is not None:
        db.execute("UPDATE users SET active=? WHERE id=?", (int(body.active), user_id))
        db.audit(user["id"], "user_activated" if body.active else "user_deactivated", f"user:{user_id}")
    return {"ok": True}


@app.put("/api/admin/flags/{flag_id}")
def admin_flag(flag_id: int, body: StatusIn, user=Depends(current_user)):
    require_role(user, "admin")
    if body.status not in ("open", "reviewing", "resolved"):
        raise HTTPException(400, "Unknown status")
    db.execute("UPDATE moderation_flags SET status=? WHERE id=?", (body.status, flag_id))
    db.audit(user["id"], f"flag_{body.status}", f"flag:{flag_id}")
    return {"ok": True}


@app.get("/api/users/{user_id}/export")
def export_user(user_id: int, user=Depends(current_user)):
    """Data export (UK GDPR right of access / portability)."""
    ensure_self_or_staff(user, user_id)
    db.audit(user["id"], "exported_user_data", f"user:{user_id}")
    tables = {
        "enrolments": "SELECT * FROM enrollments WHERE user_id=?", "lesson_progress": "SELECT * FROM lesson_progress WHERE user_id=?",
        "quiz_attempts": "SELECT * FROM quiz_attempts WHERE user_id=?", "submissions": "SELECT * FROM submissions WHERE user_id=?",
        "concept_mastery": "SELECT * FROM concept_mastery WHERE user_id=?", "notes": "SELECT * FROM notes WHERE user_id=?",
        "reviews": "SELECT * FROM reviews WHERE user_id=?", "certificates": "SELECT * FROM certificates WHERE user_id=?",
        "tutor_messages": "SELECT tm.* FROM tutor_messages tm JOIN tutor_conversations tc ON tc.id=tm.conversation_id WHERE tc.user_id=?",
        "activity": "SELECT * FROM activity WHERE user_id=?",
    }
    data = {name: db.all_rows(sql, (user_id,)) for name, sql in tables.items()}
    data["user"] = db.one("SELECT id, email, display_name, role, created_at FROM users WHERE id=?", (user_id,))
    data["profile"] = learning.profile(user_id)
    data["exported_at"] = db.now_iso()
    return data


@app.delete("/api/admin/users/{user_id}/data")
def erase_user_data(user_id: int, user=Depends(current_user)):
    """Right to erasure: removes learning data but keeps the account shell."""
    require_role(user, "admin")
    for table in ("enrollments", "lesson_progress", "quiz_attempts", "submissions", "concept_mastery", "notes", "reviews",
                  "certificates", "tutor_conversations", "activity", "discussions"):
        db.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
    db.audit(user["id"], "erased_user_data", f"user:{user_id}")
    return {"deleted": True}


# ------------------------------------------------------------------ frontend

DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        target = os.path.join(DIST, path)
        if path and os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(os.path.join(DIST, "index.html"))
