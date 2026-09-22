# Dependency-aware migration batches

> Adapted by DevilsNerve from Anthropic's Apache-2.0 uplift-migrate workflow.
> Changed: portable Python batch planner, native Codex workers, and strict dependency validation.

The pilot must build, have recorded baseline evidence, and have produced
`PLAYBOOK.md`. Show its diff and discoveries before scaling. Existing authorization
may cover continuation; a new behavior/scope decision still needs the user.

Write a plan in `analysis/<system>/migration-plan.json`:

```json
{
  "units": [
    {"name": "Core", "path": "src/Core", "deps": ["Pilot"]},
    {"name": "Api", "path": "src/Api", "deps": ["Core"]}
  ],
  "completed": ["Pilot"],
  "results": [],
  "lastBatch": [],
  "batchSize": 4
}
```

`completed` names only previously built dependencies outside `units`. Never
guess that a missing dependency is complete. Unit names and paths must be unique;
nested/overlapping directories and cycles require a different scope or an in-session
coordinated cut. A dependency and its consumer never migrate in the same batch.

Run the read-only helper with the actual plugin and workspace paths:

```text
python3 <plugin-root>/scripts/modernize.py batch --workspace <workspace> --system <system> --plan <plan.json>
```

Use `nextBatch`, capped by available worker slots, to assign one uplift-migrator
role per unit. The proven playbook is the recipe. Shared files remain with the
caller. Serialize builds when caches or generated outputs overlap. With no
delegation, use the same plan but process the selected units sequentially.

After each batch, append one result per unit and set `lastBatch` to that batch:

```json
{"unit": "Core", "buildRan": true, "built": true,
 "buildCommand": "dotnet build src/Core/Core.csproj", "playbookGaps": [],
 "sharedFileNeeds": []}
```

Inspect command output before recording success. Replace a unit's prior result
when a deliberate retry finishes; never retain duplicate/conflicting results.
Fold gaps into the playbook. If fewer than two-thirds of the last batch built,
the helper reports `circuitOpen: true` and returns no next batch. Prove a repaired
playbook on a failed unit in-session, update its actual result, and only then
resume. Record the correction trial as the new `lastBatch`, keeping all other
previous results. Set `retryUnits` to the remaining failed unit names whose
dependencies are built; this schedules an explicit retry without erasing failed
evidence. Remove a name from `retryUnits` once its replacement result succeeds.
Do not clear a failed result to make the circuit pass. After fully successful
batches, `batchSize` may grow from four to eight to sixteen, still capped by
available workers; never increase it in response to failures.

The output separately lists `failedUnits`, `blockedUnits`, and `remainingUnits`;
none is complete. After all are empty, run the entire build and baseline comparison.
`nextBatch` is scheduling advice, not a permission grant or sandbox. The helper
checks source/output separation but cannot police arbitrary worker shell commands.
