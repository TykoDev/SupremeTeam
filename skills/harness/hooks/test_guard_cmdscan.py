#!/usr/bin/env python3
"""The command analyser behind the guard: tokenising, unwrapping, write targets (SEC-02, SEC-03, SEC-05, SEC-08).

The guard decided from raw command text with a verb list and a substring match. These
tables are the ordinary spellings that got past it (a redirect with no space, ``sed -E -i``,
``curl -o``, ``sh -c "..."``, ``$(...)``, ``/bin/rm``, ``git -C r push``, ``cd`` then a
relative path) and the ordinary reads that must never be taken for writes. Everything the
analyser returns is a path word; deciding whether it lies on a boundary is ``_paths``' job.
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import _cmdscan  # noqa: E402


def analyse(text: str, ps: bool = False):
    return _cmdscan.analyse(text, powershell=ps)


def paths(text: str, ps: bool = False) -> set:
    return {write.path for write in analyse(text, ps).writes}


def commands(text: str, ps: bool = False) -> list:
    return [(command.verb, command.argv) for command in analyse(text, ps).commands]


BASH_WRITES = (
    # redirects, with and without a space, every operator, and the ones that are not writes
    ("echo x >src/payments/a.py", {"src/payments/a.py"}),
    ("echo x>>src/payments/log", {"src/payments/log"}),
    ("echo x > a 2> b", {"a", "b"}),
    ("echo a >| f", {"f"}),
    ("echo a &> f", {"f"}),
    ("echo a &>> f", {"f"}),
    ("echo a 1>f", {"f"}),
    ("cat < in > out", {"out"}),
    ("{ echo a; echo b; } > f", {"f"}),
    ("( echo a ) >> f", {"f"}),
    ("exec > f", {"f"}),
    ("echo x > f # > g", {"f"}),
    ("echo x > 'src/pay ments/a'", {"src/pay ments/a"}),
    ("a && b > f || c > g", {"f", "g"}),
    ("a | tee f1 f2", {"f1", "f2"}),
    ("a | tee -a f", {"f"}),
    ("ls 2>/dev/null", set()),
    ("make 2>&1 | tail", set()),
    ("cmd >/dev/null 2>&1", set()),
    ("cmd &>/dev/null", set()),
    ("cmd > /dev/stderr", set()),
    ("echo hi >&2", set()),
    ("cmd 1>&2", set()),
    ("cat <in", set()),
    ("echo '>' f", set()),
    ("echo a\\>b", set()),
    ("echo $((1>2))", set()),
    ("echo ->", set()),
    ("grep -rn foo src/payments 2>/dev/null", set()),
    # file-mutating commands and their operands
    ("rm -rf src/payments", {"src/payments"}),
    ("rm -rf -- -weird", {"-weird"}),
    ("rm -r a b", {"a", "b"}),
    ("mv a b", {"a", "b"}),
    ("cp a b", {"b"}),
    ("cp -r a b dir/", {"dir/"}),
    ("cp -t dir a b", {"dir"}),
    ("ln -s a b", {"b"}),
    ("install -m 755 a b", {"b"}),
    ("install -d d1 d2", {"d1", "d2"}),
    ("chmod 644 f", {"f"}),
    ("chmod -R u+w d1 d2", {"d1", "d2"}),
    ("chown user:grp f", {"f"}),
    ("touch a b", {"a", "b"}),
    ("mkdir -p d/e", {"d/e"}),
    ("truncate -s 0 f", {"f"}),
    ("dd if=a of=b bs=1", {"b"}),
    ("rsync -a src/ dest/", {"dest/"}),
    ("gzip f", {"f"}),
    ("sort -o out in", {"out"}),
    ("patch -o out in", {"out", "in"}),
    # in-place editors, every flag spelling
    ("sed -i s/a/b/ f", {"f"}),
    ("sed -E -i 's/a/b/' f", {"f"}),
    ("sed -n -i p f", {"f"}),
    ("sed -ni p f", {"f"}),
    ("sed -e s/a/b/ -i f", {"f"}),
    ("sed --in-place=.bak s/a/b/ f", {"f"}),
    ("sed -i.bak s/a/b/ f", {"f"}),
    ("sed -n p f", set()),
    ("sed -e s/a/b/ f", set()),
    ("perl -pi -e 's/a/b/' f", {"f"}),
    ("perl -i.bak -pe 's/a/b/' f", {"f"}),
    ("perl -ne print f", set()),
    ("awk -i inplace '{print}' f", {"f"}),
    ("awk '{print}' f", set()),
    # downloaders and archivers
    ("curl -o out http://h/x", {"out"}),
    ("curl -sSLo out http://h/x", {"out"}),
    ("curl --output out http://h/x", {"out"}),
    ("curl --output=out http://h/x", {"out"}),
    ("curl -O http://h/dir/f.tgz", {"f.tgz"}),
    ("curl http://h/x", set()),
    ("curl -o /dev/null http://h/x", set()),
    ("wget -O out http://h/x", {"out"}),
    ("wget -P dir http://h/x", {"dir"}),
    ("wget --output-document=out u", {"out"}),
    ("tar -xf a.tar -C dir", {"dir"}),
    ("tar xzf a.tgz -C dir", {"dir"}),
    ("tar -cf out.tar src", {"out.tar"}),
    ("tar -czf out.tgz src", {"out.tgz"}),
    ("tar -xf a.tar", {"."}),
    ("tar -tf a.tar", set()),
    ("unzip -d dir a.zip", {"dir"}),
    ("unzip a.zip", {"."}),
    # git: the subcommands that write the tree take pathspecs; reads and pushes name no file
    ("git add src/x", {"src/x"}),
    ("git checkout -- f", {"f"}),
    ("git restore f g", {"f", "g"}),
    ("git rm f", {"f"}),
    ("git mv a b", {"a", "b"}),
    ("git clean -fd d", {"d"}),
    ("git commit -m 'msg here' f", {"f"}),
    ("git -C repo add f", {"f"}),
    ("git -c core.x=1 checkout -- f", {"f"}),
    ("git push origin feature", set()),
    ("git status", set()),
    ("git diff HEAD -- f", set()),
    ("git log --oneline -5", set()),
    # find, wrappers, shells
    ("find src -delete", {"src"}),
    ("find . -exec rm {} \\;", {"."}),
    ("find src -type f", set()),
    ("find src -name x -exec grep y {} +", set()),
    ("echo src/payments | xargs rm -rf", {"src/payments"}),
    ("sudo rm -rf x", {"x"}),
    ("sudo -u root rm x", {"x"}),
    ("env FOO=1 rm x", {"x"}),
    ("env -i rm x", {"x"}),
    ("nohup rm x &", {"x"}),
    ("time rm x", {"x"}),
    ("command rm x", {"x"}),
    ("nice -n 5 rm x", {"x"}),
    ("timeout 5 rm x", {"x"}),
    ("stdbuf -oL tee f", {"f"}),
    ("sh -c 'echo x > f'", {"f"}),
    ("bash -lc 'rm -rf a'", {"a"}),
    ('eval "rm -rf a"', {"a"}),
    ("echo $(rm -rf a)", {"a"}),
    ("echo `rm -rf a`", {"a"}),
    ('echo "$(touch f)"', {"f"}),
    ("echo x | sudo tee f", {"f"}),
    ("if rm a; then touch b; fi", {"a", "b"}),
    ("bash <<EOF\nrm -rf a\nEOF", {"a"}),
    ("sh -s <<< 'rm -rf a'", {"a"}),
    # variables, cd, braces, globs, quoting, heredocs
    ("d=src; echo x > $d/payments/a.py", {"src/payments/a.py"}),
    ("d=src; echo x > ${d}/payments/a.py", {"src/payments/a.py"}),
    ("export D=src && rm -rf $D", {"src"}),
    ("rm -rf {src,build}/x", {"src/x", "build/x"}),
    ("rm -rf src/pay*", {"src/pay*"}),
    ("cat <<EOF > f\nbody > g\nEOF", {"f"}),
    ("cat > f <<'EOF'\nbody > g\nEOF", {"f"}),
    ("cat > f <<-EOF\n\tbody\n\tEOF", {"f"}),
    ("echo x > f\n# comment > g\nrm h", {"f", "h"}),
    ("echo x \\\n  > f", {"f"}),
    ("echo \"a b\" > 'c d'", {"c d"}),
    ("echo x > $'f\\x41'", {"fA"}),
)

PS_WRITES = (
    ("Set-Content src/payments/file.txt x", {"src/payments/file.txt"}),
    ("Set-Content -Path src\\payments\\f -Value x", {"src\\payments\\f"}),
    ("Out-File -FilePath f -InputObject x", {"f"}),
    ("'x' | Out-File f", {"f"}),
    ("Add-Content f x", {"f"}),
    ("Clear-Content f", {"f"}),
    ("Remove-Item -Recurse -Force .\\build", {".\\build"}),
    ("Remove-Item -Path a, b", {"a", "b"}),
    ("Copy-Item a b", {"b"}),
    ("Copy-Item -Path a -Destination b", {"b"}),
    ("Move-Item a b", {"a", "b"}),
    ("New-Item -ItemType File -Path f", {"f"}),
    ("ni f -Force", {"f"}),
    ("sc f x", {"f"}),
    ("ri f", {"f"}),
    ("echo x > f", {"f"}),
    ("Invoke-WebRequest -Uri http://h/x -OutFile f", {"f"}),
    ("Expand-Archive z.zip -DestinationPath d", {"d"}),
    ("Tee-Object -FilePath f", {"f"}),
    ("del src\\payments\\a.py", {"src\\payments\\a.py"}),
    ("copy a b", {"b"}),
    ("rd /s /q d", {"d"}),
    ("powershell -Command \"Remove-Item a\"", {"a"}),
    ("pwsh -c 'Set-Content f x'", {"f"}),
    ("cmd /c \"del a\"", {"a"}),
    ("$d='src'; Remove-Item $d\\x", {"src\\x"}),
    ("$d = 'src'; Remove-Item $d\\x", {"src\\x"}),
    ("Get-Content src/payments/f.txt", set()),
    ("Select-String -Path src/payments/*.py -Pattern x", set()),
    ("Get-ChildItem src > $null", set()),
    ("Get-ChildItem src 2>&1 | Out-Null", set()),
    ("Write-Output `\"x`\" > f", {"f"}),
)


class WriteTargetTests(unittest.TestCase):
    def test_bash_writes(self):
        for text, expected in BASH_WRITES:
            with self.subTest(command=text):
                result = analyse(text)
                self.assertTrue(result.ok, text)
                self.assertEqual({write.path for write in result.writes}, expected)

    def test_powershell_writes(self):
        for text, expected in PS_WRITES:
            with self.subTest(command=text):
                result = analyse(text, ps=True)
                self.assertTrue(result.ok, text)
                self.assertEqual({write.path for write in result.writes}, expected)

    def test_a_home_variable_resolves_where_the_shell_would_expand_it(self):
        with mock.patch.dict(os.environ, {"HOME": "/home/u"}):
            self.assertEqual(paths('echo x > "$HOME/x"'), {"/home/u/x"})
            self.assertEqual(paths("echo x > ~/y"), {"/home/u/y"})
            self.assertEqual(paths("rm -rf ${HOME}/z"), {"/home/u/z"})

    def test_an_unresolvable_expansion_is_flagged_not_guessed(self):
        write = analyse("echo x > $UNKNOWN/a").writes[0]
        self.assertEqual((write.path, write.unresolved), ("$UNKNOWN/a", True))
        write = analyse("for x in a b; do rm $x; done").writes[0]
        self.assertTrue(write.unresolved)
        write = analyse('rm "$(mktemp)"').writes[0]
        self.assertTrue(write.unresolved)
        self.assertFalse(analyse("rm known").writes[0].unresolved)

    def test_a_wildcard_word_is_flagged_a_quoted_one_is_not(self):
        self.assertTrue(analyse("rm src/pay*").writes[0].glob)
        self.assertTrue(analyse("rm src/p?y").writes[0].glob)
        self.assertFalse(analyse("rm 'src/pay*'").writes[0].glob)
        self.assertFalse(analyse("rm src/pay\\*").writes[0].glob)

    def test_cd_is_followed_into_later_relative_paths(self):
        write = analyse("cd src; echo x > payments/a.py").writes[0]
        self.assertEqual((write.path, write.cwds), ("payments/a.py", ("src",)))
        chain = analyse("cd src && cd payments && rm a.py").writes[0]
        self.assertEqual(chain.cwds, ("src", "src/payments"))
        before = analyse("rm a.py; cd src").writes[0]
        self.assertEqual(before.cwds, ())
        self.assertEqual(analyse("pushd /abs/dir; rm a").writes[0].cwds, ("/abs/dir",))

    def test_git_dash_c_is_a_working_directory_for_its_pathspecs(self):
        write = analyse("git -C repo add f").writes[0]
        self.assertEqual((write.path, write.cwds), ("f", ("repo",)))

    def test_a_cd_inside_a_subshell_or_a_substitution_does_not_leak_out(self):
        self.assertEqual(analyse("(cd src; rm a); rm b").writes[1].cwds, ())
        self.assertEqual(analyse("echo $(cd src; pwd); rm b").writes[0].cwds, ())
        self.assertEqual(analyse("{ cd src; }; rm b").writes[0].cwds, ("src",))

    def test_only_the_recent_directories_are_candidates_so_padding_cannot_grow_the_work(self):
        text = "".join(f"cd d{i}; " for i in range(40)) + "rm x"
        write = analyse(text).writes[0]
        self.assertEqual(len(write.cwds), 3)
        self.assertEqual(write.cwds[-1], "/".join(f"d{i}" for i in range(40)))

    def test_a_cd_back_into_a_visited_directory_is_where_the_next_cd_starts(self):
        """RR-guard-6: the shell is in src/payments here, not in src/x/payments, so the write lands on a frozen path."""
        for text in ("cd src; cd x; cd ..; cd payments; touch a.py", "cd src && cd x && cd .. && cd payments && touch a.py",
                     "cd src/x; cd ..; cd payments; touch a.py", "cd src; cd x; cd ../..; cd src/payments; touch a.py"):
            with self.subTest(command=text):
                self.assertEqual(analyse(text).writes[-1].cwds[-1], "src/payments")
        self.assertEqual(analyse("cd a; cd ..; cd a; touch f").writes[0].cwds[-1], "a")

    def test_the_directories_a_write_carries_are_distinct_and_the_last_is_current(self):
        write = analyse("cd a; cd ..; cd a; cd ..; cd a; touch f").writes[0]
        self.assertEqual(write.cwds, (".", "a"))

    def test_the_via_names_the_redirect_or_the_command(self):
        self.assertEqual([(w.path, w.via) for w in analyse("echo a >> f; rm g").writes], [("f", ">>"), ("g", "rm")])
        self.assertEqual(analyse("ri f", ps=True).writes[0].via, "remove-item")

    def test_a_git_write_names_its_subcommand(self):
        self.assertEqual([(w.path, w.via) for w in analyse("git add a; git checkout -- b; git -C r clean -fd c").writes],
                         [("a", "git add"), ("b", "git checkout"), ("c", "git clean")])

    def test_git_parts_skips_global_options_and_keeps_dash_c(self):
        self.assertEqual(_cmdscan.git_parts(["-C", "r", "-c", "k=v", "push", "-f", "origin", "main"])[0], "push")
        sub, operands, directories, flags = _cmdscan.git_parts(["-C", "r", "--no-pager", "commit", "-m", "msg", "f"])
        self.assertEqual((sub, [a.text for a in operands], directories, flags), ("commit", ["f"], ["r"], ["-m"]))


class CommandStructureTests(unittest.TestCase):
    def test_wrappers_and_paths_reduce_to_the_command_that_runs(self):
        cases = (
            ("sudo rm -rf /", ("rm", ("-rf", "/"))),
            ("/bin/rm -rf /*", ("rm", ("-rf", "/*"))),
            ("\\rm -rf /", ("rm", ("-rf", "/"))),
            ("RM -RF /", ("rm", ("-RF", "/"))),
            ("env -i rm -rf /", ("rm", ("-rf", "/"))),
            ("FOO=1 BAR=2 rm -rf /", ("rm", ("-rf", "/"))),
            ("nice -n 5 rm -rf /", ("rm", ("-rf", "/"))),
            ("sh -c 'rm -rf /'", ("rm", ("-rf", "/"))),
            ('bash -c "rm -rf /"', ("rm", ("-rf", "/"))),
            ("x=rm; $x -rf /", ("rm", ("-rf", "/"))),
            ("r''m -rf /", ("rm", ("-rf", "/"))),
            ("git -C r push -f origin main", ("git", ("-C", "r", "push", "-f", "origin", "main"))),
            ("C:\\Windows\\System32\\Remove-Item.exe -Recurse C:\\", ("remove-item", ("-Recurse", "C:\\"))),
        )
        for text, expected in cases:
            with self.subTest(command=text):
                self.assertIn(expected, commands(text, ps="Remove-Item" in text), text)

    def test_substitutions_and_pipelines_are_commands_too(self):
        self.assertIn(("rm", ("-rf", "/")), commands("echo $(rm -rf /)"))
        self.assertIn(("rm", ("-rf", "/")), commands("echo `rm -rf /`"))
        self.assertIn(("rm", ("-rf", "/")), commands('echo "$(rm -rf /)"'))
        self.assertIn(("rm", ("-rf", "/")), commands("(rm -rf /)"))
        self.assertIn(("rm", ("-rf", "/")), commands("echo / | xargs rm -rf"))
        self.assertIn(("rm", ("-rf", "/")), commands("true && { rm -rf /; }"))
        self.assertIn(("rm", ("-rf", "/")), commands("echo a\nrm -rf /"))
        self.assertIn(("rm", ("-rf", "/")), commands("eval 'rm -rf /'"))

    def test_xargs_takes_its_operands_from_a_literal_upstream_stage_only(self):
        self.assertIn(("rm", ("-rf", "/")), commands("printf '/\\n' | xargs rm -rf"))
        self.assertNotIn(("rm", ("-rf", "/")), commands("cat list | xargs rm -rf"))
        self.assertIn(("rm", ("-rf",)), commands("cat list | xargs rm -rf"))

    def test_keywords_do_not_hide_the_command(self):
        for text in ("if rm -rf /; then :; fi", "while rm -rf /; do :; done", "! rm -rf /", "time rm -rf /",
                     "for i in 1; do rm -rf /; done", "{ rm -rf /; }", "function f { rm -rf /; }; f"):
            with self.subTest(command=text):
                self.assertIn(("rm", ("-rf", "/")), commands(text), text)

    def test_a_tokenisation_failure_is_reported_not_guessed(self):
        for text in ('echo "x', "echo 'x", "echo $(rm", "echo `rm", "echo ${x", "echo $((1", "echo \"$(\""):
            with self.subTest(command=text):
                self.assertFalse(analyse(text).ok, text)

    def test_an_unterminated_heredoc_still_parses(self):
        result = analyse("cat <<EOF > f\nno terminator")
        self.assertTrue(result.ok)
        self.assertEqual({w.path for w in result.writes}, {"f"})

    def test_empty_and_comment_only_input_is_clean(self):
        for text in ("", "   ", "\n\n", "# just a comment", "   # c > f"):
            with self.subTest(text=text):
                result = analyse(text)
                self.assertEqual((result.ok, result.commands, result.writes, result.code), (True, [], [], []))


class OpaqueCodeTests(unittest.TestCase):
    """An interpreter's code cannot be read for what it writes; its text is handed to the guard to search."""

    def test_inline_code_is_returned_as_code(self):
        cases = (
            ("python3 -c \"open('f','w')\"", "open('f','w')"),
            ("python -Bc 'x=1'", "x=1"),
            ("python3.13 -c 'x=1'", "x=1"),
            ("py -3 -c 'x=1'", "x=1"),
            ("node -e 'fs.writeFileSync(1)'", "fs.writeFileSync(1)"),
            ("node --eval 'x'", "x"),
            ("node -p 'x'", "x"),
            ("perl -e 'print 1'", "print 1"),
            ("perl -pe 's/a/b/' f", "s/a/b/"),
            ("ruby -e 'puts 1'", "puts 1"),
            ("php -r 'echo 1;'", "echo 1;"),
            ("lua -e 'x'", "x"),
            ("awk '{print > \"out\"}' f", '{print > "out"}'),
            ("sudo python -c 'x=1'", "x=1"),
            ("bash -c 'python -c \"x=1\"'", "x=1"),
            ("python - <<'EOF'\nopen('f','w')\nEOF", "open('f','w')"),
            ("python - <<< \"x=1\"", "x=1"),
        )
        for text, fragment in cases:
            with self.subTest(command=text):
                joined = "\n".join(analyse(text).code)
                self.assertIn(fragment, joined, text)

    def test_a_script_or_module_run_has_no_inline_code(self):
        for text in ("python script.py arg", "python -m pytest tests", "python skills/harness/hooks/save_run.py status",
                     "node app.js", "python script.py <<EOF\nx\nEOF", "perl script.pl", "bash script.sh"):
            with self.subTest(command=text):
                self.assertEqual(analyse(text).code, [], text)

    def test_powershell_dotnet_file_calls_are_code(self):
        result = analyse("[IO.File]::WriteAllText('f','x')", ps=True)
        self.assertIn("WriteAllText", "\n".join(result.code))
        result = analyse("[System.IO.File]::Delete('f')", ps=True)
        self.assertTrue(result.code)
        self.assertEqual(analyse("[Math]::Max(1,2)", ps=True).code, [])


