"""Secret handling tests for skills/scripts/check_runtime.py.

Two things keep a secret out of the report. Files that are sensitive by name or
location are never read or listed, and every string that does flow from a project
into the report (a start command, a scaffold context line, a diagnostic) goes
through the redactor, which works from context: a secret-named key, a flag, an
auth scheme, credentials in a URL. The tests cover both, end to end through
``check()``, and pin the redactor's forms directly.
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

import check_runtime
import test_check_runtime_detection as fixtures

SECRET = "S3cr3tValue"
#: How deep a structure is followed before its remainder is dropped from the report.
REDACTION_DEPTH_LIMIT = 100


class RedactionFormTests(unittest.TestCase):
    def test_secret_values_are_replaced_in_every_supported_form(self):
        forms = {
            "flag with a space": (f"node server.js --token {SECRET}", "node server.js --token=<redacted>"),
            "flag with an equals sign": (f"node server.js --token={SECRET}", "node server.js --token=<redacted>"),
            "hyphenated flag": (f"run --api-key {SECRET} --port 80", "run --api-key=<redacted> --port 80"),
            "client secret flag": (f"run --client-secret={SECRET} --port 3000", "run --client-secret=<redacted> --port 3000"),
            "environment prefix": (f"API_KEY={SECRET} node server.js", "API_KEY=<redacted> node server.js"),
            "quoted value with spaces": (
                f"export DB_PASSWORD='{SECRET} with spaces' && run",
                "export DB_PASSWORD=<redacted> && run",
            ),
            "bearer header": (
                f"curl -H 'Authorization: Bearer {SECRET}' https://x",
                "curl -H 'Authorization: <redacted>' https://x",
            ),
            "basic header": (
                f'curl -H "Authorization: Basic {SECRET}" https://x',
                'curl -H "Authorization: <redacted>" https://x',
            ),
            "bare bearer": (f"bearer {SECRET}.tail and more", "bearer <redacted>"),
            "url credentials": (f"postgres://app:{SECRET}@db/app", "postgres://<redacted>@db/app"),
            "url token as user": (f"https://{SECRET}:x-oauth@github.com/o/r", "https://<redacted>@github.com/o/r"),
            "url query": (f"https://h/p?sig={SECRET}&x=1", "https://h/p?sig=<redacted>&x=1"),
            "signed url query": (f"https://h/p?X-Amz-Signature={SECRET}", "https://h/p?X-Amz-Signature=<redacted>"),
            "connection url variable": (f"DATABASE_URL=postgres://u:{SECRET}@h/db", "DATABASE_URL=<redacted>"),
            "npm auth token": (
                f"npm publish --//registry.npmjs.org/:_authToken={SECRET}",
                "npm publish --//registry.npmjs.org/:_authToken=<redacted>",
            ),
            "set-cookie": (f"Set-Cookie: session={SECRET}; HttpOnly", "Set-Cookie: <redacted>; HttpOnly"),
            "json object": (f'{{"apiKey": "{SECRET}", "name": "x"}}', '{"apiKey": "<redacted>", "name": "x"}'),
            "cloud secret key": (f'aws_secret_access_key = "{SECRET}"', "aws_secret_access_key = <redacted>"),
            "yaml style": (f"token: {SECRET}", "token: <redacted>"),
            "assignment before a comment": (f"password = '{SECRET}'  # TODO rotate", "password = <redacted>  # TODO rotate"),
            "provider key names": (f"STRIPE_SECRET_KEY={SECRET}", "STRIPE_SECRET_KEY=<redacted>"),
            "quoted scheme value": (f'export AUTH="Bearer {SECRET} and more"; run', "export AUTH=<redacted>; run"),
            "two schemes in one header": (
                f"Authorization: Bearer {SECRET}, Basic {SECRET}2",
                "Authorization: <redacted>, Basic <redacted>",
            ),
            "scheme value ends at the next flag": (f"Bearer {SECRET} --flag x", "Bearer <redacted> --flag x"),
            "escaped quotes": (f'basic \\"{SECRET} more\\" tail', "basic <redacted> tail"),
            "assignment among others": (f"x=1 token={SECRET} y=2", "x=1 token=<redacted> y=2"),
        }
        for name, (text, expected) in forms.items():
            with self.subTest(form=name):
                redacted = check_runtime._redact(text)
                self.assertNotIn(SECRET, redacted)
                self.assertEqual(redacted, expected)

    def test_json_documents_are_redacted_structurally(self):
        self.assertEqual(
            check_runtime._redact(f'{{"token": "{SECRET}", "name": "x"}}'), '{"name": "x", "token": "<redacted>"}'
        )
        self.assertEqual(
            check_runtime._redact(f'["--token", "{SECRET}", "--name", "x"]'), '["--token", "<redacted>", "--name", "x"]'
        )
        self.assertEqual(check_runtime._redact(f"{{not json token={SECRET}}}"), "{not json token=<redacted>}")

    def test_prose_that_only_names_a_credential_is_left_readable(self):
        for text in (
            "authentication is required",
            "Bearer token is required",
            "token must be a string",
            "Authorization header is missing",
            "the token field is required",
        ):
            with self.subTest(text=text):
                self.assertEqual(check_runtime._redact(text), text)

    def test_structured_values_are_redacted_by_key_and_by_flag_position(self):
        value = {
            "apiKey": SECRET,
            "api_key": SECRET,
            "API-KEY": SECRET,
            "name": "kept",
            "nested": {"password": SECRET, "argv": ["--token", SECRET, "--name", "kept"]},
            "headers": ["Bearer", SECRET, "Basic", SECRET],
            "count": 3,
            "enabled": True,
            "nothing": None,
        }
        redacted = check_runtime._redact_value(value)
        self.assertNotIn(SECRET, json.dumps(redacted))
        self.assertEqual(redacted["name"], "kept")
        self.assertEqual(redacted["nested"]["argv"], ["--token", "<redacted>", "--name", "kept"])
        self.assertEqual(redacted["headers"], ["Bearer", "<redacted>", "Basic", "<redacted>"])
        self.assertEqual((redacted["count"], redacted["enabled"], redacted["nothing"]), (3, True, None))

    def test_non_finite_numbers_and_runaway_nesting_are_neutralised(self):
        redacted = check_runtime._redact_value({"a": float("nan"), "b": float("inf"), "c": 1.5})
        self.assertEqual(redacted, {"a": "<non-finite>", "b": "<non-finite>", "c": 1.5})
        deep: dict = {}
        current = deep
        for _ in range(REDACTION_DEPTH_LIMIT + 50):
            current["x"] = {}
            current = current["x"]
        result = check_runtime._redact_value(deep)
        depth = 0
        while isinstance(result, dict):
            result = result["x"]
            depth += 1
        self.assertEqual(result, "<nested value omitted>")
        self.assertEqual(depth, REDACTION_DEPTH_LIMIT)


class ReportRedactionTests(fixtures.FixtureTreeCase):
    def dumped(self, report: dict) -> str:
        return json.dumps(report, sort_keys=True)

    def test_start_commands_are_redacted_from_every_source(self):
        cases = {
            "package script": {
                "package.json": fixtures.package_json(
                    scripts={
                        "dev": f"API_KEY={SECRET}A vite --token {SECRET}B",
                        "start": f"node server.js --password={SECRET}C",
                    }
                )
            },
            "makefile recipe": {"Makefile": f"dev:\n\tSECRET={SECRET}A python app.py --token={SECRET}B\n"},
            "compose command": {
                "compose.yaml": f"services:\n  web:\n    image: node\n    command: node server.js --token={SECRET}A\n"
            },
            "compose command list": {
                "compose.yaml": f'services:\n  web:\n    image: node\n    command: ["node", "--token", "{SECRET}A"]\n'
            },
        }
        for name, tree in cases.items():
            with self.subTest(source=name):
                report = self.report(tree, detect=False, start=True)
                self.assertTrue(report["project_inspection"]["start_commands"])
                self.assertNotIn(SECRET, self.dumped(report))
                self.assertTrue(
                    any("<redacted>" in item["command"] for item in report["project_inspection"]["start_commands"])
                )

    def test_secrets_in_scripts_that_are_not_start_candidates_never_appear(self):
        manifest = fixtures.package_json(
            dependencies={"express": "^5"},
            scripts={
                "start": "node server.js",
                "deploy": f"curl -H 'Authorization: Bearer {SECRET}A' https://deploy.example",
                "seed": f"node seed.js --password {SECRET}B",
            },
            config={"token": f"{SECRET}C"},
        )
        report = self.report({"package.json": manifest}, start=True)
        self.assertNotIn(SECRET, self.dumped(report))
        self.assertEqual(report["project_inspection"]["classification"], "backend-only")

    def test_scaffold_context_is_redacted(self):
        report = self.report(
            {"app.py": f"password = '{SECRET}A'  # TODO rotate\nurl = 'https://u:{SECRET}B@h/db'  # FIXME\n"},
            detect=False,
            scaffold=True,
        )
        self.assertEqual(len(report["project_inspection"]["scaffold_markers"]), 2)
        self.assertNotIn(SECRET, self.dumped(report))

    def test_diagnostics_that_quote_a_path_are_redacted(self):
        name = f"api_key={SECRET}.txt"
        report = self.report({name: b"caf\xe9"}, detect=False, scaffold=True)
        inspection = report["project_inspection"]
        self.assertFalse(inspection["ok"])
        self.assertTrue(inspection["errors"])
        self.assertNotIn(SECRET, self.dumped(report))

    def test_warnings_that_quote_a_path_are_redacted(self):
        root = self.project({**fixtures.VITE_TREE, f"token={SECRET}/x.txt": ""})
        real_scandir = os.scandir

        def scandir(path):
            if Path(path).name.startswith("token="):
                raise PermissionError(13, "Permission denied")
            return real_scandir(path)

        with mock.patch.object(os, "scandir", scandir):
            report = self.check_root(root)
        self.assertEqual(len(report["project_inspection"]["warnings"]), 1)
        self.assertIn("token=<redacted>", report["project_inspection"]["warnings"][0])
        self.assertNotIn(SECRET, self.dumped(report))

    def test_the_report_is_redacted_again_on_the_way_out(self):
        manifest = {
            "schema_version": 1,
            "runtime": {
                "python": {
                    "minimum": "3.9",
                    "optional_dependencies": [{"name": "PyYAML", "version": f"token={SECRET}A", "fallback": "x"}],
                }
            },
            "launchers": {"ci": f"python3 --token={SECRET}B", "password": f"{SECRET}C"},
        }
        with fixtures.tempfile.TemporaryDirectory() as holder:
            report = check_runtime.check(fixtures.make_catalog(Path(holder), manifest=manifest))
        self.assertTrue(report["ok"])
        self.assertEqual(report["launchers"]["ci"], "python3 --token=<redacted>")
        self.assertEqual(report["launchers"]["password"], "<redacted>")
        self.assertEqual(report["optional_dependencies"][0]["version"], "token=<redacted>")
        self.assertNotIn(SECRET, self.dumped(report))

    def test_the_manifest_error_report_is_redacted_too(self):
        manifest = {
            "schema_version": 1,
            "runtime": {
                "python": {
                    "minimum": "3.13.1",
                    "optional_dependencies": [{"name": "PyYAML", "version": f"token={SECRET}A", "fallback": "x"}],
                }
            },
            "launchers": {"ci": f"python3 --token={SECRET}B"},
        }
        with fixtures.tempfile.TemporaryDirectory() as holder:
            report = check_runtime.check(fixtures.make_catalog(Path(holder), manifest=manifest))
        self.assertFalse(report["ok"])
        self.assertEqual(report["launchers"]["ci"], "python3 --token=<redacted>")
        self.assertNotIn(SECRET, self.dumped(report))


SENSITIVE_TREE = {
    ".env": f"TOKEN={SECRET}env\n",
    ".env.local": f"TOKEN={SECRET}local\n",
    ".env.production": f"TOKEN={SECRET}production\n",
    ".env.development": f"TOKEN={SECRET}development\n",
    "config/.env": f"TOKEN={SECRET}nested\n",
    ".npmrc": f"//registry.npmjs.org/:_authToken={SECRET}npm\n",
    ".pypirc": f"password: {SECRET}pypi\n",
    "credentials.json": json.dumps({"aws_secret_access_key": f"{SECRET}credentials"}),
    "secrets.json": json.dumps({"apiKey": f"{SECRET}secrets"}),
    "service-account.json": json.dumps({"private_key": f"{SECRET}account"}),
    "id_rsa": f"-----BEGIN OPENSSH PRIVATE KEY-----\n{SECRET}rsa\n-----END OPENSSH PRIVATE KEY-----\n",
    "id_ed25519": f"-----BEGIN OPENSSH PRIVATE KEY-----\n{SECRET}ed\n-----END OPENSSH PRIVATE KEY-----\n",
    "certs/server.pem": f"-----BEGIN CERTIFICATE-----\n{SECRET}pem\n-----END CERTIFICATE-----\n",
    "certs/server.key": f"-----BEGIN PRIVATE KEY-----\n{SECRET}key\n-----END PRIVATE KEY-----\n",
    "certs/server.crt": f"-----BEGIN CERTIFICATE-----\n{SECRET}crt\n",
    "certs/server.cer": f"Bearer {SECRET}cer\n",
    "certs/server.der": b"\x30\x82" + SECRET.encode() + b"der",
    "certs/server.p12": b"\x30\x82" + SECRET.encode() + b"p12",
    "certs/server.pfx": b"\x30\x82" + SECRET.encode() + b"pfx",
    ".ssh/config": f"Host x\n  IdentityFile {SECRET}ssh\n",
    ".aws/credentials": f"aws_secret_access_key={SECRET}aws\n",
    ".azure/profile.json": json.dumps({"accessToken": f"{SECRET}azure"}),
    ".gnupg/pubring.txt": f"{SECRET}gnupg\n",
    "src/deploy.sh": f"# TODO wire the release\ncurl -H 'Authorization: Bearer {SECRET}deploy' https://x\n",
}
SENSITIVE_UPPERCASE_TREE = {
    ".ENV": f"TOKEN={SECRET}upperenv\n",
    "ID_RSA": f"{SECRET}upperrsa\n",
    "CERTS/SERVER.PEM": f"{SECRET}upperpem\n",
    ".SSH/CONFIG": f"{SECRET}upperssh\n",
    ".AWS/Credentials": f"{SECRET}upperaws\n",
}


class SensitiveFileTests(fixtures.FixtureTreeCase):
    def everything(self, tree) -> dict:
        tree = {**tree, "package.json": fixtures.package_json(dev={"vite": "^7"}, scripts={"dev": "vite"})}
        return self.report(tree, detect=True, start=True, scaffold=True)

    def test_sensitive_files_and_directories_never_reach_any_report_mode(self):
        for label, tree in (("lower case", SENSITIVE_TREE), ("upper case", SENSITIVE_UPPERCASE_TREE)):
            with self.subTest(names=label):
                report = self.everything(tree)
                self.assertNotIn(SECRET, json.dumps(report, sort_keys=True))
                inspection = report["project_inspection"]
                self.assertEqual(inspection["errors"], [])
                listed = {item["path"].lower() for item in inspection["manifests"] + inspection["configs"]}
                self.assertEqual(listed, {"package.json"})

    def test_only_the_non_sensitive_file_is_scanned_and_its_context_is_redacted(self):
        report = self.everything(SENSITIVE_TREE)
        markers = report["project_inspection"]["scaffold_markers"]
        self.assertEqual({row["file"] for row in markers}, {"src/deploy.sh"})
        self.assertEqual([row["marker"] for row in markers], ["TODO"])

    def test_sensitive_names_are_not_read_even_when_a_detector_would_want_them(self):
        """A deno.json or main.py that is sensitive by location gives the detector nothing."""
        report = self.report(
            {".ssh/deno.json": "{}", ".aws/main.py": "import fastapi\n", ".gnupg/package.json": fixtures.package_json(dev={"vite": "^7"})}
        )
        self.assertEqual(report["project_inspection"]["stacks"], [])


if __name__ == "__main__":
    unittest.main()
