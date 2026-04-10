#!/usr/bin/env python3
"""
Full Agent Test with Phase 0 Pre-Analysis

This test simulates the complete agent workflow:
1. Receives a ticket
2. Runs Phase 0 pre-analysis
3. Either blocks (asks questions) or proceeds with execution
"""

import sys
sys.path.insert(0, "/Users/hung.l/src/lis-code-agent")

from src.core.markdown_executor import MarkdownExecutor
from unittest.mock import Mock


def create_test_ticket(key: str, summary: str, description: str) -> Mock:
    """Create a mock Jira ticket."""
    ticket = Mock()
    ticket.key = key
    ticket.summary = summary
    ticket.description = description
    return ticket


def test_agent_workflow_vague_cors():
    """
    Test Case 1: Agent receives VP-16009 (vague CORS error)

    Expected: Phase 0 should BLOCK and ask clarifying questions
    """
    print("\n" + "=" * 80)
    print("TEST CASE 1: VP-16009 - Vague CORS Error")
    print("=" * 80)

    ticket = create_test_ticket(
        "VP-16009",
        "CORS error on VI Personal Settings",
        """When accessing the API from VI Personal Settings page, getting CORS error.

The request is blocked by CORS policy."""
    )

    print(f"\n📞 Ticket: {ticket.key}")
    print(f"📝 Summary: {ticket.summary}")
    print(f"📄 Description: {ticket.description[:100]}...")

    executor = MarkdownExecutor()

    # Load skills
    from src.skills.loader import get_skill_loader
    loader = get_skill_loader()

    skill = loader.get_skill("emr-integration")
    if not skill:
        skill = Mock()
        skill.get_section = Mock(return_value="")
        skill.content = ""

    soul = loader.get_soul_md()
    tools = loader.get_tools_md()
    phase_0_doc = loader.get_skill("debugging")

    # Run Phase 0 Pre-Analysis
    print("\n" + "-" * 80)
    print("🔍 PHASE 0: Pre-Analysis")
    print("-" * 80)

    phase_0_result = executor._phase_0_pre_analysis(
        ticket, skill, soul, tools, phase_0_doc
    )

    if not phase_0_result.get("can_proceed"):
        print("\n🚨 PHASE 0 BLOCKER DETECTED!")
        print("\n" + phase_0_result.get("message", ""))

        questions = phase_0_result.get("questions", [])
        if questions:
            print("\n📋 Clarifying Questions for User:")
            for i, q in enumerate(questions, 1):
                print(f"   {i}. {q}")

        verification = phase_0_result.get("verification_needed")
        if verification:
            print(f"\n🔧 Suggested Verification:")
            print(f"   Check: {verification.get('check')}")
            print(f"   Command: {verification.get('command')}")

        print("\n✅ AGENT BEHAVIOR: CORRECT!")
        print("   Agent blocked execution and asked for clarification.")
        print("   This prevents the 'add OPTIONS handlers blindly' mistake.")
        return True
    else:
        print("\n❌ AGENT BEHAVIOR: INCORRECT!")
        print("   Agent should have blocked but proceeded.")
        return False


