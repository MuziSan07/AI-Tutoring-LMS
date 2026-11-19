"""Safeguarding and AI output safety checks.

MVP rule-based screen. Production adds a moderation model, human review queue
and the school's Designated Safeguarding Lead escalation route.
"""
import re

CONCERN_PATTERNS = {
    "self_harm": r"\b(kill myself|want to die|hurt myself|self[- ]?harm|cut myself|suicid\w*|end my life)\b",
    "abuse": r"\b(hits? me|hurting me|touch(es|ed)? me|abus\w*|scared to go home|unsafe at home)\b",
    "bullying": r"\b(bull(y|ied|ying)|everyone hates me|they hurt me at school)\b",
}
PERSONAL_DATA = r"(\b\d{5}\s?\d{6}\b|\b0\d{9,10}\b|\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b|\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b)"
INAPPROPRIATE = r"\b(fuck\w*|shit\w*|bitch\w*|cunt\w*|porn\w*|sex\w*)\b"


def screen_student_message(text: str) -> dict | None:
    lowered = text.lower()
    for category, pattern in CONCERN_PATTERNS.items():
        if re.search(pattern, lowered):
            return {
                "category": category, "escalate": True,
                "reply": ("Thank you for telling me. That sounds really hard, and you deserve to feel safe. "
                          "I'm an AI tutor, so the best thing is to talk to a trusted adult - a parent, carer or teacher. "
                          "You can also call Childline free on 0800 1111, any time. If you are in danger right now, call 999. "
                          "I've let your school's safeguarding team know so someone can check in with you."),
            }
    if re.search(PERSONAL_DATA, text, re.IGNORECASE):
        return {"category": "personal_data", "escalate": False,
                "reply": "Just a reminder to keep personal details like phone numbers, emails and addresses private - I don't need them to help you learn. Let's carry on!"}
    if re.search(INAPPROPRIATE, lowered):
        return {"category": "inappropriate_language", "escalate": False,
                "reply": "Let's keep our language kind and respectful. Shall we get back to the maths?"}
    return None


def output_is_safe(text: str) -> bool:
    return not re.search(INAPPROPRIATE, text.lower())


_STOP = set("""about above after again against because before being below between could doesn't during every their there these
those through under until where which while would should really great question let's think check right first second other""".split())


def grounded(text: str, sources: list[str], threshold: float = 0.6) -> bool:
    """Reject LLM answers whose substantive words are mostly absent from the
    verified content it was given - a cheap guard against invented facts."""
    def words(s):
        return {w for w in re.findall(r"[a-z]{5,}", s.lower()) if w not in _STOP}
    said, known = words(text), set().union(*(words(s) for s in sources))
    if not said:
        return True
    stems = {w[:5] for w in known}
    supported = sum(1 for w in said if w in known or w[:5] in stems)
    return supported / len(said) >= threshold


def reveals_answer(text: str, question: dict | None) -> bool:
    """Guard against the LLM giving away the answer during guided practice."""
    if not question:
        return False
    answer = question["answer"].replace("*", "").replace(" ", "")
    compact = text.replace(" ", "").replace("\\", "")
    if len(answer) <= 1:  # single digits appear naturally in explanations
        return f"answeris{answer}" in compact.lower() or f"x={answer}" in compact
    return answer in compact or question.get("answer_latex", "#").replace(" ", "") in compact
