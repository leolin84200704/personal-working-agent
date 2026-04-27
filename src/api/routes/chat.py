"""
Chat Routes - WebSocket endpoint for real-time conversation.

Updated to stream tool_use events as they happen.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from rich.console import Console

from src.agent.loop import AgentLoop
from src.config import get_settings

router = APIRouter()
console = Console()
settings = get_settings()


class ConnectionManager:
    """Manage active WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self.active_connections[session_id] = websocket
        console.print(f"[cyan]Session {session_id[:8]} connected[/cyan]")

    def disconnect(self, session_id: str) -> None:
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            console.print(f"[yellow]Session {session_id[:8]} disconnected[/yellow]")

    async def send_json(self, session_id: str, data: dict) -> bool:
        ws = self.active_connections.get(session_id)
        if ws:
            try:
                await ws.send_json(data)
                return True
            except Exception as e:
                console.print(f"[red]Error sending to {session_id[:8]}: {e}[/red]")
                self.disconnect(session_id)
        return False


manager = ConnectionManager()


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat with the agent.

    Streams tool_use events as they happen, then sends the final response.
    """
    session_id = str(uuid.uuid4())
    await manager.connect(websocket, session_id)

    agent = AgentLoop(session_id=session_id)

    # Wire up tool event callbacks for real-time streaming
    async def on_tool_use(tool_name: str, tool_input: dict):
        await manager.send_json(session_id, {
            "type": "tool_use",
            "tool": tool_name,
            "input": tool_input,
            "session_id": session_id,
        })

    async def on_tool_result(tool_name: str, result_preview: str):
        await manager.send_json(session_id, {
            "type": "tool_result",
            "tool": tool_name,
            "result_preview": result_preview,
            "session_id": session_id,
        })

    # Note: callbacks are async but AgentLoop calls them from sync context.
    # We use a simple sync wrapper that schedules the coroutine.
    import asyncio

    _loop = asyncio.get_event_loop()

    def sync_on_tool_use(name, inp):
        asyncio.ensure_future(on_tool_use(name, inp))

    def sync_on_tool_result(name, preview):
        asyncio.ensure_future(on_tool_result(name, preview))

    agent.on_tool_use = sync_on_tool_use
    agent.on_tool_result = sync_on_tool_result

    # Send welcome message
    await websocket.send_json({
        "type": "system",
        "content": "LIS Code Agent ready. How can I help?",
        "session_id": session_id,
    })

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "")
            # Optional ticket_id from client. When present, bind this agent
            # instance to the ticket so SessionIndex writes group per-ticket.
            ticket_id = data.get("ticket_id")
            if ticket_id:
                try:
                    agent.set_ticket(ticket_id)
                except Exception as e:
                    console.print(f"[yellow]set_ticket failed: {e}[/yellow]")

            if not user_message:
                continue

            console.print(f"[dim]{session_id[:8]}: {user_message[:80]}[/dim]")

            try:
                response = await agent.process_message(user_message)

                await websocket.send_json({
                    "type": "response",
                    "content": response.get("response", ""),
                    "session_id": session_id,
                    "tool_calls": response.get("tool_calls", []),
                    "rounds": response.get("rounds", 1),
                })

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                import traceback
                traceback.print_exc()

                await websocket.send_json({
                    "type": "error",
                    "content": f"Error: {str(e)}",
                    "session_id": session_id,
                })

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        console.print(f"[red]WebSocket error: {e}[/red]")
        manager.disconnect(session_id)
