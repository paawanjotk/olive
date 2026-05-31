"""Workflow graph compilation + routing. Uses dummy node functions so it runs
without any LLM or DB — it validates the LangGraph wiring itself."""
import asyncio

from app.core.workflow.graph_builder import build_graph


def _initial():
    return {
        "execution_id": "test", "original_input": "hi",
        "messages": [], "node_outputs": {}, "next": "", "iterations": 0,
    }


def test_deterministic_sequence_runs_in_order():
    graph_json = {
        "nodes": [
            {"id": "trigger", "type": "trigger"},
            {"id": "a", "type": "agent"},
            {"id": "b", "type": "agent"},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"source": "trigger", "target": "a"},
            {"source": "a", "target": "b"},
            {"source": "b", "target": "end"},
        ],
    }

    async def mk(name):
        async def fn(state):
            outs = dict(state.get("node_outputs", {}))
            outs[name] = name.upper()
            return {"node_outputs": outs, "messages": [{"role": "assistant", "content": name}]}
        return fn

    async def run():
        node_fn_map = {"a": await mk("a"), "b": await mk("b")}
        compiled = build_graph(graph_json, node_fn_map)
        return await compiled.ainvoke(_initial())

    final = asyncio.run(run())
    assert final["node_outputs"] == {"a": "A", "b": "B"}
    # both assistant messages accumulated via the add-reducer
    assert [m["content"] for m in final["messages"]] == ["a", "b"]


def test_supervisor_routes_and_loops_until_done():
    graph_json = {
        "nodes": [
            {"id": "trigger", "type": "trigger"},
            {"id": "sup", "type": "supervisor"},
            {"id": "w1", "type": "agent"},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"source": "trigger", "target": "sup"},
            {"source": "sup", "target": "w1"},
            {"source": "sup", "target": "end"},
            {"source": "w1", "target": "sup"},
        ],
    }

    async def sup_fn(state):
        # Route to w1 until it has produced output, then end.
        nxt = "__end__" if "w1" in state.get("node_outputs", {}) else "w1"
        return {"next": nxt, "iterations": state.get("iterations", 0) + 1}

    async def w1_fn(state):
        outs = dict(state.get("node_outputs", {}))
        outs["w1"] = "handled"
        return {"node_outputs": outs}

    async def run():
        compiled = build_graph(graph_json, {"sup": sup_fn, "w1": w1_fn})
        return await compiled.ainvoke(_initial(), {"recursion_limit": 20})

    final = asyncio.run(run())
    assert final["node_outputs"].get("w1") == "handled"
    assert final["next"] == "__end__"
    assert final["iterations"] >= 2  # routed once, then ended
