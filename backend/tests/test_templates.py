"""Prebuilt template blueprints. Validates structure without touching the DB."""
from app.core.workflow.templates import TEMPLATES, list_templates


def test_two_templates_exist():
    keys = {t["key"] for t in list_templates()}
    assert {"research_report", "support_triage"} <= keys


def test_research_report_has_supervisor_loop():
    g = TEMPLATES["research_report"]["build_graph"]({k: k for k in TEMPLATES["research_report"]["agents"]})
    ids = {n["id"] for n in g["nodes"]}
    assert {"trigger", "router", "researcher", "writer", "end"} <= ids
    # supervisor can reach a worker and the worker loops back
    edges = {(e["source"], e["target"]) for e in g["edges"]}
    assert ("router", "researcher") in edges
    assert ("researcher", "router") in edges
    assert ("router", "end") in edges


def test_support_triage_has_checkpoint_and_three_specialists():
    g = TEMPLATES["support_triage"]["build_graph"]({k: k for k in TEMPLATES["support_triage"]["agents"]})
    types = {n["id"]: n["type"] for n in g["nodes"]}
    assert types.get("approval") == "checkpoint"
    for specialist in ("billing", "technical", "general"):
        assert types.get(specialist) == "agent"
    edges = {(e["source"], e["target"]) for e in g["edges"]}
    assert ("triage", "approval") in edges
    assert ("approval", "end") in edges


def test_supervisor_agents_flagged():
    for key in ("research_report", "support_triage"):
        agents = TEMPLATES[key]["agents"]
        assert any(spec.get("supervisor") for spec in agents.values())
