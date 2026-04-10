#!/usr/bin/env python3
"""
Process VP-15980 using the AI Agent with Phase 0 Pre-Analysis
"""

import sys
sys.path.insert(0, "/Users/hung.l/src/lis-code-agent")

from src.core.markdown_executor import MarkdownExecutor
from src.integrations.jira import JiraClient
from unittest.mock import Mock


def main():
    print("\n" + "=" * 80)
    print("PROCESSING TICKET: VP-15980")
    print("=" * 80)

    # Fetch the ticket
    client = JiraClient()
    ticket = client.get_ticket("VP-15980")

    print(f"\n📞 Ticket: {ticket.key}")
    print(f"📝 Summary: {ticket.summary}")
    print(f"📄 Description: {ticket.description}")
    print(f"📊 Status: {ticket.status}")
    print(f"🔑 Type: {ticket.issue_type}")

    # Initialize executor
    executor = MarkdownExecutor()

    from src.skills.loader import get_skill_loader
    loader = get_skill_loader()

    skill = loader.get_skill("emr-integration")
    soul = loader.get_soul_md()
    tools = loader.get_tools_md()
    agents = loader.get_agents_md()
    phase_0_doc = loader.get_skill("debugging")

    # ============================================================
    # PHASE 0: Pre-Analysis
    # ============================================================
    print("\n" + "=" * 80)
    print("🔍 PHASE 0: Pre-Analysis")
    print("=" * 80)

    phase_0_result = executor._phase_0_pre_analysis(
        ticket, skill, soul, tools, phase_0_doc
    )

    if not phase_0_result.get("can_proceed"):
        print("\n🚨 PHASE 0 BLOCKER!")
        print("\n" + phase_0_result.get("message", ""))
        questions = phase_0_result.get("questions", [])
        if questions:
            print("\n📋 Clarifying Questions:")
            for i, q in enumerate(questions, 1):
                print(f"   {i}. {q}")
        return 1

    print("\n✅ Phase 0 PASSED")
    print(f"   {phase_0_result.get('message', '')}")

    # ============================================================
    # LLM Analysis
    # ============================================================
    print("\n" + "=" * 80)
    print("🧠 STEP 1: LLM Analysis & Reasoning")
    print("=" * 80)

    analysis = executor._llm_analyze_with_skill(
        ticket, skill, soul, tools, agents, phase_0_result
    )

    if not analysis.get("success"):
        print(f"\n❌ LLM Analysis failed: {analysis.get('error')}")
        return 1

    plan = analysis.get("plan", {})

    print(f"\n📝 Reasoning:")
    print(f"   {plan.get('reasoning', '')}")

    extracted = plan.get('extracted_data', {})
    print(f"\n📋 Extracted Data:")
    for key, value in extracted.items():
        print(f"   {key}: {value}")

    missing = plan.get('missing_data', [])
    if missing:
        print(f"\n❓ Missing Data (will fetch):")
        for item in missing:
            print(f"   - {item}")

    actions = plan.get('actions', [])
    print(f"\n📋 Planned Actions:")
    for action in actions:
        step = action.get('step')
        act = action.get('action')
        tool = action.get('tool')
        print(f"   {step}. {act} (tool: {tool})")

    # ============================================================
    # Execute Plan
    # ============================================================
    print("\n" + "=" * 80)
    print("⚙️  STEP 2: Executing Plan")
    print("=" * 80)

    result = executor._execute_plan(ticket, analysis, phase_0_result)

    if result.get("success"):
        print("\n✅ Execution completed successfully!")
        print("\n" + result.get("output", ""))
    else:
        print(f"\n❌ Execution failed: {result.get('error')}")
        return 1

    print("\n" + "=" * 80)
    print("✅ VP-15980 COMPLETED")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
