"""
Tool definitions for Claude's tool_use API.

Each tool is a dict matching the Anthropic tool schema format.
The model sees these definitions and decides which tools to call.
"""

TOOL_DEFINITIONS = [
    # ─── Jira Tools ───────────────────────────────────────────────
    {
        "name": "jira_get_ticket",
        "description": (
            "Fetch a Jira ticket by key. Returns ticket fields: "
            "summary, description, status, type, priority, assignee, "
            "reporter, labels, components, and attachments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "Jira ticket key (e.g., VP-15979, LIS-123)",
                },
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "jira_get_assigned",
        "description": (
            "Get Jira tickets assigned to the current user. "
            "Returns a list of tickets with key, summary, status, type, priority."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status (e.g., 'In Progress', 'Dev To Do')",
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project key (e.g., 'VP', 'LIS')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max tickets to return (default 20)",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "jira_search",
        "description": (
            "Search Jira tickets by text query. "
            "Searches summary and description fields."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for in ticket summary/description",
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project key",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 20)",
                    "default": 20,
                },
            },
            "required": ["query"],
        },
    },
    # ─── File Tools ───────────────────────────────────────────────
    {
        "name": "read_file",
        "description": (
            "Read a file's content with line numbers. "
            "Use offset/limit for large files. "
            "Path can be absolute or relative to repos base (/Users/hung.l/src)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path (absolute, or relative to repos base)",
                },
                "offset": {
                    "type": "integer",
                    "description": "Start line (1-based, default 1)",
                    "default": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max lines to return (default 500)",
                    "default": 500,
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Edit a file by replacing an exact string match with new content. "
            "The old_string must uniquely match a section of the file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path",
                },
                "old_string": {
                    "type": "string",
                    "description": "Exact string to find in the file",
                },
                "new_string": {
                    "type": "string",
                    "description": "Replacement string",
                },
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with the given content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path",
                },
                "content": {
                    "type": "string",
                    "description": "File content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    # ─── Search Tools ─────────────────────────────────────────────
    {
        "name": "search_files",
        "description": (
            "Search for files by name pattern (glob) across repos. "
            "Returns matching file paths."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '*.ts', 'application.properties', '**/*.java')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: repos base path)",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "grep",
        "description": (
            "Search file contents using a regex pattern. "
            "Returns matching lines with file paths and line numbers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in (default: repos base)",
                },
                "include": {
                    "type": "string",
                    "description": "Glob to filter files (e.g., '*.java', '*.ts')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max matching lines to return (default 50)",
                    "default": 50,
                },
            },
            "required": ["pattern"],
        },
    },
    # ─── Bash Tool ────────────────────────────────────────────────
    {
        "name": "run_bash",
        "description": (
            "Execute a bash command and return stdout, stderr, and exit code. "
            "Use for: running scripts (npx ts-node ...), DB queries, "
            "gRPC calls, npm commands, curl, etc. "
            "Default working directory is repos base (/Users/hung.l/src)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (default: repos base path)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 120)",
                    "default": 120,
                },
            },
            "required": ["command"],
        },
    },
    # ─── Git Tools ────────────────────────────────────────────────
    {
        "name": "git_status",
        "description": "Get git status (short format) for a repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repo name (e.g., 'lis-backend-emr-v2')",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "git_diff",
        "description": (
            "Get git diff for a repository. "
            "Use '--stat' for an overview, or '-- path/to/file' for specific files. "
            "Use '--cached' for staged changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repo name",
                },
                "args": {
                    "type": "string",
                    "description": "Additional git diff args (e.g., '--stat', '--cached', 'HEAD~1 -- src/file.ts')",
                    "default": "",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "git_log",
        "description": "Get recent git commits for a repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repo name",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of commits to show (default 10)",
                    "default": 10,
                },
                "args": {
                    "type": "string",
                    "description": "Additional git log args (e.g., '--oneline', '-- src/')",
                    "default": "",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "git_create_branch",
        "description": (
            "Create a new git branch. "
            "Branch name is validated to follow naming convention: "
            "feature/leo/{ticket_id} or bugfix/leo/{ticket_id}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repo name",
                },
                "branch_name": {
                    "type": "string",
                    "description": "Desired branch name",
                },
                "ticket_id": {
                    "type": "string",
                    "description": "Jira ticket ID (e.g., VP-15979)",
                },
            },
            "required": ["repo", "branch_name", "ticket_id"],
        },
    },
    {
        "name": "git_commit",
        "description": (
            "Stage files and create a commit. "
            "Commit message format: [{ticket_id}] {message}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repo name",
                },
                "message": {
                    "type": "string",
                    "description": "Commit message",
                },
                "ticket_id": {
                    "type": "string",
                    "description": "Ticket ID to prepend (e.g., VP-15979)",
                    "default": "",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to stage. If empty, stages all changed files.",
                },
            },
            "required": ["repo", "message"],
        },
    },
    {
        "name": "git_push",
        "description": (
            "Push current branch to remote. "
            "Only allowed for feature/leo/* and bugfix/leo/* branches."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repo name",
                },
            },
            "required": ["repo"],
        },
    },
    # ─── Memory Tools ─────────────────────────────────────────────
    {
        "name": "memory_search",
        "description": (
            "Search agent's accumulated knowledge base using semantic similarity. "
            "Searches past conversations, patterns, and gotchas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "collection": {
                    "type": "string",
                    "description": "Collection to search: conversations, patterns, gotchas, code_snippets (default: conversations)",
                    "default": "conversations",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
]


# ─── Plan Mode Tools ─────────────────────────────────────────────
PLAN_TOOL_DEFINITIONS = [
    {
        "name": "enter_plan_mode",
        "description": (
            "Enter planning mode. In this mode, only read-only tools are available. "
            "Use this before complex tasks to investigate first, then create a structured plan. "
            "The user must approve the plan before execution begins."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "create_plan",
        "description": (
            "Create a structured execution plan for user approval. "
            "Only available in planning mode. List each step with description, "
            "the tool you intend to use, and your reasoning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The overall goal of this plan",
                },
                "steps": {
                    "type": "array",
                    "description": "Ordered list of execution steps",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "What this step does",
                            },
                            "tool": {
                                "type": "string",
                                "description": "Which tool to use (e.g., edit_file, run_bash)",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Why this step is needed",
                            },
                        },
                        "required": ["description"],
                    },
                },
            },
            "required": ["goal", "steps"],
        },
    },
    {
        "name": "exit_plan_mode",
        "description": (
            "Exit planning mode and restore all tools. "
            "Call this after the user has approved the plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ─── Sub-Agent Tools ─────────────────────────────────────────────
SUB_AGENT_TOOL_DEFINITIONS = [
    {
        "name": "spawn_agent",
        "description": (
            "Spawn a sub-agent to handle a specific task independently. "
            "The sub-agent runs with its own context and tool set, then returns results. "
            "Use this to delegate investigation, analysis, or code tasks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear task description for the sub-agent",
                },
                "agent_type": {
                    "type": "string",
                    "enum": ["explore", "analyze", "code"],
                    "description": (
                        "Agent type: "
                        "'explore' = read-only file/git tools for investigation; "
                        "'analyze' = read-only + jira + memory for analysis; "
                        "'code' = full tools for code changes"
                    ),
                    "default": "explore",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context to provide to the sub-agent (e.g., what you've already found)",
                },
            },
            "required": ["task", "agent_type"],
        },
    },
    {
        "name": "list_agents",
        "description": "List all sub-agent results from this session.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


from src.agent.task_manager import TASK_TOOL_DEFINITIONS
from src.tools.web import WEB_TOOL_DEFINITIONS
from src.agent.background import BACKGROUND_TOOL_DEFINITIONS
from src.memory.short_term import STM_TOOL_DEFINITIONS
from src.memory.distiller import DISTILL_TOOL_DEFINITIONS

ALL_TOOL_DEFINITIONS = (
    TOOL_DEFINITIONS
    + PLAN_TOOL_DEFINITIONS
    + SUB_AGENT_TOOL_DEFINITIONS
    + TASK_TOOL_DEFINITIONS
    + WEB_TOOL_DEFINITIONS
    + BACKGROUND_TOOL_DEFINITIONS
    + STM_TOOL_DEFINITIONS
    + DISTILL_TOOL_DEFINITIONS
)
