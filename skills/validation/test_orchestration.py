#!/usr/bin/env python3
"""Comparators for the delegation layer that sits between the manifests.

`validate_manifests.py` checks YAML against YAML, `test_pipeline_contracts.py`
checks a pipeline's owners and artifacts against the roster, and
`test_catalog_contracts.py` checks prose against the specs one skill at a time.
None of them reads the *graph*: who hands work to whom, whether the receiver
agrees it may be handed work by that sender, and whether the vocabulary the
handoff travels in is the same at both ends. That layer was entirely unchecked,
so the failures below could all have shipped green.

Each class states the failure it prevents.

* `DelegationTargetTests` - a surface bullet naming a skill that does not exist.
  A renamed or deleted skill leaves a dangling delegate, and the run discovers
  it at the moment an orchestrator tries to hand off.
* `DelegationSymmetryTests` - a specialist whose surface does not name the owner
  that delegates to it. `test_catalog_contracts.py` checks the forward direction,
  that an owner names its stage owners; nothing checked the return direction, so
  a specialist reassigned to a second pipeline kept a surface listing only the
  first, and a reader of that skill could not tell who was allowed to call it.
* `SpecialistEntryRoutingTests` - a pipeline delegating to a specialist that
  does not list that pipeline's owner as a legitimate sender. The specialist's
  own loop guard then refuses the handoff and routes the user back to the front
  door, which reads as an infinite bounce rather than as the spec conflict it is.
* `DelegationGraphTests` - a delegation cycle. Two orchestrators that delegate
  to each other never terminate, and no gate closes because no package is ever
  assembled.
* `VerdictVocabularyTests` - a fourth gate verdict. Three tokens are the whole
  contract between a gatekeeper and a submitter; a skill that invents a fourth
  emits a verdict the receiving orchestrator has no branch for.
* `PipelineOwnerRoleTests` - a pipeline owned by a skill that holds no
  orchestrator role, or a `delegate` naming nothing. `pipelines.yaml` itself
  records the delegate field as unchecked, so a typo there fails at run time.
* `RevisionCapTests` - two documents stating different revision caps. One says
  stop, the other says continue, and a run resubmits past the cap.
* `GatekeeperBoundaryTests` - a boundary with no gatekeeper, or two phase
  gatekeepers claiming the same boundary. Either way the package is judged by
  the wrong evidence table or by nobody.
* `GuardedTransitionTests` - a `guards` string naming a transition the state
  machine forbids. Every validator reads that field for presence only, so the
  spec could send a gatekeeper down an edge no owner is allowed to take, and the
  run would discover it as an invalid transition mid-handoff.
* `StageConditionTests` - a `fan_out` that stops producing the number of records
  the gate counts, and a conditional stage no document admits is conditional.
  The first is a pipeline that cannot close; the second is a stage run every
  time or skipped with no record.

Every expectation is derived from `team-manifest.yaml`, `pipelines.yaml`,
`gates.yaml`, `routing-doctrine.md`, or `contracts/workflow-protocol.md`, so the
specs stay the single source of truth and no assertion can rot independently of
them.
"""

import copy
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


def _load_text(text):
    if yaml is None:  # pragma: no cover
        from data_formats import parse_yaml
        return parse_yaml(text)
    return yaml.safe_load(text)


GATES = _load(SKILLS / "gates.yaml")
PIPELINES = _load(SKILLS / "pipelines.yaml")
TEAM = _load(SKILLS / "team-manifest.yaml")
DOCTRINE = (SKILLS / "routing-doctrine.md").read_text(encoding="utf-8")
WORKFLOW = (SKILLS / "contracts" / "workflow-protocol.md").read_text(
    encoding="utf-8")

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


SKILL_DIRS = _skill_dirs()
#: Catalog-relative path of every skill, e.g. "design/planner" -> "planner".
SKILL_PATHS = {d.relative_to(SKILLS).as_posix(): n for n, d in SKILL_DIRS.items()}
#: Directories directly under skills/. A reference whose first path segment is
#: not one of these is not claiming a location in the catalog at all.
TOP_LEVEL = {p.name for p in SKILLS.iterdir() if p.is_dir()}


def _skill_md(name: str) -> str:
    return (SKILL_DIRS[name] / "SKILL.md").read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """The body of one `## heading` section, or '' when the skill has none."""
    match = re.search(r"^## " + re.escape(heading) + r"\s*$(.*?)(?=^## |\Z)",
                      text, re.S | re.M)
    return match.group(1) if match else ""


def _stages():
    """(pipeline, pipeline owner, stage, role, skill) for every delegation."""
    for name, pipeline in (PIPELINES.get("pipelines") or {}).items():
        owner = pipeline.get("owner")
        for stage in pipeline.get("stages") or []:
            for role in ("owner", "delegate"):
                who = stage.get(role)
                if who:
                    yield name, owner, stage.get("step"), role, who


def _roster() -> set:
    """Every name the manifest declares, across all nine role and list keys."""
    names = set()
    for key in ("phase_leads", "phase_gatekeepers", "pipeline_owners", "specialists",
                "creation", "release", "safety", "browser", "testing"):
        names.update(TEAM.get(key) or [])
    for key in ("front_door", "session_memory", "cross_stage_gatekeeper"):
        if TEAM.get(key):
            names.add(TEAM[key])
    return names


ROSTER = _roster()


class DelegationTargetTests(unittest.TestCase):
    """Every skill a surface names as a delegate is a skill that exists.

    Six skills declare a `## Delegation Surface` and thirty-six a
    `## Collaboration Surface`; between them they name the entire delegation
    graph in prose, and nothing resolved a single one of those names. A skill
    renamed or moved leaves the naming side pointing at nothing, and the error
    surfaces only when an orchestrator tries to hand off mid-run.

    **How the extraction is scoped.** These sections also name artifacts
    (`bug-findings`), evidence keys (`security_seed`), boundaries
    (`design-to-build`), stage ids (`phase-gate`), pipelines (`build`,
    `review`, `security`), verdicts (`REVISE`) and files
    (`../../pipelines.yaml`, `references/workflow.md`). Resolving every
    backticked token would fail on all of those, so only two shapes are read:

    1. **Catalog paths** - a token like `design/planner` or `review/code-chief`,
       backticked or bare, whose first segment is a real directory under
       `skills/`. Such a token asserts a location inside the catalog, so it must
       hold a SKILL.md. The first-segment rule is what keeps `frontend/UI` and
       `references/workflow.md` out; the shape rule is what keeps
       `../../pipelines.yaml` out.
    2. **Backticked bare names in bullet-leading position** - the first token of
       a bullet is that bullet's subject by the format of these sections, so
       `` - `session-memory` owns the run record `` names a delegate.

    A bare name *mid*-bullet is deliberately not read. `security-review` is at
    once a skill, a boundary and a pipeline; `build`, `review` and `design` are
    pipelines that are not skills. Nothing in the text says which is meant, and
    a rule that guesses is worse than no rule.
    """

    #: A catalog path: lowercase slug segments, no extension, no traversal.
    PATH = re.compile(r"(?<![\w/.-])([a-z][a-z0-9-]*(?:/[a-z0-9-]+)+)(?![\w/.-])")
    #: A backticked bare slug opening a list bullet.
    LEAD = re.compile(r"^[-*]\s+`([a-z][a-z0-9-]*)`(?=[\s,.]|$)")

    @classmethod
    def references(cls, section: str) -> list:
        """Every token in a surface section that names a skill. See the class doc."""
        found = []
        for token in cls.PATH.findall(section):
            if token.split("/", 1)[0] in TOP_LEVEL:
                found.append(token)
        for line in section.splitlines():
            match = cls.LEAD.match(line.strip())
            if match:
                found.append(match.group(1))
        return found

    @classmethod
    def _surfaces(cls):
        for name in sorted(SKILL_DIRS):
            body = _skill_md(name)
            for heading in ("Delegation Surface", "Collaboration Surface"):
                section = _section(body, heading)
                if section:
                    yield name, heading, section

    @staticmethod
    def _resolves(token: str) -> bool:
        return token in SKILL_PATHS or token in SKILL_DIRS

    def test_every_named_delegate_resolves_to_a_skill(self):
        dangling = []
        for name, heading, section in self._surfaces():
            for token in self.references(section):
                if not self._resolves(token):
                    dangling.append(
                        f"{name} names '{token}' in its {heading} but no SKILL.md "
                        f"declares it")
        self.assertEqual(dangling, [],
                         "a delegation surface may only name skills that exist:\n  "
                         + "\n  ".join(dangling))

    def test_the_extractor_reads_both_spellings_the_catalog_uses(self):
        """Guard against an extractor that silently matches nothing.

        The catalog writes surface bullets two ways - backticked paths in
        thirty-five skills, bare paths in seven - and an earlier version of this
        pattern required the backticks, which skipped those seven entirely while
        still reporting zero failures.
        """
        for sample, expected in [
            ("- `design/planner` (delivery plan, sequenced against the architecture)",
             {"design/planner"}),
            ("- review/code-chief", {"review/code-chief"}),
            ("- `session-memory` owns the run record; investigate never writes it.",
             {"session-memory"}),
            ("- The requesting phase lead - `build/build-management`, `design/commander`, "
             "or `review/code-chief` - receives the fix path for the change it owns.",
             {"build/build-management", "design/commander", "review/code-chief"}),
        ]:
            with self.subTest(sample=sample[:40]):
                self.assertEqual(set(self.references(sample)), expected)

    def test_the_extractor_ignores_the_non_skill_tokens_these_sections_carry(self):
        """Tokens a looser rule matched, each of which is not a skill.

        Every string here is lifted from a real surface section. They are the
        reason the extractor reads catalog paths and bullet-leading names rather
        than every backticked token.
        """
        for sample, expected in [
            # stage ids, evidence keys and boundaries riding beside a real delegate
            ("- `build/security-builder` for `security-checkpoint`, when a trust "
             "boundary is in scope", {"build/security-builder"}),
            ("- `build/test-builder` for `test-surface`", {"build/test-builder"}),
            # a pipeline name and a relative file path, neither a skill
            ("The `build` pipeline stages in `../../pipelines.yaml` and their owners.",
             set()),
            ("`references/workflow.md` - \"Collaboration notes\" - states what each "
             "party owns.", set()),
            # a slash pair whose first segment is not a catalog directory
            ("- `design/architect` (architecture, API endpoint contracts, and the "
             "frontend/UI visual design system)", {"design/architect"}),
            # `admiral` and `security-review` are both skills, but here they are a
            # route qualifier and a boundary; mid-bullet bare names are not read
            ("- `gatekeeper-admiral` through `admiral` (the verdict at `security-review`)",
             {"gatekeeper-admiral"}),
            # the sentinel an empty surface uses
            ("- None required beyond the active task surface.", set()),
        ]:
            with self.subTest(sample=sample[:40]):
                self.assertEqual(set(self.references(sample)), expected)

    def test_the_surfaces_are_read_and_are_not_mostly_empty(self):
        """A parser that finds no sections would make the rule above vacuous."""
        surfaces = list(self._surfaces())
        self.assertGreaterEqual(len(surfaces), 40,
                                "the catalog declares a surface in most skills")
        named = sum(len(self.references(section)) for _, _, section in surfaces)
        self.assertGreaterEqual(named, 100,
                                "the extractor found almost no delegation targets")


