"""
API Schemas - Pydantic models for request/response validation.

Simplified: removed IntentType (no more intent classification layer).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in the conversation."""
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str
    session_id: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    rounds: int = 1


class ToolEvent(BaseModel):
    """A tool use event streamed to the client."""
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    result_preview: str = ""


class MemoryUpdate(BaseModel):
    """A memory update to be applied."""
    file_type: Literal["soul", "identity", "user", "memory"]
    operation: Literal["append", "replace", "delete"]
    content: str
    section: str | None = None


class SessionInfo(BaseModel):
    """Information about a conversation session."""
    session_id: str
    created_at: datetime
    last_activity: datetime
    message_count: int
    is_active: bool = True
