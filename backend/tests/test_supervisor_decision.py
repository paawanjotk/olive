"""Supervisor routing parser — the bit that turns an LLM reply into a routing
decision. Pure logic, no LLM/DB."""
from app.core.workflow.node_runner import _parse_decision

WORKERS = ["researcher", "writer"]


def test_clean_json():
    d = _parse_decision('{"next": "researcher", "reason": "need facts"}', WORKERS)
    assert d["next"] == "researcher"
    assert d["reason"] == "need facts"


def test_json_wrapped_in_prose():
    raw = 'Sure! Here is my decision:\n{"next": "writer", "reason": "ready"}\nThanks.'
    assert _parse_decision(raw, WORKERS)["next"] == "writer"


def test_done_maps_to_end():
    assert _parse_decision('{"next": "done"}', WORKERS)["next"] == "__end__"


def test_unknown_worker_maps_to_end():
    assert _parse_decision('{"next": "nonexistent"}', WORKERS)["next"] == "__end__"


def test_garbage_maps_to_end():
    assert _parse_decision("the model rambled with no json", WORKERS)["next"] == "__end__"
