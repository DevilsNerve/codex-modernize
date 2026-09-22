---
name: modernize-reimagine
description: "Rebuild a legacy system from extracted business intent: specification, reviewed target architecture, service scaffolds, acceptance tests, and an AGENTS.md handoff."
---

# modernize-reimagine

> Adapted for Codex by DevilsNerve from Anthropic code-modernization (Apache-2.0).
> Changed: native skills, argument binding, orchestration, paths, and authorization handling.

Invocation: `$codex-modernize:modernize-reimagine <system-dir> <target-vision>`. These are prompt arguments, not a shell command.

First read [the Codex runtime guide](../../references/runtime.md). It defines
argument binding, path validation, role execution, and how existing user
authorization applies to checkpoints below. Resolve links relative to this
installed `SKILL.md`, not the current working directory.


The first token of `the invocation text` is the system dir (`{system}`); **everything
after it is the target vision** — it is usually multiple words, so do not
truncate it to one token. Below, `<vision>` means that full remainder.

**Reimagine** `legacy/{system}` as: <vision>

This is not a port — it's a rebuild from extracted intent. The legacy system
becomes the *specification source*, not the structural template. This command
orchestrates a multi-agent team with explicit human checkpoints.

**The brief is binding — read it first.** If `analysis/{system}/MODERNIZATION_BRIEF.md`
exists, this reimagine is executing one of its phases: read it before doing
anything below. Find the phase that names this command with a scope matching
`{system}` and <vision>, and treat that phase's **scope, entry criteria, exit
criteria, and any edits the user made to it** as binding on the phases below
— on top of, never instead of, this command's own two HITL checkpoints.
Entry criteria are *gates*, not context: if one is not met (a prior phase's
exit criteria, an SME sign-off the brief requires), meeting it **is** the
next step — do not proceed past it and do not silently re-plan around it. If
the brief exists but no phase matches, stop and ask which phase this is. The
user steers execution by editing the brief; a brief the execution command
never reads cannot steer anything.

## Phase A — Specification mining (parallel agents)

Use these three specialist passes; report parallel execution only if they actually run concurrently:

1. **business-rules-extractor** — "Extract every business rule from legacy/{system}
   into Given/When/Then form. Output to a structured list I can parse."

2. **legacy-analyst** — "Catalog every external interface of legacy/{system}:
   inbound (screens, APIs, batch triggers, queues) and outbound (reports,
   files, downstream calls, DB writes). For each: name, direction, payload
   shape, frequency/SLA if discernible. Mask any credential embedded in
   endpoints or payload examples per your secret-handling rules."

3. **legacy-analyst** — "Identify the core domain entities in legacy/{system} and
   their relationships. Return as an entity list + Mermaid erDiagram."

Collect results. Write `analysis/{system}/AI_NATIVE_SPEC.md` containing:
- **Capabilities** (what the system must do — derived from rules + interfaces)
- **Domain Model** (entities + erDiagram)
- **Interface Contracts** (each external interface as an OpenAPI fragment or
  AsyncAPI fragment)
- **Non-functional requirements** inferred from legacy (batch windows, volumes)
- **Behavior Contract** (the Given/When/Then rules — these are the acceptance tests)

Credential values are masked everywhere in the spec; connection details
appear as env-var placeholders (`${DATABASE_URL}`), never literals.

## Phase B — HITL checkpoint #1

Present the spec summary. If not already specified, ask the user **one focused question**: "Which of
these capabilities are P0 for the reimagined system, and are there any we
should deliberately drop?" Reuse an existing answer; otherwise wait for the decision and record it in the spec.

## Phase C — Architecture (single agent, then critique)

Design the target architecture for "<vision>":
- Mermaid C4 Container diagram
- Service boundaries with rationale (which rules/entities live where)
- Technology choices with one-line justification each
- Data migration approach from legacy stores

Then use **architecture-critic**: "Review this proposed architecture for
<vision> against the spec in analysis/{system}/AI_NATIVE_SPEC.md. Identify over-engineering,
missed requirements, scaling risks, and simpler alternatives." Incorporate
the critique. Write the result to `analysis/{system}/REIMAGINED_ARCHITECTURE.md`.

## Phase D — HITL checkpoint #2

Present the architecture and **verify that the architecture is covered by the user's authorization before scaffolding** (use the available user-interaction tools).

## Phase E — Parallel scaffolding

This phase runs only **after** the user approved the architecture in
Phase D — the approval is what authorizes the build-out.

Follow [service scaffolding](../../references/workflows/reimagine-scaffold.md).
Use the scaffolder role once per service in the approved architecture.
Each owns only `modernized/{system}-reimagined/<service>/`; shared manifests
are owned by the calling session. Run all services, in bounded batches or
sequentially when delegation is unavailable. Return exact test commands,
passing/failed/skipped counts, pending rule IDs, and blockers per service.
Run the actual acceptance suites yourself before reporting completion.

Report progress and actual test results: total tests, passing (scaffolded
behavior), pending (rule IDs awaiting implementation), and failures.

## Phase F — Knowledge graph handoff

Write `modernized/{system}-reimagined/AGENTS.md` — the persistent context file for
the new system, containing: architecture summary, service responsibilities,
where the spec lives, how to run tests, and the legacy→modern traceability
map. This file IS the knowledge graph that future agents and engineers will
load — and it gets committed: connection details and credentials appear
only as env-var names with a pointer to where they're provisioned, never
as values.

Report: services scaffolded, acceptance tests defined, % behaviors with a
home, location of all artifacts.
