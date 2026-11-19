"""Core LMS logic: course structure, enrolment, progress, quiz marking,
per-concept mastery (Bayesian Knowledge Tracing), spaced review,
certificates and personalised recommendations."""
import re
import secrets
from datetime import date, timedelta

from . import db

PASS_MARK = 0.7
# Bayesian Knowledge Tracing parameters
P_INIT, P_TRANSIT, P_SLIP, P_GUESS = 0.2, 0.1, 0.1, 0.25
ACRONYMS = {"ctr": "CTR", "cac": "CAC", "roi": "ROI", "seo": "SEO", "ux-vs-ui": "UX vs UI", "if-function": "IF function"}


def concept_label(concept: str) -> str:
    return ACRONYMS.get(concept, concept.replace("-", " ").capitalize())


# ------------------------------------------------------------------ structure

def course(course_id: int) -> dict | None:
    c = db.one("SELECT * FROM courses WHERE id=?", (course_id,))
    if c:
        c["outcomes"] = db.loads(c.pop("outcomes_json"), [])
    return c


def course_by_slug(slug: str) -> dict | None:
    row = db.one("SELECT id FROM courses WHERE slug=?", (slug,))
    return course(row["id"]) if row else None


def lessons_of(course_id: int) -> list[dict]:
    """All lessons in course order, with module info."""
    rows = db.all_rows(
        "SELECT l.*, m.title module_title, m.position module_position FROM lessons l JOIN modules m ON m.id=l.module_id "
        "WHERE m.course_id=? ORDER BY m.position, l.position", (course_id,))
    for r in rows:
        r["concepts"] = db.loads(r.pop("concepts_json"), [])
        r["quiz"] = db.loads(r.pop("quiz_json"), None)
        r["rubric"] = db.loads(r.pop("rubric_json"), None)
    return rows


def lesson(lesson_id: int) -> dict | None:
    row = db.one("SELECT l.*, m.course_id, m.title module_title FROM lessons l JOIN modules m ON m.id=l.module_id WHERE l.id=?", (lesson_id,))
    if row:
        row["concepts"] = db.loads(row.pop("concepts_json"), [])
        row["quiz"] = db.loads(row.pop("quiz_json"), None)
        row["rubric"] = db.loads(row.pop("rubric_json"), None)
    return row


def learner_quiz(quiz: list[dict] | None) -> list[dict] | None:
    """Quiz questions without answers or explanations, for the learner."""
    if not quiz:
        return quiz
    return [{"q": q["q"], "type": q["type"], "options": q.get("options"), "concept": q["concept"]} for q in quiz]


def course_tree(course_id: int, user_id: int | None = None) -> dict:
    c = course(course_id)
    progress = {}
    if user_id:
        progress = {r["lesson_id"]: r for r in db.all_rows(
            "SELECT lp.* FROM lesson_progress lp JOIN lessons l ON l.id=lp.lesson_id JOIN modules m ON m.id=l.module_id "
            "WHERE lp.user_id=? AND m.course_id=?", (user_id, course_id))}
    modules = []
    for m in db.all_rows("SELECT * FROM modules WHERE course_id=? ORDER BY position", (course_id,)):
        items = []
        for l in db.all_rows("SELECT id, title, kind, duration_min, position FROM lessons WHERE module_id=? ORDER BY position", (m["id"],)):
            p = progress.get(l["id"])
            items.append({**l, "status": p["status"] if p else "not_started", "best_score": p["best_score"] if p else None})
        modules.append({**m, "lessons": items})
    c["modules"] = modules
    c["lesson_count"] = sum(len(m["lessons"]) for m in modules)
    c["duration_min"] = sum(l["duration_min"] for m in modules for l in m["lessons"])
    return c


def course_card(c: dict, user_id: int | None = None) -> dict:
    stats = db.one("SELECT COUNT(*) n FROM enrollments WHERE course_id=?", (c["id"],))
    rating = db.one("SELECT AVG(rating) avg, COUNT(*) n FROM reviews WHERE course_id=?", (c["id"],))
    size = db.one("SELECT COUNT(*) lessons, COALESCE(SUM(l.duration_min),0) minutes FROM lessons l JOIN modules m ON m.id=l.module_id WHERE m.course_id=?",
                  (c["id"],))
    instructor = db.one("SELECT display_name, headline FROM users WHERE id=?", (c["instructor_id"],))
    card = {k: c[k] for k in ("id", "slug", "title", "subtitle", "category", "level", "colour", "icon", "status")}
    card.update(learners=stats["n"], rating=round(rating["avg"], 1) if rating["avg"] else None, reviews=rating["n"],
                lessons=size["lessons"], minutes=size["minutes"], instructor=instructor)
    if user_id:
        card["enrolled"] = bool(db.one("SELECT 1 FROM enrollments WHERE user_id=? AND course_id=?", (user_id, c["id"])))
        if card["enrolled"]:
            card["progress"] = progress_of(user_id, c["id"])
    return card


