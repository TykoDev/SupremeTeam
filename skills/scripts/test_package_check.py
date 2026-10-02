"""Regression coverage for package_check.py: what it names as residue and how it fails.

The residue checks were name-only and case-sensitive on POSIX, a tracked symlink
was zipped with its target's bytes under an innocent name, common credential files
passed, and a manifest that was not a mapping ended in a traceback instead of the
documented exit 2.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from package_check import REQUIRED_ASSET_GLOBS, RESIDUE_CLASSES, matches

SCRIPTS = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPTS.parent
PACKAGE_CHECK = SCRIPTS / "package_check.py"


def residue_class(relative: str) -> str | None:
    """The class a file name lands in, in the order the checker tries them."""
    return next((klass for klass, patterns in RESIDUE_CLASSES.items() if matches(relative, patterns)), None)


class HelpTests(unittest.TestCase):
    """CR-23: `--root` is the repository root here, the catalog directory in the other two scripts."""

    def test_the_help_names_the_directory_root_takes_and_the_one_it_does_not(self):
        proc = subprocess.run([sys.executable, str(PACKAGE_CHECK), "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(0, proc.returncode, proc.stderr)
        flat = " ".join(proc.stdout.split())
        self.assertIn("the directory to package: the repository root, the directory that contains skills/", flat)
        self.assertIn("not skills/ itself", flat)


class ResidueClassTests(unittest.TestCase):
    def test_matching_folds_case_so_an_upper_case_secret_is_the_same_secret(self):
        for relative in (".ENV", ".Env.local", "app/.ENV.production", "deploy/KEY.PEM", "keys/Server.Key", "x/ID_RSA",
                         "Cert.P12", "app/.NPMRC", "CREDENTIALS.JSON"):
            with self.subTest(relative=relative):
                self.assertEqual(residue_class(relative), "secrets")
        self.assertEqual(residue_class("dist/App.ZIP"), "archives")
        self.assertEqual(residue_class("Pkg/__PyCache__/mod.PYC"), "interpreter-cache")

    def test_common_credential_files_are_secrets(self):
        for relative in ("id_rsa", "keys/id_dsa", "keys/id_ecdsa", "home/.ssh/id_ed25519", "cert.p12", "certs/site.pfx",
                         ".npmrc", "app/.netrc", ".pypirc", "creds/credentials.json", "creds/credentials.prod.json",
                         "server.key", "server.pem", ".env", "app/.env.local"):
            with self.subTest(relative=relative):
                self.assertEqual(residue_class(relative), "secrets")

    def test_public_keys_and_ordinary_credential_words_are_not_secrets(self):
        for relative in ("id_rsa.pub", "keys/id_ed25519.pub", "docs/credentials-guide.md", "credentials.md",
                         "docs/credentials.schema.md", "src/env.py", "environment.md", "npmrc-notes.md", "keyboard.md"):
            with self.subTest(relative=relative):
                self.assertIsNone(residue_class(relative))

    def test_a_nested_git_directory_and_supremeteam_state_are_residue(self):
        for relative in ("vendor/.git/config", "vendor/.git/objects/ab/cdef", "a/b/.git/HEAD"):
            with self.subTest(relative=relative):
                self.assertEqual(residue_class(relative), "vcs-metadata")
        for relative in (".supremeteam/state.json", "pkg/.supremeteam/x", "a/b/.SupremeTeam/x"):
            with self.subTest(relative=relative):
                self.assertEqual(residue_class(relative), "runtime-state")

    def test_a_git_file_is_not_a_repository_and_is_not_residue(self):
        """A worktree or a submodule keeps a `.git` file pointing at its repository."""
        for relative in (".git", "vendor/.git", ".claude/worktrees/agent-1/.git", "docs/git-notes.md", ".gitignore",
                         ".github/workflows/x.yml"):
            with self.subTest(relative=relative):
                self.assertIsNone(residue_class(relative))


class SharedResidueListTests(unittest.TestCase):
    """RR-V5-3: the secret and run-state names are one list, read from the skill packager's directory."""

    SHARED = SKILLS_DIR / "skill-maker" / "skill-creator" / "scripts" / "residue-classes.json"

    def test_the_shared_classes_match_what_the_checker_listed_before_it_read_them(self):
        self.assertEqual(RESIDUE_CLASSES["runtime-state"],
                         [".harness-state/**", "**/.harness-state/**", ".supremeteam/**", "**/.supremeteam/**"])
        self.assertEqual(RESIDUE_CLASSES["save-state"], ["skillset-saves/**", "**/skillset-saves/**"])
        self.assertEqual(RESIDUE_CLASSES["secrets"], [
            "**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/*.p12", "**/*.pfx",
            "**/id_rsa", "**/id_dsa", "**/id_ecdsa", "**/id_ed25519",
            "**/.npmrc", "**/.netrc", "**/.pypirc", "**/credentials*.json",
        ])

    def test_the_shared_file_names_are_lower_case_because_matching_folds_case(self):
        shared = json.loads(self.SHARED.read_text(encoding="utf-8"))
        self.assertEqual(sorted(shared), ["runtime-state", "save-state", "secrets"])
        for names in shared.values():
            self.assertEqual(names, [name.lower() for name in names])

    def shadow_tree(self, shared_text: str | None) -> tuple[Path, Path]:
        """A copy of the checker beside a residue list of the test's choosing, and a root to check."""
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        base = Path(holder.name).resolve()
        scripts = base / "skills" / "scripts"
        scripts.mkdir(parents=True)
        for name in ("package_check.py", "data_formats.py"):
            shutil.copy(SCRIPTS / name, scripts / name)
        if shared_text is not None:
            listing = base / "skills" / "skill-maker" / "skill-creator" / "scripts" / "residue-classes.json"
            listing.parent.mkdir(parents=True)
            listing.write_text(shared_text, encoding="utf-8")
        (base / "manifest.json").write_text(json.dumps({"include": ["**/*"], "exclude": []}), encoding="utf-8")
        root = base / "root"
        root.mkdir()
        return scripts / "package_check.py", root

    def run_shadow(self, checker: Path, root: Path) -> subprocess.CompletedProcess:
        manifest = checker.parents[2] / "manifest.json"
        return subprocess.run([sys.executable, str(checker), "--root", str(root), "--manifest", str(manifest)],
                              capture_output=True, text=True, check=False)

    def test_a_name_added_to_the_list_is_caught_without_touching_the_checker(self):
        shared = json.loads(self.SHARED.read_text(encoding="utf-8"))
        shared["secrets"].append("*.vault")
        shared["runtime-state"].append(".scratchpad")
        checker, root = self.shadow_tree(json.dumps(shared))
        (root / "app").mkdir()
        (root / "app" / "prod.vault").write_text("x", encoding="utf-8")
        (root / "app" / ".scratchpad").mkdir()
        (root / "app" / ".scratchpad" / "notes.md").write_text("x", encoding="utf-8")
        process = self.run_shadow(checker, root)
        self.assertEqual({row["path"]: row["class"] for row in json.loads(process.stdout)["violations"]},
                         {"app/prod.vault": "secrets", "app/.scratchpad/notes.md": "runtime-state"})

    def test_a_list_that_cannot_be_used_is_an_engine_error_and_never_a_pass(self):
        broken = {
            "missing": None,
            "not json": "{",
            "not a mapping": "[]",
            "a class is missing": json.dumps({"secrets": [".env"], "runtime-state": [".harness-state"]}),
            "an empty class": json.dumps({"secrets": [], "runtime-state": ["a"], "save-state": ["b"]}),
            "a name that is not text": json.dumps({"secrets": [1], "runtime-state": ["a"], "save-state": ["b"]}),
        }
        for label, text in broken.items():
            with self.subTest(list=label):
                checker, root = self.shadow_tree(text)
                process = self.run_shadow(checker, root)
                self.assertEqual(process.returncode, 2, process.stdout + process.stderr)
                self.assertNotIn("Traceback", process.stderr)
                report = json.loads(process.stdout)
                self.assertFalse(report["ok"])
                self.assertIn("residue-classes.json", report["engine_error"])


class PackageRootCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        for relative in (*REQUIRED_ASSET_GLOBS, "README.md"):
            self.write(relative, "fixture\n")

    def write(self, relative: str, text: str = "x\n") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_check(self, *extra: str, manifest: Path | None = None) -> tuple[int, dict, str]:
        cmd = [sys.executable, str(PACKAGE_CHECK), "--root", str(self.root), *extra]
        if manifest is not None:
            cmd += ["--manifest", str(manifest)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return proc.returncode, (json.loads(proc.stdout) if proc.stdout.strip() else {}), proc.stderr

    def symlink(self, link: str, target: Path, directory: bool = False) -> Path:
        path = self.root / link
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"cannot create a symlink here: {exc}")
        return path


class EnumerationTests(PackageRootCase):
    def test_a_clean_root_passes_and_writes_an_archive(self):
        code, report, _ = self.run_check("--out", str(self.root / "dist" / "p.zip"))
        self.assertEqual(code, 0, report)
        self.assertTrue((self.root / "dist" / "p.zip").is_file())

    def test_new_secret_names_fail_the_check_and_write_no_archive(self):
        self.write("skills/id_rsa")
        self.write("skills/.npmrc")
        self.write("skills/creds/credentials.json")
        self.write("skills/Deploy.PEM")
        code, report, _ = self.run_check("--out", str(self.root / "dist" / "p.zip"))
        self.assertEqual(code, 1, report)
        self.assertEqual({v["path"]: v["class"] for v in report["violations"]},
                         {"skills/id_rsa": "secrets", "skills/.npmrc": "secrets",
                          "skills/creds/credentials.json": "secrets", "skills/Deploy.PEM": "secrets"})
        self.assertFalse((self.root / "dist" / "p.zip").exists())

    def test_an_upper_case_env_file_is_dropped_by_the_manifest_exclude_like_the_lower_case_one(self):
        self.write(".ENV", "SECRET=1\n")
        self.write("skills/.Env.local", "SECRET=1\n")
        code, report, _ = self.run_check("--out", str(self.root / "dist" / "p.zip"))
        self.assertEqual(code, 0, report)
        with zipfile.ZipFile(self.root / "dist" / "p.zip") as archive:
            self.assertFalse([n for n in archive.namelist() if n.lower().rsplit("/", 1)[-1].startswith(".env")])

    def test_a_nested_git_directory_fails_but_the_root_git_file_and_directory_do_not(self):
        self.write(".git", "gitdir: /elsewhere/.git/worktrees/x\n")
        code, report, _ = self.run_check()
        self.assertEqual((code, report["violations"]), (0, []), "a worktree's .git file is the checkout's own")
        self.write("vendor/lib/.git/config", "[core]\n")
        code, report, _ = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(report["violations"], [{"path": "vendor/lib/.git/config", "class": "vcs-metadata"}])

    def test_nested_supremeteam_state_fails(self):
        self.write("skills/.supremeteam/state.json")
        code, report, _ = self.run_check()
        self.assertEqual((code, report["violations"]),
                         (1, [{"path": "skills/.supremeteam/state.json", "class": "runtime-state"}]))

    def test_a_symlinked_file_is_a_violation_and_is_never_archived(self):
        outside = self.root.parent / f"{self.root.name}-outside-secret.txt"
        outside.write_text("secret bytes\n", encoding="utf-8")
        self.addCleanup(outside.unlink)
        self.symlink("docs/notes.md", outside)
        code, report, _ = self.run_check("--out", str(self.root / "dist" / "p.zip"))
        self.assertEqual(code, 1, report)
        self.assertEqual(report["violations"], [{"path": "docs/notes.md", "class": "symlink"}])
        self.assertFalse((self.root / "dist" / "p.zip").exists())

    def test_a_symlinked_directory_is_a_violation_too(self):
        target = self.root.parent / f"{self.root.name}-outside-dir"
        target.mkdir()
        (target / "leak.txt").write_text("leak\n", encoding="utf-8")
        self.addCleanup(lambda: (target / "leak.txt").unlink() or target.rmdir())
        self.symlink("docs/linked", target, directory=True)
        code, report, _ = self.run_check()
        self.assertEqual(code, 1, report)
        self.assertEqual(report["violations"], [{"path": "docs/linked", "class": "symlink"}])

    def test_a_symlink_the_manifest_excludes_is_not_reported(self):
        """An excluded path is out of the delivery set whatever it is, so it cannot ship."""
        self.symlink(".harness-state/link", self.root / "README.md")
        code, report, _ = self.run_check()
        self.assertEqual((code, report["violations"]), (0, []))

    def test_violations_are_reported_in_a_stable_order(self):
        for name in ("z.pem", "a.pem", "m.key"):
            self.write(f"skills/{name}")
        _, report, _ = self.run_check()
        self.assertEqual([v["path"] for v in report["violations"]], ["skills/a.pem", "skills/m.key", "skills/z.pem"])


