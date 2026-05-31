import operator
from typing import Annotated

from typing_extensions import TypedDict


class WorkflowState(TypedDict, total=False):
    """Shared state passed between LangGraph nodes during one execution.

    `messages` is the running transcript (append-reducer so any node can add to
    it). `node_outputs` maps node_id -> latest text output. `next` is the
    supervisor's routing decision, read by the conditional edge. `iterations`
    guards against infinite supervisor loops.
    """

    execution_id: str
    original_input: str
    messages: Annotated[list[dict], operator.add]
    node_outputs: dict[str, str]
    next: str
    iterations: int
