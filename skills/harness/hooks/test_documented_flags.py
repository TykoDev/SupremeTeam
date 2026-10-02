#!/usr/bin/env python3
"""Every command line the user-facing documents show is accepted by the script it names.

A documented ``python skills/.../tool.py --flag`` that the tool's argument parser
does not define exits 2 on the reader's first copy-paste. This test finds those
command lines in ``README.md``, ``QUICK-START.md``, ``Install.md`` and the hooks
``README.md``, asks each script for its own option list (``--help``, one level of
sub-command where the parser has them), and fails on any flag the parser does not
know. The installer wrappers are held to the same rule: ``install.sh`` against its
usage text and ``install.ps1`` against its parameter block, including the flag
cells of the "Installer options" tables.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
SKILLS = HOOK_DIR.parents[1]
REPO = SKILLS.parent
DOCS = [REPO / "README.md", REPO / "QUICK-START.md", REPO / "Install.md", HOOK_DIR / "README.md"]
# The documents name `scripts/install*`, which an installed copy does not carry.
CHECKOUT = (REPO / "README.md").is_file() and (REPO / "scripts" / "install_hooks.py").is_file()

_PYTHON_COMMAND = re.compile(r"""\b(?:python3?|py\s+-3)\s+["']?(?P<script>[^\s"'`|<>]+\.py)["']?(?P<args>[^`\n|]*)""")
_WRAPPER_COMMAND = re.compile(r"\binstall\.(?P<kind>sh|ps1)\b(?P<args>[^`\n|]*)")
_FLAG = re.compile(r"-{1,2}[A-Za-z][\w-]*")
_STOP = {"&&", "||", ";", ">", ">>", "2>&1", "#"}
_help_cache: dict[tuple, set[str] | None] = {}


def _index() -> dict[str, list[Path]]:
    found: dict[str, list[Path]] = {}
    for root in (SKILLS, REPO / "scripts"):
        if root.is_dir():
            for path in root.rglob("*.py"):
                if "__pycache__" not in path.parts and not path.name.startswith("test_"):
                    found.setdefault(path.name, []).append(path)
    return found


def _tokens(args: str) -> list[str]:
    args = args.split(" #")[0]
    try:
        raw = shlex.split(args)
    except ValueError:
        raw = args.split()
    kept = []
    for token in raw:
        if token in _STOP:
            break
        kept.append(token.strip("[]"))
    return kept


def _flags(tokens: list[str]) -> list[str]:
    return [t.split("=", 1)[0] for t in tokens if _FLAG.fullmatch(t.split("=", 1)[0])]


def _option_names(help_text: str) -> set[str]:
    """The option strings of an argparse help screen: the first column of each option line."""
    names: set[str] = set()
    for line in help_text.splitlines():
        match = re.match(r"^  (-\S.*?)(?:\s{2,}.*)?$", line)
        if match:
            names.update(_FLAG.findall(match.group(1)))
    return names


def parser_flags(script: Path, subcommand: str | None = None) -> set[str] | None:
    """The flags ``script`` accepts, from its own ``--help``; None when it has no argument parser."""
    key = (script, subcommand)
    if key not in _help_cache:
        argv = [sys.executable, str(script), *([subcommand] if subcommand else []), "--help"]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        done = subprocess.run(argv, capture_output=True, text=True, cwd=str(REPO), env=env, timeout=60, check=False)
        _help_cache[key] = _option_names(done.stdout) if done.returncode == 0 and "usage:" in done.stdout else None
    return _help_cache[key]


def subcommands(script: Path) -> set[str]:
    done = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, cwd=str(REPO),
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}, timeout=60, check=False)
    usage = done.stdout.split("\n\n", 1)[0]
    match = re.search(r"\{([\w,-]+)\}", usage)
    return set(match.group(1).split(",")) if match else set()


def resolve(documented: str, index: dict[str, list[Path]]) -> list[Path]:
    parts = documented.replace("\\", "/").strip("\"'").split("/")
    tail = "/".join(parts[-3:])
    candidates = index.get(parts[-1], [])
    narrowed = [p for p in candidates if p.as_posix().endswith(tail)]
    return narrowed or candidates


