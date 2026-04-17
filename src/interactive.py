"""
Interactive Mode - Chat with the agent and teach it.

This allows you to:
1. Ask questions about tickets
2. Request analysis
3. Teach the agent new patterns
4. Give feedback on its decisions
"""
from __future__ import annotations

import os
import sys
from pathlib import Path as PathlibPath

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Prompt
from rich.table import Table

from src.config import get_settings
from src.integrations.jira import JiraClient
from src.core.ticket_processor import TicketProcessor
from src.memory.manager import MemoryManager

load_dotenv()

console = Console()


class InteractiveAgent:
    """Interactive agent that can chat, learn, and execute tasks."""

    def __init__(self):
        """Initialize the interactive agent."""
        self.jira = JiraClient()
        self.processor = TicketProcessor(dry_run=False)
        self.memory = MemoryManager()
        self.running = True

    def show_welcome(self):
        """Show welcome message."""
        console.print(Panel.fit(
            "[bold cyan]LIS Code Agent - Interactive Mode[/bold cyan]\n\n"
            "Commands:\n"
            "  • [yellow]ask[/yellow] <question> - Ask a question\n"
            "  • [yellow]analyze[/yellow] <ticket> - Analyze a ticket\n"
            "  • [yellow]scan[/yellow] - Scan for new tickets\n"
            "  • [yellow]teach[/yellow] - Teach the agent something new\n"
            "  • [yellow]report[/yellow] - Generate a report\n"
            "  • [yellow]memory[/yellow] - Show memory\n"
            "  • [yellow]exit[/yellow] - Exit",
            title="🤖",
            border_style="cyan"
        ))

    def handle_ask(self, question: str):
        """Handle a question from the user."""
        console.print(f"\n[bold]Question:[/bold] {question}")

        # Try to answer from memory first
        memory = self.memory.read_memory()

        # Use Claude to generate answer
        response = self.processor.claude.messages.create(
            model=get_settings().default_model,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": f"""You are LIS Code Agent, a helpful assistant for Leo.

IMPORTANT: Always answer in **Traditional Chinese (繁體中文)** unless explicitly asked to use English.

Context about the repos and patterns:
{memory}

User's question: {question}

Provide a helpful answer in Chinese. If you're uncertain, say so explicitly and suggest what information would help."""
                }
            ]
        )

        answer = response.content[0].text
        console.print(Panel(answer, title="[bold green]Answer[/bold green]", border_style="green"))

        # Offer to learn
        if console.input("\n[yellow]Was this helpful? Should I remember this?[/yellow] (y/N): ").lower() == "y":
            question_key = console.input("[yellow]Give this knowledge a short key/summary:[/yellow] ")
            self.memory.learn_qa(question, f"Q: {question}\nA: {answer}")
            console.print("[green]✓ Learned![/green]")

    def handle_analyze(self, ticket_id: str):
        """Analyze a ticket."""
        console.print(f"\n[bold]Analyzing ticket:[/bold] {ticket_id}")

        try:
            ticket = self.jira.get_ticket(ticket_id)
            analysis = self.processor.analyze_ticket(ticket)

            # Build the display content
            content = f"""[bold]Ticket:[/bold] {ticket.key}
[bold]Summary:[/bold] {ticket.summary}

[bold]Status:[/bold] {ticket.status} | [bold]Type:[/bold] {ticket.issue_type} | [bold]Priority:[/bold] {ticket.priority or 'N/A'}

[bold]Description:[/bold]
{ticket.description[:500]}{'...' if len(ticket.description) > 500 else ''}

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
                download = console.input("\n[yellow]Download attachment?[/yellow] (y/N): ")
                if download.lower() == "y":
                    for att in ticket.attachments:
                        try:
                            path = self.jira.download_attachment(att.get('content'))
                            console.print(f"[green]✓ Downloaded to:[/green] {path}")
                        except Exception as e:
                            console.print(f"[red]✗ Download failed:[/red] {e}")

            # Ask for feedback
            feedback = console.input("\n[yellow]Is this correct? Any feedback?[/yellow] (or press Enter to continue): ")
            if feedback:
                # Learn from feedback
                self.memory.learn_qa(
                    f"Ticket analysis for {ticket_id}",
                    f"Analysis: {analysis}\nFeedback: {feedback}"
                )
                console.print("[green]✓ Feedback recorded![/green]")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def handle_scan(self):
        """Scan for new tickets."""
        console.print("\n[bold]Scanning for new tickets...[/bold]")

        tickets = self.processor.scan_tickets(limit=10)

        if not tickets:
            console.print("[yellow]No new tickets found.[/yellow]")
            return

        table = Table(title="New Tickets")
        table.add_column("Key", style="cyan")
        table.add_column("Summary")
        table.add_column("Status")
        table.add_column("Type")

        for ticket in tickets[:5]:
            table.add_row(ticket.key, ticket.summary[:50], ticket.status, ticket.issue_type)

        console.print(table)

        # Ask which to analyze
        choice = console.input("\n[yellow]Enter ticket ID to analyze, or press Enter:[/yellow] ")
        if choice:
            self.handle_analyze(choice)

    def handle_teach(self):
        """Teach the agent something new."""
        console.print("\n[bold]Teach the Agent[/bold]\n")

        console.print("What do you want to teach?")
        console.print("  1. A pattern for a specific repo")
        console.print("  2. A gotcha (common pitfall)")
        console.print("  3. General Q&A")

        choice = Prompt.ask(
            "[yellow]Choose[/yellow]",
            choices=["pattern", "gotcha", "qa"],
            default="qa"
        )

        if choice == "pattern":
            repo = console.input("[yellow]Repo name:[/yellow] ")
            pattern = console.input("[yellow]Pattern name:[/yellow] ")
            description = console.input("[yellow]Description:[/yellow] ")
            self.memory.learn_repo_pattern(repo, pattern, description)

        elif choice == "gotcha":
            repo = console.input("[yellow]Repo name (optional):[/yellow] ") or "general"
            gotcha = console.input("[yellow]What's the pitfall?[/yellow] ")
            solution = console.input("[yellow]What's the solution?[/yellow] ")
            self.memory.learn_gotcha(repo, gotcha, solution)

        elif choice == "qa":
            question = console.input("[yellow]Question:[/yellow] ")
            answer = console.input("[yellow]Answer:[/yellow] ")
            self.memory.learn_qa(question, answer)

        console.print("[green]✓ Learned![/green]")

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
        if "Questions" in memory:
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
                user_input = console.input("\n[bold cyan]>>> [/bold cyan]").strip()

                if not user_input:
                    continue

                # Parse command
                parts = user_input.split(maxsplit=1)
                command = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if command in ["exit", "quit", "q"]:
                    console.print("[yellow]Goodbye![/yellow]")
                    self.running = False

                elif command == "ask":
                    if arg:
                        self.handle_ask(arg)
                    else:
                        console.print("[yellow]Usage: ask <your question>[/yellow]")

                elif command == "analyze":
                    if arg:
                        self.handle_analyze(arg)
                    else:
                        console.print("[yellow]Usage: analyze <ticket-id>[/yellow]")

                elif command == "scan":
                    self.handle_scan()

                elif command == "teach":
                    self.handle_teach()

                elif command == "report":
                    self.handle_report()

                elif command == "memory":
                    self.handle_memory()

                else:
                    # Treat as a question
                    self.handle_ask(user_input)

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit.[/yellow]")
            except EOFError:
                self.running = False


def main():
    """Entry point for interactive mode."""
    try:
        from rich import print as rprint
    except ImportError:
        console.print("[yellow]Installing rich for better display...[/yellow]")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "rich"])
        from rich import print as rprint

    agent = InteractiveAgent()
    agent.run()


if __name__ == "__main__":
    main()
