#!/usr/bin/env python3
"""
Aggregate individual run results into benchmark summary statistics.

Reads grading.json files from run directories and produces:
- run_summary with mean, stddev, min, max for each metric
- delta between the primary configuration (with_skill, or new_skill) and its
  baseline (without_skill, or old_skill): primary minus baseline, primary listed first

Run as a module from the skill-creator directory, so the `scripts` package
resolves, or by path from anywhere:

    python -m scripts.aggregate_benchmark <benchmark_dir> [--skill-name NAME]
    python <skill-creator>/scripts/aggregate_benchmark.py <benchmark_dir> [--skill-name NAME]

Example:
    python -m scripts.aggregate_benchmark benchmarks/2026-01-15T10-30-00/

A run is a directory holding grading.json (and, optionally, timing.json and
outputs/). The script supports three directory layouts:

    Workspace layout (references/real-evals.md): the configuration directory
    is the run.
    <benchmark_dir>/
    └── eval-N-<name>/
        ├── eval_metadata.json
        ├── with_skill/
        │   ├── outputs/
        │   ├── timing.json
        │   └── grading.json
        └── without_skill/
            ├── outputs/
            ├── timing.json
            └── grading.json

    Repeated runs: run-<N>/ subdirectories of the configuration directory.
    <benchmark_dir>/
    └── eval-N/
        ├── with_skill/
        │   ├── run-1/grading.json
        │   └── run-2/grading.json
        └── without_skill/
            ├── run-1/grading.json
            └── run-2/grading.json

    Legacy layout (with runs/ subdirectory): either of the above under
    <benchmark_dir>/runs/.

A value a run did not record (time, tokens) is null, never zero, and a
configuration with no graded run is null in run_summary and has no delta.

Exit codes:
    0  benchmark.json and benchmark.md were written
    1  the directory is missing or holds no graded run; nothing is written
"""

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.utils import configure_stdout
except ModuleNotFoundError:  # run by path, where only this directory is on sys.path
    from utils import configure_stdout

RUN_DIR = re.compile(r"run-(\d+)")

# The configuration names the viewer recognises, in the order they are preferred.
PRIMARY_CONFIGS = ("with_skill", "new_skill")
BASELINE_CONFIGS = ("without_skill", "old_skill")


def ordered_configs(configs) -> list[str]:
    """The primary configuration, then its baseline, then the rest, each group in name order.

    The delta is primary minus baseline, so which is which comes from the names:
    in name order alone old_skill sorts ahead of with_skill and an improvement
    reads as a regression. Names that are none of these keep plain name order.
    """
    names = sorted(configs)
    primary = next((name for name in PRIMARY_CONFIGS if name in names), None)
    baseline = next((name for name in BASELINE_CONFIGS if name in names), None)
    rest = [name for name in names if name not in (primary, baseline)]
    primary = primary or (rest.pop(0) if rest else None)
    baseline = baseline or (rest.pop(0) if rest else None)
    return [name for name in (primary, baseline, *rest) if name is not None]


def calculate_stats(values: list[float]) -> dict:
    """Calculate mean, stddev, min, max for a list of values."""
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    n = len(values)
    mean = sum(values) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4)
    }


def _warn(message: str) -> None:
    print(f"Warning: {message}", file=sys.stderr)


