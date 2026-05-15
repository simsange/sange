---
generated_by: hand-authored (detail file backfilled for an accepted ADR)
generator_version: n/a
generated_at: 2026-05-16T04:30:00Z
manual_edits_allowed: true
---
# ADR-0031: Memory preservation + crash-recovery + resumability (audit-trail append-only)

**Status:** Accepted
**Date:** 2026-05-14 (concurrent with the architecture v4.4 lock)

## Context

Sange is built across long-running sessions — human and model. Each
session adds to a working tree, files in `.design/`, decisions in
ADRs, ephemeral conversation context, and runtime state in
`.sange/`. Three failure modes recur on a project this size:

1. **Mid-task crash.** The host or the chat session dies. The
   ephemeral conversation is lost. The next session must pick up
   the work from disk alone.
2. **Stale memory.** Someone (human or model) recalls a "fact"
   from an earlier session that's been superseded — a path
   renamed, a flag removed, a decision overturned. Acting on the
   stale fact corrupts state.
3. **Audit-trail tampering.** A change lands without a record of
   why. Six months later nobody can explain it; rolling it back
   risks reverting something that was actually intentional.

Without explicit discipline, all three failures eat into delivery
velocity. The project's earliest session-log entries
(`S-001-T-{1..N}`) include examples of all three biting before the
discipline was formalized.

The decision concerns **what to write, where, when, and how to
ensure it's never silently rewritten**. The discipline has to
work for both human and AI contributors, across solo sessions
and multi-author sessions, and survive context-window resets.

## Decision

`.design/` is the memory. The chat is ephemeral. **Three durable
append-only surfaces** capture the audit trail:

