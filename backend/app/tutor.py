"""Personalised AI tutor, one per course.

Each turn is one of:
  * practice  - "Quiz me": a question on the learner's weakest concept, marked
                deterministically and fed into concept mastery
  * explain / example - instant, from the lesson's verified Key points / Example
  * question  - free-form: retrieve course passages, let the LLM answer in the
                learner's preferred style, then check it is safe, grounded in
                the course and doesn't give away quiz answers. If any check
                fails (or no LLM is running) the learner gets the verified
                passage instead.

`respond` yields events: {"type": "delta", "text"} while streaming and a final
{"type": "done", "message": {...}}.
"""
import random
import re

from . import db, learning, llm, retrieval, safety

STYLE_GUIDE = {
    "examples": "Lead with an example taken from the course excerpts, then state the rule.",
    "step-by-step": "Break explanations into short numbered steps.",
    "concise": "Be brief: the key idea in two or three sentences.",
}
LETTERS = "ABCDEFG"


def conversation(user_id: int, course_id: int) -> dict:
    conv = db.one("SELECT * FROM tutor_conversations WHERE user_id=? AND course_id=?", (user_id, course_id))
    if not conv:
        cid = db.execute("INSERT INTO tutor_conversations (user_id, course_id, created_at, updated_at) VALUES (?,?,?,?)",
                         (user_id, course_id, db.now_iso(), db.now_iso()))
        conv = db.one("SELECT * FROM tutor_conversations WHERE id=?", (cid,))
    return conv


def history(user_id: int, course_id: int, limit: int = 40) -> list[dict]:
    conv = conversation(user_id, course_id)
    rows = db.all_rows("SELECT * FROM tutor_messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?", (conv["id"], limit))
    return [{"role": r["role"], "text": r["text"], "meta": db.loads(r["meta_json"], {}), "created_at": r["created_at"]} for r in reversed(rows)]


def greeting(user: dict, course_id: int, lesson_id: int | None) -> str:
    name = user["display_name"].split()[0]
    weak = learning.weak_concepts(user["id"], course_id)
    l = learning.lesson(lesson_id) if lesson_id else None
    text = f"Hi {name}, I'm Nova, your AI tutor for this course."
    if weak:
        text += f" Last time, {weak[0]['label']} needed more practice - tap **Quiz me** whenever you want a quick round on it."
    elif l:
        text += f" Ask me anything about **{l['title']}**, or tap a button below."
    return text


def _save(conv_id: int, lesson_id: int | None, role: str, text: str, meta: dict | None = None) -> int:
    mid = db.execute("INSERT INTO tutor_messages (conversation_id, lesson_id, role, text, meta_json, created_at) VALUES (?,?,?,?,?,?)",
                     (conv_id, lesson_id, role, text, db.dumps(meta or {}), db.now_iso()))
    db.execute("UPDATE tutor_conversations SET updated_at=? WHERE id=?", (db.now_iso(), conv_id))
    return mid


def _classify(message_id: int, kind: str, redact: bool = False) -> None:
    """Label the learner's message once we know what it was (and never keep personal data)."""
    if redact:
        db.execute("UPDATE tutor_messages SET text='[removed: contained personal data]' WHERE id=?", (message_id,))
    db.execute("UPDATE tutor_messages SET meta_json=? WHERE id=?", (db.dumps({"kind": kind}), message_id))


def _done(conv: dict, lesson_id, text: str, **meta) -> dict:
    _save(conv["id"], lesson_id, "tutor", text, meta)
    return {"type": "done", "message": {"role": "tutor", "text": text, "meta": meta}}


def _open_quiz(user_id: int, l: dict | None) -> list[dict]:
    """Questions of the current quiz lesson if the learner hasn't passed it yet."""
    if not l or l["kind"] != "quiz":
        return []
    passed = db.one("SELECT 1 FROM quiz_attempts WHERE user_id=? AND lesson_id=? AND passed=1", (user_id, l["id"]))
    return [] if passed else l["quiz"]


# ------------------------------------------------------------------ practice

def _pick_practice(user_id: int, course_id: int, current: dict | None) -> tuple[dict, dict] | None:
    weak = [c["concept"] for c in learning.weak_concepts(user_id, course_id)]  # weakest first
    focus = weak[:1] or (current["concepts"] if current else [])
    attempted = {r["lesson_id"] for r in db.all_rows("SELECT DISTINCT lesson_id FROM quiz_attempts WHERE user_id=?", (user_id,))}
    bank = []
    for l in learning.lessons_of(course_id):
        # only quizzes already attempted: their answers were revealed on submission, so nothing unseen is spoiled
        if l["kind"] != "quiz" or l["id"] not in attempted:
            continue
        for i, q in enumerate(l["quiz"]):
            bank.append((l, i, q))
    if not bank:
        return None
    preferred = [b for b in bank if b[2]["concept"] in focus] or bank
    l, i, q = random.choice(preferred)
    return {"lesson_id": l["id"], "index": i}, q


