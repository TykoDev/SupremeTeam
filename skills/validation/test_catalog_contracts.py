#!/usr/bin/env python3
"""Comparators for the contracts the catalog states in prose.

`validate_manifests.py` checks YAML against YAML and `test_pipeline_contracts.py`
checks the pipeline specs against each other. Neither opens a SKILL.md, so every
rule expressed as prose — "the owning skill names the evidence it produces", "a
paraphrase of the execution contract is drift", "a skill never writes an artifact
its ownership entry forbids" — was unenforced and had silently drifted.

These tests close that gap. Each derives its expectation from the machine specs,
so the specs stay the single source of truth and the assertions cannot rot
independently of them.
"""

import re
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # PyYAML is optional; fall back to the bundled parser.
    yaml = None

SKILLS = Path(__file__).resolve().parents[1]

if yaml is None:  # pragma: no cover - exercised only on a host without PyYAML
    import sys
    sys.path.insert(0, str(SKILLS / "scripts"))
    from data_formats import parse_yaml as _parse

    def _load(path):
        return _parse(path.read_text(encoding="utf-8"))
else:
    def _load(path):
        return yaml.safe_load(path.read_text(encoding="utf-8"))


GATES = _load(SKILLS / "gates.yaml")
PIPELINES = _load(SKILLS / "pipelines.yaml")
OWNERSHIP = _load(SKILLS / "ownership.yaml")
TEAM = _load(SKILLS / "team-manifest.yaml")
CONTRACT = (SKILLS / "execution-contract.md").read_text(encoding="utf-8")

_FM = re.compile(r"^---\r?\n(.*?)\r?\n---", re.S)


def _skill_dirs():
    """Map skill name -> directory, from the frontmatter each SKILL.md declares."""
    found = {}
    for md in sorted(SKILLS.rglob("SKILL.md")):
        match = _FM.match(md.read_text(encoding="utf-8"))
        if not match:
            continue
        front = _load_text(match.group(1))
        if isinstance(front, dict) and front.get("name"):
            found[front["name"]] = md.parent
    return found


def _load_text(text):
    if yaml is None:  # pragma: no cover
        from data_formats import parse_yaml
        return parse_yaml(text)
    return yaml.safe_load(text)


SKILL_DIRS = _skill_dirs()


def _front(skill_md: Path) -> dict:
    """Parsed frontmatter of a SKILL.md, or an empty dict."""
    match = _FM.match(skill_md.read_text(encoding="utf-8"))
    if not match:
        return {}
    parsed = _load_text(match.group(1))
    return parsed if isinstance(parsed, dict) else {}



def _corpus(directory: Path) -> str:
    """Every document a skill owns, excluding any nested skill's subtree."""
    parts = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix not in {".md", ".yaml", ".yml"}:
            continue
        if "__pycache__" in path.parts:
            continue
        nested = False
        for parent in path.parents:
            if parent == directory:
                break
            if (parent / "SKILL.md").is_file():
                nested = True
                break
        if not nested:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


CORPUS = {name: _corpus(path) for name, path in SKILL_DIRS.items()}


def _names(text: str, token: str) -> bool:
    return re.search(r"\b" + re.escape(token) + r"\b", text) is not None


# The set the execution contract binds: every pipeline owner, the entry
# orchestrator, and every gatekeeper. Derived from team-manifest.yaml so the set
# tracks the roster instead of a hand-maintained list.
def _contract_bound() -> set:
    bound = set(TEAM.get("pipeline_owners") or [])
    bound.update(TEAM.get("phase_leads") or [])  # phase leads own a pipeline too
    bound.add(TEAM.get("front_door"))
    bound.add(TEAM.get("cross_stage_gatekeeper"))
    bound.update(TEAM.get("phase_gatekeepers") or [])
    return {name for name in bound if name}


def _clauses() -> list:
    """The six numbered clauses, verbatim, from the canonical section."""
    section = CONTRACT.split("## Canonical clauses", 1)[1].split("\n## ", 1)[0]
    clauses = re.findall(r"^\d\.\s+(.*?)(?=^\d\.\s|\Z)", section, re.S | re.M)
    return [" ".join(c.split()) for c in clauses]


class EvidenceOwnershipTests(unittest.TestCase):
    """Every evidence key is named by the skill that owes it.

    gates.yaml assigns each key an owner. If the owner's own documentation never
    names the key, the gate contract exists only in the spec and the skill has
    not been told what to produce.
    """

    def test_every_evidence_owner_names_the_key_it_owns(self):
        missing = []
        for boundary, owners in (GATES.get("evidence_owners") or {}).items():
            for key, owner in sorted(owners.items()):
                directory = SKILL_DIRS.get(owner)
                self.assertIsNotNone(directory, f"{boundary}.{key} owner '{owner}' is not a skill")
                if not _names(CORPUS[owner], key):
                    missing.append(f"{owner} never names '{key}' (required at {boundary})")
        self.assertEqual(missing, [], "evidence owners must document the keys they produce:\n  "
                                      + "\n  ".join(missing))

    def test_every_gate_submitter_names_its_boundary(self):
        missing = []
        for boundary, spec in GATES["boundaries"].items():
            submitter = spec.get("submitter")
            directory = SKILL_DIRS.get(submitter)
            if directory is None:
                continue
            if not _names(CORPUS[submitter], boundary):
                missing.append(f"{submitter} never names the boundary it submits at ({boundary})")
        self.assertEqual(missing, [], "\n  ".join(missing))


