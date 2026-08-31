# Review instruments

Measurement scripts the PR review handoffs describe, kept so the published figures can be
regenerated instead of re-derived.

## Single-operand survivor enumeration

    python3 enumerate_survivors.py <module.py> [extra sibling files/dirs to copy]

Over every top-level function except `selftest` and the CLI `main`: each `if`/`elif` test is
replaced by `False`; each `and`/`or` operand is replaced by its identity; and each
non-constant `return` is replaced by `True` and by `False` (two mutants, with a site killed
only when both are killed). The pristine source must first emit one terminal green receipt.
A mutant is killed only by one terminal red receipt for the same suite and check count
with assertion-failure exit 1; timeout, crash, missing receipt, count drift, every other
exit, and setup failure are instrument errors.
Fixture symlinks and Python bytecode caches are rejected. Each completed private copy is
checked against its recorded digest before and after execution. The report binds those
starting and ending snapshots, not transient changes restored by the code under test or
arbitrary undeclared file reads. JSON is written to stdout, progress to stderr, and the
checkout is not modified.

## Differential judge fuzz

    python3 fuzz_judge_diff.py <oracle_guard.py> <candidate_guard.py> <seed> <count>

Compares Stop-guard verdicts between two guard sources in isolated workers over
grammar-generated endings. Instrument and guard bytes are captured once; each side gets a
separate private snapshot that is verified before and after execution, and the guard is
compiled directly without import bytecode. Runtime reads through the guard's `__file__`
resolve to that private snapshot; the original path remains only the compile filename used
in tracebacks. The deterministic prefix
covers every production and renders every supported delimiter before random cases begin.
JSON on stdout retains every case; stderr summarizes block-to-allow, allow-to-block, and
block-reason changes separately, and reports how many cases the oracle blocked. A
block-to-allow divergence exits 1 and an instrument failure exits 2.

A run whose oracle blocked nothing exits 2 rather than green: with no oracle block every
case can only classify as agreement or allow-to-block, so a clean verdict would be entailed
by the run instead of measured by it.

The vocabulary bounds what a null result proves; extend it with the tokens a change touches.
Two vocabularies do different jobs. Tokens drawn from the guard's own tables detect a
NARROWED table -- a generated token stops being admitted. They cannot detect a WIDENED one,
because the grammar never emits the token a widening would newly admit. `NEAR_MISS_MODIFIERS`,
`NEAR_MISS_CONTEXTS` and `NEAR_MISS_TERMS` are drawn from outside every uppercase collection in
the guard for
that direction -- not merely outside the table each one probes, since a token with meaning in a
sibling table can block for that reason instead and score a control that cannot fail. Each must
block today and starts allowing the moment a table grows to cover THAT TOKEN. The mandatory
prefix pins every one of them, so such a widening diverges at the minimum case count. Three
of the guard's collections are covered that way. The selftest applies every pinned token as an
actual one-literal widening of a private shipped-guard copy and requires the matching production
to change from block to allow; merely rendering the token is not sufficient. A widening elsewhere may still diverge --
whether it does depends on whether a grammar string spells the admitted token into a position
the guard reads -- so a clean run over an unpinned collection proves nothing. Adding a token to
a guard table means adding a near-miss beside it, or the next widening is a null result. Source symlinks are rejected. The report binds the two top-level guard
sources and their runtime `__file__` reads, not modules they import from the interpreter
environment.

Adding a production is not free. `FLAT_SHARE` pins the random arm, but the remaining share
is split across the structured productions, so every existing one loses coverage per case
when a new one lands -- the near-miss additions roughly halved the per-production share of
the productions that predate them. The pinned mandatory prefix is unaffected; only the
random tail thins. Raise the case count, or check the realized split, with:

    python3 -c "import importlib.util,sys,collections; \
      s=importlib.util.spec_from_file_location('f','fuzz_judge_diff.py'); \
      f=importlib.util.module_from_spec(s); sys.modules['f']=f; s.loader.exec_module(f); \
      t=f.generate(9,20000)[f.MIN_CASES:]; \
      print(collections.Counter(c['production'] for c in t))"

Both figures move with the enumeration and the grammar. Publish the invocation with the
number.
