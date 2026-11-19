"""Pedagogical orchestration engine.

Implements the SOW teaching workflow as an explicit state machine:
greet -> recall learning record -> lesson objective -> diagnostic question ->
explain (age-appropriate, multiple methods) -> worked example -> guided practice ->
evaluate answer + reasoning -> detect misconception -> hint / alternative
explanation -> reassess before advancing -> update record -> recommend next.

All marking is done by SymPy (mathcheck); the LLM only phrases turns.
"""
import json
import re
from datetime import datetime

from . import curriculum, db, llm, mathcheck, memory, safety

HINT_WORDS = r"\b(hint|help|stuck|don'?t know|dunno|idk|no idea|not sure|clue)\b"
EXPLAIN_WORDS = r"(don'?t (get|understand)|do not (get|understand)|confus|explain|another way|again|what do you mean|makes? no sense|lost)"
GIVE_ANSWER_WORDS = r"(just tell me|tell me the answer|what'?s the answer|give me the answer|show me the answer)"
CLAIM_WORDS = r"\b(i (get|understand|know) (it|this)|got it|easy|i'?m fine)\b"
SMALLTALK = r"^\s*(hi|hello|hey|ok|okay|thanks|thank you|cool|yes|yeah|no|sure|ready|go)\b[\s!.]*$"


# ------------------------------------------------------------------ helpers

def _turn(say: str, board: list | None = None, question: dict | None = None, action: str = "say", **meta) -> dict:
    return {"role": "tutor", "say": say, "board": board or [], "question": question, "action": action, "meta": meta}


def _first_name(student: dict) -> str:
    return student["display_name"].split()[0]


def _public_question(q: dict) -> dict:
    return {"prompt": q["prompt"], "latex": q["latex"], "kind": q["kind"], "visual": q.get("visual"),
            "input_hint": curriculum.INPUT_HINTS[q["kind"]], "difficulty": q["difficulty"]}


def _question_board(q: dict, heading: str) -> list:
    board = [{"type": "clear"}, {"type": "title", "content": heading},
             {"type": "text", "content": q["prompt"]}, {"type": "math", "content": q["latex"]}]
    if q.get("visual"):
        board.append(q["visual"])
    return board


def _solution_board(q: dict) -> list:
    board = [{"type": "clear"}, {"type": "title", "content": "Worked solution"}, {"type": "math", "content": q["latex"]}]
    for i, s in enumerate(q["steps"], 1):
        board.append({"type": "step", "n": i, "content": s["text"], "latex": s["latex"]})
    board.append({"type": "highlight", "content": "Answer:", "latex": q["answer_latex"]})
    return board


def _load(lesson_id: int, student: dict) -> tuple[dict, dict]:
    lesson = db.one("SELECT * FROM lessons WHERE id=? AND student_id=?", (lesson_id, student["id"]))
    if not lesson:
        raise LookupError("Lesson not found")
    return lesson, json.loads(lesson["state_json"])


def _save(lesson: dict, state: dict, turns: list[dict]) -> None:
    board = json.loads(lesson["board_json"])
    for t in turns:
        for op in t["board"]:
            board = [] if op["type"] == "clear" else board + [op]
    last = datetime.fromisoformat(lesson["last_active_at"])
    now = datetime.fromisoformat(db.now_iso())
    gained = min(120, max(0, int((now - last).total_seconds())))
    db.execute("UPDATE lessons SET state_json=?, board_json=?, last_active_at=?, duration_seconds=duration_seconds+? WHERE id=?",
               (db.dumps(state), db.dumps(board), db.now_iso(), gained, lesson["id"]))
    for t in turns:
        db.execute("INSERT INTO messages (lesson_id, role, text, board_json, meta_json, created_at) VALUES (?,?,?,?,?,?)",
                   (lesson["id"], "tutor", t["say"], db.dumps(t["board"]), db.dumps({"action": t["action"], **t["meta"]}), db.now_iso()))


def _new_question(lesson_id: int, state: dict, difficulty: int) -> dict:
    state["seed_counter"] = state.get("seed_counter", 0) + 1
    q = curriculum.generate_question(state["topic_id"], difficulty, seed=lesson_id * 1000 + state["seed_counter"])
    state.update(q=q, difficulty=difficulty, q_attempts=0, q_hints=0)
    return q


