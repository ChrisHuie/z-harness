# Cross-harness compatibility contract

This contract separates shared instruction content from host-enforced behavior. Sharing source
bytes does not establish runtime parity.

## Compatibility levels

| level | required evidence |
|---|---|
| `portable-core` | The selected Agent Skills package is structurally valid, installs without hidden dependencies, and passes positive and negative invocation scenarios on the named host. No hook, permission, trust, or side-effect guarantee is implied. |
| `adapter-functional` | The target-native package additionally passes invocation identity, argument handling, workflow-output, and expected-side-effect scenarios. |
| `host-integrated` | Installation scope, project binding, cache activation, fresh-session behavior, update, collision detection, and rollback pass on the named host version. |
| `governed-parity` | Every authority-bearing invariant has one named host enforcement mechanism, and its allow, deny, crash, timeout, malformed-output, and non-interactive cases pass. |

An artifact records `targetLevel` separately from `earnedLevel`. A renderer may set a target, but
only target-host evidence may advance the earned level. `unverified` is the required earned level
for an artifact that has only been rendered or statically inspected.

## Authority classes

- `instruction-only`: model-visible text asks for behavior. It is not an authorization boundary.
- `host-enforced`: a named host mechanism disposes of the action and has failure-path evidence.
- `external-boundary`: enforcement occurs outside the harness process and survives arbitrary
  behavior by the harness and model.

Portable Agent Skill fields, including tool hints, are `instruction-only` unless a target adapter
names and tests a stronger mechanism. A hook is not automatically `host-enforced`: its registration,
event coverage, decision envelope, timeout behavior, and crash behavior are part of the claim.

## Package isolation

Each installable artifact has one package format and one intended target family. A target root must
not contain a competing root or native manifest:

- Agent Plugins: `plugin.json`
- Codex: `.codex-plugin/plugin.json`
- Claude Code: `.claude-plugin/plugin.json`
- Kimi Code: `kimi.plugin.json`
- Hermes native: `plugin.yaml`

The canonical authoring repository is not an installation unit. Generated artifacts may be exposed
through a marketplace subdirectory, immutable archive, or generated publisher repository, but the
package root presented to a client must contain only its intended format.

## Release identity

A promoted target release records all of:

- canonical package and skill identifiers;
- core package version and target adapter revision;
- target package version and tested host versions;
- canonical source-tree digest and upstream lock digest, when an upstream contributed content;
- payload file inventory, modes, per-file digests, and aggregate digest;
- license set;
- validation results and the fresh-session installed artifact digest.

The render-time artifact manifest intentionally omits wall-clock time and ambient environment data.
Publication provenance binds the artifact digest to a Git commit after rendering; Git state is not an
implicit renderer input.

## Current migration boundary

The repository-root Claude/Codex package remains the v0.3 compatibility surface while the renderer
is introduced. The pilot reads the existing canonical `skills/` tree and renders only
`ground-claims` into isolated skills-only Agent Plugins, Codex, and Claude artifacts. It does not
migrate a runtime home, publish packages, add MCP servers, translate hooks, or claim runtime
compatibility.

The next cutover moves canonical authoring away from the installable root only after protective
tests prove every supported target artifact contains the expected skill inventory and behavior.
