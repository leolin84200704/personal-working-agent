#!/usr/bin/env python3
"""
Test configuration and connections.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add parent directory and src to path for proper imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from dotenv import load_dotenv

from src.integrations.jira import JiraClient
from src.core.ticket_processor import TicketProcessor
from src.integrations.git_operator import find_git_repos
from src.memory.manager import MemoryManager

load_dotenv()

def test_env_vars():
    """Test environment variables are set."""
    print("=" * 60)
    print("Testing Environment Variables")
    print("=" * 60)

    required_vars = [
        "ANTHROPIC_API_KEY",
        "JIRA_SERVER",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "REPOS_BASE_PATH",
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if "API_KEY" in var or "TOKEN" in var:
                print(f"✓ {var}: {'*' * 20}...{value[-10:]}")
            else:
                print(f"✓ {var}: {value}")
        else:
            print(f"✗ {var}: NOT SET")
            missing.append(var)

    # Check optional vars
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    if base_url:
        print(f"✓ ANTHROPIC_BASE_URL: {base_url}")

    if missing:
        print(f"\n❌ Missing required variables: {', '.join(missing)}")
        return False

    print("\n✅ All required environment variables are set")
    return True


def test_jira_connection():
    """Test Jira API connection."""
    print("\n" + "=" * 60)
    print("Testing Jira Connection")
    print("=" * 60)

    try:
        client = JiraClient()
        print(f"✓ JiraClient initialized")

        # Try to get projects
        projects = client.get_projects()
        print(f"✓ Found {len(projects)} projects")

        # Show first few projects
        for project in projects[:5]:
            print(f"  - {project['key']}: {project['name']}")

        print("\n✅ Jira connection successful")
        return True

    except Exception as e:
        print(f"\n❌ Jira connection failed: {e}")
        return False


def test_claude_connection():
    """Test Claude API connection."""
    print("\n" + "=" * 60)
    print("Testing Claude API Connection")
    print("=" * 60)

    try:
        processor = TicketProcessor(dry_run=True)
        print(f"✓ TicketProcessor initialized")

        # Simple test call
        response = processor.claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'Hello from Claude!'"}]
        )

        content = response.content[0].text
        print(f"✓ Claude response: {content}")

        print("\n✅ Claude API connection successful")
        return True

    except Exception as e:
        print(f"\n❌ Claude API connection failed: {e}")
        return False


def test_repo_discovery():
    """Test repository discovery."""
    print("\n" + "=" * 60)
    print("Testing Repository Discovery")
    print("=" * 60)

    try:
        repos = find_git_repos(Path(os.getenv("REPOS_BASE_PATH", "/Users/hung.l/src")))
        print(f"✓ Found {len(repos)} repositories")

        for repo in repos:
            print(f"  - {repo.name}")

        print("\n✅ Repository discovery successful")
        return True

    except Exception as e:
        print(f"\n❌ Repository discovery failed: {e}")
        return False


def test_memory_system():
    """Test memory system."""
    print("\n" + "=" * 60)
    print("Testing Memory System")
    print("=" * 60)

    try:
        memory = MemoryManager()

        # Test reading
        soul = memory.read_soul()
        print(f"✓ SOUL.md: {len(soul)} characters")

        identity = memory.read_identity()
        print(f"✓ IDENTITY.md: {len(identity)} characters")

        user = memory.read_user()
        print(f"✓ USER.md: {len(user)} characters")

        mem = memory.read_memory()
        print(f"✓ MEMORY.md: {len(mem)} characters")

        # Test getting branch prefixes
        prefixes = memory.get_branch_prefixes()
        print(f"✓ Branch prefixes: {prefixes}")

        # Test getting repo info
        repos = memory.get_repo_info()
        print(f"✓ Repo info: {len(repos)} repos documented")

        print("\n✅ Memory system successful")
        return True

    except Exception as e:
        print(f"\n❌ Memory system failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n🔧 LIS Code Agent - Configuration Test\n")

    results = {
        "Environment Variables": test_env_vars(),
        "Jira Connection": test_jira_connection(),
        "Claude API": test_claude_connection(),
        "Repository Discovery": test_repo_discovery(),
        "Memory System": test_memory_system(),
    }

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 All tests passed! The agent is ready to use.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Please check the configuration.")
        return 1


if __name__ == "__main__":
    from pathlib import Path
    sys.exit(main())
