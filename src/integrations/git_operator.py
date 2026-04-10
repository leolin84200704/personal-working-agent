"""
Git Operator - Safe git operations with restricted permissions.

Enforces security rules:
- Only allowed branch prefixes: feature/leo/* or bugfix/leo/*
- No force push
- No direct push to main/master
- No destructive operations
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal
import subprocess
import re


class GitOperationError(Exception):
    """Raised when a git operation fails."""

    def __init__(self, message: str, command: str, output: str = ""):
        self.message = message
        self.command = command
        self.output = output
        super().__init__(f"{message}: {command}")


class BranchValidationError(GitOperationError):
    """Raised when branch name doesn't match required pattern."""


class GitOperator:
    """Safe git operations with enforced permissions."""

    ALLOWED_PREFIXES = ["feature/leo/", "bugfix/leo/"]
    PROTECTED_BRANCHES = ["main", "master", "develop", "staging"]
    BLOCKED_COMMANDS = ["push --force", "push -f", "reset --hard", "rm -rf"]

    def __init__(self, repo_path: Path, dry_run: bool = False):
        """
        Initialize GitOperator for a repository.

        Args:
            repo_path: Path to the git repository
            dry_run: If True, print commands without executing
        """
        self.repo_path = Path(repo_path)
        self.dry_run = dry_run
        self._validate_git_repo()

    def _validate_git_repo(self):
        """Check if the path is a valid git repository."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            raise GitOperationError(
                f"Not a git repository",
                str(self.repo_path),
            )

    def _run(self, command: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Run a git command safely.

        Args:
            command: Command parts as a list
            check: If True, raise exception on non-zero exit

        Returns:
            CompletedProcess with stdout/stderr
        """
        # Check for blocked commands
        cmd_str = " ".join(command)
        for blocked in self.BLOCKED_COMMANDS:
            if blocked in cmd_str:
                raise GitOperationError(
                    f"Blocked command for security reasons",
                    cmd_str,
                )

        if self.dry_run:
            print(f"[DRY RUN] {cmd_str}")
            return subprocess.CompletedProcess(command, 0, b"", b"")

        try:
            result = subprocess.run(
                command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            raise GitOperationError(
                f"Git command failed",
                cmd_str,
                e.stderr or e.stdout,
            )

    def validate_branch_name(self, branch_name: str, ticket_id: str) -> str:
        """
        Validate and generate proper branch name.

        Args:
            branch_name: Proposed branch name
            ticket_id: Jira ticket ID (e.g., LIS-123)

        Returns:
            Validated branch name with proper prefix

        Raises:
            BranchValidationError: If branch name doesn't match pattern
        """
        # Determine if it's a feature or bugfix based on ticket type or branch name
        ticket_type = self._infer_ticket_type(ticket_id, branch_name)
        prefix = f"{ticket_type}/leo/"

        # If already has correct prefix, return as-is
        if branch_name.startswith(prefix):
            return branch_name

        # Construct proper branch name
        if branch_name.startswith(ticket_type):
            # Has type but wrong prefix format
            clean_name = branch_name.split("/", 1)[-1]
            return f"{prefix}{ticket_id}/{clean_name}"
        else:
            # No type prefix
            return f"{prefix}{ticket_id}/{branch_name}"

    def _infer_ticket_type(self, ticket_id: str, branch_name: str) -> Literal["feature", "bugfix"]:
        """Infer if ticket is feature or bugfix from available info."""
        # Check branch name for hints
        branch_lower = branch_name.lower()
        if any(word in branch_lower for word in ["fix", "bug", "hotfix", "patch"]):
            return "bugfix"

        # Check ticket ID pattern
        if ticket_id.upper().startswith("BUG-"):
            return "bugfix"

        # Default to feature
        return "feature"

    def get_current_branch(self) -> str:
        """Get the current branch name."""
        result = self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip()

    def get_default_branch(self) -> str:
        """Get the default branch (main or master)."""
        # Try origin/main first, then origin/master
        for branch in ["main", "master"]:
            try:
                result = self._run(
                    ["git", "symbolic-ref", f"refs/remotes/origin/{branch}"],
                    check=False,
                )
                if result.returncode == 0:
                    return branch
            except GitOperationError:
                continue

        # Fallback: check local branches
        result = self._run(["git", "branch"])
        branches = [b.strip().replace("*", "").strip() for b in result.stdout.split("\n")]

        if "main" in branches:
            return "main"
        if "master" in branches:
            return "master"

        # Last resort: ask git
        result = self._run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"])
        return result.stdout.split("/")[-1].strip()

    def fetch(self, remote: str = "origin") -> None:
        """Fetch updates from remote."""
        self._run(["git", "fetch", remote])

    def checkout(self, branch: str, create: bool = False) -> None:
        """
        Checkout a branch.

        Args:
            branch: Branch name to checkout
            create: If True, create new branch with -b flag

        Raises:
            BranchValidationError: If trying to checkout protected branch directly
        """
        if branch in self.PROTECTED_BRANCHES and create:
            raise BranchValidationError(
                f"Cannot create protected branch: {branch}",
                f"git checkout -b {branch}",
            )

        cmd = ["git", "checkout"]
        if create:
            cmd.append("-b")
        cmd.append(branch)

        self._run(cmd)

    def create_branch(self, branch_name: str, ticket_id: str, base_branch: str | None = None) -> str:
        """
        Create a new branch with proper naming.

        Args:
            branch_name: Desired branch name (will be validated)
            ticket_id: Jira ticket ID
            base_branch: Base branch to create from (default: default branch)

        Returns:
            The created branch name
        """
        validated_name = self.validate_branch_name(branch_name, ticket_id)

        # Ensure we're on a clean state
        if base_branch is None:
            base_branch = self.get_default_branch()

        # First checkout base branch and pull
        self._run(["git", "checkout", base_branch])
        self._run(["git", "pull", "origin", base_branch])

        # Create new branch
        self._run(["git", "checkout", "-b", validated_name])

        return validated_name

    def add(self, files: list[str] | str = ".") -> None:
        """Stage files for commit."""
        if isinstance(files, str):
            files = [files]
        self._run(["git", "add"] + files)

    def commit(self, message: str, ticket_id: str = "") -> None:
        """
        Create a commit with formatted message.

        Args:
            message: Commit message
            ticket_id: Jira ticket ID to include in message
        """
        if ticket_id:
            formatted_msg = f"[{ticket_id}] {message}"
        else:
            formatted_msg = message

        self._run(["git", "commit", "-m", formatted_msg])

    def push(self, branch: str | None = None, remote: str = "origin") -> None:
        """
        Push branch to remote.

        Args:
            branch: Branch to push (default: current branch)
            remote: Remote name

        Raises:
            GitOperationError: If trying to push to protected branch
        """
        if branch is None:
            branch = self.get_current_branch()

        # Validate branch name before push
        if not any(branch.startswith(prefix) for prefix in self.ALLOWED_PREFIXES):
            raise GitOperationError(
                f"Cannot push branch without allowed prefix",
                f"git push {remote} {branch}",
            )

        self._run(["git", "push", "-u", remote, branch])

    def get_diff(self, cached: bool = False) -> str:
        """
        Get git diff output.

        Args:
            cached: If True, show staged changes (git diff --cached)

        Returns:
            Diff output as string
        """
        cmd = ["git", "diff"]
        if cached:
            cmd.append("--cached")
        cmd.append("--color=never")

        result = self._run(cmd)
        return result.stdout

    def get_status(self) -> str:
        """Get git status output."""
        result = self._run(["git", "status", "--short"])
        return result.stdout

    def has_changes(self) -> bool:
        """Check if there are any uncommitted changes."""
        return bool(self.get_status().strip())

    def get_commits(self, count: int = 10) -> list[dict[str, str]]:
        """
        Get recent commits.

        Args:
            count: Number of commits to retrieve

        Returns:
            List of commit dicts with hash, message, author
        """
        result = self._run([
            "git", "log",
            f"-{count}",
            "--pretty=format:%H|%s|%an"
        ])

        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 3:
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "author": parts[2],
                    })

        return commits

    def find_files_by_pattern(self, pattern: str, file_pattern: str = "*") -> list[Path]:
        """
        Find files matching a pattern using git grep.

        Args:
            pattern: Regex pattern to search in file contents
            file_pattern: Glob pattern for filenames

        Returns:
            List of matching file paths
        """
        try:
            result = self._run([
                "git", "grep", "-l",
                "--untracked",
                pattern,
                "--", file_pattern
            ], check=False)

            if result.returncode != 0:
                return []

            return [
                self.repo_path / f
                for f in result.stdout.strip().split("\n")
                if f
            ]
        except GitOperationError:
            return []

    def get_files_touched(self, since: str = "HEAD~10") -> list[Path]:
        """
        Get list of files changed in recent commits.

        Args:
            since: Git revision specifier

        Returns:
            List of file paths
        """
        result = self._run([
            "git", "diff", "--name-only", since
        ])

        return [
            self.repo_path / f
            for f in result.stdout.strip().split("\n")
            if f
        ]

    def create_summary(self) -> dict:
        """Create a summary of the repository state."""
        return {
            "path": str(self.repo_path),
            "current_branch": self.get_current_branch(),
            "default_branch": self.get_default_branch(),
            "has_changes": self.has_changes(),
            "status": self.get_status(),
        }