def _read_json(path: Path) -> dict | None:
    """The JSON object in a file, or None (with a warning) when it cannot be used."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        _warn(f"cannot read {path}: {e}")
        return None
    if not isinstance(data, dict):
        _warn(f"{path} is not a JSON object")
        return None
    return data


def _positive_number(*candidates):
    """The first candidate that is a real, positive number; None when there is none."""
    for value in candidates:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return value
    return None


def _eval_dirs(search_dir: Path) -> list[Path]:
    return [d for d in sorted(search_dir.glob("eval-*")) if d.is_dir()]


def _eval_identity(eval_dir: Path, index: int) -> tuple[int, str]:
    """The eval's numeric id and display name.

    eval_metadata.json wins; the directory name is the fallback, because
    real-evals.md asks for descriptive eval directory names and the viewer shows them.
    """
    metadata = {}
    metadata_path = eval_dir / "eval_metadata.json"
    if metadata_path.exists():
        metadata = _read_json(metadata_path) or {}

    eval_id = metadata.get("eval_id")
    if isinstance(eval_id, bool) or not isinstance(eval_id, int):
        try:
            eval_id = int(eval_dir.name.split("-")[1])
        except ValueError:
            eval_id = index

    name = metadata.get("eval_name")
    return eval_id, name if isinstance(name, str) and name else eval_dir.name


def _run_dirs(config_dir: Path) -> list[tuple[int, Path]]:
    """The runs of one configuration directory, as (run number, directory).

    run-<N>/ subdirectories are the runs. Without any, the configuration
    directory is itself run 1 when it holds a grading.json or an outputs/, which
    is the layout real-evals.md documents. Anything else (inputs/, notes) is not
    a configuration and yields no runs.
    """
    numbered = []
    for child in sorted(config_dir.iterdir()):
        if not child.name.startswith("run-") or not child.is_dir():
            continue
        match = RUN_DIR.fullmatch(child.name)
        if match is None:
            _warn(f"ignoring {child}: expected run-<number>")
            continue
        numbered.append((int(match.group(1)), child))
    if numbered:
        return sorted(numbered)
    if (config_dir / "grading.json").exists() or (config_dir / "outputs").is_dir():
        return [(1, config_dir)]
    return []


def _load_run(run_dir: Path, eval_id: int, eval_name: str, run_number: int) -> dict | None:
    """One run's metrics, or None when it has no usable grading.json."""
    grading_file = run_dir / "grading.json"
    if not grading_file.exists():
        _warn(f"grading.json not found in {run_dir}")
        return None
    grading = _read_json(grading_file)
    if grading is None:
        return None

    summary = grading.get("summary") or {}
    passed = summary.get("passed", 0)
    total = summary.get("total", 0)
    pass_rate = summary.get("pass_rate")
    if pass_rate is None and total:
        pass_rate = passed / total
    if pass_rate is None:
        _warn(f"{grading_file} has no pass_rate and no graded expectations; skipping the run")
        return None

    timing_file = run_dir / "timing.json"
    timing_data = (_read_json(timing_file) if timing_file.exists() else None) or {}
    timing = grading.get("timing") or {}
    metrics = grading.get("execution_metrics") or {}

    # Viewer requires fields: text, passed, evidence
    expectations = grading.get("expectations", [])
    for exp in expectations:
        if "text" not in exp or "passed" not in exp:
            _warn(f"expectation in {grading_file} missing required fields (text, passed, evidence): {exp}")

    notes_summary = grading.get("user_notes_summary", {})
    notes = []
    notes.extend(notes_summary.get("uncertainties", []))
    notes.extend(notes_summary.get("needs_review", []))
    notes.extend(notes_summary.get("workarounds", []))

    return {
        "eval_id": eval_id,
        "eval_name": eval_name,
        "run_number": run_number,
        "pass_rate": pass_rate,
        "passed": passed,
        "failed": summary.get("failed", 0),
        "total": total,
        # A duration or token count a run never recorded stays None: a zero would
        # be averaged in as if it had been measured, and output_chars is a
        # character count, not tokens.
        "time_seconds": _positive_number(timing.get("total_duration_seconds"),
                                         timing_data.get("total_duration_seconds")),
        "tokens": _positive_number(timing_data.get("total_tokens"), timing.get("total_tokens")),
        "tool_calls": metrics.get("total_tool_calls", 0),
        "errors": metrics.get("errors_encountered", 0),
        "expectations": expectations,
        "notes": notes,
    }


def load_run_results(benchmark_dir: Path) -> dict:
    """
    Load all run results from a benchmark directory.

    Returns dict keyed by config name (e.g. "with_skill"/"without_skill",
    or "new_skill"/"old_skill"), each containing a list of run results.
    """
    # Support both layouts: eval dirs directly under benchmark_dir, or under runs/
    runs_dir = benchmark_dir / "runs"
    if runs_dir.exists():
        search_dir = runs_dir
    elif _eval_dirs(benchmark_dir):
        search_dir = benchmark_dir
    else:
        print(f"No eval directories found in {benchmark_dir} or {benchmark_dir / 'runs'}", file=sys.stderr)
        return {}

    results: dict[str, list] = {}

    for eval_idx, eval_dir in enumerate(_eval_dirs(search_dir)):
        eval_id, eval_name = _eval_identity(eval_dir, eval_idx)

        # Discover config directories dynamically rather than hardcoding names
        for config_dir in sorted(eval_dir.iterdir()):
            if not config_dir.is_dir():
                continue
            runs = _run_dirs(config_dir)
            if not runs:
                continue
            config = config_dir.name
            results.setdefault(config, [])

            for run_number, run_dir in runs:
                result = _load_run(run_dir, eval_id, eval_name, run_number)
                if result is not None:
                    results[config].append(result)

    return results


