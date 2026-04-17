"""
Permission system for tool execution.

Provides configurable allow/deny rules loaded from a JSON config file,
with hardcoded safety defaults that cannot be overridden.

Design:
- Hardcoded deny rules are ALWAYS enforced (safety net)
- Config file rules are additive on top of defaults
- Deny rules take priority over allow rules
- If no rule matches, the action is allowed (default-allow)
- Pattern matching uses re.search against the relevant input field
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class PermissionRule:
    """A single permission rule."""

    tool: str           # tool name or "*" for all tools
    action: str         # "allow" or "deny"
    pattern: str        # regex pattern to match against tool input
    reason: str = ""    # human-readable explanation
    _is_default: bool = field(default=False, repr=False)  # True = hardcoded, cannot be removed

    def __post_init__(self) -> None:
        if self.action not in ("allow", "deny"):
            raise ValueError(f"Invalid action '{self.action}': must be 'allow' or 'deny'")
        # Validate regex at construction time
        try:
            re.compile(self.pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{self.pattern}': {e}")

    def matches_tool(self, tool_name: str) -> bool:
        """Check if this rule applies to the given tool."""
        return self.tool == "*" or self.tool == tool_name

    def matches_input(self, text: str) -> bool:
        """Check if the pattern matches the input text."""
        return bool(re.search(self.pattern, text))

    def to_dict(self) -> dict[str, str]:
        """Serialize to dict (for JSON export), excluding internal fields."""
        d: dict[str, str] = {
            "tool": self.tool,
            "action": self.action,
            "pattern": self.pattern,
        }
        if self.reason:
            d["reason"] = self.reason
        return d


# ---------------------------------------------------------------------------
# Input extraction helpers
# ---------------------------------------------------------------------------

def _extract_match_text(tool_name: str, input_data: dict[str, Any]) -> str:
    """
    Extract the text to match against from a tool's input_data.

    - run_bash:        the command string
    - read_file/edit_file/write_file/search_files: the file path
    - grep:            the search path (or pattern if no path)
    - git_*:           repo name + branch name (if present) + args (if present)
    - *:               JSON dump of entire input_data as fallback
    """
    if tool_name == "run_bash":
        return input_data.get("command", "")

    if tool_name in ("read_file", "edit_file", "write_file", "search_files"):
        return input_data.get("path", "")

    if tool_name == "grep":
        # Match against both path and pattern so rules can block either
        parts = []
        if input_data.get("path"):
            parts.append(input_data["path"])
        if input_data.get("pattern"):
            parts.append(input_data["pattern"])
        return " ".join(parts)

    if tool_name.startswith("git_"):
        parts = []
        if input_data.get("repo"):
            parts.append(input_data["repo"])
        if input_data.get("branch_name"):
            parts.append(input_data["branch_name"])
        if input_data.get("args"):
            parts.append(input_data["args"])
        if input_data.get("message"):
            parts.append(input_data["message"])
        return " ".join(parts)

    # Fallback: serialise entire input for pattern matching
    return json.dumps(input_data, default=str)


# ---------------------------------------------------------------------------
# PermissionManager
# ---------------------------------------------------------------------------

class PermissionManager:
    """
    Manages permission rules and checks tool calls against them.

    Usage::

        pm = PermissionManager()                           # defaults only
        pm = PermissionManager(Path("permissions.json"))   # defaults + config

        allowed, reason = pm.check("run_bash", {"command": "rm -rf /"})
        # allowed=False, reason="Blocked: destructive filesystem command"
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Load permission rules.

        Args:
            config_path: Optional path to a JSON config file with extra rules.
        """
        self.rules: list[PermissionRule] = []
        self._load_defaults()
        if config_path and config_path.exists():
            self._load_from_file(config_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, tool_name: str, input_data: dict[str, Any]) -> tuple[bool, str]:
        """
        Check if a tool call is permitted.

        Returns:
            (allowed, reason) -- ``allowed`` is True if the call may proceed.
            ``reason`` explains why it was denied (empty string when allowed).

        Evaluation order:
        1. All **deny** rules are checked first.  If any deny rule matches,
           the call is denied immediately (deny wins).
        2. All **allow** rules are checked next.  If an allow rule matches,
           the call is explicitly permitted.
        3. If no rule matches at all, the call is **allowed** (default-allow).
        """
        text = _extract_match_text(tool_name, input_data)

        # --- Phase 1: deny rules (checked first, deny wins) ---
        for rule in self.rules:
            if rule.action != "deny":
                continue
            if rule.matches_tool(tool_name) and rule.matches_input(text):
                reason = rule.reason or f"Denied by rule: {rule.pattern}"
                return False, reason

        # --- Phase 2: allow rules ---
        for rule in self.rules:
            if rule.action != "allow":
                continue
            if rule.matches_tool(tool_name) and rule.matches_input(text):
                return True, rule.reason or "Allowed by rule"

        # --- Phase 3: default-allow ---
        return True, ""

    def add_rule(self, rule: PermissionRule) -> None:
        """Add a rule at runtime (appended after existing rules)."""
        self.rules.append(rule)

    def get_rules(self, include_defaults: bool = True) -> list[PermissionRule]:
        """Return a copy of the current rule list."""
        if include_defaults:
            return list(self.rules)
        return [r for r in self.rules if not r._is_default]

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_defaults(self) -> None:
        """
        Load hardcoded safety defaults.

        These rules are always present and cannot be removed by config.
        They cover the most dangerous operations that should never be
        executed by an automated agent.
        """
        defaults = [
            # ── Bash: destructive filesystem commands ──
            PermissionRule(
                tool="run_bash",
                action="deny",
                pattern=r"rm\s+-rf\s+/(?!\S)",
                reason="Blocked: destructive filesystem command (rm -rf /)",
                _is_default=True,
            ),
            PermissionRule(
                tool="run_bash",
                action="deny",
                pattern=r"rm\s+-rf\s+~",
                reason="Blocked: destructive filesystem command (rm -rf ~)",
                _is_default=True,
            ),
            PermissionRule(
                tool="run_bash",
                action="deny",
                pattern=r"mkfs\.",
                reason="Blocked: filesystem format command",
                _is_default=True,
            ),
            PermissionRule(
                tool="run_bash",
                action="deny",
                pattern=r">\s*/dev/sd",
                reason="Blocked: writing to raw block device",
                _is_default=True,
            ),

            # ── Git: force push ──
            PermissionRule(
                tool="run_bash",
                action="deny",
                pattern=r"git\s+push\s+.*--force",
                reason="Blocked: force push is not allowed",
                _is_default=True,
            ),
            PermissionRule(
                tool="run_bash",
                action="deny",
                pattern=r"git\s+push\s+-f\b",
                reason="Blocked: force push (-f) is not allowed",
                _is_default=True,
            ),

            # ── Git: reset --hard ──
            PermissionRule(
                tool="run_bash",
                action="deny",
                pattern=r"git\s+reset\s+--hard",
                reason="Blocked: hard reset is not allowed",
                _is_default=True,
            ),

            # ── Git: push to protected branches ──
            PermissionRule(
                tool="run_bash",
                action="deny",
                pattern=r"git\s+push\s+\S+\s+(main|master)\b",
                reason="Blocked: push to protected branch (main/master)",
                _is_default=True,
            ),

            # ── Git tools: force push via args ──
            PermissionRule(
                tool="git_push",
                action="deny",
                pattern=r"--force|-f\b",
                reason="Blocked: force push is not allowed",
                _is_default=True,
            ),
        ]

        self.rules.extend(defaults)

    def _load_from_file(self, path: Path) -> None:
        """
        Load additional rules from a JSON config file.

        Expected format::

            {
                "rules": [
                    {"tool": "run_bash", "action": "deny", "pattern": "...", "reason": "..."},
                    ...
                ]
            }

        Rules loaded from file are appended *after* the hardcoded defaults,
        so default deny rules are always evaluated first.
        """
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"Failed to load permissions config from {path}: {e}")

        if not isinstance(data, dict) or "rules" not in data:
            raise ValueError(
                f"Invalid permissions config: expected a JSON object with a 'rules' key, got: {path}"
            )

        for entry in data["rules"]:
            if not isinstance(entry, dict):
                continue
            try:
                rule = PermissionRule(
                    tool=entry.get("tool", "*"),
                    action=entry["action"],
                    pattern=entry["pattern"],
                    reason=entry.get("reason", ""),
                    _is_default=False,
                )
                self.rules.append(rule)
            except (KeyError, ValueError) as e:
                # Skip malformed rules but warn
                import logging
                logging.getLogger(__name__).warning(
                    "Skipping invalid permission rule %r: %s", entry, e
                )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def export_rules(self, include_defaults: bool = False) -> dict[str, Any]:
        """Export rules as a dict suitable for JSON serialization."""
        rules = self.get_rules(include_defaults=include_defaults)
        return {"rules": [r.to_dict() for r in rules]}

    def __repr__(self) -> str:
        n_default = sum(1 for r in self.rules if r._is_default)
        n_custom = len(self.rules) - n_default
        return f"PermissionManager(defaults={n_default}, custom={n_custom})"