def _practice_text(q: dict, concept_is_weak: bool) -> str:
    intro = f"Let's practise **{learning.concept_label(q['concept'])}**" + (" - it's one of your focus areas." if concept_is_weak else ".")
    body = f"{intro}\n\n{q['q']}"
    if q["type"] == "choice":
        body += "\n\n" + "\n".join(f"- **{LETTERS[i]}.** {opt}" for i, opt in enumerate(q["options"]))
        body += "\n\nReply with the letter."
    else:
        body += "\n\nType your answer."
    return body


def _looks_like_answer(text: str, q: dict) -> bool:
    t = text.strip()
    if q["type"] == "choice":
        return bool(re.fullmatch(r"[A-Ga-g][.)]?|\d", t))
    return len(t) <= 40 and "?" not in t


def _mark_practice(user: dict, conv: dict, text: str, lesson_id) -> dict:
    ref = db.loads(conv["practice_json"])
    source = learning.lesson(ref["lesson_id"])
    q = source["quiz"][ref["index"]]
    answer = text.strip()
    if q["type"] == "choice" and re.fullmatch(r"[A-Ga-g][.)]?", answer):
        answer = LETTERS.index(answer[0].upper())
    ok = learning.mark_question(q, answer)
    p = learning.record_concept(user["id"], source["course_id"], q["concept"], ok)
    db.execute("UPDATE tutor_conversations SET practice_json=NULL WHERE id=?", (conv["id"],))
    correct = q["options"][q["answer"]] if q["type"] == "choice" else q["accept"][0]
    teaches = next((c for c in learning.concepts_of(user["id"], source["course_id"]) if c["concept"] == q["concept"]), None)
    if ok:
        reply = f"✅ Correct! {q['explain']}"
    else:
        where = teaches["lesson_title"] if teaches else source["title"]
        reply = f"Not quite - the answer is **{correct}**. {q['explain']}\n\nTo go over it again, revisit **{where}** or ask me to explain."
    status = learning.mastery_status(p, 1 + (1 if p > 0.5 else 0))
    reply += f"\n\n_{learning.concept_label(q['concept'])}: {round(p * 100)}% mastery estimate._ Tap **Quiz me** for another."
    return _done(conv, lesson_id, reply, kind="practice_feedback", correct=ok, concept=q["concept"], mastery=round(p, 2), status=status)


# ------------------------------------------------------------------ main entry

def respond(user: dict, course_id: int, lesson_id: int | None, text: str, action: str | None):
    conv = conversation(user["id"], course_id)
    l = learning.lesson(lesson_id) if lesson_id else None
    if l and l["course_id"] != course_id:
        l, lesson_id = None, None
    text = (text or "").strip()[:800]
    shown = {"quiz_me": "Quiz me", "explain_simple": "Explain this lesson simply", "example": "Give me an example"}.get(action, text)
    msg_id = _save(conv["id"], lesson_id, "learner", shown, {"kind": action} if action else None)

    # Practice answer pending?
    if conv["practice_json"] and not action and text:
        ref = db.loads(conv["practice_json"])
        q = learning.lesson(ref["lesson_id"])["quiz"][ref["index"]]
        if _looks_like_answer(text, q):
            _classify(msg_id, "practice_answer")
            yield _mark_practice(user, conv, text, lesson_id)
            return

    if text and not action:
        concern = safety.screen(text)
        if concern:
            _classify(msg_id, "flagged", redact=concern["category"] == "personal_data")
            if concern["escalate"]:
                db.execute("INSERT INTO moderation_flags (user_id, source, category, excerpt, created_at) VALUES (?,?,?,?,?)",
                           (user["id"], f"tutor:course:{course_id}", concern["category"], text[:200], db.now_iso()))
                db.audit(user["id"], "moderation_flag_raised", concern["category"])
            yield _done(conv, lesson_id, concern["reply"], kind="safety")
            return
        if re.fullmatch(r"(please )?(quiz|test) me( again)?[.!]?", text.lower()):
            action = "quiz_me"
        else:
            _classify(msg_id, "question")

    if action == "quiz_me":
        picked = _pick_practice(user["id"], course_id, l)
        if not picked:
            yield _done(conv, lesson_id, "Take your first quiz in this course, then I'll build personal practice from it - focused on whatever you find hardest.", kind="info")
            return
        ref, q = picked
        db.execute("UPDATE tutor_conversations SET practice_json=? WHERE id=?", (db.dumps(ref), conv["id"]))
        weak = {c["concept"] for c in learning.weak_concepts(user["id"], course_id)}
        yield _done(conv, lesson_id, _practice_text(q, q["concept"] in weak), kind="practice",
                    question={"q": q["q"], "type": q["type"], "options": q.get("options")})
        return

    if action in ("explain_simple", "example"):
        if not l or l["kind"] == "quiz":
            yield _done(conv, lesson_id, "Open an article lesson and I'll summarise it or give you an example from it.", kind="info")
            return
        if action == "explain_simple":
            points = retrieval.section(l, "Key points")
            reply = f"**{l['title']}** in a nutshell:\n\n{points}" if points else l["content_md"][:600]
            prof = learning.profile(user["id"])
            if prof["style"] == "examples" and retrieval.section(l, "Example"):
                reply += f"\n\n**Example:**\n{retrieval.section(l, 'Example')}"
        else:
            ex = retrieval.section(l, "Example")
            reply = f"Here's an example from **{l['title']}**:\n\n{ex}" if ex else "This lesson doesn't include a worked example yet - ask me a specific question instead."
        yield _done(conv, lesson_id, reply + "\n\nWant to check your understanding? Tap **Quiz me**.", kind=action,
                    sources=[{"lesson_id": l["id"], "lesson_title": l["title"]}])
        return

    if not text:
        yield _done(conv, lesson_id, "Ask me anything about this course.", kind="info")
        return

    yield from _answer_question(user, conv, course_id, l, text)


