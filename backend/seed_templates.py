#!/usr/bin/env python3
"""Seed all Ollive workflow templates for a user account.

Run from /backend:
    python seed_templates.py                          # prompts for email
    python seed_templates.py ayaan@example.com        # seed for specific user
    python seed_templates.py --list                   # just list templates, no DB changes

What it does:
  1. Connects to the local Postgres database (reads DATABASE_URL from .env).
  2. Finds the user by email (or creates a stub account if none exists).
  3. Instantiates every template in TEMPLATES, skipping any that already exist.
  4. Prints a summary of what was created or skipped.

Templates included:
  • Research Report            — web researcher + plain-English writer
  • Support Triage             — supervisor routes to billing / tech / general specialists
  • Slack Thread Summarizer    — summarises a Slack thread when @mentioned
  • Slack Q&A Assistant        — answers Slack questions with web search + human approval
  • Notion Report Generator    — researches any topic and saves a report to Notion
  • GitHub Codebase Summary    — reads a GitHub repo and saves a dev summary to Notion
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5433/ollive_chat",
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
DIM    = "\033[2m"


def _banner():
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}  Ollive — Workflow Template Seeder{RESET}")
    print(f"{BOLD}{'─' * 60}{RESET}\n")


def _list_templates():
    from app.core.workflow.templates import TEMPLATES, list_templates
    rows = list_templates()
    print(f"{BOLD}Available templates ({len(rows)}):{RESET}\n")
    for t in rows:
        agents = TEMPLATES[t["key"]]["agents"]
        mcp = sorted({
            p
            for spec in agents.values()
            for p in spec.get("mcp_providers", [])
        })
        mcp_str = f"  {DIM}requires: {', '.join(mcp)}{RESET}" if mcp else ""
        print(f"  {CYAN}{t['key']}{RESET}")
        print(f"    {BOLD}{t['name']}{RESET} · {t['agent_count']} agents{mcp_str}")
        print(f"    {DIM}{t['description']}{RESET}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Seed logic
# ─────────────────────────────────────────────────────────────────────────────

async def seed(email: str):
    from app.core.workflow.templates import TEMPLATES, instantiate_template
    from app.db.models.users import User
    from app.db.models.workflows import Workflow

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession,
        expire_on_commit=False, autocommit=False, autoflush=False,
    )

    async with factory() as db:
        # ── Find or create user ──────────────────────────────────────────────
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"{YELLOW}User '{email}' not found — creating stub account...{RESET}")
            user = User(name=email.split("@")[0].replace(".", " ").title(), email=email)
            db.add(user)
            await db.flush()
            print(f"  {GREEN}✓{RESET} Created user {DIM}{user.id}{RESET}\n")
        else:
            print(f"{GREEN}✓{RESET} Found user {DIM}{user.id}{RESET} ({user.email})\n")

        # ── Seed each template ───────────────────────────────────────────────
        created = 0
        skipped = 0
        for key, tpl in TEMPLATES.items():
            # Check if a workflow for this template already exists
            exists_result = await db.execute(
                select(Workflow).where(
                    Workflow.user_id == user.id,
                    Workflow.name == tpl["name"],
                    Workflow.is_active.is_(True),
                )
            )
            existing = exists_result.scalars().first()

            if existing:
                print(f"  {YELLOW}↩{RESET}  {tpl['name']} {DIM}(already exists — skipped){RESET}")
                skipped += 1
                continue

            try:
                wf = await instantiate_template(db, key, user.id)
                print(f"  {GREEN}✓{RESET}  {tpl['name']} {DIM}→ {wf.id}{RESET}")
                created += 1
            except Exception as exc:
                print(f"  {YELLOW}✗{RESET}  {tpl['name']} — {exc}")

        # ── Summary ─────────────────────────────────────────────────────────
        print(f"\n{'─' * 60}")
        print(f"  {BOLD}Created:{RESET} {created}   {BOLD}Skipped:{RESET} {skipped}")
        if created:
            print(f"\n  {DIM}Open the Ollive UI → Workflows to see your new pipelines.{RESET}")
        print(f"{'─' * 60}\n")

    await engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    _banner()

    args = sys.argv[1:]

    if "--list" in args or "-l" in args:
        _list_templates()
        return

    if args:
        email = args[0]
    else:
        try:
            email = input("Enter the user email to seed templates for: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return

    if not email or "@" not in email:
        print(f"{YELLOW}Invalid email address.{RESET}")
        sys.exit(1)

    _list_templates()
    print(f"Seeding all templates for {BOLD}{email}{RESET}...\n")
    asyncio.run(seed(email))


if __name__ == "__main__":
    main()