class StageDelegationTests(unittest.TestCase):
    """A pipeline owner names every specialist its own pipeline delegates to."""

    def test_pipeline_owner_names_each_stage_owner(self):
        missing = []
        for name, pipeline in PIPELINES["pipelines"].items():
            owner = pipeline.get("owner")
            if owner not in CORPUS:
                continue
            for stage in pipeline.get("stages", []):
                stage_owner = stage.get("owner")
                if not stage_owner or stage_owner == owner:
                    continue
                if not _names(CORPUS[owner], stage_owner):
                    missing.append(
                        f"{owner} ({name} pipeline) never names stage owner '{stage_owner}' "
                        f"for stage '{stage.get('step')}'")
        self.assertEqual(missing, [], "pipeline owners must name their delegates:\n  "
                                      + "\n  ".join(missing))


class ExecutionContractTests(unittest.TestCase):
    """execution-contract.md says a paraphrase in a skill is drift.

    That rule had no comparator, so only one of the bound skills carried the
    clauses at all. These tests are that comparator.
    """

    def test_canonical_section_parses_to_six_clauses(self):
        self.assertEqual(len(_clauses()), 6,
                         "execution-contract.md must state exactly six numbered clauses")

    def test_every_bound_skill_states_the_clauses_verbatim(self):
        clauses = _clauses()
        failures = []
        for name in sorted(_contract_bound()):
            directory = SKILL_DIRS.get(name)
            if directory is None:
                failures.append(f"{name} is bound by the execution contract but is not a skill")
                continue
            body = " ".join((directory / "SKILL.md").read_text(encoding="utf-8").split())
            for index, clause in enumerate(clauses, start=1):
                if clause not in body:
                    failures.append(f"{name} does not state clause {index} verbatim")
        self.assertEqual(failures, [],
                         "every orchestrator and gatekeeper carries the clauses locally:\n  "
                         + "\n  ".join(failures))


