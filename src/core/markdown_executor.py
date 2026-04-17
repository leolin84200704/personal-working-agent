"""
Markdown Executor - OpenClaw-style execution engine.

This executor reads skills from markdown files and consults the LLM
on how to execute them, rather than having hardcoded execution logic.

SUPPORTED: Self-iteration and error correction (like Claude Code)
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from ..auth import resolve_api_key
from ..config import get_settings
from ..skills.loader import get_skill_loader, Skill

load_dotenv()


class MarkdownExecutor:
    """
    Execute tasks based on markdown skill definitions.

    The executor:
    1. Reads the skill markdown
    2. Provides the skill content to the LLM
    3. LLM determines the execution plan
    4. Executor runs the plan and reports results
    """

    def __init__(self, claude: Anthropic | None = None):
        """
        Initialize the markdown executor.

        Args:
            claude: Anthropic client for LLM consultation
        """
        if claude is None:
            import os
            api_key = resolve_api_key(os.getenv("ANTHROPIC_API_KEY"))
            base_url = os.getenv("ANTHROPIC_BASE_URL")
            if base_url:
                self.claude = Anthropic(api_key=api_key, base_url=base_url)
            else:
                self.claude = Anthropic(api_key=api_key)
        else:
            self.claude = claude

        self.skill_loader = get_skill_loader()
        self.repo_path = Path("/Users/hung.l/src/lis-backend-emr-v2")

    def execute_emr_integration(self, ticket: Any) -> dict:
        """
        Execute an EMR Integration ticket using markdown-driven approach.

        NEW: Includes Phase 0 pre-analysis for critical thinking.

        Args:
            ticket: JiraTicket object

        Returns:
            Dict with execution results
        """
        # Load the skill
        skill = self.skill_loader.get_skill("emr-integration")
        if not skill:
            return {
                "success": False,
                "error": "emr-integration skill not found",
                "output": "Please ensure skills/emr-integration/SKILL.md exists"
            }

        # Load supporting documents
        soul = self.skill_loader.get_soul_md()
        tools = self.skill_loader.get_tools_md()
        agents = self.skill_loader.get_agents_md()
        phase_0_doc = self.skill_loader.get_skill("debugging")

        # ============================================================
        # PHASE 0: Pre-Analysis (CRITICAL THINKING)
        # ============================================================
        # Before any execution, verify assumptions and check existing state
        phase_0_result = self._phase_0_pre_analysis(
            ticket, skill, soul, tools, phase_0_doc
        )

        # If Phase 0 detected a problem or needs clarification, stop here
        if not phase_0_result.get("can_proceed"):
            return {
                "success": False,
                "phase_0_blocker": True,
                "output": phase_0_result.get("message"),
                "clarifying_questions": phase_0_result.get("questions"),
                "verification_needed": phase_0_result.get("verification_needed"),
            }

        # Phase 0 passed - proceed with analysis and execution
        # Step 1: LLM Analysis Phase
        analysis = self._llm_analyze_with_skill(
            ticket, skill, soul, tools, agents, phase_0_result
        )

        if not analysis.get("success"):
            return analysis

        # Step 2: Execute the plan
        result = self._execute_plan(ticket, analysis, phase_0_result)

        return {
            "success": result.get("success", False),
            "output": result.get("output", ""),
            "analysis": analysis,
            "error": result.get("error"),
        }

    # ============================================================
    # PHASE 0: Pre-Analysis (CRITICAL THINKING)
    # ============================================================

    def _phase_0_pre_analysis(
        self, ticket: Any, skill: Skill, soul: str, tools: str, debug_skill: Skill | None
    ) -> dict:
        """
        Phase 0: Verify assumptions before executing.

        This implements critical thinking by:
        1. Questioning the problem statement
        2. Checking existing configuration
        3. Identifying vague or error-prone assumptions

        Returns dict with:
            can_proceed: bool - whether execution should continue
            message: str - explanation of any issues found
            questions: list - clarifying questions to ask user
            verification_needed: dict - what needs to be verified
        """
        # Load debugging guidelines if available
        debug_guidelines = ""
        if debug_skill:
            debug_guidelines = debug_skill.get_section("Common Traps") or ""
            if not debug_guidelines:
                debug_guidelines = debug_skill.content or ""

        # Extract ticket info
        summary = ticket.summary.lower() if hasattr(ticket, 'summary') else ""
        description = ticket.description.lower() if hasattr(ticket, 'description') else ""

        # Combine for analysis
        ticket_text = f"{summary} {description}"

        # ============================================================
        # CRITICAL PATTERN DETECTION - Known Problematic Patterns
        # ============================================================

        # Pattern 1: "CORS error" without details
        cors_patterns = ["cors error", "cors issue", "cors blocked", "cross-origin"]
        has_cors_keyword = any(p in ticket_text for p in cors_patterns)
        has_cors_details = any([
            "allow_origins" in ticket_text,
            "allowed_origins" in ticket_text,
            "credentials" in ticket_text,
            "preflight" in ticket_text,
            "options request" in ticket_text,
        ])

        if has_cors_keyword and not has_cors_details:
            return {
                "can_proceed": False,
                "message": """🚨 PHASE 0 BLOCKER: Vague problem statement detected

