import logging
from typing import AsyncIterator, List, Dict, Any

import anthropic

from app.core.llm.base import BaseLLMProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider — pure LLM logic, no tracing concerns."""

    def __init__(self):
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return settings.ANTHROPIC_MODEL

    @property
    def max_tokens(self) -> int:
        return settings.ANTHROPIC_MAX_TOKENS

    async def _do_stream(
        self, messages: List[Dict[str, Any]], system: str = ""
    ) -> AsyncIterator[str]:
        """Stream chat from Anthropic. Sets self._last_usage after completion."""
        client = self._get_client()
        kwargs: Dict[str, Any] = {
            "model": settings.ANTHROPIC_MODEL,
            "max_tokens": settings.ANTHROPIC_MAX_TOKENS,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text

                # Still inside context manager — capture usage for @trace_llm
                try:
                    final = await stream.get_final_message()
                    self._last_usage = (
                        final.usage.input_tokens,
                        final.usage.output_tokens,
                    )
                except Exception:
                    pass  # Usage is optional; trace is still recorded

        except anthropic.APIConnectionError as e:
            logger.error("Anthropic connection error: %s", e)
            raise
        except anthropic.RateLimitError as e:
            logger.error("Anthropic rate limit: %s", e)
            raise
        except anthropic.APIStatusError as e:
            logger.error("Anthropic API error %s: %s", e.status_code, e.message)
            raise
        except Exception as e:
            logger.error("Unexpected Anthropic error: %s", e)
            raise

    async def generate_title(self, first_message: str) -> str:
        client = self._get_client()
        try:
            response = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=32,
                system=(
                    "Generate a very short title (3-5 words) for a chat conversation "
                    "that starts with the given message. Return ONLY the title, no quotes, "
                    "no punctuation at the end, no explanation."
                ),
                messages=[{"role": "user", "content": first_message}],
            )
            title = response.content[0].text.strip().strip('"').strip("'")
            return title[:57] + "..." if len(title) > 60 else title
        except Exception as e:
            logger.error("Anthropic title generation failed: %s", e)
            words = first_message.split()[:4]
            return " ".join(words) if words else "New Chat"
