#!/usr/bin/env python3
"""Comparators for the trigger surface a request is routed on.

A skill's frontmatter `description` is the whole of what a model reads to decide
whether the skill applies. Nothing downstream re-opens the body to correct a
description that has claimed a sibling's phrasing, and nothing compared the
phrasings a SKILL.md advertises under `## Use This Skill When` against the
description that has to make them reachable. Both failures are silent and both
had already happened: `review the code` was claimed by `review/code-chief` and
`review/code-review` at once, and `code quality`, `pressure-test` and
`responsive behavior` were each claimed twice. Every one was found by grepping,
which means the same collision can reappear the next time a description is
widened.

`routing-doctrine.md` has the matching gap one level up. Its routing-class table
decides whether a skill may be entered directly or must hand off first, and the
file's own enforcement table records that no comparator reads it -- a pipeline
owner filed as an internal specialist is exactly the error the table exists to
prevent, and the last one was corrected by hand.

These tests are those comparators. Each derives its expectation from a machine
spec -- `team-manifest.yaml` for the roster, the front door, and the role lists;
the routing-class table for how a skill is entered -- so the specs stay the
single source of truth and the assertions cannot rot independently of them.

What each class prevents:

- `TriggerCollisionTests`: two skills advertising the same phrase, so the phrase
  resolves to whichever one the model happens to prefer. The declared
  `front_door` is exempt by doctrine, because fronting the lifecycle triggers is
  its job; nothing else is.
- `AdvertisedTriggerTests`: a body that advertises a phrasing the description
  cannot reach, which is a trigger documented for a human reader and invisible
  to the router that actually decides.
- `TriggerReachabilityTests`: a skill with no trigger surface of its own, an
  empty description, or one written in a voice that addresses the reader instead
  of describing the skill.
- `RoutingClassTableTests`: the gap the doctrine names -- a skill in two routing
  classes, in none, named in the table but absent from the catalog, or filed
  under a manifest role it is not declared in.
- `EntryRoutingConsistencyTests`: a skill the table calls internal that never
  states how it is entered, or one the table calls standalone that tells its
  reader to hand off first.
"""

import re
import unicodedata
import unittest
from collections import defaultdict
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

    def _load_text(text):
        return _parse(text)
else:
    def _load_text(text):
        return yaml.safe_load(text)


def _load(path):
    return _load_text(path.read_text(encoding="utf-8"))


TEAM = _load(SKILLS / "team-manifest.yaml")
DOCTRINE = (SKILLS / "routing-doctrine.md").read_text(encoding="utf-8")
FRONT_DOOR = TEAM.get("front_door")

_FM = re.compile(r"^---\r?\n(.*?)\r?\n---", re.S)


def _catalog():
    """name -> (relative directory, SKILL.md text, description)."""
    found = {}
    for md in sorted(SKILLS.rglob("SKILL.md")):
        text = md.read_text(encoding="utf-8")
        match = _FM.match(text)
        if not match:
            continue
        front = _load_text(match.group(1))
        if not isinstance(front, dict) or not front.get("name"):
            continue
        found[front["name"]] = (
            md.parent.relative_to(SKILLS).as_posix(),
            text,
            str(front.get("description", "")),
        )
    return found


CATALOG = _catalog()
DIRS = {name: entry[0] for name, entry in CATALOG.items()}
BODY = {name: entry[1] for name, entry in CATALOG.items()}
DESCRIPTION = {name: entry[2] for name, entry in CATALOG.items()}


# --------------------------------------------------------------------------
# Phrase extraction
# --------------------------------------------------------------------------

#: Typographic characters the catalog uses that would otherwise split a phrase
#: differently depending on which skill's author typed it. The em dash becomes a
#: free-standing ` - ` because it is the catalog's clause separator: every
#: description ends its trigger list with ` - even when ...`.
_SMART = (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"),
          ("—", " - "), ("–", " - "))


def _flatten(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text))
    for src, dst in _SMART:
        text = text.replace(src, dst)
    return text


