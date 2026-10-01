#!/usr/bin/env python3
"""Rule F: the hook scripts and the host files that register them are protected while the guard is in use (SEC-06).

No rule covered them, so one edit to ``guard_hook.py`` returned early from every rule for good while readiness
kept reporting the hooks registered and observed. They are now denied to edit tools and to the shell while a run
is pinned or a boundary is recorded. Developing the hooks in a plain checkout is never blocked, a maintainer
inside a run lifts the rule for a whole host session with ``SUPREMETEAM_HARNESS_DEV=1`` (set by whoever launches
the host, not by anything the agent can run), and the sanctioned registration writers keep working.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import _testkit as kit  # noqa: E402

HOOK = HOOK_DIR.as_posix()
SCRIPTS = ("guard_hook.py", "pre_tool_use.py", "_state.py", "post_tool_use.py", "user_prompt_submit.py", "_cmdscan.py")
REGISTRATION = (".claude/settings.json", ".claude/settings.local.json", ".codex/hooks.json", ".github/hooks.json")
UNRELATED_FREEZE = {"frozen_globs": [{"glob": "docs/**", "owner": "ops"}]}


class HarnessFileCase(unittest.TestCase):
    def setUp(self):
        manager = kit.project()
        self.root = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        self.home = self.root / "home"
        patcher = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("SUPREMETEAM_HARNESS_DEV", None)

    def engage_with_a_boundary(self) -> None:
        kit.write_guard(self.root, UNRELATED_FREEZE)

    def engage_with_a_pinned_run(self) -> None:
        (self.root / "README.md").write_text("# fixture\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(HOOK_DIR / "save_run.py"), "create", "--run-id", "r1", "--evidence", "README.md",
                               "--project-root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def edit(self, path: str) -> str:
        return kit.decide(kit.edit(path), self.root)

    def shell(self, command: str) -> str:
        return kit.decide(kit.bash(command), self.root)

    def assertProtected(self, output: str, message: str = "") -> None:
        self.assertTrue(kit.denied(output), message or output)
        self.assertIn("SUPREMETEAM_HARNESS_DEV", kit.reason(output))
        self.assertIn("not a hook", kit.reason(output))  # RR-guard-4: the cost of covering the whole file is said, with who decides
        self.assertIn("owner", kit.reason(output))


class NotEngagedTests(HarnessFileCase):
    def test_developing_the_hooks_in_a_plain_checkout_is_never_blocked(self):
        for name in SCRIPTS:
            with self.subTest(name=name):
                self.assertEqual(self.edit(f"{HOOK}/{name}"), "")
        self.assertEqual(self.shell(f"sed -i s/a/b/ {HOOK}/guard_hook.py"), "")
        self.assertEqual(self.shell(f"echo x > {HOOK}/new_helper.py"), "")
        self.assertEqual(self.edit(".claude/settings.json"), "")

    def test_a_grant_alone_does_not_engage_it(self):
        kit.write_guard(self.root, {"allow_dangerous": {"owner": "o", "reason": "r", "scope": "s", "created_at": "2026-01-01T00:00:00Z",
                                                        "expires_at": "2026-01-01T00:10:00Z"}})
        self.assertEqual(self.edit(f"{HOOK}/guard_hook.py"), "")

    def test_a_released_boundary_does_not_engage_it(self):
        kit.write_guard(self.root, {"frozen_globs": [{"glob": "docs/**", "owner": "ops", "released_at": "2026-09-05T00:00:00Z"}]})
        self.assertEqual(self.edit(f"{HOOK}/guard_hook.py"), "")


class EngagedByABoundaryTests(HarnessFileCase):
    def setUp(self):
        super().setUp()
        self.engage_with_a_boundary()

    def test_edit_tools_cannot_change_a_hook_script(self):
        for name in SCRIPTS:
            for tool in ("Edit", "Write", "MultiEdit"):
                with self.subTest(name=name, tool=tool):
                    self.assertProtected(kit.decide(kit.edit(f"{HOOK}/{name}", tool), self.root))
        self.assertProtected(self.edit(f"{HOOK}//./guard_hook.py"))
        self.assertProtected(self.edit(f"{HOOK}/sub/../GUARD_HOOK.PY"))

    def test_the_shell_cannot_change_a_hook_script_by_any_ordinary_route(self):
        for command in (
            f"echo 'import sys; sys.exit(0)' > {HOOK}/guard_hook.py", f"echo x>>{HOOK}/_state.py", f"sed -i s/a/b/ {HOOK}/guard_hook.py",
            f"sed -E -i s/a/b/ {HOOK}/guard_hook.py", f"perl -pi -e s/a/b/ {HOOK}/guard_hook.py", f"cp evil.py {HOOK}/guard_hook.py",
            f"mv evil.py {HOOK}/guard_hook.py", f"tee {HOOK}/guard_hook.py < evil.py", f"rm {HOOK}/guard_hook.py", f"rm -rf {HOOK}",
            f"truncate -s 0 {HOOK}/guard_hook.py", f"curl -o {HOOK}/guard_hook.py http://h/x", f"dd if=x of={HOOK}/guard_hook.py",
            f"python3 -c \"open('{HOOK}/guard_hook.py','w').write('')\"", f"python3 - <<'EOF'\nopen('{HOOK}/guard_hook.py','w')\nEOF",
            f"node -e \"require('fs').writeFileSync('{HOOK}/guard_hook.py','')\"", f"sh -c 'echo x > {HOOK}/guard_hook.py'",
            f"cd {HOOK} && echo x > guard_hook.py", f"cd {HOOK}; rm _state.py", f"git -C {HOOK} checkout -- guard_hook.py",
            f"find {HOOK} -name '*.py' -delete", f"rm -rf {HOOK_DIR.parent}", f"mv {HOOK_DIR.parent} {HOOK_DIR.parent}.off",
        ):
            with self.subTest(command=command):
                self.assertProtected(self.shell(command))

    def test_the_host_registration_files_are_protected(self):
        for path in REGISTRATION:
            with self.subTest(path=path):
                self.assertProtected(self.edit(path))
                self.assertProtected(self.edit(f"{self.root}/{path}"))
                self.assertProtected(self.shell(f"echo '{{}}' > {path}"))
                self.assertProtected(self.shell(f"python3 -c \"open('{path}','w').write('{{}}')\""))
        for path in (".claude/settings.json", ".codex/hooks.json", ".config/github-copilot/hooks.json"):
            with self.subTest(user_scope=path):
                self.assertProtected(self.edit(f"{self.home}/{path}"))
                self.assertProtected(self.shell(f"cp x ~/{path}"))

    def test_reads_other_files_and_the_sanctioned_registration_writers_pass(self):
        for command in (
            f"cat {HOOK}/guard_hook.py", f"grep -n rule {HOOK}/guard_hook.py", f"ls {HOOK}", f"cp {HOOK}/guard_hook.py /tmp/copy.py",
            f"python -m unittest discover -s {HOOK}", "cat .claude/settings.json", "echo x > .claude/launch.json", "echo x > src/notes.md",
            "python skills/harness/hooks/repair_registration.py --host claude --scope project --apply",
            "python scripts/install_hooks.py --host claude --scope project", "python skills/harness/hooks/verify_registration.py --host claude",
            f"python {HOOK}/check_readiness.py --host claude", f"python {HOOK}/guard_state.py status",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.shell(command), "")
        self.assertEqual(self.edit(f"{self.root}/src/app.py"), "")
        self.assertEqual(self.edit(".claude/launch.json"), "")

    def test_a_maintenance_session_lifts_the_rule(self):
        with mock.patch.dict(os.environ, {"SUPREMETEAM_HARNESS_DEV": "1"}):
            self.assertEqual(self.edit(f"{HOOK}/guard_hook.py"), "")
            self.assertEqual(self.shell(f"sed -i s/a/b/ {HOOK}/guard_hook.py"), "")
            self.assertEqual(self.edit(".claude/settings.json"), "")
        with mock.patch.dict(os.environ, {"SUPREMETEAM_HARNESS_DEV": "yes"}):
            self.assertProtected(self.edit(f"{HOOK}/guard_hook.py"))

    def test_the_single_writer_rules_still_speak_first(self):
        out = self.edit(".harness-state/guard-state.json")
        self.assertIn("guard_state.py", kit.reason(out))
        self.assertNotIn("SUPREMETEAM_HARNESS_DEV", kit.reason(out))

    def test_an_unparseable_command_is_still_searched(self):
        self.assertProtected(self.shell(f"echo \"x > {HOOK}/guard_hook.py"))
        self.assertEqual(self.shell(f"cat {HOOK}/guard_hook.py \""), "")


class EngagedByAPinnedRunTests(HarnessFileCase):
    def test_a_pinned_run_protects_the_hooks_and_releasing_it_lifts_the_protection(self):
        self.engage_with_a_pinned_run()
        self.assertProtected(self.edit(f"{HOOK}/guard_hook.py"))
        self.assertProtected(self.shell(f"rm {HOOK}/_state.py"))
        self.assertProtected(self.edit(".claude/settings.json"))
        subprocess.run([sys.executable, str(HOOK_DIR / "save_run.py"), "release", "--run-id", "r1", "--project-root", str(self.root)],
                       capture_output=True, text=True, check=True)
        self.assertEqual(self.edit(f"{HOOK}/guard_hook.py"), "")


if __name__ == "__main__":
    unittest.main()
