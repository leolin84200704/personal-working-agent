"""
Authentication - Resolve Claude API credentials.

Priority:
1. macOS Keychain (Claude Code /login session) — no API key needed
2. ANTHROPIC_API_KEY environment variable — fallback
"""
from __future__ import annotations

import json
import subprocess
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger("auth")

KEYCHAIN_SERVICE = "Claude Code-credentials"


def get_oauth_token() -> Optional[str]:
    """Extract the OAuth access token from macOS Keychain.

    Returns the token string, or None if not available.
    """
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout.strip())
        token = data.get("claudeAiOauth", {}).get("accessToken")
        if token:
            logger.info("Using OAuth token from Claude Code /login session")
        return token

    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.debug("Could not read keychain: %s", e)
        return None


def resolve_api_key(configured_key: Optional[str] = None) -> str:
    """Resolve the best available API key.

    1. Try macOS Keychain (Claude Code /login)
    2. Fall back to configured API key
    3. Raise if neither is available
    """
    token = get_oauth_token()
    if token:
        return token

    if configured_key:
        logger.info("Using ANTHROPIC_API_KEY from environment")
        return configured_key

    raise RuntimeError(
        "No Claude credentials found. Either run `claude /login` or set ANTHROPIC_API_KEY."
    )
