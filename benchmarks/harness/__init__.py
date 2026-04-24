"""LoCoMo benchmark harness for lis-code-agent memory system.

This package provides:
- adapter.py: Convert LoCoMo conversations into lis-code-agent memory injection
- runner.py: Execute a benchmark run against a configured agent version
- judge.py: Score agent answers against gold answers (string + LLM-as-judge)
- compare.py: Diff two result JSON files and produce a markdown report
"""