class DelegationSymmetryTests(unittest.TestCase):
    """A specialist's surface names every owner that delegates to it.

    `test_catalog_contracts.StageDelegationTests` walks this edge forwards - a
    pipeline owner must name each of its stage owners. Nothing walked it back,
    and the back direction is the one that rots: a lens gains a second pipeline,
    its `## Entry Routing` is updated because that is where the loop guard lives,
    and its surface keeps listing only the pipeline it started in. The audit that
    added this test found exactly that in `review/design-qa` and `review/frontier`
    - both serve the `redesign` pipeline, both accept a `design/redesign` handoff
    in their Entry Routing, and neither named `design/redesign` as a party it
    works with. A reader auditing who may call that lens would have concluded
    only `code-chief` could.

    **Scoped to internal specialists that already publish a surface.** Two groups
    are deliberately out of scope. Ten skills - the four gatekeepers, the
    skill-maker family, `taste`, `taste-review`, `session-memory` - declare no
    surface section at all; requiring one is an editorial decision this
    comparator has no standing to make. Standalone tools like
    `open-browser` do appear as stage owners, but they are
    reachable without any handoff, so the delegating owner is one caller among
    many rather than the only door in.
    """

    @classmethod
    def surface(cls, name: str) -> str:
        body = _skill_md(name)
        for heading in ("Delegation Surface", "Collaboration Surface"):
            section = _section(body, heading)
            if section.strip():
                return section
        return ""

    @classmethod
    def delegations(cls):
        """(specialist, delegating owner, pipeline, stage) for scoped specialists."""
        specialists = SpecialistEntryRoutingTests.internal_specialists()
        for pipeline, owner, step, _role, who in _stages():
            if who in specialists and who != owner and cls.surface(who):
                yield who, owner, pipeline, step

    def test_every_specialist_surface_names_its_delegating_owner(self):
        violations, checked = [], 0
        for who, owner, pipeline, step in self.delegations():
            checked += 1
            named = {SKILL_PATHS.get(token, token) for token in
                     DelegationTargetTests.references(self.surface(who))}
            if owner not in named:
                violations.append(
                    f"{who} runs {pipeline}/{step} for '{owner}' but its surface never "
                    f"names {owner}")
        self.assertEqual(sorted(set(violations)), [],
                         "a specialist works with the owner that delegates to it:\n  "
                         + "\n  ".join(sorted(set(violations))))
        self.assertGreaterEqual(checked, 20,
                                "almost no specialist delegations were checked")

    def test_the_two_pipeline_specialists_are_in_scope(self):
        """The rule must cover the specialists that serve more than one owner.

        A specialist reached by one owner cannot drift; the ones that can are
        those with two. If the scoping ever excludes them the rule above still
        passes while checking nothing that matters.
        """
        owners = {}
        for who, owner, _pipeline, _step in self.delegations():
            owners.setdefault(who, set()).add(owner)
        shared = {who for who, names in owners.items() if len(names) > 1}
        self.assertGreaterEqual(len(shared), 4,
                                "the multi-owner specialists dropped out of scope")
        for name in ("design-qa", "frontier"):
            self.assertIn(name, shared, f"{name} serves review and redesign")


class SpecialistEntryRoutingTests(unittest.TestCase):
    """A specialist names the owner that is allowed to delegate to it.

    `routing-doctrine.md` puts internal specialists behind their owning
    sub-orchestrator: reached any other way they must decline and route to the
    front door. Each one states that rule in its own `## Entry Routing` section
    by naming the owner whose handoff it accepts. Nothing compared those names
    against `pipelines.yaml`, so a stage could be reassigned to a new owner while
    the specialist still recognised only the old one - and the specialist would
    then bounce a legitimate delegation back to `admiral`, which looks like a
    routing loop rather than a spec conflict.

    The delegating owner is the *pipeline's* `owner`, not the stage's: the stage
    owner is the specialist itself, and it is the pipeline owner that hands the
    work over.

    The owner must be named inside a code span, bare (`` `taste` ``) or as a
    catalog path (`` `design/commander` ``). A plain word-boundary search was the
    first version and it is wrong in a way that only ever hides failures: three
    owner names - `taste`, `ship`, `investigate` - are ordinary English, and
    `review/design-qa` ends its Entry Routing with "a fidelity judgment against
    an unpinned baseline is taste, not verification". A loose matcher reads that
    sentence as design-qa recognising the `taste` skill. Every one of the
    catalog's thirty-three specialist delegations satisfies the strict form, so
    the tighter rule costs no coverage and closes the hole.
    """

    @staticmethod
    def _names(section: str, owner: str) -> bool:
        return re.search(r"`(?:[a-z0-9-]+/)?" + re.escape(owner) + r"`", section) is not None

    @staticmethod
    def _routing_rows() -> dict:
        """The routing-class table as {class: member cell}."""
        table = re.search(r"^## Routing classes\s*$(.*?)(?=^## )", DOCTRINE, re.S | re.M)
        assert table, "routing-doctrine.md has no Routing classes section"
        rows = {}
        for cls, members in re.findall(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|.*\|\s*$",
                                       table.group(1), re.M):
            if cls in {"Routing class"} or set(cls) <= {"-", " "}:
                continue
            rows[cls] = members
        return rows

    @classmethod
    def internal_specialists(cls) -> set:
        """The internal-specialist row of routing-doctrine.md, resolved to names.

        The row reads "every skill under `design/`, `build/`, `review/` not named
        in a row above; `taste/taste-review`; `skill-maker/skill-creator` and
        `skill-maker/skill-reviewer`", so it is a set of directory prefixes minus
        the skills other rows claim, plus three explicit paths. Both halves are
        read from the table rather than restated here, so the classification
        tracks the doctrine.
        """
        rows = cls._routing_rows()
        row = next(v for k, v in rows.items() if k.startswith("Internal specialist"))
        tokens = re.findall(r"`([^`]+)`", row)
        prefixes = [t for t in tokens if t.endswith("/")]
        explicit = {SKILL_PATHS[t] for t in tokens if t in SKILL_PATHS}

        claimed = set()
        for name, members in rows.items():
            if name.startswith("Internal specialist"):
                continue
            for token in re.findall(r"`([^`]+)`", members):
                if token in SKILL_DIRS:
                    claimed.add(token)
                elif token in SKILL_PATHS:
                    claimed.add(SKILL_PATHS[token])

        found = set(explicit)
        for path, name in SKILL_PATHS.items():
            if any(path.startswith(p) for p in prefixes) and name not in claimed:
                found.add(name)
        return found

    def test_the_routing_table_yields_a_usable_specialist_set(self):
        """A table parse that returned nothing would make the rule below vacuous."""
        rows = self._routing_rows()
        self.assertGreaterEqual(len(rows), 6, "routing-doctrine.md lost its class rows")
        specialists = self.internal_specialists()
        self.assertGreaterEqual(len(specialists), 15,
                                "the internal-specialist row resolved to almost nothing")
        # A specialist is never an orchestrator: the two rows must not overlap.
        orchestrators = set(TEAM.get("phase_leads") or []) | set(TEAM.get("pipeline_owners") or [])
        self.assertEqual(specialists & orchestrators, set(),
                         "a pipeline owner filed as an internal specialist")

    def test_every_delegated_specialist_declares_an_entry_routing_section(self):
        missing = []
        specialists = self.internal_specialists()
        for _pipeline, _owner, _step, _role, who in _stages():
            if who in specialists and not _section(_skill_md(who), "Entry Routing"):
                missing.append(who)
        self.assertEqual(sorted(set(missing)), [],
                         "an internal specialist must state how it may be entered:\n  "
                         + "\n  ".join(sorted(set(missing))))

    def test_every_internal_specialist_names_its_delegating_owner(self):
        specialists = self.internal_specialists()
        violations = []
        checked = 0
        for pipeline, owner, step, role, who in _stages():
            if who not in specialists or who == owner:
                continue
            routing = _section(_skill_md(who), "Entry Routing")
            if not routing:
                continue  # reported by the test above
            checked += 1
            if not self._names(routing, owner):
                violations.append(
                    f"{who} runs {pipeline}/{step} as its {role} but its Entry Routing "
                    f"never names the delegating owner '{owner}'")
        self.assertEqual(violations, [],
                         "a specialist must recognise the owner that delegates to it:\n  "
                         + "\n  ".join(violations))
        self.assertGreaterEqual(checked, 20,
                                "almost no specialist delegations were checked")

    def test_the_owner_matcher_ignores_the_owner_name_used_as_english(self):
        """`taste`, `ship` and `investigate` are skills and also ordinary words."""
        prose = ("a fidelity judgment against an unpinned baseline is taste, not "
                 "verification. Investigate the failure before you ship it.")
        for owner in ("taste", "ship", "investigate"):
            with self.subTest(owner=owner, kind="english word"):
                self.assertFalse(self._names(prose, owner))
        for section, owner in [
            ("the prompt carries a `### Save Context` block from `taste`", "taste"),
            ("the invocation explicitly names `design/commander` as the owner", "commander"),
            ("(or `design/redesign` at `redesign-review`)", "redesign"),
        ]:
            with self.subTest(owner=owner, kind="real reference"):
                self.assertTrue(self._names(section, owner))


