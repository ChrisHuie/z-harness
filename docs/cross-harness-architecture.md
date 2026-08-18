# Cross-harness packaging architecture

## Decision

z-harness has one human-maintained authoring authority and isolated derived artifacts for Agent
Plugins, Codex, Claude Code, Kimi Code, and Hermes Agent. Target adapters project the canonical
semantic source; they are neither independent copies nor pairwise converters.

```text
canonical source + render config + target adapter
                       |
                       v
             deterministic projection
                       |
             isolated target artifact
                       |
             static and native validators
                       |
      future publication -> install -> launch
                       |
       future host receipt -> promotion decision
```

Rendering, publication, installation, project binding, launch, host observation, promotion, and
rollback are distinct state transitions. The pilot implements only rendering and verification.

## Migration and package boundaries

During the v0.3-to-v0.4 migration, root `skills/` remains the installed compatibility source for
existing Claude and Codex users. The pilot renders the real `ground-claims` skill before moving the
canonical tree or changing installation.

Generated outputs are disposable and are not another source of truth. Each target root contains
exactly one package format:

| target | root contract |
|---|---|
| Agent Plugins | `plugin.json` plus `skills/` |
| Codex | `.codex-plugin/plugin.json` plus `skills/` |
| Claude Code | `.claude-plugin/plugin.json` plus `skills/` |
| Kimi Code | `kimi.plugin.json` plus `skills/` |
| Hermes Agent | repository-root `skills/`; no executable plugin manifest |

The candidates contain skills only. They do not carry hooks, always-on policy, agents, commands,
MCP servers, credentials, model choice, project scope, or trust decisions. A mixed repository with
several native manifests is not an installation shortcut because the clients select and merge those
formats differently.

## Target projections

The source `SKILL.md` is parsed using a deliberately narrow YAML subset. The current source may
contain `name`, `description`, `argument-hint`, `allowed-tools`, and `metadata.version`; any unknown
top-level or metadata field fails closed. The renderer serializes parsed values rather than editing
YAML text.

