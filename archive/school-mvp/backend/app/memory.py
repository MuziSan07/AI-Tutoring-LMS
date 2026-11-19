"""Student memory: evidence-based mastery, misconceptions, spaced repetition,
lesson summaries and next-activity recommendations."""
from datetime import date, datetime, timedelta, timezone

from . import curriculum, db

# Bayesian Knowledge Tracing parameters
P_INIT, P_TRANSIT, P_SLIP, P_GUESS = 0.2, 0.1, 0.1, 0.25
MASTERED_P, MASTERED_EVIDENCE = 0.85, 4


def get_mastery(student_id: int, topic_id: str) -> dict:
    row = db.one("SELECT * FROM mastery WHERE student_id=? AND topic_id=?", (student_id, topic_id))
    if row:
        return row
    db.execute("INSERT INTO mastery (student_id, topic_id, p_mastery) VALUES (?,?,?)", (student_id, topic_id, P_INIT))
    return db.one("SELECT * FROM mastery WHERE student_id=? AND topic_id=?", (student_id, topic_id))


def is_mastered(m: dict) -> bool:
    # A student's claim to understand is never evidence: only marked answers move p_mastery.
    return m["p_mastery"] >= MASTERED_P and m["evidence_count"] >= MASTERED_EVIDENCE and m["correct_count"] >= 3


def status_label(m: dict | None) -> str:
    if not m or m["evidence_count"] == 0:
        return "Not started"
    if is_mastered(m):
        return "Secure"
    return "Developing" if m["p_mastery"] >= 0.5 else "Learning"


def record_evidence(student_id: int, topic_id: str, correct: bool, assisted: bool) -> dict:
    m = get_mastery(student_id, topic_id)
    p = m["p_mastery"]
    if correct:
        post = p * (1 - P_SLIP) / (p * (1 - P_SLIP) + (1 - p) * P_GUESS)
        if assisted:  # correct after hints is weaker evidence
            post = p + (post - p) * 0.3
    else:
        post = p * P_SLIP / (p * P_SLIP + (1 - p) * (1 - P_SLIP))
    p_new = min(0.95, max(0.02, post + (1 - post) * P_TRANSIT))  # never claim certainty
    db.execute(
        "UPDATE mastery SET p_mastery=?, evidence_count=evidence_count+1, correct_count=correct_count+?, last_practised=? "
        "WHERE student_id=? AND topic_id=?",
        (p_new, 1 if correct and not assisted else 0, db.now_iso(), student_id, topic_id))
    return get_mastery(student_id, topic_id)


def record_misconception(student_id: int, topic_id: str, code: str, description: str) -> None:
    db.execute(
        "INSERT INTO misconceptions (student_id, topic_id, code, description, last_seen) VALUES (?,?,?,?,?) "
        "ON CONFLICT(student_id, topic_id, code) DO UPDATE SET count=count+1, last_seen=excluded.last_seen, resolved=0",
        (student_id, topic_id, code, description, db.now_iso()))


def resolve_misconceptions(student_id: int, topic_id: str, codes: list[str]) -> None:
    for code in codes:
        db.execute("UPDATE misconceptions SET resolved=1 WHERE student_id=? AND topic_id=? AND code=?",
                   (student_id, topic_id, code))


def open_misconceptions(student_id: int, topic_id: str | None = None) -> list[dict]:
    if topic_id:
        return db.all_rows("SELECT * FROM misconceptions WHERE student_id=? AND topic_id=? AND resolved=0 ORDER BY count DESC",
                           (student_id, topic_id))
    return db.all_rows("SELECT * FROM misconceptions WHERE student_id=? AND resolved=0 ORDER BY count DESC", (student_id,))


def schedule_review(student_id: int, topic_id: str, accuracy: float) -> str:
    """Spaced repetition: grow the interval on good performance, reset on poor."""
    m = get_mastery(student_id, topic_id)
    interval = m["interval_days"] or 0
    if accuracy >= 0.8:
        interval = 1 if interval == 0 else min(60, round(interval * 2.3))
    elif accuracy >= 0.5:
        interval = max(1, interval)
    else:
        interval = 1
    nxt = (date.today() + timedelta(days=interval)).isoformat()
    db.execute("UPDATE mastery SET interval_days=?, next_review=? WHERE student_id=? AND topic_id=?",
               (interval, nxt, student_id, topic_id))
    return nxt


def set_effective_method(student_id: int, topic_id: str, method: str) -> None:
    db.execute("UPDATE mastery SET effective_method=? WHERE student_id=? AND topic_id=?", (method, student_id, topic_id))


def all_mastery(student_id: int) -> dict[str, dict]:
    return {r["topic_id"]: r for r in db.all_rows("SELECT * FROM mastery WHERE student_id=?", (student_id,))}


def last_lesson(student_id: int, exclude_id: int | None = None) -> dict | None:
    return db.one("SELECT * FROM lessons WHERE student_id=? AND summary IS NOT NULL AND id != ? ORDER BY last_active_at DESC LIMIT 1",
                  (student_id, exclude_id or -1))