def _stats_or_none(values: list[float]) -> dict | None:
    return calculate_stats(values) if values else None


def aggregate_results(results: dict) -> dict:
    """
    Aggregate run results into summary statistics.

    Returns run_summary with stats for each configuration and delta. A
    configuration without a graded run is None, and so is any metric none of
    its runs recorded; a delta needs both sides and is None otherwise.
    """
    run_summary = {}
    configs = ordered_configs(results)

    for config in configs:
        runs = results.get(config, [])

        if not runs:
            run_summary[config] = None
            continue

        run_summary[config] = {
            "pass_rate": calculate_stats([r["pass_rate"] for r in runs]),
            "time_seconds": _stats_or_none([r["time_seconds"] for r in runs if r["time_seconds"] is not None]),
            "tokens": _stats_or_none([r["tokens"] for r in runs if r["tokens"] is not None]),
        }

    # Primary minus baseline, the first two of ordered_configs, when both have data
    primary =run_summary.get(configs[0]) if len(configs) >= 2 else None
    baseline = run_summary.get(configs[1]) if len(configs) >= 2 else None

    def delta(metric: str, fmt: str) -> str | None:
        if not primary or not baseline or not primary[metric] or not baseline[metric]:
            return None
        return format(primary[metric]["mean"] - baseline[metric]["mean"], fmt)

    run_summary["delta"] = {
        "pass_rate": delta("pass_rate", "+.2f"),
        "time_seconds": delta("time_seconds", "+.1f"),
        "tokens": delta("tokens", "+.0f"),
    }

    return run_summary


def generate_benchmark(benchmark_dir: Path, skill_name: str = "", skill_path: str = "") -> dict:
    """
    Generate complete benchmark.json from run results.
    """
    results = load_run_results(benchmark_dir)
    run_summary = aggregate_results(results)

    # Build runs array for benchmark.json
    runs = []
    for config in ordered_configs(results):
        for result in results[config]:
            runs.append({
                "eval_id": result["eval_id"],
                "eval_name": result["eval_name"],
                "configuration": config,
                "run_number": result["run_number"],
                "result": {
                    "pass_rate": result["pass_rate"],
                    "passed": result["passed"],
                    "failed": result["failed"],
                    "total": result["total"],
                    "time_seconds": result["time_seconds"],
                    "tokens": result["tokens"],
                    "tool_calls": result["tool_calls"],
                    "errors": result["errors"]
                },
                "expectations": result["expectations"],
                "notes": result["notes"]
            })

    # Determine eval IDs from results
    eval_ids = sorted(set(
        r["eval_id"]
        for config in results.values()
        for r in config
    ))

    # The most runs any configuration has for one eval; the layouts allow it to vary.
    per_eval: dict[tuple[str, int], int] = {}
    for config, config_runs in results.items():
        for r in config_runs:
            key = (config, r["eval_id"])
            per_eval[key] = per_eval.get(key, 0) + 1

    benchmark = {
        "metadata": {
            "skill_name": skill_name or "<skill-name>",
            "skill_path": skill_path or "<path/to/skill>",
            "executor_model": "<model-name>",
            "analyzer_model": "<model-name>",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": eval_ids,
            "runs_per_configuration": max(per_eval.values(), default=0)
        },
        "runs": runs,
        "run_summary": run_summary,
        "notes": []  # To be filled by analyzer
    }

    return benchmark


