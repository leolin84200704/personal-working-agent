"""
Jira Integration - Connect to Jira API and fetch tickets.

Supports:
- Fetching assigned tickets
- Parsing ticket descriptions
- Determining ticket type (feature vs bugfix)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Optional
from jira import JIRA, Issue
from dotenv import load_dotenv

load_dotenv()


@dataclass
class JiraTicket:
    """Represents a Jira ticket with relevant information."""

    key: str
    summary: str
    description: str
    status: str
    issue_type: str
    priority: str | None
    assignee: str | None
    reporter: str | None
    labels: list[str]
    components: list[str]
    attachments: list[dict[str, Any]]  # List of attachment metadata

    @property
    def is_bug(self) -> bool:
        """Determine if this is a bug/bugfix ticket."""
        type_lower = self.issue_type.lower()
        return any(word in type_lower for word in ["bug", "defect", "fault"])

    @property
    def is_feature(self) -> bool:
        """Determine if this is a feature ticket."""
        type_lower = self.issue_type.lower()
        return any(word in type_lower for word in ["feature", "story", "enhancement"])

    @property
    def ticket_type(self) -> Literal["bugfix", "feature"]:
        """Get the ticket type for branch naming."""
        return "bugfix" if self.is_bug else "feature"

    @property
    def branch_name(self) -> str:
        """Generate a branch name from the ticket."""
        # Clean the summary for use in branch name
        clean_summary = self.summary.lower()
        clean_summary = clean_summary.replace(" ", "-")
        # Remove special characters
        clean_summary = "".join(
            c for c in clean_summary
            if c.isalnum() or c in "-_"
        )
        # Limit length
        clean_summary = clean_summary[:50]

        return f"{self.ticket_type}/leo/{self.key}/{clean_summary}"

    def get_context(self) -> str:
        """Get ticket context for processing."""
        return f"""# Ticket: {self.key}

## Summary
{self.summary}

## Description
{self.description}