class DelegationGraphTests(unittest.TestCase):
    """Delegation runs downhill and stops.

    `pipelines.yaml` is the only machine-readable statement of who hands work to
    whom, and nothing has ever traversed it. A cycle - an orchestrator whose
    pipeline delegates to a skill whose own pipeline delegates back - never
    terminates and never assembles a package, so no gate ever closes and the run
    hangs rather than failing.

    A stage whose owner is the pipeline's own owner is not an edge: `taste` runs
    eight of its nine stages itself, and reading those as self-delegation would
    report a cycle in every pipeline that does its own work.
    """

    @staticmethod
    def graph() -> dict:
        edges = {}
        for _pipeline, owner, _step, _role, who in _stages():
            if owner and who != owner:
                edges.setdefault(owner, set()).add(who)
        return edges

    def test_the_graph_has_edges(self):
        """An empty graph is trivially acyclic, which would prove nothing."""
        edges = self.graph()
        self.assertGreaterEqual(len(edges), 8, "most pipelines delegate to someone")
        self.assertGreaterEqual(sum(len(v) for v in edges.values()), 30)

    def test_every_delegation_edge_ends_at_a_skill(self):
        unknown = sorted({w for targets in self.graph().values() for w in targets
                          if w not in SKILL_DIRS})
        self.assertEqual(unknown, [],
                         "a pipeline delegates to something that is not a skill: "
                         + ", ".join(unknown))

    def test_the_delegation_graph_is_acyclic(self):
        edges = self.graph()
        state, cycles = {}, []

        def walk(node, path):
            state[node] = "open"
            for target in sorted(edges.get(node, ())):
                if state.get(target) == "open":
                    start = path.index(target) if target in path else 0
                    cycles.append(" -> ".join(path[start:] + [node, target]))
                elif target not in state:
                    walk(target, path + [node])
            state[node] = "done"

        for node in sorted(set(edges) | {w for v in edges.values() for w in v}):
            if node not in state:
                walk(node, [])
        self.assertEqual(cycles, [],
                         "delegation must terminate:\n  " + "\n  ".join(cycles))