class ManifestErrorTests(PackageRootCase):
    def manifest(self, text: str) -> Path:
        path = self.root / "custom-manifest.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def assert_engine_error(self, text: str, needle: str) -> None:
        code, report, stderr = self.run_check(manifest=self.manifest(text))
        self.assertEqual(code, 2, (report, stderr))
        self.assertNotIn("Traceback", stderr)
        self.assertFalse(report["ok"])
        self.assertIn(needle, report["engine_error"])

    def test_a_manifest_that_is_not_a_mapping_is_an_engine_error(self):
        for text in ('["include"]', "- a\n- b\n", '"text"', "42"):
            with self.subTest(text=text):
                self.assert_engine_error(text, "root must be a mapping")

    def test_include_and_exclude_must_be_lists_of_non_empty_strings(self):
        for key in ("include", "exclude"):
            for value in ('"**/*"', "7", '{"a": 1}', "[1, 2]", '["ok", ""]', "[null]"):
                with self.subTest(key=key, value=value):
                    self.assert_engine_error(json.dumps({"schema_version": 1}) [:-1] + f', "{key}": {value}' + "}",
                                             f"{key} must be a list of non-empty strings")

    def test_an_unreadable_manifest_is_an_engine_error(self):
        code, report, stderr = self.run_check(manifest=self.root / "no-such-manifest.yaml")
        self.assertEqual((code, report["ok"]), (2, False))
        self.assertNotIn("Traceback", stderr)

    def test_a_manifest_that_omits_both_lists_selects_everything(self):
        code, report, _ = self.run_check(manifest=self.manifest('{"schema_version": 1}'))
        self.assertEqual(code, 0, report)
        self.assertEqual(report["selected_count"], len(REQUIRED_ASSET_GLOBS) + 2, "the assets, README.md, and the manifest")


if __name__ == "__main__":
    unittest.main()
