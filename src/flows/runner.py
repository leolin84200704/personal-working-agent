"""
Flow Runner — Orchestrates workflows triggered by external events.

Execution layer: Claude Code CLI (`claude -p`)
- Uses /login session (no API key needed)
- Has access to Vibrant MCP Server tools (Jira, DB, Sentry, Datadog)
- Has access to Claude Code native tools (Bash, Read, Edit, Grep)

This is the "when and what" layer:
- WHEN: webhook, schedule, manual trigger
- WHAT: which prompt to send
- WHERE: where to send the result (Jira comment, file)
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from src.flows.prompts import TICKET_TRIAGE_PROMPT, TRIAGE_REVIEW_PROMPT, TICKET_CODE_REVIEW_PROMPT
from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()
settings = get_settings()


def _retrieve_context(query: str, n_results: int = 5) -> str:
    """
    Retrieve relevant knowledge from ChromaDB (Tier 2 context).

    Searches MEMORY.md and SOUL.md sections indexed in the vector store.
    Returns formatted context string to append to the prompt.
    """
    try:
        from src.memory.vector_store import VectorStore
        from src.memory.indexer import retrieve_relevant_knowledge, KNOWLEDGE_COLLECTION

        vs = VectorStore(persist_path=str(settings.chroma_path))

        # Ensure indexed
        collection = vs.client.get_or_create_collection(name=KNOWLEDGE_COLLECTION)
        if collection.count() == 0:
            from src.memory.indexer import index_memory_file, index_soul_details
            index_memory_file(vs)
            index_soul_details(vs)

        results = retrieve_relevant_knowledge(vs, query=query, n_results=n_results)
        if not results:
            return ""

        sections = []
        for r in results:
            sections.append(f"### {r['title']}\n{r['text']}")

        return "\n\n".join(sections)
    except Exception as e:
        logger.debug(f"[Flow] Knowledge retrieval failed: {e}")
        return ""


def _run_claude(prompt: str, timeout: int = 600) -> dict[str, Any]:
    """
    Execute a prompt via Claude Code CLI.

    Context loading:
    - Tier 1: CLAUDE.md (auto-loaded by Claude Code from project root)
    - Tier 2: Retrieved knowledge (appended via --append-system-prompt)
    - Tier 3: MEMORY.md/SOUL.md readable on-demand (Claude Code can Read them)

    Uses the /login session — no API key needed.
    Has access to MCP servers configured in .mcp.json.

    Args:
        prompt: The prompt to send
        timeout: Max seconds to wait (default 10 min)

    Returns:
        Dict with response text, cost info, and metadata
    """
    # Tier 2: Retrieve relevant knowledge for this prompt
    retrieved = _retrieve_context(prompt[:500])  # Use first 500 chars as query

    cmd = [
        "claude",
        "-p", prompt,
        "--output-format", "json",
    ]

    # Inject Tier 2 context via --append-system-prompt
    if retrieved:
        tier2_prompt = (
            "以下是與當前任務相關的領域知識（從 MEMORY.md 和 SOUL.md 檢索）：\n\n"
            + retrieved
        )
        cmd.extend(["--append-system-prompt", tier2_prompt])

    # Allow all MCP tools from Vibrant server
    if settings.claude_allowed_tools:
        cmd.extend(["--allowedTools", settings.claude_allowed_tools])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(settings.agent_root),  # .mcp.json lives here
        )

        if result.returncode != 0:
            logger.error(f"[Flow] Claude CLI error: {result.stderr[:500]}")
            return {
                "response": f"Claude CLI failed (exit {result.returncode}): {result.stderr[:500]}",
                "error": result.stderr[:500],
            }

        # Parse JSON output
        # claude -p --output-format json returns:
        # {"type":"result","result":"...","total_cost_usd":0.04,"duration_ms":2345,"num_turns":1}
        try:
            output = json.loads(result.stdout)
            return {
                "response": output.get("result", result.stdout),
                "cost_usd": output.get("total_cost_usd"),
                "duration_ms": output.get("duration_ms"),
                "num_turns": output.get("num_turns"),
                "is_error": output.get("is_error", False),
                "session_id": output.get("session_id"),
            }
        except json.JSONDecodeError:
            # Fallback: treat stdout as plain text
            return {"response": result.stdout}

    except subprocess.TimeoutExpired:
        logger.error(f"[Flow] Claude CLI timed out after {timeout}s")
        return {"response": f"Timed out after {timeout}s", "error": "timeout"}
    except FileNotFoundError:
        logger.error("[Flow] 'claude' CLI not found. Is Claude Code installed?")
        return {"response": "Error: claude CLI not found", "error": "cli_not_found"}


class FlowRunner:
    """
    Runs predefined workflows via Claude Code CLI.

    Each flow is:
    1. A trigger (webhook, schedule, manual)
    2. A prompt template (what to tell Claude)
    3. An output destination (Jira comment, Slack, file)

    Python controls the orchestration. Claude controls the analysis.
    """

    def __init__(self):
        self.output_dir = settings.storage_path / "flow_results"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def on_ticket_created(self, ticket_id: str) -> dict[str, Any]:
        """
        Triggered when a new Jira ticket is created.

        Dual-agent flow:
        1. Agent A: Full triage analysis (reads ticket, queries tools, produces report)
        2. Agent B: Independent review of Agent A's output (re-reads ticket, verifies)
        3. Combine both into final result
        """
        # --- Agent A: Triage Analysis ---
        prompt_a = TICKET_TRIAGE_PROMPT.format(ticket_id=ticket_id)

        logger.info(f"[Flow] Agent A (triage) started for {ticket_id}")
        result_a = _run_claude(prompt_a, timeout=settings.flow_timeout_seconds)
        logger.info(f"[Flow] Agent A completed for {ticket_id}")

        agent_a_response = result_a.get("response", "")
        agent_a_error = result_a.get("error")

        # --- Agent B: Independent Review ---
        review_response = ""
        result_b = {}
        if agent_a_response and not agent_a_error:
            prompt_b = TRIAGE_REVIEW_PROMPT.format(
                ticket_id=ticket_id,
                agent_a_response=agent_a_response[:8000],  # Cap to avoid prompt overflow
            )

            logger.info(f"[Flow] Agent B (review) started for {ticket_id}")
            result_b = _run_claude(prompt_b, timeout=settings.flow_timeout_seconds)
            review_response = result_b.get("response", "")
            logger.info(f"[Flow] Agent B completed for {ticket_id}")
        else:
            logger.warning(f"[Flow] Skipping Agent B — Agent A had error or empty response")

        # --- Combine Results ---
        combined_response = agent_a_response
        if review_response:
            combined_response = (
                f"{agent_a_response}\n\n"
                f"---\n\n"
                f"## 獨立審查 (Agent B)\n\n"
                f"{review_response}"
            )

        total_cost = (result_a.get("cost_usd") or 0) + (result_b.get("cost_usd") or 0)
        total_duration = (result_a.get("duration_ms") or 0) + (result_b.get("duration_ms") or 0)

        output = {
            "flow": "ticket_triage_dual_review",
            "ticket_id": ticket_id,
            "timestamp": datetime.now().isoformat(),
            "response": combined_response,
            "agent_a_response": agent_a_response,
            "agent_b_review": review_response,
            "cost_usd": total_cost if total_cost > 0 else None,
            "duration_ms": total_duration if total_duration > 0 else None,
            "num_turns_a": result_a.get("num_turns"),
            "num_turns_b": result_b.get("num_turns"),
            "error": agent_a_error,
        }
        self._save_result(ticket_id, "triage", output)

        # Notify + Audit
        if settings.flow_post_to_jira:
            await self._post_jira_comment(ticket_id, combined_response)
        self._write_analysis_file(ticket_id, combined_response)
        _write_audit_log(ticket_id, combined_response)

        return output

    async def on_code_review_requested(self, ticket_id: str) -> dict[str, Any]:
        """
        Triggered when user wants to review changes on a ticket's branch.
        """
        prompt = TICKET_CODE_REVIEW_PROMPT.format(ticket_id=ticket_id)

        logger.info(f"[Flow] Code review started for {ticket_id}")
        result = _run_claude(prompt, timeout=settings.flow_timeout_seconds)

        output = {
            "flow": "code_review",
            "ticket_id": ticket_id,
            "timestamp": datetime.now().isoformat(),
            "response": result.get("response", ""),
            "cost_usd": result.get("cost_usd"),
            "error": result.get("error"),
        }
        self._save_result(ticket_id, "review", output)

        self._write_analysis_file(ticket_id, result.get("response", ""))
        _write_audit_log(ticket_id, result.get("response", ""))

        return output

    def _save_result(self, ticket_id: str, flow_type: str, output: dict) -> None:
        """Save flow result to a JSON file."""
        filename = f"{ticket_id}_{flow_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.output_dir / filename
        filepath.write_text(
            json.dumps(output, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        logger.info(f"[Flow] Result saved to {filepath}")

    async def _post_jira_comment(self, ticket_id: str, content: str) -> None:
        """Post analysis result as a Jira comment."""
        try:
            from src.integrations.jira import JiraClient
            client = JiraClient()
            client.jira.add_comment(
                ticket_id,
                f"**LIS Code Agent — Auto Triage**\n\n{content}",
            )
            logger.info(f"[Flow] Posted Jira comment on {ticket_id}")
        except Exception as e:
            logger.error(f"[Flow] Failed to post Jira comment: {e}")

    def _write_analysis_file(self, ticket_id: str, content: str) -> None:
        """Write analysis result to ~/Desktop/Jira Analysis/{ticket_id}.md"""
        try:
            analysis_dir = Path.home() / "Desktop" / "Jira Analysis"
            analysis_dir.mkdir(parents=True, exist_ok=True)
            filepath = analysis_dir / f"{ticket_id}.md"
            filepath.write_text(content, encoding="utf-8")
            logger.info(f"[Flow] Analysis written to {filepath}")
        except Exception as e:
            logger.error(f"[Flow] Failed to write analysis file: {e}")


def _write_audit_log(ticket_id: str, response_text: str) -> None:
    """
    Extract and log any SQL queries found in the agent response.

    Writes to storage/audit/sql_audit.jsonl for traceability.
    SQL safety: logs all queries so dangerous patterns can be detected post-hoc.
    """
    try:
        audit_dir = get_settings().storage_path / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "sql_audit.jsonl"

        # Extract SQL-like patterns from the response
        sql_patterns = re.findall(
            r'(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)\s+.+?(?:;|$)',
            response_text,
            re.IGNORECASE | re.MULTILINE,
        )

        if not sql_patterns:
            return

        # Flag dangerous queries
        dangerous_keywords = re.compile(
            r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)\b', re.IGNORECASE
        )

        entries = []
        for sql in sql_patterns:
            sql_clean = sql.strip()[:500]  # Cap length
            is_dangerous = bool(dangerous_keywords.search(sql_clean))
            entries.append({
                "timestamp": datetime.now().isoformat(),
                "ticket_id": ticket_id,
                "sql": sql_clean,
                "dangerous": is_dangerous,
            })
            if is_dangerous:
                logger.warning(f"[Audit] DANGEROUS SQL detected for {ticket_id}: {sql_clean[:100]}")

        with open(audit_file, "a", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"[Audit] Logged {len(entries)} SQL queries for {ticket_id}")
    except Exception as e:
        logger.error(f"[Audit] Failed to write SQL audit log: {e}")
