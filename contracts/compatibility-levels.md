# Cross-harness compatibility contract

Shared instruction content does not establish runtime parity. Render identity, host observation,
promotion authority, publication, and rollback are separate records and state transitions.

## Compatibility vocabulary

An adapter declares the level it targets, and the artifact records that alongside the level it has
earned. `earnedLevel` is not read from configuration: it is pinned to `unverified`, because
rendering and static inspection earn nothing and only a target-host promotion run may advance it.

| level | evidence a future promotion decision would require |
|---|---|
| `portable-core` | The selected Agent Skill is structurally valid and passes a closed positive and negative invocation catalog on the named host. No hook, permission, trust, or side-effect guarantee is implied. |
| `adapter-functional` | The target-native package additionally passes invocation identity, argument handling, workflow-output, and expected-side-effect scenarios. |
| `host-integrated` | Installation scope, project binding, cache activation, fresh-session behavior, update, collision detection, and rollback pass for the exact host version and profile. |
| `governed-parity` | Every authority-bearing invariant has a named host enforcement mechanism, and its allow, deny, crash, timeout, malformed-output, and non-interactive cases pass. |

The current renderer earns none of these levels. It emits reproducible package candidates and
immutable render-time facts only. No host receipt producer, promotion decision maker, publication
ledger, or rollback controller exists in this pilot.

## Evidence required by a claim

`validationStatus` is gated on the evidence this contract names, at both ends: the adapter
configuration is refused at input time and the rendered artifact is refused at verification time,
through one predicate, so neither end can claim a status the other would reject.

| `validationStatus` | required |
|---|---|
| `fixture-only` | no host evidence records at all |
| `candidate`, `promoted` | at least one evidence record, and a non-empty license set |

Each evidence record names a host, that host's version, the artifact digest observed after a
fresh-session install, and the scenario results behind the claim. A scenario that did not pass
cannot support a status above `fixture-only`.

This checks that a claim carries evidence of the required shape, not that the evidence is true;
only a target-host run establishes the latter. Because no producer of host receipts exists and the
pilot declares no license, every status above `fixture-only` is currently unreachable by
construction rather than by convention, and the absent license set is a mechanical promotion
blocker rather than a note.

## Why authority is not an artifact field

`authority` is deliberately absent from render configuration and from every rendered artifact, and
it is the one field of this family that stays absent. Authority is a property of a guarded fact —
its mechanism, the host version enforcing it, and the scope over which it holds — so a
package-wide scalar would assert something no package can hold. An adapter that set
`authority: external-boundary` while carrying no evidence would be making exactly the claim the
authority vocabulary below exists to discipline.

Recording authority therefore requires a target-owned overlay keyed per guarded fact, with
denial-path evidence, not a field on the package manifest.

## Authority vocabulary

- `instruction-only`: model-visible text requests behavior. It is not an authorization boundary.
- `host-enforced`: a named host mechanism disposes of an action and has scoped failure-path
  evidence.
- `external-boundary`: enforcement occurs outside the harness process and survives arbitrary
  behavior by the harness and model.

These are also future decision vocabulary, not artifact-wide scalar fields. Authority must be
recorded per guarded fact, mechanism, host version, and scope. Portable skill text is
instruction-only. A hook is not automatically host-enforced: registration, event coverage,
decision envelopes, timeout behavior, and crash behavior are part of the claim.