## Metadata
- Type: {self.issue_type}
- Status: {self.status}
- Priority: {self.priority or 'None'}
- Labels: {', '.join(self.labels) or 'None'}
- Components: {', '.join(self.components) or 'None'}
"""


class JiraClient:
    """Client for interacting with Jira API."""

    def __init__(
        self,
        server: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ):
        """
        Initialize Jira client.

        Args:
            server: Jira server URL
            email: Account email
            api_token: Jira API token
        """
        self.server = server or os.getenv("JIRA_SERVER")
        self.email = email or os.getenv("JIRA_EMAIL")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN")

        if not all([self.server, self.email, self.api_token]):
            raise ValueError(
                "Jira credentials not provided. "
                "Set JIRA_SERVER, JIRA_EMAIL, and JIRA_API_TOKEN environment variables."
            )

        self._client: JIRA | None = None

    @property
    def client(self) -> JIRA:
        """Get or create JIRA client instance."""
        if self._client is None:
            # Jira Cloud uses email + API token as basic auth
            # Use API v3 to avoid deprecation warnings
            self._client = JIRA(
                server=self.server,
                basic_auth=(self.email, self.api_token),
                options={"rest_api_version": "3"}
            )
        return self._client

    def get_ticket(self, key: str) -> JiraTicket:
        """
        Fetch a single ticket by key.

        Args:
            key: Ticket key (e.g., LIS-123)

        Returns:
            JiraTicket object
        """
        import requests

        # Request attachment field
        url = f"{self.server}/rest/api/3/issue/{key}?fields=summary,description,status,issuetype,priority,assignee,reporter,labels,components,attachment"
        auth = (self.email, self.api_token)

        response = requests.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()

        expanded_issue = self._expand_issue(data)
        return self._parse_issue(expanded_issue)

    def download_attachment(self, attachment_url: str, save_path: Path | None = None) -> Path:
        """
        Download an attachment from Jira.

        Args:
            attachment_url: URL to the attachment content
            save_path: Where to save (default: current directory with original filename)

        Returns:
            Path to downloaded file
        """
        import requests
        from urllib.parse import urlparse

        # Parse filename from URL if not provided
        if save_path is None:
            # URL looks like: .../attachment/content/12345
            # We need to get the filename from the attachment metadata first
            save_path = Path(attachment_url.split("/")[-1])

        # Make request with auth
        response = requests.get(attachment_url, auth=(self.email, self.api_token))
        response.raise_for_status()

        # Save file
        save_path = Path(save_path)
        save_path.write_bytes(response.content)

        return save_path

    def get_assigned_tickets(
        self,
        assignee: str | None = None,
        status: str | None = None,
        project: str | None = None,
        limit: int = 50,
    ) -> list[JiraTicket]:
        """
        Fetch tickets assigned to a user.

        Args:
            assignee: User email or username (default: authenticated user)
            status: Filter by status (e.g., "In Progress")
            project: Filter by project key
            limit: Maximum number of tickets to return

        Returns:
            List of JiraTicket objects
        """
        import requests

        jql = "assignee is not EMPTY"

        if assignee:
            jql += f" AND assignee = '{assignee}'"
        else:
            # Use current user
            jql += " AND assignee = currentUser()"

        if status:
            jql += f" AND status = '{status}'"
        else:
            # Default to open tickets
            jql += " AND status NOT IN (Closed, Done, Resolved)"

        if project:
            jql += f" AND project = '{project}'"

        # Add ordering
        jql += " ORDER BY priority DESC, created DESC"

        # Use REST API v3 search/jql endpoint directly
        url = f"{self.server}/rest/api/3/search/jql"

        auth = (self.email, self.api_token)
        params = {
            "jql": jql,
            "maxResults": limit,
            "fields": "*all"
        }

        response = requests.get(url, params=params, auth=auth)
        response.raise_for_status()
        data = response.json()

        # Parse issues
        tickets = []
        for issue in data.get("issues", []):
            # Expand the issue data to match JIRA library format
            expanded_issue = self._expand_issue(issue)
            tickets.append(self._parse_issue(expanded_issue))

        return tickets

    def _expand_issue(self, issue_data: dict) -> Any:
        """Expand issue data from REST API response to match JIRA library format."""
        # Helper to extract text from Atlassian Document Format (ADF)
        def extract_adf_text(adf_obj):
            """Extract plain text from ADF content object."""
            if not adf_obj:
                return ""
            if isinstance(adf_obj, str):
                return adf_obj
            if isinstance(adf_obj, dict):
                # ADF format: {type: "doc", content: [...]}
                if adf_obj.get("type") == "doc":
                    content = adf_obj.get("content", [])
                    return extract_adf_text(content)
                # Text node: {type: "text", text: "..."}
                elif adf_obj.get("type") == "text":
                    return adf_obj.get("text", "")
                # Paragraph with content
                elif "content" in adf_obj:
                    return extract_adf_text(adf_obj["content"])
            elif isinstance(adf_obj, list):
                return " ".join(extract_adf_text(item) for item in adf_obj)
            return ""

        # Create a simple object to match the expected structure
        class ExpandedIssue:
            def __init__(self, data):
                self.key = data.get("key", "")
                self.id = data.get("id", "")
                self.fields = self._expand_fields(data.get("fields", {}), extract_adf_text)

            def _expand_fields(self, fields, extract_fn):
                class Fields:
                    def __init__(self, f, extract):
                        self.summary = f.get("summary", "")

                        # Description - handle ADF format
                        desc_data = f.get("description")
                        if desc_data:
                            if isinstance(desc_data, dict):
                                self.description = extract(desc_data)
                            else:
                                self.description = str(desc_data) if desc_data else ""
                        else:
                            self.description = ""

                        # Status
                        status_data = f.get("status")
                        if status_data:
                            self.status = type('Status', (), {'name': status_data.get('name')})()
                        else:
                            self.status = None

                        # Issue type
                        issuetype_data = f.get("issuetype")
                        if issuetype_data:
                            self.issuetype = type('Issuetype', (), {'name': issuetype_data.get('name')})()
                        else:
                            self.issuetype = None

                        # Priority
                        priority_data = f.get("priority")
                        if priority_data:
                            self.priority = type('Priority', (), {'name': priority_data.get('name')})()
                        else:
                            self.priority = None

                        # Assignee
                        assignee_data = f.get("assignee")
                        if assignee_data:
                            self.assignee = type('Assignee', (), {'displayName': assignee_data.get('displayName')})()
                        else:
                            self.assignee = None

                        # Reporter
                        reporter_data = f.get("reporter")
                        if reporter_data:
                            self.reporter = type('Reporter', (), {'displayName': reporter_data.get('displayName')})()
                        else:
                            self.reporter = None

                        # Labels
                        self.labels = f.get("labels", [])

                        # Components
                        components_data = f.get("components", [])
                        self.components = [type('Component', (), {'name': c.get('name')})() for c in components_data]

                        # Attachments
                        attachments_data = f.get("attachment", [])
                        self.attachment = [
                            type('Attachment', (), {
                                'id': a.get('id'),
                                'filename': a.get('filename'),
                                'content': a.get('content'),
                                'size': a.get('size'),
                                'mimeType': a.get('mimeType'),
                            })()
                            for a in attachments_data
                        ]

                return Fields(fields, extract_fn)

        return ExpandedIssue(issue_data)

    def _parse_issue(self, issue: Issue) -> JiraTicket:
        """Parse a JIRA Issue into JiraTicket."""
        # Handle attachments
        attachments = []
        if hasattr(issue.fields, "attachment") and issue.fields.attachment:
            for att in issue.fields.attachment:
                attachments.append({
                    "id": att.id,
                    "filename": att.filename,
                    "content": att.content,  # URL to download
                    "size": att.size,
                    "mimeType": att.mimeType,
                })

        return JiraTicket(
            key=issue.key,
            summary=issue.fields.summary or "",
            description=issue.fields.description or "",
            status=issue.fields.status.name if hasattr(issue.fields, "status") else "Unknown",
            issue_type=issue.fields.issuetype.name if hasattr(issue.fields, "issuetype") else "Unknown",
            priority=issue.fields.priority.name if hasattr(issue.fields, "priority") else None,
            assignee=issue.fields.assignee.displayName if hasattr(issue.fields, "assignee") and issue.fields.assignee else None,
            reporter=issue.fields.reporter.displayName if hasattr(issue.fields, "reporter") else None,
            labels=issue.fields.labels if hasattr(issue.fields, "labels") else [],
            components=[c.name for c in issue.fields.components] if hasattr(issue.fields, "components") else [],
            attachments=attachments,
        )

    def search_tickets(
        self,
        query: str,
        project: str | None = None,
        limit: int = 20,
    ) -> list[JiraTicket]:
        """
        Search for tickets using JQL.

        Args:
            query: Search query for summary/description
            project: Filter by project key
            limit: Maximum number of tickets to return

        Returns:
            List of JiraTicket objects
        """
        import requests

        jql = f'text ~ "{query}"'

        if project:
            jql += f' AND project = "{project}"'

        # Only open tickets
        jql += ' AND status NOT IN (Closed, Done, Resolved)'

        # Use REST API v3 search/jql endpoint
        url = f"{self.server}/rest/api/3/search/jql"

        auth = (self.email, self.api_token)
        params = {
            "jql": jql,
            "maxResults": limit,
            "fields": "*all"
        }

        response = requests.get(url, params=params, auth=auth)
        response.raise_for_status()
        data = response.json()

        tickets = []
        for issue in data.get("issues", []):
            expanded_issue = self._expand_issue(issue)
            tickets.append(self._parse_issue(expanded_issue))

        return tickets

    def add_comment(self, key: str, comment: str) -> None:
        """Add a comment to a ticket."""
        self.client.add_comment(key, comment)

    def transition_status(self, key: str, status: str) -> None:
        """
        Transition ticket to a new status.

        Args:
            key: Ticket key
            status: Target status name
        """
        issue = self.client.issue(key)
        transitions = self.client.transitions(issue)

        # Find the transition to the target status
        for transition in transitions:
            if status.lower() in transition["name"].lower():
                self.client.transition_issue(issue, transition["id"])
                return

        raise ValueError(f"No transition found to status: {status}")

    def get_projects(self) -> list[dict[str, str]]:
        """
        Get list of accessible projects.

        Returns:
            List of project dicts with key, name, url
        """
        projects = self.client.projects()
        return [
            {
                "key": p.key,
                "name": p.name,
                "url": f"{self.server}/browse/{p.key}",
            }
            for p in projects
        ]

    def guess_repos_from_ticket(self, ticket: JiraTicket) -> list[str]:
        """
        Guess which repos might be relevant based on ticket info.

        Args:
            ticket: JiraTicket to analyze

        Returns:
            List of repo names that might be relevant
        """
        repos = []

        # Check project key
        project = ticket.key.split("-")[0]

        # Map project to likely repos
        project_repo_map = {
            "LIS": [
                "LIS-transformer",
                "LIS-transformer-v2",
                "lis-backend-emr-v2",
                "LIS-backend-v2-order-management",
                "LIS-backend-v2-coreSamples",
                "LIS-backend-coreSamples",
                "LIS-backend-billing",
                "LIS-setting-consumer",
            ],
            "EMR": [
                "EMR-Backend",
                "lis-backend-emr-v2",
            ],
            "EHR": [
                "EHR-backend",
            ],
            "VP": [  # Vibrant Phlebotomy
                "LIS-transformer-v2",
                "LIS-setting-consumer",
            ],
        }

        repos.extend(project_repo_map.get(project, []))

        # Check components
        component_keywords = {
            "transformer": "LIS-transformer",
            "hl7": "LIS-transformer",
            "order": "LIS-backend-v2-order-management",
            "sample": "LIS-backend-v2-coreSamples",
            "billing": "LIS-backend-billing",
            "emr": "EMR-Backend",
            "calendar": "Portal-Calendar",
            "setting": "LIS-setting-consumer",
        }

        description_lower = (ticket.description or "").lower()
        summary_lower = (ticket.summary or "").lower()

        for keyword, repo in component_keywords.items():
            if keyword in description_lower or keyword in summary_lower:
                if repo not in repos:
                    repos.append(repo)

        return repos
