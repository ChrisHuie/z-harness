# Deferred — rank-A review rules displaced by the 5,000 B body cap

Every rule here is rank **A**: violating it puts a wrong artifact into the world — a false
claim in a PR comment, a lost finding, an unauthorized edit. They are out of `SKILL.md`
because the body is full, not because they are weaker. Read this file when the change under
review is large, is a dependency bump, is a port between repos, is a tooling/CLI change, is
a design or spec document, or when you are about to call something pre-existing, clean, or
out of scope.

The ten names cited from the body are marked `[body]`.

---

## derivative levels `[body]`

Walk four levels before proposing or claiming: the change and its full execution path ·
everything it touches across boundaries · what **masks or proves** those interactions ·
what keeps it true after this session. A proposal grounded only at level 1 is a surface
patch.

## scope test `[body]`

The scope test is not "is it in the title" but: does the expansion let the change land at a
**more correct end state**, and does its principal remain intact? Plumbing that completes
the principal is in scope; a forced title change is drift; **small ≠ in-scope**.

## sweep undercount `[body]`

An enumeration of **explicit occurrences systematically undercounts**. A 4-way scan found
106 explicit sites — roughly 55–60% of the real surface. Sweep twice: once on the
identifier, then again on the **semantic claim**, and enumerate every emission surface for
a value.

## inert declaration `[body]`

A **declaration with no consumer is inert** — it validates, it looks implemented, and
nothing reads it. When checking "is X implemented", find the consumer, not the declaration.
A field known to the schema but unhandled by the backend is silently dropped, because the
validator only rejects *unknown* fields.

## scan-set escape `[body]`

Relocating code **out of a guard's scan set** silently disables it. Widen the guard, never
move the code; a scan-set escape is a silent hatch. (Distinct from the body's "state the
scan set": that one is defense, this one is offense.)

## review tooling `[body]`

Personal tooling that **reviews** others' work must never mutate the shared repo or gate
their CI — the reviewer tier is the ceiling. Check the path is ignored before creating any
file. A tool that MUTATES the files it inspects is disqualified for reviewing someone
else's change.

**Placement dissent, recorded:** this must hold *before* the first Write, which is ARRIVAL
gate A1 — a skill body cannot govern an action that precedes its own load. It belongs in
`~/.claude/CLAUDE.md`, not here.

## dep-bump surface `[body]`

A **dependency bump** is scoped "fix what broke" and blind to changes that break nothing: a
new optional field, a field going optional, a removal, a renamed enum, a swapped nested
type. The authoritative check is a full model-surface delta between the two versions, with
every unhandled change traced as a hypothesis to falsify.

## dormant grader `[body]`

Diff-anchored review **cannot see a test that should cover the change but lives in a file
the diff never touched**. Map the changed field to every scenario that grades it across the
whole corpus, then check each one is actually executing.

## tooling invariant `[body]`

Reviewing a tool or CLI change: state its **cardinal invariant**, adversarially enumerate
the inputs and environment that defeat it, and **run it end-to-end on real input** — its
unit tests mock exactly the environment-bound layer where these bugs live. Catalog-driven
review is strong at "does this violate a known pattern" and weak at "what invariant should
this guarantee that nobody wrote down".

## port norms `[body]`

When porting between two homes, the **target's review norms outrank literal source
fidelity** — fidelity is the means, conformance the end. Record the divergence and file it
upstream. A latent anti-pattern in the source is a bug to fix in the port, not a behavior to
reproduce.

---

The five below are rank A and displaced, but are not name-cited from the body — there were
no bytes left. They fire on the same triggers as their neighbours above.

## reviewer, not steward

On someone else's change you are a **reviewer**: propose, never author, patch, or push.
"Clean and easy" almost always means **narrow**, not correct — the narrow change is fine for
its scope; calling the area clean is the over-optimism.

The never-push half is always-on in `~/.claude/CLAUDE.md` ("Never run `git push`,
`gh pr create/merge/comment`, or `gh issue create` on my own initiative"), which is why this
rule lost its body slot. The **never-author-on-their-branch** half is *not* covered there,
and this is its only home.

## widened constraint

A dependency PR that only **widens** a constraint is a no-op against a frozen lock — green
CI proves the old version still works, which was never in question; the detonation is latent
at the next refresh. Verify by installing the target and running the import lines. A
source-tree 404 at a tag is inference; the installed package is the observation.

## borrowed vocabulary

Reusing a hardened contract's **vocabulary** is not inheriting its **mechanisms** — a design
reads correct precisely because it uses the right words. Per borrowed claim: which
predicate, invariant or guard makes this true, and is it the same one the parent shipped?

## infra excuse

"The environment can't host this" is a **load-bearing claim** needing a throwaway prototype
or a line-level cost read off the actual call sites. A true premise does not license the
deferral, and an infra excuse is the easiest way to quietly take the smaller option because
it sounds like engineering judgement.

## workflow triggers

A security-workflow change can move **which events it runs on** and relocate the merge-block
outside the repo. Diff triggers against BASE and ask what still blocks a fresh,
never-commented request.

---

## Also displaced, rank B/C — full text in the registry, not reproduced here

`PRINCIPLE-REGISTRY.md` §2: R057 vendor gap misfiled as config · R058 type-as-proxy branch ·
R059 same form, different envelope · R060 hand-built error ships a fake success · R061 grade
against the repo's stated bar · R062 pre-apply your own catalog to your own change · R063
one tracking comment edited in place, with the head SHA · R064 re-derive the rationale, not
just the decision · R065 CVE fixes are graded empirically, both sides built · R066 all facts
right, relationships hide the blocker · R067 flawless and still wrong about priority · R068
error-path code that raises shadows the original · R069 rebuilding a typed object drops
unpassed fields · R070 a partial copy of a canonical map · R071 five residual code patterns ·
R072 a framework swap changes defaults, not just APIs.
