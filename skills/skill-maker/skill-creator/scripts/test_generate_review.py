"""Regression tests for the eval viewer: embedding, symlinks, sort order and the local server.

The viewer lives in eval-viewer/ (a directory name that is not importable), so it is
loaded by path. Nothing here opens a socket: the request handler is driven over an
in-memory connection.
"""
import contextlib
import importlib.util
import io
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

CREATOR = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("generate_review_under_test", CREATOR / "eval-viewer" / "generate_review.py")
gr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gr)

HOSTILE = "<html><script>fetch('/api/feedback')</script></html> --><!--<script> &amp; \u2028\u2029"


def make_run(root: Path, name: str = "eval-1", config: str = "with_skill", outputs: dict | None = None,
             metadata: dict | None = None) -> Path:
    run = root / name / config
    (run / "outputs").mkdir(parents=True)
    for filename, text in (outputs if outputs is not None else {"page.html": HOSTILE}).items():
        (run / "outputs" / filename).write_text(text, encoding="utf-8")
    if metadata is not None:
        (root / name / "eval_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return run


def make_symlink(test: unittest.TestCase, link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        test.skipTest("this host cannot create symlinks")


class ScriptTexts(HTMLParser):
    """The text of each <script> element as a browser would end it: at the first </script."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts: list[str] = []
        self._inside = False

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self._inside = True
            self.scripts.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._inside = False

    def handle_data(self, data):
        if self._inside:
            self.scripts[-1] += data


def embedded_literal(page: str) -> tuple[str, dict]:
    start = page.index("const EMBEDDED_DATA = ") + len("const EMBEDDED_DATA = ")
    value, end = json.JSONDecoder().raw_decode(page, start)
    return page[start:end], value


class EmbeddingTests(unittest.TestCase):
    """An output containing </script> (every HTML deliverable with a script does) must not end the data script."""

    def page_for(self, tmp: str) -> str:
        make_run(Path(tmp), outputs={"page.html": HOSTILE, "notes.md": HOSTILE}, metadata={"eval_id": 1, "prompt": HOSTILE})
        return gr.generate_html(gr.find_runs(Path(tmp)), "skill " + HOSTILE)

    def test_data_script_survives_a_closing_script_tag_in_the_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = self.page_for(tmp)
        scripts = ScriptTexts()
        scripts.feed(page)
        data_script = next(s for s in scripts.scripts if "EMBEDDED_DATA" in s)
        value, _ = json.JSONDecoder().raw_decode(data_script, data_script.index("const EMBEDDED_DATA = ") + len("const EMBEDDED_DATA = "))
        self.assertEqual(HOSTILE, value["runs"][0]["outputs"][0]["content"])
        self.assertEqual(HOSTILE, value["runs"][0]["prompt"])
        self.assertEqual("skill " + HOSTILE, value["skill_name"])

    def test_the_page_gains_no_script_end_tag_from_the_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = self.page_for(tmp)
        template = (CREATOR / "eval-viewer" / "viewer.html").read_text(encoding="utf-8")
        self.assertEqual(template.lower().count("</script"), page.lower().count("</script"))

    def test_the_embedded_literal_holds_no_markup_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            literal, _ = embedded_literal(self.page_for(tmp))
        self.assertFalse({"<", ">", "&"} & set(literal))

    def test_line_separators_stay_escaped(self):
        # ensure_ascii already writes U+2028/2029 as escapes; a JS parser that predates
        # ES2019 rejects them raw. Pinned so a change to json.dumps cannot silently drop it.
        with tempfile.TemporaryDirectory() as tmp:
            literal, _ = embedded_literal(self.page_for(tmp))
        self.assertNotIn("\u2028", literal)
        self.assertNotIn("\u2029", literal)

class TemplateEscapingTests(unittest.TestCase):
    def test_escape_helper_is_safe_inside_a_quoted_attribute(self):
        # The grades table puts escapeHtml(evidence) inside title="...", and innerHTML
        # serialisation does not touch quotes, so the helper has to.
        template = (CREATOR / "eval-viewer" / "viewer.html").read_text(encoding="utf-8")
        helper = template[template.index("function escapeHtml"):]
        helper = helper[:helper.index("\n    }")]
        self.assertIn("&quot;", helper)
        self.assertIn("&#39;", helper)


class SortOrderTests(unittest.TestCase):
    def test_runs_with_and_without_metadata_sort_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_run(root, "eval-a", metadata={"eval_id": 2, "prompt": "p"})
            make_run(root, "eval-b")  # no eval_metadata.json: eval_id is None
            make_run(root, "eval-c", metadata={"eval_id": "three", "prompt": "p"})
            make_run(root, "eval-d", metadata={"eval_id": 1, "prompt": "p"})
            runs = gr.find_runs(root)
        self.assertEqual(["eval-d-with_skill", "eval-a-with_skill", "eval-b-with_skill", "eval-c-with_skill"],
                         [r["id"] for r in runs])


class SymlinkTests(unittest.TestCase):
    SECRET = "TOP-SECRET-TOKEN-1234"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.workspace = self.root / "ws"
        self.secret = self.root / "secret.txt"
        self.secret.write_text(self.SECRET, encoding="utf-8")

    def page(self) -> str:
        return gr.generate_html(gr.find_runs(self.workspace), "skill")

    def test_a_symlinked_output_is_reported_not_read(self):
        run = make_run(self.workspace, outputs={"real.md": "fine"})
        make_symlink(self, run / "outputs" / "notes.md", self.secret)
        make_symlink(self, run / "outputs" / "photo.png", self.secret)
        outputs = {o["name"]: o for o in gr.find_runs(self.workspace)[0]["outputs"]}
        self.assertEqual("text", outputs["real.md"]["type"])
        self.assertEqual({"error"}, {outputs["notes.md"]["type"], outputs["photo.png"]["type"]})
        self.assertNotIn(self.SECRET, self.page())

    def test_a_symlinked_run_directory_is_not_entered(self):
        elsewhere = self.root / "elsewhere"
        make_run(elsewhere, "eval-9", outputs={"leak.md": self.SECRET})
        self.workspace.mkdir()
        make_symlink(self, self.workspace / "eval-9", elsewhere / "eval-9")
        self.assertEqual([], gr.find_runs(self.workspace))

    def test_a_symlinked_outputs_directory_is_not_a_run(self):
        real = self.root / "real-outputs"
        real.mkdir()
        (real / "leak.md").write_text(self.SECRET, encoding="utf-8")
        run = self.workspace / "eval-1" / "with_skill"
        run.mkdir(parents=True)
        make_symlink(self, run / "outputs", real)
        self.assertEqual([], gr.find_runs(self.workspace))

    def test_symlinked_grading_and_metadata_are_ignored(self):
        run = make_run(self.workspace)
        leak = self.root / "leak.json"
        leak.write_text(json.dumps({"prompt": self.SECRET, "eval_id": 7, "expectations": [self.SECRET]}), encoding="utf-8")
        make_symlink(self, run / "grading.json", leak)
        make_symlink(self, run / "eval_metadata.json", leak)
        found = gr.find_runs(self.workspace)[0]
        self.assertIsNone(found["grading"])
        self.assertNotIn(self.SECRET, self.page())


class FakeConnection:
    """Just enough socket for StreamRequestHandler: request bytes in, response bytes collected."""

    def __init__(self, request: bytes):
        self._request = io.BytesIO(request)
        self.response = bytearray()

    def settimeout(self, timeout):
        pass

    def makefile(self, mode, bufsize=-1):
        return self._request

    def sendall(self, data):
        self.response += data


class ServerTests(unittest.TestCase):
    PAGE_HOST = "localhost:3117"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name)
        make_run(self.workspace, outputs={"a.md": "hello"}, metadata={"eval_id": 1, "prompt": "p"})
        self.feedback = self.workspace / "feedback.json"

    def request(self, method: str, path: str, headers: dict | None = None, body: bytes = b"") -> tuple[int, bytes]:
        head = {"Host": self.PAGE_HOST, **(headers or {})}
        raw = f"{method} {path} HTTP/1.1\r\n".encode() + b"".join(f"{k}: {v}\r\n".encode() for k, v in head.items())
        connection = FakeConnection(raw + b"\r\n" + body)
        gr.ReviewHandler(self.workspace, "skill", self.feedback, {}, None, connection, ("127.0.0.1", 50000), None)
        header, _, payload = bytes(connection.response).partition(b"\r\n\r\n")
        return int(header.split(b" ", 2)[1]), payload

    def post(self, body: bytes = b'{"reviews": []}', **headers) -> tuple[int, bytes]:
        merged = {"Content-Type": "application/json", "Content-Length": str(len(body)), **headers}
        return self.request("POST", "/api/feedback", {k: v for k, v in merged.items() if v is not None}, body)

    def test_page_and_feedback_are_served_to_the_loopback_host(self):
        status, body = self.request("GET", "/")
        self.assertEqual(200, status)
        self.assertIn(b"EMBEDDED_DATA", body)
        self.assertEqual((200, b"{}"), self.request("GET", "/api/feedback"))

    def test_a_rebound_host_name_is_refused(self):
        # DNS rebinding: the page's own origin is the attacker's name, resolving to 127.0.0.1.
        for path in ("/", "/api/feedback"):
            self.assertEqual(403, self.request("GET", path, {"Host": "evil.example:3117"})[0], path)
        self.assertEqual(403, self.post(Host="evil.example:3117")[0])
        self.assertFalse(self.feedback.exists())

    def test_a_forwarded_port_is_still_the_same_origin(self):
        self.assertEqual(200, self.post(Host="localhost:9999", Origin="http://localhost:9999")[0])
        self.assertEqual(200, self.request("GET", "/", {"Host": "127.0.0.1:9999"})[0])

    def test_a_cross_origin_write_is_refused(self):
        for origin in ("http://evil.example", "http://localhost:8080", "null", "https://localhost:3117"):
            status, _ = self.post(Origin=origin)
            self.assertEqual(403, status, origin)
        self.assertFalse(self.feedback.exists())

    def test_the_viewers_own_write_and_a_plain_client_are_accepted(self):
        self.assertEqual(200, self.post(Origin=f"http://{self.PAGE_HOST}")[0])
        self.feedback.unlink()
        self.assertEqual(200, self.post()[0])  # curl sends no Origin
        self.assertEqual({"reviews": []}, json.loads(self.feedback.read_text(encoding="utf-8")))

    def test_only_application_json_is_accepted(self):
        for content_type in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
            self.assertEqual(415, self.post(**{"Content-Type": content_type})[0], content_type)
        self.assertEqual(200, self.post(**{"Content-Type": "application/json; charset=utf-8"})[0])

    def test_the_body_length_is_bounded(self):
        status, _ = self.request("POST", "/api/feedback", {
            "Content-Type": "application/json", "Content-Length": "5000000"})  # declared, never sent
        self.assertEqual(413, status)
        self.assertEqual(400, self.post(**{"Content-Length": None})[0])
        self.assertEqual(400, self.post(**{"Content-Length": "many"})[0])
        self.assertFalse(self.feedback.exists())

    def test_malformed_feedback_is_a_client_error(self):
        self.assertEqual(400, self.post(b"not json")[0])
        self.assertEqual(400, self.post(b'{"no": "reviews"}')[0])
        self.assertFalse(self.feedback.exists())

    def test_feedback_is_never_written_through_a_link(self):
        victim = self.workspace.parent / "victim.txt"
        victim.write_text("keep me", encoding="utf-8")
        self.addCleanup(victim.unlink)
        make_symlink(self, self.feedback, victim)
        status, _ = self.post()
        self.assertEqual(500, status)
        self.assertEqual("keep me", victim.read_text(encoding="utf-8"))
        self.assertEqual((200, b"{}"), self.request("GET", "/api/feedback"))


class PortTests(unittest.TestCase):
    """A busy port is taken by someone else; the viewer moves, it does not signal them."""

    class StubServer:
        server_address = ("127.0.0.1", 4242)

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    def run_main(self, address_in_use: bool) -> str:
        binds = []

        def server(address, handler):
            binds.append(address)
            if address_in_use and address[1] == 3117:
                raise OSError("address in use")
            return self.StubServer()

        with tempfile.TemporaryDirectory() as tmp:
            make_run(Path(tmp))
            # The banner meets a strict cp1252 stdout, as it does on a Windows pipe.
            stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict", write_through=True)
            with patch.object(sys, "argv", ["generate_review", tmp]), patch.object(sys, "stdout", stdout), \
                    contextlib.redirect_stderr(io.StringIO()), \
                    patch.object(gr, "HTTPServer", side_effect=server), patch.object(gr.webbrowser, "open"), \
                    patch("subprocess.run", side_effect=AssertionError("must not run a process")), \
                    patch("os.kill", side_effect=AssertionError("must not signal a process")):
                gr.main()
            stdout.flush()
            output = stdout.buffer.getvalue().decode("utf-8")
        self.assertEqual([("127.0.0.1", 3117)] + ([("127.0.0.1", 0)] if address_in_use else []), binds)
        return output

    def test_busy_port_falls_back_without_killing_anything(self):
        self.assertIn("http://localhost:4242", self.run_main(address_in_use=True))

    def test_free_port_is_used_as_asked(self):
        self.run_main(address_in_use=False)


if __name__ == "__main__":
    unittest.main()
