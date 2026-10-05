<p align="center">
  <img src="docs/assets/favicon.jpg" width="112" alt="Supreme Team gate seal" />
</p>

<h1 align="center">Supreme Team</h1>

<p align="center">
  Design, build, and review software through a coding assistant, with a gate between every phase.
</p>

<p align="center">
  <sub>53 skills · 10 pipelines · one front door · Claude Code, Codex, GitHub Copilot, Cursor, OpenCode</sub>
</p>

---

## What it is

Supreme Team routes a coding request through **design → build → review**, with a
gate between every phase. Each phase boundary is checked against evidence on disk
before the next phase is handed its work. Where the host allows interception,
optional runtime hooks turn some of the rules into refusals instead of advice;
they are off until you register them, and without them routing and guards are
advisory (see [Install.md](Install.md#runtime-hooks)).

![The four lifecycle layers of the runtime harness](docs/assets/7_harness.jpg)

## First ten minutes

1. **Install** — hand [Install.md](Install.md) to your agent, or run the installer for your OS from [scripts/](scripts/) (`bash ./scripts/install.sh`, or `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1`). The skill files copy without Python; the checks and hooks need **Python 3.13 or newer**. Runtime hooks are optional and registered separately (`--register-hooks`, which edits host config files and asks first on a terminal); Claude Code, Codex and GitHub Copilot take config entries, Cursor and OpenCode a plugin.
2. **Restart your assistant** so it loads the skills, then [check the installed copy](#check-an-installation).
3. **Start a run** — call `admiral`. It interviews you, writes the scope down, creates a run on disk, and hands off phase one. A governed run reads a lot of text; [QUICK-START.md](QUICK-START.md#what-a-run-costs) says how much and how to avoid it.
4. **Let it flow** — small reversible edits skip the whole route and just get done (the Tier 0 fast path); security, deploy, and production work are never Tier 0 and take the full route. Routing is instruction, not enforcement: registered hooks remind the model on every prompt and refuse guarded writes, but nothing forces a request through `admiral`.

## Review gates

Every phase boundary hits a gatekeeper. The package and its hashed evidence go
through two deterministic validators, then a gatekeeper issues one verdict:
**APPROVED** advances, **REVISE** returns with the exact missing fact (twice, then
escalate), **ESCALATE** comes to you. Evidence that names its source files by
sha256 fails with `input hash drift` when one of them changes, instead of the gate
trusting a stale log. Scan and render records must name their sources; a test or
probe record that names none is accepted as the submitter's own statement, and the
gate says so in `warnings` rather than implying it was verified.

![The review loop: package, twin validators, adjudicator verdict](docs/assets/6_review_loop.jpg)

More in [docs/gatekeepers.md](docs/gatekeepers.md).

## Persistence & recovery

Run state lives in `skillset-saves/` inside your project. Checkpoints publish
atomically, so an interrupted publish is visible and repairable, a stale lock
reclaim leaves a trace, and a lost pointer is not a lost run. Kill the session
mid-run and the next one resumes from the same files.

![Recovery: interrupted publish, stale lock, lost pointer](docs/assets/10_recovery.jpg)

More in [docs/persistent-saves.md](docs/persistent-saves.md).

## How well it works

Measured where it can be, and labelled where it cannot. Every gate boundary is
proven satisfiable by submitting a real package to the real validator, and CI runs
the test suites on Windows, macOS and Linux. The skill scores are model judgements
against a written rubric, not machine output, and the routing accuracy is a paid,
networked measurement. Both were last taken on 2026-10-05 against the 53-skill
roster. This page gives no figures for either, because nothing here would keep
them true. Every number, its date and the roster it was measured on are in
[BENCHMARK.md](BENCHMARK.md), along with what is deliberately *not* measured. The
audit record in [docs/quality-audit.md](docs/quality-audit.md) holds the reproduced
defects behind the scores.

The routing figure is the one worth reading the methodology for: a catalog scores
100% when queried with its own advertised phrasings, which measures lexical echo,
and noticeably less when those queries are rewritten the way someone would
actually type them. Only the second number measures anything.

## Check an installation

Python 3.13 or newer is the floor for everything in this section. Commands in
these documents are written for a repository checkout, start at its root and say
`python`; on macOS and Linux that is `python3` (Ubuntu 22.04 and later and current
macOS ship no `python`), on Windows `py -3`. In an installed copy `skills/` is the
install root. [Install.md](Install.md#paths-and-the-python-command) states both
substitutions.

The checkout (`package_check.py` and the tests need one):

```bash
python skills/scripts/check_runtime.py
python skills/scripts/validate_manifests.py
python skills/scripts/package_check.py --root .
python skills/harness/hooks/check_readiness.py --host auto
```

The installed copy, from any directory:

```bash
python3 ~/.agents/skills/scripts/check_runtime.py
python3 ~/.agents/skills/scripts/validate_manifests.py
python3 ~/.agents/skills/harness/hooks/check_readiness.py --host auto
```

```powershell
py -3 "$env:USERPROFILE\.agents\skills\scripts\check_runtime.py"
py -3 "$env:USERPROFILE\.agents\skills\scripts\validate_manifests.py"
py -3 "$env:USERPROFILE\.agents\skills\harness\hooks\check_readiness.py" --host auto
```

## Run the tests

Seven suites, standard library only, Python 3.13 or newer. Run them from a
repository checkout. CI runs these same commands on Windows, macOS and Linux,
on Python 3.13 and 3.14, with and without PyYAML installed
([CONTRIBUTING.md](CONTRIBUTING.md) explains how to run one suite or all of them).

```bash
python -m unittest discover -s skills/harness/hooks -p "test_*.py"
python -m unittest discover -s skills/harness/gatekeeper -p "test_*.py"
python -m unittest discover -s skills/validation -p "test_*.py"
python -m unittest discover -s skills/scripts -p "test_*.py"
python -m unittest discover -s skills/taste -p "test_*.py"
python -m unittest discover -s scripts -p "test_*.py"
python -m unittest discover -s skills/skill-maker/skill-creator -p "test_*.py"
```

## Documentation

| Document | What is in it |
|---|---|
| [QUICK-START.md](QUICK-START.md) | Install and first run |
| [Install.md](Install.md) | The full installation procedure |
| [BENCHMARK.md](BENCHMARK.md) | Scores, routing accuracy, and how each was measured |
| [docs/quality-audit.md](docs/quality-audit.md) | Audit rounds 1 to 3: benchmark runs, the findings register, surface scores |
| [AGENTS.md](AGENTS.md) | Flat skill index for tool discovery |
| [docs/architecture.md](docs/architecture.md) | Pipelines, tiers, execution modes |
| [docs/skills.md](docs/skills.md) | Every skill and what it owns |
| [docs/routing.md](docs/routing.md) | How a request finds its skill |
| [docs/gatekeepers.md](docs/gatekeepers.md) | Boundaries, evidence, verdicts |
| [docs/harness.md](docs/harness.md) | Hooks, readiness, gate validators |
| [docs/persistent-saves.md](docs/persistent-saves.md) | Save layout, locks, resume |
| [docs/direct-invocation.md](docs/direct-invocation.md) | Calling skills directly |
| [docs/directory-structure.md](docs/directory-structure.md) | Where everything lives |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Running the suites, the fail-open and fail-loud rules, commits, skill versions |
| [CHANGELOG.md](CHANGELOG.md) | What changed |

## License

Supreme Team is released under the [MIT License](LICENSE). Copyright (c) 2026 TykoDev.

<p align="center">
    <sub>Built by <a href="https://github.com/TykoDev">TykoDev</a> · Supreme Team</sub>
</p>
