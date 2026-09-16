#!/usr/bin/env python3
"""Run-level eval: which skill does a real session actually invoke?

``trigger_eval.py`` asks a model to pick a skill from a list. This runs an actual
session against an installed catalog and watches what it does. The two measure
different things, and the difference is the point: a description can win a
routing question and still never fire, because the host's skill loader has to
have registered it first.

That distinction is not hypothetical here. Claude Code discovers skills at
``.claude/skills/<name>/SKILL.md`` — one level deep. This catalog once nested 46
of its 52 skills a level below that, so the loader registered five while
``routing-doctrine.md`` called fifteen of the nested ones "invokable directly at
any time". No structural test could see it: every document involved was
internally consistent, and only installing the tree and asking the host revealed
the gap.

The layout now follows the routing classes. The 21 skills a user may reach
directly sit at the catalog root and register; the 31 internal specialists stay
nested, where the loader does not offer them, which is what "reached only through
the owning sub-orchestrator" means expressed in the filesystem. ``--registration``
re-measures that split, and is worth rerunning whenever a skill is added or moved.

The workspace matters. Asked to investigate a failure in an empty directory, a
session reasonably starts exploring rather than invoking anything, and the run
scores a miss that says nothing about the catalog. ``seed_workspace`` writes a
small plausible project so the request is not absurd on its face.

    python skills/validation/run_eval.py --registration
    python skills/validation/run_eval.py --queries 12 --out run-report.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent
REPO = SKILLS.parent

#: Files that make a request like "why does checkout fail" a sensible thing to
#: ask. Small on purpose: enough context to act on, too little to explore for
#: long, and nothing that hints at which skill should answer.
SEED = {
    "README.md": "# storefront\n\nCheckout and catalogue service.\n",
    "src/checkout.py": (
        "def submit(order):\n"
        "    total = sum(i['price'] * i['qty'] for i in order['items'])\n"
        "    if total > order['limit']:\n"
        "        raise ValueError('over limit')\n"
        "    return {'ok': True, 'total': total}\n"
    ),
    "src/cart.py": (
        "def add(cart, item):\n"
        "    cart.setdefault('items', []).append(item)\n"
        "    return cart\n"
    ),
    "tests/test_checkout.py": (
        "import unittest\n"
        "from src.checkout import submit\n\n\n"
        "class CheckoutTests(unittest.TestCase):\n"
        "    def test_under_limit(self):\n"
        "        self.assertTrue(submit({'items': [], 'limit': 10})['ok'])\n"
    ),
}


def seed_workspace(root: Path) -> None:
    for rel, body in SEED.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def install_catalog(root: Path) -> int:
    """Copy the catalog in exactly as Install.md prescribes, unflattened."""
    target = root / ".claude" / "skills"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILLS, target)
    return len(list(target.rglob("SKILL.md")))


def _claude(cwd: Path, prompt: str, turns: int, timeout: int) -> list[dict]:
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json",
           "--verbose", "--max-turns", str(turns)]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, stdin=subprocess.DEVNULL)
    events = []
    for line in proc.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def registered_skills(events: list[dict]) -> list[str]:
    for ev in events:
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            return ev.get("skills") or []
    return []


def invoked_skill(events: list[dict]) -> str | None:
    """The first Skill tool call, which is the routing decision itself.

    Later tool calls are the work, not the choice. A session that reads a
    SKILL.md without invoking it has not routed to that skill — it is looking,
    which is what an orchestrator does before delegating.
    """
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        for block in ev.get("message", {}).get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "Skill":
                return str(block.get("input", {}).get("skill", "")) or None
    return None


def cost_of(events: list[dict]) -> float:
    for ev in events:
        if ev.get("type") == "result":
            return float(ev.get("total_cost_usd") or 0.0)
    return 0.0


def check_registration(timeout: int) -> dict:
    """What this catalog adds to the host's skill list, controlled for the host.

    A bare name match is not enough. The host ships its own skills and reads a
    user-level directory, and at least one name collides: the catalog has
    `review/code-review` and Claude Code bundles a `code-review` of its own, so
    a single run makes the catalog's look registered when it is the host's that
    is present. Two runs settle it — an identical seeded workspace with and
    without the catalog installed — and only the difference is attributable here.
    That difference is also the answer to a question worth asking separately:
    when a catalog skill's name collides with a host skill, the host's wins and
    the catalog's is shadowed.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        seed_workspace(root)
        baseline = set(registered_skills(_claude(root, "hi", 1, timeout)))

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        on_disk = install_catalog(root)
        seed_workspace(root)
        withcat = set(registered_skills(_claude(root, "hi", 1, timeout)))

    added = withcat - baseline
    by_name = {}
    for skill in sorted(SKILLS.rglob("SKILL.md")):
        rel = skill.parent.relative_to(SKILLS).as_posix()
        by_name.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)

    registered, shadowed, unregistered = [], [], []
    for name, rels in sorted(by_name.items()):
        for rel in rels:
            if name in added:
                registered.append(rel)
            elif name in baseline:
                # Present before the catalog existed: the host's, not this one's.
                shadowed.append(rel)
            else:
                unregistered.append(rel)

    return {"on_disk": on_disk, "registered": sorted(registered),
            "shadowed_by_host": sorted(shadowed), "unregistered": sorted(unregistered),
            "baseline_count": len(baseline), "with_catalog_count": len(withcat)}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--registration", action="store_true",
                    help="report which skills the host actually registers, and stop")
    ap.add_argument("--queries", type=int, default=0,
                    help="how many routing runs to perform (each is a full session)")
    ap.add_argument("--turns", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    report = {"registration": check_registration(args.timeout)}
    reg = report["registration"]
    print(f"catalog on disk:      {reg['on_disk']} skills")
    print(f"host alone registers: {reg['baseline_count']}  (its own plus the user-level dir)")
    print(f"with catalog:         {reg['with_catalog_count']}")
    print("")
    print(f"attributable to this catalog: {len(reg['registered'])}")
    for rel in reg["registered"]:
        print(f"    {rel}")
    if reg["shadowed_by_host"]:
        print("")
        print(f"shadowed by a host skill of the same name: {len(reg['shadowed_by_host'])}")
        for rel in reg["shadowed_by_host"]:
            print(f"    {rel}")
    print("")
    print(f"not registered at all: {len(reg['unregistered'])}")

    # The doctrine's own claim, checked against what the host did.
    doctrine = (SKILLS / "routing-doctrine.md").read_text(encoding="utf-8", errors="replace")
    claimed = [rel for rel in reg["unregistered"]
               if f"`{rel}`" in doctrine or f"`{rel.rsplit('/', 1)[-1]}`" in doctrine]
    if claimed:
        print(f"\nnamed in routing-doctrine.md but not registered: {len(claimed)}")
        for rel in claimed[:20]:
            print(f"    {rel}")

    if args.out:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(f"\nwrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
