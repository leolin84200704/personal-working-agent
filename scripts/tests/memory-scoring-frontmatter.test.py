#!/usr/bin/env python3
"""Regression test for scripts/memory_scoring.py write_frontmatter().

Bug (found by the 2026-07-31 dream run): write_frontmatter kept the newline that
terminates the closing '---' line as part of `body`, then re-emitted '---\\n' + body.
Every write therefore inserted one more blank line between the frontmatter and the
body. The scoring script writes twice per run (auto-link pass + rescore pass), so
STM/LTM files grew ~2 blank lines every night — LBS-1541.md had reached 106, and the
growth was unbounded.

Run: python3 scripts/tests/memory-scoring-frontmatter.test.py
"""

import importlib.util
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("ms", ROOT / "scripts" / "memory_scoring.py")
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)


def blanks_after_frontmatter(text: str) -> int:
    lines = text.split("\n")
    delims = [i for i, l in enumerate(lines) if l.strip() == "---"]
    assert len(delims) >= 2, "frontmatter delimiters missing"
    count = 0
    for line in lines[delims[1] + 1:]:
        if line.strip() == "":
            count += 1
        else:
            break
    return count


def check(name: str, initial: str, writes: int = 4) -> bool:
    path = pathlib.Path(tempfile.mkdtemp()) / "t.md"
    path.write_text(initial, encoding="utf-8")
    counts = []
    for i in range(writes):
        meta = ms.read_frontmatter(path)
        meta["score"] = i  # simulate a rescore
        ms.write_frontmatter(path, meta)
        counts.append(blanks_after_frontmatter(path.read_text(encoding="utf-8")))

    final = path.read_text(encoding="utf-8")
    stable = len(set(counts)) == 1
    exactly_one = counts[-1] == 1
    body_kept = "# Heading" in final and "body text" in final
    meta_kept = ms.read_frontmatter(path).get("id") == "X"
    ok = stable and exactly_one and body_kept and meta_kept
    print(
        f"{'PASS' if ok else 'FAIL'} {name}: blanks_per_write={counts} "
        f"stable={stable} exactly_one={exactly_one} body_kept={body_kept} meta_kept={meta_kept}"
    )
    return ok


HEAD = "---\nid: X\nscore: 0\n---\n"
BODY = "# Heading\n\nbody text\n"

cases = [
    ("clean file", HEAD + "\n" + BODY),
    ("no blank separator", HEAD + BODY),
    ("already polluted (40 blanks)", HEAD + "\n" * 40 + BODY),
    ("polluted (3 blanks)", HEAD + "\n\n\n" + BODY),
    ("no frontmatter at all", BODY),
]

results = []
for name, initial in cases:
    if name == "no frontmatter at all":
        # read_frontmatter returns {} here; write must still not corrupt the body
        path = pathlib.Path(tempfile.mkdtemp()) / "t.md"
        path.write_text(initial, encoding="utf-8")
        ms.write_frontmatter(path, {"id": "X", "score": 1})
        first = path.read_text(encoding="utf-8")
        ms.write_frontmatter(path, ms.read_frontmatter(path))
        second = path.read_text(encoding="utf-8")
        ok = (
            blanks_after_frontmatter(first) == 1
            and blanks_after_frontmatter(second) == 1
            and "# Heading" in second
        )
        print(f"{'PASS' if ok else 'FAIL'} {name}: idempotent={first == second}")
        results.append(ok)
        continue
    results.append(check(name, initial))

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