1. **`.design/plans/session-log.md`** — one row per completed
   task. Every row carries:
   - `id`: `S-NNN-T-MM` — session number + task number.
   - `timestamp`: ISO 8601.
   - `actor`: human user / model name / both.
   - `surface`: code / docs / snapshot / etc.
   - `action`: prose describing what was done.
   - `files_touched`: backtick-quoted paths.
   - `grounding`: every file read before the action (the
     "anti-hallucination" column extending ADR-028 — proves the
     action wasn't guessed).
   - `linked`: cross-references to ADRs / risks / other rows.
   - `audit_chain`: free-text continuity tag.
   - `notes`: outcomes + open questions.
2. **`.design/plans/snapshots/phase-<N.M>.md`** — phase-boundary
   cold-resume artifacts. One snapshot per phase transition
   (Phase 0a → 0b → 1 → 1.5 → 2 → 2.5 → 3 → 4 → 5). Plus
   mid-phase re-snapshots when "the project state would take more
   than 30 minutes to reconstruct from the session-log alone"
   (the snapshot README's threshold).
3. **`.sange/audit/<ISO-week>.jsonl`** — runtime hash-chained
   audit log. Each record contains a hash of the previous
   record's content; tampering breaks the chain. Per-repo, written
   by every state-changing operation in the daemon.

**Three discipline rules** govern the surfaces:

1. **Append-only.** Existing rows are never modified or deleted
   once committed. If a row was wrong, the next row corrects it
   and explains. If a fact is stale, a fresh row supersedes it.
2. **Grounding-column non-empty for every row from S-001-T-20
   onward.** `verify_session_log.py` enforces this in CI; any
   merged row missing grounding fails the check.
3. **Crash-recovery protocol** (the §22 step 11.5 Continuity
   Check) — a session that resumes from crash:
   1. Reads `.design/plans/snapshots/` for the most recent
      snapshot.
   2. Reads `git status` + `git log --oneline -10` for the delta
      since the snapshot.
   3. Reads `.sange/.recovery` (gitignore-swap recovery state)
      + `.sange/purge/<latest>/plan.json` for in-flight
      operations.
   4. Reads the in-progress task's description from
      `checklist.md`.
   5. Reads the files the prior session marked `files_touched` in
      its last row.
   6. Appends a new session-log row with notes:
      `"previous_session_resume from snapshots/phase-<N.M>.md"`.
   7. Resumes the next task from the snapshot's "What the next
      session must do" section.
4. **Audit-chain integrity** — links design-time
   (`session-log.md`) and runtime (`.sange/audit/*.jsonl`)
   entries via cross-references. The `linked` column in
   session-log rows may reference runtime audit entries; the
   §11 audit chain may reference session-log task IDs.

The §22 step 11.5 Continuity Check **blocks the Deliver step**
if the latest snapshot is older than the most recent
`git commit` on the current branch, or if any session-log row
is missing required fields. Resumability test at each phase
boundary verifies a fresh session can pick up from the snapshot
alone.

## Alternatives Rejected

- **Trust git history as the audit trail.** Rejected because
  git's commit messages are summary-grade, not decision-grade —
  they capture *what* changed, not *what alternatives were
  considered* or *what the model was thinking*. The session-log
  fills that gap. Also, `git log` doesn't survive squash-merges
  or interactive rebases; the session-log is its own file.

- **Use a database for the audit log.** Rejected — adds a new
  dependency, adds a runtime surface, breaks the "everything is
  a file in the repo" property that makes `.design/` durable
  across forks. JSONL on disk preserves the same invariants with
  zero runtime cost.

- **Mutate session-log rows when facts change.** Rejected because
  the rows become unreliable as historical record. A reader can't
  tell whether they're looking at the truth-at-the-time or the
  truth-now. Append-only means the trail is forensically usable.

- **Skip snapshots; use commit messages alone for cold-resume.**
  Rejected because a "what should I do next?" question needs more
  than the last commit message — it needs the phase context, the
  open tasks, the in-flight operations, the resumability test
  result. Snapshots package all of that in one place.

- **Per-session log files instead of one accreting file.**
  Rejected because cross-session links (a row referencing a
  decision from three sessions ago) get harder to validate
  across many files. One growing file with grep-able structure
  beats many small files for the project's read patterns.

- **Use the `git notes` mechanism** for the design audit trail.
  Rejected because `git notes` doesn't replicate by default;
  forks lose them silently. Files in `.design/` replicate
  unconditionally.

## Consequences

### Positive

- **Crash-recovery is bounded.** Any session can pick up from
  the latest snapshot + the latest session-log row + the latest
  commit, with a documented protocol. No "what was I doing?"
  state.
- **Hallucinations are catchable.** The `grounding` column means
  every action has a documented source. Reviewers can spot-check
  ("you said you read X; let me verify").
- **Decisions are forensically reconstructible.** Six months
  later, the session-log + ADR-trail + snapshots show what
  decision was made when, who made it, and why.
- **Runtime + design audit chains link.** A purge operation's
  runtime JSONL entry references the design-time session-log row
  that authorized the operation. End-to-end traceability.
- **`verify_session_log.py` makes the discipline self-enforcing.**
  CI fails if the rules are violated; nobody has to remember to
  check manually.

### Negative

- **Session-log row writing has overhead.** Every completed task
  needs ~3-5 lines of structured prose. Across a long project,
  this is hours of cumulative writing. Mitigated by the value
  (see Positive #4 + #3) and by the fact that the rows are
  grep-able + searchable.
- **The append-only rule occasionally feels wrong.** When you
  realize a row was misleading, the instinct is to fix it.
  Discipline says: write a new row that corrects it. Living with
  the friction is the cost of the forensic property.
- **Snapshots are big.** Each is ~200-400 lines. Cold-resume
  readability requires that bulk; trimming would defeat the
  purpose.

### Neutral

- **`.sange/audit/*.jsonl` is per-repo, not per-machine or
  per-user.** Multi-user teams accumulate audit records from
  every contributor; this is correct but worth noting.
- **The snapshots include some redundancy with the session-log.**
  Snapshots are point-in-time summaries; session-log is
  per-task. The redundancy is intentional and serves different
  read patterns (snapshot for cold-resume, session-log for
  "when did X happen").

## Lens Notes

- **Security**: the audit chain is the project's tamper-evident
  surface. ADR-018 (release-as-immutable) builds on it. Without
  the hash-chained property, an attacker who landed a malicious
  commit could quietly rewrite the audit log to cover their
  tracks.
- **Maintainability**: the session-log + snapshots are the
  project's most-touched files (every commit produces a row).
  The conventions stay simple specifically because they have to
  be written by hand on every task.
- **DX**: writing session-log rows is the highest-overhead part
  of contributing. The cost is real but the value compounds — a
  contributor returning after months of absence can read the log
  and orient.
- **Operability**: zero runtime overhead from design-time logs.
  Runtime JSONL writes are O(1) per state change.
- **Cost**: zero financial cost. Storage cost is negligible
  (session-log is ~hundreds of KB).

## Cross-references

- [`.design/plans/session-log.md`](../../.design/plans/session-log.md)
  — the canonical append-only audit-trail file.
- [`.design/plans/snapshots/`](../../.design/plans/snapshots/)
  — phase-boundary + mid-phase cold-resume artifacts.
- [`.design/plans/snapshots/README.md`](../../.design/plans/snapshots/README.md)
  — naming conventions + crash-recovery protocol.
- [`tools/generators/verify_session_log.py`](../../tools/generators/verify_session_log.py)
  — T-G-016 CI check enforcing the discipline.
- [`../governance/adr-process.md`](../governance/adr-process.md)
  — ADR-031 is cited extensively there for the "ADRs are
  append-only" rule.
- [`../governance/privacy.md`](../governance/privacy.md) — the
  audit-chain section explains the local-only privacy posture
  this ADR creates.
- [`../security/prompt-injection.md`](../security/prompt-injection.md)
  — the AI-call audit records live in the same chain.
- ADR-018 (release-as-immutable) — pushed tags can never move;
  the audit chain is what makes that property enforceable.
- ADR-028 (grounding for AI actions) — superseded conceptually by
  ADR-031's `grounding` column.
- ADR-030 (anti-hallucination) — close sibling; ADR-031 is the
  durability layer, ADR-030 is the input-side discipline.
- [`../../.design/plans/decisions-log.md`](../../.design/plans/decisions-log.md)
  row 39 — the master-log row this detail expands.
- §22 step 11.5 (Continuity Check) of the canonical architecture
  deliverable — the CI gate this ADR creates.