Ticket mentions 'CORS error' but lacks verification details.

**Common Trap:** Just because ticket says "CORS error" doesn't mean it is CORS.
- Same-origin requests don't have CORS
- ALLOWED_ORIGINS might already have the domain
- "Failed Network Error" is vague - could be many things

**Before proceeding, verify:**
1. What is the EXACT browser console error message?
2. What is the frontend domain calling the API?
3. Is the API call same-origin or cross-origin?
4. Check ALLOWED_ORIGINS configuration first
""",
                "questions": [
                    "What is the exact browser console error message?",
                    "What is the frontend domain making the request?",
                    "Is the API call same-origin or cross-origin?",
                    "Can you share the network tab details?"
                ],
                "verification_needed": {
                    "check": "ALLOWED_ORIGINS",
                    "command": 'grep -r "ALLOWED_ORIGINS" k8s/',
                    "reason": "Domain might already be allowed"
                }
            }

        # Pattern 2: "Network error" or "Failed to fetch" without context
        network_error_patterns = ["network error", "failed to fetch", "failed network", "connection failed"]
        has_network_error = any(p in ticket_text for p in network_error_patterns)

        if has_network_error and not any([
            "timeout" in ticket_text,
            "404" in ticket_text or "401" in ticket_text or "403" in ticket_text or "500" in ticket_text,
            "dns" in ticket_text,
        ]):
            return {
                "can_proceed": False,
                "message": """🚨 PHASE 0 BLOCKER: Vague error description

"Network error" or "Failed to fetch" could mean many things:
- DNS resolution failure
- Server not responding
- Timeout
- Actual CORS issue
- Authentication failure
- Firewall blocking

**Need more specific information to proceed.**
""",
                "questions": [
                    "What is the exact error message from browser console?",
                    "What is the HTTP status code (if any)?",
                    "What does the browser Network tab show?",
                    "Can you access the API URL directly in browser?"
                ],
                "verification_needed": {
                    "check": "API endpoint",
                    "action": "Test endpoint directly with curl"
                }
            }

        # Pattern 3: Missing critical identifiers in EMR tickets
        if "emr" in ticket_text or "integration" in ticket_text:
            has_provider_id = "provider id" in ticket_text or "provider_id" in ticket_text
            has_practice_id = "practice id" in ticket_text or "practice_id" in ticket_text or "clinic" in ticket_text

            if not has_provider_id or not has_practice_id:
                return {
                    "can_proceed": False,
                    "message": """🚨 PHASE 0 BLOCKER: Missing required identifiers

EMR Integration tickets require:
- Provider ID (customer account ID)
- Practice ID (clinic/facility ID)

Cannot proceed without these identifiers.
""",
                    "questions": [
                        "What is the Provider ID?",
                        "What is the Practice ID (or Clinic ID)?"
                    ],
                    "verification_needed": {
                        "check": "ticket description for missing IDs"
                    }
                }

        # ============================================================
        # PASSED PHASE 0 - Can proceed with execution
        # ============================================================
        return {
            "can_proceed": True,
            "message": "✅ Phase 0 passed: Problem statement appears verifiable",
            "verified_assumptions": [],
            "notes": "Proceeding with analysis and execution"
        }

    def _execute_phase_0_verification(self, verification: dict) -> dict:
        """
        Execute a Phase 0 verification command.

        This allows the agent to check existing configuration before making changes.
        Examples:
        - Check ALLOWED_ORIGINS for CORS issues
        - Test API endpoints for network errors
        - Check database for existing records

        Args:
            verification: dict with 'check', 'command', 'action', or 'reason' keys

        Returns:
            Dict with verification results
        """
        check_type = verification.get("check", "")
        command = verification.get("command", "")
        action = verification.get("action", "")

        if command:
            return self._run_bash(command, timeout=30)

        if action == "Test endpoint directly with curl":
            # Extract URL from context or return guidance
            return {
                "success": False,
                "guidance": "Please provide the API endpoint URL to test",
                "example": "curl -v https://api.example.com/endpoint"
            }

        return {
            "success": False,
            "error": f"Unknown verification type: {check_type}"
        }

    # ============================================================
    # END PHASE 0
    # ============================================================

    async def execute_with_retry(
        self,
        task_description: str,
        max_iterations: int = 5,
        context: str = "",
        debug: bool = False
    ) -> dict:
        """
        Execute a task with automatic retry on error.

        This enables the agent to:
        1. Write code
        2. Execute it
        3. See errors
        4. Auto-correct
        5. Retry

        All in a single user interaction - like Claude Code!

        Args:
            task_description: What the user wants to do
            max_iterations: Maximum retry attempts
            context: Additional context (ticket info, etc.)
            debug: Print debug info

        Returns:
            Dict with success status, iterations, and output
        """
        iteration = 0
        execution_history = []
        last_error = None
        last_output = None

        while iteration < max_iterations:
            iteration += 1

            if iteration == 1:
                # First attempt: execute original task
                prompt = f"""Execute this task:

{task_description}

{context}

You have access to these tools:
- read_file: Read file contents (params: path)
- write_file: Write/create a file (params: path, content)
- edit_file: Edit a file (params: path, old_string, new_string)
- run_bash: Execute bash commands (params: command, cwd, timeout)

IMPORTANT: Respond ONLY with a JSON array of actions, like this:
```json
[
  {{"action": "write_file", "params": {{"path": "scripts/test.ts", "content": "content here"}}}},
  {{"action": "run_bash", "params": {{"command": "npx ts-node scripts/test.ts"}}}}
]
```

Execute the actions in order. If an action fails, STOP and report the error.
"""
            else:
                # Retry: fix the error and try again
                prompt = f"""Previous attempt failed. Fix the error and retry.

**Original Task:**
{task_description}

**Error from last attempt:**
{last_error}

**What was done:**
{chr(10).join(f"- {step}" for step in execution_history[-5:])}

**Last output (if any):**
{last_output or "(none)"}

Provide CORRECTED actions in JSON format. Only include actions that need to be retried.
IMPORTANT: Respond ONLY with a JSON array.
"""

            # Get plan from LLM
            try:
                response = self.claude.messages.create(
                    model=get_settings().default_model,
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}]
                )

                plan_text = response.content[0].text

                if debug:
                    print(f"\n[DEBUG] LLM Response:\n{plan_text}\n")

                # Parse and execute actions
                result = await self._execute_plan_from_text(plan_text, execution_history)

                execution_history.append(f"Iteration {iteration}: {result.get('summary', 'Executed')}")

                if result.get("success"):
                    return {
                        "success": True,
                        "iterations": iteration,
                        "output": result.get("output"),
                        "message": f"✅ Completed in {iteration} iteration(s)",
                        "execution_history": execution_history
                    }

                # Store error for retry
                last_error = result.get("error", "Unknown error")
                last_output = result.get("output", "")

            except Exception as e:
                last_error = str(e)
                execution_history.append(f"Iteration {iteration}: Exception - {last_error}")

        # All attempts failed
        return {
            "success": False,
            "iterations": iteration,
            "error": last_error,
            "message": f"❌ Failed after {iteration} attempts",
            "execution_history": execution_history,
            "last_output": last_output
        }

    async def _execute_plan_from_text(
        self,
        plan_text: str,
        history: list | None = None
    ) -> dict:
        """
        Parse LLM response and execute the actions.

        This is the core of iterative execution - takes natural language
        (or mixed JSON) from LLM and executes the actions.
        """
        if history is None:
            history = []

        # Try JSON parsing first
        actions = self._parse_actions(plan_text)

        # Fallback: interpret natural language if no actions found
        if not actions:
            natural_result = await self._interpret_natural_language(plan_text)
            if natural_result.get("success"):
                return natural_result
            else:
                return {
                    "success": False,
                    "error": natural_result.get("error", "No actions found in LLM response"),
                    "summary": "No actions to execute"
                }

        results = []
        errors = []

        for i, action in enumerate(actions):
            action_type = action.get("action")
            params = action.get("params", {})

            try:
                if action_type == "read_file":
                    result = self._read_file(params.get("path", ""))
                    if result.get("success"):
                        results.append(f"Read {result.get('lines')} lines from {params.get('path')}")
                    else:
                        errors.append(result.get("error"))
                        return {"success": False, "error": result.get("error"), "summary": f"Failed at step {i+1}"}

                elif action_type == "write_file":
                    result = self._write_file(
                        params.get("path", ""),
                        params.get("content", "")
                    )
                    if result.get("success"):
                        results.append(f"Wrote {result.get('bytes_written')} bytes to {params.get('path')}")
                    else:
                        errors.append(result.get("error"))
                        return {"success": False, "error": result.get("error"), "summary": f"Failed at step {i+1}"}

                elif action_type == "edit_file":
                    result = self._edit_file(
                        params.get("path", ""),
                        params.get("old_string", ""),
                        params.get("new_string", "")
                    )
                    if result.get("success"):
                        results.append(f"Edited {params.get('path')} ({result.get('replacements')} changes)")
                    else:
                        errors.append(result.get("error"))
                        return {"success": False, "error": result.get("error"), "summary": f"Failed at step {i+1}"}

                elif action_type == "run_bash":
                    result = self._run_bash(
                        params.get("command", ""),
                        cwd=params.get("cwd"),
                        timeout=params.get("timeout", 120)
                    )
                    if result.get("success"):
                        stdout = result.get("stdout", "")
                        if stdout:
                            results.append(f"Command succeeded: {stdout[:200]}...")
                        else:
                            results.append(f"Command succeeded")
                    else:
                        stderr = result.get("stderr", "")
                        error = result.get("error", "")
                        errors.append(f"Bash error: {stderr or error}")
                        return {
                            "success": False,
                            "error": stderr or error,
                            "summary": f"Command failed at step {i+1}",
                            "command": params.get("command", "")
                        }

                else:
                    errors.append(f"Unknown action: {action_type}")
                    return {"success": False, "error": f"Unknown action: {action_type}", "summary": f"Failed at step {i+1}"}

            except Exception as e:
                errors.append(str(e))
                return {"success": False, "error": str(e), "summary": f"Exception at step {i+1}"}

        output = "\n".join(results)
        summary = f"Executed {len(actions)} action(s) successfully"

        return {
            "success": True,
            "output": output,
            "summary": summary,
            "actions_executed": len(actions)
        }

    async def _interpret_natural_language(self, text: str) -> dict:
        """
        Fallback: Use LLM to convert natural language to actions.

        This handles cases where the first LLM didn't return proper JSON.
        """
        try:
            response = self.claude.messages.create(
                model=get_settings().default_model,
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": f"""Convert this task into a JSON array of actions.

Task: {text}

Available actions:
- write_file: {{"action": "write_file", "params": {{"path": "file.txt", "content": "text"}}}}
- run_bash: {{"action": "run_bash", "params": {{"command": "ls -la"}}}}

Respond ONLY with the JSON array, no other text."""
                }]
            )

            llm_text = response.content[0].text
            actions = self._parse_actions(llm_text)

            if not actions:
                return {"success": False, "error": "Could not interpret natural language"}

            # Execute the parsed actions
            return await self._execute_actions(actions)

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_actions(self, actions: list) -> dict:
        """Execute a list of actions (helper for natural language fallback)."""
        results = []

        for action in actions:
            action_type = action.get("action")
            params = action.get("params", {})

            if action_type == "write_file":
                result = self._write_file(params.get("path", ""), params.get("content", ""))
                if not result.get("success"):
                    return {"success": False, "error": result.get("error")}
                results.append(f"Wrote to {params.get('path')}")

            elif action_type == "run_bash":
                result = self._run_bash(params.get("command", ""))
                if not result.get("success"):
                    return {"success": False, "error": result.get("error")}
                results.append(f"Executed: {params.get('command')}")

        return {
            "success": True,
            "output": "\n".join(results),
            "summary": f"Executed {len(actions)} action(s)"
        }

    def _parse_actions(self, text: str) -> list:
        """
        Parse actions from LLM response.

        Handles multiple formats:
        - Pure JSON array
        - JSON in code blocks
        - Mixed text with JSON
        - Individual action objects
        """
        actions = []
        seen = set()  # Avoid duplicates

        def add_action(action):
            """Add action if valid and not duplicate."""
            if not action or not isinstance(action, dict):
                return False
            action_type = action.get("action")
            if not action_type or action_type == "None":
                return False
            # Create a hash for deduplication
            action_str = json.dumps(action, sort_keys=True)
            if action_str not in seen:
                seen.add(action_str)
                actions.append(action)
                return True
            return False

        # 1. Try to find JSON array in ```json code blocks
        json_block_pattern = r'```(?:json)?\s*(\[.*?\])\s*```'
        matches = re.findall(json_block_pattern, text, re.DOTALL)

        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, list):
                    for item in parsed:
                        add_action(item)
            except json.JSONDecodeError:
                pass

        # 2. Try to find JSON array without code block (but with brackets)
        if not actions:
            # Look for outermost brackets
            start = text.find('[')
            if start != -1:
                # Find matching closing bracket
                depth = 0
                for i in range(start, len(text)):
                    if text[i] == '[':
                        depth += 1
                    elif text[i] == ']':
                        depth -= 1
                        if depth == 0:
                            json_str = text[start:i+1]
                            try:
                                parsed = json.loads(json_str)
                                if isinstance(parsed, list):
                                    for item in parsed:
                                        add_action(item)
                            except json.JSONDecodeError:
                                pass
                            break

        # 3. Try to parse individual action objects (more flexible pattern)
        if not actions:
            # Match objects with "action" and "params" keys
            object_pattern = r'\{\s*"action"\s*:\s*"([^"]+)"\s*,\s*"params"\s*:\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}\s*\}'
            matches = re.findall(object_pattern, text, re.DOTALL)

            for action_type, params_str in matches:
                try:
                    action = {
                        "action": action_type,
                        "params": json.loads('{' + params_str + '}')
                    }
                    add_action(action)
                except json.JSONDecodeError:
                    pass

        # 4. Last resort: parse line by line for JSON objects
        if not actions:
            for line in text.split('\n'):
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, dict) and "action" in parsed:
                            add_action(parsed)
                    except json.JSONDecodeError:
                        pass

        return actions

    # ============================================================
    # END ITERATIVE EXECUTION
    # ============================================================

    def _llm_analyze_with_skill(
        self, ticket: Any, skill: Skill, soul: str, tools: str, agents: str,
        phase_0_result: dict | None = None
    ) -> dict:
        """
        Consult LLM with the skill markdown to create an execution plan.
        """
        # Extract key sections from skill
        execution_flow = skill.get_section("Execution Flow")
        critical_rules = skill.get_section("Critical Business Rules")
        decision_tree = skill.get_section("Decision Tree")
        examples = skill.get_section("Examples")

        # Add Phase 0 context if available
        phase_0_context = ""
        if phase_0_result and phase_0_result.get("can_proceed"):
            phase_0_context = f"""
