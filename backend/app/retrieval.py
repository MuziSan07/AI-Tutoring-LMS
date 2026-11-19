"""Course-content retrieval for the AI tutor (RAG).

Lesson markdown is split into passages and ranked with BM25. The index is
rebuilt when a course is edited. Production: embeddings in pgvector, same API.
"""
import math
import re
from collections import Counter

from . import db, learning

STOP = set("""a an and are as at be but by can do does for from how i if in into is it its me my of on or so
than that the their then there these they this to was what when where which who why will with you your
just get got make use using""".split())

_cache: dict[int, tuple[str, list[dict], dict]] = {}


def stem(w: str) -> str:
    """Tiny suffix stripper so 'stops', 'stopped' and 'stopping' match 'stop'."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            w = w[: -len(suffix)]
            break
    if len(w) > 3 and w[-1] == w[-2]:  # stopp -> stop
        w = w[:-1]
    return w[:7]


OPERATORS = {"==": "op_eq", "!=": "op_ne", ">=": "op_ge", "<=": "op_le", "=": "op_assign"}


def tokens(text: str) -> list[str]:
    """Words (stemmed) plus code operators, which matter in programming questions."""
    out = []
    for w in re.findall(r"[a-z0-9]+|==|!=|>=|<=|=", text.lower()):
        if w in OPERATORS:
            out.append(OPERATORS[w])
        elif w not in STOP and len(w) > 1:
            out.append(stem(w))
    return out


def _passages(course_id: int) -> list[dict]:
    out = []
    for l in learning.lessons_of(course_id):
        if l["kind"] == "quiz" or not l["content_md"]:
            continue
        section = l["title"]
        for block in re.split(r"\n\s*\n", l["content_md"]):
            heading = re.match(r"^#+\s*(.+)", block.strip())
            if heading:
                section = heading.group(1)
                block = block.strip()[heading.end():].strip()
                if not block:
                    continue
            if len(block.strip()) < 20:
                continue
            if out and out[-1]["lesson_id"] == l["id"] and out[-1]["section"] == section and len(out[-1]["text"]) < 450:
                out[-1]["text"] += "\n\n" + block.strip()
            else:
                out.append({"lesson_id": l["id"], "lesson_title": l["title"], "module_title": l["module_title"],
                            "section": section, "text": block.strip()})
    return out


def _index(course_id: int) -> tuple[list[dict], dict]:
    stamp = db.one("SELECT updated_at FROM courses WHERE id=?", (course_id,))["updated_at"]
    cached = _cache.get(course_id)
    if cached and cached[0] == stamp:
        return cached[1], cached[2]
    passages = _passages(course_id)
    for p in passages:
        # titles say what a passage is about, so they count extra
        p["tf"] = Counter(tokens(p["lesson_title"]) * 3 + tokens(p["section"]) + tokens(p["text"]))
        p["len"] = sum(p["tf"].values())
    df = Counter(t for p in passages for t in p["tf"])
    stats = {"df": df, "n": len(passages), "avg": (sum(p["len"] for p in passages) / len(passages)) if passages else 1}
    _cache[course_id] = (stamp, passages, stats)
    return passages, stats


def search(course_id: int, query: str, current_lesson_id: int | None = None, k: int = 3) -> list[dict]:
    passages, st = _index(course_id)
    q = tokens(query)
    scored = []
    for p in passages:
        s = 0.0
        for t in q:
            f = p["tf"].get(t, 0)
            if f:
                idf = math.log(1 + (st["n"] - st["df"][t] + 0.5) / (st["df"][t] + 0.5))
                s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * p["len"] / st["avg"]))
        if s and p["lesson_id"] == current_lesson_id:
            s *= 1.3
        if s:
            scored.append((s, p))
    scored.sort(key=lambda x: -x[0])
    return [{k2: v for k2, v in p.items() if k2 not in ("tf", "len")} | {"score": round(s, 2)} for s, p in scored[:k]]


def section(lesson: dict, name: str) -> str | None:
    """Text of a '## name' section in a lesson, e.g. Example or Key points."""
    m = re.search(rf"^##\s*{name}\s*\n(.+?)(?=^##\s|\Z)", lesson["content_md"], re.S | re.M | re.I)
    return m.group(1).strip() if m else None