class OwnershipProseTests(unittest.TestCase):
    """A skill never instructs itself to write an artifact it may not write.

    ownership.yaml keeps authoritative records single-writer through
    `does_not_write`. Nothing compared that list against the prose, so three
    release skills were told to write exactly the artifact they are forbidden.
    """

    @staticmethod
    def _owner_entries():
        owners = OWNERSHIP.get("owners") or {}
        return owners if isinstance(owners, dict) else {}

    # Verbs that assert authorship of the artifact that follows them.
    WRITE_VERBS = (r"write|writes|produce|produces|emit|emits|author|authors|update|updates|"
                   r"shape|shapes|store|stores|narrow|narrows|record|records|return|returns|"
                   r"deliver|delivers|generate|generates|maintain|maintains")
    # A clause that disclaims THIS skill's authorship. Deliberately narrow: a bare
    # mention of consuming is not a disclaimer, because the original defect read
    # "Shape the release record so follow-up can consume it" — a write claim whose
    # sentence also mentions a downstream consumer. Only a negation, or an explicit
    # transfer of ownership, exonerates.
    DISCLAIMER = re.compile(
        r"\bnever\b|\bnot\b|\bdoes not\b|\bdo not\b|\bdoes_not_write\b|"
        r"\bconsumed here\b|\bis consumed\b|\bconsumes\b|\bdefer(?:s|red)?\b|"
        r"\brather than\b|\binstead of\b|\bbelongs to\b|\bowned by\b", re.I)

    # Words that may sit between the verb and its object without breaking the
    # claim ("Return **a new** release record"). Anything else means the two are
    # in unrelated clauses and the match is spurious.
    FILLER = r"(?:a|an|the|its|this|that|each|one|new|final|updated|verified|complete|full)"

    @classmethod
    def _artifact_pattern(cls, artifact: str) -> str:
        """Match an artifact id and the prose form of the same id.

        Ids are kebab-case (`deploy-config`) but prose says "deployment
        configuration", so each stem may carry a suffix. Single-stem ids are
        excluded by the caller: `plan`, `tests`, `findings` and `architecture`
        are ordinary English, and matching them produces false positives on
        sentences like "passes its own tests".
        """
        stems = [s for s in artifact.split("-") if s]
        return r"[\s-]+".join(re.escape(s) + r"\w*" for s in stems)

    @classmethod
    def _claim_pattern(cls, artifact: str) -> re.Pattern:
        """A write claim is the artifact as the DIRECT OBJECT of a write verb.

        Adjacency is the whole point: a wide window matches across clause
        boundaries ("Return `REVISE` ... before the design package advances"),
        which is not an authorship claim.
        """
        return re.compile(
            r"\b(?:" + cls.WRITE_VERBS + r")\b\s+(?:" + cls.FILLER + r"\s+){0,3}"
            + cls._artifact_pattern(artifact), re.I)

    def test_no_skill_claims_to_write_a_forbidden_artifact(self):
        violations = []
        for name, entry in self._owner_entries().items():
            if not isinstance(entry, dict) or name not in SKILL_DIRS:
                continue
            forbidden = [a for a in (entry.get("does_not_write") or []) if isinstance(a, str)]
            body = (SKILL_DIRS[name] / "SKILL.md").read_text(encoding="utf-8")
            for artifact in forbidden:
                if "-" not in artifact:
                    continue  # single-stem ids are ordinary English; see _artifact_pattern
                for match in self._claim_pattern(artifact).finditer(body):
                    start = body.rfind("\n", 0, match.start()) + 1
                    end = body.find("\n", match.end())
                    sentence = body[start:end if end != -1 else len(body)]
                    if self.DISCLAIMER.search(sentence):
                        continue
                    violations.append(
                        f"{name} may not write '{artifact}' but SKILL.md says: "
                        f"...{match.group(0).strip()}...")
        self.assertEqual(violations, [],
                         "prose must not contradict ownership.yaml does_not_write:\n  "
                         + "\n  ".join(violations))

    def test_the_detector_catches_the_defects_it_was_written_for(self):
        """Guard against a detector that silently matches nothing.

        Each string is a real sentence this audit found contradicting
        ownership.yaml. If the pattern stops catching them the test above
        becomes decorative, which is the failure mode it exists to prevent.
        """
        for artifact, sentence in [
            ("release-record", "Shape the release record so follow-up can consume it."),
            ("release-record", "Return a release record with next launch actions."),
            ("release-record", "Narrow the release record to the actual deployment state."),
            ("deploy-config", "Store verified deployment configuration in a durable location."),
        ]:
            with self.subTest(artifact=artifact, kind="true positive"):
                self.assertTrue(self._claim_pattern(artifact).search(sentence),
                                f"detector missed a known violation: {sentence}")
                self.assertFalse(self.DISCLAIMER.search(sentence))

    def test_the_detector_does_not_fire_on_these_known_false_positives(self):
        """Sentences that name an artifact without claiming to author it.

        Every one of these was flagged by an earlier, looser version of the
        pattern. They are the reason adjacency and multi-stem ids are required.
        """
        for artifact, sentence in [
            ("design-package", "Return `REVISE` and require the handoff section before the design package advances."),
            ("design-inventory", "The gate returns `redesign/artifacts/inventory/design-inventory.json` to its owner."),
            ("release-record", "`release-record` is listed under does_not_write; it is consumed here, never authored here."),
        ]:
            with self.subTest(artifact=artifact, kind="false positive"):
                match = self._claim_pattern(artifact).search(sentence)
                flagged = bool(match) and not self.DISCLAIMER.search(sentence)
                self.assertFalse(flagged, f"detector over-matched: {sentence}")

    def test_detector_accepts_a_correct_disclaimer(self):
        """A skill that names a forbidden artifact to disclaim it must pass."""
        ok = "`release-record` is listed under does_not_write; it is consumed here, never authored here."
        self.assertTrue(self.DISCLAIMER.search(ok))


class SaveContextParityTests(unittest.TestCase):
    """Every copy of the Save Context block carries the same field set.

    `contracts/handoff-templates.md` and `save-protocol.md` both declare that
    neither may drop a field the other carries, and eight more files embed the
    same block — ten recognized copies in all, counting the canonical one.
    Nothing compared them, so adding `Preamble tier` to the canonical copy would
    have left the other nine stale.
    """

    CANONICAL = SKILLS / "contracts" / "handoff-templates.md"

    @classmethod
    def _copies(cls):
        """Discover every Save Context copy instead of listing them.

        A hardcoded list is the same rot this suite exists to prevent: the first
        version of this test missed `admiral/stub-contract.md`, a normative field
        table that dropped a field on the line after asserting none may be
        dropped. Scanning finds copies added later, in prose or in a table.
        """
        for path in sorted(SKILLS.rglob("*.md")):
            if path == cls.CANONICAL or "__pycache__" in path.parts:
                continue
            if "Save Context" in path.read_text(encoding="utf-8", errors="replace"):
                yield path

    @staticmethod
    def _fields(path: Path) -> set:
        """Field names from a Save Context block, in list or table form.

        A file may mention "Save Context" in prose before carrying the block, so
        every occurrence is tried and the richest field set wins.
        """
        text = path.read_text(encoding="utf-8")
        best = set()
        for match in re.finditer(r"Save Context", text):
            block = text[match.end():match.end() + 3000]
            fields = set(re.findall(r"^-\s*([A-Z][A-Za-z ]+?):", block, re.M))
            fields |= {m.strip(" `") for m in
                       re.findall(r"^\|\s*`?([A-Z][A-Za-z ]+?)`?\s*\|", block, re.M)}
            fields -= {"Field", "Name", "Purpose", "Value"}
            if len(fields) > len(best):
                best = fields
        return best

    def test_canonical_block_is_parseable(self):
        fields = self._fields(self.CANONICAL)
        self.assertIn("Run ID", fields)
        self.assertIn("Preamble tier", fields,
                      "clause 1 of the execution contract needs this field to be recordable")

    def test_every_copy_carries_the_canonical_field_set(self):
        canonical = self._fields(self.CANONICAL)
        drift, checked = [], 0
        for path in self._copies():
            fields = self._fields(path)
            # A real copy carries the block's anchor field. A file that merely
            # mentions "Save Context" in prose does not, and must not be scored
            # as though it dropped all seventeen.
            if "Run ID" not in fields:
                continue
            checked += 1
            for missing in sorted(canonical - fields):
                drift.append(f"{path.relative_to(SKILLS).as_posix()} drops '{missing}'")
        self.assertGreater(checked, 5, "the scan found almost no copies — check the parser")
        self.assertEqual(drift, [],
                         "Save Context copies must not drop a canonical field:\n  "
                         + "\n  ".join(drift))