class WorkingDirectoryCostTests(unittest.TestCase):
    """RR-guard-2: a chain of relative ``cd`` makes each directory the previous one plus a segment, so what the analysis
    keeps for it must stop growing, and what it cannot follow must say so."""

    @staticmethod
    def kept(result) -> int:
        return sum(len(cwd) for write in result.writes for cwd in write.cwds)

    def test_a_long_relative_chain_is_flagged_and_what_is_kept_is_bounded(self):
        for text in ("; ".join(f"cd d{i}; touch f{i}" for i in range(5000)), " && ".join(f"cd d{i} && touch f" for i in range(4500))):
            with self.subTest(length=len(text)):
                result = analyse(text)
                self.assertTrue(result.lost_directory)
                self.assertLessEqual(max(len(cwd) for write in result.writes for cwd in write.cwds), _cmdscan.MAX_CWD)

    def test_what_is_kept_grows_with_the_command_not_with_its_square(self):
        def chain(count: int):
            return analyse("; ".join(f"cd d{i}; touch f{i}" for i in range(count)))

        small, large = chain(2000), chain(8000)
        self.assertLess(self.kept(large), self.kept(small) * 4 * 1.5)
        self.assertLess(self.kept(large), 8000 * 3 * _cmdscan.MAX_CWD)

    def test_a_chain_inside_the_limit_is_followed_exactly(self):
        result = analyse("".join(f"cd d{i}; " for i in range(60)) + "touch f")
        self.assertFalse(result.lost_directory)
        self.assertEqual(result.writes[0].cwds[-1], "/".join(f"d{i}" for i in range(60)))

    def test_going_up_and_down_never_grows_the_directory(self):
        result = analyse("".join(f"cd d{i}; touch f; cd ..; " for i in range(3000)))
        self.assertFalse(result.lost_directory)
        self.assertLess(max(len(cwd) for write in result.writes for cwd in write.cwds), 20)

    def test_a_subshell_does_not_accumulate_either(self):
        result = analyse("; ".join(f"(cd d{i} && touch f)" for i in range(4000)))
        self.assertFalse(result.lost_directory)
        self.assertLess(self.kept(result), 4000 * 3 * 20)

    def test_an_absolute_directory_longer_than_the_limit_is_flagged_too(self):
        self.assertTrue(analyse("cd /" + "/".join("d" * 40 for _ in range(14)) + "; touch f").lost_directory)
        self.assertFalse(analyse("cd /tmp/some/ordinary/directory; touch f").lost_directory)


