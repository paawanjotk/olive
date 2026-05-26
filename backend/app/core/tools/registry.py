"""Tool registry — maps Anthropic tool names to async implementations."""

import logging
from typing import Any

from .calculator import calculate
from .datetime_tool import get_datetime
from .web_search import web_search

logger = logging.getLogger(__name__)


def _schema_to_gemini(s: dict):
    """Recursively convert a JSON Schema dict to a google.genai types.Schema."""
    from google.genai import types as gtypes
    type_map = {
        "object": "OBJECT", "string": "STRING", "integer": "INTEGER",
        "number": "NUMBER", "boolean": "BOOLEAN", "array": "ARRAY",
    }
    kwargs: dict = {"type": type_map.get(str(s.get("type", "string")).lower(), "STRING")}
    if "description" in s:
        kwargs["description"] = s["description"]
    if "properties" in s:
        kwargs["properties"] = {k: _schema_to_gemini(v) for k, v in s["properties"].items()}
    if "required" in s:
        kwargs["required"] = s["required"]
    return gtypes.Schema(**kwargs)

# ── Anthropic tool definitions ────────────────────────────────────────────────

ANTHROPIC_TOOL_DEFS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for current information, news, facts, or any topic "
            "that requires up-to-date knowledge beyond your training data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "max_results": {
                    "type": "integer",
                    "description": "Number of results (1-5, default 3)",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculator",
        "description": (
            "Evaluate mathematical expressions. Supports arithmetic, powers, "
            "trig functions (sin, cos, tan), log, sqrt, pi, e, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression, e.g. '2**32', 'sqrt(144)', 'sin(pi/2)'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_datetime",
        "description": "Get the current date and time, optionally in a specific timezone.",
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone, e.g. 'UTC', 'America/New_York', 'Asia/Tokyo'",
                    "default": "UTC",
                }
            },
        },
    },
]

# ── Sync-to-async adapter for calculator and datetime ────────────────────────

async def _run_calculator(expression: str, **_) -> str:
    return calculate(expression)


async def _run_datetime(timezone: str = "UTC", **_) -> str:
    return get_datetime(timezone)


async def _run_web_search(query: str, max_results: int = 3, **_) -> str:
    return await web_search(query, max_results)


TOOL_REGISTRY: dict[str, Any] = {
    "web_search": _run_web_search,
    "calculator": _run_calculator,
    "get_datetime": _run_datetime,
}


def _build_gemini_tools():
    """Convert ANTHROPIC_TOOL_DEFS to a Gemini Tool. Returns None if google-genai not installed."""
    try:
        from google.genai import types as gtypes
        return gtypes.Tool(
            function_declarations=[
                gtypes.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=_schema_to_gemini(t["input_schema"]),
                )
                for t in ANTHROPIC_TOOL_DEFS
            ]
        )
    except ImportError:
        return None


GEMINI_TOOL_DEFS = _build_gemini_tools()


async def execute_tool(name: str, tool_input: dict) -> str:
    """Execute a tool by name with the given input dict. Returns string result or raises on failure."""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        raise ValueError(f"Unknown tool: {name}")
    return await fn(**tool_input)
