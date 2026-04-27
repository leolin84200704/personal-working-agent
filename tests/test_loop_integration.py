"""Integration tests for AgentLoop ticket binding + auto session injection.

Covers Items 1 and 2 from the FTS5-evolution change:

Item 1 — Per-ticket session_id
    * ``AgentLoop.set_ticket`` flips ``session_id`` to the ``ticket_<ID>``
      form and propagates the change to ``ConversationContext`` and
      ``SubAgentManager``.
    * Passing ``None`` / empty string falls back to the original timestamp
      session_id captured at ctor time.
    * Auto-detection: when ``process_message`` sees a Jira-style ticket id
      in the user message and we are not yet bound, ``set_ticket`` fires.
    * No ticket id in the message → session_id stays at the default
      timestamp form (no regression on baseline behaviour).

Item 2 — Auto-inject past session turns
    * ``_load_relevant_sessions`` returns ``""`` on an empty index.
    * A round-trip (write turn → query) yields a markdown block whose
      header matches the spec and whose body contains the indexed text.
    * Failures inside ``search_sessions`` are swallowed; the helper never
      raises into the agent loop.
    * The injected block is appended to the system prompt by
      ``_build_system_prompt`` when there are hits, and absent otherwise.

These tests deliberately mock out Anthropic / auth so the suite stays
network-free and matches the rest of the project's unittest harness.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _make_agent_loop(session_id: str | None = None):
    """Construct an ``AgentLoop`` with all external side-effects stubbed.

    The ctor instantiates an ``Anthropic`` client and several managers.
    For these unit tests we only care about the loop's own behaviour
    (set_ticket, _load_relevant_sessions, system prompt assembly), so we
    short-circuit Anthropic and the OAuth resolver.
    """
    with mock.patch("src.agent.loop.Anthropic") as mock_anthropic, \
         mock.patch("src.agent.loop.resolve_api_key", return_value="sk-test"):
        mock_anthropic.return_value = mock.MagicMock()
        from src.agent.loop import AgentLoop  # local import after patches
        return AgentLoop(session_id=session_id)


class _StoragePathPatch:
    """Mirror of the helper used by tests/test_session_index_production.

    Points ``Settings.storage_path`` at a fresh tempdir for the duration
    of the ``with`` block, and resets the SessionIndex singleton so
    ``search_sessions`` rebuilds against the patched path.
    """

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._patches: list = []

    def __enter__(self) -> Path:
        from src.memory.manager import _reset_session_index_for_tests

        _reset_session_index_for_tests()

        from src import config as config_module

        config_module._settings = None
        original_get_settings = config_module.get_settings

        tmp_path = Path(self.tmp.name)

        def _patched_get_settings():
            s = original_get_settings()
            s.storage_path = tmp_path
            return s

        p = mock.patch.object(config_module, "get_settings", _patched_get_settings)
        p.start()
        self._patches.append(p)
        return tmp_path

    def __exit__(self, exc_type, exc, tb) -> None:
        from src.memory.manager import _reset_session_index_for_tests

        for p in self._patches:
            p.stop()
        _reset_session_index_for_tests()
        from src import config as config_module
        config_module._settings = None
        self.tmp.cleanup()


# ──────────────────────────────────────────────────────────────────────
# Item 1: per-ticket session_id
# ──────────────────────────────────────────────────────────────────────


class SetTicketCases(unittest.TestCase):
    """``AgentLoop.set_ticket`` reflects in session_id + context."""

    def test_set_ticket_changes_session_id(self) -> None:
        agent = _make_agent_loop(session_id="session_baseline")
        new_id = agent.set_ticket("VP-16175")
        self.assertEqual(new_id, "ticket_VP-16175")
        self.assertEqual(agent.session_id, "ticket_VP-16175")
        self.assertEqual(agent.context.session_id, "ticket_VP-16175")
        self.assertEqual(agent.current_ticket_id, "VP-16175")

    def test_set_ticket_none_falls_back_to_default(self) -> None:
        agent = _make_agent_loop(session_id="session_default_baseline")
        agent.set_ticket("VP-16175")
        self.assertEqual(agent.session_id, "ticket_VP-16175")

        # Now clear: must restore the original timestamp/default form.
        agent.set_ticket(None)
        self.assertEqual(agent.session_id, "session_default_baseline")
        self.assertEqual(agent.context.session_id, "session_default_baseline")
        self.assertIsNone(agent.current_ticket_id)

    def test_set_ticket_empty_string_falls_back(self) -> None:
        agent = _make_agent_loop(session_id="session_xyz")
        agent.set_ticket("VP-1")
        agent.set_ticket("")
        self.assertEqual(agent.session_id, "session_xyz")
        self.assertIsNone(agent.current_ticket_id)

    def test_set_ticket_propagates_to_sub_agent_manager(self) -> None:
        agent = _make_agent_loop(session_id="session_init")
        agent.set_ticket("HL7-20260427")
        # SubAgentManager keys its sub-agent ids off parent_session_id;
        # keeping it in sync avoids cross-ticket id collisions.
        self.assertEqual(
            agent.sub_agent_manager.parent_session_id,
            "ticket_HL7-20260427",
        )

    def test_default_session_id_is_timestamp_form(self) -> None:
        agent = _make_agent_loop()  # no explicit id
        # Auto-generated default should look like "session_YYYYMMDD_HHMMSS".
        self.assertTrue(agent.session_id.startswith("session_"))
        self.assertIsNone(agent.current_ticket_id)


# ──────────────────────────────────────────────────────────────────────
# Item 1: auto-detection inside process_message
# ──────────────────────────────────────────────────────────────────────


class ProcessMessageTicketAutodetectCases(unittest.TestCase):
    """``process_message`` auto-detects ticket ids in the user message.

    We mock the Anthropic call to return a no-tool text response so the
    loop terminates after one round. We also short-circuit ``_learn`` so
    the tests don't write to the real chroma / session index.
    """

    def _run_message(self, agent, message: str) -> dict:
        # Build a fake response that contains a single text block — this
        # makes the loop return immediately without invoking any tools.
        text_block = mock.MagicMock()
        text_block.type = "text"
        text_block.text = "ok"

        fake_response = mock.MagicMock()
        fake_response.content = [text_block]

        agent.claude.messages.create = mock.MagicMock(return_value=fake_response)
        # Skip side-effects of _learn (chroma writes, FTS5 writes, scoring).
        agent._learn = mock.MagicMock()
        # Avoid heavy retrieval during _build_system_prompt.
        agent._ensure_knowledge_indexed = mock.MagicMock()
        agent._load_relevant_sessions = mock.MagicMock(return_value="")

        return asyncio.run(agent.process_message(message))

    def test_ticket_id_in_message_triggers_set_ticket(self) -> None:
        agent = _make_agent_loop(session_id="session_init")
        result = self._run_message(agent, "請看一下 VP-16175 這個 ticket")
        self.assertEqual(result["response"], "ok")
        self.assertEqual(agent.session_id, "ticket_VP-16175")
        self.assertEqual(agent.current_ticket_id, "VP-16175")

    def test_no_ticket_id_keeps_default_session(self) -> None:
        agent = _make_agent_loop(session_id="session_init_xyz")
        self._run_message(agent, "幫我看一下這份 code")
        self.assertEqual(agent.session_id, "session_init_xyz")
        self.assertIsNone(agent.current_ticket_id)

    def test_already_bound_ticket_is_not_overwritten(self) -> None:
        agent = _make_agent_loop(session_id="session_init")
        agent.set_ticket("VP-100")
        self._run_message(agent, "再看一下 LIS-999 然後回我")
        # Auto-detect must NOT overwrite an explicit binding mid-conversation.
        self.assertEqual(agent.session_id, "ticket_VP-100")


# ──────────────────────────────────────────────────────────────────────
# Item 2: _load_relevant_sessions
# ──────────────────────────────────────────────────────────────────────


class LoadRelevantSessionsCases(unittest.TestCase):
    """``_load_relevant_sessions`` round-trip against the real SessionIndex."""

    def test_empty_index_returns_empty_string(self) -> None:
        with _StoragePathPatch():
            agent = _make_agent_loop()
            self.assertEqual(agent._load_relevant_sessions("anything"), "")

    def test_empty_query_returns_empty_string(self) -> None:
        with _StoragePathPatch():
            agent = _make_agent_loop()
            # Even with rows present, an empty query short-circuits cleanly.
            from src.memory.manager import record_session_turns
            record_session_turns("s1", [{"text": "VP-15942 EMR routing", "speaker": "user"}])
            self.assertEqual(agent._load_relevant_sessions(""), "")

    def test_round_trip_injects_match(self) -> None:
        with _StoragePathPatch():
            from src.memory.manager import record_session_turns
            record_session_turns(
                "ticket_VP-15942",
                [
                    {
                        "text": "Leo asked about VP-15942 EMR routing today",
                        "speaker": "user",
                        "turn_date": "2026-04-23",
                    },
                ],
            )

            agent = _make_agent_loop()
            block = agent._load_relevant_sessions("VP-15942 EMR routing")

            self.assertIn("## Relevant past sessions", block)
            self.assertIn("ticket_VP-15942", block)
            self.assertIn("VP-15942", block)

    def test_search_failure_is_swallowed(self) -> None:
        agent = _make_agent_loop()
        # Force the underlying lookup to explode — helper must NOT raise.
        agent.memory_manager = mock.MagicMock()
        agent.memory_manager.search_sessions.side_effect = RuntimeError("boom")
        self.assertEqual(agent._load_relevant_sessions("anything"), "")

    def test_excerpt_truncation_and_global_cap(self) -> None:
        # Build a hand-rolled fake hit list to exercise the cap logic
        # without depending on FTS5 ranking.
        agent = _make_agent_loop()
        long_text = "X" * 5000
        fake_hits = [
            {
                "session_id": "sX",
                "turn_date": "2026-04-23",
                "speaker": "user",
                "text": long_text,
                "metadata": {},
                "rank": -1.0,
                "turn_index": 0,
            }
            for _ in range(10)
        ]
        agent.memory_manager = mock.MagicMock()
        agent.memory_manager.search_sessions.return_value = fake_hits

        from src.agent.loop import SESSION_MAX_CHARS, SESSION_EXCERPT_CHARS
        block = agent._load_relevant_sessions("query")
        # Total length must respect the global cap.
        self.assertLessEqual(len(block), SESSION_MAX_CHARS + 50)  # small slack for header
        # Each excerpt should be truncated (presence of the truncation marker).
        self.assertIn("…", block)
        # And must not contain the entire 5000-char blob.
        self.assertNotIn("X" * 1000, block)


# ──────────────────────────────────────────────────────────────────────
# Item 2: integration with _build_system_prompt
# ──────────────────────────────────────────────────────────────────────


class BuildSystemPromptInjectionCases(unittest.TestCase):
    """The system prompt grows by the sessions block iff there are hits."""

    def test_prompt_has_sessions_block_when_hits(self) -> None:
        agent = _make_agent_loop()
        agent._ensure_knowledge_indexed = mock.MagicMock()
        # Avoid chroma retrieval noise — only test the sessions injection.
        with mock.patch("src.agent.loop.retrieve_relevant_knowledge", return_value=[]):
            agent._load_relevant_sessions = mock.MagicMock(
                return_value="## Relevant past sessions\n- [sid|d|user] hi"
            )
            prompt = agent._build_system_prompt(user_message="VP-1 status?")
            self.assertIn("## Relevant past sessions", prompt)

    def test_prompt_lacks_sessions_block_when_no_hits(self) -> None:
        agent = _make_agent_loop()
        agent._ensure_knowledge_indexed = mock.MagicMock()
        with mock.patch("src.agent.loop.retrieve_relevant_knowledge", return_value=[]):
            agent._load_relevant_sessions = mock.MagicMock(return_value="")
            prompt = agent._build_system_prompt(user_message="hi")
            self.assertNotIn("## Relevant past sessions", prompt)

    def test_empty_user_message_skips_session_lookup(self) -> None:
        agent = _make_agent_loop()
        agent._load_relevant_sessions = mock.MagicMock(return_value="should-not-be-used")
        prompt = agent._build_system_prompt(user_message="")
        # With no user message, _build_system_prompt should not have called
        # the helper, so the canned return value never appears.
        agent._load_relevant_sessions.assert_not_called()
        self.assertNotIn("should-not-be-used", prompt)


if __name__ == "__main__":
    unittest.main()
