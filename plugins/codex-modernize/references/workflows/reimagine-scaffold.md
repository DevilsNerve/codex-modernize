# Service scaffolding orchestration

> Adapted by DevilsNerve from Anthropic's Apache-2.0 reimagine-scaffold workflow.
> Changed: native Codex workers with an equivalent sequential path.

Confirm that the concrete architecture, P0 scope, and behavior decisions are
authorized. Enumerate every service with its responsibilities and assigned rule
IDs. Validate unique single-component service names and non-overlapping real
output paths. Provide the spec, architecture, and scaffolder role to each worker.

Each worker owns only its service directory. The caller owns root manifests,
shared contracts, lockfiles, and integration. Use available worker slots or process
services sequentially; do not drop services because there are more than three.

Require an executable acceptance test for each assigned rule. Unimplemented rules
may be skipped/expected-failure in a scaffold, but must remain listed as pending.
Report the build/test commands actually executed and every blocker. Re-run suites
and integration checks in the calling session. A scaffold with pending rules is
not a finished equivalent implementation. Write the AGENTS.md handoff after
inspection of the generated tree.
