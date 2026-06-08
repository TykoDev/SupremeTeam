# Real Evals — Track A Workflow

Track A catches behavioral problems that structural scoring can't see: "the output
looks ugly", "it missed the deadline column", "the generated code doesn't compile on
the test data". It runs real test cases with subagents, lets the user review, and
feeds feedback back into the improvement loop.

Read this before your first pass. The summary in SKILL.md Phase 3 is intentionally
brief; the full mechanics live here.

## Contents

1. Writing test cases
2. Workspace layout
3. Spawning runs (with-skill + baseline)
4. Drafting assertions
5. Capturing timing
6. Grading and aggregation
7. Launching the viewer
8. Reading feedback
9. Iteration mechanics

---

## 1. Writing test cases

After drafting the skill, come up with 2–3 realistic test prompts — the kind of thing
a real user would actually say. Share them with the user: "Here are a few test cases
I'd like to try. Do these look right, or do you want to add more?" Then run them.

Save to `evals/evals.json` at the repo root (sibling to the skill directory). Don't
write assertions yet — just the prompts. You'll draft assertions while runs are
in progress.

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt",
      "expected_output": "Description of expected result",
      "files": []
    }
  ]
}
```

Full schema including the `assertions` field (added later) is in `schemas.md`.

### What makes a realistic prompt

- Casual phrasing, not textbook-clean
- Specific details (file paths, column names, personal context)
- A little backstory — what the user is trying to accomplish
- Mix lengths
- Include at least one edge-case-leaning prompt

---

## 2. Workspace layout

Put results in `<skill-name>-workspace/` as a sibling to the skill directory. Within
the workspace, organize results by iteration and then by test case:

```
<skill-name>-workspace/
├── iteration-1/
│   ├── eval-0-<descriptive-name>/
│   │   ├── eval_metadata.json
│   │   ├── with_skill/
│   │   │   ├── outputs/
│   │   │   ├── timing.json
│   │   │   └── grading.json
│   │   └── without_skill/       (or old_skill/ for improvements)
│   │       ├── outputs/
│   │       ├── timing.json
│   │       └── grading.json
│   └── benchmark.json
└── iteration-2/
    └── ...
