"""
Context Compaction - Summarize old messages instead of dropping them.

When conversation history exceeds a threshold, the oldest messages are
summarized into a single message using a fast/cheap model, preserving
key decisions and context while reducing token count.
"""
from __future__ import annotations

from anthropic import Anthropic

from src.agent.state import ConversationContext, Message
from src.utils.logger import get_logger

logger = get_logger()

from src.config import get_settings as _get_settings

SUMMARY_SYSTEM_PROMPT = (
    "Summarize this conversation concisely in Traditional Chinese. "
    "Keep key decisions, findings, and context. Be brief."
)


def build_summary_prompt(messages: list[Message]) -> str:
    """Format messages into a prompt for summarization."""
    lines = []
    for msg in messages:
        role_label = "User" if msg.role == "user" else "Assistant"
        lines.append(f"[{role_label}]: {msg.content}")
    return "\n\n".join(lines)


class CompactionManager:
    """Manages conversation history compaction via summarization."""

    def __init__(self, claude_client: Anthropic):
        self.claude = claude_client

    def compact_if_needed(
        self,
        context: ConversationContext,
        max_messages: int = 20,
        keep_recent: int = 10,
    ) -> bool:
        """
        If messages exceed max_messages, summarize the oldest ones.

        1. Take the oldest (total - keep_recent) messages
        2. Summarize them using Claude Haiku (fast + cheap)
        3. Replace them with a single summary message
        4. Return True if compaction happened
        """
        total = len(context.messages)
        if total <= max_messages:
            return False

        # Split: old messages to summarize, recent messages to keep
        split_index = total - keep_recent
        old_messages = context.messages[:split_index]
        recent_messages = context.messages[split_index:]

        # Build the summary
        prompt = build_summary_prompt(old_messages)
        try:
            response = self.claude.messages.create(
                model=_get_settings().default_model,
                max_tokens=1024,
                system=SUMMARY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = response.content[0].text
        except Exception as e:
            logger.error(f"Compaction summarization failed: {e}")
            return False

        # Replace conversation history: summary message + recent messages
        summary_message = Message(
            role="user",
            content=f"[Previous conversation summary]\n{summary}",
        )
        context.messages = [summary_message] + recent_messages

        logger.info(
            f"Compacted conversation: {total} messages -> {len(context.messages)} "
            f"(summarized {len(old_messages)} old messages)"
        )
        return True
