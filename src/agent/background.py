"""
Background task execution - Run commands in background threads and check later.

Allows the agent to start long-running commands (builds, tests, deploys)
without blocking the conversation. The agent calls `run` to start a command,
gets back a task_id immediately, then calls `get` to check status later.

Uses threading.Thread + subprocess.run (simpler than asyncio for this use case).
"""
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.config import get_settings

# Safety limits (same as executors.py)
MAX_OUTPUT_CHARS = 80_000
BLOCKED_PATTERNS = ["rm -rf /", "rm -rf ~", "mkfs.", "> /dev/sd"]


@dataclass
class BackgroundTask:
    """A background command execution with its status and output."""

    id: str
    command: str
    cwd: str
    status: str  # "running", "completed", "failed", "timeout"
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        """Serialize to a dict for JSON output."""
        return {
            "id": self.id,
            "command": self.command,
            "cwd": self.cwd,
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Truncate text with notice if it exceeds the limit."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n... (truncated, showing {limit} of {len(text)} chars)"


class BackgroundRunner:
    """Manages background command execution in threads."""

    def __init__(self) -> None:
        self.tasks: dict[str, BackgroundTask] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def _next_id(self) -> str:
        """Generate the next task ID (thread-safe)."""
        with self._lock:
            self._counter += 1
            return f"bg-{self._counter}"

    def _execute(self, task: BackgroundTask, timeout: int) -> None:
        """Run the command in a thread and update the task when done."""
        try:
            result = subprocess.run(
                task.command,
                shell=True,
                cwd=task.cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            task.stdout = _truncate(result.stdout)
            task.stderr = _truncate(result.stderr)
            task.exit_code = result.returncode
            task.status = "completed" if result.returncode == 0 else "failed"
        except subprocess.TimeoutExpired as e:
            task.stdout = _truncate(e.stdout or "") if e.stdout else ""
            task.stderr = _truncate(e.stderr or "") if e.stderr else ""
            task.status = "timeout"
        except Exception as e:
            task.stderr = str(e)
            task.status = "failed"
        finally:
            task.completed_at = datetime.now(timezone.utc)

    def run(self, command: str, cwd: str | None = None, timeout: int = 600) -> BackgroundTask:
        """
        Start a command in a background thread. Returns immediately with task info.

        Args:
            command: The bash command to execute.
            cwd: Working directory (default: repos_base_path from settings).
            timeout: Max seconds before the command is killed (default 600).

        Returns:
            BackgroundTask with status "running" and an assigned task id.

        Raises:
            ValueError: If the command matches a blocked pattern.
        """
        # Safety check (same as run_bash)
        for blocked in BLOCKED_PATTERNS:
            if blocked in command:
                raise ValueError(f"Blocked command for safety: contains '{blocked}'")

        work_dir = cwd or str(get_settings().repos_base_path)
        task_id = self._next_id()

        task = BackgroundTask(
            id=task_id,
            command=command,
            cwd=work_dir,
            status="running",
        )
        self.tasks[task_id] = task

        thread = threading.Thread(
            target=self._execute,
            args=(task, timeout),
            daemon=True,
            name=f"bg-task-{task_id}",
        )
        thread.start()

        return task

    def get(self, task_id: str) -> BackgroundTask | None:
        """Get task status and output. Returns None if task_id not found."""
        return self.tasks.get(task_id)

    def list(self) -> list[BackgroundTask]:
        """List all background tasks, most recent first."""
        return sorted(self.tasks.values(), key=lambda t: t.started_at, reverse=True)


# ─── Tool Definitions (Anthropic tool_use schema) ────────────────

BACKGROUND_TOOL_DEFINITIONS = [
    {
        "name": "run_background",
        "description": (
            "Start a bash command running in the background. Returns immediately "
            "with a task_id. Use get_background_task to check status and read output later. "
            "Good for long-running commands: builds, test suites, deployments, "
            "large git operations, etc. Default timeout 600s (10 min)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute in the background",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (default: repos base path)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 600, max 600)",
                    "default": 600,
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "get_background_task",
        "description": (
            "Check the status and output of a background task. "
            "Returns task status (running/completed/failed/timeout), "
            "stdout, stderr, and exit code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID returned by run_background (e.g., 'bg-1')",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "list_background_tasks",
        "description": (
            "List all background tasks in this session with their status. "
            "Shows task id, command, status, and timing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]