def generate_markdown(benchmark: dict) -> str:
    """Generate human-readable benchmark.md from benchmark data."""
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]

    # Determine config names (excluding "delta")
    configs = [k for k in run_summary if k != "delta"]
    config_a = configs[0] if len(configs) >= 1 else "config_a"
    config_b = configs[1] if len(configs) >= 2 else "config_b"
    label_a = config_a.replace("_", " ").title()
    label_b = config_b.replace("_", " ").title()

    lines = [
        f"# Skill Benchmark: {metadata['skill_name']}",
        "",
        f"**Model**: {metadata['executor_model']}",
        f"**Date**: {metadata['timestamp']}",
        f"**Evals**: {', '.join(map(str, metadata['evals_run']))} ({metadata['runs_per_configuration']} runs each per configuration)",
        "",
        "## Summary",
        "",
        f"| Metric | {label_a} | {label_b} | Delta |",
        "|--------|------------|---------------|-------|",
    ]

    a_summary = run_summary.get(config_a) or {}
    b_summary = run_summary.get(config_b) or {}
    delta = run_summary.get("delta") or {}

    def cell(stat: dict | None, scale: float, decimals: int, suffix: str) -> str:
        if not stat:
            return "n/a"
        return f"{stat['mean'] * scale:.{decimals}f}{suffix} ± {stat['stddev'] * scale:.{decimals}f}{suffix}"

    def delta_cell(value: str | None, suffix: str = "") -> str:
        return f"{value}{suffix}" if value is not None else "n/a"

    lines.append(f"| Pass Rate | {cell(a_summary.get('pass_rate'), 100, 0, '%')} | {cell(b_summary.get('pass_rate'), 100, 0, '%')} | {delta_cell(delta.get('pass_rate'))} |")
    lines.append(f"| Time | {cell(a_summary.get('time_seconds'), 1, 1, 's')} | {cell(b_summary.get('time_seconds'), 1, 1, 's')} | {delta_cell(delta.get('time_seconds'), 's')} |")
    lines.append(f"| Tokens | {cell(a_summary.get('tokens'), 1, 0, '')} | {cell(b_summary.get('tokens'), 1, 0, '')} | {delta_cell(delta.get('tokens'))} |")

    # Notes section
    if benchmark.get("notes"):
        lines.extend([
            "",
            "## Notes",
            ""
        ])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines)


def main():
    configure_stdout()
    parser = argparse.ArgumentParser(
        description="Aggregate benchmark run results into summary statistics"
    )
    parser.add_argument(
        "benchmark_dir",
        type=Path,
        help="Path to the benchmark directory"
    )
    parser.add_argument(
        "--skill-name",
        default="",
        help="Name of the skill being benchmarked"
    )
    parser.add_argument(
        "--skill-path",
        default="",
        help="Path to the skill being benchmarked"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output path for benchmark.json (default: <benchmark_dir>/benchmark.json)"
    )

    args = parser.parse_args()

    if not args.benchmark_dir.exists():
        print(f"Directory not found: {args.benchmark_dir}", file=sys.stderr)
        sys.exit(1)

    # Generate benchmark
    benchmark = generate_benchmark(args.benchmark_dir, args.skill_name, args.skill_path)

    # An empty benchmark reads as a real one with no difference, so write none.
    if not benchmark["runs"]:
        print(f"Error: no graded runs found in {args.benchmark_dir}; "
              "nothing was written (expected eval-*/<config>/grading.json)", file=sys.stderr)
        sys.exit(1)

    # Determine output paths
    output_json = args.output or (args.benchmark_dir / "benchmark.json")
    output_md = output_json.with_suffix(".md")

    # Write benchmark.json
    output_json.write_text(json.dumps(benchmark, indent=2), encoding="utf-8")
    print(f"Generated: {output_json}")

    # Write benchmark.md
    output_md.write_text(generate_markdown(benchmark), encoding="utf-8")
    print(f"Generated: {output_md}")

    # Print summary
    run_summary = benchmark["run_summary"]
    configs = [k for k in run_summary if k != "delta"]
    delta = run_summary.get("delta", {})

    print("\nSummary:")
    for config in configs:
        stats = run_summary[config]
        label = config.replace("_", " ").title()
        rate = f"{stats['pass_rate']['mean'] * 100:.1f}% pass rate" if stats else "n/a (no graded run)"
        print(f"  {label}: {rate}")
    print(f"  Delta:         {delta.get('pass_rate') or 'n/a'}")


if __name__ == "__main__":
    main()