def _progress(student_id: int, state: dict) -> dict:
    m = memory.get_mastery(student_id, state["topic_id"])
    t = curriculum.topic(state["topic_id"])
    return {"phase": state["phase"], "difficulty": state["difficulty"], "level": t["levels"][state["difficulty"] - 1],
            "streak": state["streak"], "answered": state["answered"], "correct": state["correct"],
            "p_mastery": round(m["p_mastery"], 2), "status": memory.status_label(m), "evidence": m["evidence_count"]}


def _voice(student: dict, lesson_id: int, state: dict, action: str, draft: str, facts: dict, query: str | None = None) -> tuple[str, list]:
    """Let the LLM phrase the verified draft; fall back to the draft on any problem."""
    if action not in llm.LLM_ACTIONS:
        return draft, []
    t = curriculum.topic(state["topic_id"])
    payload = {
        "student": {"first_name": _first_name(student), "school_year": student["year_group"]},
        "topic": t["title"], "action": action, "facts": facts, "draft": draft,
        "current_question": state["q"]["prompt"] if state.get("q") else None,
        "retrieved_content": [c["text"] for c in curriculum.retrieve(state["topic_id"], query or t["title"], k=2)],
    }
    if query:
        payload["student_message"] = query
        payload["recent_transcript"] = [
            f"{m['role']}: {m['text'][:200]}"
            for m in reversed(db.all_rows("SELECT role, text FROM messages WHERE lesson_id=? ORDER BY id DESC LIMIT 3", (lesson_id,)))]
    out = llm.voice.generate(payload, student["id"], lesson_id)
    if not out or not out.get("say"):
        return draft, []
    say = out["say"]
    if not safety.output_is_safe(say) or (action != "show_solution" and safety.reveals_answer(say, state.get("q"))):
        return draft, []
    sources = [draft, *payload["retrieved_content"], *(c for c in curriculum.topic(state["topic_id"])["content"]),
               state["q"]["prompt"] if state.get("q") else "", query or "", student["display_name"]]
    if not safety.grounded(say, sources):
        print(f"[llm] ungrounded answer rejected, using verified content: {say[:120]}")
        return draft, []
    extra = [b for b in out.get("board", [])[:3] if b.get("type") in ("math", "text")]
    return say, extra


# ------------------------------------------------------------------ teaching moves

def _explanation_turns(state: dict, method: int) -> list[dict]:
    t = curriculum.topic(state["topic_id"])
    script = t["explanations"][method % len(t["explanations"])]
    turns = []
    for i, part in enumerate(script):
        board = ([{"type": "clear"}, {"type": "title", "content": t["title"] + (" - another way" if method else "")}] if i == 0 else []) + part["board"]
        turns.append(_turn(part["say"], board, action="explain", method=method))
    state["methods_used"] = sorted(set(state.get("methods_used", [])) | {method % len(t["explanations"])})
    return turns


def _ask(lesson_id: int, state: dict, difficulty: int, intro: str, heading: str = "Your turn") -> dict:
    q = _new_question(lesson_id, state, difficulty)
    return _turn(f"{intro} {q['prompt']}".strip(), _question_board(q, heading), _public_question(q), action="ask")


def _repeat_question(state: dict, intro: str) -> dict:
    q = state["q"]
    return _turn(f"{intro} {q['prompt']}".strip(), _question_board(q, "Back to our question"), _public_question(q), action="ask")


def _record_attempt(student: dict, lesson_id: int, state: dict, answer: str, result: dict) -> None:
    q = state["q"]
    correct = result["result"] == "correct"
    mc_code = result["misconception"]["code"] if result["misconception"] else None
    db.execute(
        "INSERT INTO attempts (student_id, lesson_id, topic_id, question_json, answer, result, correct, misconception, difficulty, hints_used, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (student["id"], lesson_id, state["topic_id"], db.dumps(q), answer, result["result"], int(correct), mc_code,
         q["difficulty"], state["q_hints"] + state["q_attempts"], db.now_iso()))
    memory.record_evidence(student["id"], state["topic_id"], correct, assisted=(state["q_hints"] + state["q_attempts"]) > 0)
    if mc_code:
        memory.record_misconception(student["id"], state["topic_id"], mc_code, curriculum.MISCONCEPTIONS[mc_code])
        state.setdefault("lesson_misconceptions", [])
        if mc_code not in state["lesson_misconceptions"]:
            state["lesson_misconceptions"].append(mc_code)
    state["answered"] += 1
    if correct:
        state["correct"] += 1


