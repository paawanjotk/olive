"""Pre-built workflow templates. A template defines the agents to create plus a
graph blueprint that wires them together. Cloning instantiates real agents for
the user and produces a runnable workflow.

To add a new template: append an entry to TEMPLATES with its agents and a
build_graph() that returns React Flow {nodes, edges} referencing agent keys.
"""
import uuid
from typing import Callable

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agents import Agent
from app.db.models.workflows import Workflow


def _node(node_id: str, ntype: str, x: int, y: int, label: str,
          agent_key: str | None = None, description: str = "",
          extra: dict | None = None) -> dict:
    data: dict = {"label": label, "description": description}
    if agent_key:
        data["agentKey"] = agent_key
    if extra:
        data.update(extra)
    return {"id": node_id, "type": ntype, "position": {"x": x, "y": y}, "data": data}


def _edge(source: str, target: str) -> dict:
    return {"id": f"{source}->{target}", "source": source, "target": target}


# ── Template 1: Research Report ───────────────────────────────────────────────
# Supervisor delegates between a researcher (web tools) and a writer, looping
# until the report is complete. Demonstrates delegation + feedback loop.

_RESEARCH_AGENTS = {
    "router": {
        "name": "Research Supervisor",
        "role": "supervisor",
        "description": "Coordinates research and writing until a report is ready.",
        "system_prompt": (
            "You are the supervisor of a research team. You MUST follow this exact sequence:\n"
            "1. Route to RESEARCHER first to gather facts.\n"
            "2. After the researcher replies, ALWAYS route to WRITER next — never skip this step.\n"
            "3. After the writer produces the final formatted report, THEN reply 'done'.\n\n"
            "CRITICAL RULES:\n"
            "- Never route to 'end' until the writer has run at least once.\n"
            "- The researcher's bullet-point findings are NOT the final report — the writer must still format them.\n"
            "- If the user asked to save to Notion or any external service, include that instruction when routing to the writer."
        ),
        "tools": [],
        "supervisor": True,
    },
    "researcher": {
        "name": "Researcher",
        "role": "researcher",
        "description": "Gathers facts and sources using web search.",
        "system_prompt": (
            "You are a meticulous researcher. Use web_search to gather current, accurate "
            "facts on the topic. Return concise bullet-point findings with sources. Do not "
            "write prose — just well-organised findings."
        ),
        "tools": ["web_search", "get_datetime"],
        "supervisor": False,
    },
    "writer": {
        "name": "Report Writer",
        "role": "writer",
        "description": "Turns research findings into a polished report.",
        "system_prompt": (
            "You are a sharp report writer. Using the researcher's findings, write a clear, "
            "well-structured report with a short intro, organised sections, and a takeaway. "
            "Do not invent facts beyond the provided findings."
        ),
        "tools": [],
        "supervisor": False,
    },
}


def _research_graph(ids: dict[str, str]) -> dict:
    return {
        "nodes": [
            _node("trigger", "trigger", 0, 120, "Manual / Chat input"),
            _node("router", "supervisor", 260, 120, "Research Supervisor", "router",
                  _RESEARCH_AGENTS["router"]["description"]),
            _node("researcher", "agent", 560, 20, "Researcher", "researcher",
                  _RESEARCH_AGENTS["researcher"]["description"]),
            _node("writer", "agent", 560, 220, "Report Writer", "writer",
                  _RESEARCH_AGENTS["writer"]["description"]),
            _node("end", "end", 860, 120, "End"),
        ],
        "edges": [
            _edge("trigger", "router"),
            _edge("router", "researcher"),
            _edge("router", "writer"),
            _edge("router", "end"),
            _edge("researcher", "router"),
            _edge("writer", "router"),
        ],
    }


# ── Template 2: Support Triage (Telegram-ready) ───────────────────────────────
# Supervisor routes a customer message to the right specialist, then to a human
# checkpoint before the reply is delivered. Demonstrates conditional routing +
# human-in-the-loop + messaging trigger.

