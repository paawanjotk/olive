"""Notion MCP tools — calls the Notion API v1 on behalf of the user."""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

_NOTION_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _title_from_page(page: dict) -> str:
    props = page.get("properties", {})
    for key in ("Name", "Title", "title", "name"):
        prop = props.get(key, {})
        if prop.get("type") == "title":
            parts = prop.get("title", [])
            return "".join(p.get("plain_text", "") for p in parts)
    return page.get("id", "Untitled")


async def notion__search(token: str, query: str = "", filter_type: str = "page", limit: int = 20, **_) -> str:
    """Search Notion pages and databases."""
    body: dict = {"page_size": min(limit, 50)}
    if query:
        body["query"] = query
    if filter_type in ("page", "database"):
        body["filter"] = {"value": filter_type, "property": "object"}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{_NOTION_BASE}/search", headers=_headers(token), json=body)
    r.raise_for_status()
    results = r.json().get("results", [])
    lines = []
    for item in results:
        title = _title_from_page(item) if item["object"] == "page" else item.get("title", [{}])[0].get("plain_text", "Untitled DB") if item["object"] == "database" else "?"
        lines.append(f"• [{item['object']}] {title} — ID: {item['id']}")
    return f"Search results for '{query}':\n" + "\n".join(lines) if lines else "No results found."


async def notion__get_page(token: str, page_id: str, **_) -> str:
    """Get a Notion page's metadata and title."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{_NOTION_BASE}/pages/{page_id}", headers=_headers(token))
    r.raise_for_status()
    page = r.json()
    title = _title_from_page(page)
    url = page.get("url", "")
    props = {k: v.get("type") for k, v in page.get("properties", {}).items()}
    return json.dumps({"id": page["id"], "title": title, "url": url, "property_types": props}, indent=2)


async def notion__get_page_content(token: str, page_id: str, **_) -> str:
    """Get the text content of a Notion page by reading its blocks."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{_NOTION_BASE}/blocks/{page_id}/children", headers=_headers(token))
    r.raise_for_status()
    blocks = r.json().get("results", [])
    lines = []
    for block in blocks:
        btype = block.get("type", "")
        content = block.get(btype, {})
        rich = content.get("rich_text", [])
        text = "".join(p.get("plain_text", "") for p in rich)
        if text:
            prefix = {"heading_1": "# ", "heading_2": "## ", "heading_3": "### ",
                      "bulleted_list_item": "• ", "numbered_list_item": "1. ",
                      "to_do": "☐ ", "quote": "> "}.get(btype, "")
            lines.append(f"{prefix}{text}")
    return "\n".join(lines)[:8000] if lines else "(empty page)"


def _md_to_blocks(content: str) -> list[dict]:
    """Convert markdown text to Notion block objects. Handles headings, bullets, numbered lists."""
    blocks = []
    for line in content.split("\n"):
        stripped = line.rstrip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            btype, text = "heading_3", stripped[4:]
        elif stripped.startswith("## "):
            btype, text = "heading_2", stripped[3:]
        elif stripped.startswith("# "):
            btype, text = "heading_1", stripped[2:]
        elif stripped.startswith(("- ", "* ", "• ")):
            btype, text = "bulleted_list_item", stripped[2:]
        elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1:3] in (". ", ") "):
            btype, text = "numbered_list_item", stripped[3:]
        else:
            btype, text = "paragraph", stripped
        # Notion text blocks have a 2000-char limit — split long lines
        for chunk in [text[i:i+2000] for i in range(0, max(len(text), 1), 2000)]:
            blocks.append({
                "object": "block",
                "type": btype,
                btype: {"rich_text": [{"type": "text", "text": {"content": chunk}}]},
            })
    return blocks


async def notion__create_page(token: str, parent_page_id: str, title: str, content: str = "", **_) -> str:
    """Create a new Notion page under a parent page with full content support."""
    all_blocks = _md_to_blocks(content) if content else []
    # Notion limits initial children to 100 blocks per request
    first_batch, remaining = all_blocks[:100], all_blocks[100:]
    payload = {
        "parent": {"page_id": parent_page_id},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": title}}]}
        },
        "children": first_batch,
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{_NOTION_BASE}/pages", headers=_headers(token), json=payload)
        r.raise_for_status()
        page = r.json()
        page_id = page["id"]
        # Append remaining blocks in batches of 100
        for i in range(0, len(remaining), 100):
            batch = remaining[i:i+100]
            ra = await c.patch(
                f"{_NOTION_BASE}/blocks/{page_id}/children",
                headers=_headers(token),
                json={"children": batch},
            )
            ra.raise_for_status()
    return f"Created page '{title}'\nID: {page_id}\nURL: {page.get('url', '')}"


