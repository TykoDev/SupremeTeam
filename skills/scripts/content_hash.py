#!/usr/bin/env python3
"""Print the catalog's canonical sha256 for one or more files.

    python skills/scripts/content_hash.py <path> [<path> ...] [--project-root .]

This is the hash every gate, save checkpoint, and typed record expects: text is
folded to LF before hashing and binary is hashed byte-for-byte
(``data_formats.normalize_line_endings``), so the value is the same on an LF
and a CRLF checkout. ``sha256sum`` or ``Get-FileHash`` on a CRLF working tree
gives a different digest for the same text and fails the gate; use this instead.

Exit 0 with ``{"ok": true, "hashes": {<path>: <sha256>}}``; exit 1 with the
first unreadable path named.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from data_formats import content_sha256  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical, line-ending-agnostic sha256 of files.")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--project-root", default=".", help="paths in the output are made relative to this root when possible")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    hashes: dict[str, str] = {}
    for raw in args.paths:
        path = Path(raw)
        try:
            digest = content_sha256(path)
        except OSError as exc:
            print(json.dumps({"ok": False, "error": f"cannot read {raw}: {exc}"}))
            return 1
        try:
            label = path.resolve().relative_to(root).as_posix()
        except ValueError:
            label = path.as_posix()
        hashes[label] = digest
    print(json.dumps({"ok": True, "hashes": hashes}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
