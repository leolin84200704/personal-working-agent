"""
Tool executors - Functions that execute tools and return raw/trimmed results.

Design principles (from Claude Code analysis):
1. Return raw data, not interpreted summaries
2. Model controls what to query; Python only executes and trims for safety
3. Safety-net truncation prevents context window overflow
4. Each function returns a plain string (what the model sees)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.integrations.jira import JiraClient, JiraTicket
from src.integrations.git_operator import GitOperator, find_git_repos
from src.memory.vector_store import VectorStore
from src.tools.web import web_fetch, web_search

settings = get_settings()

# Safety limits
MAX_OUTPUT_CHARS = 80_000  # ~20K tokens, safety net
MAX_FILE_LINES = 500
MAX_SEARCH_RESULTS = 50
BLOCKED_PATTERNS = ["rm -rf /", "rm -rf ~", "mkfs.", "> /dev/sd"]


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Truncate text with notice if it exceeds the limit."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n... (truncated, showing {limit} of {len(text)} chars)"


def _resolve_path(path_str: str) -> Path | None:
    """Resolve a file path: try absolute, then relative to repos base, then search repos."""
    p = Path(path_str)
    if p.is_absolute() and p.exists():
        return p

    # Relative to repos base
    base = settings.repos_base_path
    candidate = base / path_str
    if candidate.exists():
        return candidate

    # Search in repos
    for repo_dir in base.iterdir():
        if repo_dir.is_dir() and (repo_dir / ".git").exists():
            candidate = repo_dir / path_str
            if candidate.exists():
                return candidate

    return None


def _get_repo_path(repo_name: str) -> Path:
    """Get the path to a repo by name."""
    repo_path = settings.repos_base_path / repo_name
    if not repo_path.exists():
        raise FileNotFoundError(f"Repo not found: {repo_name} (looked in {settings.repos_base_path})")
    if not (repo_path / ".git").exists():
        raise ValueError(f"Not a git repository: {repo_path}")
    return repo_path


def _ticket_to_dict(ticket: JiraTicket) -> dict[str, Any]:
    """Convert JiraTicket to a raw dict preserving all fields."""
    return {
        "key": ticket.key,
        "summary": ticket.summary,
        "description": ticket.description,
        "status": ticket.status,
        "issue_type": ticket.issue_type,
        "priority": ticket.priority,
        "assignee": ticket.assignee,
        "reporter": ticket.reporter,
        "labels": ticket.labels,
        "components": ticket.components,
        "attachments": ticket.attachments,
        "is_bug": ticket.is_bug,
        "suggested_branch": ticket.branch_name,
    }


# ─── Jira Tools ───────────────────────────────────────────────────


def jira_get_ticket(ticket_id: str) -> str:
    """Fetch a Jira ticket. Returns raw ticket fields as JSON."""
    client = JiraClient()
    ticket = client.get_ticket(ticket_id)
    data = _ticket_to_dict(ticket)
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def jira_get_assigned(
    status: str | None = None,
    project: str | None = None,
    limit: int = 20,
) -> str:
    """Get assigned tickets. Returns list of ticket dicts as JSON."""
    client = JiraClient()
    tickets = client.get_assigned_tickets(status=status, project=project, limit=limit)

    data = [_ticket_to_dict(t) for t in tickets]

    # Safety net: if too many, show count + first N
    if len(data) > MAX_SEARCH_RESULTS:
        result = {
            "total": len(data),
            "showing": MAX_SEARCH_RESULTS,
            "tickets": data[:MAX_SEARCH_RESULTS],
        }
    else:
        result = {"total": len(data), "tickets": data}

    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


def jira_search(query: str, project: str | None = None, limit: int = 20) -> str:
    """Search Jira tickets. Returns matching tickets as JSON."""
    client = JiraClient()
    tickets = client.search_tickets(query=query, project=project, limit=limit)

    data = [_ticket_to_dict(t) for t in tickets]
    result = {"total": len(data), "query": query, "tickets": data}
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


# ─── File Tools ────────────────────────────────────────────────────


def read_file(path: str, offset: int = 1, limit: int = MAX_FILE_LINES) -> str:
    """Read a file with line numbers. Returns content in cat -n format."""
    resolved = _resolve_path(path)
    if resolved is None:
        return f"Error: File not found: {path}"
    if resolved.is_dir():
        return f"Error: Path is a directory, not a file: {path}"

    try:
        lines = resolved.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return f"Error: Cannot read binary file: {path}"

    total_lines = len(lines)

    # Apply offset/limit (1-based offset)
    start = max(0, offset - 1)
    end = start + limit
    selected = lines[start:end]

    # Format with line numbers (like cat -n)
    numbered = []
    for i, line in enumerate(selected, start=start + 1):
        numbered.append(f"{i:6}\t{line}")

    header = f"File: {resolved} ({total_lines} lines total)"
    if total_lines > limit or start > 0:
        header += f", showing lines {start + 1}-{min(end, total_lines)}"

    return header + "\n" + "\n".join(numbered)


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Edit a file by exact string replacement. Returns the result."""
    resolved = _resolve_path(path)
    if resolved is None:
        return f"Error: File not found: {path}"

    content = resolved.read_text(encoding="utf-8")

    # Check old_string exists
    count = content.count(old_string)
    if count == 0:
        return f"Error: old_string not found in {path}. Make sure it matches exactly (including whitespace)."
    if count > 1:
        return f"Error: old_string found {count} times in {path}. Provide a more specific match."

    new_content = content.replace(old_string, new_string, 1)
    resolved.write_text(new_content, encoding="utf-8")

    return f"OK: Replaced {len(old_string)} chars with {len(new_string)} chars in {resolved}"