```

Don't create all of this upfront — create directories as you go.

### Naming eval directories

Use descriptive names, not just `eval-0`. If the test case checks quarterly report
generation, the directory is `eval-0-quarterly-report-generation` or similar. Names
show up in the viewer; clear names make navigation easy.

---

## 3. Spawning runs (with-skill + baseline)

**Critical rule**: for each test case, spawn *both* subagents in the same turn — one
with the skill, one baseline. Don't run with-skill first and come back for baselines
later. Launch everything at once so it all finishes around the same time.

### With-skill run

```
Execute this task:
- Skill path: <path-to-skill>
- Task: <eval prompt>
- Input files: <eval files, or "none">
- Save outputs to: <workspace>/iteration-<N>/eval-<ID>/with_skill/outputs/
- Outputs to save: <what the user cares about — e.g., "the .docx file", "the final CSV">
```

### Baseline run

The baseline depends on context:

- **Creating a new skill**: no skill. Same prompt, no skill path. Save to
  `without_skill/outputs/`
- **Improving an existing skill**: the old version. Before editing, snapshot the skill
  (`cp -r <skill-path> <workspace>/skill-snapshot/`), then point the baseline subagent
  at the snapshot. Save to `old_skill/outputs/`

### eval_metadata.json

Write one per test case. Assertions can be empty at first — they're drafted while
runs are in progress.

```json
{
  "eval_id": 0,
  "eval_name": "quarterly-report-generation",
  "prompt": "The user's task prompt",
  "assertions": []
}
```

If an iteration uses new or modified eval prompts, create these files for each new
eval directory. Don't assume they carry over from previous iterations.

---

## 4. Drafting assertions

Don't wait idle for runs to finish — draft assertions now.

Good assertions are:

- Objectively verifiable (programmatic if possible)
- Descriptively named (they appear in the viewer)
- Specific to this test case, not generic

Subjective skills (writing style, design quality) are better evaluated qualitatively —
don't force assertions onto things that need human judgment.

Update `eval_metadata.json` and `evals/evals.json` with assertions once drafted.
Explain to the user what the viewer will show — both qualitative outputs and
quantitative benchmark.

---

## 5. Capturing timing

When each subagent task completes, you receive a notification with `total_tokens` and
`duration_ms`. Save to `timing.json` in the run directory immediately:

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

**This is the only opportunity** to capture this data — it comes through the task
notification and isn't persisted elsewhere. Process each notification as it arrives
rather than batching them at the end (you'll lose the data).

---

## 6. Grading and aggregation

Once all runs are done:

### Grade each run

Spawn a grader subagent (or grade inline) that reads `agents/grader.md` and evaluates
each assertion against the outputs. Save to `grading.json` in each run directory.

**Critical field names**: the `grading.json` expectations array must use the fields
`text`, `passed`, and `evidence` — not `name`/`met`/`details` or other variants. The
viewer depends on these exact field names.

For programmatically-checkable assertions, write and run a script rather than
eyeballing it — scripts are faster, more reliable, and reusable across iterations.

### Aggregate

```bash
python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <n>
```

This produces `benchmark.json` and `benchmark.md` with pass_rate, time, and tokens
for each configuration (mean ± stddev, delta). If you need to generate
`benchmark.json` manually, see `schemas.md` for the exact schema the viewer expects.
Put each with_skill entry *before* its baseline counterpart in the output.

---

## 7. Launching the viewer

Run `eval-viewer/generate_review.py` to produce the reviewer. On Claude Code it opens
in the browser. On Cowork, use `--static <output_path>` to produce standalone HTML
and give the user a link. On Claude.ai, skip this — present results inline instead
(see SKILL.md environment notes).

### What the user sees

The "Outputs" tab shows one test case at a time:

- **Prompt**: the task given
- **Output**: files the skill produced, rendered inline where possible
- **Previous Output** (iteration 2+): collapsed, last iteration's output
- **Formal Grades** (if graded): collapsed, assertion pass/fail
- **Feedback**: textbox that auto-saves as they type
- **Previous Feedback** (iteration 2+): their comments from last time

The "Benchmark" tab shows pass rates, timing, token usage for each configuration.

Navigation: prev/next buttons or arrow keys. When done, "Submit All Reviews" saves
feedback to `feedback.json`.

### In Cowork specifically

The viewer's "Submit All Reviews" button downloads `feedback.json` as a file instead
of posting to a server. You may need to request access to read it.

---

## 8. Reading feedback

When the user says they're done, read `feedback.json`:

```json
{
  "reviews": [
    {"run_id": "eval-0-with_skill", "feedback": "the chart is missing axis labels", "timestamp": "..."},
    {"run_id": "eval-1-with_skill", "feedback": "", "timestamp": "..."},
    {"run_id": "eval-2-with_skill", "feedback": "perfect, love this", "timestamp": "..."}
  ],
  "status": "complete"
}
```

Empty feedback means the user thought it was fine. Focus improvements on test cases
with specific complaints.

Kill the viewer server when done:

```bash
kill $VIEWER_PID 2>/dev/null
```

---

## 9. Iteration mechanics

After applying improvements (Phase 4 in SKILL.md):

1. Rerun all test cases into `iteration-<N+1>/`, including baselines
2. For new skills, baseline stays `without_skill` across iterations
3. For hardening existing skills, use judgment: original version the user came in
   with, or previous iteration — whichever is a fairer comparison
4. Launch the reviewer with `--previous-workspace` pointing at the previous iteration
   so users can see before/after
5. Wait for user review, read new feedback, improve again, repeat

Stop when: user is happy, feedback is all empty, or you're not making meaningful
progress. Track B (rubric) has its own stopping rules — apply whichever triggers
first.

---

## Advanced: blind comparison

For rigorous A/B between two versions ("is the new version actually better?"), read
`agents/comparator.md` and `agents/analyzer.md`. Give two outputs to an independent
agent without labels, let it judge, analyze why the winner won. Optional, requires
subagents, most users won't need it.
