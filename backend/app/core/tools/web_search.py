import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"


async def web_search(query: str, max_results: int = 3) -> str:
    """Search the web using Tavily and return formatted results."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                TAVILY_URL,
                json={
                    "api_key": settings.TAVILY_API_KEY,
                    "query": query,
                    "max_results": min(max_results, 5),
                    "search_depth": "basic",
                    "include_answer": True,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        parts = []
        if data.get("answer"):
            parts.append(f"Summary: {data['answer']}\n")

        for r in data.get("results", [])[:max_results]:
            parts.append(
                f"**{r.get('title', 'Untitled')}**\n"
                f"{r.get('content', '')}\n"
                f"Source: {r.get('url', '')}"
            )

        return "\n\n".join(parts) if parts else "No results found."

    except Exception as e:
        logger.error("Tavily search error: %s", e)
        raise