`allowed-tools` is omitted from every rendered target. Its meaning is not portable. Current
[Claude Code documentation](https://code.claude.com/docs/en/skills) describes preapproval for the
invoking turn rather than restriction to the named tools, but those documentation bytes are not
version-bound to the tested CLI. The conservative omission does not claim that runtime behavior.
Adding permission metadata later requires a target-owned authority overlay and denial-path tests.

## Changing a native manifest

`contracts/goldens/native-manifests.json` holds the expected bytes of every target-native
manifest. Rendering builds the manifest from `release/render.json`; verification compares it to
that golden. The two derivations are independent, which is what makes a rethreaded edit to a
rendered artifact detectable.

There is deliberately no command that rewrites the golden from a render. A detector whose
documented remedy clears the detection proves nothing, and the point of an authored golden is that
a person reads the bytes. Editing package metadata therefore means updating the golden by hand in
the same commit, so the manifest change appears in review as a diff rather than as a digest.

## Package isolation

Each installable artifact has one package format and one intended target family. A target root must
not contain a competing root or native manifest:

- Agent Plugins: `plugin.json`
- Codex: `.codex-plugin/plugin.json`
- Claude Code: `.claude-plugin/plugin.json`
- Kimi Code: `kimi.plugin.json`; `.kimi-plugin/plugin.json` is absent
- Hermes skill tap: no plugin manifest; `skills/<name>/SKILL.md` is required. Hermes also supports
  a separate portable `plugin.json` route, represented by the Agent Plugins target rather than this
  tap artifact; `plugin.json`, `plugin.yaml`, and Python entrypoints are forbidden in the tap target

The canonical authoring repository is not the five-target installation unit. Generated artifacts
may later be exposed through a marketplace subdirectory, immutable archive, or generated publisher
repository, but a client must receive exactly one target root.

## Render identity

Artifact schema v3 contains facts derivable during rendering, plus the claims block derived from
the target's adapter entry and gated on the evidence above:

- package, target, version, format, and adapter revision;
- exact renderer, closed render schema/golden set, render-config, and selected adapter-config
  digests;
- canonical input and included-source identities;
- target payload inventory and identity; and
- the filesystem and digest algorithm identifiers.

`z-harness-framed-sha256-v2` frames its algorithm identifier and domain, then preserves the sequence
supplied by the caller. Tree digests sort records by path and frame path, canonical file mode, size,
and content digest in that fixed order. JSON digests frame one UTF-8 canonical JSON value with sorted
object keys; array order is retained. Seven fixed digest domains are in use: build contracts, the
canonical render configuration, the selected adapter entry, source input, included source, target
payload, and complete artifact. Two more are emitted per selected skill, for that skill's own input
and included source, so the total tracks the selected inventory rather than being a fixed count.
Empty directories are forbidden, so directory topology is derived from file paths.

The cross-transport logical digest does not claim ownership, ACLs, xattrs, birth time, or directory
metadata: Git does not preserve those properties. Renderer-owned output separately conforms to
`z-harness-posix-tree-v1`: files are exactly `0644` or `0755`, directories are `0755`, all mtimes are
the Unix epoch, symlinks and hardlinks are absent, and every directory is non-empty. `--verify`
applies that strict profile to renderer output; a Git clone is not expected to pass it until it has
been normalized as an output artifact.

Verification binds an artifact to the current selected source, renderer, contracts, and
configuration. An older artifact correctly fails after those inputs move. A future rollback or
publication verifier must therefore use the exact source commit and build inputs recorded at
publication rather than the current authoring checkout.

## Future evidence and promotion

Host observations must not be written back into an already rendered artifact. Doing so would change
the complete artifact identity after the tested bytes were installed.

A future host receipt should at minimum identify the exact artifact and publication subject,
runner, target host/version, project/workspace/profile scope, installed inventory, cache/session
activation, complete required scenario catalog, and evidence-log digests. It records observations;
it does not grant a level.

A separate promotion decision must bind those receipts to a versioned closed policy and scenario
catalog, reject omissions, failures, and infrastructure errors, and derive any earned level for the
specific artifact × host version × profile. The promotion authority must be outside the component
whose claim it disposes.

## Publication and rollback

Publication is not implemented. A future publisher must re-verify the exact subject at its commit
or upload fence and record both the logical artifact digest and an immutable transport identity such
as a Git commit/tree or canonical archive SHA. Reusing `(target, packageVersion)` for different bytes
must fail.

Rollback is a new, forward-recorded channel transition, not an edit to an old artifact. It needs the
previous channel identity, restored artifact and transport identities, causal link, policy and actor,
provider compare-and-swap result, and a fresh install/session check of the restored subject.

## Current migration boundary

The repository-root Claude/Codex package remains the v0.3 compatibility surface. The v0.4 pilot
reads the existing `skills/` tree and renders only `ground-claims` into isolated skills-only Agent
Plugins, Codex, Claude, Kimi, and Hermes candidates. Claude alone retains `argument-hint`; every
target omits `allowed-tools`; all retain the same Markdown body. Kimi uses its native manifest.
Hermes uses a non-executable GitHub skill tap.

The pilot does not migrate a runtime home, publish or install packages, add MCP servers, translate
hooks, produce host receipts, promote compatibility, or implement rollback. Issues #5 and #6 remain
separate recorded deferrals.
