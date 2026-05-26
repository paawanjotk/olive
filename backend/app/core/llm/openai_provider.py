import logging
from typing import AsyncIterator, List, Dict, Any

import openai

from app.core.llm.base import BaseLLMProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider — pure LLM logic, no tracing concerns."""

    def __init__(self):
        self._client: openai.AsyncOpenAI | None = None

    def _get_client(self) -> openai.AsyncOpenAI:
        if self._client is None:
            self._client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return settings.OPENAI_MODEL

    @property
    def max_tokens(self) -> int:
        return settings.OPENAI_MAX_TOKENS

    async def _do_stream(
        self, messages: List[Dict[str, Any]], system: str = ""
    ) -> AsyncIterator[str]:
        client = self._get_client()

        all_messages: List[Dict[str, Any]] = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        try:
            stream = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                messages=all_messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                if chunk.usage:
                    self._last_usage = (
                        chunk.usage.prompt_tokens,
                        chunk.usage.completion_tokens,
                    )
        except openai.APIConnectionError as e:
            logger.error("OpenAI connection error: %s", e)
            raise
        except openai.RateLimitError as e:
            logger.error("OpenAI rate limit: %s", e)
            raise
        except openai.APIStatusError as e:
            logger.error("OpenAI API error %s: %s", e.status_code, e.message)
            raise
        except Exception as e:
            logger.error("Unexpected OpenAI error: %s", e)
            raise

    async def generate_title(self, first_message: str) -> str:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                max_tokens=32,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate a very short title (3-5 words) for a chat conversation "
                            "that starts with the given message. Return ONLY the title, no quotes, "
                            "no punctuation at the end, no explanation."
                        ),
                    },
                    {"role": "user", "content": first_message},
                ],
            )
            title = response.choices[0].message.content.strip().strip('"').strip("'")
            return title[:57] + "..." if len(title) > 60 else title
        except Exception as e:
            logger.error("OpenAI title generation failed: %s", e)
            words = first_message.split()[:4]
            return " ".join(words) if words else "New Chat"