class VerdictVocabularyTests(unittest.TestCase):
    """Three verdict tokens, catalog-wide, and no fourth.

    `team-manifest.yaml` declares `verdicts: [APPROVED, REVISE, ESCALATE]` and
    `check.py` emits nothing else. The submitting orchestrator branches on
    exactly those three, so a skill that documents a fourth teaches a verdict the
    receiver cannot act on - and the receiver's most likely reading of an
    unrecognised token is that the gate did not fail.

    **Script output is not a verdict, and the distinction is the whole
    difficulty.** `harness/gatekeeper/check.py` and the per-gate `scripts/check.py`
    report `PASS` / `FAIL` / `UNCHECKED` findings and a `gate_status` of
    `STRUCTURE_OK` / `NEEDS_JUDGMENT` / `BLOCKERS_PRESENT`; every gatekeeper
    states in so many words that those scripts never emit a verdict. Those tokens
    are correct where they appear and must not be flagged. Three narrow rules
    separate the two vocabularies without ever having to name the script tokens:

    * **Alternation.** A run of shouted tokens joined by `/`, `,`, `or` or `and`
      is a single vocabulary. If the run contains a canonical verdict, every
      token in it must be canonical. A run of script tokens contains none, so it
      is not examined at all.
    * **Issuance.** A shouted token that is the direct object of "return",
      "issue" or "emit" is a verdict, unless it heads an alternation - which is
      how "returns `PASS` / `FAIL` / `UNCHECKED` findings" stays out.
    * **Mapping.** `skill-maker` grades with a private `SHIP` / `ITERATE` /
      `BLOCKED` scale and `admiral` translates it. A translation whose target is
      a verdict must land on all three: a mapping that covers only two leaves one
      verdict unreachable, and one that invents a fourth target reintroduces the
      defect through the back door.
    """

    VOCAB = set(TEAM.get("verdicts") or [])
    SHOUT = r"[A-Z][A-Z_]{2,}"
    #: X -> Y, in the three arrow spellings the catalog uses (ASCII, fat, and
    #: the box-drawn U+2192 that the unicode documents prefer).
    MAP = re.compile(r"`?(" + SHOUT + r")`?\s*(?:-{1,3}>|={1,3}>|\u2500*\u2192)\s*`?("
                     + SHOUT + r")`?")
    ALT = re.compile(r"(?:`?" + SHOUT + r"`?)(?:\s*(?:/|,|,?\s+or|,?\s+and)\s*(?:`?"
                     + SHOUT + r"`?))+")
    TOKEN = re.compile(r"\b(" + SHOUT + r")\b")
    ISSUE = re.compile(r"\b(?:[Rr]eturns?|[Ii]ssues?|[Ee]mits?)\s+(?:a|an|the)?\s*`("
                       + SHOUT + r")`(?!\s*(?:/|,\s*`?[A-Z]|\s+(?:and|or)\s+`?[A-Z]))")

    @staticmethod
    def segments(text: str) -> list:
        """Bullets and paragraphs, unwrapped.

        A mapping is often wrapped across two source lines, so line-at-a-time
        reading splits `ITERATE ->` from its target and the mapping looks partial.
        """
        out = []
        for block in re.split(r"\n\s*\n", text):
            for piece in re.split(r"\n(?=\s*[-*+]\s)", block):
                collapsed = " ".join(piece.split())
                if collapsed:
                    out.append(collapsed)
        return out

    @classmethod
    def alternation_defects(cls, segment: str) -> list:
        """Non-verdict tokens sharing an alternation with a verdict."""
        # A mapping pair is two vocabularies meeting, not one alternation: blank
        # each pair out before looking for runs, or the comma between `SHIP` ->
        # `APPROVED` and `ITERATE` -> `REVISE` reads as `APPROVED`, `ITERATE`.
        flat = cls.MAP.sub(" mapped ", segment)
        defects = []
        for run in cls.ALT.finditer(flat):
            tokens = set(cls.TOKEN.findall(run.group(0)))
            if tokens & cls.VOCAB and not tokens <= cls.VOCAB:
                defects.append((run.group(0).strip(), sorted(tokens - cls.VOCAB)))
        return defects

    @classmethod
    def mapping_targets(cls, segment: str) -> list:
        """Targets of a mapping run that lands on at least one verdict."""
        pairs = cls.MAP.findall(segment)
        targets = [target for _source, target in pairs]
        if len(pairs) >= 2 and any(t in cls.VOCAB for t in targets):
            return targets
        return []

    def test_the_manifest_declares_the_three_token_vocabulary(self):
        self.assertEqual(self.VOCAB, {"APPROVED", "REVISE", "ESCALATE"})
        self.assertEqual(set(GATES.get("verdicts") or []), self.VOCAB,
                         "gates.yaml and team-manifest.yaml must declare the same verdicts")

    def test_no_alternation_beside_a_verdict_introduces_a_fourth(self):
        violations = []
        for name in sorted(SKILL_DIRS):
            for segment in self.segments(_skill_md(name)):
                for run, extra in self.alternation_defects(segment):
                    violations.append(f"{name}: {run!r} lists {', '.join(extra)} "
                                      f"beside a gate verdict")
        self.assertEqual(violations, [],
                         "the gate vocabulary is exactly three tokens:\n  "
                         + "\n  ".join(violations))

    def test_every_verdict_a_skill_issues_is_one_of_the_three(self):
        violations, issued = [], 0
        for name in sorted(SKILL_DIRS):
            for match in self.ISSUE.finditer(_skill_md(name)):
                issued += 1
                if match.group(1) not in self.VOCAB:
                    violations.append(f"{name} says {match.group(0).strip()!r}")
        self.assertEqual(violations, [],
                         "a skill may only issue a declared verdict:\n  "
                         + "\n  ".join(violations))
        self.assertGreaterEqual(issued, 20, "the issuance rule matched almost nothing")

    def test_a_private_verdict_scale_maps_onto_all_three(self):
        violations, mappings = [], 0
        for name in sorted(SKILL_DIRS):
            for segment in self.segments(_skill_md(name)):
                targets = self.mapping_targets(segment)
                if not targets:
                    continue
                mappings += 1
                if set(targets) != self.VOCAB:
                    violations.append(
                        f"{name} maps onto {sorted(set(targets))}; the gate vocabulary "
                        f"is {sorted(self.VOCAB)}")
        self.assertEqual(violations, [],
                         "a private verdict scale must translate onto the whole "
                         "vocabulary:\n  " + "\n  ".join(violations))
        self.assertGreaterEqual(mappings, 1,
                                "skill-maker's verdict mapping is no longer detected")

    def test_every_gatekeeper_states_the_whole_vocabulary(self):
        gatekeepers = set(TEAM.get("phase_gatekeepers") or [])
        if TEAM.get("cross_stage_gatekeeper"):
            gatekeepers.add(TEAM["cross_stage_gatekeeper"])
        self.assertGreaterEqual(len(gatekeepers), 4)
        incomplete = []
        for name in sorted(gatekeepers):
            body = _skill_md(name)
            absent = [v for v in sorted(self.VOCAB)
                      if not re.search(r"\b" + v + r"\b", body)]
            if absent:
                incomplete.append(f"{name} never states {', '.join(absent)}")
        self.assertEqual(incomplete, [],
                         "a gatekeeper must state every verdict it can return:\n  "
                         + "\n  ".join(incomplete))

    def test_the_detectors_tell_a_verdict_from_a_script_finding(self):
        """The distinction the class doc turns on, pinned to real sentences.

        The first group is script output lifted from the gatekeeper skills and
        must never be flagged; the second group is what a fourth verdict would
        actually look like and must always be flagged. Without this the two rules
        could quietly stop matching and the suite would stay green.
        """
        clean = [
            "It returns `PASS` / `FAIL` / `UNCHECKED` findings plus a `gate_status`.",
            "a `gate_status` (`STRUCTURE_OK` / `NEEDS_JUDGMENT` / `BLOCKERS_PRESENT`)",
            "apply judgment to the `FAIL` and `UNCHECKED` findings to choose",
            "Map skill-maker verdicts as `SHIP` -> `APPROVED`, `ITERATE` -> `REVISE`, "
            "`BLOCKED` -> `ESCALATE`.",
            "Boundary verdict record with `APPROVED`, `REVISE`, or `ESCALATE`.",
            "Return `REVISE` to `design-qa` and require hashed captures.",
        ]
        for sentence in clean:
            with self.subTest(kind="script output or correct verdict", text=sentence[:40]):
                self.assertEqual(self.alternation_defects(sentence), [])
                self.assertEqual(
                    [m.group(1) for m in self.ISSUE.finditer(sentence)
                     if m.group(1) not in self.VOCAB], [])
        dirty = [
            ("Return `APPROVED`, `REVISE`, `ESCALATE`, or `NEEDS_JUDGMENT`.", "alternation"),
            ("The verdict is `APPROVED` / `REVISE` / `ESCALATE` / `PASS`.", "alternation"),
            ("The gate returns `NEEDS_JUDGMENT` when the evidence is thin.", "issuance"),
        ]
        for sentence, rule in dirty:
            with self.subTest(kind="fourth verdict", rule=rule, text=sentence[:40]):
                flagged = bool(self.alternation_defects(sentence)) or any(
                    m.group(1) not in self.VOCAB for m in self.ISSUE.finditer(sentence))
                self.assertTrue(flagged, f"detector missed a fourth verdict: {sentence}")
        with self.subTest(kind="partial mapping"):
            self.assertEqual(
                self.mapping_targets("`SHIP` -> `APPROVED`, `ITERATE` -> `REVISE`."),
                ["APPROVED", "REVISE"])


class PipelineOwnerRoleTests(unittest.TestCase):
    """A pipeline is owned by an orchestrator, and a delegate is a real skill.

    `test_pipeline_contracts.py` requires every owner to be *somewhere* on the
    roster, which a specialist also satisfies. It is the role that matters: a
    pipeline owned by a specialist has no one bound by the execution contract to
    assemble the package and submit it at the boundary, and the boundary then has
    no submitter. `routing-doctrine.md` makes the same split in prose - pipeline
    owners defer, internal specialists are reached only through them.

    The `delegate` field is the other gap, and `pipelines.yaml` says so itself:
    "Judgement: no comparator checks that the delegate exists or is reachable."
    Three stages carry one, and a typo in any of them fails when the stage runs.
    """

    ORCHESTRATORS = set(TEAM.get("phase_leads") or []) | set(TEAM.get("pipeline_owners") or [])

    def test_the_roster_and_roles_are_populated(self):
        self.assertGreaterEqual(len(ROSTER), 40, "the manifest roster looks truncated")
        self.assertGreaterEqual(len(self.ORCHESTRATORS), 8)

    def test_every_pipeline_owner_holds_an_orchestrator_role(self):
        wrong = []
        for name, pipeline in (PIPELINES.get("pipelines") or {}).items():
            owner = pipeline.get("owner")
            if owner not in self.ORCHESTRATORS:
                wrong.append(
                    f"{name} is owned by '{owner}', which team-manifest.yaml declares "
                    f"under neither phase_leads nor pipeline_owners")
        self.assertEqual(wrong, [],
                         "a pipeline owner must hold an orchestrator role:\n  "
                         + "\n  ".join(wrong))

    def test_every_stage_owner_is_on_the_roster(self):
        missing = []
        for pipeline, _owner, step, role, who in _stages():
            if role == "owner" and who not in ROSTER:
                missing.append(f"{pipeline}/{step} owner '{who}' is not on the roster")
        self.assertEqual(missing, [], "\n  ".join(missing))

    def test_every_stage_delegate_is_a_skill_on_the_roster(self):
        missing, delegates = [], 0
        for pipeline, _owner, step, role, who in _stages():
            if role != "delegate":
                continue
            delegates += 1
            if who not in SKILL_DIRS:
                missing.append(f"{pipeline}/{step} delegates to '{who}', which is not a skill")
            elif who not in ROSTER:
                missing.append(f"{pipeline}/{step} delegates to '{who}', which is not on "
                               f"the roster")
        self.assertEqual(missing, [],
                         "a delegate must be a skill the manifest declares:\n  "
                         + "\n  ".join(missing))
        self.assertGreaterEqual(delegates, 3, "the declared delegates are no longer found")


