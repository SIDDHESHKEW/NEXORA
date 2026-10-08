"""Gemini AI Provider implementation supporting dual API keys with automatic failover."""

import json
import logging
from typing import Optional
import httpx
from backend.core.config import settings
from backend.services.providers.base import BaseAIProvider

logger = logging.getLogger("sgsu.ai.gemini")


class GeminiProvider(BaseAIProvider):
    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or settings.AI_MODEL
        self._key1 = settings.GEMINI_API_KEY_1
        self._key2 = settings.GEMINI_API_KEY_2

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    def has_keys(self) -> bool:
        return bool(self._key1 or self._key2)

    async def _call_api_with_key(self, api_key: str, prompt: str, system_prompt: Optional[str], timeout_s: float) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_name}:generateContent?key={api_key}"
        
        contents = []
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nPlease respond in valid JSON only."}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will provide strictly valid JSON matching the requested schema."}]
            })
            
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            }
        }

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates returned from Gemini")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise ValueError("Empty candidate content from Gemini")
            text = parts[0].get("text", "")
            return text.strip()

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, timeout_s: float = 25.0) -> str:
        # Try Key 1 first
        if self._key1:
            try:
                return await self._call_api_with_key(self._key1, prompt, system_prompt, timeout_s)
            except Exception as e:
                logger.warning(f"Gemini Key 1 call failed: {e}. Trying Gemini Key 2...")

        # Failover to Key 2
        if self._key2:
            try:
                return await self._call_api_with_key(self._key2, prompt, system_prompt, timeout_s)
            except Exception as e:
                logger.warning(f"Gemini Key 2 call failed: {e}")

        raise RuntimeError("All configured Gemini API keys failed or were unavailable")
