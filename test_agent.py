#!/usr/bin/env python3
"""
Test script to verify the agent core functionality.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agent.loop import AgentLoop
from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


async def test_agent():
    """Test the agent with simple messages."""
    print("=" * 60)
    print("LIS Code Agent - Core Functionality Test")
    print("=" * 60)

    # Show config
    settings = get_settings()
    print(f"\nConfiguration:")
    print(f"  Agent Root: {settings.agent_root}")
    print(f"  Repos Path: {settings.repos_base_path}")
    print(f"  Storage: {settings.storage_path}")
    print(f"  Memory Files:")
    print(f"    SOUL.md: {settings.soul_path.exists()}")
    print(f"    IDENTITY.md: {settings.identity_path.exists()}")
    print(f"    USER.md: {settings.user_path.exists()}")
    print(f"    MEMORY.md: {settings.memory_path.exists()}")

    # Initialize agent
    print("\nInitializing agent...")
    agent = AgentLoop(session_id="test_session")

    # Test 1: Simple conversation
    print("\n" + "-" * 60)
    print("Test 1: Simple conversation")
    print("-" * 60)

    response = await agent.process_message("你好，我是 Leo")
    print(f"Response: {response['response'][:100]}...")
    print(f"Intent: {response['intent']}")

    # Test 2: Jira question
    print("\n" + "-" * 60)
    print("Test 2: Jira question")
    print("-" * 60)

    response = await agent.process_message("幫我掃描一下有哪些新的 Jira tickets")
    print(f"Response: {response['response'][:200]}...")
    print(f"Intent: {response['intent']}")

    # Test 3: Memory question
    print("\n" + "-" * 60)
    print("Test 3: Memory question")
    print("-" * 60)

    response = await agent.process_message("我的工作是什麼？")
    print(f"Response: {response['response'][:200]}...")
    print(f"Intent: {response['intent']}")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_agent())