class ToolSurfaceTests(unittest.TestCase):
    """`allowed-tools` must encode the posture the skill's own text declares.

    A skill whose contract says it never modifies what it examines, or that it
    mutates durable state only through a sanctioned writer, should not be handed
    an edit tool. Declaring the field and then granting everything would make it
    decoration; this keeps it an invariant.
    """

    @staticmethod
    def _must_not_edit() -> set:
        """Skills that may not hold an edit tool, derived from the manifests.

        Inferring this from prose does not work: these documents describe each
        other constantly, so "report-only run" and "implements nothing here"
        match skills that are quoting a sibling's contract rather than declaring
        their own. Two spec facts are unambiguous instead — a gatekeeper never
        modifies the submission it judges, and a declared single-writer mutates
        its path class only through its own tool.
        """
        no_edit = set(TEAM.get("phase_gatekeepers") or [])
        cross = TEAM.get("cross_stage_gatekeeper")
        if cross:
            no_edit.add(cross)
        save_ownership = _load(SKILLS / "save-ownership.yaml")
        for entry in save_ownership.get("classes", []):
            writer, tool = entry.get("writer"), entry.get("tool")
            if tool and writer in SKILL_DIRS:
                no_edit.add(writer)
        return no_edit

    def test_every_skill_declares_a_tool_surface(self):
        missing = [name for name, d in SKILL_DIRS.items()
                   if "allowed-tools" not in (_front(d / "SKILL.md") or {})]
        self.assertEqual(missing, [], "every skill declares allowed-tools: " + ", ".join(missing))

    def test_tools_are_drawn_from_the_documented_vocabulary(self):
        known = {"Read", "Write", "Edit", "Bash", "Glob", "Grep", "TodoWrite"}
        bad = []
        for name, d in SKILL_DIRS.items():
            front = _front(d / "SKILL.md") or {}
            for tool in str(front.get("allowed-tools", "")).split(","):
                tool = tool.strip()
                if tool and tool not in known:
                    bad.append(f"{name}: unknown tool '{tool}'")
        self.assertEqual(bad, [], "\n  ".join(bad))

    def test_gatekeepers_and_single_writers_do_not_grant_edit(self):
        expected = self._must_not_edit()
        self.assertGreaterEqual(len(expected), 5,
                                "the manifests should name at least the gatekeepers here")
        violations = []
        for name in sorted(expected):
            front = _front(SKILL_DIRS[name] / "SKILL.md") or {}
            tools = {t.strip() for t in str(front.get("allowed-tools", "")).split(",")}
            if "Edit" in tools:
                violations.append(
                    f"{name} is a gatekeeper or declared single-writer but grants Edit")
        self.assertEqual(violations, [],
                         "tool surface must match the contract the manifests declare:\n  "
                         + "\n  ".join(violations))



