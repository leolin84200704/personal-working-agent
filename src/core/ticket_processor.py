"""
Ticket Processor - Main workflow for processing Jira tickets.

Orchestrates:
1. Fetching tickets from Jira
2. Analyzing which repos to modify
3. Creating branches
4. Making changes
5. Committing and pushing
6. Generating reports
"""
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from typing import Literal

from anthropic import Anthropic
from dotenv import load_dotenv

from ..integrations.jira import JiraClient, JiraTicket
from ..integrations.git_operator import GitOperator, find_git_repos
from ..memory.manager import MemoryManager

load_dotenv()


class TicketProcessor:
    """Main processor for handling Jira tickets end-to-end."""

    def __init__(
        self,
        jira_client: JiraClient | None = None,
        repos_base_path: Path | None = None,
        dry_run: bool = False,
    ):
        """
        Initialize TicketProcessor.

        Args:
            jira_client: JiraClient instance
            repos_base_path: Base path containing all repos
            dry_run: If True, don't make actual changes
        """
        self.jira = jira_client or JiraClient()
        self.repos_base_path = Path(repos_base_path or os.getenv("REPOS_BASE_PATH", "/Users/hung.l/src"))
        self.dry_run = dry_run
        self.memory = MemoryManager()

        # Initialize Claude for analysis (supports z.ai proxy)
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        # Support for z.ai proxy or other custom base URLs
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        if base_url:
            self.claude = Anthropic(api_key=api_key, base_url=base_url)
        else:
            self.claude = Anthropic(api_key=api_key)

        # Discover repos
        self.repos = {r.name: r for r in find_git_repos(self.repos_base_path)}

    def scan_tickets(self, limit: int = 10) -> list[JiraTicket]:
        """
        Scan for assigned tickets that need processing.

        Args:
            limit: Maximum number of tickets to fetch

        Returns:
            List of tickets to process
        """
        print(f"Scanning for assigned tickets...")
        tickets = self.jira.get_assigned_tickets(limit=limit)

        # Filter out already processed tickets (could check git branches)
        filtered = []
        for ticket in tickets:
            # Check if branch already exists for this ticket
            branch_exists = self._branch_exists_for_ticket(ticket)
            if not branch_exists:
                filtered.append(ticket)

        print(f"Found {len(filtered)} new tickets to process")
        return filtered

    def _branch_exists_for_ticket(self, ticket: JiraTicket) -> bool:
        """Check if a branch already exists for this ticket."""
        for repo_path in self.repos.values():
            try:
                git_op = GitOperator(repo_path, dry_run=True)
                # List all branches
                result = git_op._run(["git", "branch", "-a"], check=False)
                if ticket.key in result.stdout:
                    return True
            except Exception:
                continue
        return False

    def analyze_ticket(self, ticket: JiraTicket) -> dict:
        """
        Analyze a ticket to determine what needs to be done.

        Args:
            ticket: JiraTicket to analyze

        Returns:
            Dict with analysis results including repos to modify and changes needed
        """
        print(f"\nAnalyzing ticket {ticket.key}: {ticket.summary}")

        # Get relevant repos from Jira info
        suggested_repos = self.jira.guess_repos_from_ticket(ticket)

        # Filter to repos that actually exist
        available_repos = [r for r in suggested_repos if r in self.repos]

        if not available_repos:
            print(f"Warning: No repos found for ticket {ticket.key}")
            print(f"Suggested: {suggested_repos}")
            print(f"Available: {list(self.repos.keys())}")
            return {
                "ticket": ticket,
                "repos": [],
                "confidence": "low",
                "reason": "No matching repos found",
            }

        # Use Claude to analyze which repos need changes
        repo_context = self._build_repo_context(available_repos)

        prompt = f"""You are analyzing a Jira ticket to determine which repositories need to be modified.

## Ticket Information
{ticket.get_context()}

## Available Repositories
{repo_context}

## Agent Identity
{self.memory.read_identity()}

## Agent User Preferences
{self.memory.read_user()}

## Task
Analyze this ticket and determine:
1. Which repos need to be modified (list all that apply)
2. What files might need changes (be specific based on the repo context)
3. What type of changes are needed (new feature, bug fix, config change, etc.)
4. Your confidence level (high/medium/low)

Respond in JSON format:
{{
    "repos": ["repo1", "repo2"],
    "files": {{
        "repo1": ["path/to/file1.py", "path/to/file2.py"],
        "repo2": ["path/to/file3.ts"]
    }},
    "change_type": "feature|bugfix|config|docs",
    "confidence": "high|medium|low",
    "reasoning": "Brief explanation of your analysis"
}}
"""

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            import json
            content = response.content[0].text

            # Try to extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            analysis = json.loads(content)

            print(f"  Analysis: {analysis.get('confidence', 'unknown')} confidence")
            print(f"  Repos to modify: {analysis.get('repos', [])}")

            return {
                "ticket": ticket,
                "repos": analysis.get("repos", available_repos),
                "files": analysis.get("files", {}),
                "change_type": analysis.get("change_type", "unknown"),
                "confidence": analysis.get("confidence", "medium"),
                "reasoning": analysis.get("reasoning", ""),
            }

        except Exception as e:
            print(f"  Error in analysis: {e}")
            print(f"  Falling back to suggested repos: {available_repos}")

            return {
                "ticket": ticket,
                "repos": available_repos,
                "files": {},
                "change_type": "bugfix" if ticket.is_bug else "feature",
                "confidence": "low",
                "reasoning": f"Analysis failed: {e}",
            }

    def _build_repo_context(self, repo_names: list[str]) -> str:
        """Build context string about the repos."""
        context_parts = []

        for name in repo_names:
            if name not in self.repos:
                continue

            repo_path = self.repos[name]

            # Try to read README
            readme_path = repo_path / "README.md"
            readme = ""
            if readme_path.exists():
                readme = readme_path.read_text(encoding="utf-8")[:500]

            # Get language/framework from common files
            language = self._detect_repo_language(repo_path)

            context_parts.append(f"""
### {name}
- Path: {repo_path}
- Language: {language}
{f"- README: {readme[:200]}..." if readme else ""}
""")

        return "\n".join(context_parts)

    def _detect_repo_language(self, repo_path: Path) -> str:
        """Detect the primary language of a repo."""
        # Check for common indicators
        if (repo_path / "pom.xml").exists():
            return "Java (Maven)"
        if (repo_path / "build.gradle").exists():
            return "Java (Gradle)"
        if (repo_path / "package.json").exists():
            return "TypeScript/JavaScript"
        if (repo_path / "requirements.txt").exists() or (repo_path / "pyproject.toml").exists():
            return "Python"

        # Count file extensions
        from collections import Counter
        extensions = Counter()

        for file in repo_path.rglob("*"):
            if file.is_file() and not file.name.startswith("."):
                ext = file.suffix
                if ext:
                    extensions[ext] += 1

        if extensions:
            most_common = extensions.most_common(1)[0][0]
            lang_map = {
                ".py": "Python",
                ".java": "Java",
                ".ts": "TypeScript",
                ".js": "JavaScript",
                ".go": "Go",
                ".rs": "Rust",
            }
            return lang_map.get(most_common, "Unknown")

        return "Unknown"

    def process_ticket(self, ticket: JiraTicket) -> dict:
        """
        Process a ticket from start to finish.

        Args:
            ticket: JiraTicket to process

        Returns:
            Dict with processing results
        """
        print(f"\n{'='*60}")
        print(f"Processing ticket: {ticket.key}")
        print(f"Summary: {ticket.summary}")
        print(f"{'='*60}")

        # Analyze the ticket
        analysis = self.analyze_ticket(ticket)

        if not analysis["repos"]:
            return {
                "status": "skipped",
                "reason": "No repos identified for changes",
                "analysis": analysis,
            }

        results = {
            "ticket": ticket.key,
            "analysis": analysis,
            "branches": [],
            "changes": {},
            "errors": [],
        }

        # Process each repo
        for repo_name in analysis["repos"]:
            if repo_name not in self.repos:
                results["errors"].append(f"Repo not found: {repo_name}")
                continue

            repo_path = self.repos[repo_name]
            result = self._process_repo(ticket, repo_name, repo_path, analysis)
            results["branches"].append(result["branch"])
            results["changes"][repo_name] = result

        # Generate report
        self._generate_report(results)

        return results

    def _process_repo(
        self,
        ticket: JiraTicket,
        repo_name: str,
        repo_path: Path,
        analysis: dict,
    ) -> dict:
        """Process a ticket for a single repo."""
        result = {
            "repo": repo_name,
            "branch": None,
            "changes": [],
            "commit": None,
            "pushed": False,
            "errors": [],
        }

        try:
            git_op = GitOperator(repo_path, dry_run=self.dry_run)

            # Create branch
            branch_name = git_op.validate_branch_name(
                ticket.summary.replace(" ", "-").lower()[:50],
                ticket.key,
            )

            print(f"\n  Creating branch: {branch_name}")
            git_op.create_branch(branch_name, ticket.key)

            result["branch"] = branch_name

            # Determine what files to change
            files_to_modify = analysis.get("files", {}).get(repo_name, [])

            if files_to_modify:
                # Use Claude to make the changes
                changes = self._make_changes(
                    git_op,
                    ticket,
                    repo_path,
                    files_to_modify,
                )
                result["changes"] = changes
            else:
                print(f"  No specific files identified, analyzing codebase...")

                # Use Claude to find relevant files
                relevant_files = self._find_relevant_files(
                    repo_path,
                    ticket,
                )

                if relevant_files:
                    changes = self._make_changes(
                        git_op,
                        ticket,
                        repo_path,
                        relevant_files,
                    )
                    result["changes"] = changes
                else:
                    print(f"  Warning: Could not identify relevant files")
                    result["errors"].append("No relevant files found")

            # Commit if there are changes
            if result["changes"] and not self.dry_run:
                git_op.add(".")
                git_op.commit(ticket.summary, ticket.key)
                result["commit"] = git_op.get_commits(1)[0]["hash"]

                # Push
                print(f"  Pushing branch: {branch_name}")
                git_op.push(branch_name)
                result["pushed"] = True

        except Exception as e:
            result["errors"].append(str(e))
            print(f"  Error processing repo {repo_name}: {e}")

        return result

    def _find_relevant_files(self, repo_path: Path, ticket: JiraTicket) -> list[str]:
        """Use Claude to find relevant files in a repo for a ticket."""
        # Get file list
        files = []
        for ext in [".py", ".java", ".ts", ".js", ".md"]:
            files.extend([str(f.relative_to(repo_path)) for f in repo_path.rglob(f"*{ext}")])

        # Limit files for context
        files_str = "\n".join(files[:100])

        prompt = f"""Given this ticket, identify which files would likely need to be modified.

## Ticket
{ticket.get_context()}

## Available Files
{files_str}

Return only a JSON list of file paths that should be modified, e.g.:
["src/hl7_parser.py", "tests/test_parser.py"]
"""

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            import json
            content = response.content[0].text

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            relevant_files = json.loads(content)
            return relevant_files[:5]  # Limit to 5 files

        except Exception as e:
            print(f"    Error finding files: {e}")
            return []

    def _make_changes(
        self,
        git_op: GitOperator,
        ticket: JiraTicket,
        repo_path: Path,
        files: list[str],
    ) -> list[dict]:
        """Use Claude to make code changes."""
        changes = []

        for file_path in files:
            full_path = repo_path / file_path
            if not full_path.exists():
                print(f"    File not found: {file_path}")
                continue

            # Read current content
            current_content = full_path.read_text(encoding="utf-8")

            # Ask Claude for changes
            prompt = f"""You need to modify this file to implement the ticket requirements.

## Ticket
{ticket.get_context()}

## Current File: {file_path}
```
{current_content[:3000]}  # Limit for context
```

## Task
Make the necessary changes to this file to implement the ticket.
Respond with the complete modified file content wrapped in ```CODE_START``` and ```CODE_END```.
Only output the modified file, no explanations.
"""

            try:
                response = self.claude.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=10000,
                    messages=[{"role": "user", "content": prompt}],
                )

                content = response.content[0].text

                # Extract the code
                if "CODE_START" in content:
                    new_content = content.split("CODE_START")[1].split("CODE_END")[0].strip()
                elif "```" in content:
                    # Last code block
                    blocks = content.split("```")
                    if len(blocks) >= 3:
                        new_content = blocks[-2].split("\n", 1)[1] if "\n" in blocks[-2] else blocks[-2]
                    else:
                        new_content = blocks[1]
                else:
                    new_content = content

                # Write the file
                if not self.dry_run:
                    full_path.write_text(new_content, encoding="utf-8")

                changes.append({
                    "file": file_path,
                    "type": "modified",
                })
                print(f"    Modified: {file_path}")

            except Exception as e:
                print(f"    Error modifying {file_path}: {e}")

        return changes

    def _generate_report(self, results: dict) -> Path:
        """Generate a report document for the user to review."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = Path(__file__).parent.parent.parent / "output" / f"report_{results['ticket']}_{timestamp}.md"

        report_path.parent.mkdir(parents=True, exist_ok=True)

        ticket = results["ticket"]
        analysis = results["analysis"]
        branches = results["branches"]

        report = f"""# Ticket Processing Report: {ticket}