_TRIAGE_AGENTS = {
    "triage": {
        "name": "Support Triage",
        "role": "supervisor",
        "description": "Routes each customer message to the right specialist.",
        "system_prompt": (
            "You are a support triage supervisor. Read the customer's message and route it "
            "to exactly one specialist: billing (payments, invoices, refunds), technical "
            "(errors, bugs, how-to), or general (everything else). After a specialist has "
            "drafted a reply, route to approval to have it reviewed before sending."
        ),
        "tools": [],
        "supervisor": True,
    },
    "billing": {
        "name": "Billing Specialist",
        "role": "support",
        "description": "Handles payments, invoices, and refunds.",
        "system_prompt": (
            "You are a billing support specialist. Answer the customer's billing question "
            "clearly and empathetically. Be concise and actionable."
        ),
        "tools": [],
        "supervisor": False,
    },
    "technical": {
        "name": "Technical Specialist",
        "role": "support",
        "description": "Handles errors, bugs, and how-to questions.",
        "system_prompt": (
            "You are a technical support specialist. Diagnose the issue and give clear, "
            "step-by-step guidance. Be concise and practical."
        ),
        "tools": ["web_search"],
        "supervisor": False,
    },
    "general": {
        "name": "General Support",
        "role": "support",
        "description": "Handles general questions and everything else.",
        "system_prompt": (
            "You are a friendly general support agent. Answer the customer's question "
            "helpfully and concisely."
        ),
        "tools": [],
        "supervisor": False,
    },
}


def _triage_graph(ids: dict[str, str]) -> dict:
    return {
        "nodes": [
            _node("trigger", "trigger", 0, 200, "Telegram / Chat input"),
            _node("triage", "supervisor", 260, 200, "Support Triage", "triage",
                  _TRIAGE_AGENTS["triage"]["description"]),
            _node("billing", "agent", 560, 40, "Billing Specialist", "billing",
                  _TRIAGE_AGENTS["billing"]["description"]),
            _node("technical", "agent", 560, 200, "Technical Specialist", "technical",
                  _TRIAGE_AGENTS["technical"]["description"]),
            _node("general", "agent", 560, 360, "General Support", "general",
                  _TRIAGE_AGENTS["general"]["description"]),
            _node("approval", "checkpoint", 860, 200, "Human approval"),
            _node("end", "end", 1100, 200, "End"),
        ],
        "edges": [
            _edge("trigger", "triage"),
            _edge("triage", "billing"),
            _edge("triage", "technical"),
            _edge("triage", "general"),
            _edge("triage", "approval"),
            _edge("billing", "triage"),
            _edge("technical", "triage"),
            _edge("general", "triage"),
            _edge("approval", "end"),
        ],
    }


# ── Template 3: Slack Thread Summarizer ──────────────────────────────────────
# When @mentioned in a Slack thread, summarizes the conversation and replies
# in-thread. Demonstrates Slack integration + supervisor + single-agent flow.

_SLACK_AGENTS = {
    "supervisor": {
        "name": "Thread Supervisor",
        "role": "supervisor",
        "description": "Routes to the summarizer agent.",
        "system_prompt": (
            "You are a workflow supervisor for a Slack assistant. Route the request to "
            "the summarizer. As soon as the summarizer has produced its answer, reply done — "
            "do not loop back for more work."
        ),
        "tools": [],
        "supervisor": True,
    },
    "summarizer": {
        "name": "Thread Summarizer",
        "role": "analyst",
        "description": "Reads a Slack thread and produces a concise summary.",
        "system_prompt": (
            "You summarize Slack conversations. The FULL thread text is given to you "
            "directly in the user message, between '=== THREAD START ===' and "
            "'=== THREAD END ===' markers. It is plain text already provided to you — "
            "you do NOT need to open any URL or access Slack; never claim you cannot "
            "access threads. Read the provided messages and answer the user's request "
            "(e.g. a concise summary, who said what, who introduced themselves, key "
            "decisions, and action items). Use short bullet points and reference people "
            "by the names shown in the thread."
        ),
        "tools": [],
        "supervisor": False,
    },
}


def _slack_summarizer_graph(ids: dict[str, str]) -> dict:
    return {
        "nodes": [
            _node("trigger", "trigger", 0, 120, "Slack @mention"),
            _node("supervisor", "supervisor", 260, 120, "Thread Supervisor", "supervisor",
                  _SLACK_AGENTS["supervisor"]["description"]),
            _node("summarizer", "agent", 560, 120, "Thread Summarizer", "summarizer",
                  _SLACK_AGENTS["summarizer"]["description"]),
            _node("end", "end", 860, 120, "Reply to thread"),
        ],
        "edges": [
            _edge("trigger", "supervisor"),
            _edge("supervisor", "summarizer"),
            _edge("supervisor", "end"),
            _edge("summarizer", "supervisor"),
        ],
    }


# ── Template: Slack Q&A Assistant (deterministic + web search + approval) ─────
# A single capable agent answers questions in Slack (with web search), then a
# REAL human-approval gate posts the draft to the thread and waits for an
# approve/reject reply before the answer is delivered. No supervisor — the path
# is deterministic (trigger → agent → checkpoint → end), so approval ALWAYS runs.

