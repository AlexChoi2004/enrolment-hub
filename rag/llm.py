"""The language model behind the answers. The app never depends on one: this adapter hides which one it is.

  ollama  - a model running on this computer (default qwen3:14b through Ollama). Student questions never leave the machine.
  off     - no model: the app still searches and shows the sources, it just does not write an answer.
  fake    - used by the tests to stand in for a model.
The address is fixed by the server's settings; nothing a student types can change where a request goes.
"""
import json
import urllib.request
from urllib.parse import urlparse

TIMEOUT_SECONDS = 90


class LLMError(Exception):
    """The model could not be used (not running, too slow, or an unusable reply)."""


class OllamaClient:
    name = "ollama"

    def __init__(self, url, model, timeout=TIMEOUT_SECONDS):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise LLMError("The model address must be an http or https URL.")
        self.url, self.model, self.timeout = url.rstrip("/"), model, timeout

    def generate(self, system, user):
        body = json.dumps({
            "model": self.model, "stream": False, "think": False,  # a plain answer, without the model's reasoning text
            "options": {"temperature": 0.1, "num_ctx": 4096},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode()
        request = urllib.request.Request(  # noqa: S310 (only http or https, checked in __init__; the address is a server setting)
            self.url + "/api/chat", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 (scheme checked in __init__)
                data = json.loads(response.read().decode())
            return data["message"]["content"]
        except Exception as exc:  # not running, timed out, or an unexpected reply
            raise LLMError(f"The AI model could not be reached ({type(exc).__name__}).") from exc


class FakeLLM:
    """A stand-in model for tests: returns the given reply (or calls it with the prompts) and records every call."""
    name = "fake"

    def __init__(self, reply="Not enough context."):
        self.reply, self.calls = reply, []

    def generate(self, system, user):
        self.calls.append((system, user))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply(system, user) if callable(self.reply) else self.reply


def get_llm(config):
    """The model the app is set up to use, or None when the AI model is switched off."""
    backend = config.get("AI_BACKEND", "ollama")
    if backend == "off":
        return None
    if backend == "ollama":
        return OllamaClient(config.get("OLLAMA_URL", "http://127.0.0.1:11434"), config.get("OLLAMA_MODEL", "qwen3:14b"))
    raise LLMError(f"Unknown AI backend: {backend}")