class RevisionCapTests(unittest.TestCase):
    """One revision cap, stated the same number everywhere.

    `gates.yaml` `revise_policy.cycle_cap` decides when a boundary stops
    accepting resubmissions and escalates instead. Thirty-odd documents restate
    it in prose, in at least seven phrasings, and a document that says three
    where the spec says two tells an owner to resubmit past the point the gate
    stops listening - so the run neither advances nor escalates.

    `test_catalog_contracts.py` already checks the one phrasing
    "Maximum revisions per phase/stage/boundary". This reads every phrasing the
    catalog actually uses, including `cycle_cap` of/is/`:`, the bare
    "`cycle_cap` 2" of a cycle-count line, the spelled-out "a cycle cap of two",
    and "Maximum revisions per cross-stage handoff" - which the narrower pattern
    does not match.
    """

    WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    #: Two shapes. The first allows only backticks, spaces and an of/is/:/=
    #: between the phrase and its number, which is what keeps "At the cycle cap,
    #: an unresolved Critical..." and "the revision cap, `post_tool_use.py`" out.
    #: The second requires the explicit colon a "Maximum revisions per X: N" line
    #: always carries, so the phrase cannot reach across a clause to a stray digit.
    CAP = re.compile(
        r"(?:cycle[_ ]cap|revision\s+cap)[`\s]*(?:of|is|set\s+to)?[`\s:=]*"
        r"(\d+|one|two|three|four|five)\b"
        r"|maximum\s+revisions?(?:\s+per\s+[\w-]+(?:[\s-][\w-]+){0,2})?\s*[:=]\s*"
        r"(\d+|one|two|three|four|five)\b", re.I)

    @classmethod
    def stated_caps(cls, text: str) -> list:
        found = []
        for match in cls.CAP.finditer(text):
            raw = (match.group(1) or match.group(2)).lower()
            found.append(int(raw) if raw.isdigit() else cls.WORDS[raw])
        return found

    @staticmethod
    def _documents():
        for path in sorted(SKILLS.rglob("*.md")):
            if "__pycache__" not in path.parts:
                yield path

    def test_the_gate_spec_declares_a_numeric_cap(self):
        cap = (GATES.get("revise_policy") or {}).get("cycle_cap")
        self.assertIsInstance(cap, int, "gates.yaml must declare revise_policy.cycle_cap")

    def test_every_stated_cycle_cap_matches_the_gate_spec(self):
        cap = (GATES.get("revise_policy") or {}).get("cycle_cap")
        violations, seen = [], 0
        for path in self._documents():
            text = path.read_text(encoding="utf-8", errors="replace")
            for stated in self.stated_caps(text):
                seen += 1
                if stated != cap:
                    violations.append(
                        f"{path.relative_to(SKILLS).as_posix()} states a cap of {stated}; "
                        f"gates.yaml revise_policy.cycle_cap is {cap}")
        self.assertEqual(violations, [],
                         "every restatement of the cap must match the spec:\n  "
                         + "\n  ".join(violations))
        self.assertGreaterEqual(seen, 30, "the cap detector matched almost nothing")

    def test_the_cap_detector_reads_every_phrasing_the_catalog_uses(self):
        """Each string is a real sentence; the negatives each broke an earlier pattern."""
        for text, expected in [
            ("exhausting `../gates.yaml` `revise_policy.cycle_cap` of 2", [2]),
            ("`revise_policy.cycle_cap` is 2; a third cycle escalates", [2]),
            ("- Maximum revisions per boundary: 2 (`gates.yaml` `revise_policy.cycle_cap`)", [2]),
            ("- Maximum revisions per cross-stage handoff: 2.", [2]),
            ("- Cycle count: 1 of `revise_policy.cycle_cap` 2. A third cycle escalates.", [2]),
            ("`revise_policy` sets `cycle_cap: 2`. A second `REVISE` ends the cycle", [2]),
            ("| A `REVISE` is one packet with a cycle cap of two |", [2]),
            ("Either way the `cycle_cap` is 2.", [2]),
        ]:
            with self.subTest(kind="phrasing", text=text[:45]):
                self.assertEqual(self.stated_caps(text), expected)
        for text in [
            "At the cycle cap, an unresolved Critical or Major returns unchanged.",
            "the revision cap, `harness/hooks/post_tool_use.py`",
            "the cap never justifies a downgrade",
            "a third cycle escalates to the build owner",
            "`revise_policy.cycle_cap` is never waived by the owner who hit it",
        ]:
            with self.subTest(kind="no number stated", text=text[:45]):
                self.assertEqual(self.stated_caps(text), [])


class GatekeeperBoundaryTests(unittest.TestCase):
    """Every boundary is judged, and the phase gate is judged by exactly one.

    The literal "one gatekeeper per boundary" is false here, and asserting it
    would be asserting a defect. `pipelines.yaml` `gate_model` states the real
    shape: all ten boundaries are validated by `gatekeeper-admiral` as the
    cross-stage handoff, and four of them - design, redesign, build, review -
    are validated *first*, inside the pipeline, by a phase gatekeeper. The six
    that carry no phase-gate stage have no phase gatekeeper by design, and their
    boundary is judged once.

    So the invariant is: at most one phase gatekeeper per boundary; the phase
    gatekeeper that claims a boundary is the owner of that pipeline's
    `phase-gate` stage; a pipeline with no phase-gate stage has no phase
    gatekeeper claiming its boundary; and the cross-stage gatekeeper claims all
    ten. `harness/gatekeeper/test_gate_manifests.py` already checks that each
    table's *evidence keys* mirror the spec. What no test checked is the
    assignment itself - which gatekeeper is standing at which boundary - so a
    phase-gate stage could be handed to the wrong gatekeeper and the package
    would be judged against another boundary's evidence table.
    """

    HEADER = "| Boundary | Guards | Submitter | Required evidence |"

    @classmethod
    def declared(cls) -> dict:
        """{gatekeeper: [boundary]} from each gatekeeper's Boundary Contract table."""
        out = {}
        for name in cls.gatekeepers():
            body = _skill_md(name)
            if cls.HEADER not in body:
                out[name] = []
                continue
            block = body.split(cls.HEADER, 1)[1].split("\n\n", 1)[0]
            out[name] = [m.group(1) for m in
                         re.finditer(r"^\|\s*`([a-z][a-z-]+)`\s*\|", block, re.M)]
        return out

    @staticmethod
    def gatekeepers() -> set:
        names = set(TEAM.get("phase_gatekeepers") or [])
        if TEAM.get("cross_stage_gatekeeper"):
            names.add(TEAM["cross_stage_gatekeeper"])
        return names

    @staticmethod
    def phase_gate_owner(boundary: str):
        """Owner of the phase-gate stage of the pipeline that closes `boundary`."""
        phase = set(TEAM.get("phase_gatekeepers") or [])
        for pipeline in (PIPELINES.get("pipelines") or {}).values():
            if pipeline.get("boundary") != boundary:
                continue
            for stage in pipeline.get("stages") or []:
                if stage.get("owner") in phase:
                    return stage["owner"]
        return None

    def test_every_gatekeeper_declares_a_boundary_table(self):
        empty = sorted(name for name, rows in self.declared().items() if not rows)
        self.assertEqual(empty, [],
                         "a gatekeeper must publish the boundaries it judges: "
                         + ", ".join(empty))

    def test_every_declared_boundary_exists_in_the_gate_spec(self):
        spec = set(GATES.get("boundaries") or {})
        self.assertGreaterEqual(len(spec), 10)
        unknown = []
        for name, rows in sorted(self.declared().items()):
            for boundary in rows:
                if boundary not in spec:
                    unknown.append(f"{name} judges '{boundary}', which gates.yaml "
                                   f"does not define")
        self.assertEqual(unknown, [],
                         "a gatekeeper may only judge a declared boundary:\n  "
                         + "\n  ".join(unknown))

    def test_the_cross_stage_gatekeeper_judges_every_boundary(self):
        cross = TEAM.get("cross_stage_gatekeeper")
        declared = set(self.declared().get(cross) or [])
        missing = sorted(set(GATES.get("boundaries") or {}) - declared)
        self.assertEqual(missing, [],
                         f"{cross} is the cross-stage gate for the whole catalog but "
                         f"never judges: " + ", ".join(missing))

    def test_no_boundary_carries_two_phase_gatekeepers(self):
        phase = set(TEAM.get("phase_gatekeepers") or [])
        declared = self.declared()
        doubled = []
        for boundary in sorted(GATES.get("boundaries") or {}):
            claiming = sorted(g for g in phase if boundary in (declared.get(g) or []))
            if len(claiming) > 1:
                doubled.append(f"{boundary} is claimed by {', '.join(claiming)}")
        self.assertEqual(doubled, [],
                         "a boundary has one phase gatekeeper at most:\n  "
                         + "\n  ".join(doubled))

    def test_the_phase_gate_stage_owner_is_the_gatekeeper_that_claims_it(self):
        phase = set(TEAM.get("phase_gatekeepers") or [])
        declared = self.declared()
        mismatched, matched = [], 0
        for boundary in sorted(GATES.get("boundaries") or {}):
            claiming = sorted(g for g in phase if boundary in (declared.get(g) or []))
            stage_owner = self.phase_gate_owner(boundary)
            if stage_owner is None:
                # gate_model: six boundaries have no phase gatekeeper by design.
                if claiming:
                    mismatched.append(
                        f"{boundary} has no phase-gate stage but {', '.join(claiming)} "
                        f"claims it")
                continue
            matched += 1
            if claiming != [stage_owner]:
                mismatched.append(
                    f"{boundary} runs its phase gate under '{stage_owner}' but the "
                    f"gatekeeper claiming that boundary is {claiming or 'nobody'}")
        self.assertEqual(mismatched, [],
                         "the phase-gate stage owner and the boundary's gatekeeper are "
                         "the same skill:\n  " + "\n  ".join(mismatched))
        self.assertGreaterEqual(matched, 4,
                                "the four phase-gated boundaries are no longer found")

    def test_every_boundary_submitter_is_the_owner_of_the_pipeline_that_closes_it(self):
        """A gate is opened by the pipeline that closes it, not by a specialist.

        `gates.yaml` names a submitter per boundary and `pipelines.yaml` names an
        owner per pipeline. Both are checked against the roster; neither was
        checked against the other, so the gate could expect a package from one
        skill while the pipeline hands assembly to a different one, and the
        boundary would reject a correct package as coming from the wrong owner.
        """
        owners = {p.get("boundary"): p.get("owner")
                  for p in (PIPELINES.get("pipelines") or {}).values()}
        wrong = []
        for boundary, spec in (GATES.get("boundaries") or {}).items():
            submitter = spec.get("submitter")
            expected = owners.get(boundary)
            if expected is not None and submitter != expected:
                wrong.append(f"{boundary} expects a package from '{submitter}' but the "
                             f"pipeline that closes it is owned by '{expected}'")
        self.assertEqual(wrong, [],
                         "the gate submitter is the owning pipeline's owner:\n  "
                         + "\n  ".join(wrong))


