"""Content moderation and AI output checks.

MVP rule-based screen. Production adds a moderation model and a human review
queue (the admin Moderation tab is that queue's starting point).
"""
import re

CONCERN_PATTERNS = {
    "self_harm": r"\b(kill myself|want to die|hurt myself|self[- ]?harm|cut myself|suicid\w*|end my life)\b",
    "harassment": r"\b(i('| wi)ll (kill|hurt) (you|him|her|them))\b",
}
PERSONAL_DATA = r"(\b\d{5}\s?\d{6}\b|\b0\d{9,10}\b|\b(?:\d[ -]?){13,16}\b|\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b)"
INAPPROPRIATE = r"\b(fuck\w*|cunt\w*|nigg\w*|fagg\w*)\b"


def screen(text: str) -> dict | None:
    lowered = text.lower()
    if re.search(CONCERN_PATTERNS["self_harm"], lowered):
        return {"category": "wellbeing", "escalate": True,
                "reply": ("I'm really sorry you're feeling this way. I'm an AI study tutor, so I'm not the right support, but you don't have to deal with this alone. "
                          "In the UK you can call Samaritans free on 116 123, any time, or text SHOUT to 85258. If you're in immediate danger, call 999 (or your local emergency number). "
                          "Our support team has been notified so a person can check in.")}
    if re.search(CONCERN_PATTERNS["harassment"], lowered):
        return {"category": "harassment", "escalate": True,
                "reply": "Let's keep things respectful. This message has been passed to the academy's moderation team."}
    if re.search(PERSONAL_DATA, text, re.IGNORECASE):
        return {"category": "personal_data", "escalate": False,
                "reply": "Please don't share personal details like phone numbers, card numbers or addresses here - I don't need them to help you learn."}
    if re.search(INAPPROPRIATE, lowered):
        return {"category": "abusive_language", "escalate": True,
                "reply": "Let's keep the language respectful. Shall we get back to the course?"}
    return None


def output_is_safe(text: str) -> bool:
    return not re.search(INAPPROPRIATE, text.lower())


_STOP = set("""about above after again against because before being below between could doesn't during every their there these
those through under until where which while would should really great question let's think check right first second other
understand means might whether things something example simple simply basically""".split())


def grounded(text: str, sources: list[str], threshold: float = 0.6) -> bool:
    """Reject LLM answers whose substantive words are mostly absent from the
    course content it was given - a cheap guard against invented facts."""
    def words(s):
        return {w for w in re.findall(r"[a-z]{5,}", s.lower()) if w not in _STOP}
    said, known = words(text), set().union(set(), *(words(s) for s in sources))
    if not said:
        return True
    stems = {w[:5] for w in known}
    supported = sum(1 for w in said if w in known or w[:5] in stems)
    return supported / len(said) >= threshold


def leaks_quiz_answer(text: str, open_quiz: list[dict]) -> bool:
    """True if the reply hands over an answer to a quiz the learner hasn't passed."""
    low = text.lower()
    for q in open_quiz:
        answer = q["options"][q["answer"]] if q["type"] == "choice" else q["accept"][0]
        a = answer.lower().strip("`'\"")
        if len(a) >= 2 and re.search(rf"(answer|correct|it's|it is|choose|pick)[^.\n]{{0,40}}{re.escape(a)}", low):
            return True
    return False