def _complete(student: dict, lesson: dict, state: dict) -> list[dict]:
    state["phase"] = "complete"
    summary, stats = memory.summarise_lesson(lesson["id"])
    nxt = memory.schedule_review(student["id"], state["topic_id"], stats["accuracy"])
    # misconceptions not repeated after correct reassessment are considered addressed
    memory.resolve_misconceptions(student["id"], state["topic_id"],
                                  [m["code"] for m in memory.open_misconceptions(student["id"], state["topic_id"])])
    if state.get("methods_used"):
        memory.set_effective_method(student["id"], state["topic_id"], "alternative" if 1 in state["methods_used"] else "standard")
    db.execute("UPDATE lessons SET status='completed', ended_at=?, summary=? WHERE id=?", (db.now_iso(), summary, lesson["id"]))
    for a in db.all_rows("SELECT id FROM assignments WHERE student_id=? AND topic_id=? AND status='pending'", (student["id"], state["topic_id"])):
        db.execute("UPDATE assignments SET status='completed' WHERE id=?", (a["id"],))
    m = memory.get_mastery(student["id"], state["topic_id"])
    recs = [r for r in memory.recommendations(student["id"]) if r["topic_id"] != state["topic_id"]]
    rec = recs[0] if recs else None
    status = memory.status_label(m)
    draft = (f"Brilliant work, {_first_name(student)}! You passed the final check. {summary} "
             f"This topic is now '{status}'. I'll bring it back for revision on {datetime.fromisoformat(nxt).strftime('%A %d %B')} "
             "so it sticks in your long-term memory.")
    if rec:
        draft += f" Next, I recommend: {rec['title']}."
    board = [{"type": "clear"}, {"type": "title", "content": "Lesson complete"},
             {"type": "text", "content": summary},
             {"type": "highlight", "content": f"Status: {status}  |  Next revision: {nxt}"}]
    say, extra = _voice(student, lesson["id"], state, "lesson_complete", draft, {"summary": summary, "status": status, "next": rec})
    return [_turn(say, board + extra, action="complete", recommendation=rec, summary=summary)]


# ------------------------------------------------------------------ public API

