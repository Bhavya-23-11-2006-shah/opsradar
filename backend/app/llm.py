"""Provider-agnostic LLM access (gemini | openai | anthropic | none).

The LLM is only ever used to turn already-computed facts into hypotheses and a
recommendation. It never computes or returns numbers that reach a finding.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import httpx

from .config import LLM_API_KEY, LLM_MODEL, LLM_PROVIDER

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = {"gemini", "openai", "anthropic"}
DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-latest",
}
TIMEOUT_SECONDS = 30.0


def extract_json(text: str) -> Optional[dict]:
    """Pull the first JSON object out of a model response (handles code fences)."""
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


class LLMClient:
    """Small synchronous client with graceful degradation to template mode."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.provider = (provider or LLM_PROVIDER or "none").strip().lower()
        self.api_key = (api_key if api_key is not None else LLM_API_KEY) or ""
        self.model = (model if model is not None else LLM_MODEL) or ""

    @property
    def configured(self) -> bool:
        return self.provider in SUPPORTED_PROVIDERS and bool(self.api_key)

    @property
    def mode(self) -> str:
        return "llm" if self.configured else "template"

    @property
    def model_name(self) -> str:
        return self.model or DEFAULT_MODELS.get(self.provider, "")

    def _request(self, system: str, user: str, *, json_mode: bool, max_tokens: int) -> Optional[str]:
        if not self.configured:
            return None
        try:
            if self.provider == "openai":
                payload: dict[str, Any] = {
                    "model": self.model_name,
                    "temperature": 0.2,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                }
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}
                response = httpx.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                    timeout=TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]

            if self.provider == "anthropic":
                response = httpx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "max_tokens": max_tokens,
                        "temperature": 0.2,
                        "system": system,
                        "messages": [{"role": "user", "content": user}],
                    },
                    timeout=TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                blocks = response.json().get("content", [])
                return "".join(block.get("text", "") for block in blocks if block.get("type") == "text")

            if self.provider == "gemini":
                response = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent",
                    params={"key": self.api_key},
                    json={
                        "systemInstruction": {"parts": [{"text": system}]},
                        "contents": [{"role": "user", "parts": [{"text": user}]}],
                        "generationConfig": {
                            "temperature": 0.2,
                            "maxOutputTokens": max_tokens,
                            **({"responseMimeType": "application/json"} if json_mode else {}),
                        },
                    },
                    timeout=TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                candidates = response.json().get("candidates", [])
                if not candidates:
                    return None
                parts = candidates[0].get("content", {}).get("parts", [])
                return "".join(part.get("text", "") for part in parts)
        except Exception as exc:  # noqa: BLE001 - provider failures must degrade
            logger.warning("LLM request failed (%s): %s", self.provider, exc)
        return None

    def complete_text(self, system: str, user: str, *, max_tokens: int = 800) -> Optional[str]:
        return self._request(system, user, json_mode=False, max_tokens=max_tokens)

    def complete_json(self, system: str, user: str, *, max_tokens: int = 900) -> Optional[dict]:
        raw = self._request(system, user, json_mode=True, max_tokens=max_tokens)
        return extract_json(raw or "")


client = LLMClient()
