> **RETIRED 2026-08-02 — all three machine facts are APPLIED** (live `~/.claude/CLAUDE.md`
> "## This machine"). Derivation record only; nothing here is pending.

# Proposed `~/.claude/CLAUDE.md` lines — three machine facts

Not applied. `~/.claude/CLAUDE.md` was **not edited** by this pass. These three were parked
in the `-Users-quantum` home silo by the registry (§12 MACHINE). A project-memory directory
does not load across directories (CLAUDE.md:14), and all three are needed *while working in
some other project's directory* — so a silo is the one destination that guarantees they are
absent when they fire. They must arrive unprompted; a skill body cannot deliver them,
because the cue that would load this skill ("spawn agents") is not the cue that fires them.

Each is one line. Placement is given against the live file as read on 2026-08-02 (10,368 B,
179 lines).

---

**1. `timeout` is not installed** — registry R276. Rank A: a command that "should just work"
silently fails, and every wrapper built on it is dead on arrival.

Add under **Agent dispatch → Preflight**, beside the existing `df` / `docker info` block:

```
- `timeout` is NOT installed on this Mac (`which timeout` → not found). Any command
  needing a wall-clock bound needs its own; do not wrap a dispatch in `timeout`.
```

---

**2. Docker's stale-Electron-singleton signature** — registry R275. Rank A. The *fix* is
already verbatim at CLAUDE.md:51-52; what is missing is how to recognize the condition and
the negative result that saves a wasted reinstall.

Amend the existing CLAUDE.md:51-52 bullet in place — do not add a second bullet:

```
- Docker dead after a hard crash = stale Electron singleton. Signature: launch exits 0
  while spawning no process, log reads `unmarshaling start request: unexpected EOF`;
  deleting `backend.lock` does NOT fix it. Fix:
  `rm ~/Library/Application\ Support/Docker\ Desktop/Singleton{Cookie,Lock,Socket}`
  then `open -a Docker`.
```

---

**3. The system Python fails TLS verification** — registry R283. Rank A: it presents as a
remote host being down or a cert being bad, and the wrong diagnosis is the expensive one.

Add under **Claims and evidence** or **Verification** (it is a "your instrument is lying"
fact, not a dispatch fact):

```
- The system Python fails TLS verification against some hosts. A cert error from
  `/usr/bin/python3` is an instrument failure, not a remote failure — drive the vendor CLI
  via subprocess instead of the stdlib client.
```

---

## Cost

~11 added lines against CLAUDE.md's current 179. Registry §16.6 already records that the
CLAUDE.md additions land at 11 lines against SKILL-SET §5's ~9-line budget; these three are
**on top of** that, so the combined ask is ~22 lines / ~1,900 B (18% growth). That is a
decision for the diet pass, not something to wave through — but the routing verdict stands
either way: the silo is the wrong home, because it is the one home that cannot fire.
