"""Tool registry — maps Anthropic tool names to async implementations."""

import logging
from typing import Any

from .calculator import calculate
from .datetime_tool import get_datetime
from .web_search import web_search
from .workflow_tools import (
    tool_list_workflows, tool_run_workflow, tool_get_workflow_status,
    tool_pause_execution, tool_resume_execution, tool_terminate_execution,
)
from .slack_tools import slack_list_threads, slack_get_thread

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
    {
        "name": "list_workflows",
        "description": "List the user's available workflows. Use this before running a workflow to find the correct workflow_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max workflows to return (default 10)", "default": 10}
            },
        },
    },
    {
        "name": "run_workflow",
        "description": "Trigger a workflow to run asynchronously. Returns an execution_id. Use list_workflows first to find the workflow_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "The workflow UUID to run"},
                "input_text": {"type": "string", "description": "The input/task description to pass to the workflow"},
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "get_workflow_status",
        "description": "Check the status and output of a running or completed workflow execution.",
        "input_schema": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "description": "The execution UUID from run_workflow"},
            },
            "required": ["execution_id"],
        },
    },
    {
        "name": "pause_execution",
        "description": "Pause a running workflow execution. The execution can be resumed later. Use get_workflow_status to confirm the paused state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "description": "The execution UUID to pause"},
            },
            "required": ["execution_id"],
        },
    },
    {
        "name": "resume_execution",
        "description": "Resume a paused workflow execution from where it left off.",
        "input_schema": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "description": "The execution UUID to resume"},
            },
            "required": ["execution_id"],
        },
    },
    {
        "name": "terminate_execution",
        "description": "Immediately stop (terminate) a running or paused workflow execution. This cannot be undone — use pause_execution if you want to resume later.",
        "input_schema": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "description": "The execution UUID to terminate"},
            },
            "required": ["execution_id"],
        },
    },
    {
        "name": "slack_list_threads",
        "description": (
            "List recent parent messages (thread starters) from a Slack channel. "
            "Returns each thread's opening text and reply count so you can decide "
            "which threads to read in full with slack_get_thread. "
            "Use this to explore Slack without loading all content at once."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "description": "Slack channel ID (e.g. C012AB3CD)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of threads to return (1-100, default 20)",
                    "default": 20,
                },
                "oldest": {
                    "type": "string",
                    "description": "Only include messages after this Unix timestamp (e.g. '1716000000')",
                },
                "latest": {
                    "type": "string",
                    "description": "Only include messages before this Unix timestamp",
                },
            },
            "required": ["channel_id"],
        },
    },
    {
        "name": "slack_get_thread",
        "description": (
            "Fetch all messages in a specific Slack thread (parent message + replies). "
            "Use the ts value from slack_list_threads to identify the thread. "
            "Returns formatted conversation text from that thread only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "description": "Slack channel ID containing the thread",
                },
                "thread_ts": {
                    "type": "string",
                    "description": "Timestamp of the thread's parent message (ts from slack_list_threads)",
                },
            },
            "required": ["channel_id", "thread_ts"],
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
    "list_workflows": tool_list_workflows,
    "run_workflow": tool_run_workflow,
    "get_workflow_status": tool_get_workflow_status,
    "pause_execution": tool_pause_execution,
    "resume_execution": tool_resume_execution,
    "terminate_execution": tool_terminate_execution,
    "slack_list_threads": slack_list_threads,
    "slack_get_thread": slack_get_thread,
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
    """Execute a tool by name. Handles both built-in tools and MCP provider tools.

    MCP tool names use double-underscore provider prefix: github__list_repos, notion__search.
    """
    fn = TOOL_REGISTRY.get(name)
    if fn is not None:
        return await fn(**tool_input)

    # MCP tool — delegate to the MCP registry with the current user context
    if "__" in name:
        from app.core.mcp.registry import execute_mcp_tool
        from .workflow_tools import get_tool_user_id
        return await execute_mcp_tool(name, tool_input, get_tool_user_id())

    raise ValueError(f"Unknown tool: {name}")


from .workflow_tools import set_tool_user_id  # noqa: E402 — re-exported for callers

__all__ = [
    "TOOL_REGISTRY", "ANTHROPIC_TOOL_DEFS", "GEMINI_TOOL_DEFS",
    "execute_tool", "set_tool_user_id",
]