class PerDocumentConsistencyTests(unittest.TestCase):
    """A supporting document must not contradict the spec its SKILL.md follows.

    The other comparators in this file are corpus-level — they accept a fact
    stated anywhere in the skill's tree. That let two documents drift while the
    tests stayed green: a stub-contract omitting a mandatory stage, and two
    stating a revision cap the gate spec does not allow.
    """

    def _supporting_docs(self, directory: Path):
        """Every .md the skill owns except SKILL.md, excluding nested skills."""
        for path in sorted(directory.rglob("*.md")):
            if path.name == "SKILL.md" or "__pycache__" in path.parts:
                continue
            nested = any((p / "SKILL.md").is_file()
                         for p in path.parents if p != directory and p.is_relative_to(directory))
            if not nested:
                yield path

    def test_no_document_states_a_revision_cap_the_gate_spec_forbids(self):
        cap = (GATES.get("revise_policy") or {}).get("cycle_cap")
        self.assertIsInstance(cap, int, "gates.yaml must declare revise_policy.cycle_cap")
        pattern = re.compile(r"[Mm]aximum revisions? per (?:phase|stage|boundary)[^\n]*?(\d+)")
        violations = []
        for name, directory in SKILL_DIRS.items():
            for path in [directory / "SKILL.md", *self._supporting_docs(directory)]:
                for match in pattern.finditer(path.read_text(encoding="utf-8", errors="replace")):
                    if int(match.group(1)) != cap:
                        violations.append(
                            f"{path.relative_to(SKILLS).as_posix()} states a cap of "
                            f"{match.group(1)}; gates.yaml revise_policy.cycle_cap is {cap}")
        self.assertEqual(violations, [],
                         "revision caps must match the gate spec:\n  " + "\n  ".join(violations))

    def test_a_stated_phase_order_includes_every_unconditional_stage(self):
        """A document that enumerates the mandatory order may not drop a stage.

        Only unconditional stages are required: a stage carrying a `when:` runs
        sometimes, so omitting it from a mandatory-order list is legitimate.
        """
        violations = []
        for pipeline_name, pipeline in PIPELINES["pipelines"].items():
            owner = pipeline.get("owner")
            directory = SKILL_DIRS.get(owner)
            if directory is None:
                continue
            # A phase's own order covers its specialists. The front door that
            # precedes the phase and the gatekeeper that closes it sit outside
            # it, so their absence from such a list is not a contradiction.
            outside = {TEAM.get("front_door")} | set(TEAM.get("phase_gatekeepers") or [])
            outside.add(TEAM.get("cross_stage_gatekeeper"))
            required = [s["owner"] for s in pipeline.get("stages", [])
                        if s.get("owner") and s["owner"] != owner
                        and s["owner"] not in outside and not s.get("when")]
            if not required:
                continue
            for path in self._supporting_docs(directory):
                text = path.read_text(encoding="utf-8", errors="replace")
                match = re.search(r"^#+\s*(?:Mandatory )?(?:Phase|Stage) Order\s*$(.*?)(?=^#|\Z)",
                                  text, re.S | re.M)
                if not match:
                    continue
                block = match.group(1)
                # Stage owners are slugs; a phase list names them capitalized
                # ("Researcher"), so match without regard to case.
                missing = [o for o in required
                           if not re.search(r"\b" + re.escape(o) + r"\b", block, re.I)]
                if missing:
                    violations.append(
                        f"{path.relative_to(SKILLS).as_posix()} states a mandatory order for the "
                        f"{pipeline_name} pipeline but omits: {', '.join(missing)}")
        self.assertEqual(violations, [],
                         "a mandatory order must name every unconditional stage:\n  "
                         + "\n  ".join(violations))

    def test_evidence_keys_are_reachable_from_skill_md(self):
        """An owner names its keys in SKILL.md, or in a reference SKILL.md links.

        Corpus-level matching accepted a key mentioned in any file, including one
        nothing points at. Progressive disclosure legitimately moves a gate table
        into `references/`, so a linked reference counts — an unlinked one does not.
        """
        link = re.compile(r"\[[^\]]*\]\(([^)#]+)\)|`((?:\./)?references/[\w./-]+\.md)`")
        violations = []
        for boundary, owners in (GATES.get("evidence_owners") or {}).items():
            for key, owner in sorted(owners.items()):
                directory = SKILL_DIRS.get(owner)
                if directory is None:
                    continue
                skill_md = (directory / "SKILL.md").read_text(encoding="utf-8")
                reachable = skill_md
                for match in link.finditer(skill_md):
                    target = (match.group(1) or match.group(2) or "").split("#")[0].strip()
                    if not target or target.startswith(("http", "mailto")):
                        continue
                    resolved = (directory / target).resolve()
                    if resolved.is_file() and resolved.suffix == ".md":
                        reachable += resolved.read_text(encoding="utf-8", errors="replace")
                if not _names(reachable, key):
                    violations.append(
                        f"{owner} states '{key}' ({boundary}) only in a file SKILL.md does not link")
        self.assertEqual(violations, [],
                         "a gate key must be reachable from SKILL.md:\n  " + "\n  ".join(violations))


