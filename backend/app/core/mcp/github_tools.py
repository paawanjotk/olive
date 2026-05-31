"""GitHub MCP tools — calls the GitHub REST API v3 on behalf of the user."""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

_GH_BASE = "https://api.github.com"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def github__list_repos(token: str, visibility: str = "all", limit: int = 20, **_) -> str:
    """List the authenticated user's repositories."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            f"{_GH_BASE}/user/repos",
            headers=_headers(token),
            params={"visibility": visibility, "per_page": min(limit, 50), "sort": "updated"},
        )
    r.raise_for_status()
    repos = r.json()
    lines = [f"• {repo['full_name']} ({repo['visibility']}) — {repo.get('description') or 'no description'}" for repo in repos]
    return f"Found {len(repos)} repos:\n" + "\n".join(lines)


async def github__get_repo(token: str, owner: str, repo: str, **_) -> str:
    """Get details about a specific repository."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{_GH_BASE}/repos/{owner}/{repo}", headers=_headers(token))
    r.raise_for_status()
    d = r.json()
    return json.dumps({
        "full_name": d["full_name"],
        "description": d.get("description"),
        "default_branch": d["default_branch"],
        "stars": d["stargazers_count"],
        "forks": d["forks_count"],
        "open_issues": d["open_issues_count"],
        "language": d.get("language"),
        "url": d["html_url"],
        "topics": d.get("topics", []),
    }, indent=2)


async def github__list_issues(token: str, owner: str, repo: str, state: str = "open", limit: int = 20, **_) -> str:
    """List issues in a repository."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            f"{_GH_BASE}/repos/{owner}/{repo}/issues",
            headers=_headers(token),
            params={"state": state, "per_page": min(limit, 50)},
        )
    r.raise_for_status()
    issues = [i for i in r.json() if "pull_request" not in i]
    lines = [f"#{i['number']} [{i['state']}] {i['title']} — {i['user']['login']}" for i in issues]
    return f"Issues in {owner}/{repo} ({state}):\n" + "\n".join(lines) if lines else f"No {state} issues."


async def github__create_issue(token: str, owner: str, repo: str, title: str, body: str = "", labels: list | None = None, **_) -> str:
    """Create a new issue in a repository."""
    payload: dict = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{_GH_BASE}/repos/{owner}/{repo}/issues", headers=_headers(token), json=payload)
    r.raise_for_status()
    issue = r.json()
    return f"Created issue #{issue['number']}: {issue['title']}\nURL: {issue['html_url']}"


async def github__list_prs(token: str, owner: str, repo: str, state: str = "open", limit: int = 20, **_) -> str:
    """List pull requests in a repository."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            f"{_GH_BASE}/repos/{owner}/{repo}/pulls",
            headers=_headers(token),
            params={"state": state, "per_page": min(limit, 50)},
        )
    r.raise_for_status()
    prs = r.json()
    lines = [f"#{p['number']} [{p['state']}] {p['title']} ← {p['head']['ref']} by {p['user']['login']}" for p in prs]
    return f"PRs in {owner}/{repo} ({state}):\n" + "\n".join(lines) if lines else f"No {state} PRs."


async def github__get_file(token: str, owner: str, repo: str, path: str, ref: str = "", **_) -> str:
    """Get the content of a file from a repository."""
    import base64
    params = {}
    if ref:
        params["ref"] = ref
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{_GH_BASE}/repos/{owner}/{repo}/contents/{path}", headers=_headers(token), params=params)
    r.raise_for_status()
    data = r.json()
    if data.get("encoding") == "base64":
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    else:
        content = data.get("content", "")
    return f"File: {data['path']} ({data.get('size', 0)} bytes)\n\n{content[:8000]}"


async def github__search_code(token: str, query: str, limit: int = 10, **_) -> str:
    """Search for code across GitHub repositories the user has access to."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            f"{_GH_BASE}/search/code",
            headers=_headers(token),
            params={"q": query, "per_page": min(limit, 30)},
        )
    r.raise_for_status()
    items = r.json().get("items", [])
    lines = [f"• {i['repository']['full_name']}/{i['path']}" for i in items]
    return f"Code search results for '{query}':\n" + "\n".join(lines) if lines else "No results."


# ── Anthropic tool definitions ────────────────────────────────────────────────

GITHUB_TOOL_DEFS = [
    {
        "name": "github__list_repos",
        "description": "List the user's GitHub repositories. Returns names, descriptions, and visibility.",
        "input_schema": {
            "type": "object",
            "properties": {
                "visibility": {"type": "string", "description": "Filter by visibility: 'all', 'public', or 'private'. Default 'all'.", "default": "all"},
                "limit": {"type": "integer", "description": "Max repos to return (default 20, max 50).", "default": 20},
            },
        },
    },
    {
        "name": "github__get_repo",
        "description": "Get details about a specific GitHub repository: stars, forks, open issues, language, topics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner username or org"},
                "repo": {"type": "string", "description": "Repository name"},
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "github__list_issues",
        "description": "List issues in a GitHub repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "state": {"type": "string", "description": "'open', 'closed', or 'all'. Default 'open'.", "default": "open"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "github__create_issue",
        "description": "Create a new issue in a GitHub repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "title": {"type": "string", "description": "Issue title"},
                "body": {"type": "string", "description": "Issue description (markdown supported)", "default": ""},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Optional label names"},
            },
            "required": ["owner", "repo", "title"],
        },
    },
    {
        "name": "github__list_prs",
        "description": "List pull requests in a GitHub repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "state": {"type": "string", "default": "open"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "github__get_file",
        "description": "Read a file from a GitHub repository. Returns the file content (truncated to 8000 chars).",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string", "description": "File path relative to repo root, e.g. 'src/main.py'"},
                "ref": {"type": "string", "description": "Branch, tag, or commit SHA. Defaults to default branch.", "default": ""},
            },
            "required": ["owner", "repo", "path"],
        },
    },
    {
        "name": "github__search_code",
        "description": "Search for code on GitHub. Returns matching file paths and repositories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "GitHub code search query, e.g. 'useState repo:my-org/my-repo'"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
]

GITHUB_TOOL_FNS = {
    "github__list_repos": github__list_repos,
    "github__get_repo": github__get_repo,
    "github__list_issues": github__list_issues,
    "github__create_issue": github__create_issue,
    "github__list_prs": github__list_prs,
    "github__get_file": github__get_file,
    "github__search_code": github__search_code,
}
