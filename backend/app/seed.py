"""Demo data for the academy. All people are fictional test users; every
account's password is DEMO_PASSWORD."""
import random
from datetime import date, datetime, timedelta, timezone

from . import auth, db, learning
from .seed_content import COURSES

DEMO_PASSWORD = "demo1234"


def _ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def _user(role, email, name, headline=None, days_ago=60) -> int:
    return db.execute("INSERT INTO users (role, email, password_hash, display_name, headline, created_at) VALUES (?,?,?,?,?,?)",
                      (role, email, auth.hash_password(DEMO_PASSWORD), name, headline, _ago(days_ago)))


def _profile(uid, goal, experience, interests, style, onboarded=1):
    db.execute("INSERT OR REPLACE INTO learner_profiles (user_id, goal, experience, interests_json, style, onboarded) VALUES (?,?,?,?,?,?)",
               (uid, goal, experience, db.dumps(interests), style, onboarded))


def _create_course(spec: dict, instructor_id: int) -> int:
    cid = db.execute(
        "INSERT INTO courses (slug, title, subtitle, description, category, level, colour, icon, outcomes_json, instructor_id, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (spec["slug"], spec["title"], spec["subtitle"], spec["description"], spec["category"], spec["level"], spec["colour"], spec["icon"],
         db.dumps(spec["outcomes"]), instructor_id, spec.get("status", "published"), _ago(90), _ago(30)))
    for mpos, (mtitle, lessons) in enumerate(spec["modules"], 1):
        mid = db.execute("INSERT INTO modules (course_id, title, position) VALUES (?,?,?)", (cid, mtitle, mpos))
        for lpos, l in enumerate(lessons, 1):
            db.execute(
                "INSERT INTO lessons (module_id, title, kind, content_md, video_url, duration_min, concepts_json, quiz_json, rubric_json, position) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (mid, l["title"], l["kind"], l["md"], l["video"], l["minutes"], db.dumps(l["concepts"]),
                 db.dumps(l["quiz"]) if l["quiz"] else None, db.dumps(l["rubric"]) if l["rubric"] else None, lpos))
    return cid


def _study(uid: int, course_id: int, upto: int, rng: random.Random, skill: float, days_ago: float, weak: set[str] = frozenset()):
    """Simulate a learner working through the first `upto` lessons."""
    learning.enrol(uid, course_id)
    db.execute("UPDATE enrollments SET enrolled_at=? WHERE user_id=? AND course_id=?", (_ago(days_ago + 10), uid, course_id))
    lessons = learning.lessons_of(course_id)
    for i, l in enumerate(lessons[:upto]):
        l["course_id"] = course_id
        day = (date.today() - timedelta(days=max(0, int(days_ago - i * 0.6)))).isoformat()
        secs = l["duration_min"] * 60 + rng.randint(-60, 120)
        db.execute("INSERT INTO activity (user_id, day, seconds) VALUES (?,?,?) ON CONFLICT(user_id, day) DO UPDATE SET seconds=seconds+excluded.seconds",
                   (uid, day, secs))
        db.execute("INSERT INTO lesson_progress (user_id, lesson_id, status, seconds_spent, updated_at) VALUES (?,?,?,?,?) "
                   "ON CONFLICT(user_id, lesson_id) DO UPDATE SET seconds_spent=seconds_spent+excluded.seconds_spent", (uid, l["id"], "started", secs, _ago(days_ago)))
        if l["kind"] == "quiz":
            answers = []
            for q in l["quiz"]:
                good = rng.random() < (0.25 if q["concept"] in weak else skill)
                if q["type"] == "choice":
                    answers.append(q["answer"] if good else (q["answer"] + 1) % len(q["options"]))
                else:
                    answers.append(q["accept"][0] if good else "0")
            res = learning.submit_quiz(uid, l, answers)
            if not res["passed"] and not weak:
                learning.submit_quiz(uid, l, [q["answer"] if q["type"] == "choice" else q["accept"][0] for q in l["quiz"]])
        elif l["kind"] == "assignment":
            continue
        else:
            learning.complete_lesson(uid, l)
    for table in ("lesson_progress",):
        db.execute(f"UPDATE {table} SET updated_at=? WHERE user_id=?", (_ago(days_ago), uid))
    db.execute("UPDATE quiz_attempts SET created_at=? WHERE user_id=? AND created_at > ?", (_ago(days_ago), uid, _ago(0.01)))
    db.execute("UPDATE enrollments SET last_active_at=? WHERE user_id=? AND course_id=?", (_ago(days_ago), uid, course_id))
    nxt = next((l for l in lessons[upto:upto + 1]), lessons[min(upto, len(lessons)) - 1])
    db.execute("UPDATE enrollments SET last_lesson_id=? WHERE user_id=? AND course_id=?", (nxt["id"], uid, course_id))


