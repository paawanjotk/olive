from uuid import UUID
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, field_validator


VALID_PROVIDERS = {"anthropic", "gemini", "openai"}


def _is_valid_tool(name: str) -> bool:
    from app.core.tools.registry import TOOL_REGISTRY
    return name in TOOL_REGISTRY or "__" in name


class AgentBase(BaseModel):
    name: str
    description: str = ""
    role: str = "assistant"
    system_prompt: str
    model: str = "claude-sonnet-4-6"
    provider: str = "anthropic"
    temperature: float = 0.7
    max_tokens: int = 8096
    max_iterations: int = 5
    tools: list[str] = []
    soul_md: Optional[str] = None
    memory_md: Optional[str] = None
    guardrails: dict[str, Any] = {}
    # Flexible display metadata — avatar_emoji, avatar_color, tags, etc.
    # Clients can send any JSON-serialisable keys; unknown keys are stored as-is.
    meta: dict[str, Any] = {}

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in VALID_PROVIDERS:
            raise ValueError(f"provider must be one of {VALID_PROVIDERS}")
        return v

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, v: list[str]) -> list[str]:
        invalid = [t for t in v if not _is_valid_tool(t)]
        if invalid:
            raise ValueError(f"unknown tools: {invalid}")
        return list(dict.fromkeys(v))  # deduplicate, preserve order

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        if not 256 <= v <= 32768:
            raise ValueError("max_tokens must be between 256 and 32768")
        return v

    @field_validator("max_iterations")
    @classmethod
    def validate_max_iterations(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError("max_iterations must be between 1 and 20")
        return v


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_iterations: Optional[int] = None
    tools: Optional[list[str]] = None
    soul_md: Optional[str] = None
    memory_md: Optional[str] = None
    guardrails: Optional[dict[str, Any]] = None
    meta: Optional[dict[str, Any]] = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PROVIDERS:
            raise ValueError(f"provider must be one of {VALID_PROVIDERS}")
        return v

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            invalid = [t for t in v if not _is_valid_tool(t)]
            if invalid:
                raise ValueError(f"unknown tools: {invalid}")
            return list(dict.fromkeys(v))
        return v


class AgentTestRequest(BaseModel):
    message: str


class AgentTestResponse(BaseModel):
    response: str
    provider_used: str
    tokens_used: Optional[int] = None


class AgentResponse(AgentBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
