"""Curriculum knowledge base: KS3 / GCSE Mathematics (Phase 1 scope).

Each topic carries:
  * metadata (country, curriculum, key stage, year, objectives, prerequisites)
  * verified teaching content used for retrieval (RAG) - versioned with a source
  * two explanation methods (standard + alternative) as whiteboard scripts
  * a question generator with three difficulty levels; answers, worked steps,
    hints and common-misconception answers are computed, not written by an LLM.
"""
import random
from fractions import Fraction
from math import gcd, lcm, sqrt

import sympy as sp

CONTENT_VERSION = "1.0.0"
CONTENT_SOURCE = "Platform-authored content aligned to the DfE National Curriculum (KS3) and GCSE (9-1) subject content"

X = sp.Symbol("x")


# ---------------------------------------------------------------- helpers

def fl(f: Fraction) -> str:
    """LaTeX for a Fraction."""
    if f.denominator == 1:
        return str(f.numerator)
    sign = "-" if f < 0 else ""
    return f"{sign}\\frac{{{abs(f.numerator)}}}{{{f.denominator}}}"


def fs(f: Fraction) -> str:
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def num(v: float) -> str:
    v = round(v, 2)
    return str(int(v)) if v == int(v) else f"{v:g}"


def step(text: str, latex: str | None = None) -> dict:
    return {"text": text, "latex": latex}


def mc(answer, code: str, feedback: str) -> dict:
    return {"answer": str(answer), "code": code, "feedback": feedback}


def dedupe_misconceptions(question: dict) -> dict:
    """Drop misconception answers that coincide with the correct answer."""
    ans = sp.sympify(question["answer"], locals={"x": X})
    tol = question.get("tolerance")
    keep = []
    for m in question["misconceptions"]:
        val = sp.sympify(m["answer"], locals={"x": X})
        same = abs(float(sp.N(val - ans))) <= tol if tol and not val.free_symbols else sp.simplify(val - ans) == 0
        if not same and all(m["answer"] != k["answer"] for k in keep):
            keep.append(m)
    question["misconceptions"] = keep
    return question


# ---------------------------------------------------------------- generators

def _proper(den: int, rng: random.Random, hi: int | None = None) -> int:
    """A numerator giving a proper fraction already in its simplest form."""
    return rng.choice([n for n in range(1, (hi or den - 1) + 1) if gcd(n, den) == 1])


