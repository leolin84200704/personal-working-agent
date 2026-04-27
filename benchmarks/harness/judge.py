"""Scoring for agent answers.

Implements stdlib-only string-overlap metrics (token F1, BLEU-1, ROUGE-L)
and an LLM-as-judge that shells out to ``claude -p`` (no Anthropic SDK
needed; the Claude Code CLI handles auth).

Interface (stable):
    judge = Judge(llm_judge_enabled=True, llm_judge_model="claude-sonnet-4-6")
    scores = judge.score(question, expected, actual, category)
    # -> {"f1": float, "bleu1": float, "rougeL": float,
    #     "llm_judge": None|dict, "llm_judge_score": int|None,
    #     "llm_judge_raw": str}
"""
from __future__ import annotations

import math
import re
import shutil
import string
import subprocess
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


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


_JUDGE_PROMPT_TEMPLATE = """You are an answer-correctness judge for a question-answering benchmark.

Given a QUESTION, the GROUND_TRUTH answer, and a CANDIDATE answer produced by a memory system, decide whether the candidate is correct.

Scoring rubric (3-point):
- 2 (correct): candidate conveys the same factual answer as ground truth. Paraphrasing, capitalization, and minor formatting differences are acceptable. Numeric/date values must be the same.
- 1 (partial): candidate captures part of the ground truth but is incomplete, or includes a minor error (e.g., right entity wrong year, right action wrong subject).
- 0 (wrong): candidate is incorrect, off-topic, or admits inability ("unknown", "not in memory") when the ground truth is in fact provided.

Output STRICTLY one line, no preamble, no explanation:
SCORE: <0|1|2>

QUESTION: {question}
GROUND_TRUTH: {expected}
CANDIDATE: {actual}"""


_SCORE_RE = re.compile(r"^SCORE:\s*([012])", re.MULTILINE)


