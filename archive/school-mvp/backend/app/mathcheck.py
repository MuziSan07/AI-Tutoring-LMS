"""Mathematical verification with SymPy.

Every answer the tutor marks is checked here symbolically, never by the LLM.
"""
import re

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

X = sp.Symbol("x")
_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
_LOCALS = {"x": X, "sqrt": sp.sqrt, "pi": sp.pi}

_WORD_NUMBERS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
}


def normalise(text: str, kind: str) -> str:
    s = text.strip().lower()
    s = (s.replace("×", "*").replace("÷", "/").replace("−", "-").replace("–", "-")
          .replace("²", "^2").replace("√", "sqrt"))
    s = re.sub(r"\b(the answer is|answer|it's|it is|i think|i got|maybe|equals|is)\b", " ", s)
    for word, digit in _WORD_NUMBERS.items():
        s = re.sub(rf"\b{word}\b", digit, s)
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)          # 1,200 -> 1200
    s = re.sub(r"[£$€%]|\b(cm|mm|m|km|pounds?|units?)\b", "", s)
    if kind in ("solve", "number", "fraction") and "=" in s:
        s = s.split("=")[-1]
    if kind == "line":
        s = s.split("=")[-1] if "=" in s else s
    s = s.strip().rstrip(".!")
    return s


def parse(text: str, kind: str):
    s = normalise(text, kind)
    if not s or len(s) > 60:
        return None
    if re.search(r"[a-wyz]", s.replace("sqrt", "")):  # stray letters -> probably prose, not maths
        return None
    try:
        return parse_expr(s, local_dict=_LOCALS, transformations=_TRANSFORMS, evaluate=True)
    except Exception:
        return None


def equivalent(a, b, tolerance: float | None = None) -> bool:
    try:
        if tolerance is not None:
            return abs(float(sp.N(a)) - float(sp.N(b))) <= tolerance
        return sp.simplify(sp.sympify(a) - sp.sympify(b)) == 0
    except Exception:
        return False


def looks_like_answer(text: str, kind: str) -> bool:
    return parse(text, kind) is not None and "?" not in text


def check(text: str, question: dict) -> dict:
    """Mark a student's answer.

    Returns {"result": correct|incorrect|needs_simplifying|not_expanded|unparseable,
             "misconception": {...} | None}
    """
    kind = question["kind"]
    tol = question.get("tolerance")
    student = parse(text, kind)
    if student is None:
        return {"result": "unparseable", "misconception": None}
    expected = sp.sympify(question["answer"], locals=_LOCALS)

    if equivalent(student, expected, tol):
        raw = normalise(text, kind)
        if kind == "fraction":
            m = re.fullmatch(r"\s*(-?\d+)\s*/\s*(\d+)\s*", raw)
            if m and sp.gcd(int(m.group(1)), int(m.group(2))) > 1:
                return {"result": "needs_simplifying", "misconception": None}
        if kind == "expression" and "(" in raw:
            return {"result": "not_expanded", "misconception": None}
        return {"result": "correct", "misconception": None}

    for mc in question.get("misconceptions", []):
        if equivalent(student, sp.sympify(mc["answer"], locals=_LOCALS), tol):
            return {"result": "incorrect", "misconception": mc}
    return {"result": "incorrect", "misconception": None}
