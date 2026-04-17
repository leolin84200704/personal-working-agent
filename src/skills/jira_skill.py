"""
Jira Skill - Interact with Jira tickets.
"""
from __future__ import annotations

from typing import Any

from anthropic import Anthropic

from src.config import get_settings
from src.skills.base import Skill
from src.integrations.jira import JiraClient
from src.memory.manager import MemoryManager


class JiraSkill(Skill):
    """Skill for interacting with Jira tickets."""

    def __init__(self, claude: Anthropic, memory: MemoryManager):
        super().__init__(claude, memory)
        self.jira = JiraClient()

    async def analyze_ticket(self, ticket_id: str) -> dict[str, Any]:
        """Analyze a Jira ticket."""
        try:
            ticket = self.jira.get_ticket(ticket_id)

            # Use Claude to analyze the ticket
            prompt = f"""Analyze this Jira ticket:

## Ticket: {ticket.key}
**Summary**: {ticket.summary}
**Type**: {ticket.issue_type}
**Status**: {ticket.status}
**Priority**: {ticket.priority or 'N/A'}

**Description**:
{ticket.description[:1000]}

**Labels**: {', '.join(ticket.labels) or 'None'}
**Components**: {', '.join(ticket.components) or 'None'}

Provide a brief analysis in Traditional Chinese:
1. What is this ticket asking for?
2. Which repos might need changes?
3. What type of work is this? (feature, bugfix, config change, etc.)
4. Any concerns or clarifications needed?

Be concise."""

            response = self.claude.messages.create(
                model=get_settings().default_model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            analysis = response.content[0].text

            return {
                "status": "success",
                "response": analysis,
                "data": {
                    "ticket": ticket_id,
                    "summary": ticket.summary,
                    "status": ticket.status,
                    "type": ticket.issue_type,
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "response": f"Failed to analyze ticket {ticket_id}: {str(e)}",
                "error": str(e),
            }

    async def scan_tickets(self, limit: int = 10) -> dict[str, Any]:
        """Scan for new assigned tickets."""
        try:
            tickets = self.jira.get_assigned_tickets(limit=limit)

            if not tickets:
                return {
                    "status": "success",
                    "response": "No new tickets found assigned to you.",
                    "data": {"tickets": []},
                }

            # Format ticket list
            ticket_list = "\n".join([
                f"• **{t.key}**: {t.summary} ({t.status})"
                for t in tickets[:5]
            ])

            return {
                "status": "success",
                "response": f"Found {len(tickets)} ticket(s):\n\n{ticket_list}",
                "data": {
                    "tickets": [
                        {
                            "key": t.key,
                            "summary": t.summary,
                            "status": t.status,
                            "type": t.issue_type,
                        }
                        for t in tickets
                    ]
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "response": f"Failed to scan tickets: {str(e)}",
                "error": str(e),
            }

    async def execute(self, action: str = "scan", **kwargs) -> dict[str, Any]:
        """Execute a Jira action."""
        if action == "scan":
            return await self.scan_tickets()
        elif action == "analyze":
            return await self.analyze_ticket(kwargs.get("ticket_id", ""))
        else:
            return {
                "status": "error",
                "response": f"Unknown action: {action}",
            }
