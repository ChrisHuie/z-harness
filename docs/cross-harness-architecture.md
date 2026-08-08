# Cross-harness packaging architecture

## Decision

z-harness has one human-maintained authoring authority and multiple derived runtime artifacts.
Target adapters are projections from the canonical semantic source; they are not independent
copies and not pairwise converters.

```text
canonical skills + policy + adapter config
                 |
                 v
        deterministic renderer
                 |
       isolated target artifacts
                 |
       target validators and evals
                 |
   archive or generated publisher repo
                 |
      install -> fresh-session launch
```

The renderer produces package bytes. An installer copies or caches one package for a host. A
launcher binds that installed package to a project path, resolved Git root, workspace or worktree,
profile, and session. These are separate state transitions and must not be described as one action.

## Source and artifact boundaries

During the v0.3-to-v0.4 migration, root `skills/` remains the compatibility source so existing
Claude and Codex installations keep working. The render pilot selects one real skill from that tree
and introduces the source-to-artifact boundary before moving directories or changing installation.

The intended end state is:

```text
source/       canonical semantic content
adapters/     target format and capability declarations
contracts/    internal compatibility and artifact contracts
release/      explicit render and promotion inputs
tools/        renderer, verifier, release checks
```

The authoring root will stop looking installable only after target inventory and behavior tests
protect the cutover. Generated outputs are disposable and are not committed as another source of
truth.

## Portable and native packages

Agent Plugins 1.0 is a portable packaging boundary for Agent Skills and MCP configuration. The
initial artifact contains skills only. It does not carry hooks, always-on policy, agents, commands,
credentials, model selection, installation scope, or trust decisions.

Claude, Codex, Kimi, and Hermes therefore require separate adapters whenever z-harness depends on
native behavior. A package containing several native manifests is not accepted as a shortcut:
clients select and merge formats differently, so co-location makes the active contract ambiguous.

### Kimi and Hermes adapter evidence

