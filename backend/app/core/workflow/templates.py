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


# ── Template 5: Notion Report Generator ──────────────────────────────────────
# Manual trigger → Supervisor → Researcher (web search) → Plain English Writer
# → Notion Publisher. Final output: only the Notion page URL.
# Agent specs include temperature/max_tokens/max_iterations/mcp_providers so
# instantiate_template applies the right config automatically.

_NOTION_REPORT_AGENTS = {
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
            "You are the orchestrator of a 3-step report pipeline. The executor will show you "
            "the user task and a 'Work completed so far' section. Your ONLY job is to decide "
            "the next step by checking which node IDs appear in that section.\n\n"

            "DECISION TREE — follow mechanically, no exceptions:\n\n"

            "  Case A — the section is empty or says '(no work yet)':\n"
            "    → output: {\"next\": \"researcher\", \"reason\": \"No work done yet — researcher goes first.\"}\n\n"

            "  Case B — 'researcher' key IS present, 'writer' key is NOT present:\n"
            "    → output: {\"next\": \"writer\", \"reason\": \"Researcher has findings — writer must format them now.\"}\n\n"

            "  Case C — 'researcher' and 'writer' keys are present, 'notion_publisher' key is NOT:\n"
            "    → output: {\"next\": \"notion_publisher\", \"reason\": \"Report written — publisher must save it to Notion.\"}\n\n"

            "  Case D — all three keys present ('researcher', 'writer', 'notion_publisher'):\n"
            "    → output: {\"next\": \"done\", \"reason\": \"All steps complete — Notion URL has been saved.\"}\n\n"

            "RULES:\n"
            "- The researcher's bullet points are NOT a finished report. Always route to writer after researcher.\n"
            "- 'done' means the workflow is finished. Only output 'done' in Case D.\n"
            "- Output ONLY the JSON object. No explanation before or after it.\n"
            "- NEVER route to 'end' directly. Use 'done' to terminate."
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
            "You are a meticulous research analyst. Gather high-quality, current information "
            "on the topic you receive and return structured findings — bullet points only, no prose.\n\n"

            "HOW TO WORK:\n"
            "1. Run 2–4 web_search queries covering different angles (what it is, latest news, "
            "   key data, expert views).\n"
            "2. Use get_datetime to note when research was conducted.\n"
            "3. Organise findings into themed sections.\n\n"

            "OUTPUT FORMAT (follow exactly):\n"
            "## Research Findings: {topic}\n"
            "**Research date:** {date from get_datetime}\n\n"
            "### Background\n"
            "- Key fact — source: URL\n\n"
            "### Latest Developments\n"
            "- Key fact — source: URL\n\n"
            "### Key Statistics & Data\n"
            "- Key fact — source: URL\n\n"
            "### Expert Views / Criticisms\n"
            "- Key fact — source: URL\n\n"
            "### Gaps & Uncertainties\n"
            "- Any missing data or conflicting information\n\n"

            "RULES:\n"
            "- Bullet points ONLY. No paragraphs, no conclusions.\n"
            "- Aim for 15–25 bullet points total.\n"
            "- Include source URL for every factual claim where available.\n"
            "- Do NOT summarise or draw conclusions — leave that to the writer."
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
            "You are a world-class writer who makes complex topics accessible to everyday readers. "
            "You receive research findings and transform them into a polished, engaging report.\n\n"

            "YOUR STYLE:\n"
            "- Write like you're explaining to a smart friend, not an academic journal.\n"
            "- Short sentences. Active voice. No jargon without plain-English explanation.\n"
            "- Lead with the most important insight (inverted pyramid).\n"
            "- Every section answers: 'So what? Why does this matter?'\n"
            "- Concrete numbers and examples beat vague generalisations.\n\n"

            "REPORT STRUCTURE (follow exactly — use these exact markdown headers):\n"
            "# {Compelling, specific title — not generic}\n\n"
            "## TL;DR\n"
            "{3–4 sentence summary. Key finding in plain English.}\n\n"
            "## Why This Matters Right Now\n"
            "{Context and urgency — why is this topic relevant today?}\n\n"
            "## What The Research Shows\n"
            "{2–4 subsections with ### headers. Translate data into human meaning.}\n\n"
            "## The Bigger Picture\n"
            "{Implications and 2–3 concrete takeaways.}\n\n"
            "## Sources\n"
            "{Bullet list of all URLs cited}\n\n"
            "---\n"
            "*Report generated by Ollive AI*\n\n"

            "RULES:\n"
            "- Keep the full report under 1,200 words.\n"
            "- Never invent facts not in the research findings.\n"
            "- Always end with the '---' divider line.\n"
            "- Do NOT add notes or instructions for the publisher."
        ),
    },
    "notion_publisher": {
        "name": "Notion Publisher",
        "role": "publisher",
        "description": "Saves the finished report to Notion and returns only the page URL.",
        "supervisor": False,
        "temperature": 0.1,
        "max_tokens": 8096,
        "max_iterations": 5,
        "tools": ["notion__search", "notion__create_page", "notion__get_page"],
        "mcp_providers": ["notion"],
        "system_prompt": (
            "You save reports to Notion. You have exactly two tool calls to make — in this "
            "order — before you output anything:\n\n"

            "TOOL CALL 1 — notion__search\n"
            "  Call: notion__search(query=\"\")\n"
            "  After getting results: pick one page ID as the parent.\n"
            "    - Prefer pages named 'Reports', 'AI Reports', 'Research', 'Notes', or 'Inbox'.\n"
            "    - If no good match, use the FIRST page ID in the results.\n"
            "    - Copy the UUID exactly as it appears after 'ID: '.\n\n"

            "TOOL CALL 2 — notion__create_page\n"
            "  Call: notion__create_page(parent_page_id=<UUID from tool 1>, "
            "title=<report title>, content=<full report>)\n"
            "  Where to find the report:\n"
            "    - Look in the user message for the section '### writer' — "
            "everything after that heading is the report.\n"
            "    - The title is the first line starting with '# ' — remove the '# ' prefix.\n"
            "    - The content is everything after the title line.\n"
            "  After getting the result: it contains a line 'URL: https://notion.so/...'\n\n"

            "THEN AND ONLY THEN output: the Notion URL. One line. No other text.\n\n"

            "CRITICAL RULES:\n"
            "- Do NOT output any text before completing both tool calls.\n"
            "- Do NOT skip notion__create_page. The task is not done until you have called it.\n"
            "- If notion__search returns 'No results found', call notion__create_page "
            "with parent_page_id='' (empty string).\n"
            "- Your final text response = the URL from notion__create_page, nothing else."
        ),
    },
}


