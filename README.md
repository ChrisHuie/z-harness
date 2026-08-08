# z-harness

A version-controlled operating harness for coding agents. The v0.3 compatibility package serves
Claude Code and OpenAI Codex from one shared policy and skill tree; runtime-specific files exist
only where those products have different discovery, hook, transcript, or UI contracts.

The next architecture separates canonical authoring from installable target packages. A
deterministic renderer now provides the migration seam without changing the installed v0.3
surface. It emits isolated, skills-only Agent Plugins, Codex, Claude, Kimi, and Hermes pilot
artifacts for the real `ground-claims` skill. Rendered artifacts are unverified candidates: they
are not published, installed, or promoted by the renderer.

The live Claude installation can remain `~/.claude`, but new cross-harness authoring should occur in
a clean repository checkout. Runtime homes and plugin caches are installed state, not release
authority.

## Cross-harness render pilot

Render into a new disposable directory, then verify the exact bytes and modes recorded in each
artifact manifest:

```text
python3 tools/render-packages.py --output /tmp/z-harness-render
python3 tools/render-packages.py --verify /tmp/z-harness-render
```

The output contains five physically isolated package roots:

| directory | package format | manifest |
|---|---|---|
| `agent-plugins/` | Agent Plugins 1.0 skills-only | `plugin.json` |
| `codex/` | Codex native skills-only | `.codex-plugin/plugin.json` |
| `claude/` | Claude Code native skills-only | `.claude-plugin/plugin.json` |
| `kimi/` | Kimi Code native skills-only | `kimi.plugin.json` |
| `hermes/` | Hermes Agent GitHub skill tap | no native manifest; `skills/` is the tap root |

`release/render.json` selects source skills and package metadata.
`adapters/targets.json` declares target format, adapter revision, target compatibility level, and
evidence status. Every target writes `z-harness-artifact.json`, whose inventory and digest exclude
the manifest itself to avoid a self-referential hash and whose build record binds the renderer and
canonicalized configuration inputs. The non-installable parent
`render-index.json` hashes every complete target directory, including its artifact manifest.

`--verify` recomputes every manifest value rather than checking its shape. It validates the manifest
and index against the committed schemas in `contracts/`, validates the portable manifest against the
vendored Agent Plugins 1.0.0 schema in `contracts/vendor/`, re-derives the build record and claims
from the render config and adapter entry, and re-reads the source tree to confirm the recorded source
digests. An artifact whose configuration, renderer, or source has moved fails, which is the point:
that artifact is stale.

The renderer does not read Git state, clocks, environment variables, networks, runtime homes, or
installed harness settings. It refuses existing output paths, source symlinks, empty skill sets,
skill name/directory mismatches, frontmatter syntax it cannot decode, packages containing competing
target manifests, and any compatibility status whose evidence is absent. See
[`contracts/compatibility-levels.md`](contracts/compatibility-levels.md) for the compatibility and
authority vocabulary.

## Install in Codex

```text
codex plugin marketplace add ChrisHuie/z-harness --ref main
codex plugin add z-harness@z-harness
```

This repository is private. The marketplace command therefore requires existing Git HTTPS
credentials that can read `ChrisHuie/z-harness` (for example, a credential helper configured after
the user completes `gh auth login`, followed by `gh auth setup-git`). The credential-free URL check
in C9 prevents secrets from being embedded in package metadata; it does not grant repository access.

Start a new Codex task, open `/hooks`, review the z-harness hook definitions, and trust them. Codex
requires explicit trust for new or changed non-managed hooks; installing the plugin does not bypass
that boundary.

Confirm the installed surface:

```text
codex plugin list --json
python3 <path-to-z-harness>/hooks/harness_check.py --ci
python3 <path-to-z-harness>/tools/codex-cost.py --since 7d
```

The plugin does not select a model, change sandbox/approval policy, copy authentication, or trust
its own hooks. Those remain user-controlled Codex settings.

See [OpenAI/Codex integration](docs/openai-agents.md) for the architecture, compatibility matrix,
update flow, hook semantics, host-local context, and troubleshooting.

## Claude Code installation

The original installation remains supported: the live working tree is `~/.claude`, cloned from
this repository. `~/Documents/GitHub/z-harness` may be a second mirror. Synchronize the clones by
local fetch (`git pull <other-clone-path> main`); pushing to origin remains a separate action.

Prefer harness work in the `~/.claude` clone. A session opened in a mirror may otherwise load the
same shared policy at both user and project scope.

## Shared and runtime-specific surfaces

