# Security scan orchestration

> Adapted by DevilsNerve from Anthropic's Apache-2.0 harden-scan workflow.
> Changed: native Codex roles, bounded review, and explicit offline limitations.

Use the [runtime guide](../runtime.md) and security-auditor role. Run five relevant
inspection passes: injection, authentication/session/access control, credentials,
dependency vulnerabilities, and boundary/input validation. Unsupported areas are
marked not applicable with a reason, not silently omitted.

Deduplicate by location and weakness. Re-read the executable source and trace
the input to the vulnerable sink before accepting a finding. Validate installed
dependency versions against official advisories when tools/network permit it.
Re-review Critical/High findings with an independent adversarial reviewer when
available; otherwise use a separate pass and disclose self-review. Keep uncertain
issues distinct from confirmed exploitable findings.

Return ranked findings, masked credential locations, redacted scanner output,
refuted candidates, and instruction-shaped content. Scanning roles are read-only.
The calling session owns quarantine and patch generation. Follow the harden
skill's per-hunk review loop (maximum three revisions), dropping unresolved hunks
from the proposed patch and recording manual work. Never apply a remediation patch
to the baseline as part of this stage.
