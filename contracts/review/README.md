# Outbound review text

Review text that will be posted to a pull request is drafted here and posted from here.

The gate for this directory has a narrow claim: required generated include blocks must be
present in the registered documents and byte-identical to their sources. Free prose and
manually typed measurements outside those blocks are not mechanically verified. Source
digests, guard decisions, suite execution counts, and mutation outcomes have separate
validators under `contracts/goldens/`; none makes an unregistered GitHub edit verifiable.

## The rule

A current measurement used as evidence for the outbound head belongs in a generated file,
and outbound text INCLUDES that file rather than restating it:

```
<!-- include: contracts/goldens/mutation-summary.md -->
...byte-identical copy of that file...
<!-- end include -->
```

`tools/ci-gate.py` checks every live include block under this directory against its source,
requires the registered PR description include, and enforces the exact relative-path inventory
`README.md`, `pr-8/description.md`, and `pr-8/title.txt`. A nested duplicate, symlink, missing
file, renamed handoff, or restored roll-up is rejected.
`tools/write-mutation-receipt.py` writes the receipt and summary from one accepted
aggregate of exact-plan shard fragments; its normal aggregate mode refuses changed output.
Historical measurements may remain as context only when the document says they are not
final-head evidence; the include gate does not validate those free-prose claims.

## Layout

    contracts/review/pr-<number>/description.md    the pull request body
    contracts/review/pr-<number>/title.txt         the pull request title

Head-specific handoffs are append-only external comments, one verified head per comment.
Never edit, replace, or delete a published handoff. A later head or correction gets a new
comment that links the earlier record and states what changed. Individual findings remain
inline `path:line` threads because a PR-level handoff has no finding lifecycle.

The description and title are mutable current-state documents and live here because both carry
measured figures. Build each by editing the file and posting from it, never by retyping a number
into the web form.

Do not keep a mutable tracked file as the current handoff. Its exact head does not exist until
the implementation commit is final, and committing that head back into the same branch creates
a self-reference that can never settle. Build the handoff after exact-head verification, POST it
as a new comment, then read the created comment back and require its body to match the submitted
bytes. The repository gate validates the sources used to build that handoff; the read-back
validates the external comment, and it is a command rather than an instruction:

```
tools/verify-review-publication.py comment \
  --repo <owner/name> --pr <number> --comment-id <id> \
  --expected-head <40-hex-sha> --expected-author <login> --body-file <draft>

tools/verify-review-publication.py pr-body \
  --repo <owner/name> --pr <number> --expected-head <40-hex-sha> \
  --body-file contracts/review/pr-<number>/description.md
```

Both modes require raw UTF-8 bytes, the requested repository and pull request, the exact head, and
the canonical URL. Comment mode additionally binds the expected author, comment identity, and
unedited timestamps; the PR-body API does not expose an equivalent body-edit identity. Exit 1 is a
publication mismatch and exit 2 is local I/O, transport, or JSON failure. Nothing else in this
repository can see a posted comment or live PR body, so a publication that is never read back
carries no mechanical evidence, whatever the gate says about its source.

A document that revises published text is built by splicing the published body, not by
retyping the parts that are unchanged. Retyping is how a wrong figure enters, so it is not
the method for removing one.

## What does not go here

Anything bound for GitHub carries technical facts only. Internal strategy, motive, quality
labels, and how the artifact was produced stay out of these files as they stay out of the
comment.
