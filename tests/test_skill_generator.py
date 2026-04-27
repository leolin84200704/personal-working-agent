"""
Unit tests for src.memory.skill_generator.

Covers:
- generate_from_ticket: happy path with mocked `claude` CLI subprocess
- patch_skill: success and miss cases
- frontmatter shape matches the documented schema
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.memory.skill_generator import SkillGenerator  # noqa: E402


# A minimal MemoryManager stand-in. We deliberately don't import the
# real MemoryManager to keep this test independent of repo layout, env
# vars, and optional deps (anthropic SDK, pydantic-settings).
class _FakeManager:
    def __init__(self, root: Path) -> None:
        self.agent_root = root
        self.stm_dir = root / "storage" / "short_term_memory"
        self.stm_dir.mkdir(parents=True, exist_ok=True)

    def read_frontmatter(self, path: Path) -> dict:
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            return {}
        try:
            end = text.index("\n---", 3)
        except ValueError:
            return {}
        import yaml
        return yaml.safe_load(text[4:end]) or {}


def _write_stm(manager: _FakeManager, ticket_id: str, status: str = "completed") -> Path:
    body = (
        f"---\n"
        f"id: {ticket_id}\n"
        f"type: stm\n"
        f"category: technical\n"
        f"status: {status}\n"
        f"summary: 'Test ticket {ticket_id}'\n"
        f"---\n"
        f"# {ticket_id}\n\n"
        f"## Lessons Learned\n"
        f"When investigating slow queries, always check pg_stat_activity first, "
        f"then look at the index plan with EXPLAIN ANALYZE before changing schema.\n"
    )
    p = manager.stm_dir / f"{ticket_id}.md"
    p.write_text(body, encoding="utf-8")
    return p


class _FakeProc:
    """Fake CompletedProcess result for subprocess.run mocking."""

    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


class GenerateFromTicketTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.manager = _FakeManager(self.root)
        self.skills_root = self.root / "skills"
        self.gen = SkillGenerator(
            memory_manager=self.manager,
            skills_root=self.skills_root,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_generate_writes_skill_with_expected_frontmatter(self) -> None:
        ticket_id = "VP-99001"
        _write_stm(self.manager, ticket_id)

        fake_spec = {
            "name": "diagnose-slow-query",
            "title": "Diagnose Slow Postgres Query",
            "category": "debugging",
            "trigger": "Slow database query in Postgres",
            "when_to_use": ["DB latency spikes", "EMR ingest pipeline lag"],
            "steps": [
                "Inspect pg_stat_activity for blocking sessions.",
                "Run EXPLAIN ANALYZE on the offending query.",
                "Check index coverage before changing schema.",
            ],
            "pitfalls": ["Do not add an index without EXPLAIN evidence."],
            "references": [ticket_id],
        }

        with patch(
            "src.memory.skill_generator.subprocess.run",
            return_value=_FakeProc(json.dumps(fake_spec)),
        ) as mock_run:
            written = self.gen.generate_from_ticket(ticket_id)

        self.assertIsNotNone(written, "expected a skill path to be returned")
        mock_run.assert_called_once()
        argv = mock_run.call_args.args[0]
        self.assertEqual(argv[0], "claude")
        self.assertIn("-p", argv)
        self.assertIn("--model", argv)

        path = Path(written)
        self.assertTrue(path.exists())
        # category=debugging -> on-disk dir is "debugging"
        self.assertEqual(path.parent.name, "debugging")
        self.assertEqual(path.name, "diagnose-slow-query.md")

        text = path.read_text(encoding="utf-8")
        # Frontmatter shape
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("name: diagnose-slow-query", text)
        self.assertIn("type: skill", text)
        self.assertIn("category: debugging", text)
        self.assertIn("agent: lis-code-agent", text)
        self.assertIn(f"source_ticket: {ticket_id}", text)
        self.assertIn("trigger:", text)
        # Body sections
        self.assertIn("# Diagnose Slow Postgres Query", text)
        self.assertIn("## When to use", text)
        self.assertIn("## Steps", text)
        self.assertIn("## Common pitfalls", text)
        self.assertIn("## References", text)
        self.assertIn("1. Inspect pg_stat_activity", text)

    def test_generate_skips_non_completed_ticket(self) -> None:
        ticket_id = "VP-99002"
        _write_stm(self.manager, ticket_id, status="active")
        with patch("src.memory.skill_generator.subprocess.run") as mock_run:
            result = self.gen.generate_from_ticket(ticket_id)
        self.assertIsNone(result)
        mock_run.assert_not_called()


class PatchSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.manager = _FakeManager(self.root)
        self.skills_root = self.root / "skills"
        self.skills_root.mkdir()
        self.gen = SkillGenerator(
            memory_manager=self.manager,
            skills_root=self.skills_root,
        )

        self.skill_path = self.skills_root / "demo.md"
        self.skill_path.write_text(
            "---\n"
            "name: demo\n"
            "type: skill\n"
            "category: general\n"
            "agent: lis-code-agent\n"
            "trigger: demo\n"
            "created: 2026-01-01\n"
            "updated: 2026-01-01\n"
            "source_ticket: VP-0\n"
            "---\n"
            "# Demo\n\n"
            "## Steps\n"
            "1. Old step one\n"
            "2. Old step two\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_patch_success_replaces_section_and_bumps_updated(self) -> None:
        old = "## Steps\n1. Old step one\n2. Old step two\n"
        new = "## Steps\n1. New step one\n2. New step two\n3. New step three\n"
        ok = self.gen.patch_skill(str(self.skill_path), old, new)
        self.assertTrue(ok)
        text = self.skill_path.read_text(encoding="utf-8")
        self.assertIn("New step three", text)
        self.assertNotIn("Old step one", text)
        # `updated:` should not still be the original date.
        self.assertNotIn("updated: 2026-01-01", text)

    def test_patch_returns_false_when_old_section_missing(self) -> None:
        ok = self.gen.patch_skill(
            str(self.skill_path),
            "## Steps\nThis text is not in the file",
            "## Steps\nNew",
        )
        self.assertFalse(ok)
        # File unchanged.
        text = self.skill_path.read_text(encoding="utf-8")
        self.assertIn("Old step one", text)


if __name__ == "__main__":
    unittest.main()
