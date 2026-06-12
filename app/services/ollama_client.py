"""
Ollama local LLM client with retry logic.
"""
import json
import logging
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.settings import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL

    def is_available(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def best_available_model(self) -> Optional[str]:
        """Return configured model if available, else first available model."""
        models = self.list_models()
        if not models:
            return None
        if self.model in models:
            return self.model
        # Try prefix match
        for m in models:
            if self.model.split(":")[0] in m:
                return m
        return models[0]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ) -> str:
        """Generate text via Ollama /api/generate."""
        model = self.best_available_model()
        if not model:
            raise RuntimeError("No Ollama models available.")

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        r = httpx.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("response", "").strip()

    def generate_json(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        timeout: float = 120.0,
    ) -> dict:
        """Generate and parse JSON response."""
        json_system = (system + "\n\nRespond ONLY with valid JSON. No markdown, no backticks, no explanation.").strip()
        raw = self.generate(prompt, system=json_system, temperature=temperature, timeout=timeout)
        # Strip any accidental markdown fencing
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}\nRaw: {raw[:500]}")
            return {}


ollama_client = OllamaClient()
