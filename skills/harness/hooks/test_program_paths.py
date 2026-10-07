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
        }
        for code, paths in cases.items():
            with self.subTest(code=code):
                result = _cmdscan.analyse("python3 -c '" + code + "'")
                self.assertEqual({write.path for write in result.writes}, paths)
                self.assertFalse(any(write.unresolved for write in result.writes))
                self.assertEqual(result.unnamed, [])

    def test_runtime_paths_modes_and_other_mutators_are_not_evaluated(self):
        for code in ('open(target,"w")', 'open("out", mode)',
                     'open("out", **options)', 'Path(target).write_bytes(data)',
                     'os.write(fd,data)', 'open("out","w"); os.system(command)',
                     'open("out","w"); shutil.unpack_archive(archive)'):
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