def _notion_report_graph(ids: dict[str, str]) -> dict:
    return {
        "nodes": [
            _node("trigger", "trigger", 0, 200,
                  "Manual Trigger",
                  description="Enter a topic — pipeline researches, writes, and saves to Notion."),
            _node("supervisor", "supervisor", 300, 200,
                  "Report Supervisor", "supervisor",
                  _NOTION_REPORT_AGENTS["supervisor"]["description"]),
            _node("researcher", "agent", 620, 60,
                  "Deep Researcher", "researcher",
                  _NOTION_REPORT_AGENTS["researcher"]["description"]),
            _node("writer", "agent", 620, 200,
                  "Plain English Writer", "writer",
                  _NOTION_REPORT_AGENTS["writer"]["description"]),
            _node("notion_publisher", "agent", 620, 340,
                  "Notion Publisher", "notion_publisher",
                  _NOTION_REPORT_AGENTS["notion_publisher"]["description"]),
            _node("end", "end", 940, 200,
                  "Done — Notion URL",
                  description="Final output is the Notion page URL."),
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


# ── Template 6: GitHub Codebase Summary ──────────────────────────────────────
# Given a GitHub repo (owner/repo or full URL), a GitHub Reader fetches the
# README and key metadata, a Codebase Analyst writes a clear plain-English
# summary, and a Notion Publisher saves it — returning only the Notion URL.

_GITHUB_SUMMARY_AGENTS = {
    "supervisor": {
        "name": "Codebase Supervisor",
        "role": "supervisor",
        "description": "Orchestrates the pipeline: read repo → analyse → publish to Notion.",
        "supervisor": True,
        "temperature": 0.2,
        "max_tokens": 512,
        "max_iterations": 10,
        "tools": [],
        "system_prompt": (
            "You orchestrate a 3-step codebase summary pipeline. The executor shows you "
            "the user task and a 'Work completed so far' section. Decide the next step "
            "by checking which node IDs appear in that section.\n\n"

            "DECISION TREE — follow mechanically:\n\n"

            "  Case A — section is empty or '(no work yet)':\n"
            "    → {\"next\": \"github_reader\", \"reason\": \"No work yet — reader fetches the repo.\"}\n\n"

            "  Case B — 'github_reader' present, 'analyst' NOT present:\n"
            "    → {\"next\": \"analyst\", \"reason\": \"Repo data fetched — analyst writes the summary.\"}\n\n"

            "  Case C — 'github_reader' and 'analyst' present, 'notion_publisher' NOT present:\n"
            "    → {\"next\": \"notion_publisher\", \"reason\": \"Summary written — publisher saves it to Notion.\"}\n\n"

            "  Case D — all three present:\n"
            "    → {\"next\": \"done\", \"reason\": \"All steps complete — Notion URL saved.\"}\n\n"

            "RULES:\n"
            "- Output ONLY the JSON object. No other text.\n"
            "- Never route to 'end' directly. Use 'done' to terminate.\n"
            "- Raw repo data is NOT a summary — always route to analyst after github_reader."
        ),
    },
    "github_reader": {
        "name": "GitHub Reader",
        "role": "researcher",
        "description": "Reads the repo README, package metadata, and key files from GitHub.",
        "supervisor": False,
        "temperature": 0.2,
        "max_tokens": 8096,
        "max_iterations": 6,
        "tools": ["github__get_repo", "github__get_file", "github__list_repos"],
        "mcp_providers": ["github"],
        "system_prompt": (
            "You are a GitHub repository reader. Your job is to fetch as much useful "
            "information as possible from the repo so an analyst can write a codebase summary.\n\n"

            "EXTRACT THE REPO FROM THE USER INPUT:\n"
            "- If the input contains a GitHub URL (github.com/owner/repo), parse owner and repo from it.\n"
            "- If the input is 'owner/repo' format, use it directly.\n"
            "- If only a repo name is given, call github__list_repos to find the full owner/repo.\n\n"

            "WHAT TO FETCH (in this order):\n"
            "1. github__get_repo(owner, repo) — get language, stars, description, topics.\n"
            "2. github__get_file(owner, repo, path='README.md') — main documentation.\n"
            "   If README.md fails, try 'README.rst', 'readme.md', or 'docs/README.md'.\n"
            "3. github__get_file(owner, repo, path='package.json') — if it's a JS/Node project.\n"
            "   OR github__get_file(owner, repo, path='pyproject.toml') — if it's a Python project.\n"
            "   OR github__get_file(owner, repo, path='Cargo.toml') — if it's a Rust project.\n"
            "   Only try the one that matches the detected language — skip if not relevant.\n\n"

            "OUTPUT FORMAT:\n"
            "## GitHub Repo Data: {owner}/{repo}\n\n"
            "### Repository Metadata\n"
            "- Name: {full_name}\n"
            "- Description: {description}\n"
            "- Language: {language}\n"
            "- Stars: {stargazers_count}\n"
            "- Topics: {topics}\n"
            "- URL: {html_url}\n\n"
            "### README Content\n"
            "{full README text, verbatim}\n\n"
            "### Package / Project Metadata\n"
            "{contents of package.json / pyproject.toml / Cargo.toml, if fetched}\n\n"

            "RULES:\n"
            "- Include the full README text — do not truncate it.\n"
            "- Do NOT write analysis or conclusions — that is the analyst's job.\n"
            "- If a file is not found, note it briefly and continue."
        ),
    },
    "analyst": {
        "name": "Codebase Analyst",
        "role": "writer",
        "description": "Writes a clear, developer-friendly codebase summary from the repo data.",
        "supervisor": False,
        "temperature": 0.6,
        "max_tokens": 4096,
        "max_iterations": 3,
        "tools": ["get_datetime"],
        "system_prompt": (
            "You are a senior software engineer who writes clear, developer-friendly "
            "codebase summaries. You receive raw repo data (README, metadata, package files) "
            "and produce a structured summary that helps a new developer understand the project fast.\n\n"

            "YOUR AUDIENCE: A developer who has never seen this repo.\n\n"

            "SUMMARY STRUCTURE (follow exactly):\n"
            "# {Repo Name} — Codebase Summary\n\n"
            "## What Is This?\n"
            "{2–3 sentences. What does this project do? What problem does it solve? "
            "Who is it for? Use plain English — avoid jargon.}\n\n"
            "## Tech Stack\n"
            "{Bullet list: language, framework, key dependencies, database, infra. "
            "Each bullet: '- **Name**: what it's used for.'}\n\n"
            "## Architecture Overview\n"
            "{How is the codebase structured? Key modules/services? "
            "Is it monolith, microservices, serverless? Keep it brief — 3–5 bullets.}\n\n"
            "## Key Features\n"
            "{The 4–6 most important things this project does. One bullet per feature.}\n\n"
            "## Getting Started\n"
            "{How to run this project locally — summarised from the README. "
            "Prerequisites, install steps, run command. Numbered list.}\n\n"
            "## Who Maintains This?\n"
            "{Stars, license, GitHub URL, any notable contributors or org info from metadata.}\n\n"
            "---\n"
            "*Codebase summary generated by Ollive AI · {date from get_datetime}*\n\n"

            "RULES:\n"
            "- Base everything on the provided repo data — never invent features.\n"
            "- If the README is sparse, note what's missing rather than guessing.\n"
            "- Keep the full summary under 800 words.\n"
            "- Always end with the '---' footer."
        ),
    },
    "notion_publisher": {
        "name": "Notion Saver",
        "role": "publisher",
        "description": "Saves the codebase summary to Notion and returns only the page URL.",
        "supervisor": False,
        "temperature": 0.1,
        "max_tokens": 8096,
        "max_iterations": 5,
        "tools": ["notion__search", "notion__create_page"],
        "mcp_providers": ["notion"],
        "system_prompt": (
            "You save codebase summaries to Notion. You have exactly two tool calls to make "
            "before you output anything:\n\n"

            "TOOL CALL 1 — notion__search\n"
            "  Call: notion__search(query=\"\")\n"
            "  Pick a parent page — prefer 'Dev Notes', 'Engineering', 'Projects', 'Codebase', "
            "'Research', or 'Notes'. If no match, use the first result.\n"
            "  Copy the UUID exactly as it appears after 'ID: '.\n\n"

            "TOOL CALL 2 — notion__create_page\n"
            "  Look in the user message for the '### analyst' section — that is the summary.\n"
            "  The title is the first line starting with '# ' — remove the '# ' prefix.\n"
            "  The content is everything after the title line.\n"
            "  Call: notion__create_page(parent_page_id=<UUID>, title=<title>, content=<summary>)\n"
            "  The result contains: 'URL: https://notion.so/...'\n\n"

            "OUTPUT: that URL. One line. Nothing before it, nothing after it.\n\n"

            "If notion__search returns no results, use parent_page_id='' to create at workspace root.\n"
            "Do NOT output any text before completing both tool calls."
        ),
    },
}


def _github_summary_graph(ids: dict[str, str]) -> dict:
    return {
        "nodes": [
            _node("trigger", "trigger", 0, 200,
                  "Manual Trigger",
                  description="Paste a GitHub repo URL or 'owner/repo' to summarise."),
            _node("supervisor", "supervisor", 300, 200,
                  "Codebase Supervisor", "supervisor",
                  _GITHUB_SUMMARY_AGENTS["supervisor"]["description"]),
            _node("github_reader", "agent", 620, 60,
                  "GitHub Reader", "github_reader",
                  _GITHUB_SUMMARY_AGENTS["github_reader"]["description"]),
            _node("analyst", "agent", 620, 200,
                  "Codebase Analyst", "analyst",
                  _GITHUB_SUMMARY_AGENTS["analyst"]["description"]),
            _node("notion_publisher", "agent", 620, 340,
                  "Notion Saver", "notion_publisher",
                  _GITHUB_SUMMARY_AGENTS["notion_publisher"]["description"]),
            _node("end", "end", 940, 200,
                  "Done — Notion URL",
                  description="Final output is the Notion page URL of the codebase summary."),
        ],
        "edges": [
            _edge("trigger", "supervisor"),
            _edge("supervisor", "github_reader"),
            _edge("supervisor", "analyst"),
            _edge("supervisor", "notion_publisher"),
            _edge("supervisor", "end"),
            _edge("github_reader", "supervisor"),
            _edge("analyst", "supervisor"),
            _edge("notion_publisher", "supervisor"),
        ],
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
    "notion_report_generator": {
        "key": "notion_report_generator",
        "name": "Notion Report Generator",
        "description": "Give it any topic — a researcher gathers web facts, a writer formats a plain-English report, and a publisher saves it to Notion. Final output: just the Notion URL.",
        "agents": _NOTION_REPORT_AGENTS,
        "build_graph": _notion_report_graph,
    },
    "github_codebase_summary": {
        "key": "github_codebase_summary",
        "name": "GitHub Codebase Summary",
        "description": "Paste a GitHub repo URL — a reader fetches the README and metadata, an analyst writes a developer-friendly summary, and a publisher saves it to Notion. Final output: just the Notion URL.",
        "agents": _GITHUB_SUMMARY_AGENTS,
        "build_graph": _github_summary_graph,
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
            meta: dict = {
                "template": key,
                "is_supervisor": spec.get("supervisor", False),
            }
            if spec.get("mcp_providers"):
                meta["mcp_providers"] = spec["mcp_providers"]
            agent = Agent(
                user_id=user_id,
                name=spec["name"],
                description=spec.get("description", ""),
                role=spec.get("role", "assistant"),
                system_prompt=spec["system_prompt"],
                tools=spec.get("tools", []),
                temperature=spec.get("temperature", 0.7),
                max_tokens=spec.get("max_tokens", 8096),
                max_iterations=spec.get("max_iterations", 5),
                guardrails={},
                meta=meta,
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