def gen_fractions_add(d: int, rng: random.Random) -> dict:
    if d == 1:
        n = rng.choice([5, 7, 8, 9, 10, 11, 12])
        a = _proper(n, rng, n - 2)
        c = rng.randint(1, n - a - 1)
        b = dd = n
    elif d == 2:
        b = rng.choice([2, 3, 4, 5])
        dd = b * rng.choice([2, 3])
        a, c = _proper(b, rng), _proper(dd, rng)
    else:
        b, dd = rng.choice([(3, 4), (2, 5), (3, 5), (4, 5), (5, 6), (3, 7), (4, 7), (2, 7)])
        a, c = _proper(b, rng), _proper(dd, rng)
    f1, f2 = Fraction(a, b), Fraction(c, dd)
    op = "-" if (d > 1 and rng.random() < 0.4 and f1 != f2) else "+"
    if op == "-" and f1 < f2:
        a, b, c, dd, f1, f2 = c, dd, a, b, f2, f1
    ans = f1 + f2 if op == "+" else f1 - f2
    verb, verbing = ("add", "adding") if op == "+" else ("subtract", "subtracting")
    top = a + c if op == "+" else a - c

    steps, mcs = [], []
    if b == dd:
        steps.append(step(f"The denominators are the same ({b}), so keep the denominator and {verb} the numerators.",
                          f"\\frac{{{a}}}{{{b}}} {op} \\frac{{{c}}}{{{b}}} = \\frac{{{a} {op} {c}}}{{{b}}} = \\frac{{{top}}}{{{b}}}"))
        hints = [f"The denominators are already the same. What do you do with the numerators {a} and {c}?",
                 f"Keep the denominator as {b} and {verb} the numerators: {a} {op} {c}."]
    else:
        L = lcm(b, dd)
        a2, c2 = a * (L // b), c * (L // dd)
        top = a2 + c2 if op == "+" else a2 - c2
        steps += [
            step(f"The denominators are different. Find the lowest common multiple of {b} and {dd}: it is {L}."),
            step("Convert each fraction so the denominator is " + str(L) + " (multiply top and bottom by the same number).",
                 f"\\frac{{{a}}}{{{b}}} = \\frac{{{a2}}}{{{L}}}, \\quad \\frac{{{c}}}{{{dd}}} = \\frac{{{c2}}}{{{L}}}"),
            step(f"Now {verb} the numerators and keep the denominator.",
                 f"\\frac{{{a2}}}{{{L}}} {op} \\frac{{{c2}}}{{{L}}} = \\frac{{{top}}}{{{L}}}"),
        ]
        hints = [f"Are the denominators the same? What is the smallest number that both {b} and {dd} divide into?",
                 f"Write both fractions with denominator {L}. Remember to multiply the numerator by the same number as the denominator."]
        if top > 0:
            unscaled = Fraction(a + c if op == "+" else a - c, L)
            if unscaled > 0:
                mcs.append(mc(fs(unscaled), "numerators_not_scaled",
                              "You found a common denominator - great! But when you change the denominator, the numerator has to be multiplied by the same number."))
    if Fraction(top, lcm(b, dd)) != ans or ans.denominator != lcm(b, dd):
        steps.append(step("Simplify the fraction by dividing top and bottom by their highest common factor.", f"= {fl(ans)}"))
    across_top = a + c if op == "+" else a - c
    if across_top > 0:
        mcs.append(mc(fs(Fraction(across_top, b + dd)), "add_across",
                      f"It looks like you {verb}ed the denominators as well as the numerators. The denominator tells us the size of the pieces - it stays the same when we {verb} pieces of the same size."))
    return dedupe_misconceptions({
        "prompt": f"Work out {a}/{b} {op} {c}/{dd}. Give your answer as a fraction in its simplest form.",
        "latex": f"\\frac{{{a}}}{{{b}}} {op} \\frac{{{c}}}{{{dd}}}",
        "answer": fs(ans), "answer_latex": fl(ans), "kind": "fraction",
        "steps": steps, "hints": hints, "misconceptions": mcs,
        "visual": {"type": "fraction_bars", "fractions": [[a, b], [c, dd]], "op": op},
    })


def gen_fractions_multiply(d: int, rng: random.Random) -> dict:
    a, b = rng.randint(1, 5), rng.choice([2, 3, 4, 5, 7])
    while gcd(a, b) != 1 or a >= b:
        a, b = rng.randint(1, 5), rng.choice([2, 3, 4, 5, 7])
    if d == 1:
        c, dd = rng.randint(1, 4), rng.choice([3, 5, 7, 9])
        while gcd(c, dd) != 1 or c >= dd:
            c, dd = rng.randint(1, 4), rng.choice([3, 5, 7, 9])
        ans = Fraction(a, b) * Fraction(c, dd)
        steps = [step("Multiply the numerators together and the denominators together.",
                      f"\\frac{{{a}}}{{{b}}} \\times \\frac{{{c}}}{{{dd}}} = \\frac{{{a} \\times {c}}}{{{b} \\times {dd}}} = \\frac{{{a*c}}}{{{b*dd}}}")]
        hints = ["When multiplying fractions you do not need a common denominator. What do you do with the two numerators?",
                 f"Multiply top x top ({a} x {c}) and bottom x bottom ({b} x {dd})."]
        mcs = [mc(fs(Fraction(a * dd, b * c)), "cross_multiplied",
                  "It looks like you multiplied diagonally (cross-multiplied). For multiplication, multiply straight across: top x top and bottom x bottom.")]
        prompt, latex = f"Work out {a}/{b} x {c}/{dd}.", f"\\frac{{{a}}}{{{b}}} \\times \\frac{{{c}}}{{{dd}}}"
    elif d == 2:
        n = rng.randint(2, 6)
        ans = Fraction(a, b) * n
        steps = [step(f"Write {n} as a fraction: {n}/1.", f"{n} = \\frac{{{n}}}{{1}}"),
                 step("Multiply the numerators and the denominators.",
                      f"\\frac{{{a}}}{{{b}}} \\times \\frac{{{n}}}{{1}} = \\frac{{{a*n}}}{{{b}}}")]
        hints = [f"Try writing {n} as a fraction first. What is {n} over 1?",
                 f"Only the numerator gets multiplied by {n}: {a} x {n} over {b}."]
        mcs = [mc(fs(Fraction(a, b)), "multiplied_both",
                  f"Multiplying the top AND bottom by {n} makes an equivalent fraction - the same size. To find {n} lots of {a}/{b}, only the numerator is multiplied.")]
        prompt, latex = f"Work out {a}/{b} x {n}.", f"\\frac{{{a}}}{{{b}}} \\times {n}"
    else:
        c, dd = rng.randint(1, 4), rng.choice([3, 5, 7, 8])
        while gcd(c, dd) != 1 or c >= dd:
            c, dd = rng.randint(1, 4), rng.choice([3, 5, 7, 8])
        ans = Fraction(a, b) / Fraction(c, dd)
        steps = [step("Keep the first fraction, Change divide to multiply, Flip the second fraction (KCF).",
                      f"\\frac{{{a}}}{{{b}}} \\div \\frac{{{c}}}{{{dd}}} = \\frac{{{a}}}{{{b}}} \\times \\frac{{{dd}}}{{{c}}}"),
                 step("Multiply across.", f"= \\frac{{{a*dd}}}{{{b*c}}}")]
        hints = ["Dividing by a fraction is the same as multiplying by its reciprocal. What is the reciprocal of the second fraction?",
                 f"Keep {a}/{b}, change the divide to a multiply, and flip {c}/{dd} to {dd}/{c}."]
        mcs = [mc(fs(Fraction(a * c, b * dd)), "forgot_reciprocal",
                  "It looks like you multiplied instead of dividing. When dividing by a fraction, flip the second fraction first (Keep, Change, Flip)."),
               mc(fs(Fraction(b * c, a * dd)), "flipped_first",
                  "Careful - it's the second fraction (the divisor) that gets flipped, not the first one.")]
        prompt, latex = f"Work out {a}/{b} ÷ {c}/{dd}.", f"\\frac{{{a}}}{{{b}}} \\div \\frac{{{c}}}{{{dd}}}"
    if not (steps[-1]["latex"] or "").endswith(fl(ans)):
        steps.append(step("Simplify if possible.", f"= {fl(ans)}"))
    return dedupe_misconceptions({"prompt": prompt + " Give your answer in its simplest form.", "latex": latex,
                                  "answer": fs(ans), "answer_latex": fl(ans), "kind": "fraction",
                                  "steps": steps, "hints": hints, "misconceptions": mcs})


def _signed(n: int) -> str:
    return f"+ {n}" if n >= 0 else f"- {abs(n)}"


def gen_expanding(d: int, rng: random.Random) -> dict:
    if d == 1:
        a, b = rng.randint(2, 9), rng.choice([i for i in range(-9, 10) if i != 0])
        expr = a * (X + b)
        prompt, latex = f"Expand {a}(x {_signed(b)})", f"{a}(x {_signed(b)})"
        steps = [step(f"Multiply the {a} outside by EACH term inside the bracket.",
                      f"{a} \\times x = {a}x, \\quad {a} \\times {b if b > 0 else f'({b})'} = {a*b}"),
                 step("Write the terms together.", sp.latex(sp.expand(expr)))]
        hints = [f"The {a} outside multiplies every term inside the bracket. What is {a} times x?",
                 f"Now do {a} times {b}. Put both answers together."]
        mcs = [mc(a * X + b, "partial_distribution",
                  f"You multiplied the x by {a}, but the second term needs multiplying by {a} too. The number outside multiplies everything inside.")]
    elif d == 2:
        a = rng.choice([-2, -3, -4, -5, 3, 4, 5])
        b, c = rng.randint(2, 5), rng.choice([i for i in range(-7, 8) if i != 0])
        expr = a * (b * X + c)
        prompt, latex = f"Expand {a}({b}x {_signed(c)})", f"{a}({b}x {_signed(c)})"
        steps = [step(f"Multiply {a} by {b}x.", f"{a} \\times {b}x = {a*b}x"),
                 step(f"Multiply {a} by {c}. Watch the signs!", f"{a} \\times {c if c > 0 else f'({c})'} = {a*c}"),
                 step("Combine.", sp.latex(sp.expand(expr)))]
        hints = [f"Multiply {a} by each term. Be careful with the sign of {a}.",
                 "A negative times a negative is positive; a negative times a positive is negative."]
        mcs = [mc(a * b * X - a * c, "sign_error",
                   "Check the sign of your second term. Remember: negative x negative = positive, and negative x positive = negative."),
               mc(a * b * X + c, "partial_distribution",
                  f"The {a} multiplies the second term as well, not just the x term.")]
    else:
        p, q = rng.choice([i for i in range(-6, 8) if i != 0]), rng.choice([i for i in range(-6, 8) if i != 0])
        expr = (X + p) * (X + q)
        prompt, latex = f"Expand and simplify (x {_signed(p)})(x {_signed(q)})", f"(x {_signed(p)})(x {_signed(q)})"
        steps = [step("Multiply each term in the first bracket by each term in the second (First, Outer, Inner, Last).",
                      f"x \\cdot x + {q}x + {p}x + ({p})({q})"),
                 step("Collect the like terms (the x terms).", sp.latex(sp.expand(expr)))]
        hints = ["There are four multiplications. Can you use a grid with x and " + str(p) + " on one side, x and " + str(q) + " on the other?",
                 f"You should get x^2, {q}x, {p}x and {p*q}. Now collect the x terms."]
        mcs = [mc(X**2 + p * q, "missed_middle_terms",
                  "You multiplied the firsts and the lasts, but missed the two middle terms. Each term in the first bracket multiplies each term in the second - that's four multiplications.")]
    ans = sp.expand(expr)
    return dedupe_misconceptions({"prompt": prompt + ".", "latex": latex, "answer": str(ans), "answer_latex": sp.latex(ans),
                                  "kind": "expression", "steps": steps, "hints": hints,
                                  "misconceptions": [dict(m, answer=str(sp.expand(sp.sympify(m["answer"], locals={"x": X})))) for m in mcs]})


def gen_linear_equations(d: int, rng: random.Random) -> dict:
    if d == 1:
        s = rng.randint(1, 12)
        if rng.random() < 0.5:
            a = rng.randint(2, 9)
            b = a * s
            prompt, latex = f"Solve {a}x = {b}", f"{a}x = {b}"
            steps = [step(f"x is multiplied by {a}. Do the inverse: divide both sides by {a}.", f"x = \\frac{{{b}}}{{{a}}} = {s}")]
            hints = [f"What is happening to x? It's being multiplied by {a}. What's the inverse operation?",
                     f"Divide both sides by {a}."]
            mcs = [mc(b - a, "wrong_inverse", f"You subtracted {a}, but x is being multiplied by {a}. The inverse of multiplying is dividing.")]
        else:
            a = rng.randint(2, 15)
            b = s + a
            prompt, latex = f"Solve x + {a} = {b}", f"x + {a} = {b}"
            steps = [step(f"Subtract {a} from both sides to get x on its own.", f"x = {b} - {a} = {s}")]
            hints = [f"What has been added to x? How can you undo that?", f"Take {a} away from both sides."]
            mcs = [mc(b + a, "wrong_inverse", f"You added {a} instead of subtracting it. To undo + {a}, subtract {a} from both sides.")]
    elif d == 2:
        s = rng.randint(-5, 10)
        a, b = rng.randint(2, 7), rng.choice([i for i in range(-12, 13) if i != 0])
        c = a * s + b
        prompt, latex = f"Solve {a}x {_signed(b)} = {c}", f"{a}x {_signed(b)} = {c}"
        steps = [step(f"{'Subtract' if b > 0 else 'Add'} {abs(b)} {'from' if b > 0 else 'to'} both sides.", f"{a}x = {c - b}"),
                 step(f"Divide both sides by {a}.", f"x = \\frac{{{c - b}}}{{{a}}} = {s}")]
        hints = [f"Undo the {_signed(b)} first, so the x term is on its own.",
                 f"After that you should have {a}x = {c - b}. Now divide by {a}."]
        mcs = [mc(Fraction(c + b, a), "inverse_sign",
                  f"Check your first step: to remove {_signed(b)} you need to do the opposite operation to both sides."),
               mc(c - b, "forgot_divide", f"Good start - you got {a}x = {c - b}. But that's {a} lots of x. One more step: divide by {a}.")]
    else:
        s = rng.randint(-4, 9)
        a, c = rng.randint(4, 9), rng.randint(2, 3)
        b = rng.choice([i for i in range(-10, 11) if i != 0])
        dd = a * s + b - c * s
        prompt, latex = f"Solve {a}x {_signed(b)} = {c}x {_signed(dd)}", f"{a}x {_signed(b)} = {c}x {_signed(dd)}"
        steps = [step(f"Subtract {c}x from both sides to collect the x terms on one side.", f"{a - c}x {_signed(b)} = {dd}"),
                 step(f"{'Subtract' if b > 0 else 'Add'} {abs(b)} {'from' if b > 0 else 'to'} both sides.", f"{a - c}x = {dd - b}"),
                 step(f"Divide by {a - c}.", f"x = {s}")]
        hints = [f"Get all the x terms on one side first. What happens if you subtract {c}x from both sides?",
                 f"You should get {a - c}x {_signed(b)} = {dd}. Now solve it like a two-step equation."]
        mcs = [mc(Fraction(dd - b, a + c), "sign_moving_x",
                  f"When you move {c}x to the other side, you subtract it from both sides - so it's {a} - {c}, not {a} + {c}.")]
    return dedupe_misconceptions({"prompt": prompt + ".", "latex": latex, "answer": str(s), "answer_latex": f"x = {s}",
                                  "kind": "solve", "steps": steps, "hints": hints,
                                  "misconceptions": [dict(m, answer=str(m["answer"])) for m in mcs]})


def gen_percentages(d: int, rng: random.Random) -> dict:
    if d == 1:
        p = rng.choice([10, 20, 25, 50, 75])
        amt = rng.choice([20, 40, 60, 80, 120, 200, 360, 400])
        ans = amt * p / 100
        prompt, latex = f"Find {p}% of £{amt}.", f"{p}\\% \\text{{ of }} \\pounds{amt}"
        steps = [step(f"{p}% means {p} out of 100, or {p}/100.", f"\\frac{{{p}}}{{100}} \\times {amt}"),
                 step("Work it out.", f"= \\pounds{num(ans)}")]
        hints = [f"Percent means 'out of 100'. Can you find 10% first by dividing {amt} by 10?",
                 f"{p}% is {p}/100 - multiply {amt} by {p} and divide by 100."]
        mcs = [mc(Fraction(amt, p), "divided_by_percent", f"It looks like you divided £{amt} by {p}. To find {p}%, think of it as {p}/100 of the amount.")]
    elif d == 2:
        p = rng.choice([5, 15, 30, 35, 45, 65, 12])
        amt = rng.choice([40, 60, 80, 120, 240, 300, 360, 500])
        ans = amt * p / 100
        prompt, latex = f"Find {p}% of £{amt}.", f"{p}\\% \\text{{ of }} \\pounds{amt}"
        steps = [step(f"Find 1% by dividing by 100.", f"1\\% = {num(amt / 100)}"),
                 step(f"Multiply by {p} to get {p}%.", f"{p}\\% = {num(amt / 100)} \\times {p} = \\pounds{num(ans)}")]
        hints = [f"Can you split {p}% into easier parts, like 10% and 5%?",
                 f"Find 1% (divide by 100), then multiply by {p}."]
        mcs = [mc(Fraction(amt, p), "divided_by_percent", f"You divided £{amt} by {p}. Remember: {p}% means {p} hundredths of the amount.")]
    else:
        p = rng.choice([5, 10, 15, 20, 25, 30, 12])
        amt = rng.choice([40, 60, 80, 120, 200, 250, 400])
        up = rng.random() < 0.5
        change = amt * p / 100
        ans = amt + change if up else amt - change
        word = "Increase" if up else "Decrease"
        mult = 1 + p / 100 if up else 1 - p / 100
        prompt, latex = f"{word} £{amt} by {p}%.", f"\\text{{{word} }} \\pounds{amt} \\text{{ by }} {p}\\%"
        steps = [step(f"Find {p}% of £{amt}.", f"{p}\\% \\times {amt} = {num(change)}"),
                 step(f"{'Add it to' if up else 'Subtract it from'} the original amount.", f"{amt} {'+' if up else '-'} {num(change)} = \\pounds{num(ans)}"),
                 step(f"Or in one step, use the multiplier {num(mult)}.", f"{amt} \\times {num(mult)} = {num(ans)}")]
        hints = [f"First find {p}% of £{amt}. That's the amount of the change.",
                 f"Now {'add that to' if up else 'take that away from'} the original £{amt}."]
        mcs = [mc(Fraction(str(change)), "change_only",
                  f"You've found {p}% of £{amt} - that's the change. Now {'add it to' if up else 'subtract it from'} the original amount."),
               mc(amt + p if up else amt - p, "percent_as_amount",
                  f"{p}% isn't the same as £{p}. Work out what {p}% of £{amt} is first.")]
    return dedupe_misconceptions({"prompt": prompt, "latex": latex, "answer": str(sp.nsimplify(ans)), "answer_latex": f"\\pounds{num(ans)}",
                                  "kind": "number", "tolerance": 0.005, "steps": steps, "hints": hints,
                                  "misconceptions": [dict(m, answer=str(m["answer"])) for m in mcs]})


TRIPLES = [(3, 4, 5), (6, 8, 10), (5, 12, 13), (8, 15, 17), (9, 12, 15), (12, 16, 20)]


def gen_pythagoras(d: int, rng: random.Random) -> dict:
    if d in (1, 2):
        if d == 1:
            a, b, _ = rng.choice(TRIPLES)
        else:
            a, b = rng.randint(3, 11), rng.randint(4, 12)
        c = sqrt(a * a + b * b)
        ans = round(c, 1) if d == 2 else int(c)
        prompt = f"A right-angled triangle has shorter sides {a} cm and {b} cm. Find the length of the hypotenuse" + (" to 1 decimal place." if d == 2 else ".")
        steps = [step("Use Pythagoras' theorem: the square of the hypotenuse equals the sum of the squares of the other two sides.", "c^2 = a^2 + b^2"),
                 step("Substitute the values.", f"c^2 = {a}^2 + {b}^2 = {a*a} + {b*b} = {a*a + b*b}"),
                 step("Square root to find c.", f"c = \\sqrt{{{a*a + b*b}}} = {num(ans)}" + ("\\text{ cm (1 d.p.)}" if d == 2 else "\\text{ cm}"))]
        hints = ["Which side is the hypotenuse? It's the longest side, opposite the right angle. Write down a^2 + b^2 = c^2.",
                 f"Work out {a}^2 + {b}^2, then find the square root."]
        mcs = [mc(a + b, "added_sides", "It looks like you added the two sides. Pythagoras works with the squares of the sides: square them first, add, then square root."),
               mc(a * a + b * b, "forgot_sqrt", f"Nearly there! You found c^2 = {a*a + b*b}. One more step - take the square root to find c.")]
        visual = {"type": "triangle", "a": f"{a} cm", "b": f"{b} cm", "c": "?", "unknown": "c"}
        latex = f"a = {a},\\ b = {b},\\ c = ?"
    else:
        a, b, c = rng.choice(TRIPLES) if rng.random() < 0.5 else (rng.randint(3, 9), None, rng.randint(11, 16))
        if b is None:
            b = sqrt(c * c - a * a)
        ans = round(b, 1)
        prompt = f"A right-angled triangle has hypotenuse {c} cm and one shorter side {a} cm. Find the other side to 1 decimal place."
        steps = [step("Rearrange Pythagoras for a shorter side: subtract.", "b^2 = c^2 - a^2"),
                 step("Substitute.", f"b^2 = {c}^2 - {a}^2 = {c*c} - {a*a} = {c*c - a*a}"),
                 step("Square root.", f"b = \\sqrt{{{c*c - a*a}}} = {num(ans)}\\text{{ cm}}")]
        hints = ["You know the hypotenuse this time. Should you add or subtract the squares to find a shorter side?",
                 f"Work out {c}^2 - {a}^2, then square root."]
        mcs = [mc(round(sqrt(c * c + a * a), 1), "added_not_subtracted",
                  "You added the squares, but that would give a side longer than the hypotenuse! To find a shorter side, subtract: b^2 = c^2 - a^2."),
               mc(c * c - a * a, "forgot_sqrt", f"Good - you found b^2 = {c*c - a*a}. Now square root it to find b.")]
        visual = {"type": "triangle", "a": f"{a} cm", "b": "?", "c": f"{c} cm", "unknown": "b"}
        latex = f"c = {c},\\ a = {a},\\ b = ?"
    return dedupe_misconceptions({"prompt": prompt, "latex": latex, "answer": str(ans), "answer_latex": f"{num(ans)}\\text{{ cm}}",
                                  "kind": "number", "tolerance": 0.051, "steps": steps, "hints": hints,
                                  "misconceptions": [dict(m, answer=str(m["answer"])) for m in mcs], "visual": visual})


def line_eq(m: int, c: int) -> str:
    mx = "x" if m == 1 else "-x" if m == -1 else f"{m}x"
    return f"y = {mx}" + ("" if c == 0 else f" {_signed(c)}")


def gen_straight_line(d: int, rng: random.Random) -> dict:
    m = rng.choice([-3, -2, -1, 1, 2, 3, 4])
    c = rng.choice([i for i in range(-5, 6) if i != m])
    line = line_eq(m, c)
    if d == 1:
        prompt, latex = f"What is the gradient of the line {line}?", line
        ans, ans_latex, kind = str(m), str(m), "number"
        steps = [step("Compare with y = mx + c. The gradient is m, the number multiplying x.", f"{line} \\Rightarrow m = {m}")]
        hints = ["Lines written as y = mx + c: which letter is the gradient?", "The gradient is the coefficient of x (the number in front of x)."]
        mcs = [mc(c, "confused_m_c", f"That's the y-intercept (c) - where the line crosses the y-axis. The gradient is the number in front of x.")]
        visual = {"type": "graph", "lines": [{"m": m, "c": c, "label": line}], "points": []}
    else:
        x1 = rng.randint(-2, 2)
        x2 = x1 + rng.randint(1, 3)
        y1, y2 = m * x1 + c, m * x2 + c
        visual = {"type": "graph", "lines": [{"m": m, "c": c, "label": line}] if d == 3 else [], "points": [[x1, y1], [x2, y2]]}
        if d == 2:
            prompt, latex = f"Find the gradient of the line through ({x1}, {y1}) and ({x2}, {y2}).", f"({x1}, {y1}) \\text{{ and }} ({x2}, {y2})"
            ans, ans_latex, kind = str(m), str(m), "number"
            steps = [step("Gradient = change in y / change in x (rise over run).", f"m = \\frac{{{y2} - ({y1})}}{{{x2} - ({x1})}} = \\frac{{{y2 - y1}}}{{{x2 - x1}}} = {m}")]
            hints = ["Gradient = rise / run. How far does y change, and how far does x change?",
                     f"Change in y is {y2} - ({y1}); change in x is {x2} - ({x1}). Divide."]
            mcs = [mc(Fraction(x2 - x1, y2 - y1), "inverted_gradient", "You did run over rise. Gradient is change in y divided by change in x - rise over run."),
                   mc(y2 - y1, "forgot_divide_run", f"That's the change in y. Now divide by the change in x ({x2 - x1}).")]
        else:
            prompt, latex = f"Find the equation of the line through ({x1}, {y1}) and ({x2}, {y2}). Write it as y = mx + c.", f"({x1}, {y1}) \\text{{ and }} ({x2}, {y2})"
            ans, ans_latex, kind = str(m * X + c), line, "line"
            steps = [step("Find the gradient m.", f"m = \\frac{{{y2 - y1}}}{{{x2 - x1}}} = {m}"),
                     step(f"Substitute one point into y = {m}x + c to find c.", f"{y1} = {m}({x1}) + c \\Rightarrow c = {c}"),
                     step("Write the equation.", line)]
            hints = ["Start by finding the gradient: change in y / change in x.",
                     f"The gradient is {m}. Now put x = {x1}, y = {y1} into y = {m}x + c and solve for c."]
            mcs = [mc(m * X + y1, "used_y_as_intercept", f"The intercept c is where the line crosses the y-axis (when x = 0), which isn't necessarily {y1}. Substitute a point to find c.")]
    return dedupe_misconceptions({"prompt": prompt, "latex": latex, "answer": ans, "answer_latex": ans_latex, "kind": kind,
                                  "steps": steps, "hints": hints, "visual": visual,
                                  "misconceptions": [dict(mm, answer=str(mm["answer"])) for mm in mcs]})


# ---------------------------------------------------------------- topics

def T(kind, text=None, **kw):
    return {"type": kind, "content": text, **kw}


TOPICS: dict[str, dict] = {
    "fractions-add": {
        "title": "Adding and subtracting fractions", "subject": "Mathematics", "strand": "Number",
        "country": "England", "curriculum": "National Curriculum", "key_stage": "KS3", "year": 7,
        "objectives": ["Add and subtract fractions with the same denominator",
                       "Find a common denominator using the lowest common multiple",
                       "Add and subtract fractions with different denominators and simplify"],
        "prerequisites": [], "levels": ["same denominators", "related denominators", "different denominators"],
        "generator": gen_fractions_add,
        "content": [
            "A fraction has a numerator (top) showing how many parts, and a denominator (bottom) showing how many equal parts the whole is split into.",
            "To add or subtract fractions with the same denominator, add or subtract the numerators and keep the denominator the same. The size of the pieces does not change.",
            "To add or subtract fractions with different denominators, first rewrite them with a common denominator - usually the lowest common multiple (LCM) of the denominators. Multiply the numerator and denominator by the same number.",
            "Always simplify the final answer by dividing numerator and denominator by their highest common factor (HCF).",
            "Common misconception: adding the denominators, e.g. 1/2 + 1/3 = 2/5. This is wrong because 2/5 is smaller than 1/2.",
        ],
        "explanations": [
            [{"say": "A fraction is made of equal pieces. The bottom number - the denominator - tells us how big each piece is. The top number - the numerator - tells us how many pieces we have.",
              "board": [T("math", "\\frac{3}{8} \\leftarrow \\text{3 pieces, each one eighth}"), T("fraction_bars", fractions=[[3, 8]], op="+")]},
             {"say": "We can only add pieces that are the same size. If the denominators match, we just add the numerators and keep the denominator.",
              "board": [T("math", "\\frac{2}{7} + \\frac{3}{7} = \\frac{5}{7}"), T("highlight", "The denominator stays the same!")]},
             {"say": "If the denominators are different, we first make them the same by finding the lowest common multiple. Then we add.",
              "board": [T("math", "\\frac{1}{3} + \\frac{1}{4} = \\frac{4}{12} + \\frac{3}{12} = \\frac{7}{12}"), T("fraction_bars", fractions=[[1, 3], [1, 4]], op="+")]}],
            [{"say": "Let's think about pizza. Half a pizza plus a quarter of a pizza - you can't add halves and quarters directly, but a half is the same as two quarters!",
              "board": [T("math", "\\frac{1}{2} = \\frac{2}{4}"), T("fraction_bars", fractions=[[1, 2], [2, 4]], op="+")]},
             {"say": "So two quarters plus one quarter makes three quarters. Cutting the pizza into same-sized slices is what finding a common denominator means.",
              "board": [T("math", "\\frac{2}{4} + \\frac{1}{4} = \\frac{3}{4}"), T("highlight", "Same-sized slices first, then count them.")]}],
        ],
    },
    "fractions-multiply": {
        "title": "Multiplying and dividing fractions", "subject": "Mathematics", "strand": "Number",
        "country": "England", "curriculum": "National Curriculum", "key_stage": "KS3", "year": 7,
        "objectives": ["Multiply fractions by fractions and integers", "Divide by a fraction using the reciprocal"],
        "prerequisites": ["fractions-add"], "levels": ["fraction x fraction", "fraction x integer", "dividing fractions"],
        "generator": gen_fractions_multiply,
        "content": [
            "To multiply fractions, multiply the numerators together and the denominators together. No common denominator is needed.",
            "To multiply a fraction by a whole number, write the whole number over 1, or simply multiply the numerator by it.",
            "To divide by a fraction, multiply by its reciprocal: Keep the first fraction, Change divide to multiply, Flip the second fraction (KCF).",
            "Common misconception: flipping the first fraction instead of the second when dividing.",
        ],
        "explanations": [
            [{"say": "Multiplying fractions is the easiest operation: multiply straight across, top times top and bottom times bottom.",
              "board": [T("math", "\\frac{2}{3} \\times \\frac{4}{5} = \\frac{2 \\times 4}{3 \\times 5} = \\frac{8}{15}")]},
             {"say": "To divide, we use Keep, Change, Flip. Keep the first fraction, change divide into multiply, and flip the second fraction upside down.",
              "board": [T("math", "\\frac{1}{2} \\div \\frac{3}{4} = \\frac{1}{2} \\times \\frac{4}{3} = \\frac{4}{6} = \\frac{2}{3}"), T("highlight", "Keep - Change - Flip")]}],
            [{"say": "Think of 'times' as 'of'. Half of a third means splitting a third into two pieces - which gives a sixth.",
              "board": [T("math", "\\frac{1}{2} \\text{ of } \\frac{1}{3} = \\frac{1}{6}"), T("fraction_bars", fractions=[[1, 3], [1, 6]], op="x")]},
             {"say": "Dividing asks 'how many of these fit into that?'. How many halves fit into 3? Six! That's the same as 3 times 2.",
              "board": [T("math", "3 \\div \\frac{1}{2} = 3 \\times 2 = 6")]}],
        ],
    },
    "expanding-brackets": {
        "title": "Expanding brackets", "subject": "Mathematics", "strand": "Algebra",
        "country": "England", "curriculum": "National Curriculum", "key_stage": "KS3", "year": 8,
        "objectives": ["Expand a single bracket", "Expand brackets with negative terms", "Expand the product of two binomials"],
        "prerequisites": [], "levels": ["single bracket", "negative terms", "double brackets"],
        "generator": gen_expanding,
        "content": [
            "To expand a single bracket, multiply the term outside by every term inside: a(b + c) = ab + ac.",
            "Take care with signs: a negative multiplied by a negative is positive; a negative multiplied by a positive is negative.",
            "To expand two brackets, multiply each term in the first bracket by each term in the second (FOIL or a grid), then collect like terms: (x + a)(x + b) = x^2 + (a + b)x + ab.",
            "Common misconception: only multiplying the first term inside the bracket, e.g. 3(x + 4) = 3x + 4.",
        ],
        "explanations": [
            [{"say": "Expanding means removing the brackets by multiplying. The number outside multiplies everything inside.",
              "board": [T("math", "3(x + 4) = 3 \\times x + 3 \\times 4 = 3x + 12"), T("highlight", "Outside multiplies EVERY term inside")]},
             {"say": "For two brackets, every term in the first multiplies every term in the second - four multiplications - then we collect like terms.",
              "board": [T("math", "(x + 2)(x + 3) = x^2 + 3x + 2x + 6 = x^2 + 5x + 6")]}],
            [{"say": "Picture it as an area. A rectangle 3 wide and x plus 4 long is made of two parts: 3 times x, and 3 times 4.",
              "board": [T("text", "Grid method:"), T("math", "\\begin{array}{c|cc} \\times & x & +4 \\\\ \\hline 3 & 3x & +12 \\end{array}")]},
             {"say": "The grid works for double brackets too - fill all four boxes, then add them up.",
              "board": [T("math", "\\begin{array}{c|cc} \\times & x & +3 \\\\ \\hline x & x^2 & +3x \\\\ +2 & +2x & +6 \\end{array}")]}],
        ],
    },
    "linear-equations": {
        "title": "Solving linear equations", "subject": "Mathematics", "strand": "Algebra",
        "country": "England", "curriculum": "National Curriculum", "key_stage": "KS3", "year": 8,
        "objectives": ["Solve one-step equations using inverse operations", "Solve two-step equations",
                       "Solve equations with unknowns on both sides"],
        "prerequisites": ["expanding-brackets"], "levels": ["one-step", "two-step", "unknowns on both sides"],
        "generator": gen_linear_equations,
        "content": [
            "An equation is like a balance: whatever you do to one side you must do to the other.",
            "Use inverse operations to undo what has been done to x: the inverse of adding is subtracting; the inverse of multiplying is dividing.",
            "For two-step equations such as 3x + 5 = 20, undo the addition/subtraction first, then the multiplication.",
            "With unknowns on both sides, first collect the x terms on one side by subtracting the smaller x term from both sides.",
            "Check a solution by substituting it back into the original equation.",
        ],
        "explanations": [
            [{"say": "An equation is a balance. To find x, we undo what's been done to it, doing the same thing to both sides.",
              "board": [T("math", "3x + 5 = 20"), T("text", "Undo + 5: subtract 5 from both sides"), T("math", "3x = 15"),
                        T("text", "Undo x 3: divide both sides by 3"), T("math", "x = 5")]},
             {"say": "Always check by substituting back in. 3 times 5 plus 5 is 20 - correct!",
              "board": [T("highlight", "Check: 3(5) + 5 = 20 ✓")]}],
            [{"say": "Think of it as a 'think of a number' puzzle. I think of a number, multiply by 3, add 5, and get 20. Work backwards!",
              "board": [T("math", "x \\xrightarrow{\\times 3} \\square \\xrightarrow{+5} 20"), T("math", "20 \\xrightarrow{-5} 15 \\xrightarrow{\\div 3} 5")]},
             {"say": "Working backwards, we do the opposite operations in reverse order. That gives x equals 5.",
              "board": [T("highlight", "Reverse the steps, use the opposite operations")]}],
        ],
    },
    "percentages": {
        "title": "Percentages of amounts and percentage change", "subject": "Mathematics", "strand": "Ratio, proportion and rates of change",
        "country": "England", "curriculum": "National Curriculum", "key_stage": "KS3", "year": 8,
        "objectives": ["Find simple percentages of amounts", "Find any percentage of an amount", "Increase and decrease by a percentage"],
        "prerequisites": ["fractions-multiply"], "levels": ["simple percentages", "any percentage", "percentage change"],
        "generator": gen_percentages,
        "content": [
            "Per cent means 'out of 100'. 25% = 25/100 = 1/4.",
            "To find 10% divide by 10; to find 1% divide by 100. Build other percentages from these, e.g. 15% = 10% + 5%.",
            "To increase an amount by p%, find p% and add it on, or multiply by the multiplier (1 + p/100).",
            "To decrease by p%, subtract p% of the amount, or multiply by (1 - p/100).",
        ],
        "explanations": [
            [{"say": "Per cent means out of a hundred. A neat trick: 10 percent means divide by 10, and 1 percent means divide by 100.",
              "board": [T("math", "10\\% \\text{ of } 240 = 24"), T("math", "5\\% \\text{ of } 240 = 12"), T("math", "15\\% = 24 + 12 = 36")]},
             {"say": "To increase by a percentage, find the percentage and add it on. To decrease, take it away.",
              "board": [T("math", "\\text{Increase } 80 \\text{ by } 15\\%: 80 + 12 = 92"), T("highlight", "Or multiply: 80 x 1.15 = 92")]}],
            [{"say": "Imagine a bar split into 100 equal parts. 30 percent is 30 of those parts.",
              "board": [T("fraction_bars", fractions=[[3, 10]], op="+"), T("math", "30\\% = \\frac{30}{100} = 0.3")]},
             {"say": "So 30 percent of 60 is 0.3 times 60, which is 18.",
              "board": [T("math", "0.3 \\times 60 = 18")]}],
        ],
    },
    "pythagoras": {
        "title": "Pythagoras' theorem", "subject": "Mathematics", "strand": "Geometry and measures",
        "country": "England", "curriculum": "GCSE (9-1)", "key_stage": "KS4", "year": 9,
        "objectives": ["Identify the hypotenuse", "Find the hypotenuse of a right-angled triangle", "Find a shorter side"],
        "prerequisites": [], "levels": ["integer hypotenuse", "hypotenuse to 1 d.p.", "finding a shorter side"],
        "generator": gen_pythagoras,
        "content": [
            "Pythagoras' theorem applies only to right-angled triangles: a^2 + b^2 = c^2, where c is the hypotenuse.",
            "The hypotenuse is the longest side, opposite the right angle.",
            "To find the hypotenuse: square the two shorter sides, add, then square root.",
            "To find a shorter side: square the hypotenuse, subtract the square of the known shorter side, then square root.",
            "Common misconceptions: adding the sides without squaring; forgetting to take the square root.",
        ],
        "explanations": [
            [{"say": "In a right-angled triangle, the longest side, opposite the right angle, is called the hypotenuse.",
              "board": [T("triangle", a="a", b="b", c="c (hypotenuse)", unknown="c")]},
             {"say": "Pythagoras' theorem says a squared plus b squared equals c squared. For a 3, 4 triangle: 9 plus 16 is 25, and the square root of 25 is 5.",
              "board": [T("math", "a^2 + b^2 = c^2"), T("math", "3^2 + 4^2 = 9 + 16 = 25"), T("math", "c = \\sqrt{25} = 5")]}],
            [{"say": "Imagine a square drawn on each side of the triangle. The two smaller squares together have exactly the same area as the big square on the hypotenuse.",
              "board": [T("math", "\\underbrace{9}_{3^2} + \\underbrace{16}_{4^2} = \\underbrace{25}_{5^2}"), T("highlight", "Areas of the small squares add up to the big square")]}],
        ],
    },
    "straight-line-graphs": {
        "title": "Straight-line graphs (y = mx + c)", "subject": "Mathematics", "strand": "Algebra",
        "country": "England", "curriculum": "GCSE (9-1)", "key_stage": "KS4", "year": 9,
        "objectives": ["Identify gradient and intercept from y = mx + c", "Find the gradient between two points",
                       "Find the equation of a line through two points"],
        "prerequisites": ["linear-equations"], "levels": ["reading m and c", "gradient from two points", "equation from two points"],
        "generator": gen_straight_line,
        "content": [
            "A straight-line graph can be written as y = mx + c, where m is the gradient (steepness) and c is the y-intercept.",
            "Gradient = change in y / change in x (rise over run). Positive gradients slope upwards left to right; negative gradients slope down.",
            "To find the equation through two points: find the gradient, then substitute one point into y = mx + c to find c.",
        ],
        "explanations": [
            [{"say": "Every straight line can be written as y equals m x plus c. m is the gradient - how steep the line is - and c is where it crosses the y-axis.",
              "board": [T("math", "y = mx + c"), T("graph", lines=[{"m": 2, "c": 1, "label": "y = 2x + 1"}], points=[[0, 1]])]},
             {"say": "Gradient is rise over run: how much y goes up for each step of x.",
              "board": [T("math", "m = \\frac{\\text{change in } y}{\\text{change in } x}")]}],
            [{"say": "Think of the line as a staircase. The gradient tells you how tall each step is if every step is one unit across.",
              "board": [T("graph", lines=[{"m": 3, "c": -2, "label": "y = 3x - 2"}], points=[[0, -2], [1, 1], [2, 4]]), T("highlight", "1 across, 3 up: gradient 3")]}],
        ],
    },
}

# Phrased to complete the sentence "You sometimes ..."
MISCONCEPTIONS = {
    "add_across": "add the denominators together",
    "numerators_not_scaled": "change the denominator without changing the numerator",
    "cross_multiplied": "cross-multiply when multiplying fractions",
    "multiplied_both": "multiply the top and bottom by the whole number",
    "forgot_reciprocal": "forget to flip the second fraction when dividing",
    "flipped_first": "flip the first fraction instead of the second",
    "partial_distribution": "only multiply the first term inside the bracket",
    "sign_error": "mix up the signs when multiplying negatives",
    "missed_middle_terms": "miss the middle terms in double brackets",
    "wrong_inverse": "use the wrong inverse operation",
    "inverse_sign": "do the wrong operation when undoing a step",
    "forgot_divide": "stop before dividing to get x on its own",
    "sign_moving_x": "add an x term instead of subtracting it when collecting x terms",
    "divided_by_percent": "divide by the percentage instead of finding hundredths",
    "change_only": "find the change but forget to apply it to the original amount",
    "percent_as_amount": "treat the percentage as an amount of money",
    "added_sides": "add the sides instead of their squares",
    "forgot_sqrt": "forget the final square root",
    "added_not_subtracted": "add the squares when finding a shorter side",
    "confused_m_c": "mix up the gradient and the y-intercept",
    "inverted_gradient": "calculate run over rise instead of rise over run",
    "forgot_divide_run": "forget to divide by the change in x",
    "used_y_as_intercept": "use a point's y-value as the intercept",
}

INPUT_HINTS = {"fraction": "e.g. 3/4", "solve": "e.g. x = 5", "expression": "e.g. 3x + 12",
               "number": "e.g. 12.5", "line": "e.g. y = 2x + 3"}

SUBJECTS = [
    {"id": "maths", "name": "Mathematics", "status": "available", "note": "KS3 & GCSE - Phase 1"},
    {"id": "english", "name": "English", "status": "coming_soon", "note": "Phase 2"},
    {"id": "biology", "name": "Biology", "status": "coming_soon", "note": "Phase 2"},
    {"id": "chemistry", "name": "Chemistry", "status": "coming_soon", "note": "Phase 2"},
    {"id": "physics", "name": "Physics", "status": "coming_soon", "note": "Phase 2"},
]


def topic(topic_id: str) -> dict:
    return TOPICS[topic_id]


def public_topic(topic_id: str) -> dict:
    t = TOPICS[topic_id]
    return {"id": topic_id, **{k: v for k, v in t.items() if k not in ("generator", "explanations", "content")},
            "content_version": CONTENT_VERSION}


def generate_question(topic_id: str, difficulty: int, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    q = TOPICS[topic_id]["generator"](max(1, min(3, difficulty)), rng)
    q.update({"topic": topic_id, "difficulty": difficulty, "seed": seed,
              "content_version": CONTENT_VERSION})
    return q


def retrieve(topic_id: str, query: str, k: int = 3) -> list[dict]:
    """Curriculum retrieval. Lexical scoring over the verified content chunks of
    the topic and its prerequisites (production: pgvector embeddings)."""
    words = {w for w in query.lower().replace("?", " ").split() if len(w) > 2}
    ids = [topic_id] + TOPICS[topic_id]["prerequisites"]
    chunks = []
    for tid in ids:
        for i, text in enumerate(TOPICS[tid]["content"]):
            score = sum(1 for w in words if w in text.lower()) + (0.5 if tid == topic_id else 0)
            chunks.append({"topic": tid, "chunk": i, "text": text, "score": score,
                           "source": CONTENT_SOURCE, "version": CONTENT_VERSION})
    chunks.sort(key=lambda c: -c["score"])
    return chunks[:k]
