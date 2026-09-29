#!/usr/bin/env python3
"""Improve a skill description based on eval results.

Takes eval results (from run_eval.py) and generates an improved description
by calling `claude -p` as a subprocess (same auth pattern as run_eval.py —
uses the session's Claude Code auth, no separate ANTHROPIC_API_KEY needed).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from scripts.utils import parse_skill_md

# The host truncates a description here, so a longer one is not what gets evaluated.
MAX_DESCRIPTION_CHARS = 1024
# Each retry is a model call; three is enough to tell a bad prompt from a bad reply.
MAX_REWRITES = 3


class DescriptionError(RuntimeError):
    """The model never returned a usable description."""


def _call_claude(prompt: str, model: str | None, timeout: int = 300) -> str:
    """Run `claude -p` with the prompt on stdin and return the text response.

    Prompt goes over stdin (not argv) because it embeds the full SKILL.md
    body and can easily exceed comfortable argv length. It is UTF-8 both ways:
    the locale default (cp1252 on Windows) cannot encode a SKILL.md's punctuation.
    """
    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])

    # Remove CLAUDECODE env var to allow nesting claude -p inside a
    # Claude Code session. The guard is for interactive terminal conflicts;
    # programmatic subprocess usage is safe. Same pattern as run_eval.py.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"claude -p timed out after {timeout}s") from e
    except FileNotFoundError as e:
        raise RuntimeError("the claude CLI was not found on PATH") from e
    if result.returncode != 0:
        raise RuntimeError(
            f"claude -p exited {result.returncode}\nstderr: {result.stderr}"
        )
    return result.stdout


def _extract_description(text: str) -> str | None:
    """The text inside <new_description>, or None when the tags or their content are missing.

    A reply without the tags is an apology, a refusal or commentary; using it whole
    would put that prose into the next evaluation as the description.
    """
    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    if match is None:
        return None
    return match.group(1).strip().strip('"').strip() or None


def _unusable(description: str | None) -> bool:
    return description is None or len(description) > MAX_DESCRIPTION_CHARS


def _rewrite_prompt(prompt: str, description: str | None) -> str:
    """A fresh single-turn prompt that says what was wrong with the previous reply.

    `claude -p` is one-shot, so the earlier output is quoted into the new prompt
    rather than continued as a conversation.
    """
    if description is None:
        problem = ("A previous reply had no non-empty <new_description> block, so it could not be used. "
                   "Respond with only the new description in <new_description> tags.")
    else:
        problem = (
            f"A previous attempt produced this description, which at "
            f"{len(description)} characters is over the {MAX_DESCRIPTION_CHARS}-character hard limit:\n\n"
            f'"{description}"\n\n'
            f"Rewrite it to be under {MAX_DESCRIPTION_CHARS} characters while keeping the most "
            f"important trigger words and intent coverage. Respond with only "
            f"the new description in <new_description> tags."
        )
    return f"{prompt}\n\n---\n\n{problem}"


def improve_description(
    skill_name: str,
    skill_content: str,
    current_description: str,
    eval_results: dict,
    history: list[dict],
    model: str,
    test_results: dict | None = None,
    log_dir: Path | None = None,
    iteration: int | None = None,
) -> str:
    """Call Claude to improve the description based on eval results.

    Raises DescriptionError (a RuntimeError) when no usable description comes back.
    """
    # `is False`: a query with no observed run has a null pass and is not a failure to fix.
    failed_triggers = [
        r for r in eval_results["results"]
        if r["should_trigger"] and r["pass"] is False
    ]
    false_triggers = [
        r for r in eval_results["results"]
        if not r["should_trigger"] and r["pass"] is False
    ]

    # Build scores summary
    train_score = f"{eval_results['summary']['passed']}/{eval_results['summary']['total']}"
    if test_results:
        test_score = f"{test_results['summary']['passed']}/{test_results['summary']['total']}"
        scores_summary = f"Train: {train_score}, Test: {test_score}"
    else:
        scores_summary = f"Train: {train_score}"

    prompt = f"""You are optimizing a skill description for a Claude Code skill called "{skill_name}". A "skill" is sort of like a prompt, but with progressive disclosure -- there's a title and description that Claude sees when deciding whether to use the skill, and then if it does use the skill, it reads the .md file which has lots more details and potentially links to other resources in the skill folder like helper files and scripts and additional documentation or examples.

The description appears in Claude's "available_skills" list. When a user sends a query, Claude decides whether to invoke the skill based solely on the title and on this description. Your goal is to write a description that triggers for relevant queries, and doesn't trigger for irrelevant ones.

Here's the current description:
<current_description>
"{current_description}"
</current_description>

