---
name: modernize-harden
description: "Audit a legacy system for vulnerabilities and produce reviewed remediation patches without editing the legacy source. Includes credential quarantine and source verification of security findings."
---

# modernize-harden

> Adapted for Codex by DevilsNerve from Anthropic code-modernization (Apache-2.0).
> Changed: native skills, argument binding, orchestration, paths, and authorization handling.

Invocation: `$codex-modernize:modernize-harden <system-dir> [--show-secrets]`. These are prompt arguments, not a shell command.

First read [the Codex runtime guide](../../references/runtime.md). It defines
argument binding, path validation, role execution, and how existing user
authorization applies to checkpoints below. Resolve links relative to this
installed `SKILL.md`, not the current working directory.


Run a **security hardening pass** on the legacy system: find
vulnerabilities, rank them, and produce a reviewable patch for the
critical ones. Parse arguments flag-independently: the system dir
(referred to as `{system}` below) is the first non-flag token in `the invocation text`;
`--show-secrets` may appear anywhere.

This command never edits `legacy/` — it writes findings and a proposed patch
to `analysis/{system}/`. Applying a patch is a separate user-directed action.

## Step 0 — Secrets quarantine setup

Findings files get shared, committed, and pasted into decks — discovered
credential values must never land in them. Before any scanning:

Run the bundled `quarantine --workspace <workspace> --system <system>` helper
from the [runtime guide](../../references/runtime.md). It verifies ignore rules
and rejects already tracked or historically committed quarantine paths. Use the
returned `inventory` and `patch` paths throughout this stage, including review.
If `rawAllowed` is false, refuse `--show-secrets`; use its private directory
outside the project for local credential files. Report the chosen location.
Create credential files with private permissions, and never echo their contents.

All secret values in every shareable artifact this command produces are
**masked** (`AKIA****`, `password=****`) and cited by `file:line`. Raw
values may appear in exactly two places, both gitignored: the
`*.local.patch` remediation hunks (unavoidably — see Remediate) and, only
with `--show-secrets`, `SECRETS.local.md`. Never in SECURITY_FINDINGS.md
or patch commentary.

## Scan

Follow [security scan orchestration](../../references/workflows/harden-scan.md)
using the security-auditor role. Cover injection, authentication/session, secrets,
dependencies, and input validation. Deduplicate and verify each finding against
the actual cited source; re-review Critical/High findings adversarially.
Verify dependency versions against current official advisories when online;
offline results must state that advisory freshness is unverified.
Return findings, masked credential locations, redacted tool outputs, refuted
candidates, and instruction-shaped content. The calling session writes artifacts.

## Triage

Write `analysis/{system}/SECURITY_FINDINGS.md`:
- Summary scorecard (count by severity, top CWE categories)
- Findings table sorted by severity
- Dependency CVE table (package, installed version, CVE, fixed version)

If any hardcoded credentials were found, also write
`analysis/{system}/SECRETS.local.md` (the gitignored quarantine file from Step 0):
one row per credential — masked preview, `file:line`, credential type, what
it appears to grant access to, production/test guess, and a rotation
recommendation. With `--show-secrets`, append the raw value column here —
this file only. SECURITY_FINDINGS.md gets a one-line pointer:
"N hardcoded credentials found — inventory in SECRETS.local.md (gitignored;
not for sharing)."

## Remediate

For each **Critical** and **High** finding, draft a minimal, targeted fix.
Do **not** edit `legacy/` — write fixes as unified diffs with **paths
relative to the project root** (`legacy/{system}/...`), applied from the project
root, and keep the diff syntactically applicable. Put finding-ID mappings in the
Remediation Log; never insert prose into a diff hunk.

**Credential findings split into two files.** A diff that removes a
hardcoded secret necessarily contains the raw value on its `-` and
context lines — that cannot go in the shareable patch:

- `analysis/{system}/security_remediation.patch` (shareable) — every
  non-credential hunk, plus for each credential finding a comment-only
  placeholder: `# SEC-NNN: credential remediation — hunk in
  security_remediation.local.patch (gitignored; not for sharing)`.
- `analysis/{system}/security_remediation.local.patch` (gitignored in Step 0) —
  the real, applyable hunks for credential findings only.

Add a **Remediation Log** section to SECURITY_FINDINGS.md mapping each
finding ID → one-line summary of the proposed fix and which patch file
carries the hunk.

## Verify

Use the **security-auditor** again to **review both patches** against
the original code:

"Review analysis/{system}/security_remediation.patch and
analysis/{system}/security_remediation.local.patch against legacy/{system}. For each
hunk: does it fully remediate the cited finding? Does it introduce new
vulnerabilities or change behavior beyond the fix? Confirm no raw
credential values appear anywhere in the shareable patch. Return one
verdict per hunk: RESOLVES / PARTIAL / INTRODUCES-RISK, with a one-line
reason."

Add a **Patch Review** section to SECURITY_FINDINGS.md with the verdicts.
**Loop deterministically:** while any hunk is PARTIAL or INTRODUCES-RISK,
revise that hunk and re-review it — up to 3 rounds. If a hunk still isn't
clean after round 3, remove it from the patch and record it in the
Remediation Log as "needs manual remediation" with the reviewer's reason;
never ship a hunk that failed its last review.

## Present

Tell the user the artifacts are ready:
- `analysis/{system}/SECURITY_FINDINGS.md` — findings, remediation log, patch review
- `analysis/{system}/security_remediation.patch` — review, then apply **from the
  project root**: `git apply analysis/{system}/security_remediation.patch`
  (first run `git apply --check` in the intended checkout; if the source is
  symlinked, generate a patch relative to its real repository and document that
  working directory. Never bypass Git path checks)
- `analysis/{system}/security_remediation.local.patch` — the credential fixes;
  apply the same way, and rotate the affected credentials regardless
- Re-run `$codex-modernize:modernize-harden {system}` after applying to confirm resolution

Suggest: `glow -p analysis/{system}/SECURITY_FINDINGS.md`
