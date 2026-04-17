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
import re
from pathlib import Path
from datetime import datetime
from typing import Literal

import mysql.connector
from anthropic import Anthropic
from dotenv import load_dotenv

from ..auth import resolve_api_key
from ..config import get_settings
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

        # Initialize Claude (OAuth from /login, fallback to API key)
        api_key = resolve_api_key(os.getenv("ANTHROPIC_API_KEY"))
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        if base_url:
            self.claude = Anthropic(api_key=api_key, base_url=base_url)
        else:
            self.claude = Anthropic(api_key=api_key)

        # Discover repos
        self.repos = {r.name: r for r in find_git_repos(self.repos_base_path)}

        # Auto-discover credentials from repos
        self.credential_cache = {}

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

        # Get past feedback from memory
        past_feedback = self._get_relevant_feedback(ticket)

        # Check if this is an EMR integration ticket - if so, query database
        db_check_info = ""
        is_emr_ticket = (
            "emr" in ticket.summary.lower() or
            "emr" in ticket.description.lower() or
            "integration" in ticket.summary.lower() or
            "cerbo" in ticket.summary.lower() or
            "charm" in ticket.summary.lower()
        )

        if is_emr_ticket:
            print("  Checking EMR integration database (auto-discovering credentials)...")
            db_result = self._check_emr_integration_db(ticket)

            db_check_info = "\n\n## Database Check Results (Auto-discovered)\n"

            if db_result.get("error"):
                db_check_info += f"- **Status**: ❌ Could not connect to database\n"
                db_check_info += f"- **Error**: {db_result['error']}\n"
                if db_result.get("suggestion"):
                    db_check_info += f"- **Suggestion**: {db_result['suggestion']}\n"
                if db_result.get("db_config_used"):
                    db_check_info += f"- **Tried config**: {db_result['db_config_used']}\n"
            else:
                db_check_info += f"- **Status**: ✅ Connected (credentials auto-discovered from repo)\n"
                db_check_info += f"- **Provider ID**: {db_result.get('provider_id', 'N/A')}\n"
                db_check_info += f"- **Practice ID**: {db_result.get('practice_id', 'N/A')}\n"
                db_check_info += f"- **Customer ID**: {db_result.get('customer_id', 'N/A')}\n\n"

                # ehr_integrations check
                if db_result.get("ehr_integrations"):
                    rows = db_result['ehr_integrations']
                    db_check_info += f"- **ehr_integrations**: Found {len(rows)} row(s)\n"

                    # Check status and provide specific guidance
                    for row in rows:
                        status = row.get('status', 'UNKNOWN')
                        if status == 'PENDING':
                            db_check_info += f"  ⚠️ Status: {status} - NEEDS UPDATE TO LIVE\n"
                            db_check_info += f"  Action: UPDATE status, updated_at, enable flags (ordering_enabled=1, result_enabled=1, sftp_enabled=1)\n"
                        elif status in ['ACTIVE', 'LIVE', 'ENABLED']:
                            db_check_info += f"  ✅ Status: {status}\n"
                        else:
                            db_check_info += f"  ℹ️ Status: {status}\n"

                        # Show if ordering/result/sftp are disabled
                        if not row.get('ordering_enabled'):
                            db_check_info += f"  ⚠️ ordering_enabled=0 (disabled)\n"
                        if not row.get('result_enabled'):
                            db_check_info += f"  ⚠️ result_enabled=0 (disabled)\n"
                        if not row.get('sftp_enabled'):
                            db_check_info += f"  ⚠️ sftp_enabled=0 (disabled)\n"
                else:
                    db_check_info += "- **ehr_integrations**: NO DATA FOUND (integration not set up)\n"

                # order_clients check
                if db_result.get("order_clients"):
                    db_check_info += f"- **order_clients**: Found {len(db_result['order_clients'])} row(s)\n"
                else:
                    db_check_info += "- **order_clients**: NO DATA FOUND\n"

                # sftp_folder_mapping
                if db_result.get("sftp_folder_mapping"):
                    db_check_info += f"- **sftp_folder_mapping**: {len(db_result['sftp_folder_mapping'])} rows total\n"

                # Conclusion
                if db_result.get("ehr_integrations") or db_result.get("order_clients"):
                    has_pending = any(
                        row.get('status') == 'PENDING'
                        for row in db_result.get('ehr_integrations', [])
                    )
                    if has_pending:
                        db_check_info += "\n**Action Required**: UPDATE PENDING records to LIVE status.\n"
                    else:
                        db_check_info += "\n**Conclusion**: Integration records EXIST in database.\n"
                else:
                    db_check_info += "\n**Conclusion**: Integration NOT SET UP - need to add records to database.\n"

                    # Auto-discover gRPC config for the suggestion
                    grpc_config = self._discover_grpc_credentials()
                    if grpc_config:
                        grpc_info = f"{grpc_config.get('host', '192.168.60.6')}:{grpc_config.get('port', '30276')}"
                        db_check_info += f"- If Provider ID exists, call getCustomer RPC at {grpc_info} (auto-discovered)\n"
                    else:
                        db_check_info += "- If Provider ID exists, call getCustomer RPC (need to discover endpoint from repos)\n"

        # Use Claude to analyze which repos need changes
        repo_context = self._build_repo_context(available_repos)

        prompt = f"""You are analyzing a Jira ticket to determine which repositories need to be modified.

IMPORTANT:
- Respond in **Traditional Chinese (繁體中文)** for the "reasoning" field
- Repository names and file paths should remain in English
- Code snippets should remain in English
- **LEARN FROM PAST FEEDBACK** - use the feedback section to avoid repeating mistakes
- **INCLUDE DATABASE CHECK RESULTS** in your reasoning if available

## Ticket Information
{ticket.get_context()}

## Available Repositories
{repo_context}

## Agent Identity
{self.memory.read_identity()}

## Agent User Preferences
{self.memory.read_user()}

## PAST FEEDBACK - LEARN FROM THIS
{past_feedback}
{db_check_info}

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
    "reasoning": "Brief explanation of your analysis in Chinese"
}}
"""

        try:
            response = self.claude.messages.create(
                model=get_settings().default_model,
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

    def _get_relevant_feedback(self, ticket: JiraTicket) -> str:
        """Get past feedback from memory that might be relevant to this ticket."""
        memory = self.memory.read_memory()

        feedback_sections = []

        # 1. First, include Gotchas section (structured learnings)
        if "## Gotchas" in memory:
            gotchas_section = memory.split("## Gotchas")[1]
            # Get content until next major section
            for next_section in ["## Questions", "## Jira"]:
                if next_section in gotchas_section:
                    gotchas_section = gotchas_section.split(next_section)[0]
            feedback_sections.append("### 重要規則 (Gotchas)")
            feedback_sections.append(gotchas_section[:500])  # Limit length

        # 2. Then, include relevant Q&A feedback
        if "## Questions" in memory:
            questions_part = memory.split("## Questions")[1]
            entries = questions_part.split("### Q:")

            for entry in entries[1:]:  # Skip first empty entry
                entry_lower = entry.lower()

                # Check for keywords related to this ticket
                keywords = [
                    "emr", "integration", "result", "order",
                    "repo", "feedback", "正確", "錯誤", "lis-emr-backend-v2",
                    "emr-backend", "lis-backend-emr-v2"
                ]

                # Also check for ticket key if it exists
                if ticket.key:
                    keywords.append(ticket.key.lower())

                # If any keyword matches, include this feedback
                if any(kw in entry_lower for kw in keywords):
                    if "Feedback:" in entry:
                        feedback = entry.split("Feedback:")[1].strip()
                        feedback = feedback.split("\n\n")[0].strip()
                        feedback_sections.append(f"- {feedback}")

        if feedback_sections:
            return "\n".join(feedback_sections[:10])  # Limit to 10 entries
        else:
            return "No relevant past feedback available."

    def _discover_db_credentials(self) -> dict | None:
        """
        Auto-discover database credentials from repos.

        Searches for:
        - application.properties / application.yml (Java)
        - .env files (Python/Node.js)
        - k8s deployment yaml files
        """
        if "db_credentials" in self.credential_cache:
            return self.credential_cache["db_credentials"]

        import re

        # Common config file patterns
        config_patterns = [
            ("application.properties", r"datasource\.url[=:]\s*jdbc:mysql://([^:]+):(\d+)/([^\n]+)"),
            ("application.properties", r"spring\.datasource\.username[=:]\s*([^\n]+)"),
            ("application.properties", r"spring\.datasource\.password[=:]\s*([^\n]+)"),
            ("application.yml", r"url:\s*jdbc:mysql://([^:]+):(\d+)/([^#\n]+)"),
            ("application.yml", r"username:\s*([^\n#]+)"),
            ("application.yml", r"password:\s*([^\n#]+)"),
            (".env", r"DB_HOST[=:]\s*([^\n]+)"),
            (".env", r"DB_PORT[=:]\s*(\d+)"),
            (".env", r"DB_USER[=:]\s*([^\n]+)"),
            (".env", r"DB_PASSWORD[=:]\s*([^\n]+)"),
        ]

        credentials = {}

        for repo_name, repo_path in self.repos.items():
            # Focus on EMR-related repos first
            if "emr" not in repo_name.lower():
                continue

            for root, dirs, files in os.walk(repo_path):
                # Skip hidden dirs and common non-config dirs
                dirs[:] = [d for d in dirs if not d.startswith((".", "node_modules", "target", "build", ".git"))]

                for file in files:
                    if file in ["application.properties", "application.yml", ".env", "config.py"]:
                        file_path = Path(root) / file
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")

                            # Extract credentials using patterns
                            for pattern_name, pattern in config_patterns:
                                if pattern_name in file or file == ".env":
                                    match = re.search(pattern, content)
                                    if match:
                                        if "url" in pattern.lower() or "DB_HOST" in pattern:
                                            credentials["host"] = match.group(1)
                                            if len(match.groups()) > 1:
                                                credentials["port"] = int(match.group(2))
                                            if len(match.groups()) > 2:
                                                credentials["database"] = match.group(3)
                                        elif "username" in pattern.lower() or "DB_USER" in pattern:
                                            credentials["user"] = match.group(1).strip()
                                        elif "password" in pattern.lower() or "DB_PASSWORD" in pattern:
                                            credentials["password"] = match.group(1).strip()

                            # If we found basic credentials, stop searching
                            if "host" in credentials and "user" in credentials:
                                break
                        except Exception:
                            continue

                if "host" in credentials and "user" in credentials:
                    break

            if credentials:
                break

        if credentials:
            self.credential_cache["db_credentials"] = credentials
            return credentials

        return None

    def _discover_grpc_credentials(self) -> dict | None:
        """Auto-discover gRPC credentials from repos."""
        if "grpc_credentials" in self.credential_cache:
            return self.credential_cache["grpc_credentials"]

        import re

        credentials = {}

        for repo_name, repo_path in self.repos.items():
            if "emr" not in repo_name.lower():
                continue

            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if not d.startswith((".", "node_modules", "target", "build"))]

                for file in files:
                    if file.endswith((".properties", ".yml", ".yaml", ".env", ".py", ".ts")):
                        file_path = Path(root) / file
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")

                            # Look for gRPC server/host/port patterns
                            grpc_patterns = [
                                r"grpc\.server\.host[=:]\s*([^\n:#]+)",
                                r"grpc\.host[=:]\s*([^\n:#]+)",
                                r"GRPC_HOST[=:]\s*([^\n:#]+)",
                                r"grpc\.server\.port[=:]\s*(\d+)",
                                r"grpc\.port[=:]\s*(\d+)",
                                r"GRPC_PORT[=:]\s*(\d+)",
                                r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{4,5})",  # ip:port
                            ]

                            for pattern in grpc_patterns:
                                match = re.search(pattern, content)
                                if match:
                                    groups = match.groups()
                                    if ":" in match.group(0) or "port" in pattern.lower():
                                        if len(groups) >= 2:
                                            credentials["host"] = groups[0]
                                            credentials["port"] = groups[1]
                                        elif groups[0].isdigit():
                                            credentials["port"] = groups[0]
                                    else:
                                        credentials["host"] = groups[0]

                        except Exception:
                            continue

                if credentials:
                    break

            if credentials:
                break

        if credentials:
            self.credential_cache["grpc_credentials"] = credentials
            return credentials

        return None

    def _check_emr_integration_db(self, ticket: JiraTicket) -> dict:
        """
        Check EMR integration database tables for existing records.

        Returns dict with findings from:
        - order_clients
        - sftp_folder_mapping
        - ehr_integrations
        """
        result = {
            "exists": False,
            "order_clients": None,
            "sftp_folder_mapping": None,
            "ehr_integrations": None,
            "error": None,
        }

        # Extract IDs from ticket description
        description = ticket.description.lower()
        provider_id = None
        practice_id = None
        customer_id = None

        # Try to extract IDs
        id_patterns = {
            "provider id": r"provider id[:\s]+(\d+)",
            "practice id": r"practice id[:\s]+(\d+)",
            "customer id": r"customer id[:\s]+(\d+)",
        }

        for key, pattern in id_patterns.items():
            match = re.search(pattern, description)
            if match:
                value = match.group(1)
                if "provider" in key:
                    provider_id = value
                elif "practice" in key:
                    practice_id = value
                elif "customer" in key:
                    customer_id = value

        result["provider_id"] = provider_id
        result["practice_id"] = practice_id
        result["customer_id"] = customer_id

        # Auto-discover database credentials
        db_config = self._discover_db_credentials()

        if not db_config:
            result["error"] = "Could not auto-discover database credentials from repos"
            result["suggestion"] = "Check lis-backend-emr-v2 or EMR-Backend for application.properties with datasource config"
            return result

        result["db_source"] = f"Auto-discovered from repo"

        # Try to connect to database
        try:
            conn = mysql.connector.connect(
                host=db_config.get("host"),
                port=db_config.get("port", 3306),
                user=db_config.get("user"),
                password=db_config.get("password"),
                database=db_config.get("database", "lis_emr"),
                connection_timeout=5,
            )
            cursor = conn.cursor(dictionary=True)

            # Check ehr_integrations
            if practice_id:
                cursor.execute(
                    "SELECT * FROM ehr_integrations WHERE clinic_id = %s AND customer_id = -1",
                    (practice_id,)
                )
                result["ehr_integrations"] = cursor.fetchall()

            if customer_id:
                cursor.execute(
                    "SELECT * FROM ehr_integrations WHERE customer_id = %s",
                    (customer_id,)
                )
                rows = cursor.fetchall()
                if not result["ehr_integrations"]:
                    result["ehr_integrations"] = rows

            # Check order_clients
            if provider_id or customer_id:
                if provider_id:
                    cursor.execute(
                        "SELECT * FROM order_clients WHERE provider_id = %s",
                        (provider_id,)
                    )
                elif customer_id:
                    cursor.execute(
                        "SELECT * FROM order_clients WHERE customer_id = %s",
                        (customer_id,)
                    )
                result["order_clients"] = cursor.fetchall()

            # Check sftp_folder_mapping
            cursor.execute("SELECT * FROM sftp_folder_mapping LIMIT 100")
            result["sftp_folder_mapping"] = cursor.fetchall()

            cursor.close()
            conn.close()

            # Check if any integration exists
            if result["ehr_integrations"] or result["order_clients"]:
                result["exists"] = True

        except Exception as e:
            result["error"] = str(e)
            result["db_config_used"] = {k: v for k, v in db_config.items() if k != "password"}

        return result

    def _get_customer_from_grpc(self, provider_id: str | None, customer_id: str | None) -> dict:
        """
        Get customer data from gRPC getCustomer service.

        Returns dict with customer information.
        """
        result = {
            "found": False,
            "customer_data": None,
            "error": None,
        }

        if not provider_id and not customer_id:
            result["error"] = "No provider_id or customer_id provided"
            return result

        # Auto-discover gRPC credentials
        grpc_config = self._discover_grpc_credentials()

        if not grpc_config:
            result["error"] = "Could not auto-discover gRPC config from repos"
            result["suggestion"] = "Check lis-backend-emr-v2 or EMR-Backend for gRPC host/port in config files"
            return result

        grpc_host = grpc_config.get("host", "192.168.60.6")
        grpc_port = grpc_config.get("port", "30276")
        result["grpc_source"] = f"Auto-discovered from repo ({grpc_host}:{grpc_port})"

        try:
            import grpc

            # Try to connect to gRPC service
            channel = grpc.insecure_channel(f"{grpc_host}:{grpc_port}")

            # Check if channel is ready
            try:
                grpc.channel_ready_future(channel).result(timeout=2)
                result["channel_connected"] = True
                result["grpc_endpoint"] = f"{grpc_host}:{grpc_port}"
            except grpc.FutureTimeoutError:
                result["error"] = f"gRPC connection timeout to {grpc_host}:{grpc_port}"
                return result

            channel.close()

        except ImportError:
            result["error"] = "grpc library not installed"
        except Exception as e:
            result["error"] = str(e)

        return result

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
                model=get_settings().default_model,
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
                    model=get_settings().default_model,
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