class GuardedTransitionTests(unittest.TestCase):
    """A `guards` string is a walk through the declared state machine.

    Every boundary in `gates.yaml` carries a `guards` string naming the workflow
    transition it governs. `scripts/validate_manifests.py` check_gates and
    `harness/gatekeeper/test_gate_manifests.py` GateSpecContractTests both
    require that string to be non-empty, and neither reads a character of it -
    `gates.yaml` said so itself under `unchecked_fields` until this class landed.
    So the spec could name a transition the state machine forbids, and a
    gatekeeper following the spec would drive the run into an edge no owner is
    allowed to take. One did: `redesign-review` guarded `GATE -> DESIGN` while
    the `GATE` row allowed only RELEASE, COMPLETE, REVISE, BLOCKED, ESCALATE and
    SAFETY. The spec won and the `GATE` row gained DESIGN. The contract's own
    tie-break did not settle it - Failure paths gives the spec the guarded
    transition and the contract the allowed transitions, which is exactly the
    overlap in dispute. What settled it was that the doctrine contradicted
    itself: this document's Gate boundaries table names `GATE -> DESIGN` for
    the same boundary, and `TASTE_GATE_PENDING` already declares the same
    approved handoff into DESIGN for the taste gate. Two statements of the edge
    against one row that predates the redesign pipeline.

    `contracts/workflow-protocol.md` declares the machine in its
    `## States and transitions` table: one row per state, with the row's fourth
    cell listing the states it may move to. This walks the `guards` chain across
    that table.

    **How the tokenizer separates state names from commentary.** The strings are
    written for a reader, not a parser: `REDESIGN (design-shaped) -> GATE ->
    DESIGN with the chosen variant, or COMPLETE`. Three rules, in this order:

    1. Split the string on `->`. Each piece is one step of the chain.
    2. Inside a step, read only ALL-CAPS tokens of three characters or more.
       That is the whole state vocabulary and nothing else in these strings is
       written that way, so `(design-shaped)`, `with the chosen variant`,
       `or consuming pipeline` and the lowercase pipeline origins
       (`security pipeline`, `investigation`) drop out by construction. The
       three-character floor keeps a two-letter acronym in commentary - `UI`,
       `QA` - from being read as a state.
    3. A step may name several states (`the owning phase (DESIGN, BUILD, or
       REVIEW)`), and they are alternatives: every alternative must be reachable
       from every alternative of the step before it. A step may name none
       (`security pipeline`), and then the edge into it is unverifiable and is
       skipped rather than guessed.

    Two tokens are not states and are still correct: `REDESIGN` and `TASTE` name
    the *phase* the boundary closes, which is how `contracts/workflow-protocol.md`
    itself writes them ("`TASTE` in the spec is the phase name"; the redesign
    pipeline's "work occupies `DESIGN`-shaped or `BUILD`-shaped states"). Rather
    than exempt the two names, the rule reads them from `pipelines.yaml`: a
    non-state token is admissible when it is the name of the pipeline that closes
    that very boundary, standing at the origin of the chain. Both satisfy that;
    a typo or a phase borrowed from another pipeline would not.

    **Known limit.** An ALL-CAPS English word in commentary - `NOT`, `AND` -
    would be read as a state and reported. No `guards` string contains one, and
    the fix if one is ever wanted is to lowercase it.
    """

    #: A state name: ALL-CAPS, underscores allowed, three characters or more.
    STATE = re.compile(r"(?<![\w-])([A-Z][A-Z_]{2,})(?![\w-])")
    #: A four-column row of the States and transitions table.
    ROW = re.compile(r"^\|([^|\n]+)\|([^|\n]+)\|([^|\n]+)\|([^|\n]+)\|\s*$", re.M)

    @classmethod
    def state_machine(cls) -> dict:
        """{state: {allowed next state}} from `## States and transitions`."""
        machine = {}
        for cells in cls.ROW.findall(_section(WORKFLOW, "States and transitions")):
            state = cells[0].strip()
            if cls.STATE.fullmatch(state):
                machine[state] = set(cls.STATE.findall(cells[3]))
        return machine

    @classmethod
    def chain(cls, guards: str) -> list:
        """A `guards` string as one list of state alternatives per `->` step."""
        return [cls.STATE.findall(step) for step in guards.split("->")]

    @staticmethod
    def closing_pipeline() -> dict:
        """{boundary: the pipeline that closes it}."""
        return {p.get("boundary"): name
                for name, p in (PIPELINES.get("pipelines") or {}).items()}

    def test_the_state_table_parses_into_a_usable_machine(self):
        """A table parse that returned nothing would make every rule below pass."""
        machine = self.state_machine()
        self.assertGreaterEqual(len(machine), 10,
                                "the States and transitions table lost its rows")
        for state in ("DESIGN", "BUILD", "REVIEW", "GATE", "COMPLETE"):
            self.assertIn(state, machine, "the state table lost a lifecycle state")
        dangling = sorted(f"{state} -> {nxt}" for state, allowed in machine.items()
                          for nxt in allowed if nxt not in machine)
        self.assertEqual(dangling, [],
                         "a row allows a move to a state the table never declares:\n  "
                         + "\n  ".join(dangling))

    def test_every_guards_token_is_a_state_or_the_closing_pipeline_phase(self):
        machine = self.state_machine()
        phases = {name.upper().replace("-", "_"): name
                  for name in (PIPELINES.get("pipelines") or {})}
        closing = self.closing_pipeline()
        violations, read = [], 0
        for boundary, spec in sorted((GATES.get("boundaries") or {}).items()):
            steps = self.chain(spec.get("guards", ""))
            for index, tokens in enumerate(steps):
                for token in tokens:
                    read += 1
                    if token in machine:
                        continue
                    if phases.get(token) != closing.get(boundary):
                        violations.append(
                            f"{boundary} guards '{spec.get('guards')}' which names "
                            f"{token}, neither a state workflow-protocol.md declares "
                            f"nor the pipeline that closes this boundary "
                            f"({closing.get(boundary)!r})")
                    elif index != 0:
                        violations.append(
                            f"{boundary} guards '{spec.get('guards')}' which puts the "
                            f"phase name {token} at step {index}; a phase is where a "
                            f"boundary starts, and every later step is a state")
        self.assertEqual(violations, [],
                         "a guards string names only declared states and its own phase:\n  "
                         + "\n  ".join(violations))
        self.assertGreaterEqual(read, 20, "the tokenizer read almost nothing")

    def test_every_guards_chain_is_a_path_the_state_machine_allows(self):
        machine = self.state_machine()
        violations, edges = [], 0
        for boundary, spec in sorted((GATES.get("boundaries") or {}).items()):
            steps = self.chain(spec.get("guards", ""))
            for index in range(len(steps) - 1):
                for source in steps[index]:
                    for target in steps[index + 1]:
                        if source not in machine or target not in machine:
                            continue  # a phase name or a prose step: nothing to walk
                        edges += 1
                        if target not in machine[source]:
                            violations.append(
                                f"{boundary} guards '{spec.get('guards')}' but "
                                f"workflow-protocol.md lets {source} move only to "
                                f"{', '.join(sorted(machine[source]))} - not {target}")
        self.assertEqual(violations, [],
                         "every step of a guards chain is an allowed transition:\n  "
                         + "\n  ".join(violations))
        self.assertGreaterEqual(edges, 8, "almost no guarded edges were walked")

    def test_the_tokenizer_separates_state_names_from_commentary(self):
        """Every string here is a real `guards` value or a near miss of one."""
        for guards, expected in [
            ("DESIGN -> BUILD", [["DESIGN"], ["BUILD"]]),
            ("REVIEW -> GATE -> COMPLETE", [["REVIEW"], ["GATE"], ["COMPLETE"]]),
            ("REDESIGN (design-shaped) -> GATE -> DESIGN with the chosen variant, or COMPLETE",
             [["REDESIGN"], ["GATE"], ["DESIGN", "COMPLETE"]]),
            ("TASTE -> GATE -> COMPLETE or consuming pipeline",
             [["TASTE"], ["GATE"], ["COMPLETE"]]),
            ("investigation -> the owning phase (DESIGN, BUILD, or REVIEW)",
             [[], ["DESIGN", "BUILD", "REVIEW"]]),
        ]:
            with self.subTest(kind="chain", guards=guards[:45]):
                self.assertEqual(self.chain(guards), expected)
        for guards, expected in [
            ("testing-and-qa pipeline -> GATE", [[], ["GATE"]]),
            ("skill-maker pipeline -> GATE", [[], ["GATE"]]),
            ("a UI or QA surface -> GATE", [[], ["GATE"]]),
            ("TASTE_GATE_PENDING -> COMPLETE", [["TASTE_GATE_PENDING"], ["COMPLETE"]]),
        ]:
            with self.subTest(kind="commentary", guards=guards[:45]):
                self.assertEqual(self.chain(guards), expected)

    def test_the_comparator_reports_a_transition_the_table_forbids(self):
        """The rule is only worth its lines if a forbidden edge actually fails."""
        machine = self.state_machine()
        self.assertNotIn("INTAKE", machine["GATE"],
                         "this negative control assumed GATE -> INTAKE stays forbidden")
        steps = self.chain("REVIEW -> GATE -> INTAKE")
        walked = [(a, b) for index in range(len(steps) - 1)
                  for a in steps[index] for b in steps[index + 1]]
        self.assertIn(("GATE", "INTAKE"), walked)
        self.assertTrue(any(b not in machine.get(a, set()) for a, b in walked))


