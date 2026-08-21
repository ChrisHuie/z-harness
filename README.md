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

Render into a new disposable directory, then verify the logical file identities and the renderer's
strict physical-output profile:

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

`release/render.json` selects source skills and package metadata. `adapters/targets.json` declares
per-target render policy — target format, package version, manifest path and adapter revision — and
the compatibility claims an artifact carries: `targetLevel`, `validationStatus`, and the `evidence`
records that gate any status above `fixture-only`.
Every target writes `z-harness-artifact.json`; its payload inventory excludes that manifest to avoid
a self-reference, while the non-installable parent `render-index.json` records a domain-separated
digest of every complete target directory, including its artifact manifest.

`--verify` validates the manifests against committed schemas, compares native manifests with
hand-authored goldens, re-projects the selected source into the expected target payload, and
recomputes every immutable build, source, payload, and complete-artifact value. It rejects an unknown entry at the
render root before reading any JSON; an unknown entry inside a target root is rejected by the payload
inventory, which is read after that target's manifest. An artifact whose configuration, renderer,
closed render schema/golden set, or selected source has moved fails as stale. Compatibility prose,
the network-conformance lock, and vendored-source metadata are CI/review inputs rather than artifact
digest inputs.

The renderer does not read Git state, clocks, environment variables, networks, runtime homes, or
installed harness settings. It refuses existing output paths, source or output symlinks, hardlinks,
special files, empty directories, non-portable path aliases, empty skill sets, skill name/directory
mismatches, unclassified host-specific constructs, and competing target manifests. Renderer-owned
output files are exactly `0644` or `0755`; directories are `0755`; all mtimes are the Unix epoch.
Ownership, ACLs, xattrs, birth times, and Git-clone directory metadata are outside this profile.

Canonical `argument-hint` metadata is retained only in the Claude projection. `allowed-tools` is
omitted from every rendered target because hosts do not give it one portable authority meaning.
Rendered artifacts record `validationStatus: fixture-only` and `earnedLevel: unverified`, and carry
no runtime evidence and no package-wide authority. See
[`contracts/compatibility-levels.md`](contracts/compatibility-levels.md) for that separation.

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
| `hooks/spawn_preflight_guard.py` | shared adapter | disk-capacity gate plus required fresh scratch reservation; maps unsupported Codex `ask` decisions to fail-closed `deny` |
| `hooks/askq_timeout_guard.py` | Claude | AskUserQuestion AFK guard; no claimed Codex equivalent |
| `hooks/announced_work_guard.py` | Claude | Stop hook that blocks a final message which announces work that has not begun; no claimed Codex equivalent |
| `hooks/codex_session_start.py` | Codex | injects mandatory shared policy, resolved adapter commands, and optional host-local context |
| `$CODEX_HOME/z-harness/AGENTS.local.md` | local Codex host | optional non-packaged machine instructions appended by the session adapter |
| `hooks/harness_check.py` | shared | mechanical gate over skills, hooks, context files, and plugin packaging |
| `hooks/harness_report.py` | Claude | transcript evidence for Claude skill firing/reference reads |
| `tools/cc-cost.py` | Claude | Claude request-deduplicated token accounting |
| `tools/codex-cost.py` | Codex | per-request token accounting with copied/replayed record dedupe |
| `tools/claim-provenance.py` | shared | explicitly bound byte-exact quote and successful-read provenance checks for local documents |
| `tools/repository_ownership.py` | shared | validates nested Git ownership boundaries for inventory and evidence scans |
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
python3 hooks/announced_work_guard.py --selftest
python3 hooks/harness_report.py --selftest
python3 tools/cc-cost.py --selftest
python3 tools/codex-cost.py --selftest
python3 tools/claim-provenance.py --selftest
python3 tools/repository_ownership.py --selftest
python3 tools/pr-delivery-state.py --selftest
python3 tools/run-skill-evals.py --selftest
python3 tools/run-skill-evals.py --validate
python3 tools/render-packages.py --selftest
python3 tools/verify-review-publication.py --selftest
python3 tools/ci-gate.py --selftest
python3 tools/ci-gate.py
```

`python3 tools/ci-gate.py` is the offline CI-equivalent entry point. It runs the ordinary gate, its
meta-selftest, the renderer and guard selftests, eval validation, and a fresh render/verify pair. It
accepts each child only when the process result and one terminal, suite-qualified receipt agree.
The workflow pins its action commits and Python patch version, grants only read access to contents,
does not persist checkout credentials, and first runs `hooks/harness_check.py --ci` before the
complete gate on fixed Ubuntu and macOS runner labels. The harness binds the reviewed `ci-gate.py`
source and the gate independently binds the reviewed harness source, so replacing either runner in
isolation fails before its claimed receipt is accepted when the declared workflow invokes both.
The in-repository workflow files are trust roots: a workflow-only edit can bypass those runners,
and coordinated edits to both workflows can fabricate both in-repo job classes. Reviewer inspection
or an externally administered required workflow must govern that boundary. GitHub still manages the
image contents behind those labels. A `mutation-proof` workflow accepts pull requests, pushes to
`main`, and manual dispatches, explicitly checks out
`github.event.pull_request.head.sha || github.sha`, runs the deterministic mutation plan in six
private-tree shards for every accepted head, and aggregates raw artifacts with `if: always()`. The aggregator
rejects missing, duplicate, overlapping, foreign, or stale mutation IDs, recomputes each raw outcome,
schema-compares the canonical tracked receipt, and byte-compares the tracked summary. The offline gate validates that receipt against
the current plan and sources, derives the canonical summary bytes from the strict receipt, and then
checks the outbound include copies; it does not rerun the expensive mutation plan locally. A separate
declared Ubuntu job runs `tools/portable-conformance.py`. It resolves locked wheel filenames through
live PyPI metadata, requires the published digest to equal the lock, hash-verifies every downloaded
artifact, derives the vendored Agent Plugins schema and license URLs from their pinned repository
revision and paths, and verifies a signed, hash-pinned Claude Code release before validating a fresh render.
Network failure is red, never skipped. The repository workflow does not itself prove that either job
is a branch-protection required check. `tools/pr-delivery-state.py` proves generic exact-head check
and workflow presence; final mutation evidence additionally requires the named mutation workflow,
six nonempty shard artifacts, and its successful aggregate job to be inspected explicitly.

Local `harness_check.py` mode adds machine-specific Claude anchors, compares the complete payload
of repository-owned skills under `~/.claude/skills`, and scans tracked plus authored-untracked
context files
without crossing nested Git ownership. `--selftest` plants defects and proves each check family can
turn red; a zero-input scan is an error, not a clean verdict. C1 requires
every direct selftest to be registered with a positive floor and a unique terminal suite receipt;
`harness_check.py` is the sole recursive meta-suite exemption.

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
