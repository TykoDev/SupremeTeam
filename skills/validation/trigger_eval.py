#!/usr/bin/env python3
"""Behavioural trigger eval: does the right skill win, out of all 52?

Every other check in this catalog is structural. This one is not: it asks a real
model to route a real request against the real roster, and scores whether the
skill that should have won did.

Why a catalog-level eval rather than the per-skill one in
``skill-maker/skill-creator/scripts/run_eval.py``: that harness registers a
single skill and asks whether it fires. A skill can fire correctly in isolation
and still be wrong in the catalog, because another skill's description claims the
same phrasing. Discrimination is the property that matters once there are 52 of
them, and it is only visible when all 52 compete for the same request.

The corpus is not invented — it is taken from the catalog, in three forms of
increasing difficulty, because the easy forms flatter the result:

``advertised``
    Each skill's own ``## Use This Skill When`` phrasings. A miss means a skill's
    advertised trigger does not reach it. This is the weakest form: the winning
    description usually contains the query's words, so the match is nearly free,
    and a perfect score here says little.

``routed``
    Phrases lifted from a *sibling's* "Route elsewhere" sentence, where the
    catalog itself declares which skill should win. Adversarial by construction —
    these are the cases an over-broad description swallows — but still written in
    the catalog's vocabulary.

``--paraphrase``
    Either corpus, restated by a model as a developer would actually type it,
    with the catalog's distinctive terms removed ("audit this diff" becomes "look
    over what i changed before i commit"). This is the only form that measures
    more than lexical echo, and the only one whose score is worth quoting.

A paraphrase can drift far enough that a miss is the rewrite's fault rather than
the description's, so every result keeps both the original trigger and the text
actually asked, and misroutes print both for adjudication.

This is deliberately NOT a unittest: it costs money and needs network. Run it
when the trigger surface changes.

    python skills/validation/trigger_eval.py --pilot              # one batch, to price it
    python skills/validation/trigger_eval.py --mode both --paraphrase --out report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.exit("PyYAML is required: pip install pyyaml")

SKILLS = Path(__file__).resolve().parent.parent
REPO = SKILLS.parent

# A bullet either quotes the phrasings it answers to, or is itself the phrasing.
QUOTED = re.compile(r'"([^"]{4,80})"')
# Trailing explanation after an em dash is commentary, not part of the trigger.
EXPLAIN = re.compile(r"\s+[—-]\s+.*$")


def frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


def triggers_for(text: str) -> list[str]:
    """The user phrasings a skill advertises under `## Use This Skill When`."""
    match = re.search(r"^## Use This Skill When\s*$(.*?)^## ", text, re.M | re.S)
    if not match:
        return []
    found: list[str] = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:].strip()
        quoted = QUOTED.findall(body)
        if quoted:
            found.extend(q.strip() for q in quoted)
            continue
        # A bare bullet is the phrasing; drop any trailing gloss and markup.
        body = EXPLAIN.sub("", body)
        body = re.sub(r"[`*]", "", body).strip(" .")
        # Bullets that are prose about routing, not a phrasing a user would type.
        if 2 <= len(body.split()) <= 12 and not body.lower().startswith(("route ", "a request")):
            found.append(body)
    return found


def triggers_from_description(description: str) -> list[str]:
    """Fallback for skills with no `## Use This Skill When` section.

    Five skills advertise their triggers only inside the description, in a
    "Use to X, Y, or Z" clause. Those skills still have to be routable, so the
    corpus takes the clause apart rather than skipping them — a skill absent from
    the corpus would score as neither hit nor miss, which flatters the result.
    """
    match = re.search(r"\bUse (?:to|when|for)\b(.*?)(?:\.\s|$)", description, re.S | re.I)
    if not match:
        return []
    clause = re.sub(r"[`*]", "", match.group(1))
    parts = re.split(r",| or | and (?=\w+ing)", clause)
    out = []
    for part in parts:
        part = EXPLAIN.sub("", part).strip(" .;:—-")
        if 2 <= len(part.split()) <= 12:
            out.append(part)
    return out


def roster() -> dict[str, dict]:
    out = {}
    for path in sorted(SKILLS.rglob("SKILL.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        meta = frontmatter(text)
        name = path.parent.relative_to(SKILLS).as_posix()
        description = str(meta.get("description", "")).strip()
        advertised = triggers_for(text)
        out[name] = {
            "description": description,
            "triggers": advertised or triggers_from_description(description),
            "from_description_only": not advertised,
            "routed": routing_away(text),
        }
    return out


# "Route elsewhere to drive the page once it is open (`browse`)"
ROUTED = re.compile(r"([a-z][^(),]{8,90}?)\s*\(`([a-z0-9][A-Za-z0-9_/-]*)`\)")


def routing_away(text: str) -> list[tuple[str, str]]:
    """Cases the skill itself says belong to a sibling.

    These are the adversarial half of the corpus. A phrase lifted from a
    skill's own "Route elsewhere" sentence is, by construction, adjacent to that
    skill's scope — it is the case a careless description would swallow. The
    catalog declares the right answer, so the eval is not inventing a judgement.
    """
    out = []
    for line in re.findall(r"^Route elsewhere[^\n]*(?:\n(?!\n)[^\n]*)*", text, re.M):
        flat = " ".join(line.split())
        # Drop the stem so the first captured phrase is not left as "oute ...".
        flat = re.sub(r"^Route elsewhere\s*", "", flat)
        for phrase, target in ROUTED.findall(flat):
            phrase = phrase.strip(" ,.;:")
            # A multi-target sentence lists its cases with conjunctions, so the
            # second and third arrive as "or runtime performance" — a fragment
            # with no subject, which is not a request anyone would type. Scoring
            # one as a routing failure blames the catalog for the extractor.
            phrase = re.sub(r"^(?:or|and|nor)\s+", "", phrase, flags=re.I)
            phrase = re.sub(r"^(?:to|for|when|the work is|only if|in)\s+", "", phrase, flags=re.I)
            if 2 <= len(phrase.split()) <= 14:
                out.append((phrase, target))
    return out


ENTRY_ROUTING = re.compile(r"^## Entry Routing\s*$(.*?)^## ", re.M | re.S)
BACKTICKED = re.compile(r"`([a-z][A-Za-z0-9_-]*(?:/[A-Za-z0-9_-]+)?)`")


def delegating_owners(skills: dict) -> dict[str, set[str]]:
    """For each internal specialist, the owner its own Entry Routing names.

    `routing-doctrine.md` makes every nested specialist reachable "only through
    the owning sub-orchestrator". So when a cold request that belongs to a
    specialist arrives, routing it to that owner is not a miss — it is the
    documented path, and the orchestrator delegates from there.

    Scoring it as a miss measured the catalog against ground truth its own
    doctrine contradicts, and six of twenty-seven misroutes were exactly this.
    Credit is granted only to an owner the specialist *itself* names, read out of
    its Entry Routing section, so this cannot quietly excuse an unrelated skill.
    """
    owners: dict[str, set[str]] = {}
    for name in skills:
        if "/" not in name:
            continue  # a top-level skill is an entry point, not a specialist
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8", errors="replace")
        section = ENTRY_ROUTING.search(text)
        if not section:
            continue
        named = set(BACKTICKED.findall(section.group(1)))
        owners[name] = {ref for ref in named if ref in skills and ref != name}
    return owners


def build_corpus(skills: dict, per_skill: int, mode: str) -> list[dict]:
    corpus = []
    if mode in {"advertised", "both"}:
        for name, info in skills.items():
            for trigger in info["triggers"][:per_skill]:
                corpus.append({"query": trigger, "expected": name, "kind": "advertised"})
    if mode in {"routed", "both"}:
        seen = set()
        for name, info in skills.items():
            for phrase, target in info["routed"][:per_skill]:
                if target not in skills or (phrase, target) in seen:
                    continue
                seen.add((phrase, target))
                corpus.append({"query": phrase, "expected": target,
                               "kind": "routed", "adjacent_to": name})
    return corpus


PARAPHRASE_HEAD = """Rewrite each numbered line as a real developer would actually
type it to an assistant, in their own words.

