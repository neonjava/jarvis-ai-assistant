"""
AI Engine — Multi-provider LLM abstraction
Supports: Ollama (local) | OpenAI (cloud)
Features: streaming, memory, tool-calling, context management
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx
from loguru import logger

from config.settings import settings


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class ChatMessage:
    role: str  # system | user | assistant
    content: str
    name: Optional[str] = None


@dataclass
class AIResponse:
    content: str
    model: str
    tokens_used: int = 0
    finish_reason: str = "stop"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


# ── Base Provider ─────────────────────────────────────────────────────────────

class BaseAIProvider(ABC):
    """Abstract base for AI providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        stream: bool = False,
        tools: Optional[list[dict]] = None,
    ) -> AIResponse:
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...


# ── Ollama Provider ───────────────────────────────────────────────────────────

class OllamaProvider(BaseAIProvider):
    """Local Ollama inference provider."""

    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT

    def _client(self) -> httpx.AsyncClient:
        """Create a fresh client per request (safe after fork)."""
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )

    async def is_available(self) -> bool:
        try:
            async with self._client() as client:
                resp = await client.get("/api/tags", timeout=5)
                return resp.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        messages: list[ChatMessage],
        stream: bool = False,
        tools: Optional[list[dict]] = None,
    ) -> AIResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": settings.AI_TEMPERATURE,
                "num_predict": settings.AI_MAX_TOKENS,
            },
        }
        if tools:
            payload["tools"] = tools

        async with self._client() as client:
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        msg = data.get("message", {})
        return AIResponse(
            content=msg.get("content", ""),
            model=data.get("model", self.model),
            tokens_used=data.get("eval_count", 0),
            finish_reason=data.get("done_reason", "stop"),
            tool_calls=msg.get("tool_calls", []),
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {
                "temperature": settings.AI_TEMPERATURE,
                "num_predict": settings.AI_MAX_TOKENS,
            },
        }

        async with self._client() as client:
            async with client.stream("POST", "/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            chunk = data.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue

    async def list_models(self) -> list[str]:
        async with self._client() as client:
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]


# ── OpenAI Provider ───────────────────────────────────────────────────────────

class OpenAIProvider(BaseAIProvider):
    """OpenAI cloud provider."""

    def __init__(self) -> None:
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL
            self._available = True
        except Exception:
            self._available = False

    async def is_available(self) -> bool:
        return bool(settings.OPENAI_API_KEY) and self._available

    async def chat(
        self,
        messages: list[ChatMessage],
        stream: bool = False,
        tools: Optional[list[dict]] = None,
    ) -> AIResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": settings.AI_MAX_TOKENS,
            "temperature": settings.AI_TEMPERATURE,
        }
        if tools:
            kwargs["tools"] = tools

        resp = await self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        return AIResponse(
            content=choice.message.content or "",
            model=resp.model,
            tokens_used=resp.usage.total_tokens if resp.usage else 0,
            finish_reason=choice.finish_reason or "stop",
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[str]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": settings.AI_MAX_TOKENS,
            "temperature": settings.AI_TEMPERATURE,
            "stream": True,
        }

        async with await self._client.chat.completions.create(**kwargs) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content


# ── Conversation Memory ───────────────────────────────────────────────────────

class ConversationMemory:
    """Sliding window conversation context."""

    def __init__(self, max_turns: int = 20) -> None:
        self.max_turns = max_turns
        self._history: list[ChatMessage] = []
        self.system_prompt: str = settings.AI_SYSTEM_PROMPT

    def add(self, role: str, content: str) -> None:
        self._history.append(ChatMessage(role=role, content=content))
        # Keep within window: always keep pairs
        if len(self._history) > self.max_turns * 2:
            self._history = self._history[-(self.max_turns * 2):]

    def get_messages(self, extra_system: str = "") -> list[ChatMessage]:
        system_content = self.system_prompt
        if extra_system:
            system_content += f"\n\n{extra_system}"
        return [ChatMessage(role="system", content=system_content)] + self._history

    def clear(self) -> None:
        self._history.clear()

    def to_dict_list(self) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in self._history]


# ── AI Engine ─────────────────────────────────────────────────────────────────

class AIEngine:
    """
    Main AI engine with automatic provider selection,
    conversation memory, and tool-calling support.
    """

    def __init__(self) -> None:
        self._ollama = OllamaProvider()
        self._openai = OpenAIProvider()
        self._provider: Optional[BaseAIProvider] = None
        self.memory = ConversationMemory(max_turns=settings.MEMORY_MAX_TURNS)
        self._tools: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        """Select best available provider."""
        self._provider = None  # Reset before checking
        if settings.AI_PROVIDER == "ollama":
            if await self._ollama.is_available():
                self._provider = self._ollama
                logger.info(f"✅ AI Engine: Ollama ({settings.OLLAMA_MODEL})")
                return
            logger.warning("Ollama not available, falling back to OpenAI")

        if settings.AI_PROVIDER in ("openai", "auto"):
            if await self._openai.is_available():
                self._provider = self._openai
                logger.info(f"✅ AI Engine: OpenAI ({settings.OPENAI_MODEL})")
                return

        # Last resort: try Ollama even if not preferred
        if await self._ollama.is_available():
            self._provider = self._ollama
            logger.info("✅ AI Engine: Ollama (fallback)")
        else:
            logger.error("❌ No AI provider available!")

    def register_tool(self, tool_schema: dict[str, Any]) -> None:
        """Register a function tool for the LLM to call."""
        self._tools.append(tool_schema)

    async def chat(
        self,
        user_message: str,
        context: str = "",
        stream: bool = False,
    ) -> str:
        """Send a message and get a response."""
        # Always try to get a provider, re-initializing if needed
        if not self._provider:
            await self.initialize()

        # If still no provider, raise a clear error
        if not self._provider:
            return "No AI provider available. Make sure Ollama is running: `ollama serve`"

        self.memory.add("user", user_message)
        messages = self.memory.get_messages(extra_system=context)

        try:
            if stream:
                # Collect stream for now; caller can use stream_chat for true streaming
                response_text = ""
                async for chunk in self._provider.stream_chat(messages, self._tools or None):
                    response_text += chunk
            else:
                response = await self._provider.chat(messages, tools=self._tools or None)
                response_text = response.content

            self.memory.add("assistant", response_text)
            return response_text

        except Exception as e:
            logger.error(f"AI chat error: {e}")
            return f"I encountered an error: {e}"

    async def stream_chat(
        self,
        user_message: str,
        context: str = "",
    ) -> AsyncIterator[str]:
        """Stream chat response token by token."""
        if not self._provider:
            await self.initialize()
            if not self._provider:
                yield "No AI provider available."
                return

        self.memory.add("user", user_message)
        messages = self.memory.get_messages(extra_system=context)

        full_response = ""
        async for chunk in self._provider.stream_chat(messages, self._tools or None):
            full_response += chunk
            yield chunk

        self.memory.add("assistant", full_response)

    def clear_memory(self) -> None:
        self.memory.clear()

    async def get_available_models(self) -> list[str]:
        if isinstance(self._provider, OllamaProvider):
            return await self._ollama.list_models()
        return [settings.OPENAI_MODEL]


# ── Singleton ─────────────────────────────────────────────────────────────────

ai_engine = AIEngine()