def _answer_question(user: dict, conv: dict, course_id: int, l: dict | None, text: str):
    lesson_id = l["id"] if l else None
    hits = retrieval.search(course_id, text, lesson_id, k=3)
    sources = [{"lesson_id": h["lesson_id"], "lesson_title": h["lesson_title"]} for h in hits]
    sources = list({s["lesson_id"]: s for s in sources}.values())
    course = learning.course(course_id)

    if not hits:
        yield _done(conv, lesson_id,
                    f"I couldn't find that in **{course['title']}**. I only answer from the course material so I never give you made-up information. "
                    "Try rephrasing, or post it in the lesson's discussion so the course team can help.", kind="not_found")
        return

    fallback = (f"Here's what the course says about that:\n\n{hits[0]['text']}\n\n"
                f"_From: {hits[0]['lesson_title']}_")
    open_quiz = _open_quiz(user["id"], l)

    if llm.model.name == "offline":
        yield _done(conv, lesson_id, fallback, kind="answer", sources=sources, grounded=True, generated=False)
        return

    prof = learning.profile(user["id"])
    weak = learning.weak_concepts(user["id"], course_id)
    system = (
        "You are Nova, a friendly AI tutor inside an online academy. You are an AI, not a human.\n"
        f"The learner: {user['display_name'].split()[0]}, {prof['experience']} level, goal: {prof['goal'] or 'not stated'}.\n"
        f"Teaching style they asked for: {STYLE_GUIDE.get(prof['style'], '')}\n"
        "Rules:\n"
        "- Answer ONLY using the COURSE EXCERPTS provided. If they don't cover the question, say it isn't covered in this course.\n"
        "- Never invent facts, numbers, tools, links or new examples - reuse the course's own wording and examples.\n"
        "- Keep it under 150 words. Use simple language and markdown.\n"
        + ("- The learner is taking a quiz. Do NOT give the answer to any of these questions; give a hint or point to the relevant idea instead:\n"
           + "\n".join(f"  * {q['q']}" for q in open_quiz) + "\n" if open_quiz else "")
        + (f"- Topics they find hard: {', '.join(w['label'] for w in weak[:3])}. Be extra clear if relevant.\n" if weak else "")
        + "- End with one short question that checks their understanding."
    )
    excerpts = "\n\n".join(f"[{h['lesson_title']} - {h['section']}]\n{h['text']}" for h in hits)
    # only genuine recent Q&A, so unrelated turns don't leak into the answer
    past = [m for m in history(user["id"], course_id, 5)[:-1] if m["meta"].get("kind") in ("question", "answer")][-2:]
    messages = [{"role": "user" if m["role"] == "learner" else "assistant", "content": m["text"][:600]} for m in past]
    messages.append({"role": "user", "content": f"COURSE EXCERPTS:\n{excerpts}\n\nQUESTION: {text}"})
    # the API requires alternating roles starting with user
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    merged = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n\n" + m["content"]
        else:
            merged.append(dict(m))

    out = ""
    for chunk in llm.model.stream(system, merged, user["id"], course_id):
        out += chunk
        yield {"type": "delta", "text": chunk}

    out = out.strip()
    known = [h["text"] for h in hits] + [text, user["display_name"], course["title"], *(h["lesson_title"] for h in hits)]
    if not out:
        yield _done(conv, lesson_id, fallback, kind="answer", sources=sources, grounded=True, generated=False)
    elif not safety.output_is_safe(out) or safety.leaks_quiz_answer(out, open_quiz):
        yield _done(conv, lesson_id, "I can't give quiz answers, but this part of the course will help:\n\n" + hits[0]["text"],
                    kind="answer", sources=sources, grounded=True, generated=False, replaced="quiz_guard")
    elif not safety.grounded(out, known, threshold=0.5):
        print(f"[tutor] ungrounded answer replaced: {out[:120]}")
        yield _done(conv, lesson_id, "Here's exactly what the course says (I keep to the course material so I don't mislead you):\n\n"
                    + hits[0]["text"] + f"\n\n_From: {hits[0]['lesson_title']}_",
                    kind="answer", sources=sources, grounded=True, generated=False, replaced="grounding")
    else:
        yield _done(conv, lesson_id, out, kind="answer", sources=sources, grounded=True, generated=True)