The Kimi adapter is grounded in the official Kimi Code plugin documentation at
[`MoonshotAI/kimi-code@01c74e9`](https://github.com/MoonshotAI/kimi-code/blob/01c74e9372fcbbbe99614e859b53b505ed1664a8/docs/en/customization/plugins.md).
That revision accepts either root `kimi.plugin.json` or `.kimi-plugin/plugin.json`, gives the root
file precedence when both exist, and defines `skills` as one or more plugin-root-relative paths.
The renderer chooses only `kimi.plugin.json` and `./skills/`; the alternative manifest is a
competing format and fails verification. This is structural evidence, not proof of installation or
invocation behavior. The adapter must be revisited if a supported Kimi runtime rejects the emitted
manifest or resolves the declared skill set differently.

The Hermes adapter is grounded in the official skills documentation at
[`NousResearch/hermes-agent@7132639`](https://github.com/NousResearch/hermes-agent/blob/71326399d30034e786cf42ccb9f00f686d183e4c/website/docs/user-guide/features/skills.md)
and the plugin loader at
[`hermes_cli/plugins.py`](https://github.com/NousResearch/hermes-agent/blob/71326399d30034e786cf42ccb9f00f686d183e4c/hermes_cli/plugins.py).
At that revision, a GitHub skill tap is rooted at `skills/<name>/SKILL.md`. A native directory
plugin instead requires both `plugin.yaml` and executable `__init__.py` registration, and its skills
are namespaced explicit loads rather than ordinary indexed skills. The instruction-only pilot
therefore emits a non-executable tap and forbids `plugin.yaml`. This choice is falsified if a
supported Hermes runtime cannot enumerate and install the rendered tap with the documented slug.

## Rendering contract

For declared repository inputs, target, and adapter revision, rendering must produce the same file
bytes, normalized executable modes, inventories, and digests. The renderer:

- reads only repository paths named by versioned config;
- requires a non-empty selected skill set;
- validates immediate skill identity and required Agent Skill metadata, refusing by name any
  frontmatter syntax it cannot decode rather than mis-decoding it;
- rejects symlinks and non-regular files;
- excludes only explicitly named runtime directories and immediate files, and records every
  excluded path;
- records the renderer version, renderer digest, canonical render-config digest, and the selected
  target adapter-config digest;
- normalizes file modes to `0644` or `0755` and file mtimes to the Unix epoch;
- emits exactly the intended target manifest set: one native manifest for manifest-based targets,
  and none for the Hermes skill tap;
- inventories and hashes every payload file;
- writes no runtime compatibility claim beyond `earnedLevel: unverified`;
- builds all targets in a temporary sibling and exposes none until every target verifies; and
- refuses to overwrite an existing output root.

The aggregate payload digest is derived from sorted `(path, mode, file sha256)` tuples. The artifact
manifest is excluded from that digest because embedding a digest of itself has no finite stable
representation. A deterministic `render-index.json` outside the installable roots records a second
digest over every complete target directory, including the artifact manifest. Publication
provenance binds that complete-artifact digest to the promoted source commit.

Configuration digests use UTF-8 JSON with sorted object keys and no insignificant whitespace. Each
artifact hashes only its selected adapter object, so a Claude-only adapter change cannot churn an
otherwise unchanged Codex or Agent Plugins artifact.

## What verification settles

`--verify` answers three separate questions, and an artifact must pass all of them:

1. **Contract conformance** — the artifact manifest and render index validate against the committed
   schemas in `contracts/`, and the portable manifest validates against the vendored Agent Plugins
   1.0.0 schema in `contracts/vendor/`.
2. **Internal consistency** — the recorded inventory, modes, and digests match the bytes on disk.
3. **Identity** — the build record, claims, package identity, and source digests are recomputed from
   the render config, the adapter entry, the renderer file, and the current source tree.

The third is what makes the manifest more than an assertion. Rendering and verification call the
same derivation for the build record and the claims block, so neither can drift from the other; the
cost of that symmetry is that neither side can detect a fault inside the shared digest helpers.

Schemas are vendored rather than fetched. Agent Plugins 1.0.0 instructs a client to select locally
supported validation rules from `$schema` rather than retrieving a schema while loading a plugin,
and the same rule keeps the gate free of network state. `contracts/vendor/SOURCES.json` records each
copy's upstream URL, digest, and retrieval date, and a selftest fails if the file stops matching the
digest recorded for it. The schema reader implements the subset these contracts use and raises on any
keyword it does not evaluate, so an unchecked constraint cannot read as a clean result.

## Payload and installed inventory

`payloadSha256` states which bytes the artifact ships. It does not state which bytes a given host
installs: hosts apply their own copy rules. Agent Plugins 1.0.0 states that a skill "may contain any
additional files and directories it needs", while the pinned Hermes revision copies `SKILL.md` plus
the files it references under the documented support directories and does not copy unreferenced
repository files.

`CONTRACT.md` is authoring metadata in the same class as `evals/` — it specifies how a skill was
built, not how it runs — so `runtimeExcludeFiles` removes it from the runtime payload and records it
in `excludedPaths`. One payload identity therefore holds across all five targets, and the question of
which hosts would have copied it does not arise. Excluding a path preserves `inputTreeSha256` and
moves only `includedTreeSha256` and the payload digests, so the source of record stays intact.

A per-target payload projection is the general answer and is not built here: no runtime file yet
needs to differ between targets, and adding a second projection axis before then would be machinery
without a case.

## Validation and promotion

Static rendering earns no runtime compatibility level. Promotion is per target and requires:

1. target-native manifest validation;
2. exact installed skill inventory and invocation identity, compared against the artifact's payload
   inventory so any host-side copy rule that drops a shipped file is caught before promotion;
3. positive and negative trigger scenarios;
4. output and side-effect assertions;
5. project, cwd, workspace, and worktree binding checks;
6. collision, update, cache activation, new-session, and rollback checks; and
7. authority failure cases for every claimed guard.

MCP remains out of the portable artifact until each host's process, credential, redirect, trust,
and annotation behavior has a separate threat model and runtime fixture.

## Publication topology

The canonical repository may expose generated subdirectories to marketplaces that support a pinned
Git subdirectory. Clients that accept only a repository-root package receive either an immutable
archive or a bot-owned publisher repository whose root is the artifact root. Publisher repositories
contain no human edits and retain the source commit, renderer version, artifact digest, validation
results, and rollback history.

Kimi's GitHub installer and Hermes taps both resolve repository-root layouts. Their generated
artifacts therefore need a root-preserving archive or generated publisher repository; a directory
inside the mixed authoring repository is not, by itself, the published installation unit.

Publishing, installation, trust approval, and launch are not renderer responsibilities.