_SLACK_QA_AGENTS = {
    "assistant": {
        "name": "Slack Assistant",
        "role": "assistant",
        "description": "Answers Slack questions, using web search for current facts.",
        "system_prompt": (
            "You are a helpful assistant operating in Slack. Answer the user's question "
            "directly and concisely. Use the web_search tool whenever the question needs "
            "current facts, news, or anything you are not certain about — do not guess. "
            "Format for Slack: short paragraphs, bullet points, and cite sources inline. "
            "Do NOT ask the user for permission to post — a separate approval step handles "
            "that. Just produce the best answer."
        ),
        "tools": ["web_search", "get_datetime"],
        "supervisor": False,
    },
}


def _slack_qa_graph(ids: dict[str, str]) -> dict:
    return {
        "nodes": [
            _node("trigger", "trigger", 0, 120, "Slack @mention"),
            _node("assistant", "agent", 280, 120, "Slack Assistant", "assistant",
                  _SLACK_QA_AGENTS["assistant"]["description"]),
            _node("approval", "checkpoint", 580, 120, "Approve before posting",
                  description="Posts the draft to the Slack thread and waits for an approve/reject reply.",
                  extra={"approval_mode": "slack"}),
            _node("end", "end", 860, 120, "Reply to thread"),
        ],
        "edges": [
            _edge("trigger", "assistant"),
            _edge("assistant", "approval"),
            _edge("approval", "end"),
        ],
        "channel_config": {"slack": {"enabled": False, "channel_id": "", "reply_in_thread": True}},
    }


TEMPLATES: dict[str, dict] = {
    "research_report": {
        "key": "research_report",
        "name": "Research Report",
        "description": "A supervisor coordinates a researcher and a writer to produce a sourced report.",
        "agents": _RESEARCH_AGENTS,
        "build_graph": _research_graph,
    },
    "support_triage": {
        "key": "support_triage",
        "name": "Support Triage",
        "description": "A supervisor routes customer messages to billing/technical/general specialists, with a human approval step. Telegram-ready.",
        "agents": _TRIAGE_AGENTS,
        "build_graph": _triage_graph,
    },
    "slack_thread_summarizer": {
        "key": "slack_thread_summarizer",
        "name": "Slack Thread Summarizer",
        "description": "When @mentioned in a Slack thread, summarizes the conversation and replies in-thread. Bind this workflow to a Slack channel.",
        "agents": _SLACK_AGENTS,
        "build_graph": _slack_summarizer_graph,
    },
    "slack_qa_assistant": {
        "key": "slack_qa_assistant",
        "name": "Slack Q&A Assistant",
        "description": "Answers questions in Slack using web search, then asks for human approval in-thread before posting. Deterministic flow — the approval gate always runs.",
        "agents": _SLACK_QA_AGENTS,
        "build_graph": _slack_qa_graph,
    },
}


def list_templates() -> list[dict]:
    return [
        {
            "key": t["key"],
            "name": t["name"],
            "description": t["description"],
            "agent_count": len(t["agents"]),
            "preview_graph": t["build_graph"]({k: k for k in t["agents"]}),
        }
        for t in TEMPLATES.values()
    ]


async def instantiate_template(db: AsyncSession, key: str, user_id: uuid.UUID) -> Workflow:
    """Create the template's agents for the user and a workflow wiring them.

    Agents are reused if an active agent with the same name and template key
    already exists for this user — prevents duplicates when the same template
    is cloned more than once."""
    template = TEMPLATES.get(key)
    if template is None:
        raise KeyError(key)

    # 1. Create agents, mapping each agent key -> agent id.
    #    Reuse an existing agent if name + template key already match.
    key_to_id: dict[str, str] = {}
    for akey, spec in template["agents"].items():
        existing_result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.user_id == user_id,
                    Agent.name == spec["name"],
                    Agent.is_active.is_(True),
                    Agent.meta["template"].as_string() == key,
                )
            )
        )
        agent = existing_result.scalar_one_or_none()
        if agent is None:
            agent = Agent(
                user_id=user_id,
                name=spec["name"],
                description=spec.get("description", ""),
                role=spec.get("role", "assistant"),
                system_prompt=spec["system_prompt"],
                tools=spec.get("tools", []),
                meta={"template": key, "is_supervisor": spec.get("supervisor", False)},
            )
            db.add(agent)
            await db.flush()  # populate agent.id
        key_to_id[akey] = str(agent.id)

    # 2. Build graph_json, replacing agentKey placeholders with real agent ids.
    graph = template["build_graph"](key_to_id)
    for node in graph["nodes"]:
        akey = node.get("data", {}).pop("agentKey", None)
        if akey and akey in key_to_id:
            node["data"]["agentId"] = key_to_id[akey]

    workflow = Workflow(
        user_id=user_id,
        name=template["name"],
        description=template["description"],
        graph_json=graph,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow
