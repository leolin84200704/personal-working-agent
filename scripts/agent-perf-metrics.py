#!/usr/bin/env python3
"""Longitudinal throughput metrics for this instance, read from Claude Code transcripts.

Answers "did a framework change make the agent slower?" with per-turn numbers rather
than impressions. Wall-clock per session is useless (idle time dominates), so the unit
is the user turn: from a user message to the last agent event before the next one.

Usage:
    python3 scripts/agent-perf-metrics.py 2026-07-20:2026-08-05 2026-08-15:2026-08-31
    python3 scripts/agent-perf-metrics.py --weekly          # every ISO week, last 90d

Scheduled jobs (dream / hl7 triage) are reported separately from interactive work, and
sessions whose first real prompt is about the agent itself are tagged FACTORY so that
self-maintenance does not get counted as ticket throughput.
"""
import collections
import datetime
import glob
import json
import os
import re
import statistics as st
import sys

TRANSCRIPTS = os.path.expanduser(
    "~/.claude/projects/-Users-hung-l-src-vibrant-america-working-agent"
)
AUTOMATED_PREFIXES = ("You are the LIS Code Agent's dreaming", "## hl7_file_input")
FACTORY_RE = re.compile(
    r"factory|framework|dream|memory|STM|LTM|hook|lesson|wave|instance|CLAUDE\.md|skill", re.I
)
# Bash command categories: everything the disciplines add, plus the residue that is
# actual product work.
CATEGORIES = [
    ("git-sync", r"git (fetch|pull|remote -v|rev-list|branch -vv)|origin/(main|master)"),
    ("git-other", r"\bgit "),
    ("memory-idx", r"_index\.md|short_term_memory|long-term-memory|journal/"),
    ("framework", r"project-agent-factory|framework/|WORK-LOOP|ENGINEERING-LESSONS|RETRIEVAL|BOOTSTRAP|AGENTS\.md"),
    ("skills", r"\.claude/skills|SKILL\.md"),
    ("gh", r"\bgh (pr|issue|api|run)"),
]
GUARD_RE = re.compile(
    r"PreToolUse:.*hook|PAUSED \(once per session\)|blocked by hook|"
    r"protect-verification-assets|validate-repo-language|validate-git-push"
)


def parse_ts(value):
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_turns():
    """One record per user turn, with the agent activity that followed it."""
    turns = []
    for path in glob.glob(os.path.join(TRANSCRIPTS, "*.jsonl")):
        events = []
        with open(path, errors="replace") as handle:
            for line in handle:
                if not line.startswith("{"):
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("timestamp"):
                    events.append(event)
        events.sort(key=lambda e: e["timestamp"])
        current = None
        for event in events:
            kind = event.get("type")
            message = event.get("message") or {}
            content = message.get("content")
            if kind == "user":
                is_result = isinstance(content, list) and any(
                    isinstance(c, dict) and c.get("type") == "tool_result" for c in content
                )
                if not is_result:
                    if current:
                        turns.append(current)
                    text = content if isinstance(content, str) else " ".join(
                        c.get("text", "") for c in content or [] if isinstance(c, dict)
                    )
                    current = {
                        "session": os.path.basename(path),
                        "start": parse_ts(event["timestamp"]),
                        "end": parse_ts(event["timestamp"]),
                        "prompt": text,
                        "tools": 0,
                        "steps": 0,
                        "output": 0,
                        "context": [],
                        "bash": [],
                        "guard_hits": 0,
                        "tool_results": 0,
                        "models": collections.Counter(),
                    }
                    continue
            if current is None:
                continue
            if kind == "assistant":
                # Turn ends at the last agent/tool event, not at trailing system
                # events -- those can land minutes later and inflate the duration.
                current["end"] = parse_ts(event["timestamp"])
                current["steps"] += 1
                usage = message.get("usage") or {}
                current["output"] += usage.get("output_tokens", 0)
                total_in = (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                )
                if total_in:
                    current["context"].append(total_in)
                model = message.get("model", "?")
                if not model.startswith("<"):
                    current["models"][model] += 1
                for block in content if isinstance(content, list) else []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        current["tools"] += 1
                        if block.get("name") == "Bash":
                            current["bash"].append((block.get("input") or {}).get("command", ""))
            elif kind == "user":
                current["end"] = parse_ts(event["timestamp"])
                for block in content if isinstance(content, list) else []:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        current["tool_results"] += 1
                        if GUARD_RE.search(json.dumps(block.get("content"), ensure_ascii=False)[:4000]):
                            current["guard_hits"] += 1
        if current:
            turns.append(current)
    for turn in turns:
        turn["duration"] = (turn["end"] - turn["start"]).total_seconds()
        turn["automated"] = turn["prompt"].startswith(AUTOMATED_PREFIXES)
    return turns