def write_file(path: str, content: str) -> str:
    """Create or overwrite a file. Returns the result."""
    p = Path(path)
    if not p.is_absolute():
        p = settings.repos_base_path / path

    # Create parent dirs if needed
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

    return f"OK: Wrote {len(content)} chars to {p}"


# ─── Search Tools ──────────────────────────────────────────────────


def search_files(pattern: str, path: str | None = None) -> str:
    """Search for files by glob pattern. Returns matching paths."""
    search_path = Path(path) if path else settings.repos_base_path

    if not search_path.exists():
        return f"Error: Path not found: {search_path}"

    matches = sorted(search_path.rglob(pattern))

    # Filter out hidden dirs and common noise
    filtered = [
        m for m in matches
        if not any(part.startswith(".") for part in m.parts[len(search_path.parts):])
        and "node_modules" not in m.parts
        and "__pycache__" not in m.parts
    ]

    if not filtered:
        return f"No files matching '{pattern}' found in {search_path}"

    total = len(filtered)
    shown = filtered[:MAX_SEARCH_RESULTS]

    lines = [str(f) for f in shown]
    result = "\n".join(lines)

    if total > MAX_SEARCH_RESULTS:
        result += f"\n\n... ({total} total matches, showing first {MAX_SEARCH_RESULTS})"

    return result


def grep(
    pattern: str,
    path: str | None = None,
    include: str | None = None,
    limit: int = 50,
) -> str:
    """Search file contents with regex. Returns matching lines."""
    search_path = path or str(settings.repos_base_path)

    cmd = ["grep", "-rn", "--color=never"]
    if include:
        cmd.extend(["--include", include])
    cmd.extend([pattern, search_path])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        lines = result.stdout.strip().splitlines()
    except subprocess.TimeoutExpired:
        return f"Error: grep timed out after 30s for pattern '{pattern}'"

    if not lines:
        return f"No matches for '{pattern}' in {search_path}"

    total = len(lines)
    shown = lines[:limit]

    output = "\n".join(shown)
    if total > limit:
        output += f"\n\n... ({total} total matches, showing first {limit})"

    return output


# ─── Bash Tool ─────────────────────────────────────────────────────


def run_bash(command: str, cwd: str | None = None, timeout: int = 120) -> str:
    """Execute a bash command. Returns stdout + stderr + exit code."""
    # Safety check
    for blocked in BLOCKED_PATTERNS:
        if blocked in command:
            return f"Error: Blocked command for safety: contains '{blocked}'"

    work_dir = cwd or str(settings.repos_base_path)

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        parts = []
        if result.stdout:
            parts.append(_truncate(result.stdout))
        if result.stderr:
            parts.append(f"STDERR:\n{_truncate(result.stderr)}")
        parts.append(f"Exit code: {result.returncode}")

        return "\n".join(parts)

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


# ─── Git Tools ─────────────────────────────────────────────────────


def git_status(repo: str) -> str:
    """Get git status. Returns raw output."""
    repo_path = _get_repo_path(repo)
    git = GitOperator(repo_path)

    branch = git.get_current_branch()
    status = git.get_status()

    output = f"Branch: {branch}\n"
    if status.strip():
        output += status
    else:
        output += "(clean - no changes)"
    return output


def git_diff(repo: str, args: str = "") -> str:
    """Get git diff. Returns raw diff output."""
    repo_path = _get_repo_path(repo)

    cmd = ["git", "diff", "--color=never"]
    if args:
        cmd.extend(args.split())

    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    output = result.stdout

    if not output.strip():
        return "(no diff)"

    return _truncate(output)