def start_lesson(student: dict, topic_id: str) -> tuple[int, list[dict], dict]:
    t = curriculum.topic(topic_id)
    name = _first_name(student)
    active = db.one("SELECT * FROM lessons WHERE student_id=? AND topic_id=? AND status='active' ORDER BY id DESC LIMIT 1",
                    (student["id"], topic_id))
    if active:  # resume exactly where the student left off
        state = json.loads(active["state_json"])
        turns = [_turn(f"Welcome back, {name}! We were partway through {t['title'].lower()} - "
                       f"you've answered {state['correct']} of {state['answered']} correctly so far. Let's pick up where we left off.",
                       action="greet")]
        if state.get("q"):
            turns.append(_repeat_question(state, "Here's the question you were on:"))
        _save(active, state, turns)
        return active["id"], turns, _progress(student["id"], state)

    m = memory.get_mastery(student["id"], topic_id)
    last_here = db.one("SELECT id FROM lessons WHERE student_id=? AND topic_id=? AND summary IS NOT NULL ORDER BY id DESC LIMIT 1",
                       (student["id"], topic_id))
    if last_here and (tricky := memory.summarise_lesson(last_here["id"])[1]["tricky"]):
        difficulty = t["levels"].index(tricky[0]) + 1
    else:
        difficulty = 1 if m["p_mastery"] < 0.35 else 2 if m["p_mastery"] < 0.7 else 3
    now = db.now_iso()
    lesson_id = db.execute("INSERT INTO lessons (student_id, topic_id, started_at, last_active_at) VALUES (?,?,?,?)",
                           (student["id"], topic_id, now, now))
    state = {"topic_id": topic_id, "phase": "diagnostic", "difficulty": difficulty, "streak": 0, "answered": 0,
             "correct": 0, "method": 0, "q": None, "q_attempts": 0, "q_hints": 0, "solutions_shown_in_row": 0}
    recall = memory.recall_line(student["id"], topic_id, exclude_lesson=lesson_id)
    objective = t["objectives"][difficulty - 1]
    greeting = f"Hi {name}! I'm Nova, your AI maths tutor."
    if recall:
        greeting += f" {recall}"
    greeting += f" Today's goal: {objective[0].lower() + objective[1:]}."
    board = [{"type": "clear"}, {"type": "title", "content": t["title"]},
             {"type": "text", "content": "Today's learning objective"}, {"type": "highlight", "content": objective}]
    if m["effective_method"]:
        state["method"] = 1 if m["effective_method"] == "alternative" else 0
    lesson = db.one("SELECT * FROM lessons WHERE id=?", (lesson_id,))
    say, _ = _voice(student, lesson_id, state, "greet", greeting, {"recall": recall, "objective": objective})
    turns = [_turn(say, board, action="greet", recall=recall),
             _ask(lesson_id, state, difficulty, "First, a quick warm-up so I can see what you already know:", "Warm-up question")]
    _save(lesson, state, turns)
    db.audit(student["id"], "lesson_started", f"lesson:{lesson_id}")
    return lesson_id, turns, _progress(student["id"], state)


def handle_message(student: dict, lesson_id: int, text: str) -> tuple[list[dict], dict]:
    lesson, state = _load(lesson_id, student)
    db.execute("INSERT INTO messages (lesson_id, role, text, created_at) VALUES (?,?,?,?)", (lesson_id, "student", text, db.now_iso()))

    concern = safety.screen_student_message(text)
    if concern:
        if concern["escalate"]:
            db.execute("INSERT INTO safeguarding_flags (student_id, lesson_id, category, excerpt, created_at) VALUES (?,?,?,?,?)",
                       (student["id"], lesson_id, concern["category"], text[:200], db.now_iso()))
            db.audit(student["id"], "safeguarding_flag_raised", f"lesson:{lesson_id}")
        turns = [_turn(concern["reply"], action="safeguarding", category=concern["category"])]
        _save(lesson, state, turns)
        return turns, _progress(student["id"], state)

    turns = _respond(student, lesson, state, text)
    _save(lesson, state, turns)
    return turns, _progress(student["id"], state)


def _respond(student: dict, lesson: dict, state: dict, text: str) -> list[dict]:
    lesson_id, low = lesson["id"], text.lower().strip()
    q = state.get("q")

    if state["phase"] == "complete":
        recs = [r for r in memory.recommendations(student["id"]) if r["topic_id"] != state["topic_id"]]
        nxt = f" When you're ready, start '{recs[0]['title']}' from your dashboard." if recs else ""
        return [_turn(f"This lesson is complete - great effort today!{nxt}", action="complete")]

    if re.search(GIVE_ANSWER_WORDS, low):
        return [_hint_turn(student, lesson_id, state, "I know it's tempting, but you'll remember it much better if you work it out - I'll guide you.")]
    if re.search(HINT_WORDS, low) and not mathcheck.looks_like_answer(text, q["kind"]):
        return [_hint_turn(student, lesson_id, state, "No problem, let's think it through together.")]
    if re.search(EXPLAIN_WORDS, low):
        state["method"] = state.get("method", 0) + 1
        intro = "Let's try explaining it a different way."
        return [_turn(intro, action="explain")] + _explanation_turns(state, state["method"]) + [_repeat_question(state, "Now, have another go:")]

    if mathcheck.looks_like_answer(text, q["kind"]):
        return _mark(student, lesson, state, text)

    if re.search(CLAIM_WORDS, low):
        return [_repeat_question(state, "Great - the best way to show me is to answer this one:")]
    if re.search(SMALLTALK, low):
        return [_repeat_question(state, "Let's keep going!")]

    # Free-form question: answer from retrieved curriculum content, then steer back.
    chunks = curriculum.retrieve(state["topic_id"], text, k=2)
    draft = f"Good question! {chunks[0]['text']} Now, back to our question: {q['prompt']}"
    say, extra = _voice(student, lesson_id, state, "answer_question", draft,
                        {"retrieved": [c["text"] for c in chunks]}, query=text)
    return [_turn(say, extra, action="answer_question", sources=[f"{c['topic']}#{c['chunk']} v{c['version']}" for c in chunks])]


