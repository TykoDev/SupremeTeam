#!/usr/bin/env python3
"""Installer contract: ownership, stage-and-swap, refusals, and the static guards.

`install.sh` and `install.ps1` are repository tooling, not part of an installed
skill tree, so their tests live beside them. The behavioural tests run the real
`install.sh` under bash against a temporary HOME and destination: nothing here
touches the real home directory, and PATH is rebuilt from a shim directory so a
host CLI on the developer's machine cannot change what auto-detection sees.

`install.ps1` cannot run in this suite. Its behaviour is pinned by parity checks
against `install.sh` (the item file, the record names, the flags, the refusals,
the one recursive delete), and no test here proves it runs under PowerShell.
Likewise the bash 3.2 rule is a static check: it fails on an unguarded
possibly-empty array expansion or a bash 4 construct. The behavioural tests run
under whatever bash `BASH` names, so they execute under bash 3.2 only on a Mac
(or with SUPREMETEAM_TEST_BASH set); on Linux and in CI images with bash 5 they do not.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent
SKILLS = REPO / "skills"
INSTALL_SH = SCRIPTS / "install.sh"
INSTALL_PS1 = SCRIPTS / "install.ps1"
ITEMS_FILE = SCRIPTS / "install-items.txt"

MANIFEST = ".supremeteam-manifest"
MARKER = ".supremeteam-managed"
STAGE_MARKER = ".supremeteam-stage"
BACKUP_SUFFIX = ".supremeteam-backup"

# On macOS the behavioural tests run under the system bash, which is 3.2: the shell
# the installer has to keep working under. SUPREMETEAM_TEST_BASH points them at any
# other bash, such as a locally built old one.
BASH = os.environ.get("SUPREMETEAM_TEST_BASH") or ("/bin/bash" if sys.platform == "darwin" else shutil.which("bash"))
RUNS_BASH = BASH is not None and os.path.exists(BASH) and os.name == "posix"


def bash_version() -> str:
    if not RUNS_BASH:
        return "no bash"
    probe = subprocess.run([BASH, "-c", "printf %s \"$BASH_VERSION\""], capture_output=True, text=True)
    return probe.stdout or "unknown"


sys.path.insert(0, str(SKILLS / "scripts"))
from data_formats import load_data  # noqa: E402


class ItemList:
    """An independent reading of install-items.txt, to cross-check the installers."""

    def __init__(self, text: str):
        self.core: list[str] = []
        self.seeds: list[str] = []
        self.teams: dict[str, list[str]] = {}
        self.legacy: dict[str, list[str]] = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            kind, name, *members = line.split()
            if kind in ("core", "seed"):
                self.core.append(name)
                if kind == "seed":
                    self.seeds.append(name)
            elif kind == "team":
                self.teams.setdefault(name, []).extend(members)
            elif kind == "legacy":
                self.legacy.setdefault(name, []).extend(members)
            else:
                raise AssertionError(f"unknown record {kind!r} in install-items.txt")

    def selected(self, *teams: str) -> list[str]:
        names = list(self.core)
        for team in teams or tuple(self.teams):
            names.extend(member for member in self.teams[team] if member not in names)
        return names


ITEMS = ItemList(ITEMS_FILE.read_text(encoding="utf-8"))


def snapshot(path: Path) -> dict:
    """Every entry under `path` with its bytes, executable bit or link target.

    Equal snapshots mean byte for byte. Only the executable bit is compared, not
    the full mode, because a copy legitimately follows the umask.
    """
    path = Path(path)
    if path.is_symlink():
        return {".": ("link", os.readlink(path))}
    if path.is_file():
        return {".": ("file", path.read_bytes(), bool(path.stat().st_mode & stat.S_IXUSR))}
    entries: dict = {".": ("dir",)}
    for item in sorted(path.rglob("*")):
        relative = item.relative_to(path).as_posix()
        if item.is_symlink():
            entries[relative] = ("link", os.readlink(item))
        elif item.is_dir():
            entries[relative] = ("dir",)
        else:
            entries[relative] = ("file", item.read_bytes(), bool(item.stat().st_mode & stat.S_IXUSR))
    return entries


def without(entries: dict, *names: str) -> dict:
    return {key: value for key, value in entries.items() if key not in names}


def read_manifest(root: Path) -> SimpleNamespace:
    lines = (root / MANIFEST).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "supremeteam-manifest 1", lines[0]
    return SimpleNamespace(
        items=[line[5:] for line in lines if line.startswith("item ")],
        teams=next(line[6:].split() for line in lines if line.startswith("teams ")),
    )


def write_source(repo: Path, items: ItemList, version: str) -> None:
    """A small catalog with the real item names, so a changed version is visible in every item."""
    skills = repo / "skills"
    for name in items.selected():
        target = skills / name
        if (SKILLS / name).is_dir():
            (target / "nested").mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(f"{name} {version}\n", encoding="utf-8")
            (target / "nested" / "data.txt").write_text(f"{name} data {version}\n", encoding="utf-8")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            body = '{"runtime": {"python": {"minimum": "3.13"}}}\n' if name == "runtime-manifest.yaml" else f"{name} {version}\n"
            target.write_text(body, encoding="utf-8")


NEEDED_TOOLS = ("basename", "cat", "cp", "date", "dirname", "head", "ls", "mkdir", "mktemp", "mv", "rm", "sed", "tr")


def build_path_directory(directory: Path) -> None:
    """The only tools the installer may find: the ones it uses, and this interpreter as python3."""
    directory.mkdir()
    for tool in NEEDED_TOOLS:
        real = shutil.which(tool)
        if real is None:
            raise unittest.SkipTest(f"{tool} is not available")
        (directory / tool).symlink_to(real)
    # A wrapper rather than a link, so a virtual environment's interpreter still finds its prefix.
    python = directory / "python3"
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    python.chmod(0o755)


class Sandbox:
    """A checkout, a HOME and a PATH of shims, all inside one temporary directory."""

    def __init__(self, case: unittest.TestCase, version: str = "v1"):
        self._tmp = tempfile.TemporaryDirectory()
        case.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.dest = self.home / ".agents" / "skills"
        self.repo = self.root / "checkout"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(INSTALL_SH, self.repo / "scripts" / "install.sh")
        shutil.copy2(ITEMS_FILE, self.repo / "scripts" / "install-items.txt")
        write_source(self.repo, ITEMS, version)
        self.bin = self.root / "bin"
        build_path_directory(self.bin)

    def run(self, *args: str, env: dict | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
        environment = {"HOME": str(self.home), "PATH": str(self.bin), "LC_ALL": "C", **(env or {})}
        return subprocess.run(
            [BASH, str(self.repo / "scripts" / "install.sh"), *args],
            cwd=str(cwd or self.root),
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )

    def install(self, *args: str, **kwargs) -> subprocess.CompletedProcess:
        return self.run("--destination", str(self.dest), *args, **kwargs)

    def publish(self, version: str, drop: tuple[str, ...] = ()) -> None:
        """Ship a new catalog: every item at `version`, without the items in `drop`."""
        lines = []
        for raw in (self.repo / "scripts" / "install-items.txt").read_text(encoding="utf-8").splitlines():
            parts = raw.split()
            if parts[:1] in (["core"], ["seed"]) and parts[1] in drop:
                continue
            if parts[:1] == ["team"]:
                raw = " ".join(parts[:2] + [name for name in parts[2:] if name not in drop])
            lines.append(raw)
        (self.repo / "scripts" / "install-items.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        for name in drop:
            target = self.repo / "skills" / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        write_source(self.repo, ItemList("\n".join(lines)), version)

    def shim(self, name: str, body: str) -> None:
        """Replace a tool on PATH with a script, to make one call fail on purpose."""
        real = shutil.which(name)
        path = self.bin / name
        path.unlink()
        path.write_text(f'#!/bin/sh\n{body}\nexec "{real}" "$@"\n', encoding="utf-8")
        path.chmod(0o755)

    def backups(self) -> list[Path]:
        base = self.dest.parent / (self.dest.name + BACKUP_SUFFIX)
        return sorted(base.iterdir()) if base.is_dir() else []

    def stages(self) -> list[Path]:
        return sorted(self.dest.glob(".supremeteam-stage.*"))


def listing(result: subprocess.CompletedProcess) -> str:
    return f"bash {bash_version()}, exit {result.returncode}\n{result.stdout}\n{result.stderr}"


@unittest.skipUnless(RUNS_BASH, "the installer tests run install.sh under bash on a POSIX host")
class InstallerBehaviourTests(unittest.TestCase):
    def only_backup(self, box: Sandbox) -> Path:
        backups = box.backups()
        self.assertEqual(len(backups), 1, "items the installer did not install must be moved aside, not deleted or overwritten")
        return backups[0]

    def assert_installed(self, box: Sandbox, root: Path | None = None, names: list[str] | None = None) -> None:
        root = root or box.dest
        for name in names or ITEMS.selected():
            source = snapshot(box.repo / "skills" / name)
            installed = snapshot(root / name)
            if (box.repo / "skills" / name).is_dir():
                self.assertIn(MARKER, installed, f"{name} carries no ownership marker")
                installed = without(installed, MARKER)
            self.assertEqual(installed, source, f"{name} differs from the catalog")

    def test_a_fresh_install_copies_every_item_and_records_what_it_installed(self):
        box = Sandbox(self)
        result = box.install()
        self.assertEqual(result.returncode, 0, listing(result))
        self.assert_installed(box)
        manifest = read_manifest(box.dest)
        self.assertEqual(manifest.items, ITEMS.selected())
        self.assertEqual(manifest.teams, list(ITEMS.teams))
        self.assertEqual(box.backups(), [])
        self.assertEqual(box.stages(), [])
        for line in ("Supreme Team installation complete.", f"Target: {box.dest}", "Host targets: none detected",
                     "Host mirrors: none", "Moved aside: nothing", "Hook registration: not requested",
                     f"installed {len(ITEMS.selected())} items ({len(ITEMS.selected())} new, 0 replaced)",
                     f"recorded in {box.dest / MANIFEST}"):
            self.assertIn(line, result.stdout)
        self.assertIn(f"Installed items: {len(ITEMS.selected())} in 1 location(s)", result.stdout)

    def test_running_it_again_replaces_owned_items_with_the_same_content_and_moves_nothing_aside(self):
        box = Sandbox(self)
        box.install()
        before = without(snapshot(box.dest), MANIFEST)
        result = box.install()
        self.assertEqual(result.returncode, 0, listing(result))
        self.assertEqual(without(snapshot(box.dest), MANIFEST), before)
        self.assertEqual(read_manifest(box.dest).items, ITEMS.selected())
        self.assertEqual(box.backups(), [])
        self.assertIn("Moved aside: nothing", result.stdout)

    def test_an_upgrade_replaces_owned_items_and_removes_only_owned_stale_ones(self):
        box = Sandbox(self)
        box.install()
        notes = box.dest / "my-notes"
        notes.mkdir()
        (notes / "todo.md").write_text("mine\n", encoding="utf-8")
        loose = box.dest / "loose.txt"
        loose.write_text("also mine\n", encoding="utf-8")
        mine = (snapshot(notes), snapshot(loose))
        retired = ("investigate", "package-manifest.yaml", "benchmark")
        box.publish("v2", drop=retired)

        result = box.install()

        self.assertEqual(result.returncode, 0, listing(result))
        for name in retired:
            self.assertFalse((box.dest / name).exists(), f"{name} is no longer shipped and was owned")
        self.assertIn("removed, no longer shipped: " + " ".join(retired), result.stdout)
        self.assert_installed(box, names=[name for name in ITEMS.selected() if name not in retired and name != "mcp-tools.md"])
        self.assertEqual((box.dest / "admiral" / "SKILL.md").read_text(encoding="utf-8"), "admiral v2\n")
        self.assertEqual((snapshot(notes), snapshot(loose)), mine)
        self.assertEqual(box.backups(), [])
        self.assertEqual(read_manifest(box.dest).items, [name for name in ITEMS.selected() if name not in retired])

    def test_user_items_named_like_managed_ones_survive_a_first_install_byte_for_byte(self):
        box = Sandbox(self)
        outside = box.root / "elsewhere"
        outside.mkdir()
        (outside / "precious.txt").write_text("not the installer's\n", encoding="utf-8")
        box.dest.mkdir(parents=True)
        (box.dest / "review" / "deep").mkdir(parents=True)
        (box.dest / "review" / "SKILL.md").write_text("my own review skill\n", encoding="utf-8")
        (box.dest / "review" / "deep" / "notes.md").write_text("nested\n", encoding="utf-8")
        (box.dest / "scripts").mkdir()
        tool = box.dest / "scripts" / "tool.sh"
        tool.write_bytes(b"\x00\x01binary\xff\n")
        tool.chmod(0o755)
        (box.dest / "gates.yaml").write_text("mine: true\n", encoding="utf-8")
        (box.dest / "qa").symlink_to(outside, target_is_directory=True)
        (box.dest / "unrelated").mkdir()
        (box.dest / "unrelated" / "SKILL.md").write_text("not ours\n", encoding="utf-8")
        planted = {name: snapshot(box.dest / name) for name in ("review", "scripts", "gates.yaml", "qa")}
        untouched = snapshot(box.dest / "unrelated")
        outside_before = snapshot(outside)

        result = box.install()

        self.assertEqual(result.returncode, 0, listing(result))
        backup = self.only_backup(box)
        for name, before in planted.items():
            self.assertEqual(snapshot(backup / name), before, f"{name} was not kept intact in the backup")
        self.assertEqual(snapshot(box.dest / "unrelated"), untouched)
        self.assertEqual(snapshot(outside), outside_before)
        self.assertFalse((box.dest / "qa").is_symlink())
        self.assert_installed(box)
        for name in planted:
            self.assertIn(name, result.stdout)
        self.assertIn(str(backup), result.stdout)
        self.assertIn(str(backup), result.stdout.split("Moved aside, kept unchanged:")[1])

    def test_a_user_directory_that_replaces_an_owned_one_survives_the_next_upgrade(self):
        box = Sandbox(self)
        box.install()
        shutil.rmtree(box.dest / "review")
        (box.dest / "review").mkdir()
        (box.dest / "review" / "mine.md").write_text("my own review skill\n", encoding="utf-8")
        mine = snapshot(box.dest / "review")
        box.publish("v2")

        result = box.install()

        self.assertEqual(result.returncode, 0, listing(result))
        backup = self.only_backup(box)
        self.assertEqual(snapshot(backup / "review"), mine)
        self.assertEqual((box.dest / "review" / "SKILL.md").read_text(encoding="utf-8"), "review v2\n")
        self.assertTrue((box.dest / "review" / MARKER).is_file())

    def test_an_install_from_before_the_ownership_records_is_backed_up_not_deleted(self):
        box = Sandbox(self)
        box.dest.mkdir(parents=True)
        for name in ITEMS.selected():
            source = box.repo / "skills" / name
            if source.is_dir():
                shutil.copytree(source, box.dest / name)
            else:
                shutil.copy2(source, box.dest / name)
        (box.dest / "safety-guardrails" / "guard").mkdir(parents=True)
        (box.dest / "safety-guardrails" / "guard" / "SKILL.md").write_text("old layout\n", encoding="utf-8")
        (box.dest / "references").mkdir()
        (box.dest / "references" / "handoff-templates.md").write_text("old layout\n", encoding="utf-8")
        (box.dest / "testing-and-qa").mkdir()
        (box.dest / "testing-and-qa" / "mine.md").write_text("a user directory that shares a legacy name\n", encoding="utf-8")
        old = {name: snapshot(box.dest / name) for name in ITEMS.selected() if name != "mcp-tools.md"}
        old_layout = {name: snapshot(box.dest / name) for name in ("safety-guardrails", "references")}
        user_dir = snapshot(box.dest / "testing-and-qa")
        box.publish("v2")

        result = box.install()

        self.assertEqual(result.returncode, 0, listing(result))
        backup = self.only_backup(box)
        for name, before in {**old, **old_layout}.items():
            self.assertEqual(snapshot(backup / name), before, f"{name} was not kept intact in the backup")
        self.assertFalse((box.dest / "safety-guardrails").exists())
        self.assertFalse((box.dest / "references").exists())
        self.assertEqual(snapshot(box.dest / "testing-and-qa"), user_dir, "an unrecognised directory must stay put")
        self.assert_installed(box, names=[name for name in ITEMS.selected() if name != "mcp-tools.md"])
        self.assertIn("kept, yours: mcp-tools.md", result.stdout)
        again = box.install()
        self.assertEqual(again.returncode, 0, listing(again))
        self.assertEqual(box.backups(), [backup], "a second run has nothing left to move aside")

    def test_dangerous_destinations_are_refused_before_anything_is_written(self):
        box = Sandbox(self)
        (box.home / "scripts").mkdir()
        (box.home / "scripts" / "keep.txt").write_text("mine\n", encoding="utf-8")
        (box.home / "build").mkdir()
        (box.root / "afile").write_text("not a directory\n", encoding="utf-8")
        (box.root / "link-to-home").symlink_to(box.home, target_is_directory=True)
        cases = {
            "the home directory": (str(box.home), "home directory or one of its parents"),
            "a parent of the home directory": (str(box.home.parent), "home directory or one of its parents"),
            "a symlink to the home directory": (str(box.root / "link-to-home"), "home directory or one of its parents"),
            "the checkout": (str(box.repo), "contains the Supreme Team checkout"),
            "the source tree": (str(box.repo / "skills"), "inside the skills source directory"),
            "inside the source tree": (str(box.repo / "skills" / "out"), "inside the skills source directory"),
            "an empty path": ("", "destination is empty"),
            "a file": (str(box.root / "afile"), "not a directory"),
            "an unresolved parent reference": (str(box.root / "missing" / ".." / "out"), "contains '..'"),
        }
        for label, (path, message) in cases.items():
            for flags in (("--dry-run",), ()):
                with self.subTest(destination=label, flags=flags):
                    before = snapshot(box.root)
                    result = box.run("--destination", path, *flags)
                    self.assertNotEqual(result.returncode, 0, listing(result))
                    self.assertIn(message, result.stderr)
                    self.assertEqual(snapshot(box.root), before, "a refused install must write nothing")
        # The filesystem root is only ever tried as a dry run: were the refusal to
        # regress, a real run would start writing into it.
        before = snapshot(box.root)
        result = box.run("--dry-run", "--destination", "/")
        self.assertNotEqual(result.returncode, 0, listing(result))
        self.assertIn("filesystem root", result.stderr)
        self.assertEqual(snapshot(box.root), before)

    def test_the_current_directory_is_refused_unless_it_already_holds_an_install(self):
        box = Sandbox(self)
        project = box.root / "project"
        (project / "scripts").mkdir(parents=True)
        (project / "scripts" / "run.sh").write_text("the project's own\n", encoding="utf-8")
        (project / "build").mkdir()
        before = snapshot(box.root)

        result = box.run("--destination", ".", cwd=project)

        self.assertNotEqual(result.returncode, 0, listing(result))
        self.assertIn("it is the current directory and holds no Supreme Team install", result.stderr)
        self.assertEqual(snapshot(box.root), before, "the project's scripts/ and build/ must not be touched")

        self.assertEqual(box.install().returncode, 0)
        again = box.run("--destination", ".", cwd=box.dest)
        self.assertEqual(again.returncode, 0, listing(again))

        empty = box.root / "empty-skills"
        empty.mkdir()
        deliberate = box.run("--destination", str(empty), cwd=empty)
        self.assertEqual(deliberate.returncode, 0, "a full path to the current directory is deliberate: " + listing(deliberate))
        self.assertTrue((empty / MANIFEST).is_file())

    def test_an_empty_home_is_refused_instead_of_installing_at_the_filesystem_root(self):
        box = Sandbox(self)
        before = snapshot(box.root)

        result = box.run("--dry-run", env={"HOME": ""})

        self.assertNotEqual(result.returncode, 0, listing(result))
        self.assertIn("HOME is not set", result.stderr)
        self.assertNotIn("/.agents/skills", result.stdout)
        self.assertEqual(snapshot(box.root), before)
        self.assertEqual(box.run("--help", env={"HOME": ""}).returncode, 0, "--help needs no HOME")

    def test_every_mirror_destination_is_checked_before_the_first_one_is_written(self):
        box = Sandbox(self)
        result = box.install("--target", "claude", "--claude-destination", str(box.home))
        self.assertNotEqual(result.returncode, 0, listing(result))
        self.assertIn("claude destination", result.stderr)
        self.assertFalse(box.dest.exists(), "the common target must not be written when a mirror is refused")

    def test_a_dry_run_reports_the_plan_and_writes_nothing(self):
        box = Sandbox(self)
        box.install()
        box.publish("v2", drop=("investigate",))
        shutil.rmtree(box.dest / "qa")
        (box.dest / "qa").mkdir()
        (box.dest / "qa" / "mine.md").write_text("mine\n", encoding="utf-8")
        before = snapshot(box.root)

        result = box.install("--dry-run")

        self.assertEqual(result.returncode, 0, listing(result))
        self.assertEqual(snapshot(box.root), before)
        for line in ("Dry run: nothing will be written.", "would replace:", "would keep, yours: mcp-tools.md",
                     "would remove, no longer shipped: investigate", "would move aside to",
                     "Dry run complete: nothing was written."):
            self.assertIn(line, result.stdout)
        self.assertNotIn("Supreme Team installation complete.", result.stdout)

    def test_a_dry_run_never_registers_hooks(self):
        box = Sandbox(self)
        marker = box.root / "helper-ran"
        (box.repo / "scripts" / "install_hooks.py").write_text(
            f"import pathlib\npathlib.Path({str(marker)!r}).write_text('ran')\n", encoding="utf-8")
        result = box.install("--dry-run", "--register-hooks", "--target", "claude", "--claude-destination", str(box.home / ".claude" / "skills"))
        self.assertEqual(result.returncode, 0, listing(result))
        self.assertFalse(marker.exists())

    def test_an_existing_mcp_registry_is_never_replaced_and_a_missing_one_is_restored(self):
        box = Sandbox(self)
        box.install()
        registry = box.dest / "mcp-tools.md"
        self.assertEqual(registry.read_text(encoding="utf-8"), "mcp-tools.md v1\n")
        registry.write_text("refreshed by admiral\n", encoding="utf-8")
        box.publish("v2")

        result = box.install()
        self.assertEqual(registry.read_text(encoding="utf-8"), "refreshed by admiral\n")
        self.assertIn("kept, yours: mcp-tools.md", result.stdout)
        narrower = box.install("--team", "design")
        self.assertEqual(narrower.returncode, 0, listing(narrower))
        self.assertEqual(registry.read_text(encoding="utf-8"), "refreshed by admiral\n")
        self.assertIn("mcp-tools.md", read_manifest(box.dest).items)

        registry.unlink()
        box.install()
        self.assertEqual(registry.read_text(encoding="utf-8"), "mcp-tools.md v2\n")

    def test_a_narrower_team_selection_removes_only_what_this_installer_installed(self):
        box = Sandbox(self)
        box.install()
        (box.dest / "build-notes").mkdir()
        (box.dest / "build-notes" / "mine.md").write_text("mine\n", encoding="utf-8")
        mine = snapshot(box.dest / "build-notes")

        result = box.install("--team", "DESIGN", "--team", "design")

        self.assertEqual(result.returncode, 0, listing(result))
        kept = ITEMS.selected("design")
        self.assertEqual(read_manifest(box.dest).items, kept)
        self.assertEqual(read_manifest(box.dest).teams, ["design"])
        for name in ITEMS.selected():
            self.assertEqual((box.dest / name).exists(), name in kept, name)
        self.assertEqual(snapshot(box.dest / "build-notes"), mine)
        self.assertIn("Teams: design", result.stdout)

    def test_unknown_teams_are_refused_and_named_from_the_item_list(self):
        box = Sandbox(self)
        result = box.install("--team", "nope")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown team 'nope'", result.stderr)
        for team in ITEMS.teams:
            self.assertIn(team, result.stderr)
        self.assertFalse(box.dest.exists())

    def test_a_copy_that_fails_leaves_the_previous_install_untouched_and_no_staging_directory(self):
        box = Sandbox(self)
        box.install()
        box.publish("v2")
        before = snapshot(box.dest)
        box.shim("cp", 'for arg in "$@"; do\n  if [ "$arg" = "$FAIL_COPY_OF" ]; then echo "cp: injected failure" >&2; exit 1; fi\ndone')

        result = box.install(env={"FAIL_COPY_OF": str(box.repo / "skills" / "review")})

        self.assertNotEqual(result.returncode, 0, listing(result))
        self.assertEqual(snapshot(box.dest), before, "a failed copy must not change the installed tree")
        self.assertEqual(box.stages(), [])
        self.assertEqual(box.backups(), [])

    def test_a_swap_that_fails_puts_the_previous_copy_back_and_leaves_no_half_item(self):
        box = Sandbox(self)
        box.install()
        v1 = {name: without(snapshot(box.dest / name), MARKER) for name in ITEMS.selected()}
        box.publish("v2")
        v2 = {name: snapshot(box.repo / "skills" / name) for name in ITEMS.selected()}
        flag = box.root / "failed-once"
        box.shim("mv", 'for last in "$@"; do :; done\n'
                       'if [ "$last" = "$FAIL_MOVE_TO" ] && [ ! -e "$FAIL_FLAG" ]; then\n'
                       '  : > "$FAIL_FLAG"; echo "mv: injected failure" >&2; exit 1\nfi')

        result = box.install(env={"FAIL_MOVE_TO": str(box.dest / "review"), "FAIL_FLAG": str(flag)})

        self.assertNotEqual(result.returncode, 0, listing(result))
        self.assertIn("the previous copy was put back", result.stderr)
        for name in ITEMS.selected():
            now = without(snapshot(box.dest / name), MARKER)
            self.assertIn(now, (v1[name], v2[name]), f"{name} is neither the old nor the new copy")
        self.assertEqual(without(snapshot(box.dest / "review"), MARKER), v1["review"])
        self.assertEqual(box.stages(), [])
        self.assertEqual(box.backups(), [])

    def test_an_interrupted_run_clears_its_staging_directory_and_leaves_the_install_untouched(self):
        box = Sandbox(self)
        box.install()
        box.publish("v2")
        before = snapshot(box.dest)
        # The shim signals the installer, then succeeds, so only the signal handling can stop the run.
        box.shim("cp", 'for arg in "$@"; do\n  if [ "$arg" = "$INTERRUPT_ON" ]; then kill -TERM "$PPID"; sleep 1; exit 0; fi\ndone')

        result = box.install(env={"INTERRUPT_ON": str(box.repo / "skills" / "review")})

        self.assertEqual(result.returncode, 143, listing(result))
        self.assertEqual(snapshot(box.dest), before)
        self.assertEqual(box.stages(), [])
        self.assertEqual(box.backups(), [])

    def test_a_mirror_that_is_a_link_to_another_root_does_not_displace_the_install_it_points_at(self):
        box = Sandbox(self)
        box.dest.mkdir(parents=True)
        claude = box.home / ".claude" / "skills"
        claude.parent.mkdir()
        claude.symlink_to(box.dest, target_is_directory=True)

        result = box.install("--target", "claude", "--claude-destination", str(claude))

        self.assertEqual(result.returncode, 0, listing(result))
        self.assertEqual(box.backups(), [])
        self.assert_installed(box)
        self.assertEqual(read_manifest(box.dest).items, ITEMS.selected())

    def test_windows_line_endings_in_the_item_list_and_the_manifest_are_read(self):
        box = Sandbox(self)
        items = box.repo / "scripts" / "install-items.txt"
        items.write_bytes(items.read_bytes().replace(b"\n", b"\r\n"))
        first = box.install()
        self.assertEqual(first.returncode, 0, listing(first))
        self.assertEqual(read_manifest(box.dest).items, ITEMS.selected())
        record = box.dest / MANIFEST
        record.write_bytes(record.read_bytes().replace(b"\n", b"\r\n"))

        second = box.install()

        self.assertEqual(second.returncode, 0, listing(second))
        self.assertEqual(box.backups(), [], "a CRLF manifest must still identify the files it lists as owned")

    def test_a_source_item_that_is_a_link_is_never_written_through(self):
        box = Sandbox(self)
        linked = box.root / "linked-source"
        linked.mkdir()
        (linked / "SKILL.md").write_text("outside the catalog\n", encoding="utf-8")
        shutil.rmtree(box.repo / "skills" / "qa")
        (box.repo / "skills" / "qa").symlink_to(linked, target_is_directory=True)
        before = snapshot(linked)

        result = box.install()

        self.assertEqual(result.returncode, 0, listing(result))
        self.assertEqual(snapshot(linked), before, "the ownership marker must not be written into the source tree")

    def test_a_swap_that_fails_puts_a_users_item_back_where_it_was(self):
        box = Sandbox(self)
        box.dest.mkdir(parents=True)
        (box.dest / "qa").mkdir()
        (box.dest / "qa" / "SKILL.md").write_text("my own qa skill\n", encoding="utf-8")
        mine = snapshot(box.dest / "qa")
        box.shim("mv", 'for last in "$@"; do :; done\n'
                       'if [ "$last" = "$FAIL_MOVE_TO" ] && [ ! -e "$FAIL_FLAG" ]; then\n'
                       '  : > "$FAIL_FLAG"; echo "mv: injected failure" >&2; exit 1\nfi')

        result = box.install(env={"FAIL_MOVE_TO": str(box.dest / "qa"), "FAIL_FLAG": str(box.root / "failed-once")})

        self.assertNotEqual(result.returncode, 0, listing(result))
        self.assertIn("the previous copy was put back", result.stderr)
        self.assertEqual(snapshot(box.dest / "qa"), mine, "the user's item must be back where it was, unchanged")
        for backup in box.backups():
            self.assertFalse((backup / "qa").exists())
        self.assertEqual(box.stages(), [])

    def test_an_abort_between_the_two_renames_of_an_item_puts_the_previous_copy_back(self):
        box = Sandbox(self)
        box.install()
        v1 = {name: without(snapshot(box.dest / name), MARKER) for name in ITEMS.selected()}
        box.publish("v2")
        v2 = {name: snapshot(box.repo / "skills" / name) for name in ITEMS.selected()}
        # Once, the shim signals the installer instead of moving the staged copy of
        # `review` into place, so the previous copy is at that moment only in the staging directory.
        box.shim("mv", 'for last in "$@"; do :; done\n'
                       'if [ "$last" = "$INTERRUPT_MOVE_TO" ] && [ ! -e "$INTERRUPT_FLAG" ]; then\n'
                       '  : > "$INTERRUPT_FLAG"; kill -TERM "$PPID"; sleep 1; exit 0\nfi')

        result = box.install(env={"INTERRUPT_MOVE_TO": str(box.dest / "review"), "INTERRUPT_FLAG": str(box.root / "signalled")})

        self.assertEqual(result.returncode, 143, listing(result))
        self.assertTrue((box.dest / "review").is_dir(), "the item that was being replaced is missing")
        for name in ITEMS.selected():
            now = without(snapshot(box.dest / name), MARKER)
            self.assertIn(now, (v1[name], v2[name]), f"{name} is neither the old nor the new copy")
        self.assertEqual(without(snapshot(box.dest / "review"), MARKER), v1["review"])
        self.assertEqual(box.stages(), [])
        self.assertEqual(box.backups(), [])

    def test_only_a_staging_directory_the_installer_created_is_cleared(self):
        box = Sandbox(self)
        box.install()
        ours = box.dest / ".supremeteam-stage.abc123"
        (ours / "new").mkdir(parents=True)
        (ours / STAGE_MARKER).write_text("supremeteam-stage 1\n", encoding="utf-8")
        (ours / "new" / "half-copied.txt").write_text("left by an interrupted run\n", encoding="utf-8")
        users = box.dest / ".supremeteam-stage.notes"
        users.mkdir()
        (users / "todo.md").write_text("mine\n", encoding="utf-8")
        mine = snapshot(users)

        result = box.install()

        self.assertEqual(result.returncode, 0, listing(result))
        self.assertFalse(ours.exists())
        self.assertEqual(snapshot(users), mine)

    def test_a_manifest_cannot_point_the_installer_outside_the_root_or_at_unmarked_directories(self):
        box = Sandbox(self)
        box.install()
        victim = box.dest.parent / "victim"
        victim.mkdir()
        (victim / "data.txt").write_text("outside the install root\n", encoding="utf-8")
        hidden = box.dest / ".hidden"
        hidden.write_text("not a managed name\n", encoding="utf-8")
        (box.dest / "listed-but-unmarked").mkdir()
        (box.dest / "listed-but-unmarked" / "mine.md").write_text("mine\n", encoding="utf-8")
        with (box.dest / MANIFEST).open("a", encoding="utf-8") as record:
            for name in ("../victim", ".hidden", "a/b", "-rf", "listed-but-unmarked"):
                record.write(f"item {name}\n")
        outside = (snapshot(victim), snapshot(hidden), snapshot(box.dest / "listed-but-unmarked"))

        result = box.install()

        self.assertEqual(result.returncode, 0, listing(result))
        self.assertEqual((snapshot(victim), snapshot(hidden), snapshot(box.dest / "listed-but-unmarked")), outside)

    def test_a_file_where_the_record_belongs_is_moved_aside_not_overwritten(self):
        box = Sandbox(self)
        box.install()
        record = box.dest / MANIFEST
        record.write_text("something else entirely\nitem admiral\n", encoding="utf-8")
        mine = snapshot(record)

        result = box.install()

        self.assertEqual(result.returncode, 0, listing(result))
        self.assertIn("not a Supreme Team install record", result.stderr)
        backup = self.only_backup(box)
        self.assertEqual(snapshot(backup / MANIFEST), mine, "a file that is not a record must be kept, not overwritten")
        self.assertEqual(read_manifest(box.dest).items, ITEMS.selected())

    def test_a_link_where_the_record_belongs_is_moved_aside_as_a_link_even_to_a_valid_record(self):
        box = Sandbox(self)
        box.dest.mkdir(parents=True)
        shared = box.root / "shared-record"
        shared.write_text("supremeteam-manifest 1\nteams design\nitem admiral\n", encoding="utf-8")
        (box.dest / MANIFEST).symlink_to(shared)

        result = box.install()

        self.assertEqual(result.returncode, 0, listing(result))
        backup = self.only_backup(box)
        self.assertTrue((backup / MANIFEST).is_symlink(), "the link must be kept, not replaced")
        self.assertEqual((backup / MANIFEST).resolve(), shared)
        self.assertEqual(shared.read_text(encoding="utf-8"), "supremeteam-manifest 1\nteams design\nitem admiral\n")
        self.assertFalse((box.dest / MANIFEST).is_symlink())
        self.assertEqual(read_manifest(box.dest).items, ITEMS.selected())

    def test_a_directory_where_the_manifest_belongs_stops_the_install_before_any_change(self):
        box = Sandbox(self)
        box.dest.mkdir(parents=True)
        (box.dest / MANIFEST).mkdir()
        before = snapshot(box.root)

        result = box.install()

        self.assertNotEqual(result.returncode, 0, listing(result))
        self.assertIn("is a directory", result.stderr)
        self.assertEqual(snapshot(box.root), before)

    def test_hook_registration_is_reported_as_skipped_when_no_host_is_detected(self):
        box = Sandbox(self)

        result = box.install("--register-hooks")

        self.assertEqual(result.returncode, 0, listing(result))
        self.assertIn("Hook registration skipped: no host targets were detected", result.stdout)
        self.assertIn("Hook registration: skipped (no host detected)", result.stdout)
        self.assertNotIn("Hook registration: requested", result.stdout)
        self.assertNotIn("Hook registration: completed", result.stdout)

    def test_hook_registration_is_reported_as_completed_only_after_the_helper_succeeds(self):
        box = Sandbox(self)
        ran = box.root / "helper-ran"
        (box.repo / "scripts" / "install_hooks.py").write_text(
            f"import pathlib\npathlib.Path({str(ran)!r}).write_text('ran')\n", encoding="utf-8")

        result = box.install("--register-hooks", "--target", "claude", "--claude-destination", str(box.home / ".claude" / "skills"))

        self.assertEqual(result.returncode, 0, listing(result))
        self.assertTrue(ran.is_file())
        self.assertIn("Hook registration: completed", result.stdout)

    def test_mirrors_are_installed_and_recorded_separately(self):
        box = Sandbox(self)
        claude = box.home / ".claude" / "skills"
        result = box.install("--target", "claude", "--claude-destination", str(claude))
        self.assertEqual(result.returncode, 0, listing(result))
        self.assert_installed(box)
        self.assert_installed(box, claude)
        self.assertEqual(read_manifest(claude).items, ITEMS.selected())
        self.assertIn(f"Host mirrors: claude={claude}", result.stdout)
        self.assertIn(f"Installed items: {len(ITEMS.selected())} in 2 location(s)", result.stdout)

    def test_a_detected_codex_mirror_is_refreshed_only_when_it_holds_a_supreme_team_install(self):
        box = Sandbox(self)
        codex = box.home / ".codex" / "skills"
        codex.mkdir(parents=True)
        (codex / "qa").mkdir()
        (codex / "qa" / "SKILL.md").write_text("someone else's qa skill\n", encoding="utf-8")
        theirs = snapshot(codex / "qa")

        result = box.install()
        self.assertEqual(result.returncode, 0, listing(result))
        self.assertIn("Host targets: codex", result.stdout)
        self.assertIn("Host mirrors: none", result.stdout)
        self.assertEqual(snapshot(codex / "qa"), theirs, "a same-named skill is no evidence of an install")

        (codex / "admiral").mkdir()
        (codex / "admiral" / "SKILL.md").write_text("an install from before the records\n", encoding="utf-8")
        (codex / "gatekeeper-admiral").mkdir()
        (codex / "gatekeeper-admiral" / "SKILL.md").write_text("an install from before the records\n", encoding="utf-8")
        result = box.install()
        self.assertIn(f"Mirroring Supreme Team to {codex}", result.stdout)
        self.assertTrue((codex / MANIFEST).is_file())

    def test_naming_a_host_explicitly_installs_its_mirror(self):
        box = Sandbox(self)
        codex = box.home / ".codex" / "skills"

        result = box.install("--target", "codex", "--codex-destination", str(codex))

        self.assertEqual(result.returncode, 0, listing(result))
        self.assertIn(f"Mirroring Supreme Team to {codex}", result.stdout)
        self.assert_installed(box, codex)

    def test_help_lists_every_flag_the_parser_accepts(self):
        box = Sandbox(self)
        result = box.run("--help")
        self.assertEqual(result.returncode, 0, listing(result))
        parsed = set(re.findall(r"^        (--[a-z-]+)\)$", INSTALL_SH.read_text(encoding="utf-8"), re.M))
        documented = set(re.findall(r"^  (--[a-z-]+)", result.stdout, re.M))
        self.assertEqual(parsed, documented)
        self.assertFalse(box.dest.exists())

    def stub_hook_helper(self, box: Sandbox) -> Path:
        """A stand-in for install_hooks.py that records the arguments it was given."""
        record = box.root / "helper-args"
        (box.repo / "scripts" / "install_hooks.py").write_text(
            f"import pathlib, sys\npathlib.Path({str(record)!r}).write_text(' '.join(sys.argv[1:]))\n", encoding="utf-8")
        return record

    def test_copilot_is_a_target_that_registers_hooks_and_installs_no_mirror(self):
        """The hook helper supports Copilot; the installers did not let anyone name it."""
        box = Sandbox(self)
        record = self.stub_hook_helper(box)
        result = box.install("--target", "Copilot", "--register-hooks", "--hooks-yes")
        self.assertEqual(result.returncode, 0, listing(result))
        self.assertIn("--target copilot", record.read_text(encoding="utf-8"))
        for line in ("Host targets: copilot", "Host mirrors: none", f"Installed items: {len(ITEMS.selected())} in 1 location(s)",
                     "Hook registration: completed"):
            self.assertIn(line, result.stdout)
        self.assertEqual([entry.name for entry in box.home.iterdir()], [".agents"], "Copilot has no skills folder to mirror into")

    def test_auto_never_selects_copilot(self):
        box = Sandbox(self)
        (box.home / ".config" / "github-copilot").mkdir(parents=True)
        result = box.install()
        self.assertEqual(result.returncode, 0, listing(result))
        self.assertIn("Host targets: none detected", result.stdout)

    def test_the_target_help_and_the_unknown_target_message_name_copilot(self):
        box = Sandbox(self)
        self.assertIn("opencode, copilot", box.run("--help").stdout)
        refused = box.install("--target", "windsurf")
        self.assertEqual(refused.returncode, 1, listing(refused))
        self.assertIn("opencode, or copilot", refused.stderr)

    def test_a_host_whose_python_is_only_python3_13_still_registers_hooks(self):
        """DX-12: the probe tried python3 and python, so a host with only a versioned name warned and then refused."""
        box = Sandbox(self)
        (box.bin / "python3").rename(box.bin / "python3.13")
        record = self.stub_hook_helper(box)
        result = box.install("--target", "claude", "--claude-destination", str(box.home / ".claude" / "skills"), "--register-hooks", "--hooks-yes")
        self.assertEqual(result.returncode, 0, listing(result))
        self.assertNotIn("no Python", result.stderr)
        self.assertIn("--target claude", record.read_text(encoding="utf-8"))

    def test_without_any_python_the_warning_stays_and_registration_is_refused(self):
        box = Sandbox(self)
        (box.bin / "python3").unlink()
        result = box.install("--target", "claude", "--claude-destination", str(box.home / ".claude" / "skills"), "--register-hooks")
        self.assertEqual(result.returncode, 1, listing(result))
        self.assertIn("no Python 3.13+ interpreter was found", result.stderr)
        self.assertIn("Python 3.13 or newer is required to register runtime harness hooks", result.stderr)


@unittest.skipUnless(RUNS_BASH, "the installer tests run install.sh under bash on a POSIX host")
class RealCatalogTests(unittest.TestCase):
    def test_the_installer_installs_the_whole_shipped_catalog_from_the_real_tree(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        (root / "home").mkdir()
        build_path_directory(root / "bin")
        dest = root / "home" / ".agents" / "skills"

        result = subprocess.run(
            [BASH, str(INSTALL_SH), "--destination", str(dest)],
            cwd=str(root),
            env={"HOME": str(root / "home"), "PATH": str(root / "bin"), "LC_ALL": "C"},
            capture_output=True,
            text=True,
            timeout=300,
        )

        self.assertEqual(result.returncode, 0, listing(result))
        for name in ITEMS.selected():
            source = snapshot(SKILLS / name)
            installed = snapshot(dest / name)
            if (SKILLS / name).is_dir():
                installed = without(installed, MARKER)
            self.assertEqual(installed, source, f"{name} differs from skills/{name}")
        self.assertEqual(read_manifest(dest).items, ITEMS.selected())
        self.assertEqual(sorted(entry.name for entry in dest.iterdir()), sorted([*ITEMS.selected(), MANIFEST]))
        self.assertEqual((dest / "LICENSE").read_bytes(), (REPO / "LICENSE").read_bytes(), "the install carries the licence notice")


class ItemListTests(unittest.TestCase):
    def test_every_top_level_entry_of_skills_is_installed_by_exactly_one_record(self):
        listed = [name for name in ITEMS.core]
        for members in ITEMS.teams.values():
            listed.extend(members)
        on_disk = sorted(entry.name for entry in SKILLS.iterdir())
        self.assertEqual(sorted(listed), on_disk,
                         "install-items.txt and skills/ disagree; a new top-level entry needs a core or team record")

    def test_records_are_well_formed(self):
        name = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")
        names = [*ITEMS.core, *ITEMS.teams, *ITEMS.legacy]
        for members in [*ITEMS.teams.values(), *ITEMS.legacy.values()]:
            names.extend(members)
        for value in names:
            self.assertRegex(value, name)
        self.assertEqual(len(ITEMS.core), len(set(ITEMS.core)))
        self.assertTrue(set(ITEMS.seeds) <= set(ITEMS.core))
        for seed in ITEMS.seeds:
            self.assertTrue((SKILLS / seed).is_file(), f"{seed} is a seed but not a shipped file")
        self.assertFalse(set(ITEMS.legacy) & set(ITEMS.selected()), "a legacy directory must not be a current item")
        for team, members in ITEMS.teams.items():
            self.assertEqual(len(members), len(set(members)), team)

    def test_the_installed_licence_is_the_repository_licence(self):
        """An install carries only skills/, so the licence notice travels as the core item skills/LICENSE."""
        self.assertIn("LICENSE", ITEMS.core)
        self.assertEqual((SKILLS / "LICENSE").read_bytes(), (REPO / "LICENSE").read_bytes(),
                         "skills/LICENSE has to stay a copy of the repository LICENSE")

    def test_standalone_teams_match_the_team_manifest(self):
        roster = load_data(SKILLS / "team-manifest.yaml")
        for team in ("browser", "release", "safety", "testing"):
            self.assertEqual(sorted(ITEMS.teams[team]), sorted(roster[team]), team)
        for team in ("design", "build", "review"):
            self.assertEqual(ITEMS.teams[team], [team])

    def test_neither_installer_carries_an_item_list_of_its_own(self):
        # Each of these is named once for a reason other than listing it.
        reads = {
            "runtime-manifest.yaml": "the Python floor is read from it",
            "gatekeeper-admiral": "half of the signature of an install from before the records",
        }
        distinctive = sorted({name for name in ITEMS.selected() if "-" in name or "." in name} - set(reads))
        self.assertGreater(len(distinctive), 10)
        for path in (INSTALL_SH, INSTALL_PS1):
            text = path.read_text(encoding="utf-8")
            self.assertIn("install-items.txt", text)
            for name in distinctive:
                self.assertNotIn(name, text, f"{path.name} names {name} itself; the item list is install-items.txt")


def strip_comments(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def function_spans(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in re.finditer(r"^\w+\(\) \{\n.*?^\}$", text, re.M | re.S)]


def unguarded_array_expansions(text: str) -> list[tuple[int, str, str]]:
    """Expansions of a possibly-empty array that bash before 4.4 rejects under `set -u`.

    An array counts as possibly empty when it is declared `name=()` or filled by
    `read -a`. Its expansion is safe in the guarded form `${name[@]+"${name[@]}"}`,
    or after the function has returned early on `${#name[@]} -eq 0`. A length test
    (`${#name[@]}`) is always safe. This reads the text; it does not run bash.
    """
    empty = set(re.findall(r"\b([A-Za-z_]\w*)=\([ \t]*\)", text))
    empty |= set(re.findall(r"\bread[ \t]+(?:-\w+[ \t]+)*-a[ \t]+([A-Za-z_]\w*)", text))
    lines = text.splitlines()
    spans = function_spans(text)
    found = []
    for name in sorted(empty):
        guarded = re.compile(r'\$\{%s\[([@*])\]\+"\$\{%s\[\1\]\}"\}' % (re.escape(name), re.escape(name)))
        masked = guarded.sub(lambda match: " " * len(match.group(0)), text)
        early_return = re.compile(
            r"if \[\[ \$\{#%s\[@\]\} -eq 0 \]\]; then\n(?:[^\n]*\n)*?[ \t]*(?:return|exit)\b[^\n]*\n[ \t]*fi\b" % re.escape(name))
        for match in re.finditer(r"\$\{%s\[[@*]\]\}" % re.escape(name), masked):
            line_number = text.count("\n", 0, match.start()) + 1
            if lines[line_number - 1].lstrip().startswith("#"):
                continue
            enclosing = next(((start, end) for start, end in spans if start <= match.start() < end), None)
            if enclosing:
                guard = early_return.search(text, enclosing[0], match.start())
                if guard and guard.end() <= match.start():
                    continue
            found.append((line_number, name, lines[line_number - 1].strip()))
    return found


BASH4_ONLY = {
    "mapfile or readarray": r"\b(?:mapfile|readarray)\b",
    "associative array": r"\b(?:declare|local|typeset)\s+-[a-zA-Z]*A",
    "case-modifying expansion": r"\$\{[A-Za-z_]\w*(?:\^\^?|,,?)",
    "[[ -v var ]]": r"\[\[\s+-v\s",
    "|& pipe": r"\|&",
    "&>> redirect": r"&>>",
    "coproc": r"\bcoproc\b",
    "case fall-through": r";;&|;&",
    "nameref": r"\b(?:declare|local|typeset)\s+-[a-zA-Z]*n\b",
    "negative array index": r"\[-\d+\]",
    "parameter transformation": r"\$\{[A-Za-z_]\w*@[QEPAaKk]\}",
    "shopt option newer than 3.2": r"\bshopt\s+-s\s+(?:globstar|lastpipe|compat\w+)",
    "wait -n": r"\bwait\s+-n\b",
    "printf time format": r"printf[^\n]*%\([^)]*\)T",
    "declare -g": r"\bdeclare\s+-[a-zA-Z]*g",
}

GNU_ONLY_TOOLS = {
    "readlink -f": r"\breadlink\s+-f\b",
    "realpath": r"\brealpath\b",
    "sed -i": r"\bsed\s+(?:-\w+\s+)*-i\b",
    "stat -c": r"\bstat\s+-c\b",
    "date -d": r"\bdate\s+(?:-\w+\s+)*-d\b",
    "find -printf": r"-printf\b",
    "xargs -r": r"\bxargs\s+(?:-\w+\s+)*-r\b",
    "mv -T": r"\bmv\s+(?:-\w+\s+)*-T\b",
    "grep -P": r"\bgrep\s+(?:-\w+\s+)*-P\b",
    "sort -V": r"\bsort\s+(?:-\w+\s+)*-V\b",
}


def matches(patterns: dict[str, str], text: str) -> list[str]:
    body = strip_comments(text)
    return [name for name, pattern in patterns.items() if re.search(pattern, body)]


POWERSHELL_BUILTINS = {
    "Set-StrictMode", "Split-Path", "Join-Path", "New-Object", "Get-Content", "Test-Path", "Select-Object",
    "Get-ChildItem", "Where-Object", "Write-Warning", "Write-Host", "Write-Error", "Remove-Item", "Copy-Item",
    "Move-Item", "New-Item", "Out-Null", "Get-Command", "Get-Date", "ConvertFrom-Json", "ForEach-Object", "Get-Item",
    "Get-Location",
}


def powershell_code(text: str) -> str:
    """The script without comment lines and with every string literal emptied."""
    lines = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return re.sub(r'"(?:`.|[^"`])*"|\'[^\']*\'', '""', lines)


def powershell_parameters(text: str, function: str) -> list[str]:
    """Names in a function's param() block, found by balancing its parentheses."""
    start = text.index(f"function {function} {{") + len(f"function {function} {{")
    head = re.match(r"\s*param\(", text[start:])
    if head is None:
        return []
    opening = start + head.end()
    depth, position = 1, opening
    while depth:
        depth += {"(": 1, ")": -1}.get(text[position], 0)
        position += 1
    return re.findall(r"\$([A-Za-z]+)", text[opening:position - 1])


