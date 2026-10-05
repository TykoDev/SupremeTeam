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
sys.path.insert(0, str(SKILLS / "harness" / "hooks"))
from data_formats import load_data  # noqa: E402

# An upper-case event name ordered appended: "append `SESSION_PIN_RELEASE`", "appends the `X`".
ORDERED_APPEND = re.compile(r"\bappend(?:s|ed)?\s+(?:the\s+)?`([A-Z][A-Z_]{5,})`")
# The same order without a name: "Append every release to the audit trail", "the release is appended".
RELEASE_APPEND = re.compile(r"\bappend(?:s|ed)?\s+(?:every|each)\s+release\b|\brelease\s+is\s+appended\b", re.I)
OWNED = ("admiral/SKILL.md", "admiral/references/contracts.md", "admiral/agent/agent-protocol.md", "mcp-tools.md",
         "routing-doctrine.md", "save-protocol.md")


class ProseMatchesTheWriterTests(unittest.TestCase):
    def owned_files(self) -> list[Path]:
        files = [SKILLS / name for name in OWNED] + sorted((SKILLS / "session-memory").rglob("*.md"))
        docs = [SKILLS.parent / "docs" / name for name in ("persistent-saves.md", "routing.md")]
        return files + [path for path in docs if path.is_file()]

    def test_no_contract_orders_an_audit_line_the_writer_cannot_emit(self):
        offenders = []
        for path in self.owned_files():
            text = path.read_text(encoding="utf-8")
            for match in ORDERED_APPEND.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(SKILLS.parent).as_posix()}:{line} orders `{match.group(1)}` appended")
            for match in RELEASE_APPEND.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(SKILLS.parent).as_posix()}:{line} orders a release appended to the trail")
        self.assertEqual(offenders, [], "the trail's events are fixed by save_run.py; carry a fact as `--set key=value` on "
                                        "create or checkpoint instead:\n  " + "\n  ".join(offenders))

    def test_the_intake_facts_are_carried_as_state_fields_by_name(self):
        contracts = (SKILLS / "admiral" / "references" / "contracts.md").read_text(encoding="utf-8")
        for key in ("hook_registration_status", "mcp_registry_check", "runtime_readiness_check", "session_pin_release"):
            with self.subTest(key=key):
                self.assertIn(f"--set {key}=", contracts)

    def test_every_document_that_lists_the_trail_or_the_statuses_lists_the_writers(self):
        """agent-protocol.md kept an eleven-event list after the writer learned `refused` and `degraded`, and its status
        vocabulary lacked `uninitialized`; both lists repeat what save-protocol.md and `NEXT_STEPS` state."""
        from _saves import NEXT_STEPS

        def events(path: Path) -> set[str]:
            text = path.read_text(encoding="utf-8")
            sentence = re.search(r"trail\s+(?:holds\s+\w+\s+events\s+and\s+no\s+others|can\s+only\s+ever\s+contain):(.*?)\.\s", text, re.S).group(1)
            return set(re.findall(r"`([a-z][a-z-]*)`", sentence.split(" with its ")[0]))

        protocol = events(SKILLS / "save-protocol.md")
        self.assertEqual(len(protocol), 13)
        self.assertEqual(events(SKILLS / "admiral" / "agent" / "agent-protocol.md"), protocol)
        agent = (SKILLS / "admiral" / "agent" / "agent-protocol.md").read_text(encoding="utf-8")
        listed = re.search(r"SAVE_STATUS_CHECK — status: \{([^}]*)\}", agent).group(1).split("|")
        self.assertEqual(set(listed), set(NEXT_STEPS))

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

    def test_every_documented_save_command_names_the_lock_holder_as_owner(self):
        """Twelve skills told their agent to checkpoint with `--owner <self>`. `save_run.py` refuses every owner but the
        lock holder, and admiral takes the lock at `create` and keeps it, so each of those commands failed with
        `lock is owned by 'admiral'` at the first checkpoint of every delegated phase. A delegate records itself with
        `--set delegated_to=`; `--owner` is always the lock holder, which is the writer's default."""
        writer = (SKILLS / "harness" / "hooks" / "save_run.py").read_text(encoding="utf-8")
        holder = re.search(r'add_argument\("--owner",\s*default="([a-z-]+)"\)', writer).group(1)
        command = re.compile(r"save_run\.py\s+(?:create|checkpoint|heartbeat|complete|block|release|recover)\b[^`\n]*")
        roots = [SKILLS, SKILLS.parent / "docs"]
        files = [path for root in roots if root.is_dir() for path in sorted(root.rglob("*.md"))]
        files += [path for path in (SKILLS.parent / name for name in ("README.md", "QUICK-START.md", "AGENTS.md")) if path.is_file()]
        offenders = []
        for path in files:
            text = path.read_text(encoding="utf-8").replace("\\\n", " ")
            for match in command.finditer(text):
                owner = re.search(r"--owner\s+([a-z][a-z-]*)\b", match.group(0))
                if owner and owner.group(1) != holder:
                    line = text.count("\n", 0, match.start()) + 1
                    offenders.append(f"{path.relative_to(SKILLS.parent).as_posix()}:{line} --owner {owner.group(1)}")
        self.assertGreater(len(files), 100)
        self.assertEqual(offenders, [], f"save_run.py refuses an owner that is not the lock holder ({holder!r}); record "
                                        "the delegate with `--set delegated_to=<skill>`:\n  " + "\n  ".join(offenders))


if __name__ == "__main__":
    unittest.main()
