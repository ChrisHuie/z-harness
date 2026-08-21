# Outbound review text

Publication policy and frozen pull-request metadata live here. Head-specific review text is
prepared only after exact-head verification and posted as a new comment.

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

`tools/ci-gate.py` checks every live include block under this directory against its source and
enforces the exact relative-path inventory `README.md` and
`pr-8/frozen-publication.json`. A nested duplicate, symlink, missing file, mutable body draft,
renamed handoff, or restored roll-up is rejected.
`tools/write-mutation-receipt.py` writes the receipt and summary from one accepted
aggregate of exact-plan shard fragments; its normal aggregate mode refuses changed output.
Historical measurements may remain as context only when the document says they are not
final-head evidence; the include gate does not validate those free-prose claims.

## Layout

    contracts/review/pr-<number>/frozen-publication.json    frozen body/title digests

Head-specific handoffs are append-only external comments, one verified head per comment.
Never edit, replace, or delete a published handoff. A later head or correction gets a new
comment that links the earlier record and states what changed. Individual findings remain
inline `path:line` threads because a PR-level handoff has no finding lifecycle.

All published PR narrative is append-only. The pull-request body and title are frozen after
initial publication; later summaries, corrections, and exact-head evidence are new comments.
The frozen manifest records only the bytes observed when this rule was adopted. It does not claim
that GitHub independently attested who wrote the earlier body or when an earlier edit occurred.

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

tools/verify-review-publication.py pr-snapshot \
  --repo <owner/name> --pr <number> --expected-head <40-hex-sha> \
  --manifest contracts/review/pr-<number>/frozen-publication.json
```

Both modes require the requested repository, pull request, exact current head, and canonical URL.
Comment mode additionally binds raw UTF-8 body bytes, the expected author, comment identity, and
unedited timestamps. Snapshot mode binds the live body and title bytes to the frozen manifest; the
PR API exposes no body-edit identity or timestamp, so the receipt proves current equality, not the
history before the snapshot. Exit 1 is a publication mismatch and exit 2 is local I/O, transport,
or JSON failure. Nothing else in this repository can see a posted comment or live PR body, so a
publication that is never read back carries no mechanical evidence, whatever the gate says about
its source.

Comment receipts classify `terminal_line_feed` as `retained`, `stripped`, or `mismatch`. The first
two values are emitted only when the complete published bytes equal one accepted source form;
byte-comparison failures use `mismatch` and retain the canonical submitted byte count and digest.
A metadata failure may still report `retained` or `stripped` when the body bytes matched that form;
the separate `verified` and `problem` fields carry the overall publication verdict.

A correction never rewrites published text. Build a new comment that states the correction,
links the superseded publication, and binds the evidence to the new exact head.

## What does not go here

Anything bound for GitHub carries technical facts only. Internal strategy, motive, quality
labels, and how the artifact was produced stay out of these files as they stay out of the
comment.
