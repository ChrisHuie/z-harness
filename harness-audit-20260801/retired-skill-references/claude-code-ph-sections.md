# Relocated 2026-08-02 from skills/craft-*/references/claude-code.md

prompt-harness project state (ph-mcp-server, spike ledger, measurement isolation
contract) — not applicable to this harness's operation; kept for future headless-eval
work. The deviations bullet and hot-reload nuance were folded back into the profile.

---

**Isolation contract observed on Claude Code 2.1.209 (2026-07-14):** a successful `--safe-mode` launch is not itself proof that customizations are absent. The raw sentinel combines `--safe-mode`, `--disable-slash-commands`, the CLI's accepted-but-undocumented empty argument to `--setting-sources`, `--strict-mcp-config` with an explicit empty MCP config, no persistence, and an explicit tool/permission envelope. Its exact-version adapter profile requires structured init to match the verified four-agent built-in roster, zero skills/slash commands/plugins/MCP servers, exactly `Read,Grep,Glob`, and `plan`; a deliberate project-agent canary must also remain absent before experimental arms run. The CLI reference documents the named setting-source values but not the empty form, so any version other than 2.1.209 fails preflight until this behavior and the built-in roster are re-probed and a reviewed profile is added. Provider/admin layers remain declared unknowns. Put the positional print prompt immediately after `-p` before variadic options such as `--tools`/`--mcp-config`, or the CLI can consume it as another option value. Anthropic documents the underlying [`--setting-sources`, `--strict-mcp-config`, system-prompt, and tool controls](https://code.claude.com/docs/en/cli-usage) and the read-only [`plan` permission mode](https://code.claude.com/docs/en/permission-modes). The first measurement slice supports only an inline `--append-system-prompt` treatment, bound by content/configuration hashes; settings, plugin, MCP, and agent treatments remain disabled until the adapter can prevalidate them and verify effective load evidence. Automatic fallback is never enabled.

---

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

---

# From references/codex.md (same relocation)

## Serving over MCP (ph-mcp-server v0 — verified 2026-07-14; resolves the wave-3 UNVERIFIED item)
- Register: `codex mcp add prompt-harness -- node <repo>/packages/mcp-server/dist/index.js --repo <repo>` (**global** config — unlike Claude Code's project-local default).
- **Codex surfaces MCP prompts**: a probe run enumerated both skills by exact name in its prompt inventory, plus the full resource list (44 references + 3 styles by served name).
- Same trust model as the Claude Code section: read-only local checkout, stdio; `--http` localhost-only.
- Hot updates hold (server re-reads per request); `list_changed` push behavior in Codex sessions untested (each `exec` is fresh anyway).

