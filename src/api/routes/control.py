"""
Control Routes - REST endpoints for service control and monitoring.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import get_settings
from src.memory.manager import MemoryManager
from src.memory.vector_store import VectorStore

router = APIRouter()
settings = get_settings()


class MemoryResponse(BaseModel):
    """Response for memory endpoint."""
    file_type: str
    content: str
    last_modified: str | None = None


class StatsResponse(BaseModel):
    """Response for stats endpoint."""
    uptime: str
    total_sessions: int
    active_sessions: int
    memory_files: dict[str, bool]
    vector_store_stats: dict[str, Any]


@router.get("/memory/{file_type}")
async def get_memory(file_type: str) -> MemoryResponse:
    """
    Get content from a memory file.

    Supported file types: soul, identity, user, memory
    """
    memory = MemoryManager()

    file_map = {
        "soul": ("SOUL.md", memory.read_soul),
        "identity": ("IDENTITY.md", memory.read_identity),
        "user": ("USER.md", memory.read_user),
        "memory": ("MEMORY.md", memory.read_memory),
    }

    if file_type not in file_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file_type. Must be one of: {list(file_map.keys())}"
        )

    filename, reader = file_map[file_type]
    content = reader()

    # Get file modification time
    file_path = settings.agent_root / filename
    last_modified = None
    if file_path.exists():
        last_modified = datetime.fromtimestamp(
            file_path.stat().st_mtime
        ).isoformat()

    return MemoryResponse(
        file_type=file_type,
        content=content,
        last_modified=last_modified,
    )


@router.get("/stats")
async def get_stats() -> StatsResponse:
    """Get service statistics."""
    # Check memory files
    memory_files = {
        "soul": settings.soul_path.exists(),
        "identity": settings.identity_path.exists(),
        "user": settings.user_path.exists(),
        "memory": settings.memory_path.exists(),
    }

    # Vector store stats (basic)
    vector_store_stats = {
        "path": str(settings.chroma_path),
        "exists": settings.chroma_path.exists(),
    }

    return StatsResponse(
        uptime="N/A",  # TODO: Track actual uptime
        total_sessions=0,  # TODO: Track session count
        active_sessions=0,  # TODO: Track active sessions
        memory_files=memory_files,
        vector_store_stats=vector_store_stats,
    )


@router.post("/memory/update")
async def update_memory(
    file_type: str,
    content: str,
    section: str | None = None,
) -> dict[str, str]:
    """
    Manually update a memory file.

    This endpoint is for manual memory updates.
    The agent also updates memory automatically during conversations.
    """
    memory = MemoryManager()

    file_map = {
        "soul": memory.soul_path,
        "identity": memory.identity_path,
        "user": memory.user_path,
        "memory": memory.memory_path,
    }

    if file_type not in file_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file_type. Must be one of: {list(file_map.keys())}"
        )

    file_path = file_map[file_type]

    # For now, just append. TODO: Implement smarter updates
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"\n\n## Manual Update ({datetime.now().isoformat()})\n\n{content}\n")

    return {
        "status": "success",
        "file": str(file_path),
        "message": f"Updated {file_type}.md",
    }


class ResetRequest(BaseModel):
    """Request to reset conversation history."""
    session_id: str | None = None
    confirm: bool = False


@router.post("/reset")
async def reset_conversation(request: ResetRequest) -> dict[str, str]:
    """
    Reset conversation history.

    If session_id is provided, only that session is reset.
    Otherwise, all conversation history is cleared.
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to proceed with reset"
        )

    # TODO: Implement actual session reset
    # For now, just acknowledge
    return {
        "status": "success",
        "message": "Conversation reset",
    }
