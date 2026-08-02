verified: 2026-07-14 · sources: landscape §3 (Claude Code), example-corpus §4/§5, concepts M4 (capability tier)

# Harness profile: Claude Code

**Default model family:** Claude. **Capability tier: T3** (tool restrictions + dynamic injection + hooks).

## Skill directories + precedence
- `~/.claude/skills/`, `.claude/skills/`, plugins, enterprise config. Nested dirs give scoped names (`apps/web:deploy`). Live-reload on edit.
- Slash commands merged into skills; `.claude/commands/` still works; **skill wins on a name clash**.
- Does NOT read the portable `.agents/skills/` — bridge by mirroring the canonical source into `.claude/skills/`.

## Frontmatter dialect (beyond spec core)
`when_to_use`, `argument-hint`/`arguments` (`$ARGUMENTS`, `$1`…, named), `disable-model-invocation`, `user-invocable`, `allowed-tools`/`disallowed-tools`, `model`, `effort`, `context: fork`, `agent`, `hooks`, `paths` (glob-gated activation), `shell`; dynamic injection via `` !`cmd` ``.

## Budgets
Skill listing ≈ 1% of context. Per-entry description text capped at **1,536 chars** (deviation from spec's 1,024). Post-compaction re-attach budget 25k tokens.

## Invocation mechanics
Implicit (description match) + explicit (slash command / `user-invocable`). Arguments via `$ARGUMENTS`, positional `$1`…, or named — verified for Claude Code.

## Enforcement surfaces
Permission modes/rules + PreToolUse/PostToolUse hooks are the real tool restriction; plus `paths` glob-gating, `context: fork` isolation, `` !`cmd` `` runtime injection. **Verified 2026-07-14:** `allowed-tools` in SKILL.md frontmatter is advisory permission-smoothing only — parsed, never enforced (https://github.com/anthropics/claude-code/issues/37683); documented syntax is comma-separated or array. Read-only stances therefore rest on prose + permission rules/hooks, not skill frontmatter.

## Capability tier justification
**T3** — tool restriction via permission rules + hooks (T2; skill-frontmatter `allowed-tools` is advisory only) AND runtime dynamic injection + hooks (T3). The reference implementation of the spec's rich end.

## Headless (evals)
Legacy captures use `claude -p --output-format json` (+ `--json-schema`, `--max-budget-usd`); output shape varies (single result object vs event array), so parse both. Controlled runs use `stream-json`, retain structured init evidence, and reject malformed/empty/provider-error streams before grading.

**Isolation contract observed on Claude Code 2.1.209 (2026-07-14):** a successful `--safe-mode` launch is not itself proof that customizations are absent. The raw sentinel combines `--safe-mode`, `--disable-slash-commands`, the CLI's accepted-but-undocumented empty argument to `--setting-sources`, `--strict-mcp-config` with an explicit empty MCP config, no persistence, and an explicit tool/permission envelope. Its exact-version adapter profile requires structured init to match the verified four-agent built-in roster, zero skills/slash commands/plugins/MCP servers, exactly `Read,Grep,Glob`, and `plan`; a deliberate project-agent canary must also remain absent before experimental arms run. The CLI reference documents the named setting-source values but not the empty form, so any version other than 2.1.209 fails preflight until this behavior and the built-in roster are re-probed and a reviewed profile is added. Provider/admin layers remain declared unknowns. Put the positional print prompt immediately after `-p` before variadic options such as `--tools`/`--mcp-config`, or the CLI can consume it as another option value. Anthropic documents the underlying [`--setting-sources`, `--strict-mcp-config`, system-prompt, and tool controls](https://code.claude.com/docs/en/cli-usage) and the read-only [`plan` permission mode](https://code.claude.com/docs/en/permission-modes). The first measurement slice supports only an inline `--append-system-prompt` treatment, bound by content/configuration hashes; settings, plugin, MCP, and agent treatments remain disabled until the adapter can prevalidate them and verify effective load evidence. Automatic fallback is never enabled.

## Native version and update controls

verified: 2026-07-15 · primary sources: [advanced setup](https://code.claude.com/docs/en/setup), [environment variables](https://code.claude.com/docs/en/env-vars), [settings table](https://code.claude.com/docs/en/settings#available-settings)

- Native installations check for updates at startup and periodically, install them in the background, and activate them on the next process start. On macOS/Linux, the managed launcher points into `~/.local/share/claude/versions/`; from 2.1.207 onward, a custom launcher is preserved and newly installed siblings do not determine which version it launches.
- `DISABLE_AUTOUPDATER=1` disables automatic background updates while leaving manual update/install commands available. `DISABLE_UPDATES=1` blocks background and manual update/install paths. The current environment-variable reference explicitly documents both names and the value `1`.
- For controlled measurement, set both variables in the frozen launch environment. Their presence proves only which environment the runner requested; Anthropic documents no independent runtime attestation that the internal updater honored them. Bind executable identity separately through the direct versioned path, reported version, and binary hash.
- Releases from 2.1.89 onward publish a detached-signed manifest containing platform SHA-256 values. Verify the selected binary against that manifest and the documented release-key fingerprint before qualification, then record the manifest digest, signature result, fingerprint, and binary digest. Hash the selected version binary/package rather than the parent `versions/` directory so installation of an unused sibling is not misclassified as execution drift.
- `minimumVersion` constrains updates but does not block startup. The primary [`requiredMaximumVersion` and `requiredMinimumVersion` settings rows](https://code.claude.com/docs/en/settings#available-settings) explicitly mark both fields managed-only, state that older versions predating each setting ignore it, and state that `claude update`, `claude install`, and `claude doctor` remain available outside the allowed range for recovery. Invalid managed values are stripped and fail open. On macOS, file-based managed policy lives under `/Library/Application Support/ClaudeCode/`; managed sources outrank command, project, and user settings and therefore remain active independently of a fresh user config home.
- Treat exact managed version bounds as optional dedicated-host defense-in-depth, not a portable baseline. Before relying on them, use a zero-provider-call canary in a disposable or exclusively controlled host to prove that the in-range binary passes the startup version gate, an adjacent version refuses before network/model execution, invalid policy is surfaced by the runner's own gate, and the complete highest-precedence managed-policy source and hash are observable. Do not mutate a shared machine's policy merely to run an experiment.

## Serving over MCP (ph-mcp-server v0 — verified 2026-07-14)
- Register: `claude mcp add prompt-harness -- node <repo>/packages/mcp-server/dist/index.js --repo <repo>` (local scope by default; `-s user` for all projects).
- Both skills surface as slash commands `/mcp__prompt-harness__<skill>` (verified via the headless init event's `slash_commands`); prompt arguments enforce the grammar — `input` is required, arg-less invocation fast-fails.
- References/styles are MCP resources at `ph://references/<bundled-name>` and `ph://styles/<name>.yaml`, reachable through the native resource tools (ListMcpResourcesTool / ReadMcpResourceTool).
- Hot updates: the server re-reads the checkout per request — edits serve immediately with no reinstall; stdio mode additionally pushes prompts/resources `list_changed` (debounced, advisory).
- Trust model: read-only server over a local checkout, stdio default. `--http <port>` is stateless JSON bound to 127.0.0.1, no auth — remote access via SSH tunnel/tailnet only.
- `install.sh` remains the offline/primary delivery; MCP serving is the hot-sync path (production-architecture wave-3 v0, owner-pulled-forward).

## Spike-question ledger (resolutions 2026-07-14; details in docs/research/spike-findings.md)
- Q4 RESOLVED: no listing crowd-out observed; edits to an existing installed skill hot-reload mid-session, brand-new skill dirs need a restart (https://github.com/anthropics/claude-code/issues/38707).
- Q5 RESOLVED: `allowed-tools` does NOT restrict — advisory only (see Enforcement surfaces above).
- Q6 RESOLVED: 6/6 trigger accuracy at MVP + 9/9 anti-probes (both harnesses) at the audit-fix pass.
- Q8 RESOLVED: copy-based install; symlink mode never attempted (self-containment per spec).
- Deviations to design around: `name` optional (dir-derived); description cap 1,536 vs spec 1,024; no `.agents/skills/`; no native `AGENTS.md` ([issue #6235](https://github.com/anthropics/claude-code/issues/6235) open) — bridge via `@AGENTS.md` import in `CLAUDE.md` or a symlink.
