"""LLM provider abstraction with streaming.

The tutor engine decides what to say from verified course content; the LLM
phrases answers to learners' free-form questions. Providers implement
`stream(system, messages, user_id, course_id)` yielding text chunks, so
swapping providers needs no changes elsewhere.
"""
import json
import os
import threading
import time
import urllib.request

from . import db

# USD per million tokens (input, output) for cost-per-learner reporting
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}


def _record(provider, model, user_id, course_id, tokens_in, tokens_out, started, cost=0.0):
    db.execute(
        "INSERT INTO llm_usage (user_id, course_id, provider, model, input_tokens, output_tokens, cost_usd, latency_ms, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, course_id, provider, model, tokens_in, tokens_out, cost, int((time.time() - started) * 1000), db.now_iso()))


class OfflineModel:
    """No language model: the tutor answers directly from verified course content."""
    name, model = "offline", "course-content"

    def stream(self, system, messages, user_id=None, course_id=None):
        return iter(())


class OllamaModel:
    """Local open-weight model served by Ollama - no API cost, data stays on the machine."""
    name = "ollama"

    def __init__(self):
        self.url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.model = os.environ.get("TUTOR_MODEL", "llama3.2:3b")
        with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as r:
            models = [m["name"] for m in json.load(r)["models"]]
        if self.model not in models:
            raise RuntimeError(f"model {self.model} not pulled (have: {', '.join(models)})")

    def stream(self, system, messages, user_id=None, course_id=None):
        started = time.time()
        body = json.dumps({
            "model": self.model, "stream": True, "keep_alive": "60m",
            # GPU offload crashes on some Windows drivers; OLLAMA_NUM_GPU=99 enables it where it works
            "options": {"temperature": 0.3, "num_predict": 260, "num_ctx": 3072,
                        "num_gpu": int(os.environ.get("OLLAMA_NUM_GPU", "0"))},
            "messages": [{"role": "system", "content": system}, *messages],
        }).encode()
        req = urllib.request.Request(f"{self.url}/api/chat", data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                for line in r:
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if chunk.get("message", {}).get("content"):
                        yield chunk["message"]["content"]
                    if chunk.get("done"):
                        _record(self.name, self.model, user_id, course_id,
                                chunk.get("prompt_eval_count", 0), chunk.get("eval_count", 0), started)
        except Exception as e:
            print(f"[llm] Ollama call failed, falling back to course content: {e}")


class ClaudeModel:
    """Optional commercial provider (TUTOR_LLM=claude + ANTHROPIC_API_KEY)."""
    name = "claude"

    def __init__(self):
        import anthropic
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(timeout=60, max_retries=1)
        self.model = os.environ.get("TUTOR_MODEL", "claude-opus-5-5")

    def stream(self, system, messages, user_id=None, course_id=None):
        started = time.time()
        try:
            with self.client.beta.messages.stream(
                model=self.model, max_tokens=4000, system=system, messages=messages,
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                output_config={"effort": "low"},
            ) as s:
                yield from s.text_stream
                final = s.get_final_message()
            p_in, p_out = PRICES.get(self.model, (4.0, 20.0))
            u = final.usage
            _record(self.name, self.model, user_id, course_id, u.input_tokens, u.output_tokens, started,
                    u.input_tokens / 1e6 * p_in + u.output_tokens / 1e6 * p_out)
        except (self.anthropic.APIStatusError, self.anthropic.APIConnectionError) as e:
            print(f"[llm] Claude call failed, falling back to course content: {e}")


def _make_model():
    provider = os.environ.get("TUTOR_LLM", "ollama")
    factories = {"ollama": OllamaModel, "claude": ClaudeModel}
    if provider in factories:
        try:
            return factories[provider]()
        except Exception as e:  # server not running, model missing, no credentials...
            print(f"[llm] {provider} unavailable ({e}); tutor will answer from course content only")
    return OfflineModel()


model = _make_model()


def warm_up() -> None:
    """Load the local model into memory so the first learner question is not slow."""
    if isinstance(model, OllamaModel):
        threading.Thread(target=lambda: list(model.stream("Reply OK.", [{"role": "user", "content": "hi"}])), daemon=True).start()


def status() -> dict:
    return {"provider": model.name, "model": model.model}


# def  Payment_Processsing(self, payload: dict, student_id: int | None, lesson_id: int | None) -> dict | None:
#     """Process payment for LLM usage."""
#     # This is a placeholder for payment processing logic.
#     # In a real implementation, you would integrate with a payment gateway here.
#     print(f"[llm] Processing payment for student {student_id}, lesson {lesson_id}, payload: {payload}")
#     return {"status": "success", "message": "Payment processed successfully."}

#     class meta:
#         verbose_name = "Payment Processing"
#         verbose_name_plural = "Payment Processings"
