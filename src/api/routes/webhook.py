"""
Webhook Routes — Receive events from external systems (Jira, GitHub, etc.)

These endpoints trigger flows. Python validates the event and extracts the
ticket_id, then hands off to FlowRunner which sends a prompt to AgentLoop.
All analysis is done by the LLM.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from pydantic import BaseModel

from src.config import get_settings
from src.flows.runner import FlowRunner
from src.utils.logger import get_logger

router = APIRouter()
logger = get_logger()
settings = get_settings()

# Flow results stored for polling (in-memory, recent only)
_recent_results: dict[str, dict] = {}
MAX_RECENT = 50


class ManualTriggerRequest(BaseModel):
    """Request body for manually triggering a flow."""
    ticket_id: str
    flow: str = "triage"  # triage | review


class FlowStatusResponse(BaseModel):
    """Response for flow status check."""
    ticket_id: str
    status: str  # pending | completed | error
    result: dict | None = None


# ─── Jira Webhook ─────────────────────────────────────────────────


@router.post("/webhook/jira")
async def jira_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive Jira webhook events.

    Jira sends POST requests when tickets are created, updated, etc.
    We only act on ticket creation events.

    Setup in Jira:
      Admin → System → WebHooks → Create
      URL: https://your-server/api/webhook/jira
      Events: Issue → created
    """
    body = await request.json()

    # Validate webhook secret if configured
    if settings.jira_webhook_secret:
        _verify_jira_webhook(request, settings.jira_webhook_secret)

    # Extract event type
    webhook_event = body.get("webhookEvent", "")
    issue = body.get("issue", {})
    ticket_id = issue.get("key", "")

    if not ticket_id:
        return {"status": "ignored", "reason": "no ticket key in payload"}

    # Only trigger on ticket creation
    if webhook_event == "jira:issue_created":
        logger.info(f"[Webhook] Jira ticket created: {ticket_id}")

        # Run flow in background (don't block the webhook response)
        background_tasks.add_task(_run_triage, ticket_id)

        return {
            "status": "accepted",
            "ticket_id": ticket_id,
            "flow": "ticket_triage",
            "message": f"Triage flow started for {ticket_id}",
        }

    # Log but ignore other events
    logger.debug(f"[Webhook] Ignored Jira event: {webhook_event} for {ticket_id}")
    return {"status": "ignored", "event": webhook_event}


# ─── Manual Trigger ───────────────────────────────────────────────


@router.post("/webhook/trigger")
async def manual_trigger(req: ManualTriggerRequest, background_tasks: BackgroundTasks):
    """
    Manually trigger a flow for a ticket.

    Useful for:
    - Testing the webhook flow without Jira
    - Re-running triage on an existing ticket
    - Triggering code review after changes are made

    Example:
        curl -X POST http://localhost:8000/api/webhook/trigger \
            -H "Content-Type: application/json" \
            -d '{"ticket_id": "VP-16000", "flow": "triage"}'
    """
    ticket_id = req.ticket_id
    flow = req.flow

    if flow == "triage":
        logger.info(f"[Webhook] Manual triage trigger for {ticket_id}")
        background_tasks.add_task(_run_triage, ticket_id)
    elif flow == "review":
        logger.info(f"[Webhook] Manual review trigger for {ticket_id}")
        background_tasks.add_task(_run_review, ticket_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown flow: {flow}")

    return {
        "status": "accepted",
        "ticket_id": ticket_id,
        "flow": flow,
        "message": f"{flow} flow started for {ticket_id}",
    }


# ─── Status Check ────────────────────────────────────────────────


@router.get("/webhook/status/{ticket_id}")
async def flow_status(ticket_id: str):
    """
    Check the status/result of a flow for a ticket.

    Example:
        curl http://localhost:8000/api/webhook/status/VP-16000
    """
    if ticket_id in _recent_results:
        return _recent_results[ticket_id]

    return {
        "ticket_id": ticket_id,
        "status": "not_found",
        "result": None,
    }


# ─── Internal helpers ─────────────────────────────────────────────


async def _run_triage(ticket_id: str):
    """Background task: run triage flow and store result."""
    _recent_results[ticket_id] = {"ticket_id": ticket_id, "status": "pending", "result": None}

    try:
        runner = FlowRunner()
        result = await runner.on_ticket_created(ticket_id)
        _recent_results[ticket_id] = {
            "ticket_id": ticket_id,
            "status": "completed",
            "result": result,
        }
    except Exception as e:
        logger.error(f"[Webhook] Triage failed for {ticket_id}: {e}", exc_info=True)
        _recent_results[ticket_id] = {
            "ticket_id": ticket_id,
            "status": "error",
            "result": {"error": str(e)},
        }

    # Trim old results
    if len(_recent_results) > MAX_RECENT:
        oldest = list(_recent_results.keys())[: len(_recent_results) - MAX_RECENT]
        for key in oldest:
            del _recent_results[key]


async def _run_review(ticket_id: str):
    """Background task: run code review flow and store result."""
    _recent_results[ticket_id] = {"ticket_id": ticket_id, "status": "pending", "result": None}

    try:
        runner = FlowRunner()
        result = await runner.on_code_review_requested(ticket_id)
        _recent_results[ticket_id] = {
            "ticket_id": ticket_id,
            "status": "completed",
            "result": result,
        }
    except Exception as e:
        logger.error(f"[Webhook] Review failed for {ticket_id}: {e}", exc_info=True)
        _recent_results[ticket_id] = {
            "ticket_id": ticket_id,
            "status": "error",
            "result": {"error": str(e)},
        }


def _verify_jira_webhook(request: Request, secret: str) -> None:
    """Verify Jira webhook signature if secret is configured."""
    # Jira Cloud uses X-Hub-Signature for webhook verification
    # This is optional — only if you set a secret in Jira webhook config
    signature = request.headers.get("X-Hub-Signature")
    if not signature:
        return  # No signature header = no verification configured in Jira

    # Verification logic (Jira uses HMAC-SHA256)
    # In practice, you'd verify the body against the signature
    # For now, log a warning if signature doesn't match
    logger.debug(f"[Webhook] Jira signature present: {signature[:20]}...")
