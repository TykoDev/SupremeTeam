"""Fixture-tree tests for the --scan-scaffold mode of skills/scripts/check_runtime.py.

The scan looks for conservative placeholder and unfinished-work markers in text
files. It reads the code with quoted strings blanked so a marker word inside a
string literal is not a finding, and it reports the path class of every hit so a
reader can tell production code from tests and documents.
"""
from __future__ import annotations

import unittest

import test_check_runtime_detection as fixtures


class ScaffoldCase(fixtures.FixtureTreeCase):
    def scan(self, files: dict[str, str | bytes]) -> list[dict]:
        inspection = self.inspect_tree(files, detect=False, scaffold=True)
        self.assertClean(inspection)
        return inspection["scaffold_markers"]

    def markers(self, files: dict[str, str | bytes]) -> dict[str, list[tuple[int, str]]]:
        found: dict[str, list[tuple[int, str]]] = {}
        for row in self.scan(files):
            found.setdefault(row["file"], []).append((row["line"], row["marker"]))
        return found


class MarkerDetectionTests(ScaffoldCase):
    def test_python_markers(self):
        source = (
            "def unfinished(): pass\n"
            "def also_unfinished():\n"
            "    pass\n"
            "def real():\n"
            "    return compute()\n"
            "def later():\n"
            "    raise NotImplementedError\n"
            "try:\n"
            "    run()\n"
            "except ValueError: pass\n"
            "print('debugging')\n"
            "def none():\n"
            "    return None\n"
        )
        self.assertEqual(
            self.markers({"app.py": source}),
            {
                "app.py": [
                    (1, "EMPTY FUNCTION"),
                    (2, "EMPTY FUNCTION"),
                    (7, "NOT IMPLEMENTED"),
                    (10, "EMPTY ERROR HANDLER"),
                    (11, "DEBUG STATEMENT"),
                    (13, "RETURN NONE"),
                ]
            },
        )

    def test_a_python_function_with_a_real_body_is_not_empty(self):
        source = "def f():\n    pass\n    return 1\n\ndef g():\n    # explain\n    ...\n    print_it()\n"
        self.assertEqual(self.markers({"app.py": source}), {})

    def test_javascript_markers(self):
        source = (
            "function empty() {}\n"
            "const arrow = () => {};\n"
            "try { run(); } catch (error) {}\n"
            "console.log('debugging');\n"
            "function list() { return []; }\n"
            "function object() { return {}; }\n"
            "function nothing() { return null; }\n"
            "function zero() { return 0; }\n"
        )
        self.assertEqual(
            self.markers({"app.js": source}),
            {
                "app.js": [
                    (1, "EMPTY FUNCTION"),
                    (2, "EMPTY FUNCTION"),
                    (3, "EMPTY ERROR HANDLER"),
                    (4, "DEBUG STATEMENT"),
                    (5, "RETURN []"),
                    (6, "RETURN {}"),
                    (7, "RETURN NULL"),
                    (8, "RETURN 0"),
                ]
            },
        )

    def test_typescript_and_module_variants_are_scanned_as_javascript(self):
        for name in ("a.ts", "a.tsx", "a.jsx", "a.mjs", "a.cjs", "a.mts", "a.cts"):
            with self.subTest(file=name):
                self.assertEqual(self.markers({name: "console.debug(1);\n"}), {name: [(1, "DEBUG STATEMENT")]})

    def test_multiline_empty_blocks(self):
        js = "function empty() {\n}\n\nclass A {\n  method() {\n    // nothing yet\n  }\n}\n\nfunction full() {\n  work();\n}\n"
        self.assertEqual(self.markers({"a.js": js}), {"a.js": [(1, "EMPTY FUNCTION"), (5, "EMPTY FUNCTION")]})
        finding = next(row for row in self.scan({"a.js": js}) if row["line"] == 1)
        self.assertEqual(finding["context"], "function empty() {\n}")

    def test_empty_function_shapes_across_lines(self):
        python = "def commented():\n    # explain later\n    pass\n\ndef trailing():\n    pass\n    # nothing else\n\ndef real():\n    pass\n    return 1\n"
        self.assertEqual(self.markers({"a.py": python}), {"a.py": [(1, "EMPTY FUNCTION"), (5, "EMPTY FUNCTION")]})
        allman = "function empty()\n{\n}\n\nfunction filled()\n{\n  work();\n}\n"
        self.assertEqual(self.markers({"a.js": allman}), {"a.js": [(1, "EMPTY FUNCTION")]})
        finding = self.scan({"a.js": allman})[0]
        self.assertEqual(finding["context"], "function empty()\n{\n}")

    def test_go_markers(self):
        source = (
            "package main\n\n"
            "func empty() {}\n\n"
            "func (s *Server) method() {\n}\n\n"
            "func real() {\n\twork()\n}\n\n"
            "func loud() {\n\tfmt.Println(1)\n}\n\n"
            "func swallow() {\n\trecover()\n}\n"
        )
        self.assertEqual(
            self.markers({"main.go": source}),
            {
                "main.go": [
                    (3, "EMPTY FUNCTION"),
                    (5, "EMPTY FUNCTION"),
                    (13, "DEBUG STATEMENT"),
                    (17, "EMPTY ERROR HANDLER"),
                ]
            },
        )

    def test_rust_markers(self):
        source = "fn a() { todo!() }\nfn b() { unimplemented!() }\nfn c() { dbg!(x); }\nfn d() { let _ = run(); }\n"
        self.assertEqual(
            self.markers({"lib.rs": source}),
            {
                "lib.rs": [
                    (1, "NOT IMPLEMENTED"),
                    (1, "TODO"),
                    (2, "NOT IMPLEMENTED"),
                    (3, "DEBUG STATEMENT"),
                    (4, "IGNORED RESULT"),
                ]
            },
        )

    def test_csharp_and_java_markers(self):
        csharp = (
            "class A {\n"
            "  public void A1() { throw new NotImplementedException(); }\n"
            "  public void A2() { Console.WriteLine(1); }\n"
            "  public void A3() { }\n"
            "  private int A4() {\n  }\n"
            "}\n"
        )
        self.assertEqual(
            self.markers({"A.cs": csharp}),
            {"A.cs": [(2, "NOT IMPLEMENTED"), (3, "DEBUG STATEMENT"), (4, "EMPTY FUNCTION"), (5, "EMPTY FUNCTION")]},
        )
        java = "class B {\n  public void b1() { System.out.println(1); }\n  protected void b2() { }\n}\n"
        self.assertEqual(self.markers({"B.java": java}), {"B.java": [(2, "DEBUG STATEMENT"), (3, "EMPTY FUNCTION")]})

    def test_ruby_markers(self):
        source = "def a\n  raise NotImplementedError\nend\n\ndef b\n  nil\nend\n\ndef c\n  work\nend\n\nputs 'x'\n"
        self.assertEqual(
            self.markers({"a.rb": source}),
            {"a.rb": [(2, "NOT IMPLEMENTED"), (5, "EMPTY FUNCTION"), (13, "DEBUG STATEMENT")]},
        )

    def test_shell_markers(self):
        source = (
            "echo TODO\n"
            "exit 0\n"
            "noop() { :; }\n"
            "function quiet {\n  true\n}\n"
            "deploy() {\n  ./run.sh\n}\n"
        )
        self.assertEqual(
            self.markers({"run.sh": source}),
            {
                "run.sh": [
                    (1, "TODO"),
                    (1, "UNFINISHED OUTPUT"),
                    (2, "EXIT 0"),
                    (3, "EMPTY FUNCTION"),
                    (4, "EMPTY FUNCTION"),
                ]
            },
        )
        for name in ("a.bash", "a.zsh", "Makefile"):
            with self.subTest(file=name):
                self.assertEqual(self.markers({name: "echo STUB\n"}), {name: [(1, "STUB"), (1, "UNFINISHED OUTPUT")]})

    def test_language_independent_markers(self):
        text = (
            "lorem ipsum dolor sit amet\n"
            "visit example.com or test.org\n"
            "password: password\n"
            "secret: secret\n"
            "key: changeme\n"
            "host: localhost\n"
            "bind: 0.0.0.0\n"
            "addr: 127.0.0.1\n"
        )
        self.assertEqual(
            self.markers({"config.yaml": text}),
            {
                "config.yaml": [
                    (1, "FILLER PROSE"),
                    (2, "PLACEHOLDER DOMAIN"),
                    (3, "DEFAULT SECRET"),
                    (4, "DEFAULT SECRET"),
                    (5, "CHANGEME"),
                    (5, "DEFAULT SECRET"),
                    (6, "LOCALHOST ADDRESS"),
                    (7, "LOCALHOST ADDRESS"),
                    (8, "LOCALHOST ADDRESS"),
                ]
            },
        )

    def test_marker_vocabulary_in_comments_is_case_insensitive_and_canonical(self):
        vocabulary = {
            "TODO": "TODO",
            "fixme": "FIXME",
            "Hack": "HACK",
            "XXX": "XXX",
            "placeholder": "PLACEHOLDER",
            "stub": "STUB",
            "temporary": "TEMPORARY",
            "temp": "TEMP",
            "dummy": "DUMMY",
            "fake": "FAKE",
            "sample": "SAMPLE",
            "remove this": "REMOVE THIS",
            "remove me": "REMOVE ME",
            "remove before": "REMOVE BEFORE",
            "change me": "CHANGE ME",
            "changeme": "CHANGEME",
            "not implemented": "NOT IMPLEMENTED",
            "coming soon": "COMING SOON",
            "coming   soon": "COMING SOON",
        }
        for written, canonical in vocabulary.items():
            with self.subTest(written=written):
                self.assertEqual(self.markers({"a.py": f"# {written}\n"}), {"a.py": [(1, canonical)]})
        for word in ("fake_data", "stubby", "todos", "tempest"):
            with self.subTest(identifier=word):
                self.assertEqual(self.markers({"a.py": f"{word} = 1\n"}), {})

    def test_comment_styles(self):
        cases = {
            "hash": ("a.py", "x = 1  # TODO later\n", [(1, "TODO")]),
            "slashes": ("a.js", "x = 1; // FIXME later\n", [(1, "FIXME")]),
            "block": ("a.js", "x = 1; /* HACK */\n", [(1, "HACK")]),
            "block spanning lines": ("a.js", "/*\n * TODO first\n * still open\n */\nrun();\n", [(2, "TODO")]),
        }
        for name, (file, source, expected) in cases.items():
            with self.subTest(style=name):
                self.assertEqual(self.markers({file: source}), {file: expected})

    def test_marker_words_inside_string_literals_are_not_findings(self):
        source = (
            "message = 'TODO: tell the user'\n"
            'other = "FIXME in a string"\n'
            "'''\nTODO inside a docstring\n'''\n"
            '"""\nSTUB in another\n"""\n'
            "real = 1  # TODO after code\n"
        )
        self.assertEqual(self.markers({"a.py": source}), {"a.py": [(9, "TODO")]})
        template = "const s = `\nTODO inside a template literal\n`;\nrun(); // TODO real\n"
        self.assertEqual(self.markers({"a.js": template}), {"a.js": [(4, "TODO")]})

    def test_an_apostrophe_does_not_hide_the_lines_after_it(self):
        """A Rust lifetime, a regex literal or a digit separator opens no string that spans lines."""
        cases = {
            "rust lifetime": ("lib.rs", "fn first<'a>(x: &str) -> usize {\n    x.len()\n}\n\nfn later() {\n    todo!()\n}\n", 6),
            "javascript regex": ("a.js", "const re = /'/;\nrun();\n// TODO after the regex\n", 3),
            "digit separator": ("a.cpp", "int big = 1'000;\nint next = 2;\n// TODO after the separator\n", 3),
            "unterminated double quote": ("a.py", 'x = "unterminated\n# TODO next line\n', 2),
        }
        for name, (file, source, line) in cases.items():
            with self.subTest(case=name):
                found = self.markers({file: source})[file]
                self.assertIn(line, [number for number, _ in found])

    def test_quote_state_that_is_meant_to_span_lines_still_does(self):
        source = "text = '''\nline one\nTODO not a finding\n'''\n# TODO a finding\n"
        self.assertEqual(self.markers({"a.py": source}), {"a.py": [(5, "TODO")]})

    def test_string_content_patterns_do_not_match_quoted_forms(self):
        """Pins a known limitation, not a wanted behaviour.

        The language patterns run on the line with its string literals blanked, so
        those that describe string content never match a quoted form. When the scan
        learns to read literals, these expectations change with it.
        """
        source = {
            "a.js": 'throw new Error("not implemented");\n',
            "main.go": 'package main\n\nfunc a() {\n\tpanic("not implemented")\n}\n',
            "B.java": 'class B { void m() { throw new UnsupportedOperationException("not implemented"); } }\n',
            "a.py": 'password = "password"\nurl = "http://localhost:3000"\n',
        }
        self.assertEqual(self.markers(source), {})

    def test_findings_carry_path_class_and_production_flag(self):
        files = {
            "src/app.py": "# TODO\n",
            "tests/test_app.py": "# TODO\n",
            "docs/guide.md": "TODO write this\n",
            "dist/bundle.js": "// TODO\n",
            "vendor/lib.go": "// TODO\n",
        }
        rows = {row["file"]: row for row in self.scan(files)}
        self.assertEqual(
            {name: (row["path_class"], row["production_finding"]) for name, row in rows.items()},
            {
                "src/app.py": ("production", True),
                "tests/test_app.py": ("test", False),
                "docs/guide.md": ("documentation", False),
                "dist/bundle.js": ("generated-or-vendored", False),
                "vendor/lib.go": ("generated-or-vendored", False),
            },
        )

    def test_findings_are_sorted_and_carry_message_and_context(self):
        files = {"b.py": "x = 1\n# FIXME two\n# TODO one\n", "a.py": "# HACK zero\n"}
        rows = self.scan(files)
        self.assertEqual(
            [(row["file"], row["line"], row["marker"]) for row in rows],
            [("a.py", 1, "HACK"), ("b.py", 2, "FIXME"), ("b.py", 3, "TODO")],
        )
        self.assertEqual(rows[1]["message"], "# FIXME two")
        self.assertEqual(rows[1]["context"], rows[1]["message"])

    def test_one_line_reports_each_marker_once(self):
        rows = self.scan({"a.py": "# TODO TODO TODO fix\n"})
        self.assertEqual([(row["line"], row["marker"]) for row in rows], [(1, "TODO")])

    def test_only_text_files_that_are_not_sensitive_are_scanned(self):
        files = {
            "app.py": "# TODO real\n",
            ".env": "# TODO secret file\n",
            ".npmrc": "# TODO registry\n",
            "server.pem": "# TODO cert\n",
            "id_rsa": "# TODO key\n",
            "credentials.json": '{"todo": "TODO"}\n',
            "logo.png": b"\x89PNG TODO \x00",
            "archive.zip": b"PK TODO",
            ".ssh/config": "# TODO ssh\n",
            ".aws/credentials": "# TODO aws\n",
            "node_modules/dep/index.js": "// TODO dependency\n",
        }
        self.assertEqual(self.markers(files), {"app.py": [(1, "TODO")]})

    def test_the_context_of_a_finding_is_redacted(self):
        rows = self.scan(
            {
                "app.py": (
                    "password = 'hunter2hunter2'  # TODO rotate\n"
                    "url = 'https://user:swordfish@host/db'  # FIXME move\n"
                )
            }
        )
        self.assertEqual([row["marker"] for row in rows], ["TODO", "FIXME"])
        for row in rows:
            for value in ("hunter2hunter2", "swordfish"):
                self.assertNotIn(value, row["context"])
                self.assertNotIn(value, row["message"])
        self.assertIn("<redacted>", rows[0]["context"])

    def test_scan_mode_does_not_need_or_load_a_registry(self):
        inspection = self.inspect_tree({"app.py": "# TODO\n"}, detect=False, scaffold=True)
        self.assertEqual(inspection["stacks"], [])
        self.assertIsNone(inspection["classification"])
        self.assertEqual(inspection["start_commands"], [])


if __name__ == "__main__":
    unittest.main()