def _hint_turn(student: dict, lesson_id: int, state: dict, intro: str) -> dict:
    q = state["q"]
    idx = state["q_hints"]
    state["q_hints"] += 1
    if idx < len(q["hints"]):
        draft = f"{intro} {q['hints'][idx]}"
        say, extra = _voice(student, lesson_id, state, "give_hint", draft, {"hint": q["hints"][idx]})
        return _turn(say, [{"type": "highlight", "content": "Hint " + str(idx + 1) + ": " + q["hints"][idx]}] + extra, action="hint")
    state["q_attempts"] = 99  # exhausted - the next wrong answer shows the solution
    return _turn(f"{intro} You've used all the hints. Try your best answer and, if it's not right, I'll walk you through the full solution.",
                 action="hint")


def _mark(student: dict, lesson: dict, state: dict, text: str) -> list[dict]:
    lesson_id, q, name = lesson["id"], state["q"], _first_name(student)
    result = mathcheck.check(text, q)
    t = curriculum.topic(state["topic_id"])

    if result["result"] == "needs_simplifying":
        return [_turn("That's equivalent to the right answer - nice! But can you simplify it fully? Divide the top and bottom by their highest common factor.",
                      action="nudge")]
    if result["result"] == "not_expanded":
        return [_turn("That's equal to the original, but it still has brackets. Multiply out the brackets completely.", action="nudge")]

    phase = state["phase"]
    _record_attempt(student, lesson_id, state, text, result)
    correct = result["result"] == "correct"
    first_try = state["q_attempts"] == 0 and state["q_hints"] == 0

    if correct:
        state["solutions_shown_in_row"] = 0
        praise = "Spot on!" if first_try else "Yes, that's right - well done for sticking with it!"
        if phase == "diagnostic":
            state["phase"] = "practice"
            nxt = min(3, state["difficulty"] + 1)
            draft = f"{praise} You clearly know the basics of {t['levels'][state['difficulty'] - 1]}. Let's build on that."
            say, extra = _voice(student, lesson_id, state, "feedback_correct", draft, {"correct": True})
            return [_turn(say, extra, action="feedback", correct=True),
                    _ask(lesson_id, state, nxt, "Try this one:")]
        if phase == "reassess":
            if first_try:
                return _complete(student, lesson, state)
            state["phase"] = "practice"
            return [_turn(f"{praise} Because you needed some help on that one, let's do one more before we finish.", action="feedback", correct=True),
                    _ask(lesson_id, state, 3, "")]
        # practice
        state["streak"] = state["streak"] + 1 if first_try else state["streak"]
        if state["difficulty"] == 3 and state["streak"] >= 2 or (state["correct"] >= 5 and state["streak"] >= 2):
            state["phase"] = "reassess"
            draft = f"{praise} You're ready for a final check. Answer this one without hints to show me you've really got it."
            say, extra = _voice(student, lesson_id, state, "feedback_correct", draft, {"correct": True, "next": "final check"})
            return [_turn(say, extra, action="feedback", correct=True), _ask(lesson_id, state, 3, "", "Final check")]
        if state["streak"] >= 2 and state["difficulty"] < 3:
            state["streak"] = 0
            nd = state["difficulty"] + 1
            draft = f"{praise} That's two in a row - time to level up to {t['levels'][nd - 1]}."
            say, extra = _voice(student, lesson_id, state, "feedback_correct", draft, {"correct": True, "level_up": t["levels"][nd - 1]})
            return [_turn(say, extra, action="feedback", correct=True), _ask(lesson_id, state, nd, "Here's a harder one:")]
        say, extra = _voice(student, lesson_id, state, "feedback_correct", praise, {"correct": True})
        return [_turn(say, extra, action="feedback", correct=True), _ask(lesson_id, state, state["difficulty"], "Next one:")]

    # ---- incorrect
    state["streak"] = 0
    state["q_attempts"] += 1
    mc = result["misconception"]
    feedback = mc["feedback"] if mc else "Not quite. Let's check your working."

    if phase == "diagnostic":
        state["phase"] = "practice"
        draft = f"Thanks for having a go, {name} - that tells me exactly where to start. {feedback if mc else ''} Let me show you how this works."
        say, _ = _voice(student, lesson_id, state, "diagnostic_feedback", draft, {"correct": False, "misconception": mc and mc["code"]})
        turns = [_turn(say, action="feedback", correct=False, misconception=mc and mc["code"])]
        turns += _explanation_turns(state, state.get("method", 0))
        turns.append(_turn("Here's how to solve the warm-up question step by step.", _solution_board(q), action="show_solution"))
        turns.append(_ask(lesson_id, state, max(1, state["difficulty"] - 1) if not mc else state["difficulty"], "Now you try one:"))
        return turns

    if phase == "reassess":
        state["phase"] = "practice"
        draft = f"{feedback} Not quite there yet, and that's fine - we don't move on until you're confident. Let's practise a bit more."
        say, _ = _voice(student, lesson_id, state, "feedback_incorrect", draft, {"correct": False, "misconception": mc and mc["code"]})
        return [_turn(say, action="feedback", correct=False, misconception=mc and mc["code"]),
                _turn("Here's the full method for that one.", _solution_board(q), action="show_solution"),
                _ask(lesson_id, state, 2, "Try this:")]

    if state["q_attempts"] == 1 and state["q_hints"] < len(q["hints"]):
        hint = q["hints"][state["q_hints"]]
        state["q_hints"] += 1
        draft = f"{feedback} {hint}"
        say, extra = _voice(student, lesson_id, state, "feedback_incorrect", draft,
                            {"correct": False, "misconception": mc and mc["code"], "hint": hint})
        return [_turn(say, [{"type": "highlight", "content": "Hint: " + hint}] + extra, action="feedback", correct=False,
                      misconception=mc and mc["code"])]
    if state["q_attempts"] == 2 and state["q_hints"] < len(q["hints"]):
        hint = q["hints"][state["q_hints"]]
        state["q_hints"] += 1
        draft = f"Still not quite. {feedback if mc else ''} {hint} Have one more go."
        say, extra = _voice(student, lesson_id, state, "feedback_incorrect", draft,
                            {"correct": False, "misconception": mc and mc["code"], "hint": hint})
        return [_turn(say, [{"type": "highlight", "content": "Hint: " + hint}] + extra, action="feedback", correct=False,
                      misconception=mc and mc["code"])]

    # third miss (or hints exhausted): worked solution, then a similar question
    state["solutions_shown_in_row"] = state.get("solutions_shown_in_row", 0) + 1
    turns = [_turn(f"{feedback if mc else 'That one was tricky.'} Let's go through it together step by step.",
                   _solution_board(q), action="show_solution", misconception=mc and mc["code"])]
    if state["solutions_shown_in_row"] >= 2:
        state["solutions_shown_in_row"] = 0
        state["method"] = state.get("method", 0) + 1
        turns.append(_turn("I think a different way of looking at this might help.", action="explain"))
        turns += _explanation_turns(state, state["method"])
    turns.append(_ask(lesson_id, state, max(1, state["difficulty"] - (1 if state["difficulty"] > 1 and not mc else 0)),
                      "Now try a similar one:"))
    return turns


def end_lesson(student: dict, lesson_id: int) -> dict:
    lesson, state = _load(lesson_id, student)
    if lesson["status"] == "active":
        summary, stats = memory.summarise_lesson(lesson_id)
        if stats["attempts"]:
            memory.schedule_review(student["id"], state["topic_id"], stats["accuracy"])
        # status stays 'active' so the student can resume; summary feeds memory recall
        db.execute("UPDATE lessons SET summary=? WHERE id=?", (summary, lesson_id))
        return {"summary": summary, "resumable": True}
    return {"summary": lesson["summary"], "resumable": False}
