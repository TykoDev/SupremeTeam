"""Secret handling tests for skills/scripts/check_runtime.py.

Two things keep a secret out of the report. Files that are sensitive by name or
location are never read or listed, and every string that does flow from a project
into the report (a start command, a diagnostic or a warning that quotes a path)
goes through the redactor, which works from context (a secret-named key, a flag, an
auth scheme, credentials in a URL) and from shape (a private key block, a provider's
key prefix, a JWT). The tests cover both, end to end through ``check()``, and pin the
redactor's forms directly.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _runtime_fixtures as fixtures
import check_runtime
from redaction import redact, redact_value

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
                redacted = redact(text)
                self.assertNotIn(SECRET, redacted)
                self.assertEqual(redacted, expected)

    def test_a_credential_is_redacted_by_its_shape_with_no_key_name_beside_it(self):
        """ST-AUD-012: only context was read, so a provider key, a JWT or a private key in free text passed whole.
        Each shape is built from pieces here so the repository holds nothing shaped like a credential."""
        body = "a1" * 18
        shapes = {
            "aws access key id": "AK" + "IA" + "Q" * 16,
            "github token": "gh" + "p_" + body,
            "github fine-grained token": "github" + "_pat_" + body,
            "gitlab token": "gl" + "pat-" + body,
            "openai key": "sk" + "-proj-" + body,
            "anthropic key": "sk" + "-ant-api03-" + body,
            "stripe key": "sk" + "_live_" + body,
            "slack token": "xo" + "xb-" + "1234567890-" + body,
            "google api key": "AI" + "za" + "B" * 35,
            "npm token": "np" + "m_" + "c" * 36,
            "jwt": ".".join(("ey" + "J" + "h" * 12, "ey" + "J" + "p" * 12, "s" * 12)),
        }
        for name, token in shapes.items():
            with self.subTest(name):
                text = redact(f"docker login -p {token} registry.example")
                self.assertNotIn(token, text)
                self.assertEqual(text, "docker login -p <redacted> registry.example")
                self.assertNotIn(token, json.dumps(redact_value({"note": f"used {token}", "argv": ["-p", token]})))
        block = "-----BEGIN " + "RSA PRIVATE KEY-----\n" + body + "\n-----END " + "RSA PRIVATE KEY-----"
        self.assertEqual(redact(f"key follows {block} done"), "key follows <redacted> done")
        self.assertEqual(redact("truncated -----BEGIN " + "PRIVATE KEY-----\n" + body), "truncated <redacted>")

    def test_a_digest_a_uuid_or_a_slug_is_not_taken_for_a_credential(self):
        for text in ("sha256 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                     "run 123e4567-e89b-12d3-a456-426614174000", "sk-telemetry-dashboard-config-panel",
                     "task-runner-0123456789-abcdefghij", "ghp_short", "eyJ alone", "-----BEGIN CERTIFICATE-----"):
            with self.subTest(text=text):
                self.assertEqual(redact(text), text)

    def test_json_documents_are_redacted_structurally(self):
        self.assertEqual(
            redact(f'{{"token": "{SECRET}", "name": "x"}}'), '{"name": "x", "token": "<redacted>"}'
        )
        self.assertEqual(
            redact(f'["--token", "{SECRET}", "--name", "x"]'), '["--token", "<redacted>", "--name", "x"]'
        )
        self.assertEqual(redact(f"{{not json token={SECRET}}}"), "{not json token=<redacted>}")

    def test_prose_that_only_names_a_credential_is_left_readable(self):
        for text in (
            "authentication is required",
            "Bearer token is required",
            "token must be a string",
            "Authorization header is missing",
            "the token field is required",
        ):
            with self.subTest(text=text):
                self.assertEqual(redact(text), text)

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
        redacted = redact_value(value)
        self.assertNotIn(SECRET, json.dumps(redacted))
        self.assertEqual(redacted["name"], "kept")
        self.assertEqual(redacted["nested"]["argv"], ["--token", "<redacted>", "--name", "kept"])
        self.assertEqual(redacted["headers"], ["Bearer", "<redacted>", "Basic", "<redacted>"])
        self.assertEqual((redacted["count"], redacted["enabled"], redacted["nothing"]), (3, True, None))

    def test_non_finite_numbers_and_runaway_nesting_are_neutralised(self):
        redacted = redact_value({"a": float("nan"), "b": float("inf"), "c": 1.5})
        self.assertEqual(redacted, {"a": "<non-finite>", "b": "<non-finite>", "c": 1.5})
        deep: dict = {}
        current = deep
        for _ in range(REDACTION_DEPTH_LIMIT + 50):
            current["x"] = {}
            current = current["x"]
        result = redact_value(deep)
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

    def test_diagnostics_that_quote_a_path_are_redacted(self):
        report = self.report({f"api_key={SECRET}/package.json": b"caf\xe9"})
        inspection = report["project_inspection"]
        self.assertFalse(inspection["ok"])
        self.assertTrue(any("cannot read text" in error for error in inspection["errors"]), inspection["errors"])
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
        with tempfile.TemporaryDirectory() as holder:
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
        with tempfile.TemporaryDirectory() as holder:
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
        return self.report(tree, detect=True, start=True)

    def test_sensitive_files_and_directories_never_reach_any_report_mode(self):
        for label, tree in (("lower case", SENSITIVE_TREE), ("upper case", SENSITIVE_UPPERCASE_TREE)):
            with self.subTest(names=label):
                report = self.everything(tree)
                self.assertNotIn(SECRET, json.dumps(report, sort_keys=True))
                inspection = report["project_inspection"]
                self.assertEqual(inspection["errors"], [])
                listed = {item["path"].lower() for item in inspection["manifests"] + inspection["configs"]}
                self.assertEqual(listed, {"package.json"})

    def test_sensitive_names_are_not_read_even_when_a_detector_would_want_them(self):
        """A deno.json or main.py that is sensitive by location gives the detector nothing."""
        report = self.report(
            {".ssh/deno.json": "{}", ".aws/main.py": "import fastapi\n", ".gnupg/package.json": fixtures.package_json(dev={"vite": "^7"})}
        )
        self.assertEqual(report["project_inspection"]["stacks"], [])


if __name__ == "__main__":
    unittest.main()