def test_agent_workflow_complete_emr():
    """
    Test Case 2: Agent receives VP-15874 (complete EMR ticket)

    Expected: Phase 0 should PASS and proceed to execution
    """
    print("\n" + "=" * 80)
    print("TEST CASE 2: VP-15874 - Complete EMR Integration")
    print("=" * 80)

    ticket = create_test_ticket(
        "VP-15874",
        "Add Next Health providers - Epic Integration",
        """Please add the following providers for Next Health Epic integration.

Provider ID: 43262
Practice ID: 2930
Clinic Name: Next Health (West Hollywood)
EMR: Epic

Provider ID: 26232
Practice ID: 2930
Clinic Name: Next Health (West Hollywood)
EMR: Epic

[result_only mode - no order clients needed]"""
    )

    print(f"\n📞 Ticket: {ticket.key}")
    print(f"📝 Summary: {ticket.summary}")
    print(f"📄 Description (first 200 chars): {ticket.description[:200]}...")

    executor = MarkdownExecutor()

    from src.skills.loader import get_skill_loader
    loader = get_skill_loader()

    skill = loader.get_skill("emr-integration")
    if not skill:
        skill = Mock()
        skill.get_section = Mock(return_value="")
        skill.content = ""

    soul = loader.get_soul_md()
    tools = loader.get_tools_md()
    phase_0_doc = loader.get_skill("debugging")

    # Run Phase 0 Pre-Analysis
    print("\n" + "-" * 80)
    print("🔍 PHASE 0: Pre-Analysis")
    print("-" * 80)

    phase_0_result = executor._phase_0_pre_analysis(
        ticket, skill, soul, tools, phase_0_doc
    )

    if phase_0_result.get("can_proceed"):
        print("\n✅ PHASE 0 PASSED!")
        print("\n" + phase_0_result.get("message", ""))
        print("\n📋 Next Steps:")
        print("   1. LLM Analysis with verified assumptions")
        print("   2. Execute database operations")
        print("   3. Report results")

        print("\n✅ AGENT BEHAVIOR: CORRECT!")
        print("   Agent recognized complete information and will proceed.")
        return True
    else:
        print("\n❌ AGENT BEHAVIOR: INCORRECT!")
        print("   Agent should have passed but blocked.")
        print(f"\nBlocker message: {phase_0_result.get('message')}")
        return False


def test_agent_workflow_network_error():
    """
    Test Case 3: Agent receives vague network error ticket

    Expected: Phase 0 should BLOCK
    """
    print("\n" + "=" * 80)
    print("TEST CASE 3: VP-99999 - Vague Network Error")
    print("=" * 80)

    ticket = create_test_ticket(
        "VP-99999",
        "API network error",
        """Getting "Failed to fetch" error when calling the API endpoint.
Need to investigate and fix."""
    )

    print(f"\n📞 Ticket: {ticket.key}")
    print(f"📝 Summary: {ticket.summary}")
    print(f"📄 Description: {ticket.description}")

    executor = MarkdownExecutor()

    from src.skills.loader import get_skill_loader
    loader = get_skill_loader()

    skill = Mock()
    skill.get_section = Mock(return_value="")
    skill.content = ""

    phase_0_result = executor._phase_0_pre_analysis(
        ticket, skill, "", "", None
    )

    if not phase_0_result.get("can_proceed"):
        print("\n🚨 PHASE 0 BLOCKER DETECTED!")
        print("\n" + phase_0_result.get("message", ""))

        questions = phase_0_result.get("questions", [])
        if questions:
            print("\n📋 Clarifying Questions:")
            for i, q in enumerate(questions, 1):
                print(f"   {i}. {q}")

        print("\n✅ AGENT BEHAVIOR: CORRECT!")
        return True
    else:
        print("\n❌ AGENT BEHAVIOR: INCORRECT!")
        return False


def main():
    """Run all agent workflow tests."""
    print("\n" + "=" * 80)
    print("AGENT WORKFLOW TESTS WITH PHASE 0")
    print("Testing complete agent behavior from ticket to execution decision")
    print("=" * 80)

    results = {
        "VP-16009 (CORS)": test_agent_workflow_vague_cors(),
        "VP-15874 (EMR)": test_agent_workflow_complete_emr(),
        "VP-99999 (Network)": test_agent_workflow_network_error(),
    }

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(results.values())

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 SUCCESS! Agent now has critical thinking capabilities!")
        print("\nKey Improvements:")
        print("  1. ✅ Detects vague problem statements")
        print("  2. ✅ Blocks execution before making incorrect changes")
        print("  3. ✅ Asks specific clarifying questions")
        print("  4. ✅ Suggests verification commands")
        print("  5. ✅ Proceeds when information is complete")
        print("\nThis prevents VP-16009 type issues from recurring.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - review needed")


if __name__ == "__main__":
    main()
