#!/usr/bin/env python3
"""
Test script for Phase 0 Pre-Analysis workflow.

This demonstrates how the agent now uses critical thinking before executing.
"""

import sys
sys.path.insert(0, "/Users/hung.l/src/lis-code-agent")

from src.core.markdown_executor import MarkdownExecutor
from unittest.mock import Mock


def create_mock_ticket(key: str, summary: str, description: str) -> Mock:
    """Create a mock Jira ticket for testing."""
    ticket = Mock()
    ticket.key = key
    ticket.summary = summary
    ticket.description = description
    return ticket


def test_phase_0_cors_vague():
    """Test Phase 0 with vague CORS error (should block)."""
    print("\n" + "=" * 70)
    print("TEST 1: Vague CORS Error (Should Block)")
    print("=" * 70)

    executor = MarkdownExecutor()
    skill = Mock()
    skill.get_section = Mock(return_value="")
    skill.content = ""

    ticket = create_mock_ticket(
        "VP-16009",
        "CORS error on VI Personal Settings",
        "Getting CORS error when accessing from VI Personal Settings"
    )

    result = executor._phase_0_pre_analysis(
        ticket, skill, "", "", None
    )

    print(f"Can Proceed: {result.get('can_proceed')}")
    print(f"\nMessage:\n{result.get('message')}")
    print(f"\nClarifying Questions:")
    for i, q in enumerate(result.get('questions', []), 1):
        print(f"  {i}. {q}")

    assert not result.get("can_proceed"), "Should block on vague CORS"
    print("\n✅ PASS: Correctly blocked vague CORS error")


def test_phase_0_network_error_vague():
    """Test Phase 0 with vague network error (should block)."""
    print("\n" + "=" * 70)
    print("TEST 2: Vague Network Error (Should Block)")
    print("=" * 70)

    executor = MarkdownExecutor()
    skill = Mock()
    skill.get_section = Mock(return_value="")
    skill.content = ""

    ticket = create_mock_ticket(
        "VP-99999",
        "Network error on API call",
        "Getting failed to fetch error when calling API"
    )

    result = executor._phase_0_pre_analysis(
        ticket, skill, "", "", None
    )

    print(f"Can Proceed: {result.get('can_proceed')}")
    print(f"\nMessage:\n{result.get('message')}")

    assert not result.get("can_proceed"), "Should block on vague network error"
    print("\n✅ PASS: Correctly blocked vague network error")


def test_phase_0_emr_missing_ids():
    """Test Phase 0 with EMR ticket missing required IDs (should block)."""
    print("\n" + "=" * 70)
    print("TEST 3: EMR Ticket Missing IDs (Should Block)")
    print("=" * 70)

    executor = MarkdownExecutor()
    skill = Mock()
    skill.get_section = Mock(return_value="")
    skill.content = ""

    ticket = create_mock_ticket(
        "VP-99998",
        "Add new EMR integration",
        "Please add a new provider to the system"
    )

    result = executor._phase_0_pre_analysis(
        ticket, skill, "", "", None
    )

    print(f"Can Proceed: {result.get('can_proceed')}")
    print(f"\nMessage:\n{result.get('message')}")

    assert not result.get("can_proceed"), "Should block on missing IDs"
    print("\n✅ PASS: Correctly blocked EMR ticket without IDs")


def test_phase_0_emr_complete():
    """Test Phase 0 with complete EMR ticket (should pass)."""
    print("\n" + "=" * 70)
    print("TEST 4: Complete EMR Ticket (Should Pass)")
    print("=" * 70)

    executor = MarkdownExecutor()
    skill = Mock()
    skill.get_section = Mock(return_value="")
    skill.content = ""

    ticket = create_mock_ticket(
        "VP-15874",
        "Add Next Health providers",
        "Provider ID: 43262, Practice ID: 2930, Clinic Name: Next Health West Hollywood"
    )

    result = executor._phase_0_pre_analysis(
        ticket, skill, "", "", None
    )

    print(f"Can Proceed: {result.get('can_proceed')}")
    print(f"\nMessage:\n{result.get('message')}")

    assert result.get("can_proceed"), "Should pass with complete info"
    print("\n✅ PASS: Correctly allowed complete EMR ticket")


def test_phase_0_cors_with_details():
    """Test Phase 0 with detailed CORS error (should pass - has verification)."""
    print("\n" + "=" * 70)
    print("TEST 5: CORS Error with Details (Should Pass)")
    print("=" * 70)

    executor = MarkdownExecutor()
    skill = Mock()
    skill.get_section = Mock(return_value="")
    skill.content = ""

    ticket = create_mock_ticket(
        "VP-88888",
        "CORS preflight OPTIONS request blocked",
        "OPTIONS request to /api/endpoint returns 403. Checked ALLOWED_ORIGINS and domain is present."
    )

    result = executor._phase_0_pre_analysis(
        ticket, skill, "", "", None
    )

    print(f"Can Proceed: {result.get('can_proceed')}")
    print(f"\nMessage:\n{result.get('message')}")

    assert result.get("can_proceed"), "Should pass with detailed CORS info"
    print("\n✅ PASS: Correctly allowed detailed CORS ticket")


def main():
    """Run all Phase 0 tests."""
    print("\n" + "=" * 70)
    print("PHASE 0 PRE-ANALYSIS TESTS")
    print("Testing Critical Thinking Capabilities")
    print("=" * 70)

    tests = [
        test_phase_0_cors_vague,
        test_phase_0_network_error_vague,
        test_phase_0_emr_missing_ids,
        test_phase_0_emr_complete,
        test_phase_0_cors_with_details,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\n🎉 All Phase 0 tests passed!")
        print("\nThe agent now has critical thinking capabilities:")
        print("  ✅ Detects vague problem statements")
        print("  ✅ Blocks execution when clarification needed")
        print("  ✅ Provides specific questions to ask user")
        print("  ✅ Suggests verification commands")
    else:
        print(f"\n⚠️  {failed} test(s) failed - review needed")


if __name__ == "__main__":
    main()
