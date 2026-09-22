# Portfolio assessment orchestration

> Adapted by DevilsNerve from Anthropic's Apache-2.0 portfolio-assess workflow.
> Changed: native Codex scheduling and artifact-based resumption.

Enumerate actual immediate subdirectories of the requested parent with filesystem
APIs. Treat names as data, quote paths, and do not follow unexpected links beyond
the requested portfolio. Tell the user how many systems will be measured.

For each system use the legacy-analyst role to obtain SLOC, file/language counts,
complexity, dependency freshness, documentation coverage, and confidence. Preserve
the measuring tool and raw numeric inputs. The complexity index is uniformly
`2.94 * (SLOC / 1000) ** 1.10`; it is neither time nor cost. Missing measurements
remain null/unmeasured, never zero.

Use bounded native concurrency where available, otherwise survey sequentially.
Checkpoint completed rows and source revision/measurement metadata in
`analysis/portfolio-progress.json`. Resume only rows whose inputs still match;
there is no opaque workflow-run cache. A failed system does not erase successful
rows. Render the heatmap and sequencing recommendation described by assess.
