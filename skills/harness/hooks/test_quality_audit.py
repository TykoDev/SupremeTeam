"""Regression probes for the open quality audit, never execute the mutating commands."""
from __future__ import annotations

import io
import os
import tarfile
import zipfile
from unittest import mock

import guard_hook
from test_guard_rules import FROZEN, READ_ONLY, GuardCase


class QualityAuditGuardTests(GuardCase):
    def setUp(self):
        super().setUp()
        self.guard(FROZEN)
        (self.root / "sub").mkdir()
        (self.root / "backup" / ".harness-state").mkdir(parents=True)
        (self.root / "backup" / ".harness-state" / "guard-state.json").write_text("{}", encoding="utf-8")
        with tarfile.open(self.root / "strip.tar", "w") as archive:
            info = tarfile.TarInfo("backup/.harness-state/guard-state.json")
            info.size = 2
            archive.addfile(info, io.BytesIO(b"{}"))
        with tarfile.open(self.root / "link.tar", "w") as archive:
            info = tarfile.TarInfo("out")
            info.type = tarfile.SYMTYPE
            info.linkname = ".harness-state"
            archive.addfile(info)
            info = tarfile.TarInfo("out/guard-state.json")
            info.size = 2
            archive.addfile(info, io.BytesIO(b"{}"))

    def test_n8_unknown_extractor_is_not_a_proven_boundary(self):
        # The command is analyzed only. An arbitrary executable's effects are not known.
        self.check(("bsdtar -xf fixtures.tar -C src/payments",), deny=True)

    def test_n8_launched_commands_module_opens_and_git_destinations_are_judged_where_they_land(self):
        with tarfile.open(self.root / "benign.tar", "w") as archive:
            info = tarfile.TarInfo("docs/readme.txt")
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
        self.check((
            "python3 -c \"import os; os.system('tar -xf benign.tar -C src/payments')\"",
            "python3 -c \"import subprocess; subprocess.run(['rsync', '-a', 'sub/', 'src/payments/'])\"",
            "python3 -c \"import subprocess; subprocess.run('curl -o src/payments/f https://h/x', shell=True)\"",
            "python3 -c \"import tarfile; tarfile.open('benign.tar').extractall('src/payments')\"",
            "python3 -c \"import zipfile; zipfile.ZipFile('a.zip').extract('f', 'src/payments')\"",
            "python3 -c \"import os; os.open('src/payments/a.py', os.O_WRONLY | os.O_CREAT)\"",
            "git -C src/payments clean -fd", "cd src/payments && git clean -fd", "git -C src clean -fd",
            "git clone https://h/x src/payments/x", "git -C src/payments clone https://h/x", "git worktree add src/payments/wt",
            "git submodule add https://h/x src/payments/x", "git archive --output=src/payments/a.tar HEAD",
            "git format-patch -o src/payments HEAD~1", "git init src/payments/x", "git bundle create src/payments/b.bundle HEAD",
            "tar -xf benign.tar --one-top-level=src/payments", "tar -xf benign.tar -C src --one-top-level=payments",
        ), deny=True, fragment="frozen boundary")
        self.check(("python3 -c \"import os; os.system(cmd)\"", "python3 -c \"exec(code)\"", "git am < p.diff", "git am p.diff",
                    "python3 -c \"import zipfile; zipfile.ZipFile('a.zip').extractall()\"",
                    "python3 -c \"import os; os.system('cat list | xargs rm')\""), deny=True, fragment="unplaced write target")
        self.check((
            "python3 -c \"import gzip; print(gzip.open('src/payments/f.gz').read())\"",
            "python3 -c \"import codecs; print(codecs.open('src/payments/a.py', 'r', 'utf-8').read())\"",
            "python3 -c \"import tarfile; print(tarfile.open('src/payments/a.tar').getnames())\"",
            "python3 -c \"import os; fd = os.open('src/payments/a.py', os.O_RDONLY)\"",
            "python3 -c \"import os; print(os.popen('cat src/payments/a.py').read())\"",
            "python3 -c \"import subprocess; print(subprocess.check_output(['git', 'status'], cwd='src/payments'))\"",
            "python3 -c \"import os; os.system('tar -xf benign.tar -C sub')\"",
            "python3 -c \"import tarfile; tarfile.open('benign.tar').extractall('sub')\"",
            "git -C sub clean -fd", "cd sub && git clean -fd", "git clone https://h/x sub/x", "git worktree add sub/wt",
            "git archive -o sub/a.tar HEAD", "git format-patch -o sub HEAD~1", "git init", "git init sub/x",
            "tar -xf benign.tar --one-top-level=sub", "tar -xf benign.tar --one-top-level",
        ), deny=False)

    def test_n8_runtime_built_interpreter_destination_is_not_placed(self):
        self.check(("python3 -c 'open(\"\".join([\"src\",\"/pay\",\"ments/a.py\"]), \"w\").write(\"x\")'",), deny=True)

    def test_archive_rewrites_and_links_cannot_hide_record_writes(self):
        self.check(("tar -xf strip.tar --strip-components=1", "tar --strip-components 1 -xf strip.tar",
                    "tar -xf strip.tar --transform=s,backup/,,", "tar -xPf strip.tar", "tar -xf link.tar",
                    "tar -xf strip.tar --strip-components=1 -C sub", "tar -xf link.tar -C sub"), deny=True)
        for name in (str(self.root / ".harness-state" / "guard-state.json"), "../.harness-state/guard-state.json"):
            with tarfile.open(self.root / "absolute.tar", "w") as archive:
                info = tarfile.TarInfo(name)
                info.size = 2
                archive.addfile(info, io.BytesIO(b"{}"))
            self.check(("tar -xPf absolute.tar", "tar -xPf absolute.tar -C sub"), deny=True)
        with zipfile.ZipFile(self.root / "link.zip", "w") as archive:
            link = zipfile.ZipInfo("out")
            link.create_system = 3
            link.external_attr = 0o120777 << 16
            archive.writestr(link, ".harness-state")
            archive.writestr("out/guard-state.json", "{}")
        self.check(("unzip link.zip",), deny=True)

    def test_n8_archive_aliases_and_unknown_extraction_intent(self):
        self.check(("gtar -xf strip.tar -C src/payments", "7zz x unknown.7z -osrc/payments",
                    "unrar x unknown.rar src/payments/", "unar -o src/payments unknown.rar",
                    "vendor-extractor --extract unknown.arc --destination src/payments",
                    "custom -x unknown.arc -C src/payments", "vendor-extractor --extract unknown.arc",
                    "vendor-extractor --extract unknown.arc --destination sub",
                    "unrar x unknown.rar -o+ src/payments/", "unrar x unknown.rar '*.txt'"), deny=True)
        self.check(("bsdtar -tf strip.tar", "7zz l unknown.7z", "unrar l unknown.rar",
                    "grep -x pattern src/payments/a.py", "python3 -x script.py",
                    "pytest -x tests", "unar -o sub unknown.rar"), deny=False)

    def test_n8_computed_and_mixed_program_targets_cannot_hide_writes(self):
        self.check(("python3 -c 'p=\"src\"+\"/payments/a.py\"; open(p, \"w\")'",
                    "python3 -c 'open(\"sub/public.txt\", \"w\"); import os; os.system(\"rm src/payments/a.py\")'",
                    "python3 -c 'open(\"src/payments/a.py\", **options)'",
                    "echo 'open(\"\".join([\"src\",\"/payments/a.py\"]),\"w\")' | python3",
                    "node -e 'require(\"fs\").writeFileSync(destination, \"x\")'"), deny=True)
        self.check(("python3 -c 'open(\"sub/public.txt\", \"w\").write(\"x\")'",
                    "python3 -c 'from pathlib import Path; Path(\"sub/public.txt\").write_text(\"x\")'",
                    "python3 -c 'print(open(\"src/payments/a.py\").read())'"), deny=False)

    def test_no_target_directory_copy_lands_the_source_contents(self):
        self.guard({})
        self.check(("cp -rT backup .", "cp -r --no-target-directory backup .", "cp -Tr backup ."), deny=True)
        (self.root / "site").mkdir()
        self.check(("cp -rT site .",), deny=False)

    def test_clean_magic_wildcards_and_descendant_excludes_do_not_hide_root_reach(self):
        self.guard({})
        self.check(("git clean -fdx :/", "git clean -fdx '*'", "git clean -fdx ':(top,glob)**'",
                    "git clean -fdx -e '.harness-state/missing'", "git clean -fdx -e '.harness-state/*'",
                    "git clean -fx .harness-state", "git clean -fx '*'"), deny=True)
        self.check(("git clean -nfdx :/", "git clean -fdx -e .harness-state", "cd sub && git clean -fdx",
                    "cd sub && git clean -fdx ."), deny=False)
        self.check(("cd sub && git clean -fdx :/", "cd sub && git clean -fdx ..",
                    "cd missing; git clean -fdx"), deny=True)

    def test_sync_excludes_must_protect_the_directory_itself(self):
        self.guard({})
        self.check(("rsync -a --delete --exclude='.harness-state/missing' backup/ .",
                    "rsync -a --delete --exclude='.harness-state/*' backup/ .",
                    "rsync -a --delete-excluded --exclude=.harness-state backup/ .",
                    "rsync -a --delete --filter='.harness-state' backup/ ."), deny=True)
        self.check(("rsync -a --delete --exclude=.harness-state backup/ .",), deny=False)

    def test_read_only_git_ref_mutations_are_not_reads(self):
        self.guard(READ_ONLY)
        self.check(("git branch -D feature", "git tag -d v1", "git update-ref -d refs/heads/feature",
                    "git branch feature", "git tag v1", "git symbolic-ref HEAD refs/heads/feature"), deny=True)
        self.check(("git branch", "git branch --list", "git tag --list", "git tag --verify v1", "git symbolic-ref HEAD",
                    "git show-ref", "git log --oneline"), deny=False)

    def test_read_only_interpreter_access_to_a_frozen_path_is_allowed(self):
        self.check(("python3 -c 'print(open(\"src/payments/a.py\").read())'",
                    "node -e 'console.log(require(\"fs\").readFileSync(\"src/payments/a.py\"))'"), deny=False)
        self.check(("python3 -c 'open(\"src/payments/a.py\", \"w\").write(\"x\")'",), deny=True)

    def test_shell_apply_patch_checks_update_add_delete_and_move_targets(self):
        for action in ("Update File", "Add File", "Delete File", "Move to"):
            patch = f"*** Begin Patch\n*** {action}: src/payments/a.py\n*** End Patch"
            self.check((f"apply_patch <<'PATCH'\n{patch}\nPATCH", f"apply_patch '{patch}'"), deny=True)
        self.check(("apply_patch <<'PATCH'\n*** Begin Patch\n*** Update File: .harness-state/guard-state.json\n*** End Patch\nPATCH",
                    "apply_patch <<'PATCH'\n*** Begin Patch\n*** Update File: skillset-saves/runs/r1/_state.md\n*** End Patch\nPATCH"),
                   deny=True)
        self.check(("apply_patch <<'PATCH'\n*** Begin Patch\n*** Add File: docs/a.md\n+x\n*** End Patch\nPATCH",), deny=False)

    def test_root_archive_cannot_write_frozen_or_hook_paths_without_a_run(self):
        with zipfile.ZipFile(self.root / "frozen.zip", "w") as archive:
            archive.writestr("src/payments/a.py", "x")
        with zipfile.ZipFile(self.root / "hooks.zip", "w") as archive:
            archive.writestr("skills/harness/hooks/guard_hook.py", "x")
        self.check(("unzip frozen.zip",), deny=True, fragment="frozen boundary")
        with mock.patch.object(guard_hook, "HOOK_DIR", self.root / "skills" / "harness" / "hooks"), \
                mock.patch.dict(os.environ, {"SUPREMETEAM_HARNESS_DEV": ""}):
            self.check(("unzip hooks.zip",), deny=True, fragment="SUPREMETEAM_HARNESS_DEV")

    def test_archive_member_existing_symlink_is_resolved(self):
        try:
            (self.root / "alias").symlink_to(self.root / ".harness-state", target_is_directory=True)
        except OSError:
            self.skipTest("host cannot create symlinks")
        with tarfile.open(self.root / "alias.tar", "w") as archive:
            info = tarfile.TarInfo("alias/guard-state.json")
            info.size = 2
            archive.addfile(info, io.BytesIO(b"{}"))
        self.check(("tar -xf alias.tar",), deny=True)