Rules:
- Keep the underlying intent identical.
- Do NOT reuse the distinctive nouns and verbs of the original. Say what someone
  wants, not what the tool is called. ("verify parity as gate evidence" becomes
  something like "make sure the build still matches the mockups".)
- Write it casually, the way a request is typed mid-task: lowercase is fine,
  fragments are fine, no jargon the original supplied.
- One rewrite per line, same numbering, nothing else.

Lines:

"""

PROMPT_HEAD = """You are routing incoming requests to exactly one skill from a catalog.

Below is the full catalog: each entry is a skill id followed by its description.
After it is a numbered list of user requests. For each request, name the single
skill id that should handle it.

Answer with one line per request, formatted exactly as:
<number>. <skill id>

No other text. Use a skill id exactly as spelled in the catalog.

## Catalog

"""


def _claude(prompt: str, model: str | None, timeout: int) -> tuple[str, float]:
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    # CLAUDECODE is a guard against interactive nesting; a subprocess call is safe.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(REPO), env=env, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[:400]}")
    payload = json.loads(proc.stdout)
    return payload.get("result") or "", float(payload.get("total_cost_usd") or 0.0)


def paraphrase(batch: list[dict], model: str | None, timeout: int) -> tuple[list[str], float]:
    """Restate each query in a user's own words, stripped of catalog vocabulary.

    Routing a skill's own advertised phrase back at it measures lexical echo: the
    winning description contains the words of the query, so the match is nearly
    free. The question that decides whether a catalog works is whether the right
    skill still wins when the user does not happen to use its words — which is
    the normal case, not the edge case.

    A query that fails to paraphrase falls back to its original text, so a
    partial rewrite degrades the difficulty of the run rather than dropping
    rows and flattering the score.
    """
    lines = "\n".join(f"{i}. {item['query']}" for i, item in enumerate(batch, 1))
    body, cost = _claude(PARAPHRASE_HEAD + lines + "\n", model, timeout)
    out = [item["query"] for item in batch]
    for line in body.splitlines():
        hit = re.match(r"\s*(\d+)\.\s*(.+)", line)
        if hit:
            index = int(hit.group(1)) - 1
            if 0 <= index < len(out):
                out[index] = hit.group(2).strip()
    return out, cost


def ask(batch: list[dict], skills: dict, model: str | None, timeout: int,
        asked: list[str] | None = None) -> tuple[dict[int, str], float]:
    catalog = "\n".join(f"- {name}: {info['description']}" for name, info in skills.items())
    texts = asked if asked is not None else [item["query"] for item in batch]
    queries = "\n".join(f"{i}. {text}" for i, text in enumerate(texts, 1))
    prompt = f"{PROMPT_HEAD}{catalog}\n\n## Requests\n\n{queries}\n"
    body, cost = _claude(prompt, model, timeout)

    answers: dict[int, str] = {}
    for line in body.splitlines():
        hit = re.match(r"\s*(\d+)\.\s*([A-Za-z0-9_./-]+)", line)
        if hit:
            answers[int(hit.group(1))] = hit.group(2).strip()
    return answers, cost


def main() -> int:
    # Paraphrases are written by a model and can contain any character; the
    # default Windows console encoding cannot represent most of them, and a
    # print that raises would otherwise discard a completed run.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover - exotic stdout
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-skill", type=int, default=2, help="queries drawn per skill")
    ap.add_argument("--batch", type=int, default=15, help="queries per model call")
    ap.add_argument("--model", default=None)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--mode", choices=("advertised", "routed", "both"), default="both",
                    help="advertised = each skill's own trigger phrases; "
                         "routed = phrases a sibling says belong elsewhere (adversarial)")
    ap.add_argument("--paraphrase", action="store_true",
                    help="restate each query in a user's own words before routing it; "
                         "the only mode that measures more than lexical echo")
    ap.add_argument("--pilot", action="store_true", help="run one batch only, to price the full run")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    skills = roster()
    missing = [n for n, i in skills.items() if not i["triggers"]]
    no_section = [n for n, i in skills.items() if i["from_description_only"]]
    corpus = build_corpus(skills, args.per_skill, args.mode)
    print(f"roster {len(skills)} skills | corpus {len(corpus)} queries "
          f"| no `Use This Skill When` section: {len(no_section)}"
          f" | no trigger at all: {len(missing)}")
    for name in no_section:
        print(f"    triggers taken from the description only: {name}")
    for name in missing:
        print(f"    NO TRIGGER FOUND, absent from the corpus: {name}")

    batches = [corpus[i:i + args.batch] for i in range(0, len(corpus), args.batch)]
    if args.pilot:
        batches = batches[:1]
        print(f"pilot: 1 batch of {len(batches[0])}")

    owners = delegating_owners(skills)
    results, cost_total = [], 0.0
    for index, batch in enumerate(batches, 1):
        asked = None
        try:
            if args.paraphrase:
                asked, cost = paraphrase(batch, args.model, args.timeout)
                cost_total += cost
            answers, cost = ask(batch, skills, args.model, args.timeout, asked)
        except Exception as exc:  # a failed batch must not discard the rest
            print(f"  batch {index}/{len(batches)}: FAILED ({exc})", flush=True)
            for item in batch:
                results.append({**item, "actual": None, "correct": False, "error": str(exc)[:120]})
            continue
        cost_total += cost
        hits = 0
        for position, item in enumerate(batch, 1):
            actual = answers.get(position)
            expected = item["expected"]
            correct = actual == expected
            via_owner = False
            if not correct and actual in owners.get(expected, set()):
                # The specialist's own declared route in. Counted, and marked,
                # so the report never hides how a hit was earned.
                correct = via_owner = True
            item = {**item, "via_owner": via_owner} if via_owner else item
            hits += correct
            if asked:
                item = {**item, "asked": asked[position - 1]}
            results.append({**item, "actual": actual, "correct": correct})
        print(f"  batch {index}/{len(batches)}: {hits}/{len(batch)} correct  (${cost:.2f})", flush=True)

    scored = [r for r in results if "error" not in r]
    correct = sum(1 for r in scored if r["correct"])

    # Persist before printing. A run costs real money and twenty minutes; the
    # first full paraphrase run computed its results and then lost all of them to
    # a UnicodeEncodeError in the misroute printer, because a model-written
    # paraphrase contained an arrow and Windows stdout is cp1252 by default.
    if args.out:
        args.out.write_text(json.dumps(
            {"accuracy": correct / max(len(scored), 1), "cost_usd": round(cost_total, 4),
             "mode": args.mode, "paraphrased": bool(args.paraphrase),
             "results": results}, indent=1), encoding="utf-8")
        print(f"wrote {args.out}", flush=True)

    print(f"\naccuracy {correct}/{len(scored)} = {correct/max(len(scored),1):.1%}   total ${cost_total:.2f}")

    confusion: dict[tuple[str, str], int] = {}
    for r in scored:
        if not r["correct"]:
            confusion[(r["expected"], r["actual"] or "(no answer)")] = \
                confusion.get((r["expected"], r["actual"] or "(no answer)"), 0) + 1
    if confusion:
        print("\nmisroutes, most frequent first:")
        for (expected, actual), count in sorted(confusion.items(), key=lambda kv: -kv[1]):
            print(f"  {count}x  {expected}  ->  {actual}")
        # A paraphrase can drift far enough that the miss is the rewrite's fault,
        # not the description's. Print what was actually asked so each one can be
        # adjudicated instead of counted blind.
        print("\nthe text that missed:")
        for r in scored:
            if r["correct"]:
                continue
            asked = r.get("asked")
            print(f"  expected {r['expected']}, got {r['actual']}")
            print(f"      trigger:   {r['query']}")
            if asked and asked != r["query"]:
                print(f"      asked as:  {asked}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
