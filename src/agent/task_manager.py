"""
Task Manager - Session-scoped task tracking for multi-step work.

Allows the agent to create, update, and query tasks within a conversation session.
Tasks are in-memory only (no persistence).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

VALID_STATUSES = ("pending", "in_progress", "completed", "cancelled")


@dataclass
class Task:
    """A single trackable task."""

    id: int
    title: str
    description: str = ""
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class TaskManager:
    """Manages a list of tasks within a session."""

    def __init__(self) -> None:
        self._tasks: dict[int, Task] = {}
        self._next_id: int = 1

    def create(self, title: str, description: str = "") -> Task:
        """Create a new task and return it."""
        task = Task(id=self._next_id, title=title, description=description)
        self._tasks[task.id] = task
        self._next_id += 1
        return task

    def update(
        self,
        task_id: int,
        *,
        status: str | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> Task:
        """Update an existing task. Raises KeyError if not found, ValueError if invalid status."""
        task = self._get_or_raise(task_id)

        if status is not None:
            if status not in VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}"
                )
            task.status = status

        if title is not None:
            task.title = title

        if description is not None:
            task.description = description

        task.updated_at = datetime.now()
        return task

    def get(self, task_id: int) -> Task:
        """Get a single task by ID. Raises KeyError if not found."""
        return self._get_or_raise(task_id)

    def list(self, status_filter: str | None = None) -> list[Task]:
        """List all tasks, optionally filtered by status."""
        tasks = self._tasks.values()
        if status_filter is not None:
            tasks = [t for t in tasks if t.status == status_filter]
        return sorted(tasks, key=lambda t: t.id)

    def _get_or_raise(self, task_id: int) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(f"Task with id {task_id} not found") from None


# ---------------------------------------------------------------------------
# Anthropic tool_use schema definitions
# ---------------------------------------------------------------------------

TASK_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "task_create",
        "description": "建立一個新的任務來追蹤多步驟工作的進度。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "任務標題，簡要描述要完成的工作。",
                },
                "description": {
                    "type": "string",
                    "description": "任務的詳細說明（選填）。",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "task_update",
        "description": "更新現有任務的狀態、標題或描述。至少需要提供一個要更新的欄位。",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "要更新的任務 ID。",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "cancelled"],
                    "description": "新的任務狀態。pending=待處理、in_progress=進行中、completed=已完成、cancelled=已取消。",
                },
                "title": {
                    "type": "string",
                    "description": "新的任務標題（選填）。",
                },
                "description": {
                    "type": "string",
                    "description": "新的任務描述（選填）。",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "task_get",
        "description": "根據 ID 取得單一任務的詳細資訊。",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "要查詢的任務 ID。",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "task_list",
        "description": "列出所有任務。可依狀態篩選，不帶參數則回傳全部任務。",
        "input_schema": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "cancelled"],
                    "description": "依此狀態篩選任務（選填）。不指定則回傳所有任務。",
                },
            },
            "required": [],
        },
    },
]
