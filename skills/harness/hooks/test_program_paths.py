"""Literal Python target regressions; code strings are analyzed, never executed."""
import unittest

import _cmdscan
import _program_paths


class ProgramPathTests(unittest.TestCase):
    def test_literal_write_targets(self):
        cases = {
            'open("out", "w")': {"out"},
            'open(file="out", mode="a")': {"out"},
            'Path("out").write_text("data")': {"out"},
            'Path("out").open("wb")': {"out"},
            'os.rename("source", "destination")': {"source", "destination"},
            'shutil.copyfile("source", "destination")': {"destination"},
            'shutil.move("source", "destination")': {"source", "destination"},
            'Path("source").rename("destination")': {"source", "destination"},
            'os.remove("out")': {"out"},
            'os.replace("source", "destination")': {"source", "destination"},
            'shutil.rmtree("out")': {"out"},
            'shutil.copy("source", "destination")': {"destination"},
            'Path("source").replace("destination")': {"source", "destination"},
            'Path("source").move("destination")': {"source", "destination"},
            'Path("source").copy("destination")': {"destination"},
            'p.copy("destination")': {"destination"},
            'import os as o; o.remove("out")': {"out"},
            'import shutil as sh; sh.rmtree("out")': {"out"},
            'import shutil as sh; exec("sh.rmtree(\\"out\\")")': {"out"},
        }
        for code, paths in cases.items():
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual({write.path for write in result.writes}, paths)
                self.assertFalse(any(write.unresolved for write in result.writes))
                self.assertEqual(result.unnamed, [])

    def test_a_function_imported_by_name_or_named_to_getattr_is_the_module_function(self):
        """`from shutil import rmtree as r; r(D)` and `getattr(os, "remove")(P)` reached a frozen boundary: a call was
        read by the name it is written with, and `r` and `getattr(...)` name no file function. `posix` and `nt` hold the
        functions `os` has, so one imported from them is `os`'s."""
        cases = {
            'from shutil import rmtree as r; r("out")': {"out"},
            'from os import remove as delete; delete("out")': {"out"},
            'from os import remove; remove("out")': {"out"},
            'from posix import remove as delete; delete("out")': {"out"},
            'from nt import mkdir as make; make("out")': {"out"},
            'import os; getattr(os, "remove")("out")': {"out"},
            'import shutil; getattr(shutil, "move", None)("source", "destination")': {"source", "destination"},
            'exec("from shutil import rmtree as r"); r("out")': {"out"},
            'from shutil import rmtree as r; exec("r(\\"out\\")")': {"out"},
            'from io import open as o; o("out", "w")': {"out"},
        }
        for code, paths in cases.items():
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual({write.path for write in result.writes}, paths)
                self.assertFalse(any(write.unresolved for write in result.writes))

    def test_copy_into_and_move_into_write_under_the_directory_they_name(self):
        """`Path.copy_into` and `Path.move_into` (Python 3.14) were no file operation to the pass at all."""
        cases = {
            'Path("source").copy_into("destination")': {("destination/source", "cp -r")},
            'Path("source").move_into("destination")': {("source", "mv"), ("destination/source", "cp -r")},
            'Path("source").copy_into(target_dir="destination")': {("destination/source", "cp -r")},
            # Called on the class, the method names its source first.
            'Path.copy_into(Path("source"), "destination")': {("destination/source", "cp -r")},
            'Path.move_into(Path("source"), target_dir="destination")': {("source", "mv"), ("destination/source", "cp -r")},
            # A source the pass cannot name may land anywhere under the directory, which a copy there reaches.
            'p.copy_into("destination")': {("destination", "cp -r")},
        }
        for code, writes in cases.items():
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual({(write.path, write.via) for write in result.writes}, writes)
                self.assertFalse(any(write.unresolved for write in result.writes))
        for code in ('Path("source").copy_into(directory)', 'p.move_into("destination")'):
            with self.subTest(code=code):
                self.assertTrue(any(write.unresolved for write in _cmdscan.analyse("python3 -c '" + code + "'").writes))

    def test_a_file_function_used_other_than_by_calling_it_is_an_unplaced_write(self):
        """`f = os.remove; f(P)` reached a frozen boundary: the pass read only calls, and `f` names no file function. A
        file function the program assigns, passes, stores or returns may be called anywhere, and so may whatever a
        `getattr` with a name built at run time returns."""
        for code in ('import os; f = os.remove; f("out")', 'import os; list(map(os.remove, paths))',
                     'import shutil, functools; functools.partial(shutil.rmtree, "out")()',
                     'import os; handlers = {"rm": os.remove}; handlers["rm"]("out")',
                     'import os; pick = lambda: os.remove; pick()("out")', 'from os import remove; f = remove; f("out")',
                     'import os; f = getattr(os, "remove"); f("out")', 'import os; getattr(os, name)("out")',
                     'f = open; f("out", "w")', 'w = Path("out").write_text; w("data")',
                     'import shutil; u = shutil.unpack_archive; u("a.zip", "out")'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertTrue(any(write.unresolved for write in result.writes), code)

    def test_getattr_reached_other_than_by_its_own_name_is_an_unplaced_write(self):
        """`g = getattr; g(os, "remove")(P)` reached a frozen boundary: the pass read `getattr` only as a call by that
        name. Reached any other way, as a value, an attribute or `__getattribute__`, it may name any function."""
        for code in ('import os; g = getattr; g(os, "remove")("out")', 'import builtins, os; builtins.getattr(os, "remove")("out")',
                     'import os; os.__getattribute__("remove")("out")', 'import os; object.__getattribute__(os, "remove")("out")',
                     'import os; from builtins import getattr as g; g(os, "remove")("out")',
                     'import functools, os; functools.reduce(getattr, ["remove"], os)("out")'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertTrue(any(write.unresolved for write in result.writes), code)

    def test_a_launcher_reached_by_name_by_alias_or_as_a_value_reads_as_its_module_form(self):
        """`from os import system as s`, `from subprocess import run` and `import subprocess as sp` ran their commands
        unread: a launcher was read only through its module's own name. A command run in a literal directory
        (`cwd=`) is judged there, and `os.execv` runs the program it names, not the first word of its argv."""
        cases = {
            'from os import system as s; s("rm -rf x")': ({"x"}, ()),
            'from subprocess import run; run(["rm", "-rf", "x"])': ({"x"}, ()),
            'from subprocess import Popen as P; P(["rm", "x"])': ({"x"}, ()),
            'from subprocess import *; check_call(["rm", "x"])': ({"x"}, ()),
            'from posix import system as s; s("rm x")': ({"x"}, ()),
            'from nt import system as s; s("rm x")': ({"x"}, ()),
            'import subprocess as sp; sp.run(["rm", "x"])': ({"x"}, ()),
            'import subprocess; subprocess.run(["rm", "x"], cwd="sub")': ({"x"}, ("sub",)),
            'import os; os.execv("/bin/rm", ["ls", "x"])': ({"x"}, ()),
        }
        for code, (paths, cwds) in cases.items():
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual((result.writes, result.unnamed), ([], []), code)
                hidden = [write for item in result.hidden for write in item.writes]
                self.assertEqual(({write.path for write in hidden}, {write.cwds for write in hidden}), (paths, {cwds}))
        # As the module form: a command built at run time, or run in a directory or by a program built at run time, and
        # a launcher used other than by calling it, are unplaced writes.
        for code in ('from os import system as s; s(cmd)', 'from subprocess import call; call(c)',
                     'import subprocess as sp; sp.run(c)', 'import subprocess; subprocess.run(["ls"], cwd=d)',
                     'import subprocess; subprocess.run(["ls"], executable="rm")', 'import os; r = os.system',
                     'from subprocess import run; f = run', 'import subprocess; list(map(subprocess.call, commands))',
                     'import subprocess as sp; f = sp.check_output'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertTrue(any(write.unresolved for write in result.writes), code)
        for code in ('from subprocess import run, PIPE; run(["ls"], stdout=PIPE)', 'from os import system as s; s("ls")',
                     'from subprocess import CalledProcessError; print(CalledProcessError)'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual((result.writes, [write for item in result.hidden for write in item.writes]), ([], []))

    def test_exec_and_namespace_lookups_reached_any_way_read_as_the_function_they_name(self):
        """`e = exec`, `builtins.exec`, `vars(os)["remove"]`, `os.__dict__["remove"]`, `globals()["r"]` and
        `operator.attrgetter("remove")` reached a frozen boundary unread: `exec` was read only by its own name and a
        namespace lookup not at all. A literal program or name is read as the call it makes; one built at run time,
        a namespace used other than by a lookup, and `attrgetter` or `methodcaller` given a name that may reach a file
        function are unplaced writes."""
        cases = {
            'e = exec; e("import os; os.remove(\\"out\\")")': {"out"},
            'e = exec; f = e; f("import os; os.remove(\\"out\\")")': {"out"},
            'import builtins as b; b.exec("import os; os.remove(\\"out\\")")': {"out"},
            'from builtins import exec as e; e("import os; os.remove(\\"out\\")")': {"out"},
            '__builtins__.exec("import os; os.remove(\\"out\\")")': {"out"},
            'import builtins; vars(builtins)["exec"]("import os; os.remove(\\"out\\")")': {"out"},
            'e = exec; e("from os import remove as r"); r("out")': {"out"},
            'import os; vars(os)["remove"]("out")': {"out"},
            'import os; os.__dict__.get("remove")("out")': {"out"},
            'from os import remove as r; globals()["r"]("out")': {"out"},
        }
        for code, paths in cases.items():
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual({write.path for write in result.writes}, paths)
                self.assertFalse(any(write.unresolved for write in result.writes))
        for code in ('e = exec; e(code)', 'import builtins; builtins.eval(code)', 'list(map(exec, programs))',
                     'exec("e = exec"); e(code)', 'import os; vars(os)[name]("out")',
                     'import os; d = vars(os); d["remove"]("out")', 'import os; ns = os.__dict__; ns["remove"]("out")',
                     'from os import remove as r; globals()[name]("out")',
                     'import operator, os; operator.attrgetter("remove")(os)("out")',
                     'import operator, os; operator.methodcaller("remove", "out")(os)',
                     'import operator, os; operator.attrgetter(name)(os)("out")',
                     'import os; from operator import attrgetter as a; a("remove")(os)("out")',
                     'import inspect, os; inspect.getattr_static(os, "remove")("out")'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertTrue(any(write.unresolved for write in result.writes), code)
        for code in ('e = exec; e("print(1)")', 'import os; print(vars(os)["sep"])', 'print(vars(object()))',
                     'import operator; print(sorted([2, 1], key=operator.attrgetter("real")))'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual((result.writes, result.unnamed), ([], []), code)

    def test_renames_fifos_temporary_files_descriptors_and_a_moved_working_directory(self):
        """`os.renames`, `os.mkfifo`, `os.mknod` and `tempfile.mkstemp(dir=...)` reached a frozen boundary unread, and a
        path given with `dir_fd=` or after `os.chdir` was placed under the working directory. A temporary file goes
        somewhere in the directory it names, or, without one, in the system's own, outside the project."""
        cases = {
            'import os; os.renames("a", "b")': {"a", "b"},
            'import os; os.mkfifo("out")': {"out"},
            'import os; os.mknod("out")': {"out"},
            'import tempfile; tempfile.mkstemp(dir="out")': {"out"},
            'import tempfile; tempfile.NamedTemporaryFile(dir="out", delete=False)': {"out"},
            'from tempfile import mkdtemp; mkdtemp("", "t", "out")': {"out"},
            'print("chdir"); open("out", "w")': {"out"},
        }
        for code, paths in cases.items():
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual({write.path for write in result.writes}, paths)
                self.assertFalse(any(write.unresolved for write in result.writes))
        for code in ('import tempfile; tempfile.mkdtemp(dir=d)', 'import tempfile; tempfile.mkstemp(prefix="../out/")',
                     'import tempfile; tempfile.mkstemp(**options)', 'import os; os.remove("a", dir_fd=fd)',
                     'import os; os.chdir("sub"); os.remove("out")', 'import os; os.chdir("sub"); os.system("rm out")',
                     'import os; getattr(os, "chdir")("sub"); os.remove("out")',
                     'import os; exec("import os; os.chdir(\\"sub\\")"); os.remove("out")'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertTrue(any(write.unresolved for write in result.writes), code)
                self.assertEqual([write for item in result.hidden for write in item.writes], [], code)
        for code in ('import tempfile; print(tempfile.mkstemp())', 'import tempfile; tempfile.TemporaryDirectory(prefix="t")',
                     'import os; os.chdir("sub")'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual((result.writes, result.unnamed), ([], []), code)

    def test_methods_of_strings_lists_and_dicts_are_not_file_operations(self):
        """`"s".replace("a", "b")` was a move of `s` and `a`, `lst.remove("a")` a delete of `a`, `{}.copy()` a copy the
        guard could not place: a read-only run refused all three."""
        for code in ('print("s".replace("a", "b"))', 'lst = ["a"]; lst.remove("a")', 'print({}.copy())', 'd = {}; d.copy()',
                     'print(f"{x}".replace("a", "b"))', 'print([x for x in "ab"].copy())', 's = {"a"}; s.remove("a")',
                     'lst: list = []; lst.remove("a")', '(lst := []); lst.remove("a")'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual((result.writes, result.unnamed), ([], []), code)

    def test_copying_an_object_and_a_call_with_no_target_are_not_file_operations(self):
        """`copy.copy(x)` after `import copy` was a copy the guard could not place, and so was `x.replace(tzinfo=None)`,
        which no file form of `replace` can be: each of them takes a target."""
        for code in ('import copy; copy.copy(x)', 'import copy; copy.deepcopy(x)', 'import copy as c; c.copy(x)',
                     'from copy import copy; copy(x)', 'from copy import deepcopy as dc; dc(x)', 'import copy; f = copy.copy',
                     'import datetime; print(datetime.datetime.now().replace(tzinfo=None))',
                     'df.rename(columns={"a": "b"})', 'x = d.copy()', 'p.move()'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual((result.writes, result.unnamed), ([], []), code)

    def test_the_same_method_on_any_other_receiver_is_still_a_file_operation(self):
        """A receiver is exempt only when it is a literal or a container, or a name bound to nothing else. A module
        reached any other way is still read as one: rebound (`o = os`), returned by a call, or bound where the syntax
        tree shows no binding (`exec("lst = os")`, `globals()`, the same under a name of its own after `from builtins
        import globals as g`, or `sys.modules` swapping the module an `import copy` binds). An `attrgetter` given such a
        name is an unplaced write of its own."""
        runtime = "$<runtime-python-target>"
        cases = {
            'import shutil; s = shutil; s.rmtree("out")': {"out"},
            'import os; o = os; o.remove("out")': {"out"},
            'import os; o = os; o.makedirs("out")': {"out"},
            'import os; o = os; o.replace("source", "destination")': {"source", "destination"},
            'import shutil; s = shutil; s.copy("source", "destination")': {"destination"},
            '__import__("os").remove("out")': {"out"},
            'import importlib; importlib.import_module("shutil").rmtree("out")': {"out"},
            'import sys; sys.modules["os"].remove("out")': {"out"},
            'import os; lst = []; lst = os; lst.remove("out")': {"out"},
            'import os; lst = []; exec("lst = os"); lst.remove("out")': {"out"},
            'import os; lst = []; globals()["lst"] = os; lst.remove("out")': {"out"},
            'import os, sys; lst = []; sys.modules["__main__"].lst = os; lst.remove("out")': {"out"},
            'import os; lst = []; from os import *; lst.remove("out")': {"out"},
            'import os; from builtins import globals as g; lst = []; g()["lst"] = os; lst.remove("out")': {"out"},
            'import os; from builtins import exec as e; lst = []; e("lst = os"); lst.remove("out")': {"out"},
            'import os, gc; lst = []; [d for d in gc.get_referrers(lst) if type(d) is dict][0]["lst"] = os; lst.remove("out")':
                {"out"},
            'import os, operator, sys; lst = []; operator.attrgetter("f_globals")(sys._getframe())["lst"] = os; lst.remove("out")':
                {"out", runtime},
        }
        for code, paths in cases.items():
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual({write.path for write in result.writes}, paths)
                self.assertEqual({write.path for write in result.writes if write.unresolved}, paths & {runtime})
        # A receiver the pass cannot know stays a write, as an unknown call does, and so does `copy` bound to anything
        # but the module, and a call whose arguments may hold a target.
        for code in ('import sys; print(sys.argv[1].replace("a", "b"))', 'import copy, os; copy = os; copy.copy(x)',
                     'import copy; exec("copy = shutil"); copy.copy("x")',
                     'import sys, shutil; sys.modules["copy"] = shutil; import copy; copy.copy("a", "out")',
                     'import sys, shutil; sys.modules["copy"] = shutil; from copy import copy; copy("a", "out")',
                     'import shutil; from sys import modules as m; m["copy"] = shutil; import copy; copy.copy("a", "out")',
                     'import operator, sys, shutil; operator.attrgetter("modules")(sys)["copy"] = shutil; import copy; '
                     'copy.copy("a", "out")',
                     'import io, pickle, shutil; pickle.Unpickler(io.BytesIO()).find_class("sys", "modules")["copy"] = shutil; '
                     'import copy; copy.copy("a", "out")',
                     'p.replace(**options)', 'shutil.copy(src=a, dst=b)'):
            with self.subTest(code=code):
                self.assertTrue(_cmdscan.analyse("python3 -c '" + code + "'").writes, code)

    def test_runtime_paths_modes_and_other_mutators_are_not_evaluated(self):
        for code in ('open(target,"w")', 'open("out", mode)',
                     'open("out", **options)', 'Path(target).write_bytes(data)',
                     'os.write(fd,data)', 'open("out","w"); os.system(command)',
                     'open("out","w"); shutil.unpack_archive(archive)', 'p.replace("destination")'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertTrue(result.writes)
                if code != 'open("out", mode)' and code != 'open("out", **options)':
                    self.assertTrue(any(write.unresolved for write in result.writes))

    def test_deep_qualifier_cannot_fail_open_during_target_rendering(self):
        code = "f." + "attribute." * 700 + "call()"
        result = _cmdscan.analyse("python3 -c '" + code + "'")
        self.assertTrue(any(write.unresolved for write in result.writes))

    def test_module_opens_read_flags_and_read_only_launches_are_reads(self):
        for code in ('import gzip; print(gzip.open("in.gz").read())', 'import gzip; gzip.open("in.gz", "rb").read()',
                     'import codecs; codecs.open("in.txt", "r", "utf-8").read()', 'import tarfile; tarfile.open("in.tar").getnames()',
                     'from PIL import Image; Image.open("in.png")', 'import os; fd = os.open("in.txt", os.O_RDONLY)',
                     'import os; print(os.popen("cat in.txt").read())', 'import subprocess; subprocess.check_output(["git", "log"])',
                     'import subprocess; subprocess.check_output(["git", "status"], cwd="src")', 'p.open()', 'p.open("r")'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual(result.writes, [], code)
                self.assertEqual(result.unnamed, [], code)
                self.assertFalse(any(item.writes or item.unnamed for item in result.hidden), code)

    def test_module_opens_for_writing_write_flags_and_extractions_are_placed(self):
        cases = {'import tarfile; tarfile.open("out.tar", "w")': {"out.tar"}, 'import gzip; gzip.open("out.gz", "wb")': {"out.gz"},
                 'import codecs; codecs.open("out.txt", "w", "utf-8")': {"out.txt"}, 'import os; os.open("out", os.O_WRONLY | os.O_CREAT)': {"out"},
                 'import os; os.open("out", flags)': {"out"}, 'import tarfile; tarfile.open("a.tar").extractall("dest")': {"dest"},
                 'import zipfile; zipfile.ZipFile("a.zip").extract("f", "dest")': {"dest"}, 'exec("open(\\"out\\", \\"w\\")")': {"out"}}
        for code, paths in cases.items():
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual({write.path for write in result.writes}, paths, code)
                self.assertFalse(any(write.unresolved for write in result.writes), code)
                if "extract" in code:
                    self.assertEqual({write.via for write in result.writes}, {"archive-extract"}, code)

    def test_runtime_modes_programs_and_destinations_stay_unplaced(self):
        for code in ('p.open("w")', 'p.open(mode)', 'import zipfile; zipfile.ZipFile("a.zip").extractall()', 'exec(code)',
                     'import os; os.system(cmd)', 'import subprocess; subprocess.run(args)', 'import subprocess; subprocess.run(["rm", name])'):
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertTrue(any(write.unresolved for write in result.writes), code)

    def test_a_literal_command_is_read_by_the_shell_analyser(self):
        cases = {'import os; os.system("tar -xf a.tar -C dest")': {"dest"},
                 'import subprocess; subprocess.run(["rsync", "-a", "sub/", "dest/"])': {"dest/"},
                 'import subprocess; subprocess.run("curl -o dest/f https://h/x", shell=True)': {"dest/f"},
                 'import os; os.system("rm -rf x")': {"x"}, 'import os; os.execvp("rm", ["rm", "-rf", "x"])': {"x"}}
        for code, paths in cases.items():
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual((result.writes, result.unnamed), ([], []), code)
                self.assertEqual({write.path for item in result.hidden for write in item.writes}, paths, code)
        result = _cmdscan.analyse("python3 -c 'import os; os.system(\"cat list | xargs rm\")'")
        self.assertTrue(any(item.unnamed for item in result.hidden))

    def test_literal_command_reads_only_literal_text(self):
        import ast

        def command(source):
            return _program_paths.literal_command(ast.parse(source).body[0].value)

        self.assertEqual(command('os.system("a b")'), "a b")
        self.assertEqual(command('subprocess.run(["a", "b"], cwd="x")'), "a b")
        self.assertEqual(command('subprocess.run(args=("a",))'), "a")
        self.assertEqual(command('os.execvp("rm", ["rm", "x"])'), "rm x")
        for source in ('os.system(cmd)', 'subprocess.run(["a", b])', 'subprocess.run(f"a {b}")', 'f()', 'subprocess.run([])'):
            self.assertIsNone(command(source), source)

    def test_reads_and_bounded_parse_fallback(self):
        for code in ('open("input")', 'open("input", "rb")', 'Path("input").open("r")'):
            self.assertEqual(_program_paths.python_targets(code, lambda func: False), [])
        for code in ('open(', '#' * (_program_paths.MAX_SOURCE + 1)):
            self.assertIsNone(_program_paths.python_targets(code, lambda func: False))


if __name__ == "__main__":
    unittest.main()
