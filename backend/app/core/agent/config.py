from dataclasses import dataclass, field
from typing import Optional


# Available tool names — the single source of truth used by both the registry
# and the AgentConfig validation.
AVAILABLE_TOOLS = [
    "web_search", "calculator", "get_datetime",
    "slack_list_threads", "slack_get_thread",
]

def _mcp_hint(providers: list[str]) -> str:
    """Generic MCP hint — injected only when at least one provider is enabled."""
    if not providers:
        return ""
    return (
        "---\n\n"
        "# Integrations\n"
        "You may have access to external integration tools (e.g. github__, notion__ prefixed tools). "
        "If such tools are available to you and using them would genuinely help complete the task, use them. "
        "Do not mention or explain the integration to the user — just act."
    )


@dataclass
class AgentConfig:
    """
    Execution contract between the API/service layer and the agent loop.

    Both chat (single-agent via WebSocket) and workflow nodes (multi-agent via
    LangGraph in L2) pass an AgentConfig into run_agent_turn. Neither caller
    needs to know how the loop works internally.
    """
    system_prompt: str
    model: str = "claude-sonnet-4-6"
    provider: str = "anthropic"
    temperature: float = 0.7
    max_tokens: int = 8096
    max_iterations: int = 5
    tools: list[str] = field(default_factory=list)
    soul_md: Optional[str] = None
    memory_md: Optional[str] = None
    name: Optional[str] = None
    # Human-in-the-loop tool approval
    approval_tools: list[str] = field(default_factory=list)  # tool names that need approval
    tool_approval_mode: str = "web"  # "web" | "slack" | "both"
    tool_approval_timeout: int = 120  # seconds before auto-approve on timeout
    # MCP providers enabled for this agent: ["github", "notion"]
    mcp_providers: list[str] = field(default_factory=list)

    @property
    def effective_system_prompt(self) -> str:
        """Merges name header + system_prompt + soul_md + memory_md + MCP hints into the final prompt."""
        parts = []
        if self.name:
            parts.append(f"Your name is {self.name}.")
        parts.append(self.system_prompt)
        if self.soul_md and self.soul_md.strip():
            parts.append(f"---\n\n{self.soul_md}")
        if self.memory_md and self.memory_md.strip():
            parts.append(f"---\n\n# Your memory (durable facts you've saved)\n\n{self.memory_md}")
        if self.mcp_providers:
            parts.append(_mcp_hint(self.mcp_providers))
        return "\n\n".join(parts)

    @classmethod
    def default(cls) -> "AgentConfig":
        """Fallback config used when no agent_id is provided — preserves existing behaviour.
        The default chat agent gets all tools including workflow orchestration tools.
        All MCP providers are included; get_mcp_tool_defs silently skips any that have
        no stored token for the current user."""
        from app.core.llm.manager import SYSTEM_PROMPT
        return cls(
            system_prompt=SYSTEM_PROMPT,
            tools=AVAILABLE_TOOLS + [
                "list_workflows", "run_workflow", "get_workflow_status",
                "pause_execution", "resume_execution", "terminate_execution",
                "slack_list_threads", "slack_get_thread",
            ],
            mcp_providers=[],
        )

    @classmethod
    def from_db(cls, agent) -> "AgentConfig":
        """Build from an ORM Agent row."""
        meta = agent.meta or {}
        return cls(
            name=agent.name,
            system_prompt=agent.system_prompt,
            model=agent.model,
            provider=agent.provider,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            max_iterations=agent.max_iterations,
            tools=agent.tools or [],
            soul_md=agent.soul_md,
            memory_md=getattr(agent, "memory_md", None),
            mcp_providers=meta.get("mcp_providers") or [],
        )
