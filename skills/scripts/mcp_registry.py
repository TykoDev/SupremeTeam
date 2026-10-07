#!/usr/bin/env python3
"""Read-only MCP cache freshness diagnostic; never asserts live availability."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from data_formats import parse_yaml


def inspect_registry(path: Path, *, host: str, workspace: Path, now: datetime | None = None) -> dict:
    """A blank shipped template is undiscovered, not a reason to pause intake."""
    result = {"path": str(path), "status": "undiscovered", "refresh_required": True,
              "intake_blocked": False, "live_availability_verified": False}
    if not path.exists():
        return {**result, "reason": "no workspace cache"}
    try:
        text = path.read_text(encoding="utf-8-sig")
        pieces = text.split("---", 2)
        if len(pieces) != 3 or pieces[0].strip():
            raise ValueError("registry needs frontmatter")
        meta = parse_yaml(pieces[1])
        if not isinstance(meta, dict):
            raise ValueError("registry metadata must be a mapping")
        ttl = meta.get("discovery_ttl_hours")
        if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or not 0 < ttl < float("inf"):
            raise ValueError("discovery_ttl_hours must be finite and positive")
        stamp = str(meta.get("last_discovery_at", ""))
        discovered = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if discovered.tzinfo is None:
            raise ValueError("discovery timestamp needs a timezone")
        if stamp == "1970-01-01T00:00:00Z" and not meta.get("host") and not meta.get("workspace"):
            return {**result, "reason": "blank template, not a confirmed inventory", "ttl_hours": ttl}
        if meta.get("host") != host or meta.get("workspace") != str(workspace.resolve()):
            return {**result, "status": "mismatch", "reason": "host or workspace changed"}
        age = ((now or datetime.now(timezone.utc)) - discovered).total_seconds() / 3600
        fresh = 0 <= age <= ttl
        return {**result, "status": "use-cache" if fresh else "stale", "refresh_required": not fresh,
                "age_hours": age, "ttl_hours": ttl, "reason": "fresh cache" if fresh else "expired or future timestamp"}
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError) as exc:
        return {**result, "status": "invalid", "reason": str(exc)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--host", required=True)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    cache = root / ".harness-state" / "mcp-tools.md"
    path = cache if cache.exists() else Path(__file__).resolve().parents[1] / "mcp-tools.md"
    print(json.dumps(inspect_registry(path, host=args.host, workspace=root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