def git_log(repo: str, count: int = 10, args: str = "") -> str:
    """Get recent git commits. Returns raw log output."""
    repo_path = _get_repo_path(repo)

    cmd = ["git", "log", f"-{count}", "--pretty=format:%h %s (%an, %ar)"]
    if args:
        cmd.extend(args.split())

    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    return result.stdout or "(no commits)"


def git_create_branch(repo: str, branch_name: str, ticket_id: str) -> str:
    """Create a git branch with validated naming. Returns result."""
    repo_path = _get_repo_path(repo)
    git = GitOperator(repo_path)

    created = git.create_branch(branch_name, ticket_id)
    return f"OK: Created branch '{created}' in {repo}"


def git_commit(
    repo: str,
    message: str,
    ticket_id: str = "",
    files: list[str] | None = None,
) -> str:
    """Stage files and commit. Returns result."""
    repo_path = _get_repo_path(repo)
    git = GitOperator(repo_path)

    # Stage files
    if files:
        git.add(files)
    else:
        git.add(".")

    # Commit
    git.commit(message, ticket_id)

    return f"OK: Committed to {repo} with message: [{ticket_id}] {message}" if ticket_id else f"OK: Committed to {repo} with message: {message}"


def git_push(repo: str) -> str:
    """Push current branch. Returns result."""
    repo_path = _get_repo_path(repo)
    git = GitOperator(repo_path)

    branch = git.get_current_branch()
    git.push(branch)

    return f"OK: Pushed branch '{branch}' to origin in {repo}"


# ─── Memory Tools ──────────────────────────────────────────────────


def memory_search(
    query: str,
    collection: str = "conversations",
    n_results: int = 5,
) -> str:
    """Search vector memory. Returns raw results as JSON."""
    try:
        store = VectorStore(persist_path=str(settings.chroma_path))
        results = store.search(query=query, collection=collection, n_results=n_results)

        if not results:
            return f"No results for '{query}' in {collection}"

        return json.dumps(results, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        return f"Memory search error: {e}"


# ─── Dispatcher ────────────────────────────────────────────────────


def execute_tool(name: str, input_data: dict[str, Any]) -> str:
    """
    Execute a tool by name with the given input.
    Returns the raw string result that goes directly to the model.
    """
    executors = {
        "jira_get_ticket": lambda d: jira_get_ticket(d["ticket_id"]),
        "jira_get_assigned": lambda d: jira_get_assigned(
            status=d.get("status"),
            project=d.get("project"),
            limit=d.get("limit", 20),
        ),
        "jira_search": lambda d: jira_search(
            query=d["query"],
            project=d.get("project"),
            limit=d.get("limit", 20),
        ),
        "read_file": lambda d: read_file(
            path=d["path"],
            offset=d.get("offset", 1),
            limit=d.get("limit", MAX_FILE_LINES),
        ),
        "edit_file": lambda d: edit_file(
            path=d["path"],
            old_string=d["old_string"],
            new_string=d["new_string"],
        ),
        "write_file": lambda d: write_file(path=d["path"], content=d["content"]),
        "search_files": lambda d: search_files(
            pattern=d["pattern"],
            path=d.get("path"),
        ),
        "grep": lambda d: grep(
            pattern=d["pattern"],
            path=d.get("path"),
            include=d.get("include"),
            limit=d.get("limit", 50),
        ),
        "run_bash": lambda d: run_bash(
            command=d["command"],
            cwd=d.get("cwd"),
            timeout=d.get("timeout", 120),
        ),
        "git_status": lambda d: git_status(d["repo"]),
        "git_diff": lambda d: git_diff(d["repo"], d.get("args", "")),
        "git_log": lambda d: git_log(
            d["repo"],
            count=d.get("count", 10),
            args=d.get("args", ""),
        ),
        "git_create_branch": lambda d: git_create_branch(
            repo=d["repo"],
            branch_name=d["branch_name"],
            ticket_id=d["ticket_id"],
        ),
        "git_commit": lambda d: git_commit(
            repo=d["repo"],
            message=d["message"],
            ticket_id=d.get("ticket_id", ""),
            files=d.get("files"),
        ),
        "git_push": lambda d: git_push(d["repo"]),
        "memory_search": lambda d: memory_search(
            query=d["query"],
            collection=d.get("collection", "conversations"),
            n_results=d.get("n_results", 5),
        ),
        "web_fetch": lambda d: web_fetch(
            url=d["url"],
            max_chars=d.get("max_chars", 80000),
        ),
        "web_search": lambda d: web_search(
            query=d["query"],
            max_results=d.get("max_results", 5),
        ),
    }

    executor = executors.get(name)
    if not executor:
        return f"Error: Unknown tool '{name}'"

    try:
        return executor(input_data)
    except Exception as e:
        return f"Error executing {name}: {e}"
