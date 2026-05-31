from uuid import UUID
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# graph_json is stored/returned as-is (React Flow shape: {nodes:[...], edges:[...]}).
# We keep it as a free dict so the visual builder can evolve node/edge props
# without backend migrations; the executor validates structure at run time.

class WorkflowBase(BaseModel):
    name: str
    description: str = ""
    graph_json: dict[str, Any] = {"nodes": [], "edges": []}


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    graph_json: Optional[dict[str, Any]] = None


class WorkflowResponse(WorkflowBase):
    id: UUID
    user_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExecuteWorkflowRequest(BaseModel):
    input: str
    trigger_type: str = "manual"
    trigger_context: dict[str, Any] = {}


class WorkflowExecutionResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    user_id: UUID
    status: str
    trigger_type: str
    trigger_context: dict[str, Any]
    input_data: dict[str, Any]
    output_data: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionWithWorkflowResponse(WorkflowExecutionResponse):
    workflow_name: str


class WorkflowStepResponse(BaseModel):
    id: UUID
    execution_id: UUID
    node_id: str
    agent_id: Optional[UUID] = None
    status: str
    input: dict[str, Any]
    output: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
