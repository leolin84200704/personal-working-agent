#!/usr/bin/env python3
"""Download the LoCoMo dataset from the official SNAP Research GitHub repo.

LoCoMo (Long Conversation Memory) is a benchmark for evaluating long-term
memory in conversational agents. It contains multi-session dialogues (~300
turns each) paired with QA items covering temporal, single-hop, multi-hop,
and open-domain reasoning.

Source:  https://github.com/snap-research/locomo
License: see the upstream repo. Redistribution of the data file itself is
         not done here; this script fetches it at runtime.

Usage:
    python benchmarks/datasets/download_locomo.py
    python benchmarks/datasets/download_locomo.py --dest benchmarks/datasets/locomo

The downloaded JSON is written to the destination directory and is excluded
from git via ``.gitignore`` (see ``benchmarks/datasets/locomo/*.json``).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Canonical raw URL for the main LoCoMo data file.
# NOTE: The upstream repo publishes the data under data/locomo10.json; if
# the filename changes upstream, update LOCOMO_FILES below.
LOCOMO_RAW_BASE = "https://raw.githubusercontent.com/snap-research/locomo/main"

LOCOMO_FILES = [
    # (relative path in upstream repo, local filename)
    ("data/locomo10.json", "locomo10.json"),
]

DEFAULT_DEST = Path(__file__).parent / "locomo"


def _download(url: str, dest: Path) -> int:
    """Download *url* to *dest*. Returns number of bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f"HTTP {e.code} fetching {url}. Check upstream repo for filename changes."
        ) from e
    except urllib.error.URLError as e:
        raise SystemExit(f"Network error fetching {url}: {e.reason}") from e
    dest.write_bytes(data)
    return len(data)


def _sanity_check(path: Path) -> dict:
    """Load JSON and report shallow structure for sanity."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    info: dict = {"path": str(path), "size_bytes": path.stat().st_size}
    if isinstance(data, list):
        info["type"] = "list"
        info["n_samples"] = len(data)
        if data and isinstance(data[0], dict):
            info["sample_keys"] = sorted(data[0].keys())
    elif isinstance(data, dict):
        info["type"] = "dict"
        info["top_keys"] = sorted(data.keys())[:20]
    info["sha256_12"] = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help="Destination directory (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the file already exists.",
    )
    args = parser.parse_args()

    dest_dir: Path = args.dest
    dest_dir.mkdir(parents=True, exist_ok=True)

    any_downloaded = False
    for rel_path, local_name in LOCOMO_FILES:
        url = f"{LOCOMO_RAW_BASE}/{rel_path}"
        out = dest_dir / local_name
        if out.exists() and not args.force:
            print(f"[skip] {out} already exists (use --force to re-download).")
        else:
            print(f"[get ] {url}")
            size = _download(url, out)
            print(f"[ok  ] Wrote {size:,} bytes to {out}")
            any_downloaded = True

        info = _sanity_check(out)
        print(f"[info] {json.dumps(info, indent=2, ensure_ascii=False)}")

    if not any_downloaded:
        print("Nothing new downloaded. Use --force to refresh.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
