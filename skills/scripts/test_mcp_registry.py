"""Freshness regressions; fixed clocks are not performance measurements."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from mcp_registry import inspect_registry


class RegistryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.path = self.root / "cache.md"
        self.now = datetime(2026, 10, 6, tzinfo=timezone.utc)

    def inspect(self):
        return inspect_registry(self.path, host="test-host", workspace=self.root, now=self.now)

    def cache(self, *, age=0, ttl=2, host="test-host", workspace=None):
        stamp = (self.now - timedelta(hours=age)).isoformat()
        self.path.write_text(f'---\nlast_discovery_at: {stamp}\ndiscovery_ttl_hours: {ttl}\nhost: "{host}"\nworkspace: "{workspace or self.root}"\n---\n', encoding="utf-8")

    def test_missing_and_shipped_blank_do_not_pause_intake(self):
        self.assertEqual(self.inspect()["status"], "undiscovered")
        template = Path(__file__).resolve().parents[1] / "mcp-tools.md"
        result = inspect_registry(template, host="test-host", workspace=self.root, now=self.now)
        self.assertEqual(result["status"], "undiscovered")
        self.assertFalse(result["intake_blocked"])
        self.assertFalse(result["live_availability_verified"])

    def test_configured_ttl_is_applied(self):
        for age, status in ((0, "use-cache"), (2, "use-cache"), (2.1, "stale"), (-1, "stale")):
            with self.subTest(age=age):
                self.cache(age=age)
                result = self.inspect()
                self.assertEqual(result["status"], status)
                self.assertEqual(result["refresh_required"], status != "use-cache")

    def test_identity_must_match(self):
        for kwargs in ({"host": "another-host"}, {"workspace": "/another-workspace"}):
            self.cache(**kwargs)
            self.assertEqual(self.inspect()["status"], "mismatch")

    def test_invalid_metadata_never_proves_freshness(self):
        for ttl in (0, -1, "true", "NaN", "infinity"):
            with self.subTest(ttl=ttl):
                self.cache(ttl=ttl)
                self.assertEqual(self.inspect()["status"], "invalid")
        self.path.write_text("not metadata", encoding="utf-8")
        self.assertEqual(self.inspect()["status"], "invalid")
