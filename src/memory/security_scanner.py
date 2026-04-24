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
- Some patterns carry an optional validator() callable that gets a final
  say: if the validator returns False the match is treated as a false
  positive and skipped. This keeps the regex-driven fast path while letting
  heuristic post-filters (e.g. password placeholder whitelist) live in
  Python.
- The scanner is dependency-free (stdlib `re` + `logging`) so it can be
  invoked from any layer of the codebase, including unit tests, without
  pulling in `anthropic` etc.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

logger = logging.getLogger("memory.security_scanner")


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

CATEGORY_PROMPT_INJECTION = "prompt_injection"
CATEGORY_CREDENTIAL_LEAK = "credential_leak"
CATEGORY_EXFILTRATION = "exfiltration"


# ---------------------------------------------------------------------------
# Password placeholder whitelist + validator
# ---------------------------------------------------------------------------

# Values that are OBVIOUS placeholders in docs/examples and should NOT
# trigger a credential_leak violation, even if the regex pattern matches.
_PASSWORD_WHITELIST = frozenset({
    "example", "password", "changeme", "redacted", "placeholder",
    "yourpassword", "yourpasswordhere", "mypassword", "mypasswordhere",
    "test1234567890", "demo12345678", "secret12345",
})


def _is_suspicious_password_value(m: "re.Match[str]") -> bool:
    """Return True if the captured password value looks like a real secret.

    The credential_leak password pattern captures the value in group(2).
    This post-filter rejects common placeholder patterns that produce
    false positives in documentation and example config.
    """
    value = m.group(2) if (m.lastindex or 0) >= 2 else m.group(0)
    low = value.lower()

    # Explicit placeholder list.
    if low in _PASSWORD_WHITELIST:
        return False
    # All lowercase letters -> almost certainly a doc/example word.
    if value.isalpha() and value.islower():
        return False
    # Redaction style (xxxxxx, ******, ...).
    if re.fullmatch(r"[x*.\-_]+", value, re.IGNORECASE):
        return False
    # Template-variable syntax: ${FOO}, {{bar}}, $(baz), <password>.
    if re.search(r"[\$\{\}<>]", value):
        return False
    return True


# ---------------------------------------------------------------------------
# Patterns
#
# Each pattern is either a raw regex string (no validator) or a 2-tuple
# `(pattern, validator)` where validator is called with the regex Match and
# returns True to keep the match, False to treat it as a false positive.
# ---------------------------------------------------------------------------

PatternSpec = object  # actually str | tuple[str, Callable[[re.Match], bool]]


_PROMPT_INJECTION_PATTERNS: list = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|commands?|rules?)",
    r"you\s+are\s+now\s+",
    r"new\s+instructions?\s*[:：]",
    r"system\s+prompt\s*[:：]",
    r"forget\s+(all|everything|your)",
    r"disregard\s+(all\s+)?(previous|above)",
    r"act\s+as\s+(if\s+you\s+are\s+)?",
    r"jailbreak",
]


_CREDENTIAL_LEAK_PATTERNS: list = [
    # generic api key / secret key assignments
    r"(api[_\-\s]?key|apikey|secret[_\-\s]?key)\s*[:=]\s*[\"']?[A-Za-z0-9+/=_\-]{16,}",
    # password / passwd / pwd assignments (post-filtered by validator below)
    (
        r"(password|passwd|pwd)\s*[:=]\s*[\"']?([^\s\"'`<>{}]{12,})",
        _is_suspicious_password_value,
    ),
    # bearer tokens
    r"Bearer\s+[A-Za-z0-9_\-\.=]{20,}",
    # PEM private keys (RSA/DSA/EC/OPENSSH/PGP/plain)
    r"-----BEGIN\s+(RSA\s+|DSA\s+|EC\s+|OPENSSH\s+|PGP\s+)?PRIVATE\s+KEY-----",
    # AWS access key id
    r"AKIA[0-9A-Z]{16}",
    # GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_)
    r"gh[pousr]_[A-Za-z0-9]{36}",
]


# Exfiltration patterns below are stricter than a naive `curl.*memory` match:
# - They require both an HTTP(S) URL AND a data-sending flag.
# - localhost / 127.x / 0.0.0.0 URLs are explicitly excluded (dev examples).
# - `[^\n|]` stops a match from jumping across a pipe into an unrelated
#   command, so `curl --help | grep memory` no longer triggers.
_EXFILTRATION_PATTERNS: list = [
    # base64 encode/decode targeting memory or secrets
    r"base64.*?(encode|decode).*?(memory|long-term|secret|credential)",
    # curl: URL appears BEFORE the data flag
    r"curl\s+(?:[^\n|]*?\s)?https?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[^\s|]+[^\n|]*?(?:-d|--data(?:-raw|-urlencode|-binary)?|-X\s+POST)\b",
    # curl: data flag appears BEFORE the URL
    r"curl\s+(?:[^\n|]*?\s)?(?:-d|--data(?:-raw|-urlencode|-binary)?|-X\s+POST)\s+[^\n|]*?\bhttps?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[^\s|]+",
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
    compiled: "re.Pattern[str]"
    validator: Optional[Callable[["re.Match[str]"], bool]] = None


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def _compile(patterns: Iterable, category: str) -> list:
    """Compile a mixed list of `str` or `(str, validator)` specs."""
    out: list = []
    for spec in patterns:
        if isinstance(spec, tuple):
            raw, validator = spec
        else:
            raw, validator = spec, None
        out.append(
            _CompiledPattern(
                category=category,
                raw=raw,
                compiled=re.compile(raw, re.IGNORECASE | re.DOTALL),
                validator=validator,
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
        self._patterns: list = (
            _compile(_PROMPT_INJECTION_PATTERNS, CATEGORY_PROMPT_INJECTION)
            + _compile(_CREDENTIAL_LEAK_PATTERNS, CATEGORY_CREDENTIAL_LEAK)
            + _compile(_EXFILTRATION_PATTERNS, CATEGORY_EXFILTRATION)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, content: str, context: str = "") -> None:
        """Scan content; raise SecurityViolation on first real match.

        Matches that fail their validator (e.g. placeholder passwords) are
        treated as false positives and skipped silently.

        Args:
            content: text to scan.
            context: short label for logging.
        """
        if not content:
            return

        for cp in self._patterns:
            for m in cp.compiled.finditer(content):
                if cp.validator is not None and not cp.validator(m):
                    continue  # false positive, keep scanning

                excerpt = self._make_excerpt(content, m.start(), m.end())
                self._log_violation(cp.category, cp.raw, excerpt, context)
                raise SecurityViolation(
                    category=cp.category,
                    pattern=cp.raw,
                    excerpt=excerpt,
                )

    def scan_safe(
        self, content: str, context: str = ""
    ) -> "tuple[bool, list[dict[str, str]]]":
        """Scan content without raising.

        Returns:
            (is_safe, violations) where violations is a list of dicts with
            keys "category", "pattern", "excerpt". Empty list when safe.

            Unlike `scan()`, this method collects ALL matches (that survive
            their validators) across all patterns instead of stopping at
            the first one, so callers can see the full picture before
            deciding what to do.
        """
        if not content:
            return True, []

        violations: list = []
        for cp in self._patterns:
            for m in cp.compiled.finditer(content):
                if cp.validator is not None and not cp.validator(m):
                    continue
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

_scanner: Optional[SecurityScanner] = None


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
) -> "tuple[bool, list[dict[str, str]]]":
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