def summarise_lesson(lesson_id: int) -> tuple[str, dict]:
    """Deterministic, evidence-based lesson summary stored in the learning record."""
    lesson = db.one("SELECT * FROM lessons WHERE id=?", (lesson_id,))
    t = curriculum.topic(lesson["topic_id"])
    attempts = db.all_rows("SELECT * FROM attempts WHERE lesson_id=?", (lesson_id,))
    first_tries = [a for a in attempts if a["hints_used"] == 0]
    correct = sum(1 for a in attempts if a["correct"])
    by_level: dict[int, list[int]] = {}
    for a in attempts:
        by_level.setdefault(a["difficulty"], []).append(a["correct"])
    strong = [t["levels"][lv - 1] for lv, rs in sorted(by_level.items()) if sum(rs) / len(rs) >= 0.75]
    tricky = [t["levels"][lv - 1] for lv, rs in sorted(by_level.items()) if sum(rs) / len(rs) < 0.6]
    mcs = sorted({a["misconception"] for a in attempts if a["misconception"]})
    mc_text = []
    for code in mcs:
        row = db.one("SELECT description FROM misconceptions WHERE student_id=? AND topic_id=? AND code=?",
                     (lesson["student_id"], lesson["topic_id"], code))
        if row:
            mc_text.append(row["description"])
    parts = [f"Practised {t['title'].lower()}: {correct} of {len(attempts)} answers correct."]
    if strong:
        parts.append(f"Confident with {', '.join(strong)}.")
    if tricky:
        parts.append(f"Found {', '.join(tricky)} tricky.")
    if mc_text:
        parts.append("Watch out for: " + "; ".join(mc_text) + ".")
    stats = {"attempts": len(attempts), "correct": correct, "first_try": len(first_tries),
             "strong": strong, "tricky": tricky, "misconceptions": mcs,
             "accuracy": (correct / len(attempts)) if attempts else 0}
    return " ".join(parts), stats


def recall_line(student_id: int, topic_id: str, exclude_lesson: int | None = None) -> str | None:
    """What the tutor says about previous learning when a student returns."""
    last = last_lesson(student_id, exclude_lesson)
    if not last:
        return None
    t_last = curriculum.topic(last["topic_id"])
    _, stats = summarise_lesson(last["id"])
    line = f"Last time we practised {t_last['title'].lower()}."
    if stats["strong"] and stats["tricky"]:
        line += f" You understood {stats['strong'][0]}, but {stats['tricky'][0]} {'was' if not stats['tricky'][0].endswith('s') else 'were'} tricky."
    elif stats["strong"]:
        line += f" You did really well with {', '.join(stats['strong'])}."
    elif stats["tricky"]:
        line += f" {stats['tricky'][0].capitalize()} {'was' if not stats['tricky'][0].endswith('s') else 'were'} tricky."
    mcs = open_misconceptions(student_id, last["topic_id"])
    if mcs:
        line += f" You sometimes {mcs[0]['description']}."
    if last["topic_id"] == topic_id and (stats["tricky"] or mcs):
        line += " Let's revise that before we continue."
    return line


def recommendations(student_id: int) -> list[dict]:
    today = date.today().isoformat()
    mastery = all_mastery(student_id)
    recs: list[dict] = []
    seen: set[str] = set()

    def add(topic_id, reason, kind):
        if topic_id not in seen:
            seen.add(topic_id)
            recs.append({"topic_id": topic_id, "title": curriculum.topic(topic_id)["title"], "reason": reason, "kind": kind})

    active = db.one("SELECT topic_id FROM lessons WHERE student_id=? AND status='active' ORDER BY last_active_at DESC LIMIT 1", (student_id,))
    if active:
        add(active["topic_id"], "Carry on where you left off", "resume")
    for tid, m in sorted(mastery.items(), key=lambda kv: kv[1]["next_review"] or "9999"):
        if m["next_review"] and m["next_review"] <= today and tid in curriculum.TOPICS:
            add(tid, "Revision due today - keeps it in your long-term memory", "revision")
    for a in db.all_rows("SELECT * FROM assignments WHERE student_id=? AND status='pending' ORDER BY due_date", (student_id,)):
        add(a["topic_id"], f"Set by your teacher{' - due ' + a['due_date'] if a['due_date'] else ''}", "assignment")
    for mc in open_misconceptions(student_id):
        add(mc["topic_id"], f"Let's fix a common slip: you sometimes {mc['description']}", "misconception")
    for tid, m in mastery.items():
        if m["evidence_count"] > 0 and not is_mastered(m) and tid in curriculum.TOPICS:
            add(tid, "Keep building towards secure", "continue")
    for tid, t in curriculum.TOPICS.items():
        m = mastery.get(tid)
        if m and m["evidence_count"] > 0:
            continue
        prereqs_ok = all(mastery.get(p) and mastery[p]["p_mastery"] >= 0.6 for p in t["prerequisites"])
        if prereqs_ok:
            add(tid, "New topic - you're ready for this", "new")
    return recs[:5]


def minutes_today(student_id: int) -> int:
    start = datetime.now(timezone.utc).date().isoformat()
    row = db.one("SELECT COALESCE(SUM(duration_seconds),0) s FROM lessons WHERE student_id=? AND started_at >= ?", (student_id, start))
    return round(row["s"] / 60)