PHASE 0 PRE-ANALYSIS (COMPLETED):
{phase_0_result.get("message", "")}

This ticket has passed pre-analysis verification. You can trust the problem statement.
"""

        system_prompt = f"""You are an EMR Integration specialist. Your task is to analyze tickets and create execution plans.

PHASE 0: CRITICAL THINKING GUIDELINES
Before ANY execution, ALWAYS verify:
1. Question the problem statement - is it accurate?
2. Check existing configuration before making changes
3. Test assumptions before coding
4. Use evidence-based analysis instead of pattern matching

{phase_0_context}

BUSINESS RULES (from SOUL.md and skill):
{soul}

{critical_rules}

AVAILABLE TOOLS:
{tools}

CODE EXECUTION CAPABILITIES:
You can CREATE and EXECUTE new scripts when needed! Use these actions:
- read_file: Read any file in the repository
- write_file: Write new scripts or modify existing ones
- edit_file: Make targeted edits to files
- run_bash: Execute any bash command (npx ts-node, npm, etc.)

When you need functionality that doesn't exist in existing scripts:
1. Create a new TypeScript script using write_file
2. Make it executable with run_bash
3. Execute it and analyze results
4. Iterate based on errors

EXECUTION FLOW:
{execution_flow}

DECISION TREE:
{decision_tree}

EXAMPLES (Learn from these):
{examples}

CRITICAL PATTERN DETECTION - MSH VALUE:
Before deciding msh06_source, CAREFULLY check if ticket description contains ANY of these phrases:
1. "MSH value is the Practice ID"
2. "MSH value is the practice ID"
3. "msh value is the practice id"
4. "update all MSH values to practice ID"  ← Check for "ALL" - indicates BULK UPDATE!
5. "use practice ID for MSH"

If ANY phrase found → msh06_source = "practice_id"
If NONE found → msh06_source = "customer_id" (DEFAULT)

BULK UPDATE DETECTION:
If ticket says "update ALL MSH values" or "for this practice" + MSH pattern:
- This means updating ALL existing providers in the clinic, not just the new one
- Use action: "bulk_update_clinic_msh" with clinic_id parameter
- Tool: update-clinic-msh.ts --clinic-id=<PRACTICE_ID>
- Example: VP-15791 required updating 3 records in clinic 127265

MULTI-PRACTICE PROVIDER DETECTION:
If ticket contains a TABLE with Practice IDs and Provider IDs:
- Check if SAME Provider ID appears under MULTIPLE Practice IDs
- This means one provider works at multiple locations
- Each (Provider, Practice) combination needs its OWN ehr_integrations record
- Example: Anna Emanuel (43262) in practices 2930, 8003, 36290 = 3 separate records
- Parse ALL combinations, not just unique providers
- Output: List ALL (provider_id, practice_id) combinations in the execution plan

This is the MOST IMPORTANT pattern to detect. Missing this causes incorrect data!

