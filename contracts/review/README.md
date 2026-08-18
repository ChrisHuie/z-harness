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
requires the registered PR description and roll-up includes, and rejects unregistered live
blocks. `tools/write-mutation-receipt.py` writes the receipt and summary from one accepted
aggregate of exact-plan shard fragments; its normal aggregate mode refuses changed output.
Historical measurements may remain as context only when the document says they are not
final-head evidence; the include gate does not validate those free-prose claims.

## Layout

    contracts/review/pr-<number>/rollup.md         the one roll-up comment, edited in place
    contracts/review/pr-<number>/description.md    the pull request body
    contracts/review/pr-<number>/title.txt         the pull request title

One roll-up per pull request, edited rather than reposted. Individual findings are inline
`path:line` threads and are not drafted here: a finding in a roll-up has no lifecycle and
drops out unaddressed.

The description and title live here for the same reason the roll-up does: both carry measured
figures, and a figure edited on GitHub is outside every check in this repository. Build each
by editing the file and posting from it, never by retyping a number into the web form.

A document that revises published text is built by splicing the published body, not by
retyping the parts that are unchanged. Retyping is how a wrong figure enters, so it is not
the method for removing one.

## What does not go here

Anything bound for GitHub carries technical facts only. Internal strategy, motive, quality
labels, and how the artifact was produced stay out of these files as they stay out of the
comment.
