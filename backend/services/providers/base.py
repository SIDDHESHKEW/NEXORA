"""Abstract base class for AI model providers."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseAIProvider(ABC):
    @abstractmethod
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, timeout_s: float = 25.0) -> str:
        """Call LLM provider and return raw JSON string response."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass
