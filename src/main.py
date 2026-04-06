"""
LIS Code Agent - Main Entry Point

CLI for scanning and processing Jira tickets.
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from src.integrations.jira import JiraClient
from src.integrations.git_operator import find_git_repos
from src.core.ticket_processor import TicketProcessor
from src.memory.manager import MemoryManager
from src.daily_pipeline import DailyPipelineService
from src.interactive import InteractiveAgent

load_dotenv()


def cmd_scan(args) -> int:
    """Scan for and process assigned tickets."""
    print("=" * 60)
    print("LIS Code Agent - Ticket Scanner")
    print("=" * 60)
    print(f"Time: {datetime.now().isoformat()}")

    processor = TicketProcessor(dry_run=args.dry_run)

    # Scan for tickets
    tickets = processor.scan_tickets(limit=args.limit)

    if not tickets:
        print("\nNo new tickets to process.")
        return 0

    print(f"\nFound {len(tickets)} ticket(s):")
    for i, ticket in enumerate(tickets, 1):
        print(f"  {i}. [{ticket.key}] {ticket.summary}")
        print(f"     Type: {ticket.issue_type} | Status: {ticket.status}")

    # Process each ticket
    results = []
    for ticket in tickets:
        if args.interactive:
            response = input(f"\nProcess {ticket.key}? [y/N]: ")
            if response.lower() != "y":
                print(f"  Skipping {ticket.key}")
                continue

        try:
            result = processor.process_ticket(ticket)
            results.append(result)
        except Exception as e:
            print(f"\nError processing {ticket.key}: {e}")
            import traceback
            traceback.print_exc()

    # Summary
    print("\n" + "=" * 60)
    print("Processing Summary")
    print("=" * 60)
    for result in results:
        ticket = result["ticket"]
        branches = result.get("branches", [])
        print(f"  [{ticket}] Created {len(branches)} branch(es)")

    return 0


def cmd_analyze(args) -> int:
    """Analyze a single ticket."""
    jira = JiraClient()

    try:
        ticket = jira.get_ticket(args.ticket)
    except Exception as e:
        print(f"Error fetching ticket {args.ticket}: {e}")
        return 1

    print(f"\nTicket: {ticket.key}")
    print(f"Summary: {ticket.summary}")
    print(f"Type: {ticket.issue_type}")
    print(f"Status: {ticket.status}")
    print(f"\nDescription:\n{ticket.description}")

    # Analyze
    processor = TicketProcessor()
    analysis = processor.analyze_ticket(ticket)

    print(f"\n\nAnalysis:")
    print(f"  Confidence: {analysis['confidence']}")
    print(f"  Repos: {', '.join(analysis['repos'])}")
    print(f"  Reasoning: {analysis['reasoning']}")

    return 0


def cmd_memory(args) -> int:
    """Memory management commands."""
    memory = MemoryManager()

    if args.action == "show":
        which = args.which or "all"
        if which == "all" or which == "soul":
            print("=" * 60)
            print("SOUL.md")
            print("=" * 60)
            print(memory.read_soul())
        if which == "all" or which == "identity":
            print("\n" + "=" * 60)
            print("IDENTITY.md")
            print("=" * 60)
            print(memory.read_identity())
        if which == "all" or which == "user":
            print("\n" + "=" * 60)
            print("USER.md")
            print("=" * 60)
            print(memory.read_user())
        if which == "all" or which == "memory":
            print("\n" + "=" * 60)
            print("MEMORY.md")
            print("=" * 60)
            print(memory.read_memory())

    elif args.action == "learn":
        if args.type == "pattern":
            memory.learn_repo_pattern(
                args.repo,
                args.pattern,
                args.description,
            )
            print(f"Recorded pattern for {args.repo}")
        elif args.type == "gotcha":
            memory.learn_gotcha(
                args.repo,
                args.gotcha,
                args.solution,
            )
            print(f"Recorded gotcha for {args.repo}")
        elif args.type == "qa":
            memory.learn_qa(args.question, args.answer)
            print("Recorded Q&A")

    elif args.action == "update":
        # Update repo knowledge
        memory.update_repo_knowledge(
            args.repo,
            args.key,
            args.value,
        )
        print(f"Updated knowledge for {args.repo}")

    return 0


def cmd_repo(args) -> int:
    """Repository management commands."""
    base_path = Path(args.path)

    if args.action == "list":
        repos = find_git_repos(base_path)
        print(f"Found {len(repos)} repository(s):")
        for repo in repos:
            print(f"  - {repo.name} ({repo})")

    return 0


def cmd_config(args) -> int:
    """Show current configuration."""
    import os

    print("=" * 60)
    print("Configuration")
    print("=" * 60)

    # Environment
    print("\nEnvironment:")
    print(f"  REPOS_BASE_PATH: {os.getenv('REPOS_BASE_PATH', 'Not set')}")
    print(f"  JIRA_SERVER: {os.getenv('JIRA_SERVER', 'Not set')}")
    print(f"  JIRA_EMAIL: {os.getenv('JIRA_EMAIL', 'Not set')}")
    print(f"  ANTHROPIC_API_KEY: {'Set' if os.getenv('ANTHROPIC_API_KEY') else 'Not set'}")

    # Memory
    memory = MemoryManager()
    prefs = memory.get_user_preferences()

    print("\nBranch Prefixes:")
    for prefix_type, prefix in prefs.get("branch_prefixes", {}).items():
        print(f"  {prefix_type}: {prefix}")

    # Repos
    base_path = Path(os.getenv("REPOS_BASE_PATH", "/Users/hung.l/src"))
    repos = find_git_repos(base_path)
    print(f"\nDiscovered Repos: {len(repos)}")
    for repo in repos:
        print(f"  - {repo.name}")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="LIS Code Agent - Automate Jira ticket processing",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan and process tickets")
    scan_parser.add_argument(
        "-l", "--limit",
        type=int,
        default=10,
        help="Maximum number of tickets to process",
    )
    scan_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Don't make actual changes",
    )
    scan_parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Ask before processing each ticket",
    )

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a single ticket")
    analyze_parser.add_argument("ticket", help="Ticket ID (e.g., LIS-123)")

    # Memory command
    memory_parser = subparsers.add_parser("memory", help="Memory management")
    memory_parser.add_argument(
        "action",
        choices=["show", "learn", "update"],
        help="Memory action",
    )
    memory_parser.add_argument(
        "-w", "--which",
        choices=["soul", "identity", "user", "memory", "all"],
        default="all",
        help="Which memory file to show",
    )
    memory_parser.add_argument("--type", choices=["pattern", "gotcha", "qa"])
    memory_parser.add_argument("--repo")
    memory_parser.add_argument("--pattern")
    memory_parser.add_argument("--description")
    memory_parser.add_argument("--gotcha")
    memory_parser.add_argument("--solution")
    memory_parser.add_argument("--question")
    memory_parser.add_argument("--answer")
    memory_parser.add_argument("--key")
    memory_parser.add_argument("--value")

    # Repo command
    repo_parser = subparsers.add_parser("repo", help="Repository management")
    repo_parser.add_argument(
        "action",
        choices=["list"],
        help="Repo action",
    )
    repo_parser.add_argument(
        "-p", "--path",
        default="/Users/hung.l/src",
        help="Base path to scan for repos",
    )

    # Config command
    subparsers.add_parser("config", help="Show current configuration")

    # Pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="Daily pipeline service")
    pipeline_parser.add_argument(
        "action",
        choices=["run", "start", "test"],
        help="Pipeline action: run once, start scheduler, or test",
    )
    pipeline_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Don't make actual code changes",
    )

    # Interactive command
    subparsers.add_parser("interactive", help="Start interactive chat mode")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch command
    handlers = {
        "scan": cmd_scan,
        "analyze": cmd_analyze,
        "memory": cmd_memory,
        "repo": cmd_repo,
        "config": cmd_config,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    # Handle pipeline command separately (no args function)
    if args.command == "pipeline":
        service = DailyPipelineService()
        if args.action == "run":
            service.run_once()
        elif args.action == "start":
            service.start()
        elif args.action == "test":
            # Test mode
            print("\n🧪 Test Mode - Showing analysis preview\n")
            new_tickets = service.get_new_tickets(since_hours=24)
            print(f"New tickets: {len(new_tickets)}")
            for ticket in new_tickets[:3]:
                print(f"\n{ticket.key}: {ticket.summary}")
                analysis = service.analyze_ticket(ticket)
                print(f"Solution: {analysis.get('solution', 'N/A')}")
        return 0

    # Handle interactive command
    if args.command == "interactive":
        agent = InteractiveAgent()
        agent.run()
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
