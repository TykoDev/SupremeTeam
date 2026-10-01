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

    def test_cd_dash_and_popd_return_to_the_directory_the_shell_is_really_in(self):
        """RR3-guard-5: `cd -` and `popd` moved the shell without moving the record, so a write after them was judged in the
        directory the shell had left (under the allow list of a read-only run, that is a way out of it)."""
        for text, expected in (
            ("cd a; cd -; touch f", "."),
            ("cd a; cd b; cd -; touch f", "a"),
            ("cd a; cd b; cd -; cd -; touch f", "a/b"),
            ("cd a && cd -  && touch f", "."),
            ("cd a; cd ..; cd -; touch f", "a"),
            ("pushd a; popd; touch f", "."),
            ("pushd a; ls; popd >/dev/null; touch f", "."),
            ("cd x; pushd a; pushd b; popd; touch f", "x/a"),
            ("cd x; pushd a; pushd b; popd; popd; touch f", "x"),
            ("cd x; pushd y; pushd; touch f", "x"),
            ("cd x; pushd y; pushd; pushd; touch f", "x/y"),
            ("cd a; popd; touch f", "a"),
            ("cd a; pushd; touch f", "a"),
            ("pushd /abs/dir; popd; touch f", "."),
            ("cd a; pushd b; cd c; popd; touch f", "a"),
        ):
            with self.subTest(command=text):
                self.assertEqual(analyse(text).writes[-1].cwds[-1], expected, text)
        self.assertEqual(analyse("cd -; touch f").writes[0].cwds, ())
        self.assertEqual(analyse("popd; touch f").writes[0].cwds, ())

    def test_a_bare_cd_goes_home_for_bash_and_nowhere_for_powershell(self):
        with mock.patch.dict(os.environ, {"HOME": "/home/u"}):
            self.assertEqual(analyse("cd a; cd; touch f").writes[-1].cwds[-1], "/home/u")
            self.assertEqual(analyse("cd a; cd; cd -; touch f").writes[-1].cwds[-1], "a")
            self.assertEqual(analyse("cd a; Set-Location; Set-Content f x", ps=True).writes[-1].cwds[-1], "a")

    def test_powershell_push_and_pop_location_follow_the_same_way(self):
        self.assertEqual(analyse("Push-Location a; Pop-Location; Set-Content f x", ps=True).writes[-1].cwds[-1], ".")
        self.assertEqual(analyse("Set-Location a; pushd b; popd; Set-Content f x", ps=True).writes[-1].cwds[-1], "a")
        self.assertEqual(analyse("Set-Location a; Set-Location b; Set-Location -; Set-Content f x", ps=True).writes[-1].cwds[-1], "a")

    def test_the_directory_stack_is_scoped_like_the_directory_itself(self):
        for text, expected in (
            ("cd x; pushd y; (popd); touch f", "x/y"),
            ("cd x; (pushd y; popd; cd z); touch f", "x"),
            ("cd x; pushd y; echo $(popd); touch f", "x/y"),
            ("cd x; pushd y; sh -c 'popd'; touch f", "x/y"),
            ("cd x; (pushd y); popd; touch f", "x"),
            ("cd x; (cd y; cd -; touch g); touch f", "x"),
        ):
            with self.subTest(command=text):
                self.assertEqual(analyse(text).writes[-1].cwds[-1], expected, text)

    def test_a_path_built_at_run_time_leaves_the_shell_where_it_was(self):
        self.assertEqual(analyse("cd a; cd $UNKNOWN; touch f").writes[-1].cwds[-1], "a")
        self.assertEqual(analyse("cd a; pushd $UNKNOWN; popd; touch f").writes[-1].cwds[-1], "a")

    def test_the_directory_stack_is_bounded(self):
        text = "pushd a; " * 5000 + "popd; " * 5000 + "touch f"
        result = analyse(text)
        self.assertTrue(result.writes)
        start = time.perf_counter()
        analyse("pushd a; " * 11000 + "( popd ); " * 100 + "touch f")
        self.assertLess(time.perf_counter() - start, 3.0)

    def test_a_git_command_that_only_moves_the_index_writes_no_file(self):
        """RR-guard-5: `git restore --staged .` is not a write into the tree, and `git reset` is not unless it is hard."""
        for text in ("git restore --staged .", "git restore -S src", "git restore --staged src/payments/a.py", "git reset HEAD src/a.py",
                     "git reset -q -- src", "git reset --mixed HEAD~1 src", "git -C r restore --staged ."):
            with self.subTest(command=text):
                self.assertEqual(paths(text), set())
        for text in ("git restore .", "git restore --staged --worktree .", "git restore -SW .", "git restore --worktree src",
                     "git reset --hard HEAD src", "git reset --merge src", "git checkout -- src", "git clean -fd src"):
            with self.subTest(command=text):
                self.assertTrue(paths(text), text)

    def test_a_trap_handler_is_read_as_the_command_line_it_is(self):
        self.assertEqual(paths("trap 'rm src/payments/a.py' EXIT"), {"src/payments/a.py"})
        self.assertEqual(paths("trap \"rm -f $tmp; cp x src/b\" EXIT INT"), {"src/b"} | paths("rm -f $tmp"))
        for text in ("trap 'echo bye' EXIT", "trap - EXIT", "trap -p", "trap -l", "trap"):
            with self.subTest(command=text):
                self.assertEqual(paths(text), set())

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


