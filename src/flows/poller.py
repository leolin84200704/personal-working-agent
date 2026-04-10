"""
Jira Poller — Polls Jira for new tickets and triggers triage flows.

Replaces webhook-based triggering when the agent runs on localhost
without a public URL. Checks every N minutes for newly created tickets.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from src.config import get_settings
from src.flows.runner import FlowRunner
from src.utils.logger import get_logger

logger = get_logger()
settings = get_settings()


class JiraPoller:
    """
    Polls Jira API for new tickets at a configurable interval.

    Keeps track of which tickets have already been processed to avoid
    re-triggering triage on the same ticket.

    Usage:
        poller = JiraPoller()
        await poller.start()  # runs forever, checking every poll_interval_minutes
    """

    def __init__(self, poll_interval_minutes: int = 60):
        self.poll_interval = poll_interval_minutes
        self.runner = FlowRunner()

        # Track processed tickets to avoid duplicates
        self._state_file = settings.storage_path / "poller_state.json"
        self._processed: set[str] = self._load_state()

    def _load_state(self) -> set[str]:
        """Load previously processed ticket IDs from disk."""
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                return set(data.get("processed", []))
            except Exception:
                return set()
        return set()

    def _save_state(self) -> None:
        """Persist processed ticket IDs to disk."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        # Keep only the last 500 IDs to prevent unbounded growth
        recent = sorted(self._processed)[-500:]
        self._state_file.write_text(
            json.dumps({"processed": recent, "updated": datetime.now().isoformat()}),
            encoding="utf-8",
        )

    def _fetch_recent_tickets(self) -> list[dict[str, str]]:
        """
        Query Jira for tickets created in the last poll interval.

        Returns list of {key, summary, created} dicts.
        """
        # JQL: tickets created in the last N minutes, assigned to me
        jql = (
            f"assignee = currentUser() "
            f"AND created >= -{self.poll_interval}m "
            f"ORDER BY created DESC"
        )

        url = f"{settings.jira_server}/rest/api/3/search/jql"
        auth = (settings.jira_email, settings.jira_api_token)
        params = {
            "jql": jql,
            "maxResults": 20,
            "fields": "summary,created",
        }

        try:
            response = requests.get(url, params=params, auth=auth, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"[Poller] Jira query failed: {e}")
            return []

        tickets = []
        for issue in data.get("issues", []):
            tickets.append({
                "key": issue["key"],
                "summary": issue.get("fields", {}).get("summary", ""),
                "created": issue.get("fields", {}).get("created", ""),
            })

        return tickets

    async def poll_once(self) -> list[dict[str, Any]]:
        """
        Run a single poll cycle.

        Returns list of triage results for newly found tickets.
        """
        tickets = self._fetch_recent_tickets()

        if not tickets:
            logger.debug("[Poller] No new tickets found")
            return []

        # Filter out already processed tickets
        new_tickets = [t for t in tickets if t["key"] not in self._processed]

        if not new_tickets:
            logger.debug(f"[Poller] {len(tickets)} tickets found, all already processed")
            return []

        logger.info(f"[Poller] Found {len(new_tickets)} new ticket(s): {[t['key'] for t in new_tickets]}")

        results = []
        for ticket in new_tickets:
            ticket_id = ticket["key"]
            try:
                logger.info(f"[Poller] Triggering triage for {ticket_id}: {ticket['summary']}")
                result = await self.runner.on_ticket_created(ticket_id)
                results.append(result)
                self._processed.add(ticket_id)
            except Exception as e:
                logger.error(f"[Poller] Triage failed for {ticket_id}: {e}", exc_info=True)
                # Still mark as processed to avoid retrying a broken ticket forever
                self._processed.add(ticket_id)

        self._save_state()
        return results

    async def start(self) -> None:
        """
        Start the polling loop. Runs forever until interrupted.

        Checks Jira every poll_interval_minutes for new tickets.
        """
        logger.info(
            f"[Poller] Started — checking Jira every {self.poll_interval} minutes. "
            f"{len(self._processed)} tickets already processed."
        )

        while True:
            try:
                await self.poll_once()
            except Exception as e:
                logger.error(f"[Poller] Unexpected error: {e}", exc_info=True)

            # Wait for next poll
            await asyncio.sleep(self.poll_interval * 60)
