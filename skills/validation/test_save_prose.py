#!/usr/bin/env python3
"""Prose that names the save writer's vocabulary is checked against the writer.

`admiral/references/contracts.md` ordered three audit-trail appends
(`SESSION_PIN_RELEASE`, `HOOK_REGISTRATION_CHECK`, `MCP_REGISTRY_CHECK`) that
`save_run.py` cannot emit, since it has no operation that appends a line by name,
and that `pre_tool_use.py` Rule C denies by hand: an agent that followed the
contract to the letter had to break write ownership. `session-memory/SKILL.md`
says it quotes the core-run-record class verbatim from the policy; when
`_write.lock` joined the class the quote was one pattern behind, and nothing
would have said so.

The scan covers the files this contract lives in. Other documents restate the
same appends and are named in the remediation hand-offs; widening `OWNED` to them
is the follow-up.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILLS / "scripts"))
from data_formats import load_data  # noqa: E402

# An upper-case event name ordered appended: "append `SESSION_PIN_RELEASE`", "appends the `X`".
ORDERED_APPEND = re.compile(r"\bappend(?:s|ed)?\s+(?:the\s+)?`([A-Z][A-Z_]{5,})`")
OWNED = ("admiral/SKILL.md", "admiral/references/contracts.md", "mcp-tools.md", "routing-doctrine.md", "save-protocol.md")


class ProseMatchesTheWriterTests(unittest.TestCase):
    def owned_files(self) -> list[Path]:
        files = [SKILLS / name for name in OWNED] + sorted((SKILLS / "session-memory").rglob("*.md"))
        saves = SKILLS.parent / "docs" / "persistent-saves.md"
        return files + ([saves] if saves.is_file() else [])

    def test_no_contract_orders_an_audit_line_the_writer_cannot_emit(self):
        offenders = []
        for path in self.owned_files():
            text = path.read_text(encoding="utf-8")
            for match in ORDERED_APPEND.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(SKILLS.parent).as_posix()}:{line} orders `{match.group(1)}` appended")
        self.assertEqual(offenders, [], "the trail's events are fixed by save_run.py; carry a fact as `--set key=value` on "
                                        "create or checkpoint instead:\n  " + "\n  ".join(offenders))

    def test_the_intake_facts_are_carried_as_state_fields_by_name(self):
        contracts = (SKILLS / "admiral" / "references" / "contracts.md").read_text(encoding="utf-8")
        for key in ("hook_registration_status", "mcp_registry_check", "runtime_readiness_check", "session_pin_release"):
            with self.subTest(key=key):
                self.assertIn(f"--set {key}=", contracts)

    def test_the_staleness_window_the_prose_states_is_the_constant(self):
        """The window was restated as the words "30 minutes" in five places, one constant in code."""
        import save_taxonomy

        window = f"{save_taxonomy.STALE_AFTER_SECONDS // 60} minutes"
        for path in self.owned_files():
            text = path.read_text(encoding="utf-8")
            if re.search(r"\bstale\b", text) and re.search(r"\b\d+ minutes\b", text):
                with self.subTest(path=path.name):
                    self.assertIn(window, text)

    def test_session_memory_quotes_the_core_run_record_class_verbatim(self):
        text = (SKILLS / "session-memory" / "SKILL.md").read_text(encoding="utf-8")
        block = re.search(r"quoted verbatim from the policy[^`]*```text\n(.*?)```", text, re.S)
        self.assertIsNotNone(block, "the quoted block moved or was reworded")
        quoted = sorted(line.strip() for line in block.group(1).splitlines() if line.strip())
        policy = load_data(SKILLS / "save-ownership.yaml")
        patterns = next(entry for entry in policy["classes"] if entry["id"] == "core-run-record")["patterns"]
        self.assertEqual(quoted, sorted(patterns))


if __name__ == "__main__":
    unittest.main()
