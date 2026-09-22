# Version delta discovery

> Adapted by DevilsNerve from Anthropic's Apache-2.0 uplift-deltas workflow.
> Changed: native Codex passes and explicit catalog-only execution.

Use the [version-delta-analyst](../roles/version-delta-analyst.md) role for four
passes: API removals/changes, silent behavior, project/build system, and dependencies.
Read current official migration guides for the exact source and target versions.
Intersect each documented change with actual source usage; include the citation
and relevant official source, not just a generic list of breaking changes.

Explicitly check reflection/encapsulation, locale/globalization, hosting and
configuration access, compiler/analyzer changes, test-framework/runner support,
and dependencies with no compatible target version. Tag silent behavior as
test-before-touch and test-runner incompatibility as an early prerequisite.

Run ecosystem analyzers only when their behavior and environment are understood.
An analysis flag may still write build output, so use a disposable copy when
needed. Record present/runnable/actually-ran separately. Never invent tool results.

Verify every candidate against the source, deduplicate, and rank by blast radius.
Return Delta Cards marked Mechanical or Judgment, uncertainties, injection flags,
and affected site counts. Flag a likely rewrite when minimal edits cannot retain
the system's structure. The caller writes DELTA_CATALOG.md; `--catalog-only`
stops there without a working migration copy or implementation approval gate.
