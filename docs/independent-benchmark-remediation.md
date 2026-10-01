# Independent benchmark remediation audit

This audit maps the seven findings reported against commit `b43838e` to the
current repository. It distinguishes a mechanical control from an operational
claim: passing tests prove the checked contract, not product success or a secure
host.

| Finding | Disposition | Current evidence |
|---|---|---|
| Installation layout drift | Remediated | Both installers consume `scripts/install-items.txt`; root-level browser, release, safety, testing, and Taste assets are listed there. Installer tests exercise full, partial, repeated, and staged installs. |
| Missing repository CI | Remediated | `.github/workflows/ci.yml` runs the runtime commands on Linux, macOS, and Windows with Python 3.13/3.14 and with/without PyYAML. `validate_manifests.py` checks that the workflow still covers the manifest. Branch-protection settings remain outside this repository. |
| Optional strong gate schema | Remediated for run submissions | A manifest inside `skillset-saves/runs/` must declare schema 2 and is checked as schema 2 even when downgraded or missing. Result records reject malformed exit codes and pass/nonzero contradictions and bind scan/render inputs. Schema 1 remains available only for detached legacy package inspection, with an explicit warning. Typed records improve consistency; they do not prove a self-asserted command ran. |
| Freeze/read-only overclaim | Remediated to its achievable boundary | The command analyser covers redirects, wrappers, chained commands, interpreter literals, and unnamed writes. Skill documentation calls the hook advisory-grade and directs hard guarantees to filesystem permissions or a sandbox. Hook faults still fail open by design, so this is accident prevention, not an authenticated security boundary. |
| Concurrent save checkpoints | Remediated | Every mutation holds the project `_write.lock` across read/compare/write, uses per-process atomic temporary files, and records an interrupted publication journal. Concurrency tests cover a single checkpoint winner, revision conflicts, active-pin creation, crash release, and recovery. |
| Engineer circular prerequisite | Remediated | Engineer explicitly treats stack lock as an output of the later commander stage. The design pipeline now declares `requires`/`produces` dependencies, and both the manifest validator and an independent contract test reject a forward dependency. |
| Benchmark reproducibility overclaim | Remediated as historical disclosure | `BENCHMARK.md` has one row per member of the measured 52-skill catalog, labels the inferred `skill-maker` row, labels `audit-improve` unscored, dates the run, and separates model-scored document quality from routing and host observations. It does not claim CI regenerates paid/model measurements. |

## Residual limitations

- Host hook registration, real-host invocation/completion, branch protection,
  and Windows PowerShell behavior require evidence from those external hosts;
  repository tests cannot establish them.
- Advisory hooks cannot authenticate a caller or constrain a process after the
  host starts it. Use OS permissions, containers, or a read-only mount where
  prevention is mandatory.
- Schema-shaped, hashed evidence proves consistency and byte identity, not the
  truth of a semantic claim. Human or controlled-runner review remains required.
- The published benchmark remains a dated historical measurement. A fresh
  scored benchmark needs raw model/tool evidence and is not synthesized from
  the contract suites.