class Judge:
    """Score agent answers.

    LLM judge runs ``claude -p`` as a subprocess — no Anthropic SDK
    dependency. Disabled by default; enable with ``llm_judge_enabled=True``.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        llm_model: str = "claude-opus-4-6",
        llm_judge_enabled: bool = False,
        llm_judge_model: str = "claude-sonnet-4-6",
        llm_judge_timeout: int = 30,
    ):
        # ``llm_client`` is kept for backwards compatibility (older runner
        # callers passed a stub). It is unused by the CLI-based judge.
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.llm_judge_enabled = llm_judge_enabled
        self.llm_judge_model = llm_judge_model
        self.llm_judge_timeout = llm_judge_timeout
        self.llm_judge_calls = 0
        self.llm_judge_failures = 0

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
            "llm_judge_score": None,
            "llm_judge_raw": "",
        }

        if self.llm_judge_enabled:
            verdict = self._llm_judge(question, expected, actual, category)
            scores["llm_judge"] = verdict
            scores["llm_judge_score"] = verdict.get("score")
            scores["llm_judge_raw"] = verdict.get("raw", "")[:200]

        return scores

    # ------------------------------------------------------------------
    # LLM judge — claude -p subprocess
    # ------------------------------------------------------------------

    def _llm_judge(
        self,
        question: str,
        expected: str,
        actual: str,
        category: str,
    ) -> Dict[str, Any]:
        """Score one (question, expected, actual) tuple via ``claude -p``.

        Returns ``{"score": 0|1|2|None, "raw": str, "rationale": str|None}``.
        Never raises — failures fall back to ``score=None`` so the runner
        can keep going.
        """
        self.llm_judge_calls += 1
        cli_path = shutil.which("claude")
        if not cli_path:
            self.llm_judge_failures += 1
            return {"score": None, "raw": "", "rationale": "cli_not_found"}

        prompt = _JUDGE_PROMPT_TEMPLATE.format(
            question=str(question or "").strip(),
            expected=str(expected or "").strip(),
            actual=str(actual or "").strip(),
        )

        try:
            completed = subprocess.run(
                [cli_path, "-p", prompt, "--model", self.llm_judge_model],
                capture_output=True,
                text=True,
                timeout=self.llm_judge_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.llm_judge_failures += 1
            return {"score": None, "raw": "", "rationale": "cli_failure: timeout"}
        except Exception as e:  # pragma: no cover - unexpected
            self.llm_judge_failures += 1
            return {"score": None, "raw": "", "rationale": f"cli_failure: {e!r}"}

        if completed.returncode != 0:
            self.llm_judge_failures += 1
            stderr_tail = (completed.stderr or "").strip().splitlines()[-3:]
            return {
                "score": None,
                "raw": (completed.stdout or "")[:200],
                "rationale": f"cli_failure: exit {completed.returncode} {' | '.join(stderr_tail)}",
            }

        raw = (completed.stdout or "").strip()
        score, rationale = _parse_judge_output(raw)
        if score is None:
            # Parsing failure isn't a CLI failure — distinguish in metrics.
            self.llm_judge_failures += 1
        return {"score": score, "raw": raw, "rationale": rationale}


def _parse_judge_output(raw: str) -> Tuple[Optional[int], Optional[str]]:
    """Extract the SCORE line. Returns (score, rationale_or_None)."""
    if not raw:
        return None, "parse_error: empty"
    m = _SCORE_RE.search(raw)
    if not m:
        return None, f"parse_error: {raw[:80]}"
    try:
        return int(m.group(1)), None
    except ValueError:
        return None, f"parse_error: {raw[:80]}"


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-record scores into overall + per-category stats.

    Includes LLM judge metrics when at least one record has an
    ``llm_judge_score`` field. Records without that key are treated as
    string-only and contribute 0 to LLM judge counters (i.e. the means
    are computed only over records that *attempted* LLM scoring).

    Returns a dict like::

        {
          "overall": {"n": 123, "f1": 0.42, "bleu1": 0.18, "rougeL": 0.35,
                      "llm_judge_n": 123, "llm_judge_mean": 0.55,
                      "llm_judge_correct_pct": 0.45,
                      "llm_judge_partial_pct": 0.20,
                      "llm_judge_wrong_pct": 0.30,
                      "llm_judge_failed_pct": 0.05},
          "by_category": {...}
        }
    """
    def _avg(xs: List[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    def _llm_score(r: Dict[str, Any]) -> Any:
        s = r.get("scores", {}) or {}
        # Direct field (preferred shape from re_judge / new Judge).
        if "llm_judge_score" in s:
            return s["llm_judge_score"]
        # Fallback: nested dict {"score": ...}.
        verdict = s.get("llm_judge")
        if isinstance(verdict, dict):
            return verdict.get("score")
        return None

    def _collect(bucket: List[Dict[str, Any]]) -> Dict[str, float]:
        out: Dict[str, Any] = {
            "n": len(bucket),
            "f1": round(_avg([r["scores"]["f1"] for r in bucket]), 4),
            "bleu1": round(_avg([r["scores"]["bleu1"] for r in bucket]), 4),
            "rougeL": round(_avg([r["scores"]["rougeL"] for r in bucket]), 4),
        }

        # Records that went through (or attempted) the LLM judge. We count
        # over the full attempted set so failed CLI calls show up as a
        # ``failed_pct`` rather than silently shrinking the denominator.
        attempted_records = [r for r in bucket if _has_llm_attempt(r)]
        if attempted_records:
            scores_seen = [_llm_score(r) for r in attempted_records]
            valid = [s for s in scores_seen if s is not None]
            n_total = len(attempted_records)
            failed_count = n_total - len(valid)
            correct = sum(1 for s in valid if s == 2)
            partial = sum(1 for s in valid if s == 1)
            wrong = sum(1 for s in valid if s == 0)
            mean = (sum(valid) / len(valid) / 2.0) if valid else 0.0
            out["llm_judge_n"] = n_total
            out["llm_judge_mean"] = round(mean, 4)
            out["llm_judge_correct_pct"] = round(correct / n_total, 4)
            out["llm_judge_partial_pct"] = round(partial / n_total, 4)
            out["llm_judge_wrong_pct"] = round(wrong / n_total, 4)
            out["llm_judge_failed_pct"] = round(failed_count / n_total, 4)
        return out

    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        cat = r.get("category", "unknown")
        buckets.setdefault(cat, []).append(r)

    return {
        "overall": _collect(records),
        "by_category": {k: _collect(v) for k, v in sorted(buckets.items())},
    }


def _has_llm_attempt(record: Dict[str, Any]) -> bool:
    """True iff this record went through (or was meant to go through) LLM judge."""
    s = record.get("scores", {}) or {}
    if "llm_judge_score" in s or "llm_judge_raw" in s:
        return True
    verdict = s.get("llm_judge")
    return isinstance(verdict, dict)
