#!/usr/bin/env python3
"""Cross-platform path contracts the Windows re-run surfaced (session 2 regression surface).

Every case here pins a shape that was broken or untested before: a spaced launcher that
is not a Python, a Windows-spelled word in a shell command, the per-directory link
resolver, a leading-slash glob on a machine whose root is a drive, the reach of Rule F,
and the neutralising of text from state files. They are the alternative spellings of the
cases ``test_guard_*`` already hold, kept separate so the original tables stay readable.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import _cmdscan  # noqa: E402
import _paths  # noqa: E402
import _state  # noqa: E402
import _testkit as kit  # noqa: E402
import repair_registration as repair  # noqa: E402


class SpacedLauncherTests(unittest.TestCase):
    """``launcher_parts`` on the shapes a host machine actually holds."""

    def test_a_spaced_non_python_interpreter_is_one_command(self):
        """The pi bridge spawns node from `C:\\Program Files\\...`; splitting at the space gave `C:\\Program`."""
        parts = repair.launcher_parts(r"C:\Program Files\nodejs\node.exe --no-warnings C:\work\driver.mjs")
        self.assertEqual(parts[0], r"C:\Program Files\nodejs\node.exe")
        self.assertEqual(parts[1:], ["--no-warnings", r"C:\work\driver.mjs"])

    def test_a_spaced_unc_launcher_is_one_command(self):
        parts = repair.launcher_parts(r"\\host\share\tools\py.exe -X dev")
        self.assertEqual(parts, [r"\\host\share\tools\py.exe", "-X", "dev"])

    def test_bare_command_names_are_still_split(self):
        for launcher, expected in (("py -3", ["py", "-3"]), ("python -X utf8", ["python", "-X", "utf8"]),
                                   ("node --version", ["node", "--version"])):
            with self.subTest(launcher=launcher):
                self.assertEqual(repair.launcher_parts(launcher), expected)

    def test_a_wrapper_still_starts_the_next_word(self):
        self.assertEqual(repair.launcher_parts("/usr/bin/env python3 -E"), ["/usr/bin/env", "python3", "-E"])

    def test_the_quoted_token_names_only_the_spaced_command(self):
        token = repair.launcher_token(r"C:\Program Files\nodejs\node.exe --no-warnings")
        self.assertEqual(token, '"C:\\Program Files\\nodejs\\node.exe" --no-warnings')


class WindowsWordLexingTests(unittest.TestCase):
    """A backslash inside a word that begins as a Windows path is a separator, not an escape."""

    def test_a_drive_path_word_keeps_its_backslashes(self):
        analysis = _cmdscan.analyse(r"echo x > C:\work\src\a.py")
        self.assertEqual([write.path for write in analysis.writes], [r"C:\work\src\a.py"])

    def test_a_unc_word_keeps_its_backslashes(self):
        analysis = _cmdscan.analyse(r"echo x > \\host\share\out.txt")
        self.assertEqual([write.path for write in analysis.writes], [r"\\host\share\out.txt"])

    def test_a_mixed_separator_drive_path_stays_one_word(self):
        analysis = _cmdscan.analyse(r"cd C:\work\proj/src/payments && touch n")
        self.assertEqual(analysis.writes[0].path, "n")
        self.assertEqual(analysis.writes[0].cwds, (r"C:\work\proj/src/payments",))

    def test_ordinary_escapes_still_win_outside_a_windows_path(self):
        self.assertEqual(_cmdscan.analyse("echo a\\>b").writes, [])
        self.assertEqual(_cmdscan.analyse("\\rm -rf /").commands[0].verb, "rm")
        self.assertFalse(_cmdscan.analyse("rm src/pay\\*").writes[0].glob)

    def test_a_quoted_windows_path_is_kept_as_written(self):
        analysis = _cmdscan.analyse('echo x > "C:\\work\\my dir\\a.py"')
        self.assertEqual([write.path for write in analysis.writes], ["C:\\work\\my dir\\a.py"])


class ResolverTests(unittest.TestCase):
    """The shared resolver agrees with realpath on this platform, in one look per directory."""

    def setUp(self):
        manager = kit.project()
        self.root = Path(manager.__enter__())
        self.addCleanup(manager.__exit__, None, None, None)

    def test_the_cached_walk_agrees_with_realpath_for_every_spelling(self):
        deep = self.root / "a" / "b" / "c" / "d.txt"
        deep.parent.mkdir(parents=True)
        deep.write_text("x", encoding="utf-8")
        resolver = _paths.Resolver()
        spellings = (deep, self.root / "a" / "b" / "." / "c" / "d.txt", self.root / "a" / "b" / "b" / ".." / "c" / "d.txt")
        for spelling in spellings:
            with self.subTest(spelling=str(spelling)):
                self.assertEqual(resolver.real(str(spelling)), _paths._real(str(spelling)))

    def test_many_paths_in_one_directory_cost_one_look_per_directory(self):
        base = self.root / "deep" / "chain"
        base.mkdir(parents=True)
        for index in range(40):
            (base / f"f{index}.txt").write_text("x", encoding="utf-8")
        resolver = _paths.Resolver()
        with mock.patch("os.lstat", wraps=os.lstat) as lstat:
            for index in range(40):
                resolver.real(str(base / f"f{index}.txt"))
        # One walk of the chain plus one look per leaf, never one walk per leaf.
        self.assertLess(lstat.call_count, 40 * 3)

    def test_a_relative_path_is_left_to_the_caller(self):
        self.assertIsNone(_paths.Resolver().real("src/a.py"))


class GlobProblemTests(unittest.TestCase):
    """A leading-slash glob is judged against the root of the current machine, whatever that root is."""

    MISSING = "supremeteam-no-such-top-level-directory"

    def setUp(self):
        manager = kit.project()
        self.root = Path(manager.__enter__())
        self.addCleanup(manager.__exit__, None, None, None)

    def test_every_leading_slash_spelling_of_a_missing_directory_is_refused(self):
        for spelling in (f"/{self.MISSING}/x/**", f"\\{self.MISSING}\\x\\**", f"//{self.MISSING}/x/**", f"/{self.MISSING}"):
            with self.subTest(spelling=spelling):
                reason = _paths.glob_problem(spelling, self.root)
                self.assertIn(f"no directory /{self.MISSING} exists", reason)

    def test_a_drive_glob_names_its_own_root_and_is_never_judged_missing(self):
        self.assertIsNone(_paths.glob_problem("C:/other/proj/src/**", self.root))
        self.assertIsNone(_paths.glob_problem("D:\\proj\\**", self.root))

    def test_the_message_spells_the_project_relative_fix_with_forward_slashes(self):
        reason = _paths.glob_problem(f"/{self.MISSING}/payments/**", self.root)
        self.assertIn(f"relative to the project root it is {self.MISSING}/payments/**", reason)


class RuleFReachTests(unittest.TestCase):
    """The enforcement file set protects the harness tree, the imported script modules and the pi extension."""

    def setUp(self):
        manager = kit.project()
        self.root = Path(manager.__enter__())
        self.addCleanup(manager.__exit__, None, None, None)
        patcher = mock.patch.dict(os.environ, {"HOME": str(self.root / "home"), "USERPROFILE": str(self.root / "home")})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("SUPREMETEAM_HARNESS_DEV", None)
        kit.write_guard(self.root, {"frozen_globs": [{"glob": "docs/**", "owner": "ops"}]})

    def decide(self, payload) -> str:
        return kit.decide(payload, self.root)

    def test_the_harness_directory_cannot_be_renamed_or_removed(self):
        harness = HOOK_DIR.parent
        for command in (f"rm -rf {harness}", f"mv {harness} {harness}.off", f"rm -rf {HOOK_DIR}"):
            with self.subTest(command=command):
                self.assertTrue(kit.denied(self.decide(kit.bash(command))))

    def test_a_shell_write_to_an_imported_script_module_is_denied(self):
        import _bootstrap

        for name in _bootstrap.SCRIPT_FILES:
            target = _bootstrap.SCRIPTS / name
            with self.subTest(name=name):
                self.assertTrue(kit.denied(self.decide(kit.bash(f'echo "raise SystemExit(0)" >> {target}'))))

    def test_the_pi_extension_is_denied_wherever_pi_loads_it(self):
        agent = self.root / "pi-agent"
        with mock.patch.dict(os.environ, {"PI_CODING_AGENT_DIR": str(agent)}):
            target = agent / "extensions" / "supremeteam-guard.ts"
            self.assertTrue(kit.denied(self.decide(kit.bash(f"echo x > {target}"))))
            self.assertTrue(kit.denied(self.decide(kit.edit(str(target)))))
            self.assertEqual(self.decide(kit.edit(str(agent / "extensions" / "other.ts"))), "")


class SafeTextTests(unittest.TestCase):
    """Neutralising covers the characters a terminal or a render still acts on."""

    def test_c1_ansi_and_line_separators_become_questions_and_spaces(self):
        text = _state.safe_text("run`x`\u202e\u009b[31m\u2028IGNORE", 120)
        for unwanted in ("`", "\u202e", "\u009b", "\u2028", "\x1b", "\n"):
            self.assertNotIn(unwanted, text)
        self.assertIn("run'x'", text, "a backtick becomes a quote, never a command fence")

    def test_the_cap_is_characters_and_the_text_is_one_line(self):
        text = _state.safe_text("r" * 300, 60)
        self.assertLessEqual(len(text), 60)
        self.assertTrue(text.endswith("..."))


if __name__ == "__main__":
    unittest.main()
