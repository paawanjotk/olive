import logging
from typing import AsyncIterator, List, Dict

from app.core.llm.anthropic_provider import AnthropicProvider
from app.core.llm.gemini_provider import GeminiProvider
from app.core.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Yuno, a helpful, friendly, and knowledgeable AI assistant.
You provide clear, accurate, and thoughtful responses.
You can help with a wide range of tasks including coding, writing, analysis, and general questions.
Be concise but thorough. Use markdown formatting when appropriate."""


class LLMManager:
    def __init__(self):
        self._anthropic = AnthropicProvider()
        self._openai = OpenAIProvider()
        self._gemini = GeminiProvider()

    async def stream_chat(
        self, messages: List[Dict], system: str = ""
    ) -> AsyncIterator[str]:
        """Try Anthropic → OpenAI → Gemini, stopping at first success."""
        if not system:
            system = SYSTEM_PROMPT

        providers = [
            ("Anthropic", self._anthropic),
            ("OpenAI", self._openai),
            ("Gemini", self._gemini),
        ]
        last_error: Exception | None = None
        for name, provider in providers:
            try:
                logger.info("Attempting stream via %s", name)
                async for chunk in provider.stream_chat(messages, system):
                    yield chunk
                logger.info("%s stream completed", name)
                return
            except Exception as e:
                logger.warning("%s failed, trying next provider: %s", name, e)
                last_error = e

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    async def generate_title(self, first_message: str) -> str:
        """Generate a session title, trying all providers in order."""
        for provider in (self._anthropic, self._openai, self._gemini):
            try:
                return await provider.generate_title(first_message)
            except Exception as e:
                logger.warning("%s title generation failed: %s", provider.name, e)
        words = first_message.split()[:4]
        return " ".join(words) if words else "New Chat"


# Singleton instance
llm_manager = LLMManager()
