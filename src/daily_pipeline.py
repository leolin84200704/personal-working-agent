"""
Daily Pipeline Service - Runs daily at 9am to scan Jira tickets and generate reports.

Features:
1. Scans for new and unresolved tickets
2. Analyzes tickets and generates solutions
3. Creates code updates when applicable
4. Generates daily report for Leo
"""
from __future__ import annotations

import asyncio
import os
import sched
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.integrations.jira import JiraClient, JiraTicket
from src.core.ticket_processor import TicketProcessor
from src.memory.manager import MemoryManager

load_dotenv()


class DailyPipelineService:
    """
    Service that runs daily at 9am to process Jira tickets.

    Usage:
        # Run once immediately
        service = DailyPipelineService()
        service.run_once()

        # Start scheduler (runs daily at 9am)
        service.start()
    """

    def __init__(self):
        """Initialize the pipeline service."""
        self.jira = JiraClient()
        self.memory = MemoryManager()
        self.processor = TicketProcessor(dry_run=False)
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.running = False

        # Output directory for reports
        self.output_dir = Path(__file__).parent.parent / "output" / "daily_reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_new_tickets(self, since_hours: int = 24) -> list[JiraTicket]:
        """
        Get tickets created in the last N hours.

        Args:
            since_hours: Hours to look back for new tickets

        Returns:
            List of new Jira tickets
        """
        # Use JQL to find tickets created recently
        # Note: This is a simplified version - actual JQL would depend on your Jira setup
        all_tickets = self.jira.get_assigned_tickets(limit=50)

        # Filter by creation time (last 24 hours)
        cutoff = datetime.now() - timedelta(hours=since_hours)
        new_tickets = []

        for ticket in all_tickets:
            # In real implementation, you'd parse created date from ticket
            # For now, return all open tickets
            if ticket.status not in ["Closed", "Done", "Resolved"]:
                new_tickets.append(ticket)

        return new_tickets

    def get_unresolved_tickets(self) -> list[JiraTicket]:
        """
        Get all unresolved (open) tickets assigned to user.

        Returns:
            List of unresolved Jira tickets
        """
        return self.jira.get_assigned_tickets(
            status=None,  # Get all statuses
            limit=50
        )

    def analyze_ticket(self, ticket: JiraTicket) -> dict[str, Any]:
        """
        Analyze a ticket and generate solution/code update.

        Args:
            ticket: JiraTicket to analyze

        Returns:
            Analysis dict with solution, files to modify, code changes, etc.
        """
        # Use the ticket processor to analyze
        analysis = self.processor.analyze_ticket(ticket)

        # Try to determine solution
        solution = self._generate_solution(ticket, analysis)

        # Try to generate code updates
        code_updates = self._generate_code_updates(ticket, analysis) if analysis.get("repos") else []

        return {
            "ticket": ticket.key,
            "summary": ticket.summary,
            "status": ticket.status,
            "type": ticket.issue_type,
            "priority": ticket.priority or "None",
            "analysis": analysis,
            "solution": solution,
            "code_updates": code_updates,
        }

    def _generate_solution(self, ticket: JiraTicket, analysis: dict) -> str:
        """Generate a solution description for the ticket."""
        repos = analysis.get("repos", [])
        confidence = analysis.get("confidence", "low")
        reasoning = analysis.get("reasoning", "")

        if not repos:
            return f"⚠️ Could not identify relevant repos. Ticket needs manual review."

        if confidence == "high":
            return f"✅ Clear path forward: Modify {', '.join(repos)}. {reasoning}"
        elif confidence == "medium":
            return f"⚡ Likely solution: Modify {', '.join(repos)}. {reasoning}"
        else:
            return f"❓ Uncertain: May involve {', '.join(repos)}. {reasoning}. Needs confirmation."

    def _generate_code_updates(self, ticket: JiraTicket, analysis: dict) -> list[dict]:
        """Generate code updates for the ticket."""
        # In dry-run mode, just return the analysis
        # In production, would actually modify code
        return [
            {
                "repo": repo,
                "files": analysis.get("files", {}).get(repo, ["To be determined"]),
                "action": "create_branch" if ticket.ticket_type == "feature" else "fix_bug",
            }
            for repo in analysis.get("repos", [])
        ]

    def generate_daily_report(self) -> dict[str, Any]:
        """
        Generate the daily report.

        Returns:
            Report dict with new tickets, unresolved tickets, and analysis
        """
        print(f"\n{'='*60}")
        print(f"Daily Pipeline Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        # Get new tickets (last 24 hours)
        print("📋 Scanning for new tickets...")
        new_tickets = self.get_new_tickets(since_hours=24)
        print(f"   Found {len(new_tickets)} new tickets")

        # Get all unresolved tickets
        print("📋 Scanning for unresolved tickets...")
        unresolved_tickets = self.get_unresolved_tickets()
        print(f"   Found {len(unresolved_tickets)} unresolved tickets")

        # Analyze tickets
        print("\n🔍 Analyzing tickets...")
        analyses = []

        # Analyze new tickets first (higher priority)
        for ticket in new_tickets[:5]:  # Limit to 5 for efficiency
            print(f"   Analyzing {ticket.key}...")
            try:
                analysis = self.analyze_ticket(ticket)
                analyses.append(analysis)
            except Exception as e:
                print(f"      Error: {e}")
                analyses.append({
                    "ticket": ticket.key,
                    "error": str(e)
                })

        # Also analyze a few high-priority unresolved tickets
        high_priority = [t for t in unresolved_tickets if t.priority and t.priority in ["High", "Highest", "P1", "P2"]]
        for ticket in high_priority[:3]:
            if ticket.key not in [a.get("ticket") for a in analyses]:
                print(f"   Analyzing {ticket.key} (high priority)...")
                try:
                    analysis = self.analyze_ticket(ticket)
                    analyses.append(analysis)
                except Exception as e:
                    print(f"      Error: {e}")

        return {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "summary": {
                "new_tickets": len(new_tickets),
                "unresolved_tickets": len(unresolved_tickets),
                "analyzed": len(analyses),
            },
            "new_tickets": [
                {
                    "key": t.key,
                    "summary": t.summary,
                    "status": t.status,
                    "type": t.issue_type,
                    "priority": t.priority,
                }
                for t in new_tickets
            ],
            "unresolved_tickets": [
                {
                    "key": t.key,
                    "summary": t.summary,
                    "status": t.status,
                    "type": t.issue_type,
                    "priority": t.priority,
                }
                for t in unresolved_tickets[:20]  # Limit to 20
            ],
            "analyses": analyses,
        }

    def save_report(self, report: dict[str, Any]) -> Path:
        """
        Save report to file.

        Args:
            report: Report dict

        Returns:
            Path to saved report file
        """
        date_str = report["date"]
        timestamp = datetime.now().strftime("%H%M%S")

        # Save JSON
        json_path = self.output_dir / f"report_{date_str}_{timestamp}.json"
        import json
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Save Markdown
        md_path = self.output_dir / f"report_{date_str}_{timestamp}.md"
        md_content = self._format_report_markdown(report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n📄 Report saved:")
        print(f"   JSON: {json_path}")
        print(f"   Markdown: {md_path}")

        return md_path

    def _format_report_markdown(self, report: dict[str, Any]) -> str:
        """Format report as Markdown."""
        lines = [
            f"# Daily Pipeline Report",
            f"",
            f"**Date**: {report['date']} at {report['timestamp'][11:19]}",
            f"",
            f"## Summary",
            f"",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| New Tickets (24h) | {report['summary']['new_tickets']} |",
            f"| Unresolved Tickets | {report['summary']['unresolved_tickets']} |",
            f"| Analyzed | {report['summary']['analyzed']} |",
            f"",
        ]

        # New tickets section
        if report["new_tickets"]:
            lines.extend([
                f"## New Tickets (Last 24 Hours)",
                f"",
            ])
            for t in report["new_tickets"]:
                lines.extend([
                    f"### {t['key']} - {t['summary']}",
                    f"- **Status**: {t['status']}",
                    f"- **Type**: {t['type']}",
                    f"- **Priority**: {t['priority']}",
                    f"",
                ])

        # Unresolved tickets section
        if report["unresolved_tickets"]:
            lines.extend([
                f"## Unresolved Tickets",
                f"",
            ])
            for t in report["unresolved_tickets"]:
                lines.extend([
                    f"### {t['key']} - {t['summary']}",
                    f"- **Status**: {t['status']}",
                    f"- **Type**: {t['type']}",
                    f"- **Priority**: {t['priority']}",
                    f"",
                ])

        # Analyses section
        if report["analyses"]:
            lines.extend([
                f"## Ticket Analysis & Solutions",
                f"",
            ])
            for a in report["analyses"]:
                if "error" in a:
                    lines.extend([
                        f"### {a['ticket']} - Analysis Error",
                        f"``",
                        f"{a['error']}",
                        f"```",
                        f"",
                    ])
                    continue

                lines.extend([
                    f"### {a['ticket']} - {a.get('summary', '')}",
                    f"",
                    f"**Status**: {a['status']} | **Type**: {a['type']} | **Priority**: {a.get('priority', 'N/A')}",
                    f"",
                    f"#### Solution",
                    f"{a.get('solution', 'No solution generated')}",
                    f"",
                ])

                if a.get("code_updates"):
                    lines.extend([
                        f"#### Proposed Code Updates",
                        f"",
                    ])
                    for update in a["code_updates"]:
                        lines.extend([
                            f"- **{update['repo']}**",
                            f"  - Action: `{update['action']}`",
                            f"  - Files: {', '.join(update.get('files', ['TBD']))}",
                            f"",
                        ])

        lines.extend([
            f"---",
            f"",
            f"*Generated by LIS Code Agent*",
        ])

        return "\n".join(lines)

    def run_once(self):
        """Run the pipeline once immediately."""
        print("\n🚀 Starting daily pipeline run...")

        report = self.generate_daily_report()
        report_path = self.save_report(report)

        print(f"\n✅ Pipeline run complete!")
        print(f"📊 Total: {report['summary']['analyzed']} tickets analyzed")

        return report_path

    def _schedule_next_run(self):
        """Schedule the next run for 9am tomorrow."""
        now = datetime.now()

        # Calculate time until next 9am
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if next_run <= now:
            # If 9am already passed today, schedule for tomorrow
            from datetime import timedelta
            next_run = next_run + timedelta(days=1)

        delay = (next_run - now).total_seconds()

        print(f"\n⏰ Next run scheduled for {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   (in {delay/3600:.1f} hours)")

        self.scheduler.enter(delay, 1, self._run_and_reschedule)

    def _run_and_reschedule(self):
        """Run pipeline and schedule next run."""
        try:
            self.run_once()
        except Exception as e:
            print(f"\n❌ Pipeline error: {e}")
            import traceback
            traceback.print_exc()

        # Schedule next run
        if self.running:
            self._schedule_next_run()

    def start(self):
        """Start the daily pipeline scheduler."""
        print("\n" + "="*60)
        print("Daily Pipeline Service Starting")
        print("="*60)
        print(f"Run time: Daily at 9:00 AM")
        print(f"Press Ctrl+C to stop")
        print("="*60 + "\n")

        self.running = True

        # Schedule first run
        self._schedule_next_run()

        # Run the scheduler
        try:
            self.scheduler.run(blocking=True)
        except KeyboardInterrupt:
            print("\n\n🛑 Pipeline service stopped by user")
            self.running = False
        except Exception as e:
            print(f"\n\n❌ Scheduler error: {e}")
            self.running = False

    def stop(self):
        """Stop the pipeline scheduler."""
        self.running = False


def main():
    """CLI entry point for the daily pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Daily Pipeline Service - Scan Jira tickets and generate reports"
    )
    parser.add_argument(
        "action",
        choices=["run", "start", "test"],
        help="Action: run once, start scheduler, or test"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't make actual code changes"
    )

    args = parser.parse_args()

    service = DailyPipelineService()

    if args.action == "run":
        # Run once immediately
        service.run_once()
    elif args.action == "start":
        # Start scheduler
        service.start()
    elif args.action == "test":
        # Test mode - show what would be analyzed
        print("\n🧪 Test Mode - Showing analysis preview\n")

        new_tickets = service.get_new_tickets(since_hours=24)
        print(f"New tickets: {len(new_tickets)}")

        for ticket in new_tickets[:3]:
            print(f"\n{ticket.key}: {ticket.summary}")
            analysis = service.analyze_ticket(ticket)
            print(f"Solution: {analysis.get('solution', 'N/A')}")


if __name__ == "__main__":
    main()
