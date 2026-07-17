"""Multi-Provider AI abstraction layer.

Supports: Anthropic Claude, OpenAI GPT, local Ollama models.
All providers expose a unified chat interface.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    text: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0


class BaseAIProvider(ABC):
    """Unified interface for all AI providers."""

    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 1000,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> AIResponse:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...

    @staticmethod
    def create(provider: str, config: dict) -> "BaseAIProvider":
        if provider == "anthropic":
            return AnthropicProvider(config.get("api_key", ""), config.get("model", "claude-sonnet-4-20250514"))
        elif provider == "openai":
            return OpenAIProvider(config.get("api_key", ""), config.get("model", "gpt-4o"))
        elif provider == "ollama":
            return OllamaProvider(config.get("base_url", "http://localhost:11434"), config.get("model", "llama3"))
        elif provider == "deepseek":
            return DeepSeekProvider(config.get("api_key", ""), config.get("model", "deepseek-chat"))
        else:
            raise ValueError(f"Unknown provider: {provider}")


# ── Anthropic ────────────────────────────────────

class AnthropicProvider(BaseAIProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None and self.api_key:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                pass
        return self._client

    async def chat(self, messages, max_tokens=1000, temperature=0.3, json_mode=False):
        client = self._get_client()
        if not client:
            return AIResponse("", self.model, "anthropic", error="No API key configured")

        # Extract system message if present
        system = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_messages.append(m)

        kwargs = dict(model=self.model, max_tokens=max_tokens, messages=user_messages)
        if system:
            kwargs["system"] = system
        if json_mode:
            kwargs["system"] = (system + "\nYou MUST respond with valid JSON only.").strip()

        try:
            resp = await client.messages.create(**kwargs)
            text = resp.content[0].text if resp.content else ""
            return AIResponse(
                text=text, model=self.model, provider="anthropic",
                input_tokens=resp.usage.input_tokens if resp.usage else 0,
                output_tokens=resp.usage.output_tokens if resp.usage else 0,
            )
        except Exception as e:
            logger.error(f"Anthropic error: {e}")
            return AIResponse("", self.model, "anthropic")

    async def is_available(self):
        return bool(self.api_key and self._get_client())


# ── OpenAI ───────────────────────────────────────

class OpenAIProvider(BaseAIProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None and self.api_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                pass
        return self._client

    async def chat(self, messages, max_tokens=1000, temperature=0.3, json_mode=False):
        client = self._get_client()
        if not client:
            return AIResponse("", self.model, "openai")

        kwargs = dict(model=self.model, messages=messages, max_tokens=max_tokens, temperature=temperature)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = await client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content if resp.choices else ""
            return AIResponse(
                text=text, model=self.model, provider="openai",
                input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            )
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return AIResponse("", self.model, "openai")

    async def is_available(self):
        return bool(self.api_key and self._get_client())


# ── Ollama (local) ───────────────────────────────

class OllamaProvider(BaseAIProvider):
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=120)
            except ImportError:
                pass
        return self._client

    async def chat(self, messages, max_tokens=1000, temperature=0.3, json_mode=False):
        client = self._get_client()
        if not client:
            return AIResponse("", self.model, "ollama")

        payload = {
            "model": self.model, "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"

        try:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            return AIResponse(text=text, model=self.model, provider="ollama")
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return AIResponse("", self.model, "ollama")

    async def is_available(self):
        try:
            client = self._get_client()
            if not client:
                return False
            resp = await client.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False


# ── DeepSeek ──────────────────────────────────────

class DeepSeekProvider(OpenAIProvider):
    name = "deepseek"

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        super().__init__(api_key, model)

    def _get_client(self):
        if self._client is None and self.api_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url="https://api.deepseek.com/v1",
                )
            except ImportError:
                pass
        return self._client


# ── Provider Registry ────────────────────────────

PROVIDER_REGISTRY = {
    "anthropic": {"name": "Anthropic Claude", "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-haiku-4-5-20251001"]},
    "openai": {"name": "OpenAI GPT", "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]},
    "ollama": {"name": "Ollama (本地)", "models": ["llama3", "qwen2", "mistral"]},
    "deepseek": {"name": "DeepSeek", "models": ["deepseek-chat", "deepseek-reasoner"]},
}

# Active provider instance
_active_provider: Optional[BaseAIProvider] = None


def get_provider() -> Optional[BaseAIProvider]:
    return _active_provider


def configure_provider(provider: str, config: dict) -> BaseAIProvider:
    global _active_provider
    _active_provider = BaseAIProvider.create(provider, config)
    return _active_provider


def list_providers() -> dict:
    return PROVIDER_REGISTRY