class BashCompatibilityTests(unittest.TestCase):
    """Static checks for the stock macOS bash 3.2, which this suite cannot run."""

    def setUp(self):
        self.text = INSTALL_SH.read_text(encoding="utf-8")

    def test_the_script_parses(self):
        if BASH is None:
            self.skipTest("bash is not available")
        result = subprocess.run([BASH, "-n", str(INSTALL_SH)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_possibly_empty_array_is_expanded_unguarded(self):
        self.assertIn("set -euo pipefail", self.text)
        self.assertEqual(unguarded_array_expansions(self.text), [],
                         "bash before 4.4 aborts on these under `set -u`; use ${name[@]+\"${name[@]}\"}")

    def test_the_guard_detector_flags_what_it_should(self):
        bad = 'set -u\nitems=()\nfor item in "${items[@]}"; do :; done\necho "${items[*]}"\n'
        self.assertEqual([hit[:2] for hit in unguarded_array_expansions(bad)], [(3, "items"), (4, "items")])
        read = 'set -u\nread -r -a parts <<< "$x"\ntouch "${parts[@]}"\n'
        self.assertEqual([hit[1] for hit in unguarded_array_expansions(read)], ["parts"])

    def test_the_guard_detector_accepts_what_it_should(self):
        good = ('items=()\nfor item in ${items[@]+"${items[@]}"}; do :; done\n'
                'echo "${items[*]+"${items[*]}"}"\necho "${#items[@]}"\n'
                'fixed=(a b)\nfor x in "${fixed[@]}"; do :; done\n# "${items[@]}" in a comment\n')
        self.assertEqual(unguarded_array_expansions(good), [])
        early = ('items=()\nuse() {\n    if [[ ${#items[@]} -eq 0 ]]; then\n        return\n    fi\n'
                 '    for item in "${items[@]}"; do :; done\n}\n')
        self.assertEqual(unguarded_array_expansions(early), [])
        late = ('items=()\nuse() {\n    for item in "${items[@]}"; do :; done\n'
                '    if [[ ${#items[@]} -eq 0 ]]; then\n        return\n    fi\n}\n')
        self.assertEqual(len(unguarded_array_expansions(late)), 1, "a guard after the use protects nothing")

    def test_no_bash_4_construct_is_used(self):
        self.assertEqual(matches(BASH4_ONLY, self.text), [])

    def test_the_bash_4_detector_flags_each_construct(self):
        examples = {
            "mapfile or readarray": "mapfile -t lines < file",
            "associative array": "declare -A seen",
            "case-modifying expansion": 'x="${name,,}"',
            "[[ -v var ]]": "[[ -v name ]]",
            "|& pipe": "cmd |& tee log",
            "&>> redirect": "cmd &>> log",
            "coproc": "coproc worker { :; }",
            "case fall-through": "case $x in a) :;;& b) :;; esac",
            "nameref": "local -n ref=name",
            "negative array index": 'echo "${items[-1]}"',
            "parameter transformation": 'echo "${name@Q}"',
            "shopt option newer than 3.2": "shopt -s globstar",
            "wait -n": "wait -n",
            "printf time format": "printf '%(%s)T' -1",
            "declare -g": "declare -g name=1",
        }
        self.assertEqual(sorted(examples), sorted(BASH4_ONLY), "every detector needs an example")
        for name, snippet in examples.items():
            self.assertEqual(matches(BASH4_ONLY, snippet), [name], snippet)
        self.assertEqual(matches(BASH4_ONLY, 'declare -a items\nlocal -r name=1\nx="${name:-y}"\n[[ -n "$x" ]]'), [])

    def test_no_gnu_only_tool_option_is_used(self):
        self.assertEqual(matches(GNU_ONLY_TOOLS, self.text), [], "macOS ships BSD tools")
        self.assertEqual(matches(GNU_ONLY_TOOLS, "readlink -f x; sed -i s/a/b/ f; date -d now"), ["readlink -f", "sed -i", "date -d"])
        self.assertEqual(matches(GNU_ONLY_TOOLS, "date -u +%Y; sed -n p f; ls -A d"), [])

    def test_the_only_recursive_delete_removes_the_installers_own_staging_directory(self):
        code = strip_comments(self.text)
        self.assertEqual(len(re.findall(r"\brm\s+-", code)), 1, "rm appears once")
        body = re.search(r"^remove_stage\(\) \{\n(.*?)^\}$", self.text, re.M | re.S).group(1)
        self.assertIn("rm -rf -- \"$path\"", body)
        self.assertIn(".supremeteam-stage.*", body)
        self.assertIn("$stage_marker_name", body)

    def test_destinations_are_checked_before_anything_is_installed(self):
        main = self.text[self.text.index("load_items\nassert_source_layout"):]
        self.assertLess(main.index("assert_safe_root"), main.index("install_supreme_team"))


class PowerShellParityTests(unittest.TestCase):
    """install.ps1 cannot run here; these checks keep it a structural mirror of install.sh."""

    def setUp(self):
        self.sh = INSTALL_SH.read_text(encoding="utf-8")
        self.ps = INSTALL_PS1.read_text(encoding="utf-8")

    def test_both_use_the_same_record_names(self):
        for value in (MANIFEST, MARKER, STAGE_MARKER, BACKUP_SUFFIX, "supremeteam-manifest 1",
                      "supremeteam-managed 1", "supremeteam-stage 1", ".supremeteam-stage.", "install-items.txt"):
            self.assertIn(value, self.sh)
            self.assertIn(value, self.ps)

    def test_both_accept_the_same_flags(self):
        bash_flags = {flag[2:].replace("-", "") for flag in re.findall(r"^        (--[a-z-]+)\)$", self.sh, re.M)}
        params = re.search(r"param\((.*?)\n\)", self.ps, re.S).group(1)
        ps_flags = {name.lower() for name in re.findall(r"\$([A-Za-z]+)(?:\s*=|\s*,|\s*$)", params, re.M)}
        self.assertEqual(bash_flags, ps_flags)

    def test_the_powershell_choices_are_the_item_lists_and_the_bash_choices(self):
        teams = re.search(r'ValidateSet\("All", (.*?)\)\]\s*\[string\[\]\]\$Team', self.ps, re.S).group(1)
        self.assertEqual([name.strip('" ').lower() for name in teams.split(",")], list(ITEMS.teams))
        targets = re.search(r'ValidateSet\("Auto", (.*?)\)\]\s*\[string\[\]\]\$Target', self.ps, re.S).group(1)
        hosts = [name.strip('" ').lower() for name in targets.split(",")]
        self.assertEqual(hosts, re.search(r"^\s+(codex(?:\|[a-z]+)+)\)$", self.sh, re.M).group(1).split("|"))
        self.assertIn("copilot", hosts, "the hook helper supports Copilot, so both installers must let it be named")

    def test_both_name_every_host_where_they_tell_the_operator_which_to_pass(self):
        hosts = ("codex", "claude", "cursor", "opencode", "copilot")
        skipped = re.search(r'Hook registration skipped: no host targets were detected\. Pass ([^"\n]*?) to choose explicitly', self.ps).group(1)
        for host in hosts:
            self.assertIn(host, skipped.lower())
        usage = re.search(r"One of: (.*?)\.\n", self.sh).group(1)
        self.assertEqual(usage.split(", ")[1:], list(hosts))
        refusal = re.search(r"Unknown target '\$target'\. Use ([^\"]*?)\.\"", self.sh).group(1)
        for host in hosts:
            self.assertIn(host, refusal)

    def test_both_probe_the_same_interpreter_names_and_the_powershell_one_adds_the_py_launcher(self):
        names = re.search(r"for candidate in ((?:python[\d.]*\s*)+); do", self.sh).group(1).split()
        self.assertEqual(names, ["python3", "python", "python3.14", "python3.13"])
        powershell = re.findall(r'Command = "(py(?:thon[\d.]*)?)"', self.ps)
        self.assertEqual(sorted(powershell), sorted(["py", *names]))
        self.assertEqual(powershell[-2:], names[-2:], "the versioned names are the last resort in both, newest first")

    def test_both_refuse_the_same_destinations_in_the_same_words(self):
        for message in ("Refusing to install into the filesystem root", "it is your home directory or one of its parents",
                        "it contains the Supreme Team checkout", "it is inside the skills source directory",
                        "it is the current directory and holds no Supreme Team install", "destination is empty", "exists and is not a directory", "is a directory; move it away",
                        "Cannot create the backup folder", "nothing was changed", "the previous copy was put back"):
            self.assertIn(message, self.sh)
            self.assertIn(message, self.ps)

    def test_both_report_the_same_summary_and_hook_status(self):
        for line in ("Supreme Team installation complete.", "Installed items:", "Moved aside, kept unchanged:", "Moved aside: nothing",
                     "Hook registration: ", "not requested", "skipped (no host detected)", "completed",
                     "Dry run: nothing will be written.", "Dry run complete: nothing was written.",
                     "would add", "would replace", "would keep, yours", "would remove, no longer shipped", "would move aside to",
                     "kept, yours", "removed, no longer shipped", "recorded in",
                     "moved aside, not installed by Supreme Team and unchanged, to"):
            self.assertIn(line, self.sh)
            self.assertIn(line, self.ps)

    def test_the_only_recursive_delete_is_the_staging_directory_in_both(self):
        code = "\n".join(line for line in self.ps.splitlines() if not line.lstrip().startswith("#"))
        self.assertEqual(len(re.findall(r"Remove-Item", code)), 1)
        body = re.search(r"function Remove-StageDirectory \{\n(.*?)\n\}\n", self.ps, re.S).group(1)
        self.assertIn("Remove-Item -LiteralPath $Path -Recurse -Force", body)
        self.assertIn(".supremeteam-stage.", body)
        self.assertIn("$stageMarkerName", body)
        # Windows PowerShell 5.1 can follow a link out of the tree, so links go first, unfollowed.
        self.assertIn("Remove-LinksWithin", body, "links inside the staging directory must be unlinked before it is deleted")
        self.assertLess(body.index("Remove-LinksWithin"), body.index("Remove-Item"))
        links = re.search(r"function Remove-LinksWithin \{\n(.*?)\n\}\n", self.ps, re.S).group(1)
        self.assertEqual(len(re.findall(r"\.Delete\(\)", code)), 1, "the only other delete unlinks a link")
        self.assertIn("Test-ReparsePoint", links.split(".Delete()")[0])

    def test_both_check_every_destination_before_installing_and_skip_hooks_on_a_dry_run(self):
        main = self.ps[self.ps.index("try {\n    Import-ItemList"):]
        self.assertLess(main.index("Assert-SafeRoot"), main.index("Install-SupremeTeam"))
        self.assertLess(main.index('Write-Host "Dry run complete'), main.index("Register-HarnessHooks"))
        shell_main = self.sh[self.sh.index("load_items\nassert_source_layout"):]
        self.assertLess(shell_main.index("Dry run complete"), shell_main.index("register_harness_hooks"))

    def test_every_call_names_a_defined_function_or_a_known_cmdlet_and_declared_parameters(self):
        code = powershell_code(self.ps)
        defined = re.findall(r"^function ([A-Z][a-z]+-[A-Za-z]+)", self.ps, re.M)
        self.assertEqual(len(defined), len(set(defined)), "a function is defined twice")
        used = set(re.findall(r"\b([A-Z][a-z]+-[A-Z][A-Za-z]+)\b", code))
        self.assertEqual(sorted(used - set(defined) - POWERSHELL_BUILTINS), [],
                         "called but neither defined here nor a known cmdlet")
        declared = {name: powershell_parameters(self.ps, name) for name in defined}
        value = (r"(?:\$[\w:]+(?:\.\w+)*|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)|\"[^\"]*\"|'[^']*'|"
                 r"@\((?:[^()]|\([^()]*\))*\)|[\w.\\-]+)")
        calls = 0
        for match in re.finditer(r"\b(%s)\b((?:\s+-\w+\s+%s)+)" % ("|".join(map(re.escape, defined)), value), code):
            for argument in re.finditer(r"\s+-(\w+)\s+" + value, match.group(2)):
                calls += 1
                self.assertIn(argument.group(1).lower(), {name.lower() for name in declared[match.group(1)]},
                              f"{match.group(1)} is called with -{argument.group(1)}, which it does not declare")
        self.assertGreater(calls, 40, "the call-site pattern stopped matching the script")

    def test_powershell_stays_within_windows_powershell_5_1_and_is_balanced(self):
        code = re.sub(r'"(?:`.|[^"`])*"|\'[^\']*\'', '""', "\n".join(
            line for line in self.ps.splitlines() if not line.lstrip().startswith("#")))
        for token in (r"\s&&\s", r"\s\|\|\s", r"\?\?", r"\?\.", r"\s\?\s.*\s:\s"):
            self.assertIsNone(re.search(token, code), f"PowerShell 7 syntax {token!r}")
        for opening, closing in ("{}", "()", "[]"):
            self.assertEqual(code.count(opening), code.count(closing), f"unbalanced {opening}{closing}")
        for match in re.finditer(r'"((?:`.|[^"`])*)"', self.ps):
            for variable in re.finditer(r"\$(\w+):(?!\w)", match.group(1)):
                self.assertIn(variable.group(1), ("env", "script", "global", "local"),
                              f"'${variable.group(1)}:' in a string is read as a drive-qualified variable; use ${{{variable.group(1)}}}:")


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.install = (REPO / "Install.md").read_text(encoding="utf-8")
        self.quick = (REPO / "QUICK-START.md").read_text(encoding="utf-8")

    def test_the_install_guide_describes_the_ownership_rules_the_installer_enforces(self):
        for term in (MANIFEST, MARKER, BACKUP_SUFFIX, "--dry-run", "-DryRun", "mcp-tools.md", "never deleted"):
            self.assertTrue(term in self.install, f"Install.md does not mention {term}")

    def test_the_remote_recipe_pins_a_ref_and_fails_on_http_errors(self):
        self.assertFalse("refs/heads" in self.install, "a branch archive moves; the recipe must download a tag or commit")
        self.assertEqual(self.install.count("/archive/$ref.zip"), 2, "both recipes download the pinned ref")
        self.assertRegex(self.install, r"curl\s[^\n]*--proto '=https'[^\n]* -[A-Za-z]*f")
        self.assertTrue("-ErrorAction Stop" in self.install, "the PowerShell download must stop on an HTTP error")
        self.assertFalse("-print -quit" in self.install, "the recipe must run the directory it verified, not the first match of find")

    def test_the_quick_start_sample_summary_matches_what_the_installer_prints(self):
        printed = INSTALL_SH.read_text(encoding="utf-8")
        for label in ("Supreme Team installation complete.", "Target:", "Host targets:", "Host mirrors:", "Teams:",
                      "Installed items:", "Moved aside", "Hook registration:"):
            self.assertTrue(label in self.quick, f"QUICK-START.md does not show {label!r}")
            self.assertTrue(label in printed, f"install.sh does not print {label!r}")
        for flag in ("--dry-run", "-DryRun"):
            self.assertTrue(flag in self.quick, f"QUICK-START.md does not document {flag}")

    def test_the_quick_start_no_longer_tells_an_agent_to_copy_skills_over_an_existing_folder(self):
        self.assertFalse("download the repo archive and copy skills/" in self.quick)


class McpRegistryTemplateTests(unittest.TestCase):
    """The shipped registry is a blank template, so no install starts from another host's tool list."""

    def setUp(self):
        self.text = (SKILLS / "mcp-tools.md").read_text(encoding="utf-8")
        head = re.match(r"---\n(.*?)\n---\n", self.text, re.S)
        self.assertIsNotNone(head)
        self.front = {}
        for line in head.group(1).splitlines():
            key, _, value = line.partition(":")
            self.front[key.strip()] = value.strip().strip('"')

    def test_the_timestamp_is_the_epoch_and_older_than_the_ttl(self):
        self.assertEqual(self.front["last_discovery_at"], "1970-01-01T00:00:00Z")
        age = datetime.now(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
        self.assertGreater(age.total_seconds() / 3600, int(self.front["discovery_ttl_hours"]))
        self.assertEqual(self.front["protocol_version"], "1")

    def test_it_names_no_host_and_lists_no_tool(self):
        self.assertEqual(self.front["host"], "")
        self.assertEqual(self.front["workspace"], "")
        rows = [line for line in self.text.splitlines() if line.startswith("|") and not re.match(r"^\|[\s|:-]+\|$", line)]
        self.assertEqual([row.split("|")[1].strip() for row in rows], ["Tool", "Tool"], "only the two table headers")
        for stale in ("codex_app", "codex_apps", "multi_agent_v1", "node_repl", "playwright", "2026-06-30"):
            self.assertNotIn(stale, self.text)

    def test_the_prose_still_describes_the_epoch_branch_admiral_relies_on(self):
        self.assertIn("epoch placeholder", self.text)
        self.assertIn("discovery_ttl_hours", self.text)


if __name__ == "__main__":
    unittest.main()