def classify_sessions(turns):
    """FACTORY when the session's first real prompt is about the agent itself."""
    first_prompt = {}
    for turn in sorted(turns, key=lambda t: t["start"]):
        prompt = turn["prompt"]
        if turn["session"] in first_prompt or turn["automated"]:
            continue
        if len(prompt) > 15 and not prompt.startswith(("<command", "<local-command")):
            first_prompt[turn["session"]] = prompt
    return {
        session: "FACTORY" if FACTORY_RE.search(prompt[:150]) else "LIS"
        for session, prompt in first_prompt.items()
    }


def report(label, turns, kinds):
    substantive = [t for t in turns if not t["automated"] and t["tools"] >= 3]
    if not substantive:
        print(f"{label:24} (no substantive turns)")
        return
    lis = [t for t in substantive if kinds.get(t["session"]) == "LIS"]
    durations = sorted(t["duration"] for t in substantive)
    bash = [cmd for t in substantive for cmd in t["bash"]]
    counts = collections.Counter()
    for cmd in bash:
        for name, pattern in CATEGORIES:
            if re.search(pattern, cmd):
                counts[name] += 1
                break
        else:
            counts["product-work"] += 1
    results = sum(t["tool_results"] for t in substantive) or 1
    guards = sum(t["guard_hits"] for t in substantive)
    models = collections.Counter()
    for t in substantive:
        models.update(t["models"])
    top_model = models.most_common(1)[0] if models else ("-", 0)
    print(
        f"{label:24} turns={len(substantive):4} (LIS {len(lis):3})"
        f"  tools/turn={st.median([t['tools'] for t in substantive]):5.1f}"
        f"  dur_med={st.median(durations):6.0f}s  dur_p75={durations[int(len(durations) * 0.75)]:6.0f}s"
        f"  out/turn={st.median([t['output'] for t in substantive]):7.0f}"
    )
    total_bash = len(bash) or 1
    shares = "  ".join(
        f"{name}={counts[name] / total_bash * 100:.1f}%"
        for name in ("git-sync", "framework", "memory-idx", "product-work")
    )
    print(
        f"{'':24} bash={total_bash:5}  {shares}"
        f"  guard_blocks={guards / results * 1000:.1f}/1k"
        f"  model={top_model[0]} {top_model[1] / max(sum(models.values()), 1) * 100:.0f}%"
    )


def main():
    turns = load_turns()
    kinds = classify_sessions(turns)
    windows = []
    if "--weekly" in sys.argv:
        cutoff = max(t["start"] for t in turns) - datetime.timedelta(days=90)
        weeks = sorted({t["start"].strftime("%G-W%V") for t in turns if t["start"] >= cutoff})
        windows = [(week, lambda t, w=week: t["start"].strftime("%G-W%V") == w) for week in weeks]
    else:
        for arg in sys.argv[1:]:
            if ":" not in arg:
                continue
            start, end = arg.split(":", 1)
            windows.append(
                (f"{start}..{end}", lambda t, s=start, e=end: s <= t["start"].strftime("%Y-%m-%d") <= e)
            )
    if not windows:
        print(__doc__)
        return
    print("Substantive turns = interactive, >=3 tool calls. Scheduled jobs excluded.\n")
    for label, predicate in windows:
        report(label, [t for t in turns if predicate(t)], kinds)


if __name__ == "__main__":
    main()
