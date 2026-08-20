#!/usr/bin/env python3
"""Regression test for scripts/extract-failures.py.

Bug (2026-08-18, and 2026-07-29 before it): the script rebuilt failures.md from
STM alone. Three things the file holds are not derivable from STM, and all three
were destroyed on every run:

  - `score`, computed by memory_scoring.py, was hardcoded back to 0.0
  - `created` was reset to today, so the file always looked newborn
  - `links` was rebuilt from the tickets currently in STM, dropping every link the
    auto-linker had added (49 of 90 on 2026-08-18, 129 lines on 2026-07-29)

And an entry whose STM has been archived has no source left to re-render, so a
from-scratch write deleted it silently. VP-16720 lived in no STM and no journal —
only in this file.

Run: python3 scripts/tests/extract-failures-preserves.test.py
"""

import importlib.util
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("ef", ROOT / "scripts" / "extract-failures.py")
ef = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ef)

fails = []


def check(label, got, want):
    if got != want:
        fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"[FAIL] {label}: got {got!r}, want {want!r}")
    else:
        print(f"[ok  ] {label}")


EXISTING = """---
id: failures
type: ltm
score: 1.2452
base_weight: 0.9
created: 2026-05-01
updated: 2026-08-16
links:
- INCIDENT-20260518
- QH-1104
- VP-16720
tags:
- failures
---

# Failure Index

## Other <a id='other'></a>

### **[[VP-16720]]** — `2026-06-01` — archived STM, no source left

body text
"""

with tempfile.TemporaryDirectory() as tmp:
    path = pathlib.Path(tmp) / "failures.md"
    path.write_text(EXISTING, encoding="utf-8")
    prior = ef.read_existing(path)

    check("reads score off disk", prior["score"], "1.2452")
    check("reads created off disk", prior["created"], "2026-05-01")
    check("reads every link", sorted(prior["links"]), ["INCIDENT-20260518", "QH-1104", "VP-16720"])
    check("reads entry ids", prior["entry_ids"], {"VP-16720"})

    # A render that knows about one new ticket and nothing about the archived one.
    grouped = {("other", "Other / uncategorized"): [
        {"ticket": "VP-17748", "date": "2026-08-18", "title": "new one", "body": "body"},
    ]}
    out = ef.render(grouped, prior)

    links = []
    in_links = False
    for line in out.splitlines():
        if line.startswith("links:"):
            in_links = True
        elif in_links:
            if line.startswith("- "):
                links.append(line[2:])
            else:
                break

    check("score is carried over, not zeroed", "score: 1.2452" in out, True)
    check("created is carried over, not today", "created: 2026-05-01" in out, True)
    check("links are unioned, not rebuilt", sorted(links),
          ["INCIDENT-20260518", "QH-1104", "VP-16720", "VP-17748"])

    dropped = sorted(prior["entry_ids"] - set(ef.ENTRY_ID_RE.findall(out)))
    check("an entry with no STM source is detected as unrenderable", dropped, ["VP-16720"])

    # ...and is carried over rather than refused. Refusing would have been worse
    # than useless: an orphan stays an orphan, so every later run would refuse
    # too, and the only escape would be --prune — deleting the very thing the
    # check exists to protect.
    carried = ef.orphan_entries(path, {"VP-17748"})
    carried_ids = sorted(e["ticket"] for entries in carried.values() for e in entries)
    check("the orphan is recovered from the file itself", carried_ids, ["VP-16720"])
    section = list(carried.keys())[0]
    check("it keeps its section", section, ("other", "Other"))
    check("it keeps its body", "body text" in carried[section][0]["body"], True)
    check("it keeps its date", carried[section][0]["date"], "2026-06-01")

    merged = dict(grouped)
    for key, entries in carried.items():
        merged.setdefault(key, []).extend(entries)
    out2 = ef.render(merged, prior)
    check("a carried entry survives the next render",
          sorted(ef.ENTRY_ID_RE.findall(out2)), ["VP-16720", "VP-17748"])
    check("nothing is left to drop once orphans are carried",
          sorted(prior["entry_ids"] - set(ef.ENTRY_ID_RE.findall(out2))), [])

    check("an entry the scan DID produce is not treated as an orphan",
          ef.orphan_entries(path, {"VP-16720"}), {})

    # No prior file: the first run must still work.
    fresh = ef.render(grouped, ef.read_existing(pathlib.Path(tmp) / "absent.md"))
    check("first run without a prior file still renders", "score: 0.0" in fresh, True)

print()
if fails:
    print(f"{len(fails)} FAILED")
    sys.exit(1)
print("all passed")