Current scores ({scores_summary}):
<scores_summary>
"""
    if failed_triggers:
        prompt += "FAILED TO TRIGGER (should have triggered but didn't):\n"
        for r in failed_triggers:
            prompt += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]} times)\n'
        prompt += "\n"

    if false_triggers:
        prompt += "FALSE TRIGGERS (triggered but shouldn't have):\n"
        for r in false_triggers:
            prompt += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]} times)\n'
        prompt += "\n"

    if history:
        prompt += "PREVIOUS ATTEMPTS (do NOT repeat these — try something structurally different):\n\n"
        for h in history:
            train_s = f"{h.get('train_passed', h.get('passed', 0))}/{h.get('train_total', h.get('total', 0))}"
            test_s = f"{h.get('test_passed', '?')}/{h.get('test_total', '?')}" if h.get('test_passed') is not None else None
            score_str = f"train={train_s}" + (f", test={test_s}" if test_s else "")
            prompt += f'<attempt {score_str}>\n'
            prompt += f'Description: "{h["description"]}"\n'
            if "results" in h:
                prompt += "Train results:\n"
                for r in h["results"]:
                    status = "PASS" if r["pass"] else "FAIL"
                    prompt += f'  [{status}] "{r["query"][:80]}" (triggered {r["triggers"]}/{r["runs"]})\n'
            if h.get("note"):
                prompt += f'Note: {h["note"]}\n'
            prompt += "</attempt>\n\n"

    prompt += f"""</scores_summary>

Skill content (for context on what the skill does):
<skill_content>
{skill_content}
</skill_content>

Based on the failures, write a new and improved description that is more likely to trigger correctly. When I say "based on the failures", it's a bit of a tricky line to walk because we don't want to overfit to the specific cases you're seeing. So what I DON'T want you to do is produce an ever-expanding list of specific queries that this skill should or shouldn't trigger for. Instead, try to generalize from the failures to broader categories of user intent and situations where this skill would be useful or not useful. The reason for this is twofold:

1. Avoid overfitting
2. The list might get loooong and it's injected into ALL queries and there might be a lot of skills, so we don't want to blow too much space on any given description.

Concretely, your description should not be more than about 100-200 words, even if that comes at the cost of accuracy. There is a hard limit of 1024 characters — descriptions over that will be truncated, so stay comfortably under it.

Here are some tips that we've found to work well in writing these descriptions:
- The description must be third-person declarative -- "Processes Excel files. Use when the user..." -- never first or second person. This is a hard constraint from the skill guide, not a stylistic preference; an imperative opener ("Use this skill to process...") is a rubric failure even when it triggers well
- The skill description should focus on the user's intent, what they are trying to achieve, vs. the implementation details of how the skill works.
- The description competes with other skills for Claude's attention — make it distinctive and immediately recognizable.
- If you're getting lots of failures after repeated attempts, change things up. Try different sentence structures or wordings.

I'd encourage you to be creative and mix up the style in different iterations since you'll have multiple opportunities to try different approaches and we'll just grab the highest-scoring one at the end. 

Please respond with only the new description text in <new_description> tags, nothing else."""

    text = _call_claude(prompt, model)
    description = _extract_description(text)

    transcript: dict = {
        "iteration": iteration,
        "prompt": prompt,
        "response": text,
        "parsed_description": description,
        "char_count": len(description or ""),
        "over_limit": len(description or "") > MAX_DESCRIPTION_CHARS,
        "rewrites": [],
    }

    # Safety net: the prompt already states the format and the hard limit, but a
    # reply can still lack the tags or blow past it. Retry, bounded, and check
    # every result the same way, since a rewrite can be just as unusable.
    while _unusable(description) and len(transcript["rewrites"]) < MAX_REWRITES:
        rewrite_prompt = _rewrite_prompt(prompt, description)
        rewrite_text = _call_claude(rewrite_prompt, model)
        description = _extract_description(rewrite_text)
        transcript["rewrites"].append({
            "prompt": rewrite_prompt,
            "response": rewrite_text,
            "description": description,
            "char_count": len(description or ""),
        })

    transcript["final_description"] = description

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"improve_iter_{iteration or 'unknown'}.json"
        log_file.write_text(json.dumps(transcript, indent=2), encoding="utf-8")

    if _unusable(description):
        reason = ("no non-empty <new_description> block" if description is None
                  else f"{len(description)} characters, over the {MAX_DESCRIPTION_CHARS} limit")
        raise DescriptionError(f"no usable description after {len(transcript['rewrites'])} rewrite(s): {reason}")

    return description


def main():
    parser = argparse.ArgumentParser(description="Improve a skill description based on eval results")
    parser.add_argument("--eval-results", required=True, help="Path to eval results JSON (from run_eval.py)")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--history", default=None, help="Path to history JSON (previous attempts)")
    parser.add_argument("--model", required=True, help="Model for improvement")
    parser.add_argument("--verbose", action="store_true", help="Print thinking to stderr")
    args = parser.parse_args()

    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    eval_results = json.loads(Path(args.eval_results).read_text(encoding="utf-8"))
    history = []
    if args.history:
        history = json.loads(Path(args.history).read_text(encoding="utf-8"))

    name, _, content = parse_skill_md(skill_path)
    current_description = eval_results["description"]

    if args.verbose:
        print(f"Current: {current_description}", file=sys.stderr)
        print(f"Score: {eval_results['summary']['passed']}/{eval_results['summary']['total']}", file=sys.stderr)

    try:
        new_description = improve_description(
            skill_name=name,
            skill_content=content,
            current_description=current_description,
            eval_results=eval_results,
            history=history,
            model=args.model,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Improved: {new_description}", file=sys.stderr)

    # Output as JSON with both the new description and updated history
    output = {
        "description": new_description,
        "history": history + [{
            "description": current_description,
            "passed": eval_results["summary"]["passed"],
            "failed": eval_results["summary"]["failed"],
            "total": eval_results["summary"]["total"],
            "results": eval_results["results"],
        }],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
