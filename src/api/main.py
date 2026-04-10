"""
FastAPI Main Entry Point - LIS Code Agent Service.

Run with: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rich.console import Console

from src.config import get_settings
from src.api.routes import chat, control, webhook
from src.memory.vector_store import VectorStore
from src.utils.logger import setup_logging

console = Console()
settings = get_settings()

# Global vector store instance
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get or create the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(persist_path=str(settings.chroma_path))
    return _vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager - startup and shutdown events."""
    # Startup
    console.print("[bold cyan]Starting LIS Code Agent Service...[/bold cyan]")

    # Ensure directories exist
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    settings.conversations_path.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)

    # Initialize vector store
    vector_store = get_vector_store()
    console.print(f"[green]✓ Vector store initialized at {settings.chroma_path}[/green]")

    # Load memory files
    from src.memory.manager import MemoryManager
    memory = MemoryManager()
    console.print(f"[green]✓ Memory files loaded from {settings.agent_root}[/green]")

    console.print("[bold green]✓ Service ready![/bold green]")
    console.print(f"  API: http://{settings.api_host}:{settings.api_port}")
    console.print(f"  Docs: http://{settings.api_host}:{settings.api_port}/docs")

    # Start Jira poller if enabled
    import asyncio
    poller_task = None
    if settings.poll_interval_minutes > 0:
        from src.flows.poller import JiraPoller
        poller = JiraPoller(poll_interval_minutes=settings.poll_interval_minutes)
        poller_task = asyncio.create_task(poller.start())
        console.print(f"[green]✓ Jira poller started (every {settings.poll_interval_minutes} min)[/green]")
    else:
        console.print("[dim]  Jira poller disabled (POLL_INTERVAL_MINUTES=0)[/dim]")

    console.print("")

    yield

    # Shutdown
    if poller_task:
        poller_task.cancel()
    console.print("[yellow]Shutting down LIS Code Agent Service...[/yellow]")


# Create FastAPI app
app = FastAPI(
    title="LIS Code Agent",
    description="AI-powered agent for Jira ticket processing and code management",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(control.router, prefix="/api", tags=["control"])
app.include_router(webhook.router, prefix="/api", tags=["webhook"])


@app.get("/")
async def root():
    """Root endpoint - service information."""
    return {
        "service": "LIS Code Agent",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "vector_store": _vector_store is not None,
        "memory_files": {
            "soul": settings.soul_path.exists(),
            "identity": settings.identity_path.exists(),
            "user": settings.user_path.exists(),
            "memory": settings.memory_path.exists(),
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