async def notion__append_block(token: str, block_id: str, content: str, block_type: str = "paragraph", **_) -> str:
    """Append content to an existing Notion page or block. Supports multi-line markdown content."""
    blocks = _md_to_blocks(content)
    if not blocks:
        return "Nothing to append (empty content)."
    # If caller forced a specific block_type, override the type on all blocks
    allowed = {"paragraph", "bulleted_list_item", "numbered_list_item", "quote", "to_do"}
    if block_type in allowed:
        for b in blocks:
            old_type = b["type"]
            b["type"] = block_type
            b[block_type] = b.pop(old_type)
    async with httpx.AsyncClient(timeout=30) as c:
        for i in range(0, len(blocks), 100):
            r = await c.patch(
                f"{_NOTION_BASE}/blocks/{block_id}/children",
                headers=_headers(token),
                json={"children": blocks[i:i+100]},
            )
            r.raise_for_status()
    return f"Appended {len(blocks)} block(s) to {block_id}."


async def notion__query_database(token: str, database_id: str, limit: int = 20, **_) -> str:
    """Query all rows from a Notion database."""
    payload = {"page_size": min(limit, 100)}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{_NOTION_BASE}/databases/{database_id}/query", headers=_headers(token), json=payload)
    r.raise_for_status()
    rows = r.json().get("results", [])
    lines = [f"• {_title_from_page(row)} — {row['id']}" for row in rows]
    return f"Database {database_id} ({len(rows)} rows):\n" + "\n".join(lines) if lines else "Empty database."


# ── Anthropic tool definitions ────────────────────────────────────────────────

NOTION_TOOL_DEFS = [
    {
        "name": "notion__search",
        "description": "Search across the user's Notion workspace for pages or databases matching a query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords. Leave empty to list all.", "default": ""},
                "filter_type": {"type": "string", "description": "'page' or 'database'. Default 'page'.", "default": "page"},
                "limit": {"type": "integer", "description": "Max results to return (default 20).", "default": 20},
            },
        },
    },
    {
        "name": "notion__get_page",
        "description": "Get the metadata and title of a specific Notion page by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Notion page UUID (from notion__search results)"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "notion__get_page_content",
        "description": "Read the full text content of a Notion page (up to 8000 characters).",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Notion page UUID"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "notion__create_page",
        "description": "Create a new Notion page under an existing parent page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_page_id": {"type": "string", "description": "UUID of the parent page"},
                "title": {"type": "string", "description": "Title for the new page"},
                "content": {"type": "string", "description": "Initial text content (newline-separated paragraphs)", "default": ""},
            },
            "required": ["parent_page_id", "title"],
        },
    },
    {
        "name": "notion__append_block",
        "description": "Append a text block to an existing Notion page or block.",
        "input_schema": {
            "type": "object",
            "properties": {
                "block_id": {"type": "string", "description": "UUID of the page or parent block to append to"},
                "content": {"type": "string", "description": "Text content for the new block"},
                "block_type": {"type": "string", "description": "Block type: 'paragraph', 'bulleted_list_item', 'numbered_list_item', 'quote', 'to_do'. Default 'paragraph'.", "default": "paragraph"},
            },
            "required": ["block_id", "content"],
        },
    },
    {
        "name": "notion__query_database",
        "description": "Query all rows from a Notion database. Returns row titles and IDs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "database_id": {"type": "string", "description": "UUID of the Notion database"},
                "limit": {"type": "integer", "description": "Max rows to return (default 20).", "default": 20},
            },
            "required": ["database_id"],
        },
    },
]

NOTION_TOOL_FNS = {
    "notion__search": notion__search,
    "notion__get_page": notion__get_page,
    "notion__get_page_content": notion__get_page_content,
    "notion__create_page": notion__create_page,
    "notion__append_block": notion__append_block,
    "notion__query_database": notion__query_database,
}