def unnamed(text: str, ps: bool = False) -> list:
    return [(entry.verb, entry.how) for entry in analyse(text, ps).unnamed]


# RR3-guard-1: a write whose target is not in the command. Each entry is a command and the (verb, how) it reports.
STDIN_FED = (
    ("cat list | xargs rm -rf", [("rm", "stdin")]),
    ("find . -name '*.pyc' | xargs rm", [("rm", "stdin")]),
    ("find . -name '*.pyc' -print0 | xargs -0 rm", [("rm", "stdin")]),
    ("git ls-files | xargs sed -i s/a/b/", [("sed", "stdin")]),
    ("git ls-files | xargs sed -i -e s/a/b/", [("sed", "stdin")]),
    ("xargs rm < list", [("rm", "stdin")]),
    ("xargs -a list rm", [("rm", "stdin")]),
    ("ls | xargs -n1 -P4 touch", [("touch", "stdin")]),
    ("ls | xargs chmod +x", [("chmod", "stdin")]),
    ("ls | xargs mv -t dest", [("mv", "stdin")]),
    ("ls | xargs gzip", [("gzip", "stdin")]),
    ("ls | xargs -r tee", [("tee", "stdin")]),
    ("ls | xargs perl -pi -e s/a/b/", [("perl", "stdin")]),
    ("ls | xargs truncate -s 0", [("truncate", "stdin")]),
    ("ls | xargs ln -s", [("ln", "stdin")]),
    ("ls | xargs mkdir -p", [("mkdir", "stdin")]),
    ("ls | xargs cp dest", [("cp", "stdin")]),
    ("ls | xargs git add", [("git", "stdin")]),
    ("ls | xargs touch named", [("touch", "stdin")]),
    ("sudo xargs rm < list", [("rm", "stdin")]),
    ("env xargs rm < list", [("rm", "stdin")]),
    ("nohup xargs rm < list", [("rm", "stdin")]),
    ("echo a | xargs rm; ls | xargs rm", [("rm", "stdin")]),
)
STDIN_NAMED = (
    "xargs grep x", "xargs -n1 echo", "git ls-files | xargs wc -l", "find . -type f -print0 | xargs -0 sha256sum",
    "git ls-files | xargs sed -n 1p", "git ls-files | xargs sed s/a/b/", "ls | xargs file", "ls | xargs cat",
    "ls | xargs cp -t dest", "ls | xargs -I{} cp {} dest/", "ls | xargs -I{} echo {}", "echo a b | xargs rm",
    "printf 'a\\nb\\n' | xargs rm", "echo a b | xargs touch c", "ls | xargs gzip -c", "ls | xargs tar tf",
    "ls | xargs git diff", "ls | xargs perl -ne 'print'", "ls | rm", "ls | touch f", "cat f | tee g", "ls | grep x | wc -l",
)
INLINE_WRITES = (
    ("awk '{print > \"out\"}' f", "awk"),
    ("awk '{print >> \"out\"}' f", "awk"),
    ("awk 'BEGIN{print 1 > \"src/payments/a\"}'", "awk"),
    ("gawk '{printf \"%s\\n\", $1 > \"out\"}' f", "gawk"),
    ("mawk '{printf(\"%s\\n\", $1) > \"out\"}' f", "mawk"),
    ("awk '/\"/ {print > \"x\"}' f", "awk"),
    ("awk '{print $1 | \"tee out\"}' f", "awk"),
    ("awk '{system(\"rm \" $1)}' f", "awk"),
    ("awk 'BEGIN{system(\"touch x\")}'", "awk"),
    ("perl -e 'open(F, \">src/payments/a\")'", "perl"),
    ("perl -e 'open(F, \">>x\"); print F 1'", "perl"),
    ("perl -e 'open F, \">\", \"x\"'", "perl"),
    ("perl -E 'open my $fh, \">>\", \"x\"'", "perl"),
    ("perl -e 'open(F, \"+<f\")'", "perl"),
    ("perl -e 'open(F, \"| tee x\")'", "perl"),
    ("perl -e 'unlink \"x\"'", "perl"),
    ("perl -e 'rename \"a\", \"b\"'", "perl"),
    ("perl -e 'system(\"rm -rf x\")'", "perl"),
    ("perl -e 'system(\"echo x > out\")'", "perl"),
    ("python3 -c \"open('x','w').write('1')\"", "python3"),
    ("python3 -c \"open('x', mode='a')\"", "python3"),
    ("python3 -c \"open('x','rb+')\"", "python3"),
    ("python3 -c \"import pathlib; pathlib.Path('x').write_text('1')\"", "python3"),
    ("python3 -c \"import os; os.remove('x')\"", "python3"),
    ("python3 -c \"import shutil; shutil.rmtree('x')\"", "python3"),
    ("python3 -c \"import os; os.system('rm -rf x')\"", "python3"),
    ("python3 -c \"import subprocess; subprocess.run(['rm','x'])\"", "python3"),
    ("python3 -c \"import subprocess; subprocess.run('echo x > f', shell=True)\"", "python3"),
    ("python - <<'EOF'\nopen('f','w')\nEOF", "python"),
    ("node -e \"require('fs').writeFileSync('x','1')\"", "node"),
    ("node -e \"require('fs').appendFileSync('x','1')\"", "node"),
    ("node -e \"require('fs').unlinkSync('x')\"", "node"),
    ("node -e \"require('fs').mkdirSync('x')\"", "node"),
    ("node -e \"require('fs').openSync('x','w')\"", "node"),
    ("node -e \"require('child_process').execSync('rm -rf x')\"", "node"),
    ("ruby -e \"File.write('x','1')\"", "ruby"),
    ("ruby -e \"File.open('x','w') {|f| f.puts 1}\"", "ruby"),
    ("ruby -e \"File.delete('x')\"", "ruby"),
    ("ruby -e \"system('rm x')\"", "ruby"),
    ("php -r 'file_put_contents(\"x\",\"1\");'", "php"),
    ("lua -e \"io.open('x','w')\"", "lua"),
    ("Rscript -e 'writeLines(\"a\",\"x\")'", "rscript"),
    ("sed -n 'w out' f", "sed"),
    ("sed -n '/x/w out' f", "sed"),
    ("sed 's/a/b/w out' f", "sed"),
    ("sed 's/a/b/gw out' f", "sed"),
    ("sed -e 's/a/b/' -e 'w out' f", "sed"),
    ("sed --expression='1w out' f", "sed"),
    ("sed -n '1,5W out' f", "sed"),
    ("sed 'e rm x' f", "sed"),
    ("sudo awk '{print > \"out\"}' f", "awk"),
    ("sh -c \"awk '{print > \\\"out\\\"}' f\"", "awk"),
)
INLINE_READS = (
    "awk '{print $1}' f", "awk '$1 > 5' f", "awk -F, '$3 >= 10 && $2 > 0 {print $1}' f", "awk '{if ($1 > 5) print $1}' f",
    "awk '{print ($1 > 5)}' f", "awk '{print ($1 > 5) ? \"a\" : \"b\"}' f", "awk '/a|b/ {print}' f", "awk '/a>b/ {print}' f",
    "awk 'NR>1 {print}' f", "awk 'NR > 1' f", "awk '{print $1 > \"/dev/stderr\"}' f", "awk '{print $1, $2 > \"/dev/stdout\"}' f",
    "awk 'BEGIN { while ((getline line < \"f\") > 0) n++; print n }'", "awk '{print $1 | \"sort\"}' f",
    "awk '{\"date\" | getline d; print d}' f", "awk '{system(\"ls\")}' f", "awk 'a || b {print}' f",
    "awk '{ a[$1]++ } END { for (k in a) print k, a[k] }' f", "awk -f prog.awk f", "awk '{print \"a > b\"}' f",
    "perl -e 'print 1'", "perl -ne 'print if /x/' f", "perl -ne 'print if /x/ && $. > 3' f", "perl -lane 'print $F[0]' f",
    "perl -e 'open(F, \"<f\"); print <F>'", "perl -e 'open(F, \"f\"); print <F>'", "perl -e 'open(my $fh, \"<\", \"f\")'",
    "perl -e 'print \"a\" if 3 > 2'", "perl script.pl", "perl -e 'system(\"ls\")'", "perl -e 'print `date`'",
    "python -c \"print(1)\"", "python3 -c \"print(1 > 0)\"", "python3 -c \"print(open('f').read())\"",
    "python3 -c \"open('f','r').read()\"", "python3 -c \"open('f','rb').read()\"", "python3 -c \"open('f').read().split('bar')\"",
    "python3 -c \"import sys; sys.stdout.write('x')\"", "python3 -c \"import shutil; print(shutil.which('git'))\"",
    "python3 -c \"import subprocess; print(subprocess.check_output(['git','log']))\"", "python3 -c \"print({}.copy())\"",
    "python3 -c \"import json,sys; print(len(json.load(open('f'))) > 3)\"", "python -m json.tool f", "python script.py",
    "python - <<'EOF'\nprint(1)\nEOF",
    "node -e \"console.log(1)\"", "node -e \"[1,2].map(x => x*2)\"", "node -p \"1+1\"", "node app.js",
    "node -e \"console.log(require('fs').readFileSync('f','utf8'))\"", "node -e \"require('child_process').execSync('git log')\"",
    "ruby -e \"puts 1\"", "ruby -e \"puts File.read('f')\"", "ruby -ne 'print if /x/' f", "ruby -e \"puts [1,2].map { |x| x > 1 }\"",
    "php -r 'echo 1;'", "lua -e \"print(1)\"", "Rscript -e 'print(1)'",
    "sed -n 's/a/b/p' f", "sed -n 1,5p f", "sed s/a/b/ f", "sed -n '/a/,/b/p' f", "sed -f script.sed f", "sed '1!G;h;$!d' f",
    "sed -n '$=' f", "sed 's/world/x/' f", "sed -n '/start/,/end/p' f", "sed -e 's/a/b/' -e 's/c/d/' f", "sed 's/^\\s*//' f",
    "sed -n 's/.*version: \\(.*\\)/\\1/p' f",
)


