#!/usr/bin/env python3
"""Run-level eval: which skills does a real session actually register?

``trigger_eval.py`` asks a model to pick a skill from a list. This runs an actual
session against an installed catalog and reads what the host registered. The two
measure different things, and the difference is the point: a description can win a
routing question and still never fire, because the host's skill loader has to
have registered it first.

That distinction is not hypothetical here. Claude Code discovers skills at
``.claude/skills/<name>/SKILL.md`` — one level deep. This catalog once nested most
of its skills a level below that, so the loader registered five while
``routing-doctrine.md`` called fifteen of the nested ones "invokable directly at
any time". No structural test could see it: every document involved was
internally consistent, and only installing the tree and asking the host revealed
the gap.

The layout now follows the routing classes. The skills a user may reach directly
sit at the catalog root and register; the internal specialists stay nested, where
the loader does not offer them, which is what "reached only through the owning
sub-orchestrator" means expressed in the filesystem. ``--registration``
re-measures that split, and is worth rerunning whenever a skill is added or moved.

Both sessions start in the same small project, written by ``seed_workspace``, so
the catalog is the only difference between them.

    python skills/validation/run_eval.py --registration
    python skills/validation/run_eval.py --registration --out run-report.json

Registration is the only thing measured here: no routing session is run, and what a
session does with a registered skill is measured nowhere in this repository (see
BENCHMARK.md, "What is not measured"). ``--registration`` names that measurement and
is accepted so the documented command line keeps working.

Exit codes:
    0  both sessions completed and the report was printed
    1  a session could not be run or reported no skill list (the claude CLI is
       missing, timed out, exited non-zero, or never emitted its init event), so
       nothing was measured and no report is printed
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

#: A small plausible project for both sessions to start in. Nothing in it hints
#: at any skill.
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


class ClaudeRunError(RuntimeError):
    """A `claude` session did not complete, so there is nothing to measure."""


def _claude(cwd: Path, prompt: str, timeout: int) -> list[dict]:
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json",
           "--verbose", "--max-turns", "1"]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise ClaudeRunError("the claude CLI was not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ClaudeRunError(f"claude did not finish within {timeout}s") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise ClaudeRunError(f"claude exited {proc.returncode}: {detail[0][:200] if detail else 'no output'}")
    events = []
    for line in proc.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def registered_skills(events: list[dict]) -> list[str]:
    """The skill list the host reported when the session started.

    A session with no init event reported nothing, which is not the same as an
    empty list: reading it as "zero skills registered" would report every catalog
    skill as unregistered whenever the CLI failed.
    """
    for ev in events:
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            return ev.get("skills") or []
    raise ClaudeRunError("the session emitted no system init event, so no skill list was measured")


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
        baseline = set(registered_skills(_claude(root, "hi", timeout)))

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        on_disk = install_catalog(root)
        seed_workspace(root)
        withcat = set(registered_skills(_claude(root, "hi", timeout)))

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

    ap = argparse.ArgumentParser(description="Report which catalog skills a real host session registers.")
    ap.add_argument("--registration", action="store_true",
                    help="measure which skills the host registers; this is the only measurement, "
                         "accepted so the documented command line keeps working")
    ap.add_argument("--timeout", type=int, default=300, help="seconds allowed per session")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    try:
        report = {"registration": check_registration(args.timeout)}
    except ClaudeRunError as exc:
        print(f"error: nothing was measured: {exc}", file=sys.stderr)
        return 1
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
