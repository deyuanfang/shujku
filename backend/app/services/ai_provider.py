"""Multi-Provider AI abstraction layer — Anthropic / OpenAI / DeepSeek / Ollama."""

import json, logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    text: str; model: str; provider: str
    input_tokens: int = 0; output_tokens: int = 0
    error: str = ""


class BaseAIProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(self, messages: list[dict], max_tokens=1000, temperature=0.3, json_mode=False) -> AIResponse: ...
    @abstractmethod
    async def is_available(self) -> bool: ...

    @staticmethod
    def create(provider: str, config: dict) -> "BaseAIProvider":
        api_key = config.get("api_key", "")
        model = config.get("model", "")
        if provider == "anthropic":
            return AnthropicProvider(api_key, model or "claude-sonnet-4-20250514")
        elif provider == "openai":
            return OpenAIProvider(api_key, model or "gpt-4o")
        elif provider == "ollama":
            return OllamaProvider(config.get("base_url", "http://localhost:11434"), model or "llama3")
        elif provider == "deepseek":
            return DeepSeekProvider(api_key, model or "deepseek-chat")
        raise ValueError(f"Unknown provider: {provider}")


# ── Anthropic ────────────────────────────────────

class AnthropicProvider(BaseAIProvider):
    name = "anthropic"
    def __init__(self, api_key="", model="claude-sonnet-4-20250514"):
        self.api_key = api_key; self.model = model; self._client = None

    def _get_client(self):
        if self._client is None and self.api_key:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError: pass
        return self._client

    async def chat(self, messages, max_tokens=1000, temperature=0.3, json_mode=False):
        client = self._get_client()
        if not client: return AIResponse("", self.model, "anthropic", error="No API key")

        system = ""; user_msgs = []
        for m in messages:
            if m["role"] == "system": system = m["content"]
            else: user_msgs.append(m)
        kwargs = dict(model=self.model, max_tokens=max_tokens, messages=user_msgs)
        if system: kwargs["system"] = system
        if json_mode: kwargs["system"] = (system + "\nOutput JSON only.").strip()

        try:
            resp = await client.messages.create(**kwargs)
            text = resp.content[0].text if resp.content else ""
            return AIResponse(text, self.model, "anthropic",
                input_tokens=resp.usage.input_tokens if resp.usage else 0,
                output_tokens=resp.usage.output_tokens if resp.usage else 0)
        except Exception as e:
            logger.error(f"Anthropic error: {e}")
            return AIResponse("", self.model, "anthropic", error=str(e))

    async def is_available(self):
        if not self.api_key: return False
        c = self._get_client()
        if not c: return False
        try:
            resp = await c.messages.create(model=self.model, max_tokens=2, messages=[{"role":"user","content":"hi"}])
            return bool(resp.content)
        except Exception: return False


# ── OpenAI ───────────────────────────────────────

class OpenAIProvider(BaseAIProvider):
    name = "openai"
    def __init__(self, api_key="", model="gpt-4o"):
        self.api_key = api_key; self.model = model; self._client = None

    def _get_client(self):
        if self._client is None and self.api_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError: pass
        return self._client

    async def chat(self, messages, max_tokens=1000, temperature=0.3, json_mode=False):
        c = self._get_client()
        if not c: return AIResponse("", self.model, "openai", error="No API key")
        kwargs = dict(model=self.model, messages=messages, max_tokens=max_tokens, temperature=temperature)
        if json_mode: kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = await c.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content if resp.choices else ""
            return AIResponse(text, self.model, "openai",
                input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                output_tokens=resp.usage.completion_tokens if resp.usage else 0)
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return AIResponse("", self.model, "openai", error=str(e))

    async def is_available(self):
        if not self.api_key: return False
        c = self._get_client()
        if not c: return False
        try:
            import asyncio
            resp = await asyncio.wait_for(
                c.chat.completions.create(
                    model=self.model, max_tokens=2,
                    messages=[{"role":"user","content":"hi"}],
                    timeout=10,
                ),
                timeout=12,
            )
            return bool(resp.choices)
        except Exception as e:
            logger.error(f"DeepSeek/OAI is_available failed: {e}")
            return False


# ── Ollama ───────────────────────────────────────

class OllamaProvider(BaseAIProvider):
    name = "ollama"
    def __init__(self, base_url="http://localhost:11434", model="llama3"):
        self.base_url = base_url.rstrip("/"); self.model = model; self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=120)
            except ImportError: pass
        return self._client

    async def chat(self, messages, max_tokens=1000, temperature=0.3, json_mode=False):
        c = self._get_client()
        if not c: return AIResponse("", self.model, "ollama", error="httpx not installed")
        payload = {"model": self.model, "messages": messages, "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens}}
        if json_mode: payload["format"] = "json"
        try:
            resp = await c.post(f"{self.base_url}/api/chat", json=payload)
            data = resp.json()
            return AIResponse(data.get("message",{}).get("content",""), self.model, "ollama")
        except Exception as e:
            return AIResponse("", self.model, "ollama", error=str(e))

    async def is_available(self):
        try:
            c = self._get_client()
            if not c: return False
            resp = await c.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception: return False


# ── DeepSeek ──────────────────────────────────────

class DeepSeekProvider(OpenAIProvider):
    name = "deepseek"
    def __init__(self, api_key="", model="deepseek-chat"):
        super().__init__(api_key, model)

    def _get_client(self):
        if self._client is None and self.api_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
            except ImportError: pass
        return self._client


# ── Registry ──────────────────────────────────────

PROVIDER_REGISTRY = {
    "anthropic": {"name": "Anthropic Claude", "models": ["claude-sonnet-4-20250514","claude-opus-4-20250514","claude-haiku-4-5-20251001"]},
    "openai": {"name": "OpenAI GPT", "models": ["gpt-4o","gpt-4o-mini","gpt-4-turbo"]},
    "ollama": {"name": "Ollama (本地)", "models": ["llama3","qwen2","mistral"]},
    "deepseek": {"name": "DeepSeek", "models": ["deepseek-chat","deepseek-reasoner"]},
}

_active_provider: Optional[BaseAIProvider] = None

def get_provider() -> Optional[BaseAIProvider]: return _active_provider
def configure_provider(provider: str, config: dict) -> BaseAIProvider:
    global _active_provider
    _active_provider = BaseAIProvider.create(provider, config)
    return _active_provider
def list_providers() -> dict: return PROVIDER_REGISTRY