def wrapper_flags() -> tuple[set[str] | None, set[str] | None]:
    """Flags ``install.sh`` documents in its usage text and parameters ``install.ps1`` declares (lower case)."""
    shell = None
    bash = shutil.which("bash")
    if bash and (REPO / "scripts" / "install.sh").is_file():
        done = subprocess.run([bash, str(REPO / "scripts" / "install.sh"), "--help"], capture_output=True, text=True, check=False)
        shell = set(re.findall(r"^\s+(--[\w-]+|-h)\b", done.stdout, re.M)) | {"--help"}
    powershell = None
    script = REPO / "scripts" / "install.ps1"
    if script.is_file():
        block = script.read_text(encoding="utf-8").split("param(", 1)[1].split("\n)\n", 1)[0]
        powershell = {"-" + name.lower() for name in re.findall(r"\]\s*\$(\w+)", block)}
    return shell, powershell


def problems_in(text: str, label: str, index: dict[str, list[Path]], shell: set[str] | None, powershell: set[str] | None) -> tuple[list[str], int]:
    """Every documented flag the named parser does not define, and how many command lines were checked."""
    text = re.sub(r"\\\n\s*", " ", text)
    problems, checked = [], 0
    for number, line in enumerate(text.splitlines(), 1):
        for match in _PYTHON_COMMAND.finditer(line):
            script, tokens = match.group("script"), _tokens(match.group("args"))
            flags = _flags(tokens)
            where = f"{label}:{number}: `{match.group(0).strip()}`"
            candidates = resolve(script, index)
            if not candidates:
                problems.append(f"{where} names {script}, which is not in the repository")
                continue
            if len(candidates) > 1:
                continue
            checked += 1
            if not flags:
                continue
            known = parser_flags(candidates[0])
            if known is None:
                problems.append(f"{where} passes {flags} to a script with no argument parser")
                continue
            sub = next((t for t in tokens if not t.startswith("-")), None)
            if sub in subcommands(candidates[0]):
                known = known | (parser_flags(candidates[0], sub) or set())
            problems.extend(f"{where}: {flag} is not defined by {candidates[0].name}" for flag in flags if flag not in known)
        for match in _WRAPPER_COMMAND.finditer(line):
            kind, flags = match.group("kind"), _flags(_tokens(match.group("args")))
            known = shell if kind == "sh" else powershell
            if known is None:
                continue
            checked += 1
            for flag in flags:
                if (flag if kind == "sh" else flag.lower()) not in known:
                    problems.append(f"{label}:{number}: `{match.group(0).strip()}`: {flag} is not an install.{kind} option")
    problems.extend(_table_problems(text, label, shell, powershell))
    return problems, checked


