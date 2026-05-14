# Phase-boundary snapshots

> Cold-resume artifacts. One snapshot per phase boundary. The snapshot lets a fresh session — human or model — pick up the build at the exact point the prior session stopped, even if all chat history is lost.

## When to write a snapshot

A new snapshot is written **before** declaring a phase complete:

- Phase 0a → 0b transition (generators emitted everything; about to start business logic)
- Phase 0b → 1 (CLI happy path works; about to start beta features)
- Phase 1 → 1.5 (beta features land; about to start v0.5 hardening)
- Phase 1.5 → 2 (v0.5 ships; about to start Web UI)
- Phase 2 → 2.5 (Web UI lands; about to start v1.0 release prep)
- Phase 2.5 → 3, Phase 3 → 4 (v1.0/v2.0/v3.0 GA boundaries)
- Any time the project state would take more than 30 minutes to reconstruct from the session-log alone

The §22 step 11.5 Continuity Check refuses to declare Deliver done if the latest snapshot is older than the most recent `git commit`.

## Filename convention

```
phase-<N.M>.md
```

Where `N.M` matches the phase tag from `implementation-plan.md`:

- `phase-0a.md` — end of Phase 0a (generators emitted)
- `phase-0b.md` — end of Phase 0b (business logic landed)
- `phase-1.md`, `phase-1.5.md`, `phase-2.md`, `phase-2.5.md`, `phase-3.md`, `phase-4.md`, `phase-5.md`

A re-snapshot mid-phase (e.g. after a major refactor that materially changes resume conditions) is named `phase-<N.M>-<slug>.md` (e.g. `phase-0b-purge-engine-rewrite.md`).

## Snapshot template

```markdown
# Snapshot — Phase <N.M> — <YYYY-MM-DD>

**Created:** <YYYY-MM-DDTHH:MMZ>
**Created by:** <user@host or model:claude-opus-4-7@user@host>
**Last git commit:** <SHA-short> "<commit subject>"
**Reason for snapshot:** <phase boundary | mid-phase pause | resume-friendly checkpoint>

## State of the world

### Tasks completed this phase
- T-NNN — short description (closed in S-NNN-T-MM)
- T-NNN — …

### ADRs accepted this phase
- ADR-NNN — short title
- ADR-NNN — …

### Risks closed this phase
- R-NNN — short title (closing reason)

### Risks opened this phase
- R-NNN — short title

### Generators state
- T-G-NNN `<generator>.py` — output_sha256: `<sha>` — emitted at <ts>
- (one row per generator that ran in this phase)

### Files materially changed (vs prior snapshot)
- src/sange/cli/app.py — added `commits` subcommand tree
- (one row per file with a one-sentence "what changed")

## What the next session must do

A fresh session with only `.design/` access should be able to read this section and know exactly what to do next.

1. **First task:** T-NNN — `<short description>`
2. **Where to start reading:** `<file:line>`
3. **Current branch:** `<branch-name>`
4. **Active in-flight operations** (purges, bundles, gitignore-swap recovery files): `<list or "none">`
5. **Open `🧪` clarifying questions for the user:** `<list or "none">`

## Resumability test result

- [ ] A fresh session given only the build-kickoff prompt + this snapshot correctly identifies the next task.
- [ ] The fresh session does not need to ask for additional context that should have been in this snapshot.

If either box is unchecked, the snapshot is incomplete — fix it before declaring the phase done.

## Audit-chain link

The runtime audit-chain entry `entry_hash: <sha>` (from `.sange/audit/<latest>.jsonl`) corresponds to the `git commit` above. Cross-reference for tampering detection.
```

## How a session uses snapshots (crash-recovery protocol per ADR-031)

A session that resumes from crash:

1. List `.design/plans/snapshots/` and pick the most recent file by mtime.
2. Read it end-to-end.
3. Read `git status` + `git log --oneline -10` for the delta since the snapshot.
4. Read `.sange/.recovery` (gitignore-swap) and `.sange/purge/<latest>/plan.json` (purge) for in-flight operations.
5. Read the in-progress task's description from `checklist.md` (using the `linked` column of the last `session-log.md` row).
6. Read the files the prior session marked `files_touched` in its last row.
7. Append a new session-log row with `notes: "previous_session_resume from snapshots/phase-<N.M>.md"`.
8. Continue the next task from the snapshot's "What the next session must do" section.

## Fork-friendliness

The snapshot template is **`🟡 META`** — reusable for any future agency project. The phase numbering (`0a / 0b / 1 / 1.5 / …`) is project-specific; replace with the new project's phase tags when forking.

---

*Append-only directory. Snapshots are durable artifacts; never delete a snapshot that's older than the current phase.*
