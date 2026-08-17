# Outbound review text

Review text that will be posted to a pull request is drafted here and posted from here.

The reason is narrow. Everything else this repository asserts is inside a gate: source
digests pin bytes, `guard-decisions.json` pins verdicts, `SUITE_FLOORS` ratchets check
counts, `mutation-receipt.json` pins what the suites catch. A GitHub comment is inside none
of them. Three mutation counts published on this branch's review were the subset under
attention rather than the suite total the surrounding sentence claimed, and no check in the
repository could have seen them, because the artifact lived where no check can reach.

## The rule

A measured number belongs in a generated file, and outbound text INCLUDES that file rather
than restating it:

```
<!-- include: contracts/goldens/mutation-summary.md -->
...byte-identical copy of that file...
<!-- end include -->
```

`tools/ci-gate.py` checks every include block under this directory against its source and
fails on a stale copy, so a table cannot drift in the copy a reviewer actually reads.
Regenerate with `tools/write-mutation-receipt.py`, which writes the receipt and the summary
from the same run.

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