class DeclaredCoverageTests(unittest.TestCase):
    """Two mirrors that nothing compared, each of which had already drifted.

    `save-ownership.yaml` states "one writer per path class", but four kinds the
    resolver offers had no class at all. `responsibility-matrix.md` mirrors the
    team manifest by hand. Both were corrected in this pass; these keep them so.
    """

    @staticmethod
    def _resolver_kinds() -> set:
        """Project kinds `output_paths.py` will resolve, read from its own parser."""
        source = (SKILLS / "scripts" / "output_paths.py").read_text(encoding="utf-8")
        match = re.search(r"--kind[\"'].*?choices=\(([^)]*)\)", source, re.S)
        if not match:
            match = re.search(r"KINDS\s*=\s*\{([^}]*)\}", source, re.S)
        self_kinds = set(re.findall(r"[\"']([a-z_]+)[\"']", match.group(1))) if match else set()
        return self_kinds

    def test_every_resolver_kind_has_a_declared_writer(self):
        """A sanctioned destination with no declared class is a policy gap.

        Global and per-user destinations live outside the project-relative glob
        policy by design, so they are exempt; everything else must be covered.
        """
        save_ownership = _load(SKILLS / "save-ownership.yaml")
        classes = save_ownership.get("classes") or []
        self.assertTrue(classes, "save-ownership.yaml declares no classes")
        # Match against class ids as well as patterns: `guards` is covered by the
        # class `harness-guards`, `trajectory` by `.harness-state/trajectories/`.
        haystack = " ".join(
            [str(c.get("id", "")) for c in classes]
            + [str(p) for c in classes for p in (c.get("patterns") or [])]).lower()

        exempt = {"global_preferences", "product", "core"}
        kinds = self._resolver_kinds()
        self.assertGreater(len(kinds), 8, "could not read the resolver's kind list")

        uncovered = []
        for kind in sorted(kinds - exempt):
            # Compare on the kind's significant token, de-pluralised, so
            # `standalone_packages` matches `standalone-packages` and
            # `trajectory` matches `trajectories`.
            token = kind.split("_")[-1][:7]  # prefix stem: trajectory ~ trajectories
            if token not in haystack:
                uncovered.append(f"{kind} (looked for '{token}')")
        self.assertEqual(uncovered, [],
                         "every resolver kind needs a declared writer class:\n  "
                         + "\n  ".join(uncovered))

    def test_responsibility_matrix_specialists_match_the_manifest(self):
        """The matrix mirrors team-manifest.yaml by hand; nothing compared them."""
        path = SKILLS / "contracts" / "responsibility-matrix.md"
        text = path.read_text(encoding="utf-8")
        section = text.split("## Specialists", 1)
        self.assertEqual(len(section), 2, "responsibility-matrix.md has no Specialists section")
        block = section[1].split("\n## ", 1)[0]

        declared = [s for s in (TEAM.get("specialists") or []) if isinstance(s, str)]
        self.assertTrue(declared, "team-manifest.yaml declares no specialists")
        missing = [s for s in declared if not re.search(r"\b" + re.escape(s) + r"\b", block)]
        self.assertEqual(missing, [],
                         "the Specialists section must name every manifest specialist:\n  "
                         + "\n  ".join(missing))

        stated = re.search(r"\b(twenty-one|\d+)\s+specialists\b", block, re.I)
        if stated:
            words = {"twenty-one": 21, "twenty": 20, "twenty-two": 22}
            value = words.get(stated.group(1).lower())
            if value is None and stated.group(1).isdigit():
                value = int(stated.group(1))
            if value is not None:
                self.assertEqual(
                    value, len(declared),
                    f"the matrix says {stated.group(1)} specialists; the manifest declares "
                    f"{len(declared)}")

    def test_release_layer_owner_matches_the_pipeline_and_the_gate(self):
        """The RELEASE row named the stage writer, not the pipeline owner."""
        text = (SKILLS / "contracts" / "responsibility-matrix.md").read_text(encoding="utf-8")
        row = next((line for line in text.splitlines()
                    if line.startswith("| RELEASE ")), None)
        self.assertIsNotNone(row, "responsibility-matrix.md has no RELEASE row")
        owner = PIPELINES["pipelines"]["release"]["owner"]
        submitter = GATES["boundaries"]["deploy-readiness"]["submitter"]
        self.assertEqual(owner, submitter,
                         "pipelines.yaml and gates.yaml disagree on who owns release")
        cells = [c.strip() for c in row.split("|")]
        self.assertIn(owner, cells,
                      f"the RELEASE row must name '{owner}' as the layer owner; row was: {row}")

class GuardWriterTests(unittest.TestCase):
    """The guard boundary record has a single writer, like every other durable class."""

    def test_guard_state_writer_is_declared_and_present(self):
        save_ownership = _load(SKILLS / "save-ownership.yaml")
        classes = {c.get("id"): c for c in save_ownership.get("classes", [])}
        guards = classes.get("harness-guards")
        self.assertIsNotNone(guards, "save-ownership.yaml must declare the harness-guards class")
        self.assertIn("guard_state.py", str(guards.get("tool", "")),
                      "harness-guards must name its sanctioned writer")
        self.assertTrue((SKILLS / "harness" / "hooks" / "guard_state.py").is_file())

    def test_pre_tool_hook_protects_the_guard_record(self):
        hook = (SKILLS / "harness" / "hooks" / "pre_tool_use.py").read_text(encoding="utf-8")
        self.assertIn("guard-state.json", hook)
        self.assertIn("guard_state.py", hook,
                      "the hook must route writes to the sanctioned writer")