class CostTests(unittest.TestCase):
    """SEC-08: analysis is linear, and padding the command is not a way past it."""

    def _bound(self, text: str, limit: float = 3.0) -> float:
        start = time.perf_counter()
        result = analyse(text)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, limit, f"{len(text)} chars took {elapsed:.2f}s")
        return elapsed if result is not None else 0.0

    def test_long_commands_are_analysed_in_about_a_second(self):
        for text in ("echo x; " * 12500, "a " * 50000, "git push " * 11000, "rm -rf / # " + "x" * 100000,
                     "echo " + "'a' " * 25000, "x" * 1000000, "echo $(" * 400 + ")" * 400,
                     "touch " + " ".join(f"f{i}" for i in range(15000))):
            with self.subTest(length=len(text)):
                self._bound(text)

    def test_padding_does_not_hide_a_write(self):
        padding = "echo padding " * 8000
        result = analyse(padding + "; rm -rf src/payments; " + padding)
        self.assertEqual({w.path for w in result.writes}, {"src/payments"})
        self.assertIn(("rm", ("-rf", "src/payments")), [(c.verb, c.argv) for c in result.commands])

    def test_growth_is_linear(self):
        small = "echo x > a; " * 2000
        big = small * 8
        t_small = min(self._time(small) for _ in range(3))
        t_big = min(self._time(big) for _ in range(3))
        self.assertLess(t_big, t_small * 8 * 3 + 0.05, (t_small, t_big))

    def _time(self, text: str) -> float:
        start = time.perf_counter()
        analyse(text)
        return time.perf_counter() - start

    def test_nesting_beyond_the_depth_cap_is_still_searched_as_code(self):
        text = "rm -rf secret/zone"
        for _ in range(12):
            text = "sh -c " + "'" + text.replace("'", "'\\''") + "'"
        result = analyse(text)
        self.assertTrue(result.ok)
        joined = "\n".join(result.code) + " ".join(w.path for w in result.writes)
        self.assertIn("secret/zone", joined)


if __name__ == "__main__":
    unittest.main()