def _table_problems(text: str, label: str, shell: set[str] | None, powershell: set[str] | None) -> list[str]:
    """The flag cells of a ``| Goal | Windows | macOS / Linux |`` table."""
    problems, inside = [], False
    for number, line in enumerate(text.splitlines(), 1):
        if re.match(r"\|\s*Goal\s*\|\s*Windows\s*\|", line):
            inside = True
            continue
        if not line.startswith("|"):
            inside = False
        if not inside or set(line) <= set("|- "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        for cell, known, kind in ((cells[1], powershell, "ps1"), (cells[2], shell, "sh")):
            if known is None:
                continue
            for span in re.findall(r"`([^`]*)`", cell):
                for flag in _flags(_tokens(span)):
                    if (flag if kind == "sh" else flag.lower()) not in known:
                        problems.append(f"{label}:{number}: {flag} is not an install.{kind} option")
    return problems


class DocumentedFlagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = _index()
        cls.shell, cls.powershell = wrapper_flags()

    def check(self, path: Path) -> tuple[list[str], int]:
        if not path.is_file():
            self.skipTest(f"{path.name} is not part of this tree")
        return problems_in(path.read_text(encoding="utf-8"), path.relative_to(REPO).as_posix() if REPO in path.parents else path.name,
                           self.index, self.shell, self.powershell)

    @unittest.skipUnless(CHECKOUT, "not a checkout: the documents name scripts/install*, which an installed copy does not carry")
    def test_every_documented_flag_exists_in_the_script_it_is_given_to(self):
        total = 0
        for path in DOCS:
            if not path.is_file():
                continue
            problems, checked = self.check(path)
            total += checked
            self.assertEqual(problems, [], "\n".join(problems))
        self.assertGreaterEqual(total, 15, "the scan found almost no command lines, so it proved nothing")

    @unittest.skipUnless(CHECKOUT, "not a checkout: the hooks README names scripts/install_hooks.py, which an installed copy does not carry")
    def test_the_hooks_readme_commands_are_all_found_and_checked(self):
        problems, checked = self.check(HOOK_DIR / "README.md")
        self.assertEqual(problems, [], "\n".join(problems))
        self.assertGreaterEqual(checked, 25)

    def test_a_flag_the_parser_does_not_define_is_reported(self):
        text = "\n".join((
            "python skills/harness/hooks/verify_registration.py --host claude --scope project",
            "python skills/harness/hooks/size_audit.py --threshold 104857600 --interval 3600",
            "python skills/harness/hooks/audit_improve.py --run --force",
            "python skills/harness/hooks/verify_registration.py --host auto --json",
        ))
        problems, checked = problems_in(text, "synthetic", self.index, self.shell, self.powershell)
        self.assertEqual(checked, 4)
        self.assertEqual(sorted(re.search(r"(--[\w-]+) is not defined", p).group(1) for p in problems),
                         ["--force", "--interval", "--scope", "--threshold"])

    def test_a_subcommand_flag_is_checked_against_the_subcommand(self):
        good = "python skills/harness/hooks/guard_state.py freeze --glob \"src/**\" --owner ops --scope \"freeze\""
        bad = "python skills/harness/hooks/guard_state.py freeze --glob \"src/**\" --nonsense 1"
        self.assertEqual(problems_in(good, "good", self.index, self.shell, self.powershell)[0], [])
        problems = problems_in(bad, "bad", self.index, self.shell, self.powershell)[0]
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("--nonsense", problems[0])

    def test_continuation_lines_and_comments_are_read_as_one_command(self):
        text = "python skills/harness/hooks/check_readiness.py --host auto \\\n  --bogus-flag  # a comment --also-bogus\n"
        problems = problems_in(text, "continued", self.index, self.shell, self.powershell)[0]
        self.assertEqual([re.search(r"(--[\w-]+) is not defined", p).group(1) for p in problems], ["--bogus-flag"])

    def test_a_script_that_does_not_exist_is_reported(self):
        problems = problems_in("python skills/harness/hooks/no_such_tool.py --x", "gone", self.index, self.shell, self.powershell)[0]
        self.assertEqual(len(problems), 1)
        self.assertIn("not in the repository", problems[0])

    def test_wrapper_options_are_checked_against_the_wrapper(self):
        if self.shell is None or self.powershell is None:
            self.skipTest("needs bash and scripts/install.ps1")
        text = "\n".join((
            "bash ./scripts/install.sh --register-hooks --hooks-scope project --nonsense",
            "powershell -File .\\scripts\\install.ps1 -RegisterHooks -HooksScope Project -Nonsense",
            "| Goal | Windows | macOS / Linux |",
            "|---|---|---|",
            "| Register hooks | `-RegisterHooks` | `--register-hooks` |",
            "| Bogus | `-NotAParameter` | `--not-an-option` |",
            "",
        ))
        problems = problems_in(text, "wrappers", self.index, self.shell, self.powershell)[0]
        self.assertEqual(sorted(re.search(r": (-[\w-]+) is not an install", p).group(1) for p in problems),
                         sorted(["--nonsense", "--not-an-option", "-NotAParameter", "-Nonsense"]))


if __name__ == "__main__":
    unittest.main()
