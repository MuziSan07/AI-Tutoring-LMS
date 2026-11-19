"""LLM provider abstraction.

The teaching engine decides *what* happens pedagogically and supplies verified
facts (marking, hints, worked steps). The LLM only phrases the tutor's turn
and answers free-form questions from retrieved curriculum content. Swapping
providers means adding a class with the same `generate` signature.
"""
import json
import os
import threading
import time
import urllib.request

from . import db

SYSTEM_PROMPT = """You are Nova, an AI maths tutor for school students in England. You are clearly an AI, never claim to be human.

How you teach:
- Speak like a warm, encouraging private tutor. British English spelling and phrasing.
- Match the language to the student's school year. Short sentences. 2-4 sentences per turn unless explaining a method.
- Prefer Socratic questioning: guide the student to the answer, do not hand it over.
- NEVER state the answer to the current practice question unless the action is "show_solution".
- Only use mathematical facts from the provided verified content, engine facts and worked steps. If you are not sure, say so and suggest asking their teacher - never invent facts.
- Praise effort and strategy specifically, not just "well done".
- Stay on the learning topic. Do not ask for personal information.

You receive a JSON object describing the student, the topic, the engine's chosen action, verified facts and a draft reply. Rewrite the draft as your spoken turn, keeping every fact and question in it. For action "answer_question" answer the student's question from the retrieved content, then steer back to the current task.
Whiteboard: optionally add up to 3 extra board items (type "math" with LaTeX, or "text") only when they genuinely help an explanation."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "say": {"type": "string"},
        "board": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"type": {"type": "string", "enum": ["math", "text"]}, "content": {"type": "string"}},
                "required": ["type", "content"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["say", "board"],
    "additionalProperties": False,
}

# USD per million tokens (input, output) for cost-per-student reporting
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}


class OfflineVoice:
    """Deterministic fallback: the engine's verified draft is used verbatim."""
    name, model = "offline", "rule-based"

    def generate(self, payload: dict, student_id: int | None, lesson_id: int | None) -> dict | None:
        return None


class OllamaVoice:
    """Local open-weight model served by Ollama - no API cost, data stays on the machine."""
    name = "ollama"

    def __init__(self):
        self.url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.model = os.environ.get("TUTOR_MODEL", "llama3.2:3b")
        with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as r:
            models = [m["name"] for m in json.load(r)["models"]]
        if self.model not in models:
            raise RuntimeError(f"model {self.model} not pulled (have: {', '.join(models)})")

    def generate(self, payload: dict, student_id: int | None, lesson_id: int | None) -> dict | None:
        started = time.time()
        body = json.dumps({
            "model": self.model, "stream": False, "format": OUTPUT_SCHEMA, "keep_alive": "60m",
            # GPU offload crashes on some Windows drivers; OLLAMA_NUM_GPU=99 enables it where it works
            "options": {"temperature": 0.4, "num_predict": 160, "num_ctx": 2048,
                        "num_gpu": int(os.environ.get("OLLAMA_NUM_GPU", "0"))},
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": json.dumps(payload, default=str)}],
        }).encode()
        req = urllib.request.Request(f"{self.url}/api/chat", data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
            out = json.loads(data["message"]["content"])
        except Exception as e:
            print(f"[llm] Ollama call failed, using verified draft: {e}")
            return None
        db.execute(
            "INSERT INTO llm_usage (student_id, lesson_id, provider, model, input_tokens, output_tokens, cost_usd, latency_ms, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (student_id, lesson_id, self.name, self.model, data.get("prompt_eval_count", 0), data.get("eval_count", 0),
             0.0, int((time.time() - started) * 1000), db.now_iso()))
        return out


class ClaudeVoice:
    """Optional commercial provider (TUTOR_LLM=claude + ANTHROPIC_API_KEY)."""
    name = "claude"

    def __init__(self):
        import anthropic
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(timeout=30, max_retries=1)
        self.model = os.environ.get("TUTOR_MODEL", "claude-opus-5-5")

    def generate(self, payload: dict, student_id: int | None, lesson_id: int | None) -> dict | None:
        started = time.time()
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            )
        except (self.anthropic.APIStatusError, self.anthropic.APIConnectionError) as e:
            print(f"[llm] Claude call failed, using verified draft: {e}")
            return None
        latency = int((time.time() - started) * 1000)
        usage = response.usage
        p_in, p_out = PRICES.get(self.model, (4.0, 20.0))
        cost = usage.input_tokens / 1e6 * p_in + usage.output_tokens / 1e6 * p_out
        db.execute(
            "INSERT INTO llm_usage (student_id, lesson_id, provider, model, input_tokens, output_tokens, cost_usd, latency_ms, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (student_id, lesson_id, self.name, self.model, usage.input_tokens, usage.output_tokens, cost, latency, db.now_iso()))
        if response.stop_reason != "end_turn":
            return None
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None


def _make_voice():
    provider = os.environ.get("TUTOR_LLM", "ollama")
    factories = {"ollama": OllamaVoice, "claude": ClaudeVoice}
    if provider in factories:
        try:
            return factories[provider]()
        except Exception as e:  # server not running, model missing, no credentials...
            print(f"[llm] {provider} unavailable ({e}); running offline tutor voice")
    return OfflineVoice()


voice = _make_voice()

# Turns the LLM may phrase. Marking feedback, hints and worked solutions use the
# verified engine text verbatim unless TUTOR_LLM_REWRITE=all (for larger models).
LLM_ACTIONS = {"answer_question"}
if os.environ.get("TUTOR_LLM_REWRITE") == "all":
    LLM_ACTIONS |= {"greet", "lesson_complete", "feedback_correct", "feedback_incorrect", "diagnostic_feedback", "give_hint"}


def warm_up() -> None:
    """Load the local model into memory so the first student question is not slow."""
    if isinstance(voice, OllamaVoice):
        threading.Thread(target=voice.generate, args=({"action": "warm_up", "draft": "Hello"}, None, None), daemon=True).start()


def status() -> dict:
    return {"provider": voice.name, "model": voice.model}


# def  Payment_Processsing(self, payload: dict, student_id: int | None, lesson_id: int | None) -> dict | None:
#     """Process payment for LLM usage."""
#     # This is a placeholder for payment processing logic.
#     # In a real implementation, you would integrate with a payment gateway here.
#     print(f"[llm] Processing payment for student {student_id}, lesson {lesson_id}, payload: {payload}")
#     return {"status": "success", "message": "Payment processed successfully."}

#     class meta:
#         verbose_name = "Payment Processing"
#         verbose_name_plural = "Payment Processings"


