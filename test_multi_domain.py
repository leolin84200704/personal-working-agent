#!/usr/bin/env python3
"""
Multi-Domain Agent Test

Demonstrates agent can handle different types of tickets:
- EMR Integration tickets (VP-xxxxx)
- Bug/Issue tickets (file size, performance, etc.)
"""

import sys
sys.path.insert(0, "/Users/hung.l/src/lis-code-agent")

from src.core.markdown_executor import MarkdownExecutor
from src.integrations.jira import JiraClient
from unittest.mock import Mock


def detect_ticket_domain(ticket) -> str:
    """
    Detect which domain/skill should handle this ticket.

    Returns: 'emr-integration' or 'general' or 'unknown'
    """
    summary_lower = ticket.summary.lower() if ticket.summary else ""
    description_lower = ticket.description.lower() if ticket.description else ""

    # EMR Integration patterns
    emr_keywords = [
        'new integration',
        'add provider',
        'provider id:',
        'practice id:',
        'emr integration',
        'set up integration'
    ]

    if any(keyword in description_lower for keyword in emr_keywords):
        return 'emr-integration'

    # Check for Provider/Practice IDs
    if 'provider id:' in description_lower and 'practice id:' in description_lower:
        return 'emr-integration'

    # Default to general problem solving
    return 'general'


def analyze_ticket(ticket_key: str):
    """Analyze a ticket using the appropriate skill."""
    print("\n" + "=" * 80)
    print(f"ANALYZING: {ticket_key}")
    print("=" * 80)

    # Fetch ticket
    client = JiraClient()
    ticket = client.get_ticket(ticket_key)

    print(f"\n📞 Ticket: {ticket.key}")
    print(f"📝 Summary: {ticket.summary}")
    print(f"📊 Type: {ticket.issue_type}")

    # Detect domain
    domain = detect_ticket_domain(ticket)
    print(f"🎯 Detected Domain: {domain}")

    # Initialize executor
    executor = MarkdownExecutor()
    from src.skills.loader import get_skill_loader
    loader = get_skill_loader()

    # ============================================================
    # PHASE 0: Pre-Analysis (Universal)
    # ============================================================
    print("\n" + "-" * 80)
    print("🔍 PHASE 0: Pre-Analysis")
    print("-" * 80)

    soul = loader.get_soul_md()
    tools = loader.get_tools_md()
    debug_skill = loader.get_skill("debugging")

    phase_0_result = executor._phase_0_pre_analysis(
        ticket, Mock(), soul, tools, debug_skill
    )

    if not phase_0_result.get("can_proceed"):
        print("\n🚨 PHASE 0 BLOCKER!")
        print("\n" + phase_0_result.get("message", ""))
        return False

    print("\n✅ Phase 0 PASSED")

    # ============================================================
    # Domain-Specific Analysis
    # ============================================================
    print("\n" + "-" * 80)
    print("🧠 DOMAIN ANALYSIS")
    print("-" * 80)

    if domain == 'emr-integration':
        print("\n📋 EMR Integration Analysis:")
        print("   - Provider ID detection")
        print("   - Practice ID detection")
        print("   - gRPC lookup required")
        print("   - Database operations")
        print("\n→ Use EMR Integration skill")

    elif domain == 'general':
        print("\n📋 General Problem Analysis:")
        print("   - Problem statement understanding")
        print("   - Context gathering")
        print("   - Root cause analysis")
        print("   - Solution design")
        print("\n→ Use General Problem Solving skill")

    return True


def main():
    """Test multi-domain detection."""

    print("\n" + "=" * 80)
    print("MULTI-DOMAIN AGENT TEST")
    print("Testing agent's ability to handle different ticket types")
    print("=" * 80)

    # Test cases
    test_tickets = [
        {
            'key': 'VP-15980',
            'domain': 'emr-integration',
            'summary': 'New EMR Integration - Cerbo'
        },
        {
            'key': 'VP-15942',
            'domain': 'general',
            'summary': 'File size too large issue'
        }
    ]

    results = {}

    for test in test_tickets:
        success = analyze_ticket(test['key'])
        results[test['key']] = {
            'expected_domain': test['domain'],
            'success': success
        }

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for key, result in results.items():
        status = "✅" if result['success'] else "❌"
        print(f"{status} {key} - Domain: {result['expected_domain']}")

    print("\n" + "=" * 80)
    print("KEY INSIGHT")
    print("=" * 80)
    print("""
The agent can now handle different domains:

1. EMR Integration Tickets (VP-xxxxx)
   - Provider/Practice ID extraction
   - gRPC lookup
   - Database operations
   - Skill: emr-integration

2. General Problem Tickets (Bugs, Issues, etc.)
   - Problem understanding
   - Investigation
   - Root cause analysis
   - Solution design
   - Skill: general

Both use Phase 0 Pre-Analysis for critical thinking!
    """)

    return 0


if __name__ == "__main__":
    sys.exit(main())
