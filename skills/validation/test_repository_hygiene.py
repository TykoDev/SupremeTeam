"""What a repository that other people copy and contribute to has to carry.

The checkout had no licence terms for code its own installer copies into a
home directory, no contribution or release process, a 1.24 MB JPEG shown at 112
pixels, a `.gitignore` that listed scratch files from one machine and missed
`.env`, and one executable file among 393. Each is a one-line check, so a later
change cannot quietly bring it back.

These read the repository around ``skills/``, so they skip in an installed copy,
which carries only ``skills/``.
"""
from __future__ import annotations

import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

import _catalog
from _catalog import SKILLS
from package_check import manifest_globs, matches

REPO = SKILLS.parent
ASSETS = REPO / "docs" / "assets"
IN_A_CHECKOUT = (REPO / "README.md").is_file() and (REPO / "docs").is_dir()
CHECKOUT_ONLY = unittest.skipUnless(IN_A_CHECKOUT, "installed copy: only skills/ is present")

#: The owner's decision, recorded in the work order for CR-02 and DX-17.
COPYRIGHT = "Copyright (c) 2026 TykoDev"


def jpeg_size(path: Path) -> tuple[int, int]:
    """Width and height from the first start-of-frame marker, with no imaging library."""
    data = path.read_bytes()
    position = 2
    while position + 9 < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        marker = data[position + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[position + 5:position + 9])
            return width, height
        position += 2 + struct.unpack(">H", data[position + 2:position + 4])[0]
    raise ValueError(f"{path} has no start-of-frame marker")