## Summary
- **Ticket**: {ticket}
- **Branches**: {', '.join(branches) if branches else 'None created'}
- **Status**: {'Success' if not results.get('errors') else 'Completed with errors'}

## Changes by Repo
"""

        for repo, change_data in results.get("changes", {}).items():
            report += f"""
### {repo}
- **Branch**: {change_data.get('branch', 'N/A')}
- **Files Modified**: {len(change_data.get('changes', []))}
- **Commit**: {change_data.get('commit', 'N/A')}
- **Pushed**: {'Yes' if change_data.get('pushed') else 'No'}
"""

            if change_data.get("errors"):
                report += f"- **Errors**: {', '.join(change_data['errors'])}\n"

        if results.get("errors"):
            report += f"""
## Errors
"""
            for error in results["errors"]:
                report += f"- {error}\n"

        report += f"""
## Next Steps
1. Review the changes in the branches above
2. Run tests: `pytest` / `npm test`
3. If satisfied, merge the PR
4. If not, let the agent know what needs to be fixed

---
Generated by LIS Code Agent at {datetime.now().isoformat()}
"""

        report_path.write_text(report, encoding="utf-8")

        print(f"\n  Report generated: {report_path}")

        return report_path

    def ask_user(self, question: str) -> str:
        """
        Ask the user a question when stuck.

        This is the learning mechanism - answers are stored in memory.
        """
        print(f"\n[QUESTION] {question}")
        print("Please provide an answer (this will be remembered)")

        # In automated mode, this would be non-blocking
        # For now, we'll just note that we need input
        return "PENDING_USER_INPUT"