| path | runtime | purpose |
|---|---|---|
| `AGENTS.md` | shared | canonical always-on operating policy; native project context for Codex |
| `CLAUDE.md` | Claude | thin `@AGENTS.md` bridge plus Claude-only mechanics |
| `skills/` | shared | twelve portable skills; Claude discovers them in place, Codex through the plugin |
| `.codex-plugin/plugin.json` | Codex | plugin identity, install metadata, and skill entry point |
| `.agents/plugins/marketplace.json` | Codex | Git-backed marketplace entry for CLI/app installation |
| `hooks/hooks.json` | Codex | SessionStart/SubagentStart policy injection and PreToolUse guard wiring |
| `settings.json` | Claude | Claude hooks, permissions, model, status line, and UI settings |
| `hooks/bash_command_guard.py` | shared adapter | shared predicates; Codex maps unsupported `ask` results to fail-closed `deny` |
| `hooks/spawn_preflight_guard.py` | shared adapter | disk-capacity gate; maps unsupported Codex `ask` decisions to fail-closed `deny` |
| `hooks/askq_timeout_guard.py` | Claude | AskUserQuestion AFK guard; no claimed Codex equivalent |
| `hooks/codex_session_start.py` | Codex | injects mandatory shared policy, resolved adapter commands, and optional host-local context |
| `$CODEX_HOME/z-harness/AGENTS.local.md` | local Codex host | optional non-packaged machine instructions appended by the session adapter |
| `hooks/harness_check.py` | shared | mechanical gate over skills, hooks, context files, and plugin packaging |
| `hooks/harness_report.py` | Claude | transcript evidence for Claude skill firing/reference reads |
| `tools/cc-cost.py` | Claude | Claude request-deduplicated token accounting |
| `tools/codex-cost.py` | Codex | per-request token accounting with copied/replayed record dedupe |
| `tools/claim-provenance.py` | shared | explicitly bound byte-exact quote and successful-read provenance checks for local documents |
| `tools/pr-delivery-state.py` | shared | proves workspace, local HEAD, PR head, and exact-head CI agree before publication claims |
| ignored `projects/*/memory/` | Claude-local data | host-bound Claude memory remains on the authoring machine and is not packaged for Codex |
| ignored `harness-audit-*/` | publisher-local record | pre-migration snapshots and machine-derived evidence stay beside the authoring checkout, never in the plugin package |

## Health

```text
python3 hooks/harness_check.py
python3 hooks/harness_check.py --selftest
python3 hooks/bash_command_guard.py --selftest
python3 hooks/spawn_preflight_guard.py --selftest
python3 hooks/codex_session_start.py --selftest
python3 hooks/askq_timeout_guard.py --selftest
python3 hooks/askq_timeout_guard.py --verify-harness
python3 hooks/harness_report.py --selftest
python3 tools/cc-cost.py --selftest
python3 tools/codex-cost.py --selftest
python3 tools/claim-provenance.py --selftest
python3 tools/pr-delivery-state.py --selftest
python3 tools/run-skill-evals.py --selftest
python3 tools/run-skill-evals.py --validate
python3 tools/render-packages.py --selftest
```

CI runs `python3 hooks/harness_check.py --ci` and `--selftest` on every push and pull
request — the mode check and the meta-suite that proves each check can still go red. Local mode adds
machine-specific Claude anchors. `--selftest` plants defects and proves each check family can turn
red; a zero-input scan is an error, not a clean verdict. C1 also requires each aggregated suite to
finish with exactly one `SELFTEST-SUMMARY` receipt, so an early exit 0 cannot impersonate a complete
test run. It also fails when a script exposing `--selftest` is neither aggregated nor explicitly
classified as a component/meta-suite.

Skill contract eval validation is free and offline. `tools/run-skill-evals.py --run` executes
headless model scenarios and spends API budget, so it remains manual.

Document quote/citation scans are also manual because they require the target document, artifact
root, and session transcript. Their detector selftest is blocking through C1.

## Mechanics worth knowing

- `AGENTS.md` is the shared source. `CLAUDE.md` must remain a bridge plus Claude-specific addendum;
  duplicating shared policy across both files is a regression.
- Codex plugins are installed into a cache. Refresh the marketplace and reinstall after changing a
  plugin version, then use a new task so skill and hook discovery starts from fresh state.
- Codex will skip changed plugin hooks until the user reviews their new hash in `/hooks`.
- Claude skills fire through the imperative routing rule in the shared policy. Editing an existing
  installed skill hot-reloads in Claude; a new skill directory requires a new session.
- A request to create or update a PR carries ordinary-push authority through published-head and
  exact-head CI verification. Run
  `python3 tools/pr-delivery-state.py --pr <number> --repo <owner/repo>` before claiming the local
  work is on that PR; merge, force-push, comments, and thread resolution remain separately
  authorized.
- `git clean -fdx` in a live `~/.claude` clone deletes ignored transcripts. Plain `-fd` preserves
  them. Never use `-x` there.
- `.gitignore` is an allowlist. New authored surfaces must be explicitly included or git cannot see
  them.
- C9 certifies the current tracked/installed file surface, including nested `projects/`,
  `harness-audit-*`, encoded absolute-path slugs, and absolute host paths inside text. It deliberately
  does not certify `.git` history. Git-backed plugin caches can retain deleted paths through history;
  keep this repository private until that history has been separately audited and scrubbed.
- Before fast-forwarding another clone across the commit that first untracks publisher-local audit
  files, copy or move any audit data that clone must retain. Git applies the tracked deletions during
  that first update; the new ignore rule protects the files only after they are untracked.
