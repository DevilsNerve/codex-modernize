# Porting notes

The upstream source is Anthropic's `code-modernization` plugin at revision
`db467cc56673fc963ca418b4165c688dfbe77007`. The original repository license
(`LICENSE.md`) is preserved byte-for-byte. The distributable plugin carries all
applicable attribution and license files independently of this repository.

| Upstream component | Codex implementation |
| --- | --- |
| Ten command Markdown files | Ten discoverable `skills/modernize-*/SKILL.md` entrypoints with `agents/openai.yaml` metadata |
| Eight named agent definitions | Eight role references used with actual native tools, or in sequential passes |
| Six Workflow-runtime JavaScript files | Six native orchestration guides; a Python helper makes migration scheduling and circuit checks deterministic |
| Positional argument expansion | Explicit binding of prompt arguments, including multiword visions and version strings |
| Plugin-root interpolation | Resource paths resolved from the installed skill file |
| Claude plugin manifest | Portable `plugin.json`, Codex compatibility manifest, repo marketplace |
| Legacy context handoff | Generated `AGENTS.md` for rebuilt systems |
| File-tool permission recipe | Existing Codex host policy plus real-path validation and explicit output ownership |
| Inline topology-injection snippet | Reusable schema-validating helper; offline viewer with native keyboard controls |
| Uplift catalog behind execution checkpoint | Explicit `--catalog-only` path usable before the brief |
| Unknown dependency treated as completed | Unknown dependencies rejected unless listed as completed |
| Automatic pauses at every checkpoint | Existing scoped authorization honored; missing decisions remain gates |

The specialized analysis content, Rule Cards, Delta Cards, preflight checks,
persona flows, baseline distinctions, pilot discipline, patch reviews, and
behavior-contract requirements are retained. Provider-specific workflow scripts
are not shipped as if Codex could execute their unsupported runtime.

## Runtime requirements

- Codex plugin/skill support; installation and discovery verified with CLI 0.155.1.
- Python 3.10+ for standard-library helpers. Python, Git, and available build
  tools run on the host; no new account or model API configuration is required.
- Git is needed for repository installation and stronger credential-quarantine
  checks. Non-Git projects use a private workspace-specific quarantine directory.
- Stack-specific build tools are required for actual migration validation.
- Native subagents and network access are optional and remain subject to host policy.
- The viewer is a local, standalone HTML artifact, not an MCP app or web service.

## Validation scope

`scripts/validate.py` checks distributable structure, both manifest identities,
skill discovery metadata, bundled references, licenses, and helper behavior.
The helper tests include realistic failures and source/output preservation.
Playwright opens generated files and exercises search, keyboard selection,
details, flows, edge controls, and malicious labels without network requests.
`scripts/check_codex.py` uses the real app-server `skills/list` API to confirm all
ten installed skills are enabled and their bundled paths resolve.

These checks establish packaging, discovery, and helper/viewer behavior. They do
not establish a completed real-world COBOL, Java, C++, or .NET migration, or claim
universal behavioral equivalence. Each modernization must run its own builds,
baseline comparisons, and acceptance checks. The Windows and macOS host-specific
build/toolchain paths require validation in the user's environment.

## Maintaining the package

Keep `plugin.json` and `.codex-plugin/plugin.json` versions and interface metadata
in sync. Codex installs a cached copy; after changing the source, update its
version/cachebuster and reinstall, then start a new session. Changing an open
session's files does not prove that the installed skills were refreshed.

Use `scripts/validate.py` and the viewer tests before publishing. Preserve the
per-file adaptation notices, upstream revision, owner's license, and D3 license
when updating from upstream. Do not reintroduce provider-specific tool names or
assume that a role prompt enforces operating-system permissions.

References: [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins),
[OpenAI skills](https://developers.openai.com/codex/skills), and
[the pinned upstream source](https://github.com/anthropics/claude-plugins-official/tree/db467cc56673fc963ca418b4165c688dfbe77007/plugins/code-modernization).
