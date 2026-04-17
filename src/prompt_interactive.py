"""
Interactive Mode - Chat with the agent and teach it.

This allows you to:
1. Ask questions about tickets
2. Request analysis
3. Teach the agent new patterns
4. Give feedback on its decisions

Uses prompt_toolkit for input + rich for output (best of both worlds).
"""
from __future__ import annotations

# Suppress urllib3 OpenSSL warning on macOS (must be before imports)
import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from src.config import get_settings
from src.integrations.jira import JiraClient
from src.core.ticket_processor import TicketProcessor
from src.core.markdown_executor import MarkdownExecutor
from src.memory.manager import MemoryManager
from src.memory.auto_learner import get_auto_learner

load_dotenv()

console = Console()


class PromptToolkitInteractiveAgent:
    """Interactive agent using prompt_toolkit for proper terminal handling."""

    def __init__(self):
        """Initialize the interactive agent."""
        self.jira = JiraClient()
        self.processor = TicketProcessor(dry_run=False)
        self.memory = MemoryManager()
        self.running = True

        # Markdown-driven executor (openclaw-style)
        self.markdown_executor = MarkdownExecutor(claude=self.processor.claude)

        # Auto learner - extracts learnings from user feedback
        self.auto_learner = get_auto_learner(claude=self.processor.claude)

        # Create prompt session
        self.prompt_session = PromptSession()

        # Conversation history for context
        self.conversation_history: list[dict] = []

    def show_welcome(self):
        """Show welcome message."""
        console.print(Panel.fit(
            "[bold cyan]LIS Code Agent[/bold cyan]\n\n"
            "直接輸入問題即可對話\n\n"
            "指令:\n"
            "  [yellow]analyze[/yellow] <ticket>  - 分析票\n"
            "  [yellow]scan[/yellow]              - 掃描新票\n"
            "  [yellow]report[/yellow]            - 報告\n"
            "  [yellow]clear[/yellow]             - 清空對話\n"
            "  [yellow]exit[/yellow]              - 離開",
            border_style="cyan"
        ))

    def get_prompt_text(self):
        """Get the prompt text."""
        return [("class:prompt", ">>> ")]

    def get_prompt_style(self):
        """Get the prompt style."""
        from prompt_toolkit.styles import Style
        return Style.from_dict({
            "prompt": "cyan bold",
        })

    def handle_ask(self, question: str):
        """Handle a question from the user."""
        console.print(f"\n[bold]Question:[/bold] {question}")

        # Get memory context
        memory = self.memory.read_memory()

        # System prompt
        system_prompt = f"""You are LIS Code Agent, a helpful assistant for Leo.

IMPORTANT: Always answer in **Traditional Chinese (繁體中文)** unless explicitly asked to use English.

Context about the repos and patterns:
{memory}

Maintain conversation context and reference previous messages when relevant."""

        # Build messages with conversation history (only user/assistant roles)
        messages = list(self.conversation_history)
        messages.append({"role": "user", "content": question})

        response = self.processor.claude.messages.create(
            model=get_settings().default_model,
            max_tokens=1000,
            system=system_prompt,
            messages=messages
        )

        answer = response.content[0].text
        console.print(Panel(answer, title="[bold green]Answer[/bold green]", border_style="green"))

        # Auto-learn from user feedback
        import asyncio
        try:
            learning_result = asyncio.run(self.auto_learner.learn_from_feedback(
                user_input=question,
                agent_response=answer,
                context="General conversation"
            ))
            if learning_result.get("learned"):
                updated = learning_result.get("updated_files", [])
                learning = learning_result.get("learning", {})
                console.print(Panel(
                    f"[dim]🧠 Learned: {learning.get('title', 'New pattern')}\n"
                    f"[dim]Updated: {', '.join(updated)}[/dim]",
                    title="[bold yellow]Auto-Learning[/bold yellow]",
                    border_style="yellow"
                ))
        except Exception as e:
            # Don't interrupt conversation for learning errors
            pass

        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": question})
        self.conversation_history.append({"role": "assistant", "content": answer})

        # Limit history to last 20 messages (10 turns)
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    def _detect_iterative_task(self, question: str) -> bool:
        """
        Detect if user wants to execute a task that requires iteration.

        Examples:
        - "寫一個 script 並執行"
        - "建立並測試"
        - "寫 code 修正這個問題"
        - "batch insert"
        """
        keywords = [
            "寫", "建立", "執行", "測試", "batch", "insert", "update",
            "write", "create", "execute", "test", "run", "script"
        ]

        question_lower = question.lower()
        return any(kw in question_lower for kw in keywords)

    async def handle_iterative_task(self, task: str):
        """
        Handle tasks that require write-test-fix iteration.

        This enables Claude-like speed: one command → automatic retry → success
        """
        console.print(Panel(
            f"[bold cyan]⚡ 執行任務 (自動迭代模式)[/bold cyan]\n"
            f"{task}",
            title="Iterative Execution",
            border_style="cyan"
        ))

        console.print("\n[dim]正在執行中，請稍候...[/dim]")

        # Execute with retry
        result = await self.markdown_executor.execute_with_retry(
            task_description=task,
            max_iterations=5
        )

        # Display results
        if result.get("success"):
            console.print(Panel(
                f"[bold green]✅ 成功![/bold green]\n\n"
                f"迭代次數: {result.get('iterations')}\n\n"
                f"[bold]輸出:[/bold]\n{result.get('output', 'N/A')}",
                title="[bold green]Task Complete[/bold green]",
                border_style="green"
            ))

            # Show execution history if available
            history = result.get('execution_history', [])
            if history and len(history) > 1:
                console.print("\n[dim]執行歷程:[/dim]")
                for h in history:
                    console.print(f"  • {h}")
        else:
            console.print(Panel(
                f"[bold red]❌ 失敗[/bold red]\n\n"
                f"嘗試次數: {result.get('iterations')}\n\n"
                f"[bold]錯誤:[/bold]\n{result.get('error', 'Unknown error')}\n\n"
                f"[bold]最後輸出:[/bold]\n{result.get('last_output', 'N/A')}",
                title="[bold red]Task Failed[/bold red]",
                border_style="red"
            ))

        # Trigger auto-learning even for iterative tasks
        try:
            learning_result = await self.auto_learner.learn_from_feedback(
                user_input=task,
                agent_response=result.get('output', str(result)),
                context="Iterative task execution"
            )
            if learning_result.get("learned"):
                updated = learning_result.get("updated_files", [])
                learning = learning_result.get("learning", {})
                console.print(Panel(
                    f"[dim]🧠 Learned: {learning.get('title', 'New pattern')}\n"
                    f"[dim]Updated: {', '.join(updated)}[/dim]",
                    title="[bold yellow]Auto-Learning[/bold yellow]",
                    border_style="yellow"
                ))
        except Exception as e:
            pass  # Don't show learning errors

    def handle_analyze(self, ticket_id: str):
        """Analyze a ticket and enter conversation mode."""
        console.print(f"\n[bold]Analyzing ticket:[/bold] {ticket_id}")

        try:
            ticket = self.jira.get_ticket(ticket_id)
            analysis = self.processor.analyze_ticket(ticket)

            # Build the display content
            content = f"""[bold]Ticket:[/bold] {ticket.key}
[bold]Summary:[/bold] {ticket.summary}

[bold]Status:[/bold] {ticket.status} | [bold]Type:[/bold] {ticket.issue_type} | [bold]Priority:[/bold] {ticket.priority or 'N/A'}

[bold]Description:[/bold]
{ticket.description[:500] + '...' if len(ticket.description) > 500 else ticket.description}

[bold]Analysis:[/bold]
  Confidence: {analysis['confidence']}
  Repos: {', '.join(analysis['repos']) or 'None found'}

[bold]Reasoning:[/bold]
  {analysis.get('reasoning', 'N/A')}"""

            # Show attachments if any
            if ticket.attachments:
                content += f"\n\n[bold]Attachments ({len(ticket.attachments)}):[/bold]"
                for att in ticket.attachments:
                    content += f"\n  • {att.get('filename')} ({att.get('mimeType', 'unknown')})"
                    content += f"\n    URL: {att.get('content')}"

            console.print(Panel(content, title="[bold cyan]Ticket Analysis[/bold cyan]", border_style="cyan"))

            # Ask if user wants to download attachments
            if ticket.attachments:
                download = self.prompt_session.prompt(
                    "\nDownload attachment? (y/N): ",
                    style=self.get_prompt_style()
                )
                if download and download.lower() == "y":
                    for att in ticket.attachments:
                        try:
                            path = self.jira.download_attachment(att.get('content'))
                            console.print(f"[green]✓ Downloaded to:[/green] {path}")
                        except Exception as e:
                            console.print(f"[red]✗ Download failed:[/red] {e}")

            # Enter conversation mode for this ticket
            self._ticket_conversation_mode(ticket_id, ticket, analysis)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _ticket_conversation_mode(self, ticket_id: str, ticket, analysis: dict):
        """Conversation mode for discussing a specific ticket."""
        console.print("\n[yellow]Entering ticket conversation mode.[/yellow]")
        console.print("[dim]Ask follow-up questions, give feedback, or type 'done' to exit.[/dim]")
        console.print("[dim]Commands: '執行', 'update', 'insert' - will ACTUALLY execute DB operations[/dim]\n")

        # Create ticket-specific conversation context
        ticket_context = f"""Current ticket context:
- Ticket: {ticket.key} - {ticket.summary}
- Status: {ticket.status}
- Analysis: {analysis.get('reasoning', 'N/A')}
- Repos: {', '.join(analysis.get('repos', []))}
"""

        while True:
            try:
                user_input = self.prompt_session.prompt(
                    f"[{ticket.key}] >>> ",
                    style=self.get_prompt_style()
                )

                if not user_input:
                    continue

                if user_input.lower() in ["done", "exit", "quit"]:
                    console.print(f"[yellow]Exiting {ticket_id} conversation mode.[/yellow]")
                    break

                # Check for execution commands
                exec_keywords = ["執行", "執行看看", "直接執行", "update", "insert", "請執行", "execute"]
                if any(kw in user_input.lower() for kw in exec_keywords):
                    result = self._execute_db_operations(ticket, analysis)
                    console.print(Panel(result, title="[bold cyan]Execution Result[/bold cyan]", border_style="cyan"))
                    # Don't add to conversation history - this is actual execution
                    continue

                # Add to conversation history
                self.conversation_history.append({"role": "user", "content": f"[{ticket_id}] {user_input}"})

                # Get response with ticket context
                system_prompt = f"""You are discussing ticket {ticket.key} with Leo.

{ticket_context}

Answer in Traditional Chinese (繁體中文). Be specific about this ticket."""

                messages = list(self.conversation_history)
                response = self.processor.claude.messages.create(
                    model=get_settings().default_model,
                    max_tokens=1000,
                    system=system_prompt,
                    messages=messages
                )

                answer = response.content[0].text
                console.print(Panel(answer, title="[bold green]Response[/bold green]", border_style="green"))

                # Auto-learn from user feedback
                import asyncio
                try:
                    learning_result = asyncio.run(self.auto_learner.learn_from_feedback(
                        user_input=user_input,
                        agent_response=answer,
                        context=ticket_context
                    ))
                    if learning_result.get("learned"):
                        updated = learning_result.get("updated_files", [])
                        learning = learning_result.get("learning", {})
                        console.print(Panel(
                            f"[dim]🧠 Learned: {learning.get('title', 'New pattern')}\n"
                            f"[dim]Updated: {', '.join(updated)}[/dim]",
                            title="[bold yellow]Auto-Learning[/bold yellow]",
                            border_style="yellow"
                        ))
                except Exception as e:
                    # Don't interrupt conversation for learning errors
                    pass

                # Add to conversation history
                self.conversation_history.append({"role": "assistant", "content": answer})

                # Keep conversation history manageable
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]

            except KeyboardInterrupt:
                console.print(f"\n[yellow]Use 'done' to exit {ticket_id} mode.[/yellow]")
            except EOFError:
                break

        # Save learnings when exiting ticket mode
        save = self.prompt_session.prompt(
            f"\n[yellow]Save learnings from {ticket_id} to memory?[/yellow] (y/N): ",
            style=self.get_prompt_style()
        )
        if save and save.lower() == "y":
            # Save the conversation as learning
            self.memory.learn_qa(
                f"Ticket {ticket_id} conversation",
                f"Ticket: {ticket.key}\nSummary: {ticket.summary}\nAnalysis: {analysis}"
            )
            console.print("[green]✓ Saved to memory![/green]")

    def _execute_db_operations(self, ticket, analysis: dict) -> str:
        """
        Execute database operations using markdown-driven architecture.

        This is the new openclaw-style approach:
        1. Read skill from SKILL.md
        2. Consult LLM with the skill content
        3. LLM creates execution plan
        4. Execute the plan
        """
        result = self.markdown_executor.execute_emr_integration(ticket)

        if result.get("success"):
            return result.get("output", "✅ Execution completed")
        else:
            error = result.get("error", "Unknown error")
            analysis_info = result.get("analysis", {})
            return f"❌ Execution failed: {error}\n\nAnalysis: {analysis_info}"

    def _llm_analyze_ticket(self, ticket) -> dict:
        """Use LLM to analyze ticket with full business context and reasoning."""
        import re
        import json

        description = ticket.description or ""

        # Read SOUL.md for business rules
        soul_path = Path(__file__).parent.parent / "SOUL.md"
        soul_content = ""
        if soul_path.exists():
            with open(soul_path) as f:
                soul_content = f.read()

        system_prompt = f"""You are an EMR Integration specialist. Analyze tickets and determine what needs to be done.

CRITICAL BUSINESS RULES (from SOUL.md):
{soul_content}

TICKET ANALYSIS PROCESS:
1. Extract all data from ticket description
2. Identify what's MISSING (e.g., provider personal name, NPI)
3. Determine HOW to get missing data (e.g., call gRPC service)
4. Plan the execution steps

IMPORTANT:
- Ticket "Name" field is CLINIC name, not provider personal name
- Provider personal name MUST come from gRPC GetCustomer RPC
- gRPC service: 192.168.60.6:30276, proto at lis-backend-emr-v2/src/proto/customer.proto
- Output your FULL reasoning process

Return valid JSON with reasoning."""

        user_prompt = f"""Analyze this EMR Integration ticket:

TICKET: {ticket.key}
SUMMARY: {ticket.summary}
DESCRIPTION:
{description}

Your task:
1. Extract all information from the ticket
2. Identify what data is MISSING and needed
3. Explain HOW to get the missing data
4. Provide your reasoning steps

Return JSON:
{{
    "reasoning": "Step-by-step explanation of your analysis...",
    "extracted": {{
        "provider_id": "...",
        "practice_id": "...",
        "clinic_name": "...",
        "emr_vendor": "...",
        "folder_path": "..."
    }},
    "missing": [
        "provider_personal_name - needs gRPC call",
        "npi - needs gRPC call"
    ],
    "actions": [
        "1. Call gRPC GetCustomer with provider_id to get provider name and NPI",
        "2. Insert into ehr_integrations table...",
        "3. Insert into order_clients table..."
    ],
    "grpc_needed": true/false,
    "provider_id_for_rpc": "...",
    "emr_name_mapped": "MDHQ/CHARMEHR/ECW/ATHENA"
}}"""

        try:
            response = self.processor.claude.messages.create(
                model=get_settings().default_model,
                max_tokens=1000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            import json
            text = response.content[0].text
            # Extract JSON from response - handle markdown code blocks and nested objects
            # First try to find JSON in markdown code blocks
            json_match = re.search(r'```(?:json)?\s*\n?(\{[^`]+\})\n?```', text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # Fallback: find JSON object (may not handle all nested cases)
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
                json_text = json_match.group(0) if json_match else None

            if json_text:
                try:
                    data = json.loads(json_text)
                except json.JSONDecodeError:
                    # Try to clean up and retry
                    json_text = json_text.replace('\n', ' ').strip()
                    data = json.loads(json_text)

                extracted = data.get('extracted', {})

                # Apply code-side EMR name mapping (more reliable than LLM)
                emr_vendor = extracted.get('emr_vendor', '').lower()
                emr_mapping = {
                    "cerbo": "MDHQ", "mdhq": "MDHQ",
                    "charm": "CHARMEHR",
                    "eclinical": "ECW", "ecw": "ECW",
                    "athena": "ATHENA"
                }
                emr_name = data.get('emr_name_mapped', 'MDHQ')  # LLM's mapping
                for key, val in emr_mapping.items():
                    if key in emr_vendor or emr_vendor in key:
                        emr_name = val  # Override with code-side mapping
                        break

                return {
                    'reasoning': data.get('reasoning', ''),
                    'extracted_data': json.dumps(extracted, indent=2),
                    'missing': data.get('missing', []),
                    'actions': data.get('actions', []),
                    'provider_id': extracted.get('provider_id'),
                    'practice_id': extracted.get('practice_id'),
                    'clinic_name': extracted.get('clinic_name'),
                    'emr_name': emr_name,
                    'folder': extracted.get('folder_path'),
                    'grpc_needed': data.get('grpc_needed', False),
                    'customer_firstname': '',  # Will get from gRPC
                    'customer_lastname': '',
                    'npi': None,  # Will get from gRPC
                    'analysis': data.get('reasoning', '')
                }
        except Exception as e:
            # Debug: print exception for troubleshooting
            import traceback
            from rich.console import Console
            console = Console()
            console.print(f"[yellow]⚠️ LLM analysis failed: {e}[/yellow]")
            console.print(f"[dim]Traceback: {traceback.format_exc()[:300]}[/dim]")
            # Fallback to regex parsing
            return self._fallback_parse(ticket)

    def _llm_diagnose_failure(self, ticket, result: dict, table: str) -> str:
        """Use LLM to diagnose failure with full reasoning."""
        error_info = result.get('error', 'Unknown error')[:500]
        output_info = result.get('output', '')[:500]

        system_prompt = """You are a database specialist. Analyze errors and suggest fixes.

Provide your reasoning:
1. What exactly went wrong?
2. Why did it go wrong?
3. How should we fix it?

Be specific and actionable."""

        user_prompt = f"""Ticket: {ticket.key}
Table: {table}
Error: {error_info}
Output: {output_info}

Analyze this failure and provide:
1. Root cause analysis
2. Suggested fix

Format your response with clear sections."""

        try:
            response = self.processor.claude.messages.create(
                model=get_settings().default_model,
                max_tokens=500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            return response.content[0].text.strip()
        except Exception:
            return "Unable to diagnose"

    def _fallback_parse(self, ticket) -> dict:
        """Fallback regex parsing if LLM fails."""
        import re
        description = ticket.description or ""

        # Provider ID
        match = re.search(r"provider id[:\s]+(\d+)", description, re.IGNORECASE)
        provider_id = match.group(1) if match else None

        # Practice ID
        match = re.search(r"practice id[:\s]+(\d+)", description, re.IGNORECASE)
        practice_id = match.group(1) if match else None

        # Clinic name - extract everything from "Name:" until "Provider ID" or "Practice ID"
        # Pattern: "Name: [text] Provider ID: [number]" or "Name: [text] Practice ID: [number]"
        match = re.search(r"name:\s*(.+?)\s*(?:provider|practice)\s+id", description, re.IGNORECASE)
        clinic_name = match.group(1).strip() if match else "Unknown"

        # EMR Vendor
        emr_mapping = {"cerbo": "MDHQ", "mdhq": "MDHQ", "charm": "CHARMEHR", "eclinical": "ECW", "athena": "ATHENA"}
        emr_name = "MDHQ"
        for key, val in emr_mapping.items():
            if key in description.lower():
                emr_name = val
                break

        # Folder path
        match = re.search(r"folder path[:\s]+(\S+)", description, re.IGNORECASE)
        folder = match.group(1).strip() if match else None

        return {
            'analysis': f"Regex parsed {ticket.key}",
            'extracted_data': f"Name: {clinic_name}, Provider: {provider_id}, Practice: {practice_id}",
            'provider_id': provider_id,
            'practice_id': practice_id,
            'customer_firstname': '',
            'customer_lastname': '',
            'clinic_name': clinic_name,
            'npi': None,
            'emr_name': emr_name,
            'folder': folder
        }

    def _execute_ehr_integration(self, ticket, provider_id, practice_id, customer_id,
                                customer_firstname, customer_lastname, npi, clinic_name,
                                emr_name, folder) -> dict:
        """Execute EHR integration script with verification."""
        import subprocess
        from pathlib import Path

        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")
        script = repo_path / "scripts/insert-ehr-integration.ts"

        if not script.exists():
            return {"success": False, "error": "Script not found", "output": ""}

        # Use clinic_name directly (no first/last split)
        if not customer_firstname:
            parts = clinic_name.split()
            customer_firstname = parts[0] if parts else ""
            customer_lastname = " ".join(parts[1:]) if len(parts) > 1 else ""

        args = [
            "--customer-firstname", customer_firstname,
            "--customer-lastname", customer_lastname,
            "--npi", npi or "0000000000",
            "--clinic-name", clinic_name,  # FULL NAME here
            "--clinic-id", str(practice_id or customer_id),
            "--customer-id", str(customer_id),
            "--emr-name", emr_name,
            "--folder", folder or "default_folder",
            "--ticket-number", ticket.key,
            "--integration-type", "FULL_INTEGRATION",
            "--msh06", str(practice_id or customer_id),
        ]

        cmd = ["npx", "ts-node", "scripts/insert-ehr-integration.ts"] + args
        result = self._run_with_autoheal(cmd, repo_path)

        # Verify after execution
        if "successfully" in result["output"].lower():
            if self._verify_ehr_integration(customer_id):
                return {"success": True, "error": "", "output": result["output"]}
            else:
                return {"success": False, "error": "Verification failed - record not in DB", "output": result["output"]}

        return {"success": False, "error": "Script execution failed", "output": result["output"]}

    def _execute_order_client(self, ticket, provider_id, customer_firstname, customer_lastname,
                             npi, clinic_name, emr_name, folder) -> dict:
        """Execute Order Client script with verification."""
        import subprocess
        from pathlib import Path

        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")
        script = repo_path / "scripts/insert-order-client.ts"

        if not script.exists():
            return {"success": False, "error": "Script not found", "output": ""}

        # Derive first/last name from clinic_name if empty
        if not customer_firstname or not customer_lastname:
            parts = clinic_name.split() if clinic_name else ["Unknown", "Clinic"]
            if not customer_firstname:
                customer_firstname = parts[0]
            if not customer_lastname:
                customer_lastname = " ".join(parts[1:]) if len(parts) > 1 else "Clinic"

        args = [
            "--customer-firstname", customer_firstname,
            "--customer-lastname", customer_lastname,
            "--npi", npi or "0000000000",
            "--clinic-name", clinic_name,  # FULL NAME
            "--clinic-id", str(provider_id),  # Use provider_id
            "--emr-name", emr_name,
            "--folder", folder or "default_folder",
        ]

        cmd = ["npx", "ts-node", "scripts/insert-order-client.ts"] + args
        result = self._run_with_autoheal(cmd, repo_path)

        # Show execution details
        execution_output = f"""
🔧 Executing order_clients insertion:
   Script: {script}
   Args: {' '.join(args)}
   Result: {result['output'][:200]}...
"""

        # Verify after execution
        if "successfully" in result["output"].lower():
            if self._verify_order_client(provider_id):
                return {"success": True, "error": "", "output": execution_output}
            else:
                return {"success": False, "error": "Verification failed - record not in DB", "output": execution_output}

        return {"success": False, "error": "Script execution failed", "output": execution_output}

    def _update_ehr_integration(self, customer_id: str, npi: str) -> dict:
        """Update ehr_integrations NPI using dedicated script."""
        import subprocess
        from pathlib import Path

        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")

        cmd = [
            "npx", "ts-node", "scripts/update-ehr-integration.ts",
            f"--customer-id={customer_id}", f"--npi={npi}"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=30)
        return {
            "success": result.returncode == 0,
            "error": "" if result.returncode == 0 else (result.stderr or result.stdout),
            "output": result.stdout + result.stderr
        }

    def _update_order_client(self, provider_id: str, customer_firstname: str, customer_lastname: str,
                             npi: str, clinic_name: str) -> dict:
        """Update order_clients using dedicated script."""
        import subprocess
        from pathlib import Path

        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")
        full_name = f"{customer_firstname} {customer_lastname}"

        cmd = [
            "npx", "ts-node", "scripts/update-order-client.ts",
            f"--customer-id={provider_id}",
            f"--customer-name={full_name}",
            f"--npi={npi}",
            f"--clinic-name={clinic_name}"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=30)
        return {
            "success": result.returncode == 0,
            "error": "" if result.returncode == 0 else (result.stderr or result.stdout),
            "output": result.stdout + result.stderr
        }


    def _get_customer_from_rpc(self, customer_id: str, practice_id: str) -> dict:
        """Get customer data from gRPC call.

        Returns dict with:
        - customer_first_name, customer_last_name, customer_middle_name, customer_suffix
        - customer_npi_number
        - clinics: array of {clinic_id, clinic_name}
        """
        import subprocess
        import json

        try:
            repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")
            grpc_script = repo_path / "scripts" / "get-customer-rpc.ts"

            if grpc_script.exists():
                cmd = ["npx", "ts-node", str(grpc_script), customer_id]
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=30)

                if result.returncode == 0:
                    try:
                        data = json.loads(result.stdout)
                        if data.get("success"):
                            return data
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            from rich.console import Console
            Console().print(f"[yellow]⚠️ RPC call failed: {e}[/yellow]")

        return {}

    def _check_db_state(self, customer_id: str) -> str:
        """Check current database state for this customer."""
        import subprocess

        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")
        check_script = repo_path / "scripts" / "check-db-state.ts"

        if check_script.exists():
            cmd = ["npx", "ts-node", str(check_script), f"--customer-id={customer_id}"]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path)
            if result.returncode == 0:
                return result.stdout

        # Fallback: check using tmp script if exists
        tmp_script = repo_path / f"tmp_check_{customer_id}.js"
        if tmp_script.exists():
            result = subprocess.run(["node", str(tmp_script)], capture_output=True, text=True, cwd=repo_path)
            if result.returncode == 0:
                return result.stdout

        return "  Unable to check DB state (no check script found)"

    def _get_existing_db_data(self, customer_id: str, provider_id: str) -> dict:
        """Get existing data from database for comparison with gRPC data."""
        import subprocess
        import json

        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")
        result = {'ehr_integrations': None, 'order_clients': None}

        try:
            cmd = [
                "npx", "ts-node", "scripts/get-existing-data-json.ts",
                f"--customer-id={customer_id}"
            ]
            process_result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=30)

            if process_result.returncode == 0:
                # Parse JSON output
                for line in process_result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line and line.startswith('{'):
                        try:
                            data = json.loads(line)
                            if 'ehr_integrations' in data:
                                result['ehr_integrations'] = data['ehr_integrations']
                            if 'order_clients' in data:
                                result['order_clients'] = data['order_clients']
                            break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            from rich.console import Console
            Console().print(f"[yellow]Warning: Could not fetch existing data: {e}[/yellow]")

        return result

    def _needs_emr_update(self, db_state: str) -> bool:
        """Determine if ehr_integrations table needs update."""
        # Check if record is missing, PENDING status, or has no records
        db_lower = db_state.lower()
        # "❌ ehr_integrations: No record found" - needs insert
        if "❌ ehr_integrations" in db_state:
            return True
        # Check specifically in ehr_integrations line for "no record found"
        for line in db_state.split('\n'):
            if 'ehr_integrations' in line.lower() and 'no record found' in line.lower():
                return True
        # "✅ ehr_integrations: ... status=PENDING" - needs update to LIVE
        for line in db_state.split('\n'):
            if 'ehr_integrations' in line.lower() and 'status=pending' in line.lower():
                return True
        # If status=LIVE, no update needed
        return False

    def _needs_order_client_update(self, db_state: str) -> bool:
        """Determine if order_clients table needs update."""
        db_lower = db_state.lower()
        # "❌ order_clients: No record found" - needs insert
        if "❌ order_clients" in db_state or "order_clients: no record found" in db_lower:
            return True
        # Also check if table doesn't exist
        if "table may not exist" in db_lower:
            return True
        return False

    def _run_with_autoheal(self, cmd: list, cwd: Path) -> dict:
        """Run command with auto-healing for common errors."""
        import subprocess

        output = ""
        actions = []

        # First attempt
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        output = result.stdout + result.stderr
        output_lower = output.lower()

        # Check for success indicators (must check before error handling)
        if result.returncode == 0 and (
            "successfully inserted" in output_lower or
            "successfully updated" in output_lower or
            "✅" in output
        ):
            actions.append("Executed script successfully")
            return {"output": output, "actions": actions}

        # === Error Handling ===

        # Error 1: ts-node not found -> install it
        if "ts-node" in output_lower and ("not found" in output_lower or "command not found" in output_lower):
            actions.append("Installed ts-node")
            subprocess.run(["npm", "install", "--save-dev", "ts-node"], capture_output=True, cwd=cwd)
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
            output = result.stdout + result.stderr
            output_lower = output.lower()
            if result.returncode == 0 and ("✅" in output or "successfully" in output_lower):
                actions.append("Executed script successfully after installing ts-node")
                return {"output": output, "actions": actions}

        # Error 2: Missing dependencies -> npm install
        if "cannot find module" in output_lower or "missing dependencies" in output_lower:
            actions.append("Installed dependencies")
            subprocess.run(["npm", "install"], capture_output=True, cwd=cwd)
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
            output = result.stdout + result.stderr
            output_lower = output.lower()
            if result.returncode == 0 and ("✅" in output or "successfully" in output_lower):
                actions.append("Executed script successfully after installing dependencies")
                return {"output": output, "actions": actions}

        # Error 3: TypeScript compile errors -> try with --transpile-only
        if "error ts" in output_lower and "transpile-only" not in " ".join(cmd):
            actions.append("Used transpile-only mode")
            cmd.insert(1, "--transpile-only")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
            output = result.stdout + result.stderr
            output_lower = output.lower()
            if result.returncode == 0 and ("✅" in output or "successfully" in output_lower):
                actions.append("Executed script successfully with transpile-only mode")
                return {"output": output, "actions": actions}

        # === NEW: Intelligent Script Fixing ===
        # Check for database/column errors that can be auto-fixed
        if ("unknown column" in output_lower or "prismaclientknownrequesterror" in output_lower or
            "fatal error" in output_lower) and cmd:
            # Try to fix the script intelligently
            fix_result = self._intelligent_fix_script(cmd, cwd, output)
            if fix_result["fixed"]:
                actions.append(f"Auto-fixed script: {fix_result['description']}")
                # Retry after fix
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
                output = result.stdout + result.stderr
                output_lower = output.lower()
                if result.returncode == 0 and ("✅" in output or "successfully" in output_lower):
                    actions.append("Executed script successfully after auto-fix")
                    return {"output": output, "actions": actions}

        # Also check for duplicate error (not a failure, just info)
        if "duplicate" in output_lower and "❌" in output:
            actions.append("Duplicate record detected (skipped)")

        # Check for fatal errors and report them
        if "fatal error" in output_lower or "prismaclientknownrequesterror" in output_lower:
            actions.append("Script execution failed (see error above)")

        return {"output": output, "actions": actions}

    def _intelligent_fix_script(self, cmd: list, cwd: Path, error_output: str) -> dict:
        """Intelligently analyze and fix script errors."""
        import subprocess
        import re

        # Extract script path from command
        script_path = None
        for part in cmd:
            if "scripts/" in part and (part.endswith(".ts") or part.endswith(".js")):
                script_path = cwd / part
                break

        if not script_path or not script_path.exists():
            return {"fixed": False, "description": "Script not found"}

        # Read the script content
        try:
            with open(script_path, 'r') as f:
                content = f.read()
        except Exception:
            return {"fixed": False, "description": "Cannot read script"}

        original_content = content
        error_lower = error_output.lower()

        # === Fix Pattern 1: Unknown column 'legacy_emr_service' ===
        if "unknown column 'legacy_emr_service'" in error_lower:
            # Remove legacy_emr_service from SELECT query
            content = re.sub(
                r'SELECT id, code, sftp_host, sftp_port, legacy_emr_service\s+FROM ehr_vendors',
                'SELECT id, code, sftp_host, sftp_port FROM ehr_vendors',
                content
            )
            # Update the return type annotation
            content = re.sub(
                r': Promise<\{ id: number; code: string; sftp_host: string \| null; sftp_port: number \| null; legacy_emr_service: string \| null \}>',
                ': Promise<{ id: number; code: string; sftp_host: string | null; sftp_port: number | null }>',
                content
            )
            # Update usage: vendorInfo.legacy_emr_service -> input.emr_name.toUpperCase()
            content = re.sub(
                r'vendorInfo\.legacy_emr_service\s*\?\?\s*',
                'input.emr_name.toUpperCase()',
                content
            )

            if content != original_content:
                with open(script_path, 'w') as f:
                    f.write(content)
                return {"fixed": True, "description": "Removed non-existent 'legacy_emr_service' column"}

        # === Fix Pattern 2: Unknown column in general ===
        match = re.search(r"unknown column '([^']+)' in 'field list'", error_output, re.IGNORECASE)
        if match:
            column_name = match.group(1)
            # Try to remove this column from SELECT statements
            content = re.sub(
                rf',\s*{re.escape(column_name)}\s*(?=[,\s]+FROM)',
                '',
                content,
                flags=re.IGNORECASE
            )
            if content != original_content:
                with open(script_path, 'w') as f:
                    f.write(content)
                return {"fixed": True, "description": f"Removed non-existent column '{column_name}'"}

        # === Fix Pattern 3: EMR vendor not found (try common name mapping) ===
        if "emr vendor '" in error_lower and "' not found in ehr_vendors" in error_lower:
            # Extract the vendor name from error
            vendor_match = re.search(r"emr vendor '([^']+)' not found", error_output, re.IGNORECASE)
            if vendor_match:
                vendor_name = vendor_match.group(1).lower()
                # Check if we need to map "cerbo" to "MDHQ"
                if vendor_name == "cerbo":
                    # This is already handled by the prompt_interactive vendor mapping
                    # But if the error still occurs, the script needs updating
                    return {"fixed": False, "description": "Vendor 'cerbo' should map to 'MDHQ' (handled by caller)"}

        return {"fixed": False, "description": "No auto-fix available for this error"}

    def _needs_order_client_update_for_provider(self, provider_id: str) -> bool:
        """Check if order_client exists for this provider_id."""
        if not provider_id:
            return False
        # Check database directly
        import subprocess
        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")
        try:
            cmd = [
                "npx", "ts-node", "--transpile-only", "-e",
                "import { PrismaClient } from '@prisma/client'; const prisma = new PrismaClient(); "
                f"prisma.$queryRaw`SELECT COUNT(*) as count FROM order_clients WHERE customer_id = {provider_id}`"
                ".then(r => console.log('COUNT:' + r[0].count)).finally(() => prisma.$disconnect());"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=30)
            output = result.stdout + result.stderr
            if "COUNT:0" in output:
                return True  # Need to create
            elif "COUNT:" in output:
                return False  # Already exists
        except Exception:
            pass
        # Default to True if we can't check
        return True

    def _verify_ehr_integration(self, customer_id: str) -> bool:
        """Verify ehr_integrations record exists."""
        import subprocess
        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")
        try:
            # Use shell=True to properly handle the command
            cmd = [
                "npx", "ts-node", "--transpile-only", "-e",
                "import { PrismaClient } from '@prisma/client'; const prisma = new PrismaClient(); "
                f"prisma.$queryRaw`SELECT COUNT(*) as count FROM ehr_integrations WHERE customer_id = '{customer_id}'`"
                ".then(r => console.log('VERIFIED:' + r[0].count)).finally(() => prisma.$disconnect());"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=30)
            output = result.stdout + result.stderr
            return "VERIFIED:1" in output or "VERIFIED:2" in output or "VERIFIED:3" in output
        except Exception as e:
            self._learn_from_verification_error("ehr_integrations", customer_id, str(e))
            return False

    def _verify_order_client(self, provider_id: str) -> bool:
        """Verify order_clients record exists."""
        import subprocess
        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")
        try:
            cmd = [
                "npx", "ts-node", "--transpile-only", "-e",
                "import { PrismaClient } from '@prisma/client'; const prisma = new PrismaClient(); "
                f"prisma.$queryRaw`SELECT COUNT(*) as count FROM order_clients WHERE customer_id = {provider_id}`"
                ".then(r => console.log('VERIFIED:' + r[0].count)).finally(() => prisma.$disconnect());"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=30)
            output = result.stdout + result.stderr
            return "VERIFIED:1" in output or "VERIFIED:2" in output or "VERIFIED:3" in output
        except Exception as e:
            self._learn_from_verification_error("order_clients", provider_id, str(e))
            return False

    def _learn_from_verification_error(self, table: str, id_value: str, error: str):
        """Learn from verification errors to improve future attempts."""
        import os
        from datetime import datetime

        learning_entry = f"""
## Verification Error - {datetime.now().isoformat()}

Table: {table}
ID: {id_value}
Error: {error}

This verification failed. Possible causes:
1. Race condition - record not yet committed
2. Wrong ID type (string vs number)
3. Connection issue

Action: Consider adding retry logic or delay before verification.
"""
        # Write to learning log
        log_path = Path("/Users/hung.l/src/lis-code-agent/memory/verification_errors.md")
        os.makedirs(log_path.parent, exist_ok=True)
        with open(log_path, 'a') as f:
            f.write(learning_entry + "\n")

    def _self_heal_ehr_integration(self, ticket, provider_id: str, practice_id: str,
                                  customer_id: str, customer_firstname: str,
                                  customer_lastname: str, npi: str,
                                  clinic_name: str, emr_name: str, folder: str) -> dict:
        """Self-heal ehr_integrations by direct database insertion."""
        import subprocess
        from pathlib import Path

        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")

        try:
            # Direct database insertion using npx ts-node
            safe_clinic_name = clinic_name.replace("'", "''") if clinic_name else "Unknown"
            safe_npi = npi or "0000000000"
            safe_folder = folder or "default"

            cmd = f"""import {{ PrismaClient }} from '@prisma/client'; const {{ createId }} = require('@paralleldrive/cuid2');
const prisma = new PrismaClient();
async function fix() {{
  const id = createId();
  const npiVal = '{safe_npi}';
  await prisma.\\$executeRaw\\`
    INSERT INTO ehr_integrations (
      id, customer_id, clinic_id, ehr_vendor_id, integration_type, integration_origin,
      priority, status, clinic_name, customer_npi, effective_npi,
      contact_name, contact_email, ordering_enabled, result_enabled, sftp_enabled,
      api_enabled, hl7_version, msh06_receiving_facility,
      use_vendor_sftp_config, sftp_result_path, sftp_archive_path,
      kit_delivery_option, legacy_emr_service, legacy_result_send_type,
      created_at, updated_at, requested_by, last_modified_by
    ) VALUES (
      \\${{id}}, '{customer_id}', '{practice_id}',
      (SELECT id FROM ehr_vendors WHERE LOWER(code) = '{emr_name.lower()}' LIMIT 1),
      'FULL_INTEGRATION', 'NEW_INTEGRATION', 'NORMAL', 'LIVE',
      '{safe_clinic_name}', npiVal, npiVal,
      'Leo', 'hung.l@zymebalanz.com', 1, 1, 1, 0, '2.3', '{practice_id}',
      1, '/{safe_folder}/results/', '/{safe_folder}/results/archive',
      'NO_DELIVERY', '{emr_name.upper()}', 'SFTP',
      NOW(), NOW(), '{ticket.key}', 'Leo'
    )
  \\`;
  console.log('Self-healed ehr_integrations for customer_id:', '{customer_id}');
  await prisma.\\$disconnect();
}}
fix().catch(console.error);
"""

            result = subprocess.run([
                "npx", "ts-node", "--transpile-only", "-e", cmd
            ], capture_output=True, text=True, cwd=repo_path, timeout=60)

            if "Self-healed" in result.stdout or "Self-healed" in result.stderr:
                return {"success": True, "message": "Direct database insertion successful"}
            else:
                return {"success": False, "message": f"Direct insertion failed: {result.stderr[:200]}"}
        except Exception as e:
            return {"success": False, "message": f"Self-heal error: {str(e)}"}

    def _self_heal_order_client(self, ticket, provider_id: str,
                                customer_firstname: str, customer_lastname: str,
                                npi: str, clinic_name: str,
                                emr_name: str, folder: str) -> dict:
        """Self-heal order_clients by direct database insertion."""
        import subprocess
        from pathlib import Path

        repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")

        try:
            customer_name = f"{customer_firstname} {customer_lastname}"
            remote_folder = f"/{folder}/orders/" if folder else "/orders/"

            cmd = f"""import {{ PrismaClient }} from '@prisma/client';
const prisma = new PrismaClient();
async function fix() {{
  await prisma.\\$executeRaw\\`
    INSERT INTO order_clients (
      customer_name, customer_id, customer_provider_NPI, customer_practice_name,
      clinic_id, kits_options, emr_name, remote_folder_path
    ) VALUES (
      '{customer_name.replace("'", "''")}', {provider_id}, '{npi}', '{clinic_name.replace("'", "''")}',
      {provider_id}, 0, '{emr_name}', '{remote_folder}'
    )
  \\`;
  console.log('Self-healed order_clients for provider_id:', provider_id);
  await prisma.\\$disconnect();
}}
fix().catch(console.error);
"""

            result = subprocess.run([
                "npx", "ts-node", "--transpile-only", "-e", cmd
            ], capture_output=True, text=True, cwd=repo_path, timeout=60)

            if "Self-healed" in result.stdout or "Self-healed" in result.stderr:
                return {"success": True, "message": "Direct database insertion successful"}
            else:
                return {"success": False, "message": f"Direct insertion failed: {result.stderr[:200]}"}
        except Exception as e:
            return {"success": False, "message": f"Self-heal error: {str(e)}"}

    def handle_scan(self):
        """Scan for new tickets."""
        console.print("\n[bold]Scanning for new tickets...[/bold]")

        tickets = self.processor.scan_tickets(limit=10)

        if not tickets:
            console.print("[yellow]No new tickets found.[/yellow]")
            return

        from rich.table import Table
        table = Table(title="New Tickets")
        table.add_column("Key", style="cyan")
        table.add_column("Summary")
        table.add_column("Status")
        table.add_column("Type")

        for ticket in tickets[:5]:
            table.add_row(ticket.key, ticket.summary[:50], ticket.status, ticket.issue_type)

        console.print(table)

        # Ask which to analyze
        choice = self.prompt_session.prompt(
            "\nEnter ticket ID to analyze, or press Enter: ",
            style=self.get_prompt_style()
        )
        if choice:
            self.handle_analyze(choice)

    def handle_teach(self):
        """Teach the agent something new."""
        console.print("\n[bold]Teach the Agent[/bold]\n")

        console.print("What do you want to teach?")
        console.print("  1. A pattern for a specific repo")
        console.print("  2. A gotcha (common pitfall)")
        console.print("  3. General Q&A")

        choices = [
            {"name": "pattern", "message": "A pattern for a specific repo"},
            {"name": "gotcha", "message": "A gotcha (common pitfall)"},
            {"name": "qa", "message": "General Q&A"},
        ]

        choice_name = self.prompt_session.prompt(
            "Choose (pattern/gotcha/qa): ",
            style=self.get_prompt_style()
        )

        if choice_name == "pattern":
            repo = self.prompt_session.prompt("Repo name: ", style=self.get_prompt_style())
            pattern = self.prompt_session.prompt("Pattern name: ", style=self.get_prompt_style())
            description = self.prompt_session.prompt("Description: ", style=self.get_prompt_style())
            self.memory.learn_repo_pattern(repo, pattern, description)

        elif choice_name == "gotcha":
            repo = self.prompt_session.prompt(
                "Repo name (optional): ",
                default="general",
                style=self.get_prompt_style()
            )
            gotcha = self.prompt_session.prompt("What's the pitfall? ", style=self.get_prompt_style())
            solution = self.prompt_session.prompt("What's the solution? ", style=self.get_prompt_style())
            self.memory.learn_gotcha(repo, gotcha, solution)

        elif choice_name == "qa":
            question = self.prompt_session.prompt("Question: ", style=self.get_prompt_style())
            answer = self.prompt_session.prompt("Answer: ", style=self.get_prompt_style())
            self.memory.learn_qa(question, answer)

        console.print("\n[green]✓ Learned![/green]")

    def handle_report(self):
        """Generate a quick report."""
        console.print("\n[bold]Generating quick report...[/bold]")

        tickets = self.jira.get_assigned_tickets(limit=10)

        # Count by status
        from collections import Counter
        status_counts = Counter(t.status for t in tickets)
        type_counts = Counter(t.issue_type for t in tickets)

        console.print(Panel(
            f"""[bold]Assigned Tickets:[/bold] {len(tickets)}

[bold]By Status:[/bold]
{chr(10).join(f'  • {k}: {v}' for k, v in status_counts.most_common())}

[bold]By Type:[/bold]
{chr(10).join(f'  • {k}: {v}' for k, v in type_counts.most_common())}""",
            title="[bold cyan]Quick Report[/bold cyan]",
            border_style="cyan"
        ))

    def handle_memory(self):
        """Show memory."""
        console.print("\n[bold]Agent Memory:[/bold]\n")

        memory = self.memory.read_memory()

        # Show recent learnings
        if "## Questions" in memory:
            console.print("[cyan]Q&A (Recent learnings):[/cyan]")
            lines = memory.split("## Questions\n")[1].split("\n")
            for line in lines[:10]:
                if line.strip():
                    console.print(f"  {line}")

    def run(self):
        """Run the interactive loop."""
        self.show_welcome()

        while self.running:
            try:
                user_input = self.prompt_session.prompt(
                    self.get_prompt_text(),
                    style=self.get_prompt_style()
                )

                if not user_input:
                    continue

                # Parse command
                parts = user_input.split(maxsplit=1)
                command = parts[0].lower().strip()
                arg = parts[1].strip() if len(parts) > 1 else ""

                if command in ["exit", "quit", "q"]:
                    console.print("[yellow]Goodbye![/yellow]")
                    self.running = False

                elif command == "analyze":
                    if arg:
                        self.handle_analyze(arg)
                    else:
                        console.print("[yellow]Usage: analyze <ticket-id>[/yellow]")

                elif command == "scan":
                    self.handle_scan()

                elif command == "report":
                    self.handle_report()

                elif command == "clear":
                    self.conversation_history = []
                    console.print("[yellow]對話已清空[/yellow]")

                elif command == "exec":
                    # Explicit iterative execution command
                    if arg:
                        import asyncio
                        asyncio.run(self.handle_iterative_task(arg))
                    else:
                        console.print("[yellow]Usage: exec <task description>[/yellow]")

                else:
                    # Check if this is an iterative task (write code + execute)
                    if self._detect_iterative_task(user_input):
                        import asyncio
                        asyncio.run(self.handle_iterative_task(user_input))
                    else:
                        # Regular question
                        self.handle_ask(user_input)

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit.[/yellow]")
            except EOFError:
                self.running = False


def main():
    """Entry point for prompt_toolkit interactive mode."""
    agent = PromptToolkitInteractiveAgent()
    agent.run()


if __name__ == "__main__":
    main()
