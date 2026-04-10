#!/usr/bin/env python3
"""
Analyze VP-15942 - File size issue (different domain from EMR Integration)

This tests the agent's general problem-solving capabilities.
"""

import sys
sys.path.insert(0, "/Users/hung.l/src/lis-code-agent")

from src.core.markdown_executor import MarkdownExecutor
from src.integrations.jira import JiraClient
from unittest.mock import Mock


def main():
    print("\n" + "=" * 80)
    print("ANALYZING TICKET: VP-15942 (Different Domain)")
    print("=" * 80)

    # Fetch the ticket
    client = JiraClient()
    ticket = client.get_ticket("VP-15942")

    print(f"\n📞 Ticket: {ticket.key}")
    print(f"📝 Summary: {ticket.summary}")
    print(f"📄 Description: {ticket.description}")
    print(f"📊 Status: {ticket.status}")
    print(f"🔑 Type: {ticket.issue_type}")
    print(f"🚨 Priority: {ticket.priority}")

    # Initialize executor
    executor = MarkdownExecutor()

    from src.skills.loader import get_skill_loader
    loader = get_skill_loader()

    # Use debugging skill for general problem analysis
    debug_skill = loader.get_skill("debugging")
    soul = loader.get_soul_md()
    tools = loader.get_tools_md()

    # ============================================================
    # PHASE 0: Pre-Analysis
    # ============================================================
    print("\n" + "=" * 80)
    print("🔍 PHASE 0: Pre-Analysis")
    print("=" * 80)

    # This is NOT an EMR integration ticket, so we use general Phase 0
    phase_0_result = executor._phase_0_pre_analysis(
        ticket, Mock(), soul, tools, debug_skill
    )

    if not phase_0_result.get("can_proceed"):
        print("\n🚨 PHASE 0 BLOCKER!")
        print("\n" + phase_0_result.get("message", ""))
        questions = phase_0_result.get("questions", [])
        if questions:
            print("\n📋 Clarifying Questions:")
            for i, q in enumerate(questions, 1):
                print(f"   {i}. {q}")
    else:
        print("\n✅ Phase 0 PASSED")
        print(f"   {phase_0_result.get('message', '')}")

    # ============================================================
    # PROBLEM ANALYSIS
    # ============================================================
    print("\n" + "=" * 80)
    print("🧠 PROBLEM ANALYSIS")
    print("=" * 80)

    print("\n📋 Problem Statement:")
    print("   - Cerbo has 15MB file size limit")
    print("   - We sent a 28MB file")
    print("   - Need to reduce file size")

    print("\n🔍 Key Facts:")
    print("   - Accession ID: 2603046143")
    print("   - Provider: Causenta Wellness (ID: 8105)")
    print("   - Practice ID: 124500")
    print("   - Previously implemented: compression solutions")

    print("\n❓ Questions to Investigate:")
    print("   1. What is in the 28MB file? (number of results, images, etc.)")
    print("   2. What compression is currently applied?")
    print("   3. Can we compress further without losing quality?")
    print("   4. Can we split large files into multiple smaller files?")
    print("   5. Is there an alternative delivery method (SFTP, API, etc.)?")

    # ============================================================
    # SUGGESTED VERIFICATION
    # ============================================================
    print("\n" + "=" * 80)
    print("🔧 SUGGESTED VERIFICATION STEPS")
    print("=" * 80)

    print("\n1️⃣ Check the actual file:")
    print("   - Find the result file for Accession ID: 2603046143")
    print("   - Check file size, content type, number of results")

    print("\n2️⃣ Check current compression logic:")
    print("   - grep for compression code in result generation")
    print("   - Check if Cerbo-specific handling exists")

    print("\n3️⃣ Check Cerbo SFTP configuration:")
    print("   - How are files currently sent to Cerbo?")
    print("   - Is there size validation before sending?")

    # ============================================================
    # POSSIBLE SOLUTIONS
    # ============================================================
    print("\n" + "=" * 80)
    print("💡 POSSIBLE SOLUTIONS")
    print("=" * 80)

    print("\nOption 1: Enhanced Compression")
    print("   - Increase image compression ratio")
    print("   - Remove unnecessary whitespace/formatting")
    print("   - Use binary format instead of text")

    print("\nOption 2: File Splitting")
    print("   - Split large result sets into multiple files")
    print("   - Send as batch with sequence numbers")

    print("\nOption 3: Content Optimization")
    print("   - Exclude redundant data")
    print("   - Use references instead of duplicating data")
    print("   - Remove optional sections that Cerbo doesn't use")

    print("\nOption 4: Alternative Delivery")
    print("   - Use API instead of file (if Cerbo supports)")
    print("   - Host file and send download link")
    print("   - Use streaming instead of batch")

    print("\n" + "=" * 80)
    print("📋 NEXT STEPS")
    print("=" * 80)
    print("\n1. Investigate the 28MB file content")
    print("2. Review current compression implementation")
    print("3. Propose specific solution based on findings")
    print("4. Test with Cerbo before deploying")

    return 0


if __name__ == "__main__":
    sys.exit(main())