@CHECKOUT_ONLY
class LicenseTests(unittest.TestCase):
    def setUp(self):
        self.text = (REPO / "LICENSE").read_text(encoding="utf-8")

    def test_the_license_is_mit_with_the_owners_copyright_line(self):
        self.assertEqual("MIT License", self.text.splitlines()[0])
        self.assertIn(f"\n{COPYRIGHT}\n", self.text)
        self.assertIn("Permission is hereby granted, free of charge, to any person obtaining a copy", self.text)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND', self.text)

    def test_the_package_manifest_declares_the_license_the_file_grants(self):
        """The manifest travels with an installed copy; the LICENSE file does not."""
        self.assertEqual("MIT", _catalog.load_spec("package-manifest.yaml")["license"])

    def test_the_readme_states_the_license_and_links_the_file(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        section = readme.split("\n## License\n", 1)
        self.assertEqual(2, len(section), "README.md has no License section")
        self.assertIn("[MIT License](LICENSE)", section[1])
        self.assertIn(COPYRIGHT, section[1])

    def test_the_project_files_ship_in_the_delivery_set(self):
        """The archive carries the licence and the contribution files, not only skills/."""
        include, exclude = manifest_globs(_catalog.load_spec("package-manifest.yaml"))
        for name in ("LICENSE", "CONTRIBUTING.md", "CHANGELOG.md"):
            with self.subTest(file=name):
                self.assertTrue(matches(name, include) and not matches(name, exclude))


@CHECKOUT_ONLY
class ProjectFileTests(unittest.TestCase):
    def test_the_changelog_keeps_a_changelog_with_an_unreleased_section(self):
        text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Changelog\n"))
        self.assertIn("https://keepachangelog.com/", text)
        self.assertIn("\n## [Unreleased]\n", text)
        self.assertTrue(re.search(r"^### (Added|Changed|Fixed)$", text, re.M), "no change group under Unreleased")

    def test_contributing_states_the_policies_it_exists_to_state(self):
        text = (REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for heading in ("Run the suites", "Fail-open and fail-loud", "Commits and pull requests", "Skill versions"):
            with self.subTest(heading=heading):
                self.assertIn(f"\n## {heading}\n", text)
        self.assertRegex(text, r"Hooks fail open")
        self.assertRegex(text, r"Gate validators fail loud")
        self.assertRegex(text, r"Bump it when the\s+skill's behaviour or contract changes")


@CHECKOUT_ONLY
class GitignoreTests(unittest.TestCase):
    def setUp(self):
        self.patterns = {
            line.strip() for line in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }

    def test_runtime_state_and_local_files_are_ignored(self):
        required = {"skillset-saves/", ".harness-state/", "__pycache__/", "*.pyc",
                    ".DS_Store", ".env", ".env.*", ".venv/", ".claude/worktrees/"}
        self.assertEqual(set(), required - self.patterns)

    def test_it_names_no_scratch_file_from_one_machine(self):
        self.assertEqual([], [pattern for pattern in sorted(self.patterns) if "GLM-SCORE" in pattern])


@CHECKOUT_ONLY
class FileModeTests(unittest.TestCase):
    def test_no_tracked_file_is_executable(self):
        """The docs run scripts through an interpreter (`bash ./scripts/install.sh`, `python x.py`)."""
        if shutil.which("git") is None or not (REPO / ".git").exists():
            self.skipTest("not a git checkout, or git is not installed: the index modes cannot be read")
        listing = subprocess.run(["git", "ls-files", "-s"], cwd=REPO, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", check=True).stdout
        executable = [line.split("\t", 1)[1] for line in listing.splitlines() if line.startswith("100755")]
        self.assertEqual([], executable)


@CHECKOUT_ONLY
class ImageBudgetTests(unittest.TestCase):
    #: The README column is about 830 px wide on GitHub; twice that is the most a
    #: diagram can use, and the diagrams are 1376 px already.
    MAX_DIAGRAM_BYTES = 200_000
    MAX_TOTAL_BYTES = 1_000_000

    def images(self):
        found = sorted(ASSETS.glob("*.jpg"))
        self.assertGreater(len(found), 4, "docs/assets yielded almost no images")
        return found

    def test_the_images_stay_small_enough_to_clone(self):
        sizes = {path.name: path.stat().st_size for path in self.images()}
        self.assertEqual({}, {name: size for name, size in sizes.items() if size > self.MAX_DIAGRAM_BYTES})
        self.assertLess(sum(sizes.values()), self.MAX_TOTAL_BYTES)

    def test_an_image_shown_at_a_set_width_is_at_most_twice_that_wide(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        shown = re.findall(r'<img src="(docs/assets/[^"]+)" width="(\d+)"', readme)
        self.assertTrue(shown, "README.md shows no image at a set width")
        for source, width in shown:
            with self.subTest(image=source):
                self.assertLessEqual(jpeg_size(REPO / source)[0], 2 * int(width))

    def test_every_image_is_referenced_and_every_reference_resolves(self):
        documents = [REPO / "README.md", *sorted((REPO / "docs").glob("*.md"))]
        text = "\n".join(path.read_text(encoding="utf-8") for path in documents)
        for image in self.images():
            with self.subTest(image=image.name):
                self.assertIn(f"assets/{image.name}", text, "no document shows this image")
        for name in sorted(set(re.findall(r"assets/([\w.-]+\.jpg)", text))):
            with self.subTest(reference=name):
                self.assertTrue((ASSETS / name).is_file(), f"documents reference docs/assets/{name}, which is missing")


class JpegReaderTests(unittest.TestCase):
    """The size check above reads JPEG headers by hand, so the reader needs its own test."""

    def test_it_reads_the_frame_header_of_a_baseline_and_a_progressive_file(self):
        header = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x04, 0x4A, 0x46])  # SOI, one APP0 segment
        for marker in (0xC0, 0xC2):
            frame = bytes([0xFF, marker, 0x00, 0x0B, 0x08]) + struct.pack(">HH", 40, 30) + bytes([0x01, 0x01, 0x11, 0x00])
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "x.jpg"
                path.write_bytes(header + frame)
                with self.subTest(marker=hex(marker)):
                    self.assertEqual((30, 40), jpeg_size(path))

    def test_a_file_without_a_frame_header_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.jpg"
            path.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xD9]) + b"\x00" * 16)
            with self.assertRaises(ValueError):
                jpeg_size(path)


if __name__ == "__main__":
    unittest.main()