# ------------------------------------------------------------------ enrolment & progress

def is_enrolled(user_id: int, course_id: int) -> bool:
    return bool(db.one("SELECT 1 FROM enrollments WHERE user_id=? AND course_id=?", (user_id, course_id)))


def enrol(user_id: int, course_id: int) -> None:
    db.execute("INSERT OR IGNORE INTO enrollments (user_id, course_id, enrolled_at, last_active_at) VALUES (?,?,?,?)",
               (user_id, course_id, db.now_iso(), db.now_iso()))


def progress_of(user_id: int, course_id: int) -> dict:
    all_lessons = lessons_of(course_id)
    done = {r["lesson_id"] for r in db.all_rows(
        "SELECT lesson_id FROM lesson_progress WHERE user_id=? AND status='completed'", (user_id,))}
    completed = [l for l in all_lessons if l["id"] in done]
    enr = db.one("SELECT * FROM enrollments WHERE user_id=? AND course_id=?", (user_id, course_id)) or {}
    nxt = next((l for l in all_lessons if l["id"] not in done), None)
    return {"completed": len(completed), "total": len(all_lessons),
            "percent": round(100 * len(completed) / len(all_lessons)) if all_lessons else 0,
            "next_lesson_id": nxt["id"] if nxt else None, "next_lesson_title": nxt["title"] if nxt else None,
            "last_lesson_id": enr.get("last_lesson_id"), "completed_at": enr.get("completed_at")}


def track_time(user_id: int, course_id: int, lesson_id: int, seconds: int) -> None:
    seconds = max(0, min(seconds, 300))  # heartbeat cap: idle tabs don't inflate study time
    now = db.now_iso()
    db.execute("INSERT INTO lesson_progress (user_id, lesson_id, status, seconds_spent, updated_at) VALUES (?,?,?,?,?) "
               "ON CONFLICT(user_id, lesson_id) DO UPDATE SET seconds_spent=seconds_spent+excluded.seconds_spent, updated_at=excluded.updated_at",
               (user_id, lesson_id, "started", seconds, now))
    db.execute("INSERT INTO activity (user_id, day, seconds) VALUES (?,?,?) ON CONFLICT(user_id, day) DO UPDATE SET seconds=seconds+excluded.seconds",
               (user_id, db.today(), seconds))
    db.execute("UPDATE enrollments SET last_lesson_id=?, last_active_at=? WHERE user_id=? AND course_id=?", (lesson_id, now, user_id, course_id))


def complete_lesson(user_id: int, l: dict, score: float | None = None) -> dict | None:
    """Mark a lesson complete; returns a new certificate if the course is now finished."""
    now = db.now_iso()
    db.execute("INSERT INTO lesson_progress (user_id, lesson_id, status, best_score, completed_at, updated_at) VALUES (?,?,?,?,?,?) "
               "ON CONFLICT(user_id, lesson_id) DO UPDATE SET status='completed', completed_at=COALESCE(completed_at, excluded.completed_at), "
               "best_score=MAX(COALESCE(best_score,0), COALESCE(excluded.best_score,0)), updated_at=excluded.updated_at",
               (user_id, l["id"], "completed", score, now, now))
    return maybe_certify(user_id, l["course_id"])


def maybe_certify(user_id: int, course_id: int) -> dict | None:
    p = progress_of(user_id, course_id)
    if p["total"] and p["completed"] == p["total"]:
        if db.one("SELECT 1 FROM certificates WHERE user_id=? AND course_id=?", (user_id, course_id)):
            return None
        code = "NOVA-" + secrets.token_hex(4).upper()
        db.execute("INSERT INTO certificates (code, user_id, course_id, issued_at) VALUES (?,?,?,?)", (code, user_id, course_id, db.now_iso()))
        db.execute("UPDATE enrollments SET completed_at=? WHERE user_id=? AND course_id=?", (db.now_iso(), user_id, course_id))
        db.audit(user_id, "certificate_issued", code)
        return {"code": code, "course_id": course_id}
    return None


