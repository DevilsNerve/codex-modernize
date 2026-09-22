---
name: modernize-map
description: "Map legacy dependencies, data lineage, entry points, and persona flows into topology.json, an offline interactive architecture viewer, and small Mermaid diagrams."
---

# modernize-map

> Adapted for Codex by DevilsNerve from Anthropic code-modernization (Apache-2.0).
> Changed: native skills, argument binding, orchestration, paths, and authorization handling.

Invocation: `$codex-modernize:modernize-map <system-dir>`. These are prompt arguments, not a shell command.

First read [the Codex runtime guide](../../references/runtime.md). It defines
argument binding, path validation, role execution, and how existing user
authorization applies to checkpoints below. Resolve links relative to this
installed `SKILL.md`, not the current working directory.


Build a **dependency and topology map** of `legacy/{system}` and render it visually.

The assessment gave us domains. Now go one level deeper: how do the *pieces*
connect? This is the map an engineer needs before touching anything.

## What to produce

Write a one-off analysis script (Python or shell — your choice) that parses
the source under `legacy/{system}` and extracts the four datasets below. Three
principles apply across stacks; getting them wrong produces a misleading map:

1. **Edges live in two places** — direct calls in source, *and* dispatcher/
   router calls whose targets are variables (config tables, route maps,
   dependency injection, dynamic dispatch). Resolve variables against config
   before declaring an edge unresolvable.
2. **The code↔storage join is usually external configuration**, not source —
   job/deployment descriptors map logical names to physical stores.
3. **Entry points usually live in deployment config**, not source — without
   parsing it, every top-level module looks unreachable.

Extract:

- **Program/module call graph** — direct calls (`CALL`, method invocations,
  `import`/`require`) *and* dispatcher calls (`EXEC CICS LINK/XCTL`, DI
  container wiring, framework routing, reflection/factory). Resolve variable
  call targets against route tables, copybooks, config, or constant pools.
- **Data dependency graph** — which modules read/write which data stores,
  joined through the relevant config: `SELECT…ASSIGN TO` ↔ JCL `DD` (batch
  COBOL), `EXEC CICS READ/WRITE…FILE()` ↔ CSD `DEFINE FILE` (CICS online),
  `EXEC SQL` table refs (embedded SQL), ORM annotations/mappings (Java/.NET),
  model files (Node/Python/Ruby). Include UI/screen bindings (BMS maps, JSPs,
  templates) — they're dependencies too.
- **Entry points** — whatever the stack's outermost invoker is, read from
  where it's defined: JCL `EXEC PGM=` and CICS CSD `DEFINE TRANSACTION`
  (mainframe), `web.xml`/route annotations/route files (web), `main()`/argv
  parsing (CLI), queue/scheduler subscriptions (event-driven).
- **Dead-end candidates** — modules with no inbound edges. **Only meaningful
  once all the entry-point and call-edge types above are in the graph.**
  Suppress the dead claim for anything that could be the target of an
  unresolved dynamic call. A grep-only graph will mark most dispatcher-driven
  modules (CICS programs, Spring controllers, ORM-bound DAOs) dead when they
  aren't.

If the source is fixed-column (COBOL columns 8–72, RPG, etc.), slice the
code area and strip comment lines before regex matching, or you'll match
sequence numbers and commented-out code.

Save the script as `analysis/{system}/extract_topology.py` (or `.sh`) so it can be
re-run and audited. Have it write a machine-readable
`analysis/{system}/topology.json` and print a human summary. Run it; show the
summary (cap at ~200 lines for very large estates).

`topology.json` must follow this schema — it feeds the interactive viewer:

```json
{
  "system": "<display name>",
  "root": {
    "id": "sys", "name": "<system>", "kind": "system",
    "children": [
      { "id": "dom:<domain>", "name": "<Domain>", "kind": "domain",
        "children": [
          { "id": "<MODULE>", "name": "<MODULE>", "kind": "module",
            "language": "cobol", "loc": 1234, "file": "src/MODULE.cbl" }
        ] },
      { "id": "dom:data", "name": "Data stores", "kind": "domain",
        "children": [
          { "id": "ds:<NAME>", "name": "<NAME>", "kind": "datastore" }
        ] }
    ]
  },
  "edges": [
    { "source": "<id>", "target": "<id>", "kind": "call" }
  ],
  "entryPoints": ["<id>", "..."],
  "deadEnds": ["<id>", "..."],
  "observations": ["<architect observation>", "..."],
  "flows": [
    { "name": "<business flow>", "persona": "<who experiences it>",
      "description": "<one sentence, plain language>",
      "steps": [
        { "label": "<business-language step>", "nodes": ["<id>", "<id>"] }
      ] }
  ]
}
```

