"""
Interactive Mode - Chat with the agent and teach it.

This allows you to:
1. Ask questions about tickets
2. Request analysis
3. Teach the agent new patterns
4. Give feedback on its decisions

Simplified version to avoid terminal issues with rich library.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from src.integrations.jira import JiraClient
from src.core.ticket_processor import TicketProcessor
from src.memory.manager import MemoryManager

load_dotenv()


class SimpleInteractiveAgent:
    """Simplified interactive agent using plain I/O to avoid rich library issues."""

    def __init__(self):
        """Initialize the interactive agent."""
        self.jira = JiraClient()
        self.processor = TicketProcessor(dry_run=False)
        self.memory = MemoryManager()
        self.running = True

    def show_welcome(self):
        """Show welcome message."""
        print("=" * 60)
        print("LIS Code Agent - Interactive Mode")
        print("=" * 60)
        print()
        print("Commands:")
        print("  • ask <question> - Ask a question")
        print("  • analyze <ticket> - Analyze a ticket")
        print("  • scan - Scan for new tickets")
        print("  • teach - Teach the agent something new")
        print("  • report - Generate a report")
        print("  • memory - Show memory")
        print("  • exit - Exit")
        print()
        print("=" * 60)

    def handle_ask(self, question: str):
        """Handle a question from the user."""
        print(f"\nQuestion: {question}")

        # Use Claude to generate answer
        memory = self.memory.read_memory()

        response = self.processor.claude.messages.create(
            model="claude-sonnet-4-6",
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
        print(f"\nAnswer:")
        print("-" * 40)
        print(answer)
        print("-" * 40)

        # Offer to learn
        learn = input("\nWas this helpful? Should I remember this? (y/N): ").strip().lower()
        if learn == "y":
            self.memory.learn_qa(question, f"Q: {question}\nA: {answer}")
            print("✓ Learned!")

    def handle_analyze(self, ticket_id: str):
        """Analyze a ticket."""
        print(f"\nAnalyzing ticket: {ticket_id}")

        try:
            ticket = self.jira.get_ticket(ticket_id)
            analysis = self.processor.analyze_ticket(ticket)

            # Show analysis
            print(f"\n{'='*60}")
            print(f"Ticket: {ticket.key}")
            print(f"Summary: {ticket.summary}")
            print(f"Status: {ticket.status} | Type: {ticket.issue_type} | Priority: {ticket.priority or 'N/A'}")
            print()
            print(f"Description:")
            desc = ticket.description[:500] + "..." if len(ticket.description) > 500 else ticket.description
            print(desc)
            print()
            print(f"Analysis:")
            print(f"  Confidence: {analysis['confidence']}")
            print(f"  Repos: {', '.join(analysis['repos']) or 'None found'}")
            print(f"  Reasoning: {analysis.get('reasoning', 'N/A')}")
            print()

            # Show attachments
            if ticket.attachments:
                print(f"Attachments ({len(ticket.attachments)}):")
                for att in ticket.attachments:
                    print(f"  • {att.get('filename')} ({att.get('mimeType', 'unknown')})")
                    print(f"    URL: {att.get('content')}")

                    # Ask if user wants to download
                    download = input(f"\nDownload {att.get('filename')}? (y/N): ").strip().lower()
                    if download == "y":
                        try:
                            path = self.jira.download_attachment(att.get('content'))
                            print(f"✓ Downloaded to: {path}")
                        except Exception as e:
                            print(f"✗ Download failed: {e}")

            print("="*60)

            # Ask for feedback
            feedback = input("\nIs this correct? Any feedback? (or press Enter to continue): ")
            if feedback:
                self.memory.learn_qa(
                    f"Ticket analysis for {ticket_id}",
                    f"Analysis: {analysis}\nFeedback: {feedback}"
                )
                print("✓ Feedback recorded!")

        except Exception as e:
            print(f"Error: {e}")

    def handle_scan(self):
        """Scan for new tickets."""
        print("\nScanning for new tickets...")

        tickets = self.processor.scan_tickets(limit=10)

        if not tickets:
            print("No new tickets found.")
            return

        print(f"\nFound {len(tickets)} ticket(s):")
        for i, ticket in enumerate(tickets[:5], 1):
            print(f"  {i}. [{ticket.key}] {ticket.summary}")
            print(f"     Status: {ticket.status} | Type: {ticket.issue_type}")

        # Ask which to analyze
        choice = input("\nEnter ticket ID to analyze, or press Enter: ")
        if choice:
            self.handle_analyze(choice)

    def handle_teach(self):
        """Teach the agent something new."""
        print("\nTeach the Agent")
        print()
        print("What do you want to teach?")
        print("  1. A pattern for a specific repo")
        print("  2. A gotcha (common pitfall)")
        print("  3. General Q&A")

        choice = input("Choose (pattern/gotcha/qa): ").strip().lower()

        if choice == "pattern":
            repo = input("Repo name: ")
            pattern = input("Pattern name: ")
            description = input("Description: ")
            self.memory.learn_repo_pattern(repo, pattern, description)

        elif choice == "gotcha":
            repo = input("Repo name (optional): ") or "general"
            gotcha = input("What's the pitfall? ")
            solution = input("What's the solution? ")
            self.memory.learn_gotcha(repo, gotcha, solution)

        elif choice == "qa":
            question = input("Question: ")
            answer = input("Answer: ")
            self.memory.learn_qa(question, answer)

        print("✓ Learned!")

    def handle_report(self):
        """Generate a quick report."""
        print("\nGenerating quick report...")

        tickets = self.jira.get_assigned_tickets(limit=10)

        # Count by status
        from collections import Counter
        status_counts = Counter(t.status for t in tickets)
        type_counts = Counter(t.issue_type for t in tickets)

        print()
        print(f"Assigned Tickets: {len(tickets)}")
        print()
        print("By Status:")
        for status, count in status_counts.most_common():
            print(f"  • {status}: {count}")
        print()
        print("By Type:")
        for issue_type, count in type_counts.most_common():
            print(f"  • {issue_type}: {count}")

    def handle_memory(self):
        """Show memory."""
        print("\nAgent Memory:")
        print()

        memory = self.memory.read_memory()

        # Show recent learnings
        if "## Questions" in memory:
            print("Q&A (Recent learnings):")
            lines = memory.split("## Questions\n")[1].split("\n")
            for line in lines[:10]:
                if line.strip():
                    print(f"  {line}")

    def run(self):
        """Run the interactive loop."""
        self.show_welcome()

        while self.running:
            try:
                user_input = input(">>> ").strip()

                if not user_input:
                    continue

                # Parse command
                parts = user_input.split(maxsplit=1)
                command = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if command in ["exit", "quit", "q"]:
                    print("Goodbye!")
                    self.running = False

                elif command == "ask":
                    if arg:
                        self.handle_ask(arg)
                    else:
                        print("Usage: ask <your question>")

                elif command == "analyze":
                    if arg:
                        self.handle_analyze(arg)
                    else:
                        print("Usage: analyze <ticket-id>")

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
                print("\nUse 'exit' to quit.")
            except EOFError:
                self.running = False


def main():
    """Entry point for simple interactive mode."""
    agent = SimpleInteractiveAgent()
    agent.run()


if __name__ == "__main__":
    main()