Every rendered target receives quoted `name`, `description`, and `metadata.version`, followed by the
canonical Markdown body. Claude alone retains `argument-hint`. Every target omits `allowed-tools`:
the field has different or experimental host semantics. [Current Claude documentation](https://code.claude.com/docs/en/skills)
describes permission preapproval rather than a restriction, but that documentation is not
version-bound to the tested CLI. The conservative omission therefore does not depend on claiming
runtime permission behavior. Future permission metadata requires an explicit target adapter,
authority model, and failure-path tests.

Consequently the five targets share one canonical source identity but have target-specific payload
identities. The four standard projections have identical `SKILL.md` bytes; Claude differs only in
its adapter projection. Native manifest bytes make whole-target payload identities target-specific.
Verification re-derives expected payload from canonical source without trusting recorded payload
fields, using the shared production projection implementation. Blocking selftests separately compare
the pilot's exact projected bytes with fixed goldens. Coherently rewriting payload bytes and their
recorded hashes therefore does not pass, but this is not a second projection implementation.

## Codex source basis

Codex was previously the only target whose root contract this repository asserted without citing
an artifact. It is grounded in
[`openai/codex@646f7c0`](https://github.com/openai/codex/blob/646f7c0a91b8e327d263335da68ae8ef212895ce/codex-rs/exec-server-protocol/src/protocol.rs),
whose `DISCOVERABLE_PLUGIN_MANIFEST_PATHS` lists `.codex-plugin/plugin.json` first, alongside
`.claude-plugin/plugin.json` and `.cursor-plugin/plugin.json`.

Codex reads **two** package routes, and the portable one is checked first. At that revision
`find_plugin_manifest_path` returns a root `plugin.json` whenever its `$schema` is Agent
Plugins-shaped, and `parse_agent_plugin_manifest_uri` then synthesises the component paths rather
than requiring them: a root Agent Plugins manifest is loaded with `skills` set to `./skills` and an
interface derived from the portable fields. The `agent-plugins` artifact is therefore already
Codex-loadable, and its skill is discovered, with no `.codex-plugin/` present at all.

The separate `codex` target is consequently not required for loading. Its whole Codex-visible
delta is authored storefront presentation — `category`, `capabilities`, `defaultPrompt`,
`brandColor`, and a long description distinct from the short one — plus headroom for `apps` and
`hooks`, which the portable route cannot express. A standalone `.codex-plugin/plugin.json` with no
root `plugin.json` parses as the legacy format and its declared `skills` path is read directly.

That dual route is also why package isolation is protecting against a demonstrable hazard rather
than a hypothetical one. In a root that carried both manifests, the root file decides everything:
an Agent Plugins `$schema` that Codex does not support causes it to reject the package outright
with no fallback to the perfectly valid `.codex-plugin/plugin.json` beside it, so a future schema
version bump would silently disable the whole package; a root manifest carrying a `com.openai`
extension object causes the overlay file to be ignored entirely; and an overlay cannot redirect the
skills path in any case, because `skills` is not among the three fields it contributes.

Neither route has been exercised against a Codex runtime. This is implementation-source evidence at
one pinned revision, not an installation or a session.

## Kimi and Hermes source basis

The Kimi layout is grounded in
[`MoonshotAI/kimi-code@01c74e9`](https://github.com/MoonshotAI/kimi-code/blob/01c74e9372fcbbbe99614e859b53b505ed1664a8/docs/en/customization/plugins.md).
At that revision Kimi accepts root `kimi.plugin.json` or `.kimi-plugin/plugin.json`, gives the root
file precedence, and resolves declared skill paths relative to the plugin root. The renderer emits
only `kimi.plugin.json` and `./skills/`; the alternative manifest is forbidden. This is structural
source evidence, not an install or invocation result.

The Hermes layout is grounded in
[`NousResearch/hermes-agent@7132639`](https://github.com/NousResearch/hermes-agent/blob/71326399d30034e786cf42ccb9f00f686d183e4c/website/docs/user-guide/features/skills.md)
and its [plugin loader](https://github.com/NousResearch/hermes-agent/blob/71326399d30034e786cf42ccb9f00f686d183e4c/hermes_cli/plugins.py).
At that revision Hermes exposes three relevant package paths: a GitHub skill tap rooted at
`skills/<name>/SKILL.md`; a portable Agent Plugin discovered through root `plugin.json`, whose skills
and MCP configuration can load without Python; and a Python-native directory plugin using
`plugin.yaml` plus executable registration. The portable plugin route is namespaced, while tap skills
enter Hermes's ordinary skill index. This pilot deliberately gives the Hermes-specific target the tap
contract, so it emits only the repository-root `skills/` tree and forbids plugin manifests or Python
entrypoints. The separate Agent Plugins target may provide another Hermes-consumable route, but that
route and the tap both remain unverified on a live Hermes installation.

## Deterministic render contract

For the declared repository inputs, render config, target, and adapter revision, the renderer:

- reads no Git state, clock, environment variable, network, runtime home, or installed setting;
- requires a non-empty selected skill inventory and exact source directory/name identity;
- rejects source symlinks, non-regular files, unknown frontmatter fields, and unclassified
  host-specific constructs;
- records excluded authoring paths without copying them into runtime payloads;
- binds the exact renderer, closed render schema/golden set, render config, and selected adapter
  record; compatibility prose, the network-conformance lock, and vendored-source metadata remain
  CI/review inputs rather than artifact digest inputs;
- compares native manifest bytes with hand-authored goldens;
- builds every target and the aggregate index in a sibling staging directory;
- normalizes the complete staging tree, runs the public aggregate verifier there, and exposes no
  destination if that verifier fails; and
- refuses any pre-existing destination at entry and again at the commit fence.

The destination contract is a trusted, stable parent with one writer per output name. Portable
Python rename does not guarantee adversarial no-replace across macOS and Linux, so uncooperative
same-user pathname replacement during the render is outside the pilot's boundary.

## Logical identity

Schema v2 uses `z-harness-framed-sha256-v2`. The algorithm frames its identifier and domain, then
preserves the caller-supplied sequence. Tree digests sort records by path and frame path, mode, size,
and content SHA-256 in fixed order. JSON digests frame one UTF-8 canonical JSON value with sorted
object keys and retained array order. Separate domains prevent reinterpretation between scopes.
Seven fixed digest domains are in use: build contracts, the canonical render configuration, the
selected adapter entry, source input, included source, target payload, and complete artifact. Two
more are emitted per selected skill, for that skill's own input and included source, so the total
tracks the selected inventory rather than being a fixed count. Independent golden examples pin both
canonical-JSON and file-tree framing.

The important identities are:

1. `source.input`: every selected canonical source file, including excluded authoring metadata;
2. `source.selected`: selected runtime source before target projection;
3. `payload`: the target manifest and projected runtime files, excluding
   `z-harness-artifact.json`; and
4. `artifact`: the complete target root including `z-harness-artifact.json`, recorded in the parent
   index.

Logical file-tree records contain path, canonical file mode, size, and content SHA-256. Empty
directories are forbidden, so file paths imply directory topology. Directory modes and mtimes are
not included in cross-transport digests because Git does not preserve them.

## Physical renderer-output profile

`z-harness-posix-tree-v1` is stricter than the logical digest:

- regular files only, with link count one;
- no symlinks, hardlinks, devices, sockets, or FIFOs;
- no empty directories;
- no case-folded, Unicode-normalized, Windows-reserved, or otherwise non-portable path aliases;
- files exactly `0644` or `0755`;
- directories exactly `0755`; and
- file and directory mtimes exactly the Unix epoch.

The verifier scans this physical tree before reading artifact or index JSON. The profile governs
renderer-owned output, not arbitrary Git clones. It deliberately says nothing about ownership,
ACLs, xattrs, birth times, filesystem compression, or platform-specific metadata. A future archive
publisher must separately normalize and hash its archive headers; a Git publisher must record the
immutable Git transport identity.

## What verification proves

`--verify` answers four bounded questions:

1. **Physical profile** — the output tree has only the permitted paths, types, modes, links, and
   mtimes.
2. **Schema and format** — artifact/index JSON conforms to committed schemas, the Agent Plugin
   manifest conforms to the vendored 1.0.0 schema, and every native manifest equals its independent
   golden.
3. **Internal identity** — inventories and domain-separated digests match the bytes on disk.
4. **Input identity** — immutable manifest facts equal the current renderer, closed schema/golden
   set, configuration, source scan, and shared production target projection. Fixed selftest goldens
   are the independent oracle for the current pilot projection.

This proves that the tree is the current renderer's candidate for those inputs. It does not prove
installation, skill discovery, invocation, project binding, cache activation, host permissions,
runtime behavior, promotion, or publication authority.

## Validation layers

`python3 tools/ci-gate.py` is the complete offline gate. It runs the ordinary harness gate and its
meta-selftest, the renderer and guard selftests, eval-contract validation, and a fresh render/verify
pair. Each process must emit one terminal suite-qualified receipt with a nonzero count and a result
consistent with its exit status. The workflow itself is an exact checked contract, grants read-only
contents permission, disables persisted checkout credentials, and runs a source-bound harness
bootstrap before the gate on fixed Ubuntu and macOS runner labels with a pinned Python patch version.
The harness binds the gate source and the gate binds the harness source, which rejects an isolated
replacement of either runner when the declared workflow invokes both. The in-repository workflow
files are trust roots: a workflow-only edit can bypass the runners, and edits to both workflows can
fabricate both in-repo job classes. Reviewer inspection or an externally administered required
workflow must govern that boundary. GitHub manages the image contents behind those labels, and this
repository cannot prove that the jobs are required by branch protection.

The pull-request-only `mutation-proof` workflow explicitly checks out the pull-request head and runs
the deterministic guard-mutation plan in six private-tree shards. Its `if: always()` aggregate job
rejects missing, duplicated, overlapping, foreign, or stale fragment IDs, recomputes the raw suite
outcomes, schema-compares the canonical tracked receipt, and byte-compares the tracked summary. The offline gate
validates that receipt against the current source and plan, derives the canonical summary from that
strict receipt, and then checks the outbound include copies; it does not rerun the full mutation plan.

The workflow also declares an Ubuntu `portable-conformance` job. It is networked and fail-closed,
and its lock pins the Agent Skills source archive, `skills-ref` sources and dependency-wheel closure,
Python version, Claude release manifest, Anthropic signing key fingerprint, signature, and Linux
binary. The vendored-source record separately pins the Agent Plugins repository revision, schema
path and digest, and upstream license path and digest; the job derives and downloads both raw URLs
before validation. It validates the
four standard projections with the pinned reference validator, all artifacts with the pinned
external `jsonschema` 4.26.0 implementation, and the Claude target with the exact signed CLI. Claude is excluded
from Agent Skills reference validation because its intentional `argument-hint` extension is outside
the portable projection.

The Agent Skills reference implementation labels itself demonstration-only; it is differential
evidence, not the renderer's authority. The local field allowlist, shared projection implementation,
fixed byte goldens, and negative mutations remain load-bearing.

## Publication, host evidence, and rollback

No publisher, host runner, promotion gate, or rollback mechanism exists yet. Render artifacts
therefore contain no host evidence, no installed digest, and no `authority`: every artifact carries
`evidence: []`, and authority is absent because it belongs to a guarded fact rather than a package.

They do carry `targetLevel`, `earnedLevel`, and `validationStatus`, derived from the target's adapter
entry. `earnedLevel` is pinned to `unverified` and never read from configuration, and a
`validationStatus` above `fixture-only` requires host evidence records plus a non-empty license set,
so no status a host receipt would justify is reachable while no host receipt producer exists. See
[`contracts/compatibility-levels.md`](../contracts/compatibility-levels.md) for the evidence rule.

A future publisher must verify the exact subject at its commit/upload fence and bind both the
logical artifact digest and an immutable transport identity. Host observations belong in separate
receipts keyed to that immutable subject. A separate authority must derive promotion from a closed,
versioned scenario policy; a host runner cannot promote its own observations.

Clients that require a repository-root package—especially Kimi Git installs and Hermes taps—need a
root-preserving immutable archive or generated publisher repository. Publisher repositories contain
no human edits. Rollback is a new compare-and-swap channel transition to a previously immutable
subject followed by a fresh install/session check, not a mutation of old artifact evidence.

The project and rendered skill content do not yet declare a license. Local fixtures and CI
validation can continue, but public distribution or promotion remains blocked until that license is
chosen and recorded.