- Group leaf modules under `domain` containers (use the domains from
  `$codex-modernize:modernize-assess` if available). Leaf kinds: `module`, `datastore`,
  `job`, `screen`. `loc` drives circle size — include it for modules.
- Edge kinds: `call` (direct), `dispatch` (dynamic/router), `read`,
  `write`. Every edge endpoint must be a leaf id that exists in the tree.
- `deadEnds`: the dead-end candidates from the extraction, rendered with
  a dashed outline in the viewer. Apply the suppression rules above —
  anything that could be the target of an unresolved dynamic call does
  NOT belong here; record that uncertainty in `observations` instead.
- **Datastore ids and names must be logical identifiers** — DD name,
  dataset name, table/schema name, at most host:port. If the resolved
  config value is a URL or DSN, strip userinfo and credential query
  params before it goes anywhere in topology.json: the file gets
  committed and the viewer displays names verbatim. Never copy raw
  config values into `observations`.
- `observations`: 3–7 architect observations — tight coupling clusters,
  single points of failure, service-extraction candidates, data stores
  with too many writers, dispatch targets the extraction could not
  resolve.
- `flows` is the **persona walkthrough** section — see below.

## Persona flows

Trace **2–4 end-to-end business flows**, each anchored to a persona —
the people who experience the system, not the people who maintain it
(e.g. for a benefits system: the claimant, the caseworker, the auditor;
for billing: the customer, the billing operator). For each flow:

- `name` + one-sentence `description` in plain business language —
  something a steering committee member relates to ("a claimant files a
  weekly claim"), not a data-flow label ("CLM batch ingest").
- `steps`: 3–8 steps, each with a business-language `label` and the
  `nodes` (programs + data stores) that implement that step, in
  execution order.

This is the bridge between the technical map and non-technical
stakeholders: the same diagram answers "which program does X" for
engineers and "what happens when someone files a claim" for everyone else.

## Render

`analysis/{system}/TOPOLOGY.html` is an **interactive map**: a zoomable
circle-pack of the whole system (domains as containers, modules sized by
LOC) with dependency edges, search, per-node detail sidebar, edge-kind
toggles, and a flow-walkthrough mode that plays each persona flow as a
numbered path. Build it from the template that ships with this plugin —
do not hand-write the viewer:

Resolve the installed plugin root from this skill file as described in the
[runtime guide](../../references/runtime.md), then run its helper with actual
absolute paths:

```text
python3 <plugin-root>/scripts/modernize.py topology --workspace <workspace-root> --system <system>
```

The helper validates the topology schema and references, escapes embedded JSON
against script-tag breakout, and creates `analysis/{system}/TOPOLOGY.html`.
The viewer includes its D3 subset and works offline. Report missing bundled
assets as an installation error; do not replace the viewer with a new implementation.

Mermaid stays for **small, exportable** diagrams. Generate standalone
`.mmd` files for reuse in docs and PRs — but keep each under ~40 edges;
collapse to domain level if the full graph is bigger (dense Mermaid
becomes unreadable, which is exactly what the interactive map is for):

- `analysis/{system}/call-graph.mmd` — domain-level `graph TD`, entry points
  highlighted
- `analysis/{system}/data-lineage.mmd` — `graph LR`, programs → data stores,
  read vs write marked
- `analysis/{system}/critical-path.mmd` — `flowchart TD` of the primary flow
  from `flows`, annotated with p50/p99 wall-clock if telemetry is
  available (see `$codex-modernize:modernize-assess` Step 4)

## Present

Tell the user to open `analysis/{system}/TOPOLOGY.html` in a browser, and to
try: search for a module, click it to see its connections, and pick a
persona flow from the walkthrough dropdown.
