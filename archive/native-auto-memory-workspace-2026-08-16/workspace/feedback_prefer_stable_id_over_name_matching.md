---
name: feedback_prefer_stable_id_over_name_matching
description: "When a design matches/joins on a human name (display string) but a stable unique id exists, proactively flag id-matching as the better option"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5b5b0197-b599-4d76-8957-2b30c8e33459
---

When implementing matching/lookup/join logic, if the design keys on a **human-readable name / display string** but a **stable unique id** is also available, proactively tell Leo that id-based matching is better and recommend it — don't just implement the name-based version.

**Why:** name matching is fragile (casing, whitespace, punctuation, duplicates/collisions, renames). VP-17076 first matched shortcuts by `shortcut_name` (needed normalization + an is_practice filter to dodge personal-vs-practice name collisions); VP-17136 switched to matching by `shortcut_id` (`VASC{id}`) → unique, deterministic, collision-free, no normalization. Leo asked to be reminded whenever this kind of name-vs-id choice comes up.

**How to apply:** during design/review of any matching code, scan for name/string keys; if a stable id exists in the same payload/table, surface "id matching is more robust here because X" as an explicit recommendation before/while implementing. Related: [[project_emr_shortcut_sync]].