if __name__ == "__main__":
    unittest.main()


class ClaimedEnforcementTests(unittest.TestCase):
    """Documents that describe their own enforcement must describe it correctly.

    Round two of the audit found the failure mode running in both directions. A
    document that claims a guarantee nothing checks misleads a reader into
    trusting a drifted row; a document that denies a guarantee it has is worse,
    because it invites someone to delete test-enforced content believing nothing
    will notice. Both are mechanical to catch, so neither should survive again.
    """

    #: "no test opens this file" and its variants, scoped to the file itself.
    #: The subject must be "this file" — a sentence denying that a script reads
    #: some *note* inside the document is a different, true claim.
    #: The object must be self-referential. An early version required the exact
    #: words "this file", and missed `routing-doctrine.md` denying a comparator
    #: for "the routing-class table below" — the same falsehood one notch below
    #: the regex, found by hand. A sweeping form ("almost nothing here is
    #: machine-checked") was tried too and rejected: it matched
    #: "nothing in the surface under review, and that is enforced", which asserts
    #: the opposite, and no tightening of it stayed both precise and general.
    DENIAL = re.compile(
        r"\bno (?:test|comparator|script)\b[^.\n]{0,80}"
        r"\b(?:this file|this document|this table|the table below|this section)\b", re.I)

    @staticmethod
    def _reading_context(sources):
        """Test source with comments removed, so only real reads count.

        A filename mentioned in a comment is not a comparator. The first version
        of this check matched any occurrence of the name anywhere in test source,
        and a one-line comment citing `design-doctrine.md` for its six-tier rule
        was enough to report the doctrine's own honest "no comparator opens this
        file" as a falsehood. A path is written as a quoted string; prose is not.
        """
        kept = []
        for path in sources:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                kept.append(line.split("#", 1)[0])
        return "\n".join(kept)

    def test_no_document_denies_a_comparator_that_exists(self):
        tests = sorted(SKILLS.rglob("test_*.py"))
        self.assertGreater(len(tests), 5, "no test files discovered - the check would pass vacuously")
        blob = self._reading_context(tests)

        false_denials = []
        for md in sorted(SKILLS.rglob("*.md")):
            if "__pycache__" in md.parts:
                continue
            text = md.read_text(encoding="utf-8", errors="replace")
            match = self.DENIAL.search(text)
            if match and f'"{md.name}"' in blob:
                line = text[: match.start()].count("\n") + 1
                false_denials.append(
                    f"{md.relative_to(SKILLS).as_posix()}:{line} denies a comparator "
                    f"({match.group(0).strip()!r}) but a test names this file"
                )
        self.assertEqual([], false_denials, "\n".join(false_denials))


