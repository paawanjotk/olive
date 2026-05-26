from dataclasses import dataclass, field
from typing import Optional


# Available tool names — the single source of truth used by both the registry
# and the AgentConfig validation.
AVAILABLE_TOOLS = ["web_search", "calculator", "get_datetime"]


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
    name: Optional[str] = None

    @property
    def effective_system_prompt(self) -> str:
        """Merges name header + system_prompt + soul_md into the final prompt sent to the LLM."""
        parts = []
        if self.name:
            parts.append(f"Your name is {self.name}.")
        parts.append(self.system_prompt)
        if self.soul_md and self.soul_md.strip():
            parts.append(f"---\n\n{self.soul_md}")
        return "\n\n".join(parts)

    @classmethod
    def default(cls) -> "AgentConfig":
        """Fallback config used when no agent_id is provided — preserves existing behaviour."""
        from app.core.llm.manager import SYSTEM_PROMPT
        return cls(
            system_prompt=SYSTEM_PROMPT,
            tools=AVAILABLE_TOOLS,
        )

    @classmethod
    def from_db(cls, agent) -> "AgentConfig":
        """Build from an ORM Agent row."""
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
        )
