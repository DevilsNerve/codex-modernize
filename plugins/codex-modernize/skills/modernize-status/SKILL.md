---
name: modernize-status
description: "Report modernization progress, stale artifacts, approval gaps, and secret-file hygiene without changing files. Use to resume a modernization effort and identify the next useful step."
---

# modernize-status

> Adapted for Codex by DevilsNerve from Anthropic code-modernization (Apache-2.0).
> Changed: native skills, argument binding, orchestration, paths, and authorization handling.

Invocation: `$codex-modernize:modernize-status <system-dir>`. These are prompt arguments, not a shell command.

First read [the Codex runtime guide](../../references/runtime.md). It defines
argument binding, path validation, role execution, and how existing user
authorization applies to checkpoints below. Resolve links relative to this
installed `SKILL.md`, not the current working directory.

Start with the runtime helper `status --workspace <workspace-root> --system <system>`; it never creates directories. Inspect the reported artifacts to finish the qualitative review below.


Report where the modernization of `{system}` stands, in one screen. This is a
read-only command — inspect, never modify.

## 1 — Artifact inventory

Check `analysis/{system}/` and `modernized/{system}*/` and build a table — one row per
workflow stage, with the artifact's presence and modification time:

| Stage | Artifacts |
|---|---|
| preflight | `PREFLIGHT.md` (note whether the Check 0 human answers and the Check 6 scope-boundary finding are present) |
| assess | `ASSESSMENT.md`, `ARCHITECTURE.mmd` |
| map | `topology.json`, `TOPOLOGY.html`, `*.mmd`, `extract_topology.*` |
| extract-rules | `BUSINESS_RULES.md`, `DATA_OBJECTS.md` |
| brief | `MODERNIZATION_BRIEF.md` (note whether the approval block is signed) |
| harden | `SECURITY_FINDINGS.md`, `security_remediation.patch` |
| uplift | `DELTA_CATALOG.md`, `BASELINE.md`, `PLAYBOOK.md` (no playbook = the pilot hasn't happened yet — the fan-out must not); `modernized/{system}-uplifted/UPLIFT_NOTES.md` (note per-unit: builds on target? baseline reproduced?) |
| transform | each `modernized/{system}/<module>/` dir — note test presence and whether `TRANSFORMATION_NOTES.md` exists |
| reimagine | `modernized/{system}-reimagined/` — note per-service acceptance tests and the `AGENTS.md` handoff (reimagine's completion markers; it does NOT write `TRANSFORMATION_NOTES.md`) |

## 2 — Staleness

Flag any artifact older than an upstream artifact it derives from:

- `MODERNIZATION_BRIEF.md` older than `ASSESSMENT.md`, `topology.json`,
  or `BUSINESS_RULES.md` → the brief no longer reflects discovery;
  recommend re-running `$codex-modernize:modernize-brief`.
- `MODERNIZATION_BRIEF.md` for a same-stack **uplift** plan that is older
  than `DELTA_CATALOG.md` — or that has no catalog at all — → the phase
  order was decided before (or without) the version deltas that determine
  it; recommend re-running `$codex-modernize:modernize-brief`.
- `TOPOLOGY.html` older than `topology.json` → re-run the injection step
  from `$codex-modernize:modernize-map`.
- Any `TRANSFORMATION_NOTES.md` older than `BUSINESS_RULES.md` → the
  module may not implement the latest rule set; list which.

## 3 — Secrets hygiene

- Does `analysis/.gitignore` exist and cover `SECRETS.local.md` /
  `*.local.patch`? (`git check-ignore` when in a git repo.)
- If `SECRETS.local.md` exists: confirm it is NOT tracked
  (`git ls-files --error-unmatch`, expect failure) and has never been
  committed (`git log --all --oneline -- <path>`, expect empty). If
  either check fails, say so prominently and recommend rotation plus
  history scrubbing.

## 4 — Verdict

End with three lines:
- **Where you are** — the furthest completed stage and roughly how much
  of the system it covers (e.g. "mapped 100%, 2 of 14 modules
  transformed").
- **What's stale** — or "nothing".
- **Next command** — the single most useful next step, with a one-line
  reason.