# ------------------------------------------------------------------ marking

def _norm(text: str) -> str:
    return re.sub(r"[£$€%,\s'\"`]", "", text.strip().lower())


def mark_question(q: dict, answer) -> bool:
    if q["type"] == "choice":
        try:
            return int(answer) == q["answer"]
        except (TypeError, ValueError):
            letter = str(answer).strip().upper()[:1]
            return len(str(answer).strip()) == 1 and "ABCDEFG".find(letter) == q["answer"]
    given = _norm(str(answer or ""))
    if not given:
        return False
    for acc in q["accept"]:
        if given == _norm(acc):
            return True
        try:
            if abs(float(given) - float(_norm(acc))) <= (q.get("tolerance") or 0):
                return True
        except ValueError:
            pass
    return False


def submit_quiz(user_id: int, l: dict, answers: list) -> dict:
    results = []
    for i, q in enumerate(l["quiz"]):
        given = answers[i] if i < len(answers) else None
        ok = mark_question(q, given)
        results.append({"correct": ok, "explain": q["explain"], "concept": q["concept"],
                        "answer": q["options"][q["answer"]] if q["type"] == "choice" else q["accept"][0]})
        record_concept(user_id, l["course_id"], q["concept"], ok)
    score = sum(r["correct"] for r in results) / len(results)
    passed = score >= PASS_MARK
    db.execute("INSERT INTO quiz_attempts (user_id, lesson_id, answers_json, results_json, score, passed, created_at) VALUES (?,?,?,?,?,?,?)",
               (user_id, l["id"], db.dumps(answers), db.dumps(results), score, int(passed), db.now_iso()))
    certificate = complete_lesson(user_id, l, score) if passed else None
    if not passed:
        db.execute("INSERT INTO lesson_progress (user_id, lesson_id, status, best_score, updated_at) VALUES (?,?,?,?,?) "
                   "ON CONFLICT(user_id, lesson_id) DO UPDATE SET best_score=MAX(COALESCE(best_score,0), excluded.best_score), updated_at=excluded.updated_at",
                   (user_id, l["id"], "started", score, db.now_iso()))
    weak = [w for w in weak_concepts(user_id, l["course_id"]) if w["concept"] in l["concepts"]]
    return {"score": score, "passed": passed, "pass_mark": PASS_MARK, "results": results, "certificate": certificate, "revisit": weak}


def rubric_check(body: str, rubric: list[dict]) -> list[dict]:
    """Automated first-pass feedback against the assignment rubric; an instructor grades."""
    text = body.lower()
    return [{"criterion": r["criterion"], "met": any(k.lower() in text for k in r["keywords"]), "tip": r["tip"]} for r in rubric]


# ------------------------------------------------------------------ concept mastery

def record_concept(user_id: int, course_id: int, concept: str, correct: bool) -> float:
    row = db.one("SELECT * FROM concept_mastery WHERE user_id=? AND course_id=? AND concept=?", (user_id, course_id, concept))
    p = row["p_mastery"] if row else P_INIT
    if correct:
        post = p * (1 - P_SLIP) / (p * (1 - P_SLIP) + (1 - p) * P_GUESS)
    else:
        post = p * P_SLIP / (p * P_SLIP + (1 - p) * (1 - P_SLIP))
    p_new = min(0.95, max(0.02, post + (1 - post) * P_TRANSIT))
    interval = row["interval_days"] if row else 0
    interval = (1 if interval == 0 else min(60, round(interval * 2.3))) if correct else 1
    nxt = (date.today() + timedelta(days=interval)).isoformat()
    db.execute(
        "INSERT INTO concept_mastery (user_id, course_id, concept, p_mastery, evidence, correct, next_review, interval_days, updated_at) "
        "VALUES (?,?,?,?,1,?,?,?,?) ON CONFLICT(user_id, course_id, concept) DO UPDATE SET p_mastery=excluded.p_mastery, "
        "evidence=evidence+1, correct=correct+excluded.correct, next_review=excluded.next_review, interval_days=excluded.interval_days, updated_at=excluded.updated_at",
        (user_id, course_id, concept, p_new, int(correct), nxt, interval, db.now_iso()))
    return p_new


def mastery_status(p: float, evidence: int) -> str:
    if evidence == 0:
        return "Not started"
    if p >= 0.8 and evidence >= 2:
        return "Strong"
    return "Developing" if p >= 0.5 else "Needs work"


