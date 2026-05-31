"""Compiles a stored graph_json blueprint (React Flow shape: nodes with
id/type/data, edges with source/target) into an executable LangGraph StateGraph.

Routing rule — the heart of "the canvas is a possibility space, not a script":
  • edges leaving an AGENT/CHECKPOINT node are deterministic   → add_edge
  • edges leaving a SUPERVISOR node are delegated (LLM-decided) → add_conditional_edges
    keyed on state['next'], with '__end__' always reachable.
"""
import logging
from typing import Callable

from langgraph.graph import StateGraph, START, END

from app.core.workflow.state import WorkflowState

logger = logging.getLogger(__name__)

_TRIGGER_TYPES = {"trigger", "start"}
_END_IDS = {"__end__", "end", "END"}


def _is_end(node_id: str, end_node_ids: set[str]) -> bool:
    return node_id in _END_IDS or node_id in end_node_ids


def build_graph(graph_json: dict, node_fn_map: dict[str, Callable]):
    """node_fn_map maps executable node_id -> async node function (built by the
    executor, which already resolved each node's agent)."""
    nodes = graph_json.get("nodes", [])
    edges = graph_json.get("edges", [])

    by_id = {n["id"]: n for n in nodes}
    node_type = {n["id"]: (n.get("type") or n.get("data", {}).get("kind") or "agent") for n in nodes}
    end_node_ids = {nid for nid, t in node_type.items() if t in ("end",)}
    trigger_ids = {nid for nid, t in node_type.items() if t in _TRIGGER_TYPES}

    builder = StateGraph(WorkflowState)

    # 1. Register executable nodes.
    for nid, fn in node_fn_map.items():
        builder.add_node(nid, fn)

    # 2. Group outgoing edges by source.
    out: dict[str, list[str]] = {}
    for e in edges:
        out.setdefault(e["source"], []).append(e["target"])

    # 3. Entry point: the node a trigger points to (or the first executable node).
    entry = None
    for tid in trigger_ids:
        targets = out.get(tid, [])
        if targets:
            entry = targets[0]
            break
    if entry is None:
        entry = next(iter(node_fn_map), None)
    if entry is not None:
        builder.add_edge(START, entry)

    # 4. Wire edges from each executable node.
    for nid in node_fn_map:
        targets = out.get(nid, [])
        if node_type.get(nid) == "supervisor":
            # Delegated routing: supervisor picks among targets, or ends.
            path_map = {}
            for t in targets:
                path_map[t] = END if _is_end(t, end_node_ids) else t
            path_map["__end__"] = END  # supervisor can always decide it's done

            def _route(state, _allowed=set(path_map.keys())):
                nxt = state.get("next", "__end__")
                return nxt if nxt in _allowed else "__end__"

            builder.add_conditional_edges(nid, _route, path_map)
        else:
            # Deterministic flow.
            if not targets:
                builder.add_edge(nid, END)
            for t in targets:
                builder.add_edge(nid, END if _is_end(t, end_node_ids) else t)

    return builder.compile()
