"""
LLM provider abstraction.

Architecture (Template Method + Strategy):

    BaseLLMProvider
    ├── stream_chat()    ← public, traced via @trace_llm, NOT overridable
    └── _do_stream()     ← protected abstract hook — subclasses implement this
                           (pure LLM logic, zero tracing concerns)

Adding a new provider:
    class MyProvider(BaseLLMProvider):
        @property
        def name(self) -> str: return "myprovider"

        @property
        def model(self) -> str: return "my-model-v1"

        async def _do_stream(self, messages, system=""):
            # call your LLM API, yield text chunks
            async for chunk in my_api.stream(...):
                yield chunk.text
            # optionally report token usage:
            self._last_usage = (prompt_tokens, completion_tokens)

        async def generate_title(self, first_message: str) -> str: ...
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any

try:
    from observe_me import trace_llm
except ImportError:
    # observe-me not installed — define a no-op pass-through decorator
    def trace_llm(fn):  # type: ignore[misc]
        return fn


class BaseLLMProvider(ABC):
    """
    Abstract base for all LLM providers.

    Subclasses MUST implement:
        - name  (property)
        - model (property)
        - _do_stream(messages, system) — async generator yielding text chunks
        - generate_title(first_message)

    Subclasses SHOULD set:
        - self._last_usage = (prompt_tokens, completion_tokens)
          inside _do_stream after all chunks have been yielded, so
          @trace_llm can record accurate token counts.
    """

    # Providers set this inside _do_stream to pass token counts to the tracer.
    _last_usage: tuple[int, int] | None = None

    # ------------------------------------------------------------------
    # Abstract interface — subclasses implement these
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. 'anthropic', 'gemini', 'openai'."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier, e.g. 'claude-sonnet-4-6'."""

    @abstractmethod
    async def _do_stream(
        self, messages: List[Dict[str, Any]], system: str = ""
    ) -> AsyncIterator[str]:
        """
        Pure LLM streaming implementation — no tracing here.

        Yield text chunks as they arrive from the provider.
        Optionally set ``self._last_usage = (prompt_tokens, completion_tokens)``
        after the last yield so @trace_llm can record token counts.
        """

    @abstractmethod
    async def generate_title(self, first_message: str) -> str:
        """Generate a short session title from the first user message."""

    # ------------------------------------------------------------------
    # Public interface — the @trace_llm decorator handles all observability
    # ------------------------------------------------------------------

    @trace_llm
    async def stream_chat(
        self, messages: List[Dict[str, Any]], system: str = ""
    ) -> AsyncIterator[str]:
        """
        Traced public streaming interface.

        Do NOT override this in subclasses — implement _do_stream instead.
        @trace_llm automatically instruments timing, tokens, errors, and
        emits telemetry to the observe-me ingestion backend.
        """
        self._last_usage = None
        async for chunk in self._do_stream(messages, system):
            yield chunk
