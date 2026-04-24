"""
Security Scanner for memory write paths.

Scans content (LLM-extracted learnings, distilled insights, conversation
extracts) before it is persisted to long-term memory files (MEMORY.md,
SOUL.md, IDENTITY.md, USER.md, knowledge/*.md, SKILL.md).

Three threat categories are detected:

1. prompt_injection - attempts to inject new instructions / override the
   agent's system prompt via memory.
2. credential_leak  - API keys, tokens, passwords, private keys that must
   never be persisted to plaintext memory files.
3. exfiltration     - outbound channels (curl/fetch/webhooks/base64 encoded
   secrets) that hint at data-exfiltration tooling being smuggled into
   memory.

Design notes:
- We RAISE on first match (fail-closed) rather than silently strip, so the
  caller always has to make an explicit decision. Silent stripping creates
  a false sense of security and makes auditing harder.
- All patterns are case-insensitive and operate on a normalized copy of the
  content (whitespace collapsed in a few patterns where matters).
- The scanner is dependency-free (stdlib `re` + `logging`) so it can be
  invoked from any layer of the codebase, including unit tests, without
  pulling in `anthropic` etc.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger("memory.security_scanner")


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

CATEGORY_PROMPT_INJECTION = "prompt_injection"
CATEGORY_CREDENTIAL_LEAK = "credential_leak"
CATEGORY_EXFILTRATION = "exfiltration"


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# All patterns are matched with re.IGNORECASE | re.DOTALL by default, except
# where noted. Order within a category matters only for which pattern is
# reported first when multiple match the same span.

_PROMPT_INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|commands?|rules?)",
    r"you\s+are\s+now\s+",
    r"new\s+instructions?\s*[:：]",
    r"system\s+prompt\s*[:：]",
    r"forget\s+(all|everything|your)",
    r"disregard\s+(all\s+)?(previous|above)",
    r"act\s+as\s+(if\s+you\s+are\s+)?",
    r"jailbreak",
]

_CREDENTIAL_LEAK_PATTERNS: list[str] = [
    # generic api key / secret key assignments
    r"(api[_\-\s]?key|apikey|secret[_\-\s]?key)\s*[:=]\s*[\"']?[A-Za-z0-9+/=_\-]{16,}",
    # password / passwd / pwd assignments
    r"(password|passwd|pwd)\s*[:=]\s*[\"']?[^\s\"']{6,}",
    # bearer tokens
    r"Bearer\s+[A-Za-z0-9_\-\.=]{20,}",
    # PEM private keys (RSA/DSA/EC/OPENSSH/PGP/plain)
    r"-----BEGIN\s+(RSA\s+|DSA\s+|EC\s+|OPENSSH\s+|PGP\s+)?PRIVATE\s+KEY-----",
    # AWS access key id
    r"AKIA[0-9A-Z]{16}",
    # GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_)
    r"gh[pousr]_[A-Za-z0-9]{36}",
]

_EXFILTRATION_PATTERNS: list[str] = [
    # base64 encode/decode targeting memory or secrets
    r"base64.*?(encode|decode).*?(memory|long-term|secret|credential)",
    # curl POST exfiltrating memory/secrets/tokens
    r"curl\s+.*?\s+(-d|--data|--data-raw)\s+[\"']?.*?(memory|secret|token)",
    # fetch / axios / requests.post to suspicious destinations
    r"(fetch|axios|requests\.post).*?(webhook|discord|ngrok)",
]


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class SecurityViolation(Exception):
    """Raised when content fails a security scan.

    Attributes:
        category: one of "prompt_injection", "credential_leak",
            "exfiltration".
        pattern: the regex pattern that matched.
        excerpt: a short snippet of the offending content (truncated).
    """

    def __init__(self, category: str, pattern: str, excerpt: str):
        self.category = category
        self.pattern = pattern
        self.excerpt = excerpt
        super().__init__(
            f"SecurityViolation[{category}] pattern={pattern!r} excerpt={excerpt!r}"
        )


@dataclass(frozen=True)
class _CompiledPattern:
    category: str
    raw: str
    compiled: re.Pattern[str]


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def _compile(patterns: Iterable[str], category: str) -> list[_CompiledPattern]:
    out: list[_CompiledPattern] = []
    for p in patterns:
        out.append(
            _CompiledPattern(
                category=category,
                raw=p,
                compiled=re.compile(p, re.IGNORECASE | re.DOTALL),
            )
        )
    return out


class SecurityScanner:
    """Scans content for prompt-injection / credential / exfiltration risks.

    Usage::

        scanner = SecurityScanner()
        try:
            scanner.scan(content, context="ticket:VP-16009")
        except SecurityViolation as e:
            log_and_reject(e)

    Or non-raising::

        is_safe, violations = scanner.scan_safe(content, context="...")
    """

    EXCERPT_LEN: int = 200

    def __init__(self) -> None:
        self._patterns: list[_CompiledPattern] = (
            _compile(_PROMPT_INJECTION_PATTERNS, CATEGORY_PROMPT_INJECTION)
            + _compile(_CREDENTIAL_LEAK_PATTERNS, CATEGORY_CREDENTIAL_LEAK)
            + _compile(_EXFILTRATION_PATTERNS, CATEGORY_EXFILTRATION)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, content: str, context: str = "") -> None:
        """Scan content; raise SecurityViolation on first match.

        Args:
            content: text to scan (memory snippet, distilled insight, etc.)
            context: short label for logging, e.g. "ticket:VP-16009" or
                "auto_update:_update_memory".
        """
        if not content:
            return

        for cp in self._patterns:
            m = cp.compiled.search(content)
            if m is None:
                continue

            excerpt = self._make_excerpt(content, m.start(), m.end())
            self._log_violation(cp.category, cp.raw, excerpt, context)
            raise SecurityViolation(
                category=cp.category,
                pattern=cp.raw,
                excerpt=excerpt,
            )

    def scan_safe(
        self, content: str, context: str = ""
    ) -> tuple[bool, list[dict[str, str]]]:
        """Scan content without raising.

        Returns:
            (is_safe, violations) where violations is a list of dicts with
            keys "category", "pattern", "excerpt". Empty list when safe.

            Unlike `scan()`, this method collects ALL matches across all
            patterns instead of stopping at the first one, so callers can
            see the full picture before deciding what to do.
        """
        if not content:
            return True, []

        violations: list[dict[str, str]] = []
        for cp in self._patterns:
            for m in cp.compiled.finditer(content):
                excerpt = self._make_excerpt(content, m.start(), m.end())
                self._log_violation(cp.category, cp.raw, excerpt, context)
                violations.append(
                    {
                        "category": cp.category,
                        "pattern": cp.raw,
                        "excerpt": excerpt,
                    }
                )

        return (len(violations) == 0), violations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_excerpt(self, content: str, start: int, end: int) -> str:
        """Return a short, single-line excerpt centered on the match."""
        half = self.EXCERPT_LEN // 2
        s = max(0, start - half)
        e = min(len(content), end + half)
        snippet = content[s:e]
        # collapse whitespace so log lines stay single-line
        snippet = re.sub(r"\s+", " ", snippet).strip()
        if len(snippet) > self.EXCERPT_LEN:
            snippet = snippet[: self.EXCERPT_LEN] + "..."
        return snippet

    @staticmethod
    def _log_violation(
        category: str, pattern: str, excerpt: str, context: str
    ) -> None:
        ctx = context or "<no-context>"
        # log format requested by spec:
        # [SECURITY] {category} pattern match in {context}: {excerpt[:80]}...
        truncated = excerpt[:80] + ("..." if len(excerpt) > 80 else "")
        logger.warning(
            "[SECURITY] %s pattern match in %s: %s",
            category,
            ctx,
            truncated,
        )
        logger.debug(
            "[SECURITY] full match details category=%s pattern=%r context=%s",
            category,
            pattern,
            ctx,
        )


# ---------------------------------------------------------------------------
# Module-level singleton + convenience functions
# ---------------------------------------------------------------------------

_scanner: SecurityScanner | None = None


def get_scanner() -> SecurityScanner:
    """Return a process-wide SecurityScanner instance."""
    global _scanner
    if _scanner is None:
        _scanner = SecurityScanner()
    return _scanner


def scan(content: str, context: str = "") -> None:
    """Convenience wrapper around `get_scanner().scan()`."""
    get_scanner().scan(content, context=context)


def scan_safe(
    content: str, context: str = ""
) -> tuple[bool, list[dict[str, str]]]:
    """Convenience wrapper around `get_scanner().scan_safe()`."""
    return get_scanner().scan_safe(content, context=context)


__all__ = [
    "SecurityScanner",
    "SecurityViolation",
    "CATEGORY_PROMPT_INJECTION",
    "CATEGORY_CREDENTIAL_LEAK",
    "CATEGORY_EXFILTRATION",
    "get_scanner",
    "scan",
    "scan_safe",
]