class UnnamedWriteTests(unittest.TestCase):
    """RR3-guard-1: a write whose target the command does not name. Rule D needs every target named, so the analyser says
    where it could not: operands that arrive on standard input, and programs that redirect or open a file."""

    def test_a_mutating_verb_fed_from_standard_input_is_unnamed(self):
        for text, expected in STDIN_FED:
            with self.subTest(command=text):
                self.assertEqual(unnamed(text), expected, text)

    def test_a_verb_with_every_operand_named_or_that_only_reads_is_not(self):
        for text in STDIN_NAMED:
            with self.subTest(command=text):
                self.assertEqual(unnamed(text), [], text)

    def test_the_literal_words_of_an_upstream_stage_are_named_operands(self):
        result = analyse("echo a b | xargs rm")
        self.assertEqual(({w.path for w in result.writes}, result.unnamed), ({"a", "b"}, []))

    def test_xargs_keeps_the_arguments_it_was_given_as_the_command(self):
        """The marker is not an argument: the commands and writes are what they were."""
        self.assertIn(("rm", ("-rf",)), commands("cat list | xargs rm -rf"))
        self.assertEqual(paths("ls | xargs touch named"), {"named"})
        self.assertNotIn("<stdin>", " ".join(" ".join(argv) for _, argv in commands("ls | xargs rm")))

    def test_a_program_that_redirects_or_opens_a_file_for_writing_is_unnamed(self):
        for text, verb in INLINE_WRITES:
            with self.subTest(command=text):
                self.assertEqual(unnamed(text), [(verb, "program")], text)

    def test_a_program_that_only_reads_is_not(self):
        for text in INLINE_READS:
            with self.subTest(command=text):
                self.assertEqual(unnamed(text), [], text)

    def test_a_script_file_or_module_has_no_inline_program_to_read(self):
        for text in ("python script.py", "python -m pytest tests", "node app.js", "perl script.pl", "bash script.sh", "make build"):
            with self.subTest(command=text):
                self.assertEqual(unnamed(text), [], text)

    def test_the_program_is_still_returned_as_code_and_names_no_write(self):
        self.assertIn('{print > "out"}', analyse("awk '{print > \"out\"}' f").code)
        self.assertEqual(paths("awk '{print > \"out\"}' f"), set())

    def test_powershell_cmdlets_that_take_their_path_from_the_pipeline_are_unnamed(self):
        for text in ("Get-ChildItem *.pyc | Remove-Item", "Get-ChildItem | Remove-Item -Recurse", "ls | rm", "gci | ri",
                     "Get-ChildItem | Move-Item -Destination d", "Get-ChildItem | Rename-Item -NewName x", "Get-Content a | Clear-Content",
                     "powershell -Command \"Get-ChildItem | Remove-Item\""):
            with self.subTest(command=text):
                self.assertEqual([entry.how for entry in analyse(text, ps=True).unnamed], ["stdin"], text)

    def test_powershell_that_names_its_path_or_only_reads_is_not(self):
        for text in ("Remove-Item x", "Get-ChildItem | Remove-Item -Path x", "'x' | Out-File out.txt", "'x' | Set-Content out.txt",
                     "Get-ChildItem | Select-Object Name", "Get-ChildItem | Where-Object Length -gt 5", "Get-ChildItem | Copy-Item -Destination d",
                     "Get-ChildItem | Export-Csv out.csv", "Get-Content a | Add-Content b", "cmd /c dir", "[System.IO.File]::ReadAllText('x')",
                     "[System.IO.File]::Exists('x')"):
            with self.subTest(command=text):
                self.assertEqual(unnamed(text, ps=True), [], text)

    def test_powershell_dotnet_file_calls_are_unnamed(self):
        for text in ("[System.IO.File]::WriteAllText('x','y')", "[IO.File]::Delete('x')", "[System.IO.Directory]::CreateDirectory('d')"):
            with self.subTest(command=text):
                self.assertEqual([entry.how for entry in analyse(text, ps=True).unnamed], ["program"], text)

    def test_a_bash_pipe_stage_does_not_make_a_verb_stdin_fed(self):
        self.assertEqual(unnamed("ls | rm"), [])
        self.assertEqual(unnamed("Get-ChildItem | Remove-Item"), [])

    def test_text_below_the_nesting_cap_is_unnamed_as_it_is_code(self):
        text = "touch x"
        for _ in range(12):
            text = "sh -c " + "'" + text.replace("'", "'\\''") + "'"
        self.assertEqual([entry.how for entry in analyse(text).unnamed], ["nested"])
        self.assertEqual(unnamed("sh -c 'sh -c \"touch x\"'"), [])

    def test_the_same_unnamed_write_is_reported_once(self):
        self.assertEqual(unnamed("ls | xargs rm; ls | xargs rm; ls | xargs rm"), [("rm", "stdin")])
        self.assertEqual(len(unnamed("awk '{print > \"a\"}' f; awk '{print > \"b\"}' f")), 1)

    def test_the_awk_scanner_tells_a_comparison_from_a_redirect(self):
        for program, writes in (
            ('{print > "out"}', True), ('{print >> "out"}', True), ("{print $1, $2 > f}", True), ('{printf("%s", $1) > f}', True),
            ("$1 > 5", False), ("{print ($1 > 5)}", False), ("{if ($1 > 5) print $1; else print 0}", False), ("{print a > b ? 1 : 2}", True),
            ('{print "a > b"}', False), ("/>/ {print}", False), ("$0 ~ /a>b/ {print}", False), ("# print > f\n{print}", False),
            ("{print; x = $1 > 5}", False), ('{print $1} END {print NR > "c"}', True), ("a || b", False), ('{print $1 > "/dev/stderr"}', False),
            ('{print $1 >> "/dev/null"}', False), ('{print $1 | "sort"}', False), ('{print $1 | "tee f"}', True),
            ('{system("ls")}', False), ('{system("rm " $1)}', True), ('{system ("touch x")}', True), ("{x = 4 / 2; print x}", False),
            ('{print "\\"" > f}', True), ('{print "unterminated', False),
        ):
            with self.subTest(program=program):
                self.assertEqual(_cmdscan._awk_writes(program), writes, program)

    def test_hostile_program_text_is_scanned_in_linear_time(self):
        """The searches are bounded: a 100 KB program of the shapes that make a backtracking pattern quadratic stays quick."""
        size = 100_000
        for text in ("python3 -c \"" + "open " * (size // 5) + "\"", "python3 -c \"" + "open(a,'b" * (size // 9) + "\"",
                     "python3 -c \"" + "'\" " * (size // 3) + "system rm\"", "awk '" + "print ((((( " * (size // 12) + "' f",
                     "awk '" + "/ " * (size // 2) + "' f", "sed '" + "/gggggggggggggggg" * (size // 17) + "' f", "sed '" + "; e " * (size // 4) + "' f"):
            with self.subTest(command=text[:30]):
                start = time.perf_counter()
                analyse(text)
                self.assertLess(time.perf_counter() - start, 2.0)


# A shell or interpreter that reads its program from a pipe: the program is not in the command line.
PIPED_PROGRAMS = (
    ("echo 'rm x' | sh", "sh"), ("echo 'touch x' | bash", "bash"), ("cat script.sh | bash", "bash"), ("curl -s http://h/x | sh", "sh"),
    ("printf 'rm a\\nrm b\\n' | sh", "sh"), ("echo 'rm x' | zsh", "zsh"), ("echo 'rm x' | dash", "dash"), ("echo 'rm x' | ksh", "ksh"),
    ("echo 'rm x' | sudo sh", "sh"), ("echo 'rm x' | env bash", "bash"), ("echo 'rm x' | sh -s", "sh"), ("ls | bash -x", "bash"),
    ("echo 'rm x' | python3", "python3"), ("echo 'x' | python3 -", "python3"), ("echo 'x' | node", "node"), ("echo 'x' | perl", "perl"),
    ("echo 'x' | ruby", "ruby"), ("echo 'x' | php", "php"), ("echo 'x' | lua -", "lua"),
    ("echo 'del x' | cmd", "cmd"),
)
PIPED_POWERSHELL = (
    ("'Remove-Item x' | powershell", "powershell"), ("'Remove-Item x' | pwsh", "pwsh"), ("'Remove-Item x' | pwsh -Command -", "pwsh"),
    ("'Remove-Item x' | iex", "iex"), ("'Remove-Item x' | Invoke-Expression", "invoke-expression"),
)
NOT_PIPED_PROGRAMS = (
    "bash script.sh", "sh ./run.sh arg", "bash -c 'ls'", "bash -lc 'echo hi'", "sh -n script.sh", "bash --version", "sh --help",
    "bash < script.sh", "bash <<< 'ls'", "bash <<EOF\nls\nEOF", "echo hi | grep h", "ls | sort | wc -l", "cat f | python3 -c 'import sys'",
    "cat f | python3 -m json.tool", "cat f | python3 script.py", "cat f | node -p '1+1'", "cat f | node app.js", "cat f | perl -ne 'print'",
    "cat f | perl script.pl", "cat f | ruby -ne 'print'", "cat f | ruby -e 'puts 1'", "cat f | php -r 'echo 1;'", "echo x | xargs sh script.sh",
    "bash", "python3", "eval 'ls'", "ls | awk '{print $1}'",
)

class PipedProgramTests(unittest.TestCase):
    """A shell or interpreter that reads its program from a pipe: the program is not in the command line, so the write has no named target."""

    def test_a_shell_or_interpreter_that_reads_its_program_from_a_pipe_is_unnamed(self):
        for text, verb in PIPED_PROGRAMS:
            with self.subTest(command=text):
                self.assertEqual(unnamed(text), [(verb, "stdin")], text)
        for text, verb in PIPED_POWERSHELL:
            with self.subTest(command=text):
                self.assertEqual(unnamed(text, ps=True), [(verb, "stdin")], text)

    def test_a_program_in_the_command_or_a_script_file_is_not(self):
        for text in NOT_PIPED_PROGRAMS:
            with self.subTest(command=text):
                self.assertEqual(unnamed(text), [], text)

    def test_a_here_document_or_here_string_is_read_and_its_writes_are_named(self):
        for text, expected in (("bash <<< 'rm x'", {"x"}), ("sh <<< 'echo y > out'", {"out"}), ("bash <<EOF\ntouch a\nrm b\nEOF", {"a", "b"})):
            with self.subTest(command=text):
                result = analyse(text)
                self.assertEqual(({w.path for w in result.writes}, result.unnamed), (expected, []))



# patch and git apply write the files their diff names, unless they only check.
DIFF_APPLIERS = (
    "patch -p1 < fix.diff", "patch -p1 -i fix.diff", "cat fix.diff | patch -p1", "patch < fix.diff", "patch -d src -p1 < fix.diff",
    "git apply fix.patch", "git apply < fix.patch", "git apply -p1 fix.patch", "git apply --apply --stat fix.patch", "cat fix.patch | git apply",
    "git diff | git apply -R", "git -C repo apply fix.patch", "sudo patch -p1 < fix.diff",
)
DIFF_CHECKS = (
    "git apply --check fix.patch", "git apply --stat fix.patch", "git apply --numstat fix.patch", "git apply --summary fix.patch",
    "git apply --check < fix.patch", "cat fix.patch | git apply --stat", "git apply --check --index fix.patch",
    "patch --dry-run -p1 < fix.diff", "patch --dry-run -p1 -i fix.diff", "patch -C -p1 < fix.diff", "cat fix.diff | patch --dry-run -p1",
    "patch --check -p1 < fix.diff", "patch file.txt fix.diff",
)



class DiffApplierTests(unittest.TestCase):
    """``patch`` and ``git apply`` write the files their diff names, which the command line does not: unnamed unless they only check."""

    def test_patch_and_git_apply_write_the_files_their_diff_names(self):
        for text in DIFF_APPLIERS:
            with self.subTest(command=text):
                self.assertEqual([u.how for u in analyse(text).unnamed], ["diff"], text)

    def test_a_check_or_a_named_file_is_not_a_diff_applied(self):
        for text in DIFF_CHECKS:
            with self.subTest(command=text):
                self.assertEqual(analyse(text).unnamed, [], text)

    def test_the_helpers_agree_with_the_analyser_about_what_only_checks(self):
        self.assertTrue(_cmdscan.git_dry_run("apply", ["--check"]))
        self.assertTrue(_cmdscan.git_dry_run("apply", ["--stat", "--numstat"]))
        self.assertFalse(_cmdscan.git_dry_run("apply", ["--check", "--apply"]))
        self.assertFalse(_cmdscan.git_dry_run("apply", []))
        self.assertFalse(_cmdscan.git_dry_run("commit", ["--check"]))
        self.assertTrue(_cmdscan.patch_dry_run(("--dry-run", "-p1")))
        self.assertTrue(_cmdscan.patch_dry_run(("-C", "-p1")))
        self.assertFalse(_cmdscan.patch_dry_run(("-p1",)))



def hidden(text: str, ps: bool = False) -> list:
    """What the commands a launcher runs would write, as ``(sorted paths, unnamed)`` for each analysis below the line's own."""
    out, pending = [], list(analyse(text, ps).hidden)
    while pending:
        item = pending.pop(0)
        out.append((sorted(write.path for write in item.writes), [(u.verb, u.how) for u in item.unnamed]))
        pending.extend(item.hidden)
    return out


# Commands a launcher runs, which only a read-only run reads: the main analysis stays what it was.
LAUNCHED = (
    ("ls | parallel rm", [([], [("rm", "stdin")])]),
    ("ls | parallel rm {}", [(["{}"], [])]),
    ("ls | parallel -j4 rm {}", [(["{}"], [])]),
    ("ls | parallel -j 4 rm", [([], [("rm", "stdin")])]),
    ("ls | parallel --will-cite -N1 touch", [([], [("touch", "stdin")])]),
    ("parallel rm ::: a b c", [(["a", "b", "c"], [])]),
    ("parallel -a list rm", [([], [("rm", "stdin")])]),
    ("parallel rm :::: list", [([], [("rm", "stdin")])]),
    ("parallel -I@@ rm @@ ::: a", [(["a"], [])]),
    ("ls | parallel -I@@ rm @@", [(["@@"], [])]),
    ("ls | parallel mv {} out/", [(["out/", "{}"], [])]),
    ("ls | parallel cp {} out/", [(["out/"], [])]),
    ("ls | parallel gzip", [([], [("gzip", "stdin")])]),
    ("ls | parallel rm {.}", [(["{.}"], [])]),
    ("echo a b | parallel rm", [(["a", "b"], [])]),
    ("ls | entr rm /_", [(["/_"], [])]),
    ("ls | entr -r rm /_", [(["/_"], [])]),
    ("ls | entr -s 'rm x; touch y'", [(["x", "y"], [])]),
    ("ls | entr sh -c 'rm x'", [(["x"], [])]),
    ("watch 'rm x'", [(["x"], [])]),
    ("watch -n 1 'touch x'", [(["x"], [])]),
    ("ls | parallel parallel rm", [([], []), ([], [("rm", "stdin")])]),
)
LAUNCHED_READS = (
    "ls | parallel echo {}", "ls | parallel -j4 wc -l {}", "ls | parallel grep x", "parallel echo ::: a b c", "ls | parallel sed -n 1p",
    "ls | entr echo changed", "ls | entr -s 'make test'", "watch -n 5 ls", "watch 'ls -l'", "watch -n1 df",
)

class LauncherTests(unittest.TestCase):
    """The commands a launcher (``parallel``, ``entr``, ``watch``) runs: read for the read-only rule only, in analyses of their own, so the main analysis stays what it was."""

    def test_what_a_launcher_runs_is_read_only_for_the_read_only_rule(self):
        for text, expected in LAUNCHED:
            with self.subTest(command=text):
                self.assertEqual(sorted(hidden(text)), sorted(expected), text)
                main = analyse(text)
                self.assertEqual((main.writes, main.unnamed), ([], []), text)
                self.assertFalse({c.verb for c in main.commands} & {"rm", "touch", "mv", "gzip", "cp"}, text)

    def test_a_launcher_that_runs_a_read_finds_nothing(self):
        for text in LAUNCHED_READS:
            with self.subTest(command=text):
                self.assertTrue(all(not paths and not named for paths, named in hidden(text)), text)



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