def seed() -> None:
    if db.one("SELECT 1 FROM users LIMIT 1"):
        return
    rng = random.Random(7)
    _user("admin", "admin@academy.demo", "Rachel Adeyemi", "Academy administrator", 200)
    dan = _user("instructor", "daniel@academy.demo", "Daniel Okoro", "Software engineer · Python & data instructor", 180)
    sofia = _user("instructor", "sofia@academy.demo", "Sofia Marin", "Growth marketer & product designer", 180)
    owners = {"Programming": dan, "Data": dan, "Marketing": sofia, "Design": sofia, "Business": sofia}
    ids = {spec["slug"]: _create_course(spec, owners[spec["category"]]) for spec in COURSES}

    # Main demo learner: a career changer, mid-way through Python with loops as a weak spot
    aisha = _user("learner", "aisha@learner.demo", "Aisha Khan", None, 40)
    _profile(aisha, "Change career into tech", "beginner", ["Programming", "Data"], "examples")
    _study(aisha, ids["data-analysis-with-excel"], 99, rng, 0.95, 20)
    _study(aisha, ids["python-for-beginners"], 6, rng, 0.9, 2, weak={"loops"})
    _study(aisha, ids["digital-marketing-fundamentals"], 2, rng, 0.9, 6)
    for d in range(1, 4):  # a 3-day study streak
        db.execute("INSERT OR REPLACE INTO activity (user_id, day, seconds) VALUES (?,?,?)",
                   (aisha, (date.today() - timedelta(days=d)).isoformat(), 900 + d * 300))
    db.execute("INSERT INTO reviews (user_id, course_id, rating, body, created_at) VALUES (?,?,?,?,?)",
               (aisha, ids["data-analysis-with-excel"], 5, "Pivot tables finally make sense. The AI tutor's examples really helped.", _ago(15)))

    names = ["Tom Fletcher", "Mei Lin", "Omar Haddad", "Grace Mensah", "Lukas Novak", "Priya Desai", "Jack O'Neill",
             "Fatima Zahra", "Ben Carter", "Chloe Dubois", "Ravi Patel", "Hannah Schmidt"]
    published = [s for s in COURSES if s.get("status", "published") == "published"]
    reviews = {
        5: ["Clear, practical and well paced.", "Loved the quizzes and the tutor.", "Exactly what I needed for my new job."],
        4: ["Great intro - would like more advanced content.", "Very good, the assignment was challenging.", "Solid course, helpful examples."],
        3: ["Good basics but a bit short.", "Useful, though I wanted videos."],
    }
    learners = [aisha]
    for i, name in enumerate(names):
        uid = _user("learner", name.split()[0].lower().replace("'", "") + "@learner.demo", name, None, rng.randint(10, 120))
        learners.append(uid)
        cats = rng.sample(["Programming", "Marketing", "Data", "Design"], 2)
        _profile(uid, rng.choice(["Get promoted", "Start a business", "Change career into tech", "Learn for fun"]),
                 rng.choice(["beginner", "beginner", "intermediate"]), cats, rng.choice(["examples", "step-by-step", "concise"]))
        for spec in rng.sample(published, rng.randint(1, 3)):
            n = len(learning.lessons_of(ids[spec["slug"]]))
            weak = set(rng.sample([c for l in learning.lessons_of(ids[spec["slug"]]) for c in l["concepts"]], 1)) if rng.random() < 0.5 else set()
            _study(uid, ids[spec["slug"]], rng.randint(2, n), rng, rng.uniform(0.6, 0.95), rng.uniform(0.5, 25), weak)
            if rng.random() < 0.55:
                stars = rng.choice([5, 5, 4, 4, 3])
                db.execute("INSERT OR IGNORE INTO reviews (user_id, course_id, rating, body, created_at) VALUES (?,?,?,?,?)",
                           (uid, ids[spec["slug"]], stars, rng.choice(reviews[stars]), _ago(rng.uniform(1, 30))))

    # Assignment submissions waiting for the content team
    py_project = next(l for l in learning.lessons_of(ids["python-for-beginners"]) if l["kind"] == "assignment")
    code = ("prices = {'apple': 0.5, 'bread': 1.2, 'cheese': 3.5}\nbasket = ['apple', 'bread', 'cheese', 'cheese']\n\n"
            "def basket_total(basket, prices):\n    total = 0\n    for item in basket:\n        total = total + prices[item]\n    return total\n\n"
            "total = basket_total(basket, prices)\nprint(total)\n\nI store prices in a dictionary and loop over the basket adding each price.")
    advanced = sorted((e["user_id"] for e in db.all_rows("SELECT user_id FROM enrollments WHERE course_id=? AND user_id != ?",
                                                          (ids["python-for-beginners"], aisha))),
                      key=lambda u: -learning.progress_of(u, ids["python-for-beginners"])["percent"])
    for uid in advanced[:2]:
        db.execute("INSERT INTO submissions (user_id, lesson_id, body, auto_feedback_json, created_at) VALUES (?,?,?,?,?)",
                   (uid, py_project["id"], code, db.dumps(learning.rubric_check(code, py_project["rubric"])), _ago(rng.uniform(0.5, 3))))

    # Discussion threads and tutor questions (feed the content team's insights)
    loops = next(l for l in learning.lessons_of(ids["python-for-beginners"]) if l["title"] == "Loops")
    q = db.execute("INSERT INTO discussions (course_id, lesson_id, user_id, body, created_at) VALUES (?,?,?,?,?)",
                   (ids["python-for-beginners"], loops["id"], learners[2], "Why does range(5) stop at 4 and not 5?", _ago(3)))
    db.execute("INSERT INTO discussions (course_id, lesson_id, user_id, parent_id, body, created_at) VALUES (?,?,?,?,?,?)",
               (ids["python-for-beginners"], loops["id"], dan, q,
                "Great question! range(stop) goes up to but not including stop, so range(5) gives five numbers: 0-4. That's handy because lists are indexed from 0 too.", _ago(2.5)))
    asked = {
        "python-for-beginners": ["what is the difference between = and ==", "why does my while loop never stop", "when should I use a dictionary instead of a list",
                                 "how do I loop through a dictionary", "what does return do"],
        "digital-marketing-fundamentals": ["how do I calculate ROI", "what is a good CTR", "difference between CPC and CPM"],
        "data-analysis-with-excel": ["how to lock a cell reference", "xlookup vs vlookup"],
        "ui-ux-design-basics": ["how many users do I need for testing"],
    }
    for slug, questions in asked.items():
        for text in questions:
            uid = rng.choice(learners[1:])
            conv = db.execute("INSERT INTO tutor_conversations (user_id, course_id, created_at, updated_at) VALUES (?,?,?,?)",
                              (uid, ids[slug], _ago(5), _ago(5)))
            db.execute("INSERT INTO tutor_messages (conversation_id, role, text, meta_json, created_at) VALUES (?,?,?,?,?)",
                       (conv, "learner", text, db.dumps({"kind": "question"}), _ago(rng.uniform(0.2, 9))))
    db.audit(None, "demo_data_seeded", f"{len(COURSES)} courses, {len(learners)} learners")
