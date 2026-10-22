"""Test support: fixture trees and a temporary catalog for the check_runtime test modules.

``FixtureTreeCase`` writes a small project tree into a temporary directory and
drives the public entry point, ``check_runtime.check()``, against a catalog that
is a temporary copy of the real registry and overlays with a minimal runtime
manifest, so the tests verify the real overlay digests without reading the
catalog's own runtime manifest. The link helpers skip a test, rather than fail it,
where the platform cannot make the link: a symlink needs a privilege on Windows,
and a junction exists only there. ``unreadable_or_skip`` skips where the account
reads every file, as root does.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import check_runtime

SCRIPTS = Path(__file__).resolve().parent
SCRIPT = SCRIPTS / "check_runtime.py"
CATALOG_SOURCE = SCRIPTS.parent

BASE_MANIFEST = {
    "schema_version": 1,
    "kind": "supremeteam-runtime-manifest",
    "runtime": {"python": {"minimum": "3.9", "optional_dependencies": []}},
    "launchers": {"linux": "python3"},
}


def write_tree(root: Path, tree: dict[str, str | bytes]) -> None:
    for relative, content in tree.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8", newline="\n")


def make_catalog(parent: Path, *, manifest: object = None, registry: object = None, overlays: bool = True) -> Path:
    """A catalog root holding a manifest and a copy of the real tech-stack overlays."""
    catalog = parent / "catalog"
    catalog.mkdir()
    (catalog / "runtime-manifest.yaml").write_text(
        json.dumps(BASE_MANIFEST if manifest is None else manifest), encoding="utf-8"
    )
    if overlays:
        shutil.copytree(CATALOG_SOURCE / "tech-stacks", catalog / "tech-stacks")
    if registry is not None:
        (catalog / "tech-stacks").mkdir(exist_ok=True)
        (catalog / "tech-stacks" / "registry.yaml").write_text(json.dumps(registry), encoding="utf-8")
    return catalog


def package_json(*, dependencies=None, dev=None, scripts=None, **extra) -> str:
    data: dict = {"name": "fixture", **extra}
    if dependencies:
        data["dependencies"] = dependencies
    if dev:
        data["devDependencies"] = dev
    if scripts:
        data["scripts"] = scripts
    return json.dumps(data)


def slugs(inspection: dict) -> list[str]:
    return [stack["slug"] for stack in inspection["stacks"]]


def evidence(inspection: dict, slug: str) -> list[dict[str, str]]:
    return next(stack["evidence"] for stack in inspection["stacks"] if stack["slug"] == slug)


def candidate(source: str, path: str, command: str) -> dict[str, str]:
    return {"source": source, "path": path, "command": command}


VITE_TREE = {"package.json": package_json(dev={"vite": "^7"})}
COMPOSE_PORTS = "services:\n  web:\n    image: nginx:1\n    ports:\n      - \"8080:80\"\n"
COMPOSE_NO_PORTS = "services:\n  worker:\n    image: busybox\n    command: sleep 1000\n"


class FixtureTreeCase(unittest.TestCase):
    catalog: Path

    @classmethod
    def setUpClass(cls) -> None:
        holder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(holder.cleanup)
        cls.catalog = make_catalog(Path(holder.name))

    def project(self, tree: dict[str, str | bytes]) -> Path:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        root = Path(holder.name).resolve()
        write_tree(root, tree)
        return root

    def check_root(self, root: Path, *, detect=True, start=False, catalog=None) -> dict:
        return check_runtime.check(
            catalog or self.catalog,
            project_root=root,
            detect_project=detect,
            detect_start_command=start,
        )

    def report(self, tree, **modes) -> dict:
        return self.check_root(self.project(tree), **modes)

    def inspect_tree(self, tree, **modes) -> dict:
        return self.report(tree, **modes)["project_inspection"]

    def assertClean(self, inspection: dict) -> None:
        self.assertEqual(inspection["errors"], [])
        self.assertTrue(inspection["ok"])


def symlink_or_skip(case: unittest.TestCase, target: Path, link: Path, *, directory: bool = False) -> None:
    try:
        os.symlink(target, link, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        case.skipTest(f"cannot create symlinks here: {exc}")


def junction_or_skip(case: unittest.TestCase, target: Path, link: Path) -> None:
    """A Windows directory junction: it needs no privilege, and ``Path.is_symlink()`` does not report it."""
    if os.name != "nt":
        case.skipTest("directory junctions exist only on Windows")
    import _winapi

    try:
        _winapi.CreateJunction(str(target), str(link))
    except OSError as exc:
        case.skipTest(f"cannot create a junction here: {exc}")


def unreadable_or_skip(case: unittest.TestCase, path: Path) -> None:
    """Make ``path`` impossible to open for reading until the test ends; its metadata still reads.

    Windows has no mode that does it, so the test holds the file open and shares
    nothing. Elsewhere the mode is cleared, which root reads past, so there it skips.
    """
    if os.name == "nt":
        import _winapi

        handle = _winapi.CreateFile(str(path), _winapi.GENERIC_READ, 0, _winapi.NULL,
                                    _winapi.OPEN_EXISTING, 0, _winapi.NULL)
        case.addCleanup(_winapi.CloseHandle, handle)
        return
    path.chmod(0)
    case.addCleanup(path.chmod, 0o600)
    if os.access(path, os.R_OK):
        case.skipTest("this account reads a file whatever its mode")