def find_git_repos(base_path: Path) -> list[Path]:
    """
    Find all git repositories under a base path.

    Args:
        base_path: Base directory to search

    Returns:
        List of paths to git repositories
    """
    repos = []

    for item in base_path.iterdir():
        if not item.is_dir():
            continue

        # Skip hidden directories
        if item.name.startswith("."):
            continue

        # Check if it's a git repo
        git_dir = item / ".git"
        if git_dir.exists() and git_dir.is_dir():
            repos.append(item)

    return repos


# Thread-safe Git operations for backend service
from threading import Lock


class ThreadSafeGitOperator(GitOperator):
    """
    Thread-safe wrapper around GitOperator.

    Ensures that concurrent operations on the same repository
    are serialized to avoid conflicts.
    """

    # Class-level locks for each repo path
    _repo_locks: dict[Path, Lock] = {}
    _global_lock = Lock()

    def __init__(self, repo_path: Path, dry_run: bool = False):
        """Initialize with thread-safe locking."""
        super().__init__(repo_path, dry_run)

        # Get or create lock for this repo
        with ThreadSafeGitOperator._global_lock:
            # Normalize path for consistent locking
            normalized_path = repo_path.resolve()
            if normalized_path not in ThreadSafeGitOperator._repo_locks:
                ThreadSafeGitOperator._repo_locks[normalized_path] = Lock()
            self._lock = ThreadSafeGitOperator._repo_locks[normalized_path]

    def _run(self, command: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run git command with lock for thread safety."""
        with self._lock:
            return super()._run(command, check)

    def create_branch(self, branch_name: str, ticket_id: str, base_branch: str | None = None) -> str:
        """Create branch with lock."""
        with self._lock:
            return super().create_branch(branch_name, ticket_id, base_branch)

    def commit(self, message: str, ticket_id: str = "") -> None:
        """Commit with lock."""
        with self._lock:
            return super().commit(message, ticket_id)

    def push(self, branch: str | None = None, remote: str = "origin") -> None:
        """Push with lock."""
        with self._lock:
            return super().push(branch, remote)

    def checkout(self, branch: str, create: bool = False) -> None:
        """Checkout with lock."""
        with self._lock:
            return super().checkout(branch, create)

    def add(self, files: list[str] | str = ".") -> None:
        """Add files with lock."""
        with self._lock:
            return super().add(files)

    @classmethod
    def get_lock_stats(cls) -> dict[str, int]:
        """Get statistics about repository locks."""
        with cls._global_lock:
            return {
                "total_repos_locked": len(cls._repo_locks),
                "repos": [str(p) for p in cls._repo_locks.keys()],
            }

    @classmethod
    def clear_locks(cls) -> None:
        """Clear all locks (use with caution, mostly for testing)."""
        with cls._global_lock:
            cls._repo_locks.clear()