def _normalise(phrase: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace.

    Hyphens go too. `pressure-test this project` and `pressure test this
    project` are the same claim on the same words, and a comparator that told
    them apart would miss the collision that a reader sees immediately.
    """
    phrase = _flatten(phrase).lower()
    phrase = re.sub(r"[^a-z0-9]+", " ", phrase)
    return re.sub(r"\s+", " ", phrase).strip()


#: The connector between `Use when` and the first real clause. It is not part of
#: any trigger: leaving it attached turns every clause list into one long phrase
#: beginning `the user asks to`, which then collides with nothing and hides
#: every real collision behind it.
_LEADIN = re.compile(
    r"^(?:the user (?:asks|says)(?:\s+for|\s+to)?"
    r"|asked to"
    r"|a user (?:explicitly )?asks(?:\s+to|\s+for)?)\s+", re.I)

_USE_CLAUSE = re.compile(r"\bUse (?:to|when|for)\b", re.I)

#: A clause list runs to the ` - even when ...` aside, to the next sentence, or
#: to the end. Stopping there is what keeps the trailing `Defers X to Y`
#: sentence -- which names a sibling skill and is the opposite of a claim --
#: out of the phrase set.
_CLAUSE_END = re.compile(r"\s-\s|(?<=[a-z])\.\s+[A-Z]|\.$")

#: A trigger has to be specific enough that claiming it means something. Two
#: words is ordinary English (`this diff`, `the build`); three is a phrasing.
MIN_TRIGGER_WORDS = 3


def _claimed_phrases(description: str) -> set:
    """Trigger phrases a description claims.

    Two sources, both of which a model reads as "say this and you want me":
    the comma-separated clauses following `Use to` / `Use when` / `Use for`,
    and any phrase the description quotes.
    """
    flat = _flatten(description)
    raw = []
    for match in _USE_CLAUSE.finditer(flat):
        tail = _CLAUSE_END.split(flat[match.end():])[0]
        raw += re.split(r",|\bor\b", _LEADIN.sub("", tail.strip()))
    raw += re.findall(r'"([^"]{3,120})"', flat)

    phrases = set()
    for piece in raw:
        piece = re.sub(r"^\s*(?:or|and)\s+", "", piece.strip().lower())
        phrase = _normalise(_LEADIN.sub("", piece))
        if len(phrase.split()) >= MIN_TRIGGER_WORDS:
            phrases.add(phrase)
    return phrases


CLAIMS = defaultdict(set)
for _name, _description in DESCRIPTION.items():
    for _phrase in _claimed_phrases(_description):
        CLAIMS[_phrase].add(_name)


# --------------------------------------------------------------------------
# Routing-class table
# --------------------------------------------------------------------------

def _routing_rows():
    """(class label, skills cell) for every row of the routing-class table."""
    section = re.search(r"^## Routing classes\s*$(.*?)(?=^## )", DOCTRINE, re.S | re.M)
    if section is None:
        return []
    rows = []
    for line in section.group(1).splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] == "Routing class" or set(cells[0]) <= set("- "):
            continue
        rows.append((cells[0], cells[1]))
    return rows


def _routing_classes():
    """class label -> set of skill names, resolving the cell's three shorthands.

    The cell is written to be mechanically comparable, but it is prose: a bare
    name, a directory glob (`safety-guardrails/*`), a path that disambiguates a
    name (`taste/taste-review`), a manifest role in parentheses, `except
    `ship``, and `not named in a row above`. A backticked token that is a
    key of team-manifest.yaml is a role annotation, never a skill, which is why
    the two are told apart against the manifest rather than by a hand-kept list.
    """
    labels = set(TEAM)
    assigned, per_class = {}, {}
    for label, cell in _routing_rows():
        excepted = set(re.findall(r"\bexcept\s+`([^`]+)`", cell))
        tokens = re.findall(r"`([^`]+)`", re.sub(r"\bexcept\s+`[^`]+`", " ", cell))
        members = set()
        for token in tokens:
            if token in labels:
                continue
            if token.endswith("/*") or token.endswith("/"):
                prefix = token.rstrip("*").rstrip("/")
                members |= {n for n, d in DIRS.items()
                            if d == prefix or d.startswith(prefix + "/")}
            elif "/" in token:
                members |= {n for n, d in DIRS.items() if d == token}
            elif token in DIRS:
                members.add(token)
        if "not named in a row above" in cell:
            members -= set(assigned)
        members -= excepted
        per_class[label] = members
        for member in members:
            assigned.setdefault(member, []).append(label)
    return per_class, assigned


ROUTING_CLASSES, ROUTING_ASSIGNMENT = _routing_classes()
CLASS_OF = {name: label
            for label, members in ROUTING_CLASSES.items() for name in members}

#: Classes the table says are reached without a prior handoff. These are the
#: skills a description actually routes; an internal specialist or a gatekeeper
#: is reached because its owner names it, which `test_catalog_contracts.py`
#: already checks through `StageDelegationTests`.
DIRECTLY_REACHABLE = {"Entry orchestrator", "Pipeline owners (must defer)",
                      "Dual-mode entry", "Session memory", "Standalone tools"}


class TriggerCollisionTests(unittest.TestCase):
    """No phrase is advertised by two skills.

    A description is the only thing consulted before a skill is chosen, so two
    skills claiming one phrase makes that phrase a coin flip. Five raw
    collisions existed when this comparator was written; four were the front
    door claiming a lifecycle trigger alongside the pipeline owner it fronts,
    which the doctrine requires, and the fifth -- `optimize the description`,
    held by `skill-maker` and by the internal `skill-creator` it delegates to --
    was a real routing defect and was removed from the specialist.
    """

    def _collisions(self):
        """Phrase -> claimants, after the front door is set aside.

        `routing-doctrine.md` makes `admiral` the single entry for lifecycle
        work and requires every pipeline owner to hand off to it when reached
        cold. Its description therefore restates the owners' triggers on
        purpose, and flagging that would be flagging the design. The exemption
        is subtraction, not a skip: three skills claiming a phrase are still a
        collision between the two that are not the front door.
        """
        collisions = {}
        for phrase, owners in CLAIMS.items():
            rest = owners - {FRONT_DOOR}
            if len(rest) > 1:
                collisions[phrase] = rest
        return collisions

    def test_the_scan_found_a_trigger_surface_to_check(self):
        self.assertEqual(len(CATALOG), TEAM["skill_count"],
                         "the catalog scan disagrees with team-manifest.yaml skill_count")
        self.assertGreater(len(CLAIMS), 150,
                           "almost no trigger phrases were extracted - check the parser")

    def test_no_phrase_is_claimed_by_two_skills(self):
        collisions = self._collisions()
        report = [f"'{phrase}' is claimed by {', '.join(sorted(owners))}"
                  for phrase, owners in sorted(collisions.items())]
        self.assertEqual(report, [],
                         "a trigger phrase must resolve to one skill:\n  "
                         + "\n  ".join(report))

    def test_the_front_door_exemption_stays_a_subtraction(self):
        """The exemption may hide a front-door overlap and nothing else."""
        raw = {p: o for p, o in CLAIMS.items() if len(o) > 1}
        for phrase, owners in raw.items():
            if phrase in self._collisions():
                continue
            self.assertIn(FRONT_DOOR, owners,
                          f"'{phrase}' was excused without the front door in it")
            self.assertEqual(len(owners), 2,
                             f"'{phrase}' is claimed by {sorted(owners)}; the exemption "
                             "covers a front-door overlap, not a three-way tie")

    def test_the_extractor_finds_the_phrases_this_audit_found_colliding(self):
        """Guard against an extractor that quietly stops finding anything.

        Each description below is a real one this audit or the last read. If the
        extractor stops pulling the phrase out of them, the collision test above
        becomes decorative, which is the failure mode it exists to prevent.
        """
        for phrase, description in [
            ("review the code",
             "Review sub-orchestrator. Use to run the full review flow, audit this "
             "change before merge, or review the code - even when unscoped."),
            ("optimize the description",
             "Drafts and improves Claude skills. Use when the user asks to write a "
             "skill, optimize the description, or package a skill directory."),
            ("audit responsive behavior",
             "Assesses frontend runtime behavior. Use when the user asks to review "
             "the frontend or audit responsive behavior."),
            ("click through the app and check it",
             'Drives a browser session. Use when the user asks to browse this site '
             '- even when they only say "click through the app and check it".'),
        ]:
            with self.subTest(phrase=phrase, kind="true positive"):
                self.assertIn(phrase, _claimed_phrases(description))

    def test_the_extractor_does_not_claim_these(self):
        """Sentences that name a phrase without the skill claiming it.

        Every one of these was produced by a looser draft of the extractor. They
        are why the clause list stops at the em dash and at the sentence end,
        why the `the user asks to` lead-in is stripped, and why a claim needs
        three words.
        """
        deferral = ("Finds correctness defects. Use when the user asks to find the "
                    "bugs. Deterministic correctness only: exploit chaining goes to "
                    "`review/mr-robot` and tech debt to `review/quality-review`.")
        claimed = _claimed_phrases(deferral)
        for spurious in ("exploit chaining goes to review mr robot",
                         "tech debt to review quality review",
                         "the user asks to find the bugs"):
            with self.subTest(phrase=spurious, kind="false positive"):
                self.assertNotIn(spurious, claimed)
        self.assertIn("find the bugs", claimed,
                      "narrowing must not cost the real claim in the same sentence")

        short = _claimed_phrases("Tunes triggering. Use to fix triggering.")
        self.assertEqual(short, set(),
                         "a two-word clause is ordinary English, not a claimed trigger")


class AdvertisedTriggerTests(unittest.TestCase):
    """A phrasing the body advertises must be reachable from the description.

    `## Use This Skill When` lists the phrasings a user might type. The
    description is what the router reads. A phrasing in the first that has no
    footing in the second is documented for a reader and invisible to the
    router, which is the quietest way for a skill to look reachable and not be.

    Three narrowing passes shaped this rule, and the rejected forms are worth
    stating because each was worse than nothing:

    1. Per quoted phrase over the whole file: 44 of 171 flagged. Most were the
       route-elsewhere prose that every section closes with -- `review/code-chief`
       lists "check this for bugs" precisely to send it to a specialist. Only
       bullets advertise; prose in the section does not.
    2. Per quoted phrase over the bullets: 30 of 167 flagged, but a bullet pairs
       alternate phrasings of ONE trigger with slashes, and reaching any of them
       reaches the trigger. The unit is the bullet.
    3. Per bullet over all 52 skills: 20 of 123 flagged, 17 of them in the six
       skills whose descriptions publish no `Use to/when/for` clause list at all.
       Those six say instead that they are reached through an owner, never
       directly; they are not claiming a user-facing surface, so there is
       nothing for a phrasing to be unreachable from.

    What is left -- a bullet in a skill that does publish a clause list -- flagged
    three, all real: two browser tools whose descriptions had dropped a phrasing
    their bodies still advertised, and one release skill whose body said `real
    environment` where its description says `live environment`.
    """

    #: Function words, plus the numerals a phrasing uses to pick one of several
    #: ("build variant two from the directions"). A numeral carries no routing
    #: signal, and requiring one made a reachable trigger look unreachable.
    STOPWORDS = {
        "a", "an", "the", "this", "that", "it", "is", "are", "to", "of", "in",
        "on", "for", "and", "or", "my", "me", "so", "at", "with", "into", "be",
        "i", "we", "us", "our", "just", "only", "please", "can", "you", "your",
        "do", "does", "s", "t", "don", "what", "how", "all", "way", "from",
        "as", "any", "one", "two", "three", "four", "five", "six", "seven",
        "eight", "nine",
    }

    @staticmethod
    def _stem(word: str) -> str:
        """Crude suffix strip, so `loads` in a description reaches `load`."""
        for suffix in ("ings", "ing", "ies", "es", "ed", "s"):
            if len(word) > len(suffix) + 2 and word.endswith(suffix):
                return word[: -len(suffix)]
        return word

    @classmethod
    def _content(cls, words):
        return [w for w in words if w not in cls.STOPWORDS]

    @staticmethod
    def advertised_bullets(text: str):
        """Quoted phrasings, grouped by the bullet that advertises them."""
        section = re.search(r"^##+\s*Use This Skill When\s*$(.*?)(?=^##\s|\Z)",
                            text, re.S | re.M)
        if section is None:
            return []
        groups = []
        for line in section.group(1).splitlines():
            if not re.match(r"\s*[-*]\s", line):
                continue
            quoted = [_normalise(q)
                      for q in re.findall(r'"([^"]{3,120})"', _flatten(line))]
            quoted = [q for q in quoted if len(q.split()) >= 2]
            if quoted:
                groups.append(quoted)
        return groups

    @classmethod
    def reaches(cls, phrasing: str, description: str):
        """How the description reaches a phrasing, or None.

        Three ways, in descending strength. `verbatim` is the phrasing itself.
        `bag` is every content word of it, stemmed, somewhere in the
        description -- the words are all there, the order is the author's.
        `run` is a contiguous stretch of the phrasing carrying at least two
        content words, which is what "a clear lexical subset" means: a
        description saying `import cookies` reaches `import cookies for browser
        work`. A one-content-word run does not qualify; `the browser` is in
        every browser tool's description and reaches nothing.
        """
        normalised = _normalise(description)
        if phrasing in normalised:
            return "verbatim"
        stems = {cls._stem(w) for w in normalised.split()}
        wanted = [cls._stem(w) for w in cls._content(phrasing.split())]
        if wanted and set(wanted) <= stems:
            return "bag"
        words = phrasing.split()
        padded = f" {normalised} "
        for size in range(len(words), 1, -1):
            for start in range(len(words) - size + 1):
                run = words[start:start + size]
                if len(cls._content(run)) < 2:
                    continue
                if f" {' '.join(run)} " in padded:
                    return "run"
        return None

    @staticmethod
    def _publishes_a_clause_list(description: str) -> bool:
        return _USE_CLAUSE.search(description) is not None

    def _in_scope(self):
        return sorted(n for n in DESCRIPTION
                      if self._publishes_a_clause_list(DESCRIPTION[n]))

    def test_the_scan_found_bullets_to_check(self):
        scope = self._in_scope()
        self.assertGreater(len(scope), 40,
                           "almost no skill publishes a clause list - check the parser")
        bullets = sum(len(self.advertised_bullets(BODY[n])) for n in scope)
        self.assertGreater(bullets, 80,
                           "almost no advertised bullets were found - check the parser")

    def test_every_advertised_bullet_is_reachable_from_the_description(self):
        unreachable = []
        for name in self._in_scope():
            for group in self.advertised_bullets(BODY[name]):
                if any(self.reaches(p, DESCRIPTION[name]) for p in group):
                    continue
                unreachable.append(
                    f"{name} advertises {' / '.join(repr(p) for p in group)} "
                    "but its description carries no part of it")
        self.assertEqual(unreachable, [],
                         "a documented trigger must be reachable from the "
                         "description:\n  " + "\n  ".join(unreachable))

    def test_the_bullet_parser_ignores_route_elsewhere_prose(self):
        """Only a bullet advertises. Prose in the section can say the opposite.

        `review/code-chief` quotes two phrasings in the sentence that routes
        them away from itself. An earlier draft read those as its own triggers
        and reported the skill as broken for documenting a boundary correctly.
        """
        section = (
            "## Use This Skill When\n"
            "\n"
            '- "run the full review flow" / "review this codebase comprehensively"\n'
            "\n"
            'A request for one lens - "check this for bugs", "is this accessible" -\n'
            "goes to that specialist reviewer directly.\n")
        groups = self.advertised_bullets(section)
        self.assertEqual(groups, [["run the full review flow",
                                   "review this codebase comprehensively"]])

    def test_the_matcher_catches_the_defects_it_was_written_for(self):
        """The three descriptions this pass corrected, as they stood before."""
        for phrasing, description in [
            ("set up remote browser access",
             "Pairs a remote collaborator to a browser session with a least-exposing "
             "scoped credential. Use when the user asks to pair another agent, share "
             "a browser session safely, issue pairing access, or hand a live browser "
             "to another operator."),
            ("work in the browser directly",
             "Launches a visible browser workspace for guided interaction. Use when "
             "the user asks to open the browser workspace, launch a visible browser, "
             "inspect the page live, or prepare a session for reuse."),
            ("take an approved change all the way into a real environment",
             "Takes one approved revision from merge into a live environment in a "
             "single controlled flow, with a recorded go decision."),
        ]:
            with self.subTest(phrasing=phrasing, kind="true positive"):
                self.assertIsNone(self.reaches(phrasing, description))

    def test_the_matcher_does_not_fire_on_these_known_false_positives(self):
        """Reachable phrasings an earlier, stricter matcher rejected."""
        for phrasing, description, expected in [
            # A contiguous two-content-word subset of the phrasing.
            ("import cookies for browser work",
             "Imports a user-owned authenticated session. Use when the user asks to "
             "set up the browser session, import cookies, or prepare authenticated "
             "access.", "run"),
            # The description reaches the subject with a different verb.
            ("look for data leakage",
             "Defensive security lens over code. Use when the user asks to review "
             "security or trace data leakage.", "run"),
            # A numeral picks one of several and carries no routing signal.
            ("build variant two from the directions",
             "Builds one redesign variant. Use when `design/redesign` delegates a "
             "variant build, or the user asks for a clickable mock of a design "
             "direction.", "bag"),
            # A hyphen in the description, a space in the phrasing.
            ("run the posture assessment",
             "Runs as the security pipeline's `posture-assessment`. Use when the "
             "user asks to review security.", "bag"),
        ]:
            with self.subTest(phrasing=phrasing, kind="false positive"):
                self.assertEqual(self.reaches(phrasing, description), expected)

    def test_a_one_content_word_run_does_not_count_as_reaching(self):
        """`the browser` is in every browser tool and distinguishes none."""
        self.assertIsNone(self.reaches(
            "work in the browser directly",
            "Launches a visible browser workspace. Use when the user asks to open "
            "the browser workspace."))


class TriggerReachabilityTests(unittest.TestCase):
    """Every skill is describable, and every routed skill is reachable.

    A description that is empty, or that holds no phrase of its own, cannot be
    chosen over its siblings. The rule is scoped to the classes the routing
    table says are entered directly: an internal specialist is reached because
    its owner names it, and six of them deliberately publish no user-facing
    phrasing at all so that a user's wording cannot land on them.
    """

    #: Claude's skill descriptions describe the skill, not the reader. A
    #: description that slips into first or second person reads as instructions
    #: to the user and stops working as a routing sentence. Quoted user
    #: phrasings are exempt -- "remember that I prefer" is what the user says.
    PERSON = re.compile(r"\b(I|we|our|us|my|you|your|yours)\b")

    def test_every_description_is_non_empty(self):
        empty = sorted(n for n, d in DESCRIPTION.items() if not d.strip())
        self.assertEqual(empty, [], "every skill needs a description: " + ", ".join(empty))

    def test_every_description_is_third_person(self):
        offenders = []
        for name, description in sorted(DESCRIPTION.items()):
            outside_quotes = re.sub(r'"[^"]*"', " ", _flatten(description))
            hits = sorted(set(self.PERSON.findall(outside_quotes)))
            if hits:
                offenders.append(f"{name} addresses the reader with {', '.join(hits)}")
        self.assertEqual(offenders, [],
                         "a description describes the skill, not the reader:\n  "
                         + "\n  ".join(offenders))

    def test_the_person_detector_works(self):
        bad = "You can use this to review your code, and I will report what we find."
        self.assertTrue(self.PERSON.search(bad))
        quoted = ('Owns the preference lifecycle. Use when a user asks to remember '
                  'a preference - "remember that I prefer dark mode".')
        self.assertFalse(self.PERSON.search(re.sub(r'"[^"]*"', " ", _flatten(quoted))),
                         "a quoted user phrasing is the user's voice, not the skill's")

    def test_every_directly_reachable_skill_owns_a_phrase(self):
        direct = sorted(n for n in DESCRIPTION
                        if CLASS_OF.get(n) in DIRECTLY_REACHABLE)
        self.assertGreater(len(direct), 20,
                           "the routing table yielded almost no direct entries")
        unreachable = []
        for name in direct:
            sole = {p for p in _claimed_phrases(DESCRIPTION[name])
                    if CLAIMS[p] == {name}}
            if not sole:
                unreachable.append(
                    f"{name} ({CLASS_OF[name]}) claims no phrase of its own")
        self.assertEqual(unreachable, [],
                         "a directly entered skill needs a phrase no sibling "
                         "claims:\n  " + "\n  ".join(unreachable))

    def test_every_skill_is_reachable_by_phrase_or_by_owner(self):
        """A skill with no phrase must be one an owner reaches by name.

        `test_catalog_contracts.py` already asserts that a pipeline owner names
        each of its stage owners, so being named there is a real entry path.
        This asserts the disjunction: a skill has a phrase, or it sits in a
        class the table says is entered through an owner.
        """
        by_owner = set(ROUTING_CLASSES) - DIRECTLY_REACHABLE
        stranded = []
        for name in sorted(DESCRIPTION):
            if _claimed_phrases(DESCRIPTION[name]):
                continue
            if CLASS_OF.get(name) in by_owner:
                continue
            stranded.append(f"{name} claims no trigger phrase and is not entered "
                            f"through an owner (class: {CLASS_OF.get(name)})")
        self.assertEqual(stranded, [], "\n  ".join(stranded))


class RoutingClassTableTests(unittest.TestCase):
    """The routing-class table partitions the catalog.

    `routing-doctrine.md` states that every skill falls in exactly one row, and
    its own enforcement table records that nothing checked it. A skill in no row
    has no stated entry rule; a skill in two has two contradictory ones; a
    pipeline owner filed under internal specialists is the specific error the
    doctrine says was last caught by hand.
    """

    def test_the_table_parses(self):
        rows = _routing_rows()
        self.assertGreater(len(rows), 5,
                           "the routing-class table did not parse - check the heading")
        self.assertIn("Every skill in the catalog falls in exactly one row.", DOCTRINE,
                      "the doctrine must still claim the partition this test checks")

    def test_every_skill_is_in_exactly_one_class(self):
        duplicated = [f"{name} is in {', '.join(labels)}"
                      for name, labels in sorted(ROUTING_ASSIGNMENT.items())
                      if len(labels) > 1]
        self.assertEqual(duplicated, [],
                         "a skill has one entry rule:\n  " + "\n  ".join(duplicated))
        unfiled = sorted(set(DIRS) - set(ROUTING_ASSIGNMENT))
        self.assertEqual(unfiled, [],
                         "every skill needs a routing class: " + ", ".join(unfiled))

    def test_the_classes_sum_to_the_declared_roster(self):
        total = sum(len(members) for members in ROUTING_CLASSES.values())
        self.assertEqual(total, TEAM["skill_count"],
                         f"the routing classes cover {total} skills; "
                         f"team-manifest.yaml declares {TEAM['skill_count']}")
        self.assertEqual(total, len(DIRS),
                         "the routing classes disagree with the SKILL.md count on disk")

    def test_every_name_in_the_table_exists(self):
        labels = set(TEAM)
        missing = []
        for label, cell in _routing_rows():
            for token in re.findall(r"`([^`]+)`", cell):
                if token in labels or token.endswith(("/*", "/")):
                    continue
                if "/" in token:
                    if not any(d == token for d in DIRS.values()):
                        missing.append(f"{label} names '{token}', which is not a skill path")
                elif token not in DIRS:
                    missing.append(f"{label} names '{token}', which is not a skill")
        self.assertEqual(missing, [], "\n  ".join(missing))

    def test_the_named_rows_win_over_the_directory_globs(self):
        """The doctrine calls out two deliberate overlaps; both must resolve.

        `review/cso` owns the security pipeline and `ship`
        owns the release pipeline, so each belongs to its named row rather than
        to the glob that would otherwise swallow it. This is the assertion that
        a parser change cannot quietly reverse.
        """
        self.assertEqual(CLASS_OF.get("cso"), "Pipeline owners (must defer)")
        self.assertEqual(CLASS_OF.get("ship"), "Dual-mode entry")
        self.assertEqual(CLASS_OF.get("qa-only"), "Dual-mode entry")
        self.assertEqual(CLASS_OF.get("benchmark"), "Standalone tools")
        self.assertEqual(CLASS_OF.get("taste-review"), "Internal specialists")

    #: The keys the doctrine's Known-gap paragraph names, and the only ones the
    #: completeness half below may use. A row may also annotate a grouping list
    #: (`qa-only` is annotated `testing`), but a grouping is not a partition:
    #: `testing` also holds `qa`, filed under `pipeline_owners`, and
    #: `benchmark`, filed under the standalone glob with no annotation at all.
    #: team-manifest.yaml says so itself under `authority.grouping` -- only the
    #: union of the groups is checked, and which group a name sits in is
    #: documentation. Requiring a grouping to be covered row by row would fail
    #: on a correct table, which is worse than not checking it.
    ROLE_KEYS = ("front_door", "phase_leads", "pipeline_owners",
                 "cross_stage_gatekeeper", "phase_gatekeepers")

    def test_each_row_files_its_skills_under_a_role_they_hold(self):
        """The gap the doctrine names, closed.

        Each segment of a Skills cell ends in the manifest key the names before
        it are declared under. Comparing them is what makes "a pipeline owner
        filed as an internal specialist" mechanical rather than a review item.
        The first half checks every annotation: a name filed under a key must be
        declared under it. The second checks the five routing roles for
        completeness: a role holder the table never files under its own role has
        no stated entry rule for the role it holds.
        """
        labels = set(TEAM)
        checked, wrong = 0, []
        claimed_by_key = defaultdict(set)
        for label, cell in _routing_rows():
            for segment in cell.split(";"):
                key = re.search(r"\(`([^`]+)`\)\s*$", segment.strip())
                if not key or key.group(1) not in labels:
                    continue
                role = key.group(1)
                declared = TEAM[role]
                declared = [declared] if isinstance(declared, str) else list(declared)
                named = [t for t in re.findall(r"`([^`]+)`", segment)
                         if t != role and t in DIRS]
                self.assertTrue(named, f"{label} segment names no skill: {segment!r}")
                checked += 1
                claimed_by_key[role] |= set(named)
                for name in named:
                    if name not in declared:
                        wrong.append(f"{label} files '{name}' under '{role}', "
                                     f"which declares {declared}")
        self.assertGreater(checked, 5, "almost no role annotations parsed")
        self.assertEqual(wrong, [],
                         "the table must file a skill under a role it holds:\n  "
                         + "\n  ".join(wrong))

        dropped = []
        for role in self.ROLE_KEYS:
            declared = TEAM[role]
            declared = {declared} if isinstance(declared, str) else set(declared)
            for missing in sorted(declared - claimed_by_key.get(role, set())):
                dropped.append(f"'{missing}' is declared under '{role}' but the "
                               "table files it under no row annotated with that role")
        self.assertEqual(dropped, [],
                         "every holder of a routing role must appear in a row "
                         "annotated with it:\n  " + "\n  ".join(dropped))


class EntryRoutingConsistencyTests(unittest.TestCase):
    """A skill's own text must agree with the class the table puts it in.

    The two directions fail differently. An internal specialist that never
    states how it is entered leaves the loop guard -- which the doctrine says
    works only because every in-scope skill carries it -- to the reader's
    memory. A standalone tool that tells its reader to hand off first
    contradicts the row that makes it reachable at any time, and the reader who
    believes the skill will decline a direct request.
    """

    ENTRY_ROUTING = re.compile(r"^##+\s*Entry Routing\s*$", re.M)

    #: Sentences asserting this skill may not be entered directly. Deliberately
    #: narrow. The bare word `handoff` is not one of these: a standalone tool
    #: legitimately writes "owner handoff notes" and "session handoff
    #: instructions", and an earlier draft keying on the word flagged four
    #: browser and safety tools for saying so.
    NEEDS_HANDOFF = re.compile(
        r"\bnot directly\b"
        r"|\breached only through\b"
        r"|\bonly through the owning\b"
        r"|\broute to `?admiral`?(?: first)?"
        r"|\bhand off to `?admiral`?(?: first)?"
        r"|\bdefers? to `?admiral`? when reached cold\b"
        r"|\bstart `?admiral`? first\b"
        r"|\brequires? an active handoff\b"
        r"|\breached cold, (?:route|hand)\b", re.I)

    def test_the_classes_this_checks_are_populated(self):
        self.assertGreater(len(ROUTING_CLASSES.get("Internal specialists", ())), 15)
        self.assertGreater(len(ROUTING_CLASSES.get("Standalone tools", ())), 8)

    def test_every_internal_specialist_states_its_entry_routing(self):
        missing = sorted(name for name in ROUTING_CLASSES["Internal specialists"]
                         if not self.ENTRY_ROUTING.search(BODY[name]))
        self.assertEqual(missing, [],
                         "a skill reached only through an owner must say so under "
                         "`## Entry Routing`: " + ", ".join(missing))

    def test_no_standalone_tool_claims_to_require_a_handoff(self):
        contradictions = []
        for name in sorted(ROUTING_CLASSES["Standalone tools"]):
            for match in self.NEEDS_HANDOFF.finditer(BODY[name]):
                contradictions.append(
                    f"{name} is a standalone tool but says: ...{match.group(0)}...")
        self.assertEqual(contradictions, [],
                         "a standalone tool is reachable at any time:\n  "
                         + "\n  ".join(contradictions))

    def test_the_handoff_detector_catches_the_sentences_it_is_for(self):
        """Real sentences from skills the table classes as needing a handoff."""
        for sentence in [
            "Internal build specialist reached through `build/build-management`, "
            "not directly, even when the request is only \"add some tests\".",
            "Build-phase gatekeeper for the `build-to-review` boundary, invoked by "
            "`build/build-management`; reached cold, route to `admiral` first.",
            "Defers to `admiral` when reached cold; reviewing the finished code "
            "belongs to `review/code-chief`.",
        ]:
            with self.subTest(kind="true positive"):
                self.assertTrue(self.NEEDS_HANDOFF.search(sentence))

    def test_the_handoff_detector_does_not_fire_on_these(self):
        """Real sentences from standalone tools, including two with a Save Context
        pipeline mode. Describing a pipeline mode is not claiming a handoff is
        required, and naming `admiral` as somewhere else to route is not either.
        """
        for sentence in [
            "`../../routing-doctrine.md` classes this skill a standalone tool, "
            "invokable directly at any time.",
            "`../../routing-doctrine.md` classes this skill as directly invokable, "
            "and `../../pipelines.yaml` also runs it as the `document` stage.",
            "Return a freeze record with release conditions, owner handoff notes, "
            "and the next safe work that can continue outside the boundary.",
            "If the release needs the gate's assurance, stop and route it through "
            "`ship` under `admiral` instead.",
            "Route the handoff to `pair-agent`, which issues a "
            "scoped credential and owns the revocation.",
        ]:
            with self.subTest(kind="false positive"):
                self.assertIsNone(self.NEEDS_HANDOFF.search(sentence))



class DescriptionPathTests(unittest.TestCase):
    """A skill path inside a description has to resolve.

    Descriptions are folded YAML block scalars. Folding rejoins wrapped lines
    with a space, so a path broken across lines comes back as
    `release-and- deployment/ship` — a skill that does not exist, inside the one
    field the router reads, in a sentence whose whole job is to send the reader
    somewhere else.

    Four descriptions carried exactly this and every existing check passed them:
    the collision and reachability tests normalise hyphens away before comparing,
    so the corruption was invisible to the surface that would otherwise have
    caught it. Nothing resolved the paths against the catalog until now.
    """

    #: A backticked token containing a slash, i.e. something shaped like a skill
    #: path rather than a word. Files are excluded: a description may legitimately
    #: cite `gates.yaml` or `../save-protocol.md`.
    PATHISH = re.compile(r"`([a-z0-9][A-Za-z0-9_-]*(?:/[A-Za-z0-9_.-]+)+)`")

    def test_every_skill_path_named_in_a_description_exists(self):
        known = {p.parent.relative_to(SKILLS).as_posix() for p in SKILLS.rglob("SKILL.md")}
        self.assertGreater(len(known), 40, "no skills discovered - the check would pass vacuously")

        broken = []
        for name, description in DESCRIPTION.items():
            for match in self.PATHISH.finditer(description):
                ref = match.group(1)
                if ref.endswith((".md", ".yaml", ".yml", ".py", ".json")):
                    continue
                if ref not in known:
                    broken.append(f"{name} names `{ref}`, which is not a skill")
        self.assertEqual([], broken, "\n  ".join(broken))

    def test_no_description_carries_a_fold_split_token(self):
        """The corruption's signature, independent of whether it resolves.

        `a- b` inside backticks is a token the folder broke; catching the shape
        as well as the broken reference means a split that happens to land on a
        real name still fails.
        """
        split = [f"{name}: {m.group(0)}"
                 for name, description in DESCRIPTION.items()
                 for m in re.finditer(r"`[A-Za-z0-9_/-]+- [A-Za-z0-9_/-]+`", description)]
        self.assertEqual([], split, "\n  ".join(split))


class AdvertisedCorpusTests(unittest.TestCase):
    """No two skills advertise the same bullet.

    `TriggerCollisionTests` compares what the *descriptions* claim. The
    behavioural eval builds its corpus from what the `## Use This Skill When`
    bullets *advertise*. Those are different surfaces, and a duplicate that lives
    only in the second one is invisible to the first: `build/debugger` and
    `investigate` both advertised "find the root cause" verbatim while the
    collision test stayed green.

    A duplicate here is worse than a description overlap, because the eval cannot
    score it at all — whichever skill the router picks, one of the two is marked
    wrong for a phrase both were told to claim.
    """

    @staticmethod
    def _advertised():
        """Bullet phrases per skill, quoted or bare, as the eval extracts them."""
        found = {}
        for skill in sorted(SKILLS.rglob("SKILL.md")):
            text = skill.read_text(encoding="utf-8", errors="replace")
            section = re.search(r"^## Use This Skill When\s*$(.*?)^## ", text, re.M | re.S)
            if not section:
                continue
            phrases = []
            for line in section.group(1).splitlines():
                line = line.strip()
                if not line.startswith("- "):
                    continue
                body = line[2:]
                quoted = re.findall(r'"([^"]{4,90})"', body)
                if quoted:
                    phrases.extend(quoted)
                else:
                    body = re.sub(r"\s+[\u2014-]\s+.*$", "", body)
                    phrases.append(re.sub(r"[`*]", "", body).strip(" ."))
            found[skill.parent.relative_to(SKILLS).as_posix()] = phrases
        return found

    def test_the_scan_found_bullets_to_check(self):
        total = sum(len(v) for v in self._advertised().values())
        self.assertGreater(total, 150, f"only {total} advertised phrases found; the extractor broke")

    def test_every_skill_advertises_at_least_four_triggers(self):
        thin = [f"{name} advertises {len(p)}" for name, p in self._advertised().items() if len(p) < 4]
        self.assertEqual([], thin, "\n  ".join(thin))

    def test_no_phrase_is_advertised_by_two_skills(self):
        claims = {}
        for name, phrases in self._advertised().items():
            for phrase in phrases:
                key = " ".join(phrase.lower().split())
                if len(key.split()) >= 3:
                    claims.setdefault(key, set()).add(name)
        clashes = [f"{phrase!r} advertised by {sorted(owners)}"
                   for phrase, owners in sorted(claims.items()) if len(owners) > 1]
        self.assertEqual([], clashes, "\n  ".join(clashes))



class HostRegistrationTests(unittest.TestCase):
    """What the loader can see, stated as arithmetic rather than belief.

    Claude Code discovers skills at `.claude/skills/<name>/SKILL.md`, one level
    deep. A skill nested below that is reachable only by an owner reading it.
    `routing-doctrine.md` once called fifteen nested skills "invokable directly
    at any time"; installing the catalog and asking the host what it registered
    showed it registers five. The doctrine now states the split explicitly, and
    these tests keep its numbers true.

    The measurement itself lives in `validation/run_eval.py --registration`,
    which needs a live host and so cannot run here. What runs here is the part
    that can: the tree shape the measurement depends on.
    """

    @staticmethod
    def _by_depth():
        top, nested = [], []
        for skill in sorted(SKILLS.rglob("SKILL.md")):
            rel = skill.parent.relative_to(SKILLS).as_posix()
            (top if "/" not in rel else nested).append(rel)
        return top, nested

    def test_the_doctrine_states_the_registration_split_it_has(self):
        """The doctrine must state how many skills are nested, in any wording.

        An earlier version of this test demanded one exact sentence, which made
        it a template check rather than a fact check: rewriting the prose around
        the same true number failed it. What matters is that the count a reader
        finds matches the tree, not that it is phrased the way the test's author
        happened to phrase it.
        """
        top, nested = self._by_depth()
        doctrine = (SKILLS / "routing-doctrine.md").read_text(encoding="utf-8", errors="replace")
        numbers = set(re.findall(r"\b(\d{1,3})\b", doctrine))
        self.assertIn(str(len(nested)), numbers,
                      f"{len(nested)} skills are nested below the loader's depth and "
                      "routing-doctrine.md states no such number")
        self.assertIn(str(len(top) + len(nested)), numbers,
                      f"the catalog holds {len(top) + len(nested)} skills and "
                      "routing-doctrine.md states no such total")

    def test_the_doctrine_does_not_promise_unqualified_direct_invocation(self):
        """A nested skill cannot be invoked by name, so nothing may say it can.

        Scoped to the sentence, not the file: the doctrine legitimately uses the
        word elsewhere, including in the corrected row that qualifies it.
        """
        doctrine = (SKILLS / "routing-doctrine.md").read_text(encoding="utf-8", errors="replace")
        offenders = [" ".join(line.split())[:120]
                     for line in doctrine.splitlines()
                     if "invokable directly at any time" in line
                     or "Directly invokable as tools" in line and "register" not in line]
        self.assertEqual([], offenders,
                         "these promise direct invocation without naming the host "
                         "registration it depends on:\n  " + "\n  ".join(offenders))

    def test_top_level_skills_are_the_ones_the_doctrine_names_as_entry_points(self):
        """Every top-level directory should be something meant to be entered.

        The loader will offer exactly these by name, so a specialist accidentally
        promoted to the top level becomes a front door nobody intended.
        """
        top, _ = self._by_depth()
        doctrine = (SKILLS / "routing-doctrine.md").read_text(encoding="utf-8", errors="replace")
        unexplained = [name for name in top if f"`{name}`" not in doctrine]
        self.assertEqual([], unexplained,
                         "top-level skills the host will offer by name, which "
                         "routing-doctrine.md never mentions: " + ", ".join(unexplained))


if __name__ == "__main__":
    unittest.main()