IMPORTANT:
- Respond in Traditional Chinese (繁體中文) for reasoning
- Output valid JSON for the execution plan
- Provider Name MUST come from gRPC, not from ticket
- Always UPDATE wrong data, never skip it
- Check MSH pattern FIRST before deciding msh06_source
"""

        user_prompt = f"""Analyze this ticket and create an execution plan.

## Ticket
Key: {ticket.key}
Summary: {ticket.summary}
Description:
{ticket.description[:2000]}

Create an execution plan in JSON format:
{{
    "extracted_data": {{
        "provider_id": "...",
        "practice_id": "...",
        "clinic_name": "...",
        "emr_name": "...",
        "msh06_source": "customer_id" or "practice_id"
    }},
    "missing_data": ["provider_name", "npi"],
    "actions": [
        {{"step": 1, "action": "fetch_grpc", "tool": "get-customer-rpc", "params": {{...}}}},
        {{"step": 2, "action": "check_db", "tool": "get-existing-data-json", "params": {{...}}}},
        {{"step": 3, "action": "compare", "description": "..."}},
        {{"step": 4, "action": "update/insert", "tool": "...", "params": {{...}}}}
    ],
    "reasoning": "..."
}}

AVAILABLE ACTIONS FOR CODE EXECUTION:
- "read_file": {{"action": "read_file", "params": {{"path": "scripts/file.ts"}}}}
- "write_file": {{"action": "write_file", "params": {{"path": "scripts/new.ts", "content": "..."}}}}
- "edit_file": {{"action": "edit_file", "params": {{"path": "file.ts", "old_string": "...", "new_string": "..."}}}}
- "run_bash": {{"action": "run_bash", "params": {{"command": "npx ts-node script.ts"}}}}
"""

        try:
            response = self.claude.messages.create(
                model=get_settings().default_model,
                max_tokens=3000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            content = response.content[0].text

            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            plan = json.loads(content)

            return {
                "success": True,
                "plan": plan,
                "raw_response": content,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"LLM analysis failed: {e}",
            }

    def _execute_plan(self, ticket: Any, analysis: dict, phase_0_result: dict | None = None) -> dict:
        """
        Execute the plan created by the LLM.
        """
        plan = analysis.get("plan", {})
        extracted = plan.get("extracted_data", {})
        actions = plan.get("actions", [])

        results = []
        results.append("=" * 60)
        results.append("🧠 STEP 1: LLM Analysis & Reasoning")
        results.append("=" * 60)
        results.append(f"\n📝 Reasoning:\n   {plan.get('reasoning', '')}")

        results.append(f"\n📋 Extracted Data:")
        for key, value in extracted.items():
            results.append(f"   {key}: {value}")

        missing = plan.get("missing_data", [])
        if missing:
            results.append(f"\n❓ Missing Data:")
            for item in missing:
                results.append(f"   - {item}")

        results.append(f"\n📋 Planned Actions:")
        for action in actions:
            step = action.get("step")
            act = action.get("action")
            results.append(f"   {step}. {act}")

        # Execute actions
        provider_id = extracted.get("provider_id")
        practice_id = extracted.get("practice_id")
        clinic_name = extracted.get("clinic_name", "")
        customer_firstname = ""
        customer_lastname = ""
        npi = None

        # Track what we need to do
        needs_update_ehr = False
        needs_update_order = False
        existing_data = {"ehr_integrations": None, "order_clients": None}

        for action in actions:
            action_type = action.get("action")
            tool = action.get("tool")
            params = action.get("params", {})

            if action_type == "fetch_grpc" and tool == "get-customer-rpc":
                results.append("\n" + "=" * 60)
                results.append("📞 STEP 2: Fetching Missing Data via gRPC")
                results.append("=" * 60)

                grpc_result = self._run_grpc_call(provider_id)
                if grpc_result.get("success"):
                    customer_firstname = grpc_result.get("first_name", "")
                    customer_lastname = grpc_result.get("last_name", "")
                    npi = grpc_result.get("npi", "")
                    results.append(f"\n✅ gRPC Response:")
                    results.append(f"   customer_first_name: {customer_firstname}")
                    results.append(f"   customer_last_name: {customer_lastname}")
                    results.append(f"   customer_npi_number: {npi}")
                else:
                    results.append(f"\n⚠️ gRPC call failed: {grpc_result.get('error')}")

            elif action_type == "check_db" and tool == "get-existing-data-json":
                results.append("\n" + "=" * 60)
                results.append("📊 STEP 3: Checking Database State")
                results.append("=" * 60)

                db_result = self._run_get_existing_data(provider_id)
                if db_result.get("success"):
                    existing_data = db_result.get("data", {})
                    ehr = existing_data.get("ehr_integrations")
                    order = existing_data.get("order_clients")

                    if ehr:
                        results.append(f"\n📊 Existing ehr_integrations:")
                        results.append(f"   customer_npi: {ehr.get('customer_npi', 'N/A')}")
                        results.append(f"   Expected NPI: {npi}")
                        if npi and ehr.get('customer_npi') != npi:
                            needs_update_ehr = True
                            results.append(f"   ⚠️ MISMATCH! Need to update NPI")
                        else:
                            results.append(f"   ✅ Data matches")
                    else:
                        needs_update_ehr = True
                        results.append(f"\n📊 ehr_integrations: No existing data (will insert)")

                    if order:
                        results.append(f"\n📊 Existing order_clients:")
                        results.append(f"   customer_name: {order.get('customer_name', 'N/A')}")
                        expected_name = f"{customer_firstname} {customer_lastname}"
                        results.append(f"   Expected: {expected_name}")
                        if order.get('customer_name') != expected_name:
                            needs_update_order = True
                            results.append(f"   ⚠️ MISMATCH! Need to update name")
                        if order.get('customer_provider_NPI') != npi:
                            needs_update_order = True
                            results.append(f"   ⚠️ MISMATCH! Need to update NPI")
                    else:
                        needs_update_order = True
                        results.append(f"\n📊 order_clients: No existing data (will insert)")

            elif action_type == "compare":
                # Comparison already done in check_db
                pass

            # === CODE EXECUTION TOOLS ===
            elif action_type == "read_file":
                file_path = params.get("path")
                results.append(f"\n📖 Reading file: {file_path}")
                read_result = self._read_file(file_path)
                if read_result.get("success"):
                    results.append(f"   ✅ Read {read_result.get('lines')} lines")
                    # Store content for potential use in subsequent actions
                    results.append(f"   Content preview: {read_result.get('content')[:200]}...")
                else:
                    results.append(f"   ❌ Error: {read_result.get('error')}")

            elif action_type == "write_file":
                file_path = params.get("path")
                content = params.get("content", "")
                results.append(f"\n✏️  Writing file: {file_path}")
                write_result = self._write_file(file_path, content)
                if write_result.get("success"):
                    results.append(f"   ✅ Wrote {write_result.get('bytes_written')} bytes")
                else:
                    results.append(f"   ❌ Error: {write_result.get('error')}")

            elif action_type == "edit_file":
                file_path = params.get("path")
                old_string = params.get("old_string", "")
                new_string = params.get("new_string", "")
                results.append(f"\n📝 Editing file: {file_path}")
                edit_result = self._edit_file(file_path, old_string, new_string)
                if edit_result.get("success"):
                    results.append(f"   ✅ Made {edit_result.get('replacements')} replacement(s)")
                else:
                    results.append(f"   ❌ Error: {edit_result.get('error')}")

            elif action_type == "run_bash":
                command = params.get("command")
                results.append(f"\n💻 Running: {command}")
                bash_result = self._run_bash(
                    command,
                    cwd=params.get("cwd"),
                    timeout=params.get("timeout", 120)
                )
                if bash_result.get("success"):
                    stdout = bash_result.get("stdout", "")
                    if stdout:
                        results.append(f"   ✅ Output:\n{self._indent_output(stdout, 6)}")
                    else:
                        results.append(f"   ✅ Command completed")
                else:
                    stderr = bash_result.get("stderr", "")
                    error = bash_result.get("error")
                    if stderr:
                        results.append(f"   ❌ Error output:\n{self._indent_output(stderr, 6)}")
                    if error:
                        results.append(f"   ❌ Error: {error}")
            # === END CODE EXECUTION TOOLS ===

            elif action_type in ["update", "insert"]:
                results.append("\n" + "=" * 60)
                results.append("🔧 STEP 4: Executing Database Operations")
                results.append("=" * 60)

                if needs_update_ehr and existing_data.get("ehr_integrations"):
                    results.append(f"\n--- Updating ehr_integrations ---")
                    update_result = self._run_update_ehr_integration(
                        provider_id, npi
                    )
                    results.append(update_result.get("output", ""))
                    if update_result.get("success"):
                        results.append("✅ ehr_integrations: Updated")

                if needs_update_order and existing_data.get("order_clients"):
                    results.append(f"\n--- Updating order_clients ---")
                    update_result = self._run_update_order_client(
                        provider_id, customer_firstname, customer_lastname, npi, clinic_name
                    )
                    results.append(update_result.get("output", ""))
                    if update_result.get("success"):
                        results.append("✅ order_clients: Updated")

        results.append("\n" + "=" * 60)
        results.append("✅ Execution completed!")
        results.append("=" * 60)

        return {
            "success": True,
            "output": "\n".join(results),
        }

    def _run_grpc_call(self, provider_id: str | None) -> dict:
        """Run the gRPC call script."""
        if not provider_id:
            return {"success": False, "error": "No provider_id"}

        try:
            cmd = [
                "npx", "ts-node",
                str(self.repo_path / "scripts/get-customer-rpc.ts"),
                f"--provider-id={provider_id}"
            ]
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parse JSON output
                data = json.loads(result.stdout.strip())
                return {
                    "success": True,
                    "first_name": data.get("customer_first_name", ""),
                    "last_name": data.get("customer_last_name", ""),
                    "suffix": data.get("customer_suffix", ""),
                    "npi": data.get("customer_npi_number", ""),
                }
            else:
                return {"success": False, "error": result.stderr}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_get_existing_data(self, customer_id: str | None) -> dict:
        """Run the get-existing-data script."""
        if not customer_id:
            return {"success": False, "error": "No customer_id"}

        try:
            cmd = [
                "npx", "ts-node",
                str(self.repo_path / "scripts/get-existing-data-json.ts"),
                f"--customer-id={customer_id}"
            ]
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                data = json.loads(result.stdout.strip())
                return {"success": True, "data": data}
            else:
                return {"success": False, "error": result.stderr}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_update_ehr_integration(self, customer_id: str | None, npi: str | None) -> dict:
        """Run the update-ehr-integration script."""
        if not customer_id or not npi:
            return {"success": False, "error": "Missing params"}

        try:
            cmd = [
                "npx", "ts-node",
                str(self.repo_path / "scripts/update-ehr-integration.ts"),
                f"--customer-id={customer_id}",
                f"--npi={npi}"
            ]
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _read_file(self, file_path: str) -> dict:
        """Read a file and return its contents."""
        try:
            # Support both absolute and relative paths
            path = Path(file_path)
            if not path.is_absolute():
                path = self.repo_path / file_path

            if not path.exists():
                return {"success": False, "error": f"File not found: {path}"}

            content = path.read_text(encoding="utf-8")
            return {
                "success": True,
                "content": content,
                "path": str(path),
                "lines": len(content.splitlines())
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _write_file(self, file_path: str, content: str) -> dict:
        """
        Write content to a file.

        Guardrail: Only allows writing within the allowed repository path.
        """
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.repo_path / file_path

            # Guardrail: Only allow writing within the repo
            try:
                path.resolve().relative_to(self.repo_path.resolve())
            except ValueError:
                return {"success": False, "error": f"Access denied: {path} is outside allowed directory"}

            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            path.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "path": str(path),
                "bytes_written": len(content.encode("utf-8"))
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _edit_file(self, file_path: str, old_string: str, new_string: str) -> dict:
        """
        Edit a file by replacing old_string with new_string.

        Guardrail: Only allows editing within the allowed repository path.
        """
        try:
            # First read the file
            read_result = self._read_file(file_path)
            if not read_result.get("success"):
                return read_result

            content = read_result["content"]

            # Check if old_string exists
            if old_string not in content:
                return {
                    "success": False,
                    "error": f"old_string not found in file. "
                            f"It may have changed or the search string is incorrect."
                }

            # Replace
            new_content = content.replace(old_string, new_string)

            # Write back
            path = Path(read_result["path"])
            path.write_text(new_content, encoding="utf-8")

            return {
                "success": True,
                "path": str(path),
                "replacements": content.count(old_string)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_bash(self, command: str, cwd: str | None = None, timeout: int = 120) -> dict:
        """
        Execute a bash command.

        Guardrail: Commands run within the repository path by default.
        """
        try:
            work_dir = Path(cwd) if cwd else self.repo_path

            result = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_update_order_client(
        self, customer_id: str | None, first_name: str, last_name: str,
        npi: str | None, clinic_name: str
    ) -> dict:
        """Run the update-order-client script."""
        if not customer_id:
            return {"success": False, "error": "Missing customer_id"}

        try:
            full_name = f"{first_name} {last_name}".strip()
            cmd = [
                "npx", "ts-node",
                str(self.repo_path / "scripts/update-order-client.ts"),
                f"--customer-id={customer_id}",
                f"--customer-name={full_name}",
                f"--npi={npi or ''}",
            ]
            if clinic_name:
                cmd.append(f"--clinic-name={clinic_name}")

            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _indent_output(self, text: str, spaces: int) -> str:
        """Indent multi-line output for cleaner display."""
        indent = " " * spaces
        return "\\n".join(indent + line for line in text.splitlines())

