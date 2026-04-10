"""
Git Skill - Safe Git operations.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from src.skills.base import Skill
from src.integrations.git_operator import GitOperator, find_git_repos
from src.memory.manager import MemoryManager
from src.config import get_settings


class GitSkill(Skill):
    """Skill for safe Git operations."""

    def __init__(self, claude: Anthropic, memory: MemoryManager):
        super().__init__(claude, memory)
        self.settings = get_settings()
        self.repos = {r.name: r for r in find_git_repos(self.settings.repos_base_path)}

    async def get_status(self, repo: str | None = None) -> dict[str, Any]:
        """Get git status for a repo."""
        if repo and repo in self.repos:
            repo_path = self.repos[repo]
        elif not repo and len(self.repos) == 1:
            repo_path = list(self.repos.values())[0]
        else:
            return {
                "status": "error",
                "response": f"Please specify a repo. Available: {', '.join(list(self.repos.keys())[:5])}",
            }

        try:
            git_op = GitOperator(repo_path, dry_run=False)
            status = git_op._run(["git", "status", "--short"], check=False)

            return {
                "status": "success",
                "response": f"Status for {repo}:\n```\n{status.stdout}\n```",
                "data": {"repo": repo, "status": status.stdout},
            }
        except Exception as e:
            return {
                "status": "error",
                "response": f"Failed to get status: {str(e)}",
                "error": str(e),
            }

    async def create_branch(self, repo: str, branch_name: str, ticket_id: str = "") -> dict[str, Any]:
        """Create a new branch."""
        if repo not in self.repos:
            return {
                "status": "error",
                "response": f"Repo not found: {repo}",
            }

        try:
            repo_path = self.repos[repo]
            git_op = GitOperator(repo_path, dry_run=False)

            # Validate and create branch
            full_branch_name = git_op.validate_branch_name(branch_name, ticket_id)
            git_op.create_branch(full_branch_name, ticket_id)

            return {
                "status": "success",
                "response": f"Created branch: {full_branch_name}",
                "data": {"repo": repo, "branch": full_branch_name},
            }
        except Exception as e:
            return {
                "status": "error",
                "response": f"Failed to create branch: {str(e)}",
                "error": str(e),
            }

    async def execute(self, action: str = "status", **kwargs) -> dict[str, Any]:
        """Execute a Git action."""
        if action == "status":
            return await self.get_status(kwargs.get("repo"))
        elif action == "branch":
            return await self.create_branch(
                kwargs.get("repo", ""),
                kwargs.get("branch_name", ""),
                kwargs.get("ticket_id", ""),
            )
        else:
            return {
                "status": "error",
                "response": f"Unknown action: {action}",
            }