class StageConditionTests(unittest.TestCase):
    """The two stage fields `pipelines.yaml` filed as judgement but need not be.

    `pipelines.yaml` `enforcement.judgement_only` put every `when`, `then`,
    `delegate` and `fan_out` value beyond the reach of a comparator, and
    `stage_fields.when` said in as many words that none evaluates it. Two of the
    four are mechanical; this class takes them, and the enforcement block was
    corrected to match.

    * **`fan_out` against the gate spec.** `redesign/mock-build` fans out four
      mock builds and `gates.yaml` `evidence_type_params.mock_set` requires four
      mocks in the submitted record - a link `check.py` genuinely enforces at the
      gate (`check_variant_set` fails the package when the list length is not
      `required_count`), so a fan-out that drifts is a pipeline that cannot
      close. The link is derived, not hard-coded: the stage owner `prototyper` is
      exactly who `gates.yaml` `evidence_owners` makes responsible for `mock_set`
      at that pipeline's boundary. Since the redesign pipeline became mock-first
      that owner holds *two* counted keys there - `mock_set` at four and
      `selected_variant` at one - so the comparator pairs an owner's counted keys
      with that owner's artifact-bearing stages positionally, and reads a stage
      with no `fan_out` as running once. That makes `selected-build` checkable
      too: the gate counts one built variant, and a stage that quietly started
      fanning out would be caught.
      `design/redesign/agent/agent-manifest.yaml` states the fanned-out number a
      third time, for the same delegate, and is compared too.

    * **`when` against the prose that invokes the stage.** A conditional stage
      that no document admits is conditional gets run every time, or skipped with
      no record - `failure_paths.when_condition_ambiguous` calls the second one
      an evidence gap. Twenty-one stages carry a `when`; four of them are the
      redesign stages that run only when a variant was selected.

    **What was measured before this asserted anything.** Of the original
    seventeen, the *stage owner's* own SKILL.md stated the condition in ten. The
    catalog does not put stage conditionality in the specialist as a rule; it
    puts it in the orchestrator that invokes the stage. `review/code-chief` names
    all five of its conditional lenses with their conditions in one sentence, and
    three of those five specialists quote no condition of their own. So the
    asserted rule accepts either end of the handoff - the stage owner or the
    pipeline owner - which held for fifteen of seventeen, and for all seventeen
    once `investigate` and `qa` were corrected to quote conditions they already
    described in other words. The four mock-first redesign stages follow the same
    pattern: one condition, stated by the pipeline owner `redesign`.

    The stage-owner-only rule is deliberately **not** asserted. At sixteen of
    twenty-one it would fail five stages that are correctly documented one step
    up the handoff - `review/security-review`, `review/penetration-review`,
    `review/frontend-review`, `security/remediation` and `qa/browser-session` -
    and rewriting five specialists to satisfy a rule the catalog does not follow
    is a worse trade than reporting the number. The floor below keeps that
    sixteen from eroding to nothing unnoticed.
    """

    #: A word that frames a quoted phrase as a condition rather than a passing
    #: mention. The hyphen in the lookaround is load-bearing: without it `only`
    #: matches inside `report-only` and `qa-only`, and every sentence in the QA
    #: skill turns into a conditionality statement.
    MARKER = re.compile(
        r"(?<![\w-])(?:when|whenever|only|conditional|conditionally|unless|if|"
        r"skip|skips|skipped|waive|waived|applicable)(?![\w-])")
    #: How far from the quoted condition the framing word may sit. Measured at
    #: 60, 80, 120 and 200 characters: 80 and above all return the same fifteen,
    #: so the constant is not what the result rests on.
    NEARBY = 120

    @staticmethod
    def conditional_stages():
        """(pipeline, pipeline owner, stage) for every stage carrying a `when`."""
        for name, pipeline in (PIPELINES.get("pipelines") or {}).items():
            for stage in pipeline.get("stages") or []:
                if stage.get("when"):
                    yield name, pipeline.get("owner"), stage

    @staticmethod
    def condition(when: str) -> str:
        """The `when` value without its parenthetical gloss.

        `report-only run (fixes not authorized)` is one condition and one
        restatement of it; requiring prose to carry the gloss verbatim would
        fail a document that phrases the same thing in its own words.
        """
        return re.sub(r"\s*\(.*?\)", "", when).strip().lower()

    @classmethod
    def states_the_condition(cls, text: str, when: str) -> bool:
        """The condition appears verbatim, with a framing word beside it.

        The text is flattened first: this catalog hard-wraps at eighty columns,
        so a line-scoped search splits sentences that do state the condition.
        """
        flat = re.sub(r"\s+", " ", text).lower()
        phrase = cls.condition(when)
        for hit in re.finditer(re.escape(phrase), flat):
            window = flat[max(0, hit.start() - cls.NEARBY):hit.end() + cls.NEARBY]
            if cls.MARKER.search(window):
                return True
        return False

    @staticmethod
    def counted_count(gates: dict, key: str) -> int | None:
        """The required_count a key is held to, read by key then by record type."""
        types = gates.get("evidence_types") or {}
        params = gates.get("evidence_type_params") or {}
        for name in (key, types.get(key)):
            entry = params.get(name) if name else None
            if isinstance(entry, dict) and entry.get("required_count") is not None:
                return int(entry["required_count"])
        return None

    @classmethod
    def fan_out_violations(cls, gates: dict, pipelines: dict) -> list:
        """Every stage whose instance count disagrees with what its gate counts.

        One owner can hold more than one counted key at a boundary - at
        `redesign-review` `prototyper` owes four `mock_set` entries and one
        `selected_variant` - so the pairing is positional: that owner's counted
        keys in `required_evidence` order against that owner's artifact-bearing
        stages in pipeline order. A stage that declares no `fan_out` runs once,
        which is a claim about the count too, so it is compared as one rather
        than skipped.
        """
        boundaries = gates.get("boundaries") or {}
        owners = gates.get("evidence_owners") or {}
        found = []
        for name, pipeline in sorted((pipelines.get("pipelines") or {}).items()):
            boundary = pipeline.get("boundary")
            spec = boundaries.get(boundary) or {}
            by_owner: dict[str, list] = {}
            for stage in pipeline.get("stages") or []:
                if stage.get("owner") and stage.get("artifact"):
                    by_owner.setdefault(stage["owner"], []).append(stage)
            for owner, stages in sorted(by_owner.items()):
                counted = [key for key in spec.get("required_evidence") or []
                           if (owners.get(boundary) or {}).get(key) == owner
                           and cls.counted_count(gates, key) is not None]
                if not counted:
                    fanned = [s for s in stages if s.get("fan_out") is not None]
                    found.extend(
                        f"{name}/{s.get('step')} fans out {s['fan_out']} ways but "
                        f"{boundary} gives its owner {owner!r} no counted evidence key, "
                        f"so the number the fan-out must equal is undecidable"
                        for s in fanned)
                    continue
                if len(counted) != len(stages):
                    found.append(
                        f"{name} gives {owner!r} {len(stages)} artifact-bearing stages but "
                        f"{boundary} counts {len(counted)} of its evidence keys "
                        f"({', '.join(counted)}), so which stage produces which count is "
                        f"undecidable")
                    continue
                for key, stage in zip(counted, stages):
                    required = cls.counted_count(gates, key)
                    declared = stage.get("fan_out")
                    if (declared if declared is not None else 1) != required:
                        found.append(
                            f"{name}/{stage.get('step')} runs "
                            f"{declared if declared is not None else 1} time(s) but "
                            f"{boundary} requires exactly {required} {key} entries, so "
                            f"the package can never close the gate")
        return found

    @staticmethod
    def agent_fan_outs():
        """(manifest, owning skill, delegate, count) from every agent manifest."""
        for manifest in sorted(SKILLS.rglob("agent-manifest.yaml")):
            data = _load(manifest) or {}
            owner = SKILL_PATHS.get(manifest.parent.parent.relative_to(SKILLS).as_posix())
            for delegate in data.get("delegates_to") or []:
                if isinstance(delegate, dict) and delegate.get("fan_out") is not None:
                    yield manifest, owner, delegate.get("name"), delegate["fan_out"]

    def test_the_fan_out_link_to_the_gate_spec_is_real(self):
        """The derivation, not the number: one fan-out, one counted key, one owner."""
        fanned = [(n, s) for n, p in (PIPELINES.get("pipelines") or {}).items()
                  for s in p.get("stages") or [] if s.get("fan_out") is not None]
        self.assertGreaterEqual(len(fanned), 1, "no stage declares a fan_out any more")
        counted = {kind for kind, params in (GATES.get("evidence_type_params") or {}).items()
                   if (params or {}).get("required_count") is not None}
        self.assertGreaterEqual(len(counted), 1,
                                "no evidence type carries a required_count any more")

    def test_every_fan_out_matches_the_count_its_gate_requires(self):
        wrong = self.fan_out_violations(GATES, PIPELINES)
        self.assertEqual(wrong, [],
                         "a fan-out must produce the number of records the gate "
                         "counts:\n  " + "\n  ".join(wrong))

    def test_the_fan_out_comparator_reports_a_disagreement(self):
        """Both sides moved independently, so both directions must be caught."""
        gates = copy.deepcopy(GATES)
        gates["evidence_type_params"]["mock_set"]["required_count"] += 1
        self.assertNotEqual([], self.fan_out_violations(gates, PIPELINES),
                            "a raised required_count went unreported")
        gates = copy.deepcopy(GATES)
        gates["evidence_type_params"]["selected_variant"]["required_count"] += 1
        self.assertNotEqual([], self.fan_out_violations(gates, PIPELINES),
                            "a stage that runs once against a count of two went unreported")
        pipelines = copy.deepcopy(PIPELINES)
        for pipeline in (pipelines.get("pipelines") or {}).values():
            for stage in pipeline.get("stages") or []:
                if stage.get("fan_out") is not None:
                    stage["fan_out"] += 1
        self.assertNotEqual([], self.fan_out_violations(GATES, pipelines),
                            "a raised fan_out went unreported")

    def test_every_agent_manifest_fan_out_matches_its_pipeline_stage(self):
        wrong, checked = [], 0
        for manifest, owner, delegate, count in self.agent_fan_outs():
            where = manifest.relative_to(SKILLS).as_posix()
            pipeline = next((p for p in (PIPELINES.get("pipelines") or {}).values()
                             if p.get("owner") == owner), None)
            if pipeline is None:
                wrong.append(f"{where} fans out to {delegate} but {owner!r} owns no pipeline")
                continue
            stages = [s for s in pipeline.get("stages") or []
                      if s.get("owner") == delegate and s.get("fan_out") is not None]
            if len(stages) != 1:
                wrong.append(f"{where} fans out to {delegate} but the {owner!r} pipeline "
                             f"has {len(stages)} fanned-out stages owned by it")
                continue
            checked += 1
            if stages[0]["fan_out"] != count:
                wrong.append(f"{where} fans out to {delegate} {count} ways; "
                             f"pipelines.yaml declares {stages[0]['fan_out']}")
        self.assertEqual(wrong, [],
                         "an agent manifest restates the fan-out and must restate it "
                         "correctly:\n  " + "\n  ".join(wrong))
        self.assertGreaterEqual(checked, 1, "no agent manifest fan-out was compared")

    def test_every_conditional_stage_states_its_condition_in_prose(self):
        undocumented, checked = [], 0
        for name, pipeline_owner, stage in self.conditional_stages():
            checked += 1
            readers = [who for who in (stage.get("owner"), pipeline_owner)
                       if who in SKILL_DIRS]
            if not any(self.states_the_condition(_skill_md(who), stage["when"])
                       for who in readers):
                undocumented.append(
                    f"{name}/{stage.get('step')} runs only on '{stage['when']}' but "
                    f"neither the stage owner ({stage.get('owner')}) nor the pipeline "
                    f"owner ({pipeline_owner}) states that condition, so a reader of "
                    f"either skill invokes the stage unconditionally")
        self.assertEqual(undocumented, [],
                         "a conditional stage must read as conditional somewhere on the "
                         "handoff:\n  " + "\n  ".join(undocumented))
        self.assertGreaterEqual(checked, 19,
                                "the conditional stages are no longer found")

    def test_the_specialists_own_share_of_that_coverage_does_not_erode(self):
        """A floor, not the invariant - see the class docstring.

        Sixteen of the twenty-one conditions are stated by the stage owner
        itself. The rule above accepts the pipeline owner instead, which is how
        the other five are documented; without this floor that allowance could
        hollow out until every specialist read as unconditional. The floor is
        fourteen, not sixteen, so an honest rewording is not a test failure.
        """
        by_owner = [f"{name}/{stage.get('step')}"
                    for name, _pipeline_owner, stage in self.conditional_stages()
                    if stage.get("owner") in SKILL_DIRS
                    and self.states_the_condition(_skill_md(stage["owner"]), stage["when"])]
        self.assertGreaterEqual(
            len(by_owner), 14,
            f"only {len(by_owner)} stage owners still state their own condition")

    def test_the_condition_detector_tells_a_stated_condition_from_a_bare_mention(self):
        """Positives are real catalog sentences; each negative broke an earlier rule."""
        for text, when in [
            ("`../../pipelines.yaml` runs the `setup` stage only `when: first deployment`, "
             "so both artifacts are built to outlive the run", "first deployment"),
            ("Both browser stages are conditional in `../../pipelines.yaml` (`when: browser\n"
             "surface under test`), so a surface with no browser simply skips them.",
             "browser surface under test"),
            ("`review/mr-robot` when an exploitable surface exists, `review/frontier` when\n"
             "visible behavior changed, `review/design-qa` when a visible surface changed",
             "visible behavior changed"),
            ("`debugging` is a conditional stage of the `build` pipeline owned by\n"
             "`debugger`, run when a reproduced build-phase failure exists",
             "reproduced build-phase failure"),
            ("defers report-only runs to `qa-only` when fixes are not applied",
             "report-only run (fixes not authorized)"),
        ]:
            with self.subTest(kind="stated", when=when):
                self.assertTrue(self.states_the_condition(text, when))
        for text, when in [
            ("- Security-relevant architecture decisions, trust boundaries, and\n"
             "  data-sensitivity classifications from the implementation.", "trust boundary"),
            ("The exploitable surface is recorded in the findings table.",
             "exploitable surface"),
            ("Run the stage only when the operator asks for it.", "first deployment"),
            ("`qa-only` handles the report-only run.",
             "report-only run (fixes not authorized)"),
        ]:
            with self.subTest(kind="bare mention", when=when):
                self.assertFalse(self.states_the_condition(text, when))


if __name__ == "__main__":
    unittest.main()
