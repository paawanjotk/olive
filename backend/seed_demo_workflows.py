#!/usr/bin/env python3
"""Seed demo workflow for ayaan.khan2812@gmail.com.

Pipeline: Notion Report Generator
  Manual trigger → Supervisor → Researcher (web) → Plain English Writer → Notion Publisher
  Final output: the Notion URL of the saved report, nothing else.

Run from /backend:
  python seed_demo_workflows.py
"""
import asyncio
import sys
import os

# Make sure app imports resolve from the backend root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.db.models.users import User
from app.db.models.agents import Agent
from app.db.models.workflows import Workflow

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/ollive_chat",
)
TARGET_EMAIL = "ayaan.khan2812@gmail.com"
TEMPLATE_KEY = "notion_report_generator"


# ─────────────────────────────────────────────────────────────────────────────
# Graph helpers
# ─────────────────────────────────────────────────────────────────────────────

def _node(node_id, ntype, x, y, label, agent_id=None, description="", extra=None):
    data = {"label": label, "description": description}
    if agent_id:
        data["agentId"] = agent_id
    if extra:
        data.update(extra)
    return {"id": node_id, "type": ntype, "position": {"x": x, "y": y}, "data": data}


def _edge(src, tgt):
    return {"id": f"{src}->{tgt}", "source": src, "target": tgt}


# ─────────────────────────────────────────────────────────────────────────────
# Agent specs — all prompts are production-quality
# ─────────────────────────────────────────────────────────────────────────────

