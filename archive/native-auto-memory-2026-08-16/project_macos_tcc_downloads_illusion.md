---
name: macos-tcc-downloads-illusion
description: ls/glob/find/mdfind failing on ~/Downloads ≠ file gone — macOS TCC blocks directory LISTING but direct full-path stat/cp still works
metadata: 
  node_type: memory
  type: project
  originSessionId: 74a86038-7535-40be-9695-7c312bed462a
  modified: 2026-07-23T23:59:47.458Z
---

macOS TCC can deny directory enumeration of ~/Downloads (`ls: Operation not permitted`, zsh glob "no matches", find/mdfind silent misses) while still allowing direct access to a known full path (`stat`/`cp ~/Downloads/exact-name` succeed).

**Why:** 2026-07-23 BioInsights SFTP retest: concluded `bioinsights_key.ppk` was moved/deleted after ls/find/mdfind all missed it; 20+ minutes of searching later, `stat` on the exact remembered path proved it was there all along.

**How to apply:** when a file under ~/Downloads (or Desktop/Documents) "disappears", FIRST stat the exact remembered full path before searching elsewhere or concluding it was moved. `osascript` System Events can also list when shell cannot.