def concepts_of(user_id: int, course_id: int) -> list[dict]:
    taught: dict[str, dict] = {}
    for l in lessons_of(course_id):
        for c in l["concepts"]:
            if c not in taught and l["kind"] in ("article", "video"):
                taught[c] = {"lesson_id": l["id"], "lesson_title": l["title"]}
            taught.setdefault(c, {"lesson_id": l["id"], "lesson_title": l["title"]})
    rows = {r["concept"]: r for r in db.all_rows("SELECT * FROM concept_mastery WHERE user_id=? AND course_id=?", (user_id, course_id))}
    out = []
    for c, where in taught.items():
        r = rows.get(c)
        p, ev = (r["p_mastery"], r["evidence"]) if r else (0.0, 0)
        out.append({"concept": c, "label": concept_label(c), "p": round(p, 2), "evidence": ev, "status": mastery_status(p, ev),
                    "next_review": r["next_review"] if r else None, **where})
    return out


def weak_concepts(user_id: int, course_id: int) -> list[dict]:
    """Concepts with evidence of difficulty: a low estimate, or a wrong answer not yet outweighed."""
    rows = {r["concept"]: r for r in db.all_rows("SELECT concept, evidence, correct FROM concept_mastery WHERE user_id=? AND course_id=?",
                                                 (user_id, course_id))}
    weak = [c for c in concepts_of(user_id, course_id) if c["evidence"] and
            (c["p"] < 0.5 or (rows[c["concept"]]["correct"] < rows[c["concept"]]["evidence"] and c["p"] < 0.6))]
    return sorted(weak, key=lambda c: c["p"])


def reviews_due(user_id: int) -> list[dict]:
    rows = db.all_rows("SELECT cm.*, c.title course_title FROM concept_mastery cm JOIN courses c ON c.id=cm.course_id "
                       "WHERE cm.user_id=? AND cm.next_review <= ? ORDER BY cm.p_mastery", (user_id, db.today()))
    return [{"course_id": r["course_id"], "course_title": r["course_title"], "concept": r["concept"],
             "label": concept_label(r["concept"]), "p": round(r["p_mastery"], 2)} for r in rows]


# ------------------------------------------------------------------ personalisation

def profile(user_id: int) -> dict:
    p = db.one("SELECT * FROM learner_profiles WHERE user_id=?", (user_id,))
    if not p:
        db.execute("INSERT INTO learner_profiles (user_id) VALUES (?)", (user_id,))
        p = db.one("SELECT * FROM learner_profiles WHERE user_id=?", (user_id,))
    p["interests"] = db.loads(p.pop("interests_json"), [])
    return p


def streak(user_id: int) -> int:
    days = {r["day"] for r in db.all_rows("SELECT day FROM activity WHERE user_id=? AND seconds > 0", (user_id,))}
    d = date.today()
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    count = 0
    while d.isoformat() in days:
        count += 1
        d -= timedelta(days=1)
    return count


def minutes_this_week(user_id: int) -> int:
    start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    row = db.one("SELECT COALESCE(SUM(seconds),0) s FROM activity WHERE user_id=? AND day >= ?", (user_id, start))
    return round(row["s"] / 60)


def recommended_courses(user_id: int, limit: int = 4) -> list[dict]:
    prof = profile(user_id)
    enrolled = {r["course_id"] for r in db.all_rows("SELECT course_id FROM enrollments WHERE user_id=?", (user_id,))}
    scored = []
    for c in db.all_rows("SELECT * FROM courses WHERE status='published'"):
        if c["id"] in enrolled:
            continue
        score, reasons = 0, []
        if c["category"] in prof["interests"]:
            score += 3
            reasons.append(f"Matches your interest in {c['category']}")
        if (c["level"] == "Beginner") == (prof["experience"] == "beginner"):
            score += 1
            reasons.append(f"Pitched at your level ({c['level'].lower()})")
        popularity = db.one("SELECT COUNT(*) n FROM enrollments WHERE course_id=?", (c["id"],))["n"]
        score += min(popularity, 10) / 10
        if not reasons:
            reasons.append("Popular with learners")
        c["outcomes"] = db.loads(c.pop("outcomes_json"), [])
        scored.append((score, {**course_card(c, user_id), "reason": reasons[0]}))
    scored.sort(key=lambda s: -s[0])
    return [c for _, c in scored[:limit]]