REPORT_AGENTS = {
    "supervisor": {
        "name": "Report Supervisor",
        "role": "supervisor",
        "description": "Orchestrates the pipeline: research → write → publish to Notion.",
        "supervisor": True,
        "temperature": 0.2,
        "max_tokens": 512,
        "max_iterations": 10,
        "tools": [],
        "system_prompt": (
            "You are the orchestrator of a high-quality report pipeline. "
            "You manage a three-person team — a researcher, a writer, and a publisher — "
            "and your job is to sequence them correctly so the user receives a polished "
            "report saved to Notion.\n\n"

            "STRICT SEQUENCE — follow this in order, never skip:\n"
            "  1. Route to 'researcher' first. Wait for bullet-point findings to come back.\n"
            "  2. Route to 'writer'. The writer turns the findings into a full, plain-language report.\n"
            "  3. Route to 'notion_publisher'. The publisher saves the report and returns a Notion URL.\n"
            "  4. Once the publisher returns a URL, reply 'done' to end the workflow.\n\n"

            "ROUTING RULES:\n"
            "- You may only route to: researcher | writer | notion_publisher | done\n"
            "- Each agent runs exactly ONCE, in the sequence above.\n"
            "- Do NOT re-route to an agent that has already produced output.\n"
            "- Do NOT route to 'done' until the notion_publisher has returned a Notion URL.\n"
            "- The researcher's bullet points are NOT the final report — always send them to the writer.\n"
            "- If you see a Notion URL (starts with https://notion.so or https://www.notion.so), "
            "  that means the publisher is done — immediately reply 'done'.\n\n"

            "Your routing reply must be a SINGLE word: researcher, writer, notion_publisher, or done."
        ),
    },
    "researcher": {
        "name": "Deep Researcher",
        "role": "researcher",
        "description": "Searches the web for current, accurate information on the given topic.",
        "supervisor": False,
        "temperature": 0.3,
        "max_tokens": 4096,
        "max_iterations": 8,
        "tools": ["web_search", "get_datetime"],
        "system_prompt": (
            "You are a meticulous research analyst. Your job is to gather high-quality, "
            "current information on the topic you receive from the supervisor and return "
            "structured findings — NOT prose, NOT conclusions, just well-organised facts.\n\n"

            "HOW TO RESEARCH:\n"
            "1. Identify 2–4 distinct angles of the topic (e.g. what it is, latest news, "
            "   key players, implications, statistics, criticisms).\n"
            "2. Run a web_search for each angle with a precise query.\n"
            "3. Use get_datetime to record when the research was done.\n"
            "4. Cross-check important claims with a second search if they seem surprising.\n\n"

            "OUTPUT FORMAT (markdown, strictly followed):\n"
            "## Research Findings: {topic}\n"
            "**Research conducted:** {date from get_datetime}\n\n"
            "### {Theme 1}\n"
            "- Key fact or data point — source: URL\n"
            "- Key fact or data point — source: URL\n\n"
            "### {Theme 2}\n"
            "- ...\n\n"
            "### Gaps & Uncertainties\n"
            "- Any missing data, conflicting reports, or areas where sources disagree\n\n"

            "RULES:\n"
            "- Bullet points only — no prose paragraphs.\n"
            "- Include a source URL for every factual claim where one is available.\n"
            "- Do NOT write conclusions or recommendations — that is the writer's job.\n"
            "- Aim for 15–30 bullet points total across all themes."
        ),
    },
    "writer": {
        "name": "Plain English Writer",
        "role": "writer",
        "description": "Transforms raw research findings into a clear, engaging report for everyday readers.",
        "supervisor": False,
        "temperature": 0.7,
        "max_tokens": 4096,
        "max_iterations": 3,
        "tools": ["get_datetime"],
        "system_prompt": (
            "You are a world-class writer who makes complex topics accessible to "
            "everyday internet readers. You receive structured research findings "
            "and transform them into a polished, engaging report.\n\n"

            "YOUR WRITING PRINCIPLES:\n"
            "- Write like you're explaining to a smart friend over coffee, not an academic journal.\n"
            "- Short sentences. Active voice. No jargon without a plain-English explanation.\n"
            "- Lead with the most important insight (inverted pyramid).\n"
            "- Every section must answer: 'So what? Why does this matter to me?'\n"
            "- Prefer concrete examples and numbers over vague generalisations.\n"
            "- Vary sentence length for rhythm — mix short punchy lines with longer explanatory ones.\n\n"

            "REPORT STRUCTURE (follow exactly):\n"
            "# {Compelling, specific title — not generic}\n\n"
            "## TL;DR\n"
            "{3–4 sentence executive summary. The key finding in plain English. "
            "A reader who stops here should still understand the main point.}\n\n"
            "## Why This Matters Right Now\n"
            "{Context and urgency — why is this topic relevant today?}\n\n"
            "## What The Research Shows\n"
            "{2–4 subsections (use ### headers) covering the most important findings. "
            "Translate data into human meaning. Cite sources inline as (Source).}\n\n"
            "## The Bigger Picture\n"
            "{Implications, trends, what to watch for, and 2–3 concrete takeaways "
            "the reader can act on or remember.}\n\n"
            "## Sources\n"
            "{Bullet list of all source URLs referenced in the report}\n\n"
            "---\n"
            "*Report generated by Ollive AI · {today's date from get_datetime}*\n\n"

            "RULES:\n"
            "- Keep the full report under 1,200 words.\n"
            "- Never invent facts not present in the research findings.\n"
            "- End with the '---' divider and the generated-by footer — this signals the publisher.\n"
            "- Do NOT add any instructions, notes, or metadata for the publisher — just the report."
        ),
    },
    "notion_publisher": {
        "name": "Notion Publisher",
        "role": "publisher",
        "description": "Saves the finished report to Notion and returns only the page URL.",
        "supervisor": False,
        "temperature": 0.1,
        "max_tokens": 512,
        "max_iterations": 5,
        "tools": ["notion__search", "notion__create_page", "notion__get_page"],
        "mcp_providers": ["notion"],
        "system_prompt": (
            "You are the final step in a report pipeline. Your entire job is to save "
            "a written report to the user's Notion workspace and return the URL. Nothing else.\n\n"

            "STEPS TO FOLLOW:\n"
            "1. Call notion__search with an empty query (query='') to list pages in the workspace.\n"
            "2. Pick the best parent page — prefer pages named 'Reports', 'AI Reports', "
            "   'Research', 'Notes', or 'Inbox'. If none match, use the first result.\n"
            "3. Extract the report title from the '# Title' line at the top of the report.\n"
            "4. Call notion__create_page with:\n"
            "   - parent_page_id = the UUID of the chosen parent page\n"
            "   - title = the report title (without the leading #)\n"
            "   - content = the FULL report text (everything after the title line)\n"
            "5. The tool returns a line like: URL: https://notion.so/...\n"
            "6. Your response = that URL. Just the URL. No other text.\n\n"

            "VALID RESPONSE EXAMPLES:\n"
            "  https://notion.so/abc123\n"
            "  https://www.notion.so/myworkspace/Report-Title-abc123\n\n"

            "INVALID RESPONSES (never do these):\n"
            "  'I have saved the report to Notion. Here is the URL: https://...'\n"
            "  'Done! The page is at https://...'\n"
            "  Any sentence, explanation, or prefix before the URL.\n\n"

            "If notion__search returns no results, call notion__create_page with "
            "parent_page_id set to an empty string — Notion will create it at the workspace root.\n\n"

            "CRITICAL: Your ONLY output is the raw Notion URL. One line. No punctuation after it."
        ),
    },
}


