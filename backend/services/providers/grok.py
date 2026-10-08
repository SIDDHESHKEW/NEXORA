"""Grok (xAI) Provider implementation."""

import json
import logging
from typing import Optional
import httpx
from backend.core.config import settings
from backend.services.providers.base import BaseAIProvider

logger = logging.getLogger("sgsu.ai.grok")


class GrokProvider(BaseAIProvider):
    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or "grok-beta"
        self._key = settings.GROK_API_KEY

    @property
    def provider_name(self) -> str:
        return "grok"

    @property
    def model_name(self) -> str:
        return self._model_name

    def has_keys(self) -> bool:
        return bool(self._key)

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, timeout_s: float = 25.0) -> str:
        if not self._key:
            raise RuntimeError("Grok API key is not configured")

        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": f"{system_prompt}\nReturn JSON strictly."})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model_name,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No choices returned from Grok")
            content = choices[0].get("message", {}).get("content", "")
            return content.strip()