class EvidenceVocabularyTests(unittest.TestCase):
    """Gate evidence keys and ownership artifact ids are two namespaces.

    Most names appear in both, spelled differently: the gate key
    `rendered_verification` is the artifact id `rendered-verification`. Prose
    that reaches for the wrong one sends a reader to a key `check.py` will not
    find, so the spelling is checked where the sentence says which namespace it
    is in.
    """

    @staticmethod
    def _gate_keys():
        spec = yaml.safe_load((SKILLS / "gates.yaml").read_text(encoding="utf-8"))
        return {k for b in spec["boundaries"].values() for k in b.get("required_evidence", [])}

    def test_evidence_owner_prose_uses_the_gate_key_spelling(self):
        hyphenated = {k.replace("_", "-"): k for k in self._gate_keys() if "_" in k}
        self.assertGreater(len(hyphenated), 10, "gates.yaml yielded almost no underscored keys")

        wrong = []
        for md in sorted(SKILLS.rglob("*.md")):
            if "__pycache__" in md.parts:
                continue
            for number, line in enumerate(md.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                # Only lines that declare which namespace they are in, and not
                # lines that also cite ownership.yaml, where the hyphen is right.
                if "evidence_owners" not in line or "ownership.yaml" in line:
                    continue
                for hyphen, key in hyphenated.items():
                    if f"`{hyphen}`" in line:
                        wrong.append(
                            f"{md.relative_to(SKILLS).as_posix()}:{number} writes `{hyphen}` "
                            f"in evidence_owners prose; the gate key is `{key}`"
                        )
        self.assertEqual([], wrong, "\n".join(wrong))

    def test_sanctioned_fallback_wording_is_never_taught_as_a_bare_string(self):
        """A file that quotes a sanctioned fallback must state the record form.

        At `schema_version: 2` `check.py` refuses a bare fallback string and
        requires `{applicable: false, reason, scope, decided_by}`. A document
        that prints the wording without ever naming that shape teaches a package
        the gate rejects.
        """
        spec = yaml.safe_load((SKILLS / "gates.yaml").read_text(encoding="utf-8"))
        values = {}
        for key, allowed in (spec.get("fallback_values") or {}).items():
            values[allowed[0]] = key
        for boundary in spec["boundaries"].values():
            for key, allowed in (boundary.get("fallback_values") or {}).items():
                values[allowed[0]] = key
        self.assertGreater(len(values), 8, "gates.yaml yielded almost no sanctioned fallbacks")

        record = re.compile(r"applicability record|applicable[\"']?\s*:\s*false", re.I)
        silent = []
        for md in sorted(SKILLS.rglob("*.md")):
            if "__pycache__" in md.parts:
                continue
            text = md.read_text(encoding="utf-8", errors="replace")
            # A sanctioned wording can be a generic phrase ("none observed")
            # that collides with ordinary prose, so a hit counts only when the
            # file also names the key whose fallback it is.
            quoted = sorted({
                key for wording, key in values.items()
                if wording in text and f"`{key}`" in text
            })
            if quoted and not record.search(text):
                silent.append(
                    f"{md.relative_to(SKILLS).as_posix()} quotes the sanctioned wording for "
                    f"{', '.join(quoted)} but never states the applicability-record form"
                )
        self.assertEqual([], silent, "\n".join(silent))


class FrontmatterBudgetTests(unittest.TestCase):
    """Frontmatter limits that have regressed silently more than once.

    The description is the whole trigger surface: it is what a model reads to
    decide whether a skill applies, and nothing downstream re-reads the body to
    correct a description that sprawled. Three skills exceeded the budget in the
    first audit pass, eleven after the first remediation, and one more crept back
    while an unrelated collision was being fixed. It is one line of arithmetic,
    so it should not need a reviewer.
    """

    #: Anthropic's published ceiling for the frontmatter description field.
    MAX_DESCRIPTION = 600

    @staticmethod
    def _frontmatter(text):
        if not text.startswith("---"):
            return None
        end = text.find("\n---", 3)
        if end == -1:
            return None
        try:
            return yaml.safe_load(text[3:end]) or {}
        except yaml.YAMLError:
            return None

    def test_every_skill_has_parseable_frontmatter(self):
        unparseable = []
        for skill in sorted(SKILLS.rglob("SKILL.md")):
            if self._frontmatter(skill.read_text(encoding="utf-8", errors="replace")) is None:
                unparseable.append(skill.relative_to(SKILLS).as_posix())
        self.assertEqual([], unparseable, "\n".join(unparseable))

    def test_no_description_exceeds_the_budget(self):
        over = []
        for skill in sorted(SKILLS.rglob("SKILL.md")):
            meta = self._frontmatter(skill.read_text(encoding="utf-8", errors="replace")) or {}
            size = len(str(meta.get("description", "")))
            if size > self.MAX_DESCRIPTION:
                over.append(
                    f"{skill.relative_to(SKILLS).as_posix()} description is {size} chars "
                    f"(budget {self.MAX_DESCRIPTION})"
                )
        self.assertEqual([], over, "\n".join(over))

    def test_every_skill_declares_allowed_tools(self):
        missing = []
        for skill in sorted(SKILLS.rglob("SKILL.md")):
            meta = self._frontmatter(skill.read_text(encoding="utf-8", errors="replace")) or {}
            if not meta.get("allowed-tools"):
                missing.append(skill.relative_to(SKILLS).as_posix())
        self.assertEqual([], missing, "\n".join(missing))


class LineEndingTests(unittest.TestCase):
    """The working tree is CRLF; three separate mechanisms have broken that.

    ``.gitattributes`` normalises to LF in the blob, so committed content is
    consistent either way — but a file that is mixed, doubled, or bare-LF in the
    working tree shows up as a whole-file diff and buries the real change. Three
    distinct causes have hit this catalog: Git Bash ``sed -i`` rewriting a file
    as LF, ``git stash push/pop`` doing the same to untouched siblings, and a
    script joining lines with ``\r\n`` and then writing in text mode, which
    translates each ``\n`` again and yields ``\r\r\n``. All three are one
    byte scan to catch.
    """

    SUFFIXES = {".md", ".py", ".yaml", ".yml", ".json"}

    def _files(self):
        for path in sorted(SKILLS.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in self.SUFFIXES:
                yield path

    def test_no_file_has_doubled_carriage_returns(self):
        doubled = []
        for path in self._files():
            count = path.read_bytes().count(b"\r\r\n")
            if count:
                doubled.append(
                    f"{path.relative_to(SKILLS).as_posix()} has {count} doubled line endings"
                )
        self.assertEqual([], doubled, "\n".join(doubled))

    def test_line_endings_are_uniform_within_each_file(self):
        mixed = []
        for path in self._files():
            data = path.read_bytes()
            crlf = data.count(b"\r\n")
            bare = data.count(b"\n") - crlf
            if crlf and bare:
                mixed.append(
                    f"{path.relative_to(SKILLS).as_posix()} mixes {crlf} CRLF with {bare} bare LF"
                )
        self.assertEqual([], mixed, "\n".join(mixed))