def build_report_graph(ids: dict) -> dict:
    """Build React Flow graph JSON for the Notion Report Generator pipeline."""
    return {
        "nodes": [
            _node("trigger", "trigger", 0, 200,
                  "Manual Trigger",
                  description="Enter a topic or question — the pipeline will research, write, and save to Notion."),
            _node("supervisor", "supervisor", 300, 200,
                  "Report Supervisor", ids["supervisor"],
                  REPORT_AGENTS["supervisor"]["description"]),
            _node("researcher", "agent", 620, 60,
                  "Deep Researcher", ids["researcher"],
                  REPORT_AGENTS["researcher"]["description"]),
            _node("writer", "agent", 620, 200,
                  "Plain English Writer", ids["writer"],
                  REPORT_AGENTS["writer"]["description"]),
            _node("notion_publisher", "agent", 620, 340,
                  "Notion Publisher", ids["notion_publisher"],
                  REPORT_AGENTS["notion_publisher"]["description"]),
            _node("end", "end", 940, 200,
                  "Done — Notion URL",
                  description="The final output is the Notion URL of the saved report."),
        ],
        "edges": [
            _edge("trigger", "supervisor"),
            _edge("supervisor", "researcher"),
            _edge("supervisor", "writer"),
            _edge("supervisor", "notion_publisher"),
            _edge("supervisor", "end"),
            _edge("researcher", "supervisor"),
            _edge("writer", "supervisor"),
            _edge("notion_publisher", "supervisor"),
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Seed logic
# ─────────────────────────────────────────────────────────────────────────────

async def upsert_agent(db: AsyncSession, user_id, akey: str, spec: dict) -> str:
    """Return the agent UUID, creating the agent if it doesn't exist yet."""
    result = await db.execute(
        select(Agent).where(
            Agent.user_id == user_id,
            Agent.name == spec["name"],
            Agent.is_active.is_(True),
            Agent.meta["template"].as_string() == TEMPLATE_KEY,
        )
    )
    agent = result.scalar_one_or_none()

    if agent is not None:
        print(f"  ↩  reused  {spec['name']}")
        return str(agent.id)

    meta: dict = {
        "template": TEMPLATE_KEY,
        "is_supervisor": spec.get("supervisor", False),
    }
    if "mcp_providers" in spec:
        meta["mcp_providers"] = spec["mcp_providers"]

    agent = Agent(
        user_id=user_id,
        name=spec["name"],
        description=spec.get("description", ""),
        role=spec.get("role", "assistant"),
        system_prompt=spec["system_prompt"],
        model="claude-sonnet-4-6",
        provider="anthropic",
        temperature=spec.get("temperature", 0.7),
        max_tokens=spec.get("max_tokens", 8096),
        max_iterations=spec.get("max_iterations", 5),
        tools=spec.get("tools", []),
        guardrails={},
        meta=meta,
    )
    db.add(agent)
    await db.flush()
    print(f"  ✓  created {spec['name']} [{akey}]")
    return str(agent.id)


async def seed():
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession,
                                  expire_on_commit=False, autocommit=False, autoflush=False)

    async with factory() as db:
        # ── Find or create user ──────────────────────────────────────────────
        result = await db.execute(select(User).where(User.email == TARGET_EMAIL))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"User {TARGET_EMAIL!r} not found — creating...")
            user = User(name="Ayaan Khan", email=TARGET_EMAIL)
            db.add(user)
            await db.flush()
            print(f"  Created user {user.id}")
        else:
            print(f"User found: {user.id}  ({user.email})")

        # ── Pipeline: Notion Report Generator ───────────────────────────────
        print("\n── Notion Report Generator ─────────────────────────────────────")
        ids: dict[str, str] = {}
        for akey, spec in REPORT_AGENTS.items():
            ids[akey] = await upsert_agent(db, user.id, akey, spec)

        graph = build_report_graph(ids)

        wf_result = await db.execute(
            select(Workflow).where(
                Workflow.user_id == user.id,
                Workflow.name == "Notion Report Generator",
                Workflow.is_active.is_(True),
            )
        )
        existing = wf_result.scalar_one_or_none()

        if existing is None:
            wf = Workflow(
                user_id=user.id,
                name="Notion Report Generator",
                description=(
                    "Give it any topic and it researches the web, writes a clear plain-English "
                    "report, saves it to Notion, and returns only the Notion page URL."
                ),
                graph_json=graph,
            )
            db.add(wf)
            await db.flush()
            print(f"  ✓  workflow created  {wf.id}")
        else:
            existing.graph_json = graph
            print(f"  ↩  workflow updated  {existing.id}")

        await db.commit()

    await engine.dispose()
    print("\n✅  Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
