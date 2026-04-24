"""Scoring for agent answers.

Implements stdlib-only string-overlap metrics (token F1, BLEU-1, ROUGE-L)
and leaves an interface stub for an LLM-as-judge. The Anthropic API call
is intentionally not wired up here: it needs an API key and a design
decision from Leo on which model and rubric to use.

Interface (stable):
    judge = Judge()
    scores = judge.score(question, expected, actual, category)
    # -> {"f1": float, "bleu1": float, "rougeL": float, "llm_judge": None|dict}
"""
from __future__ import annotations

import math
import re
import string
from collections import Counter
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation + articles + extra whitespace.

    Matches the SQuAD-style normalisation so F1 numbers are comparable to
    published dialogue-QA benchmarks.
    """
    if text is None:
        return ""
    text = str(text).lower()
    text = text.translate(_PUNCT_TABLE)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(text: str) -> List[str]:
    return _normalise(text).split()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def token_f1(expected: str, actual: str) -> float:
    """SQuAD-style token-overlap F1."""
    exp_tokens = _tokens(expected)
    act_tokens = _tokens(actual)
    if not exp_tokens and not act_tokens:
        return 1.0
    if not exp_tokens or not act_tokens:
        return 0.0
    common = Counter(exp_tokens) & Counter(act_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(act_tokens)
    recall = num_same / len(exp_tokens)
    return 2 * precision * recall / (precision + recall)


def bleu1(expected: str, actual: str) -> float:
    """Unigram BLEU with brevity penalty.

    Only BLEU-1 because LoCoMo answers are typically short; higher-order
    n-grams sparsify rapidly and add noise without insight.
    """
    exp_tokens = _tokens(expected)
    act_tokens = _tokens(actual)
    if not exp_tokens or not act_tokens:
        return 0.0

    act_counts = Counter(act_tokens)
    ref_counts = Counter(exp_tokens)
    clipped = sum(min(c, ref_counts.get(tok, 0)) for tok, c in act_counts.items())
    precision = clipped / len(act_tokens) if act_tokens else 0.0
    if precision == 0.0:
        return 0.0

    # Brevity penalty
    ref_len = len(exp_tokens)
    act_len = len(act_tokens)
    if act_len > ref_len:
        bp = 1.0
    else:
        bp = math.exp(1 - ref_len / act_len) if act_len > 0 else 0.0
    return bp * precision


def rouge_l(expected: str, actual: str) -> float:
    """ROUGE-L F1 based on longest-common-subsequence length."""
    exp_tokens = _tokens(expected)
    act_tokens = _tokens(actual)
    if not exp_tokens or not act_tokens:
        return 0.0

    # Standard LCS DP.
    m, n = len(exp_tokens), len(act_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        ei = exp_tokens[i - 1]
        row = dp[i]
        prev_row = dp[i - 1]
        for j in range(1, n + 1):
            if ei == act_tokens[j - 1]:
                row[j] = prev_row[j - 1] + 1
            else:
                row[j] = prev_row[j] if prev_row[j] >= row[j - 1] else row[j - 1]
    lcs = dp[m][n]
    if lcs == 0:
        return 0.0
    precision = lcs / n
    recall = lcs / m
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------


class Judge:
    """Score agent answers.

    ``llm_client`` is intentionally untyped for now — when we wire up
    Anthropic, the object must expose a ``.messages.create(...)`` call
    that returns the judge verdict as JSON-parseable text.
    """

    def __init__(self, llm_client: Optional[Any] = None, llm_model: str = "claude-opus-4-6"):
        self.llm_client = llm_client
        self.llm_model = llm_model

    def score(
        self,
        question: str,
        expected: str,
        actual: str,
        category: str = "unknown",
    ) -> Dict[str, Any]:
        scores: Dict[str, Any] = {
            "f1": round(token_f1(expected, actual), 4),
            "bleu1": round(bleu1(expected, actual), 4),
            "rougeL": round(rouge_l(expected, actual), 4),
            "llm_judge": None,
        }

        if self.llm_client is not None:
            try:
                scores["llm_judge"] = self._llm_judge(
                    question, expected, actual, category
                )
            except Exception as e:  # pragma: no cover - network path
                scores["llm_judge"] = {"error": str(e)}

        return scores

    # ------------------------------------------------------------------
    # LLM judge (stub)
    # ------------------------------------------------------------------

    def _llm_judge(
        self,
        question: str,
        expected: str,
        actual: str,
        category: str,
    ) -> Dict[str, Any]:
        """LLM-as-judge — NOT IMPLEMENTED.

        # TODO: wire up Anthropic messages API.
        # Planned rubric: 3-point scale (correct / partially correct / wrong)
        # plus a short rationale. Input temperature 0, max tokens 256.
        # See docs/auto-dream-architecture.md for the preferred prompt style.
        """
        raise NotImplementedError(
            "LLM judge is stubbed. Provide an llm_client and implement the "
            "Anthropic call here before enabling."
        )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-record scores into overall + per-category stats.

    ``records`` is the list emitted by ``runner.py``.
    Returns a dict like::

        {
          "overall": {"n": 123, "f1": 0.42, "bleu1": 0.18, "rougeL": 0.35},
          "by_category": {"temporal": {...}, "multi_hop": {...}}
        }
    """
    def _avg(xs: List[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    def _collect(bucket: List[Dict[str, Any]]) -> Dict[str, float]:
        return {
            "n": len(bucket),
            "f1": round(_avg([r["scores"]["f1"] for r in bucket]), 4),
            "bleu1": round(_avg([r["scores"]["bleu1"] for r in bucket]), 4),
            "rougeL": round(_avg([r["scores"]["rougeL"] for r in bucket]), 4),
        }

    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        cat = r.get("category", "unknown")
        buckets.setdefault(cat, []).append(r)

    return {
        "overall": _collect(records),
        "by_category": {k: _collect(v) for k, v in sorted(buckets.items())},
    }
