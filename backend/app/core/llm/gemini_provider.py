import asyncio
import logging
from typing import AsyncIterator, List, Dict, Any

from google import genai
from google.genai import types

from app.core.llm.base import BaseLLMProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


def _to_gemini_contents(messages: List[Dict]) -> List[types.Content]:
    """Convert OpenAI-format messages to Gemini Content objects.

    Handles both plain-string content and list-typed content (tool results /
    multi-part blocks) that the Anthropic agent loop produces.
    """
    result = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        content = msg.get("content", "")

        if isinstance(content, str):
            if content:
                result.append(types.Content(role=role, parts=[types.Part(text=content)]))
        elif isinstance(content, list):
            # Flatten tool_result / text blocks to a single text part
            texts: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    texts.append(block.get("text", ""))
                elif btype == "tool_result":
                    # content field may itself be a string or list
                    inner = block.get("content", "")
                    if isinstance(inner, str):
                        texts.append(inner)
                    elif isinstance(inner, list):
                        texts.extend(
                            b.get("text", "") for b in inner
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
            combined = " ".join(t for t in texts if t)
            if combined:
                result.append(types.Content(role=role, parts=[types.Part(text=combined)]))

    return result


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider — pure LLM logic, no tracing concerns."""

    def __init__(self):
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return settings.GEMINI_MODEL

    @property
    def max_tokens(self) -> int:
        return settings.GEMINI_MAX_TOKENS

    async def _do_stream(
        self, messages: List[Dict[str, Any]], system: str = ""
    ) -> AsyncIterator[str]:
        """True async streaming via a queue that bridges the sync Gemini iterator."""
        client = self._get_client()
        contents = _to_gemini_contents(messages)

        config_kwargs: Dict[str, Any] = {"max_output_tokens": settings.GEMINI_MAX_TOKENS}
        if system:
            config_kwargs["system_instruction"] = system
        config = types.GenerateContentConfig(**config_kwargs)

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        usage_holder: list = [None]

        def _sync_stream():
            try:
                for chunk in client.models.generate_content_stream(
                    model=settings.GEMINI_MODEL, contents=contents, config=config
                ):
                    if chunk.text:
                        loop.call_soon_threadsafe(queue.put_nowait, ("text", chunk.text))
                    if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                        usage_holder[0] = chunk.usage_metadata
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", e))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _sync_stream)

        while True:
            item = await queue.get()
            if item is None:
                break
            kind, val = item
            if kind == "error":
                logger.error("Gemini streaming error: %s", val)
                raise val
            yield val  # text chunk

        usage = usage_holder[0]
        if usage and hasattr(usage, "prompt_token_count"):
            self._last_usage = (
                getattr(usage, "prompt_token_count", 0) or 0,
                getattr(usage, "candidates_token_count", 0) or 0,
            )

    async def generate_title(self, first_message: str) -> str:
        client = self._get_client()
        try:
            loop = asyncio.get_running_loop()

            def _sync_generate() -> str:
                config = types.GenerateContentConfig(
                    max_output_tokens=32,
                    system_instruction=(
                        "Generate a very short title (3-5 words) for a chat conversation "
                        "that starts with the given message. Return ONLY the title, no quotes, "
                        "no punctuation at the end, no explanation."
                    ),
                )
                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL, contents=first_message, config=config
                )
                return response.text

            title = await loop.run_in_executor(None, _sync_generate)
            title = title.strip().strip('"').strip("'")
            return title[:57] + "..." if len(title) > 60 else title
        except Exception as e:
            logger.error("Gemini title generation failed: %s", e)
            words = first_message.split()[:4]
            return " ".join(words) if words else "New Chat"
