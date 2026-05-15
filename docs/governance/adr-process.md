# How Sange records decisions (ADR process)

Sange uses lightweight **Architecture Decision Records** for every
non-trivial design choice. This file is the operator's manual for
that process — how to read existing ADRs, when to write a new one,
and how to scaffold the file.

For the broader project context, see
[`roadmap.md`](roadmap.md).

## What's an ADR

An ADR is a single, immutable, append-only record of one decision:
the situation, what was chosen, what was rejected, and the
consequences. Sange follows the
[Michael Nygard pattern](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
with a couple of Sange-specific additions (the **Lens Notes** line
covering Security / Performance / Maintainability / DX / Operability
/ Cost trade-offs).

The discipline that matters:

- One decision per ADR.
- ADRs are **never edited** after they're accepted. If the decision
  changes, write a new ADR that supersedes the old one (status:
  `Superseded by ADR-XXX` on the original).
- Numbering is sequential, never reused.
- Every non-trivial change in the codebase points at an ADR for
  rationale.

## Two surfaces, one decision

Each accepted ADR lives in **two places**:

| Surface | Purpose | Length |
| :--- | :--- | :--- |
| [`.design/plans/decisions-log.md`](../../.design/plans/decisions-log.md) | Master index — one row per ADR with status + one-paragraph summary. The reader skims this to find the relevant decision. | ~5 lines per ADR |
| `docs/adr/<NNNN>-<slug>.md` | Detail file — full context, decision, rejected alternatives, consequences, lens notes. The reader drills down here for the why. | ~50-300 lines per ADR |

Not every ADR has a detail file yet — the project shipped 33 ADRs
in the prompt-architecture phase before the discipline of writing
a separate file per ADR was enforced. The two detail files that
exist today
([`0032-variant-matrix-android-studio-inspired.md`](../adr/0032-variant-matrix-android-studio-inspired.md)
and [`0033-multi-arch-docker.md`](../adr/0033-multi-arch-docker.md))
set the pattern. Pre-32 ADRs live only in the decisions log;
their detail files land as those subsystems are implemented.

## The template

```markdown
### ADR-NNN: <short title>

**Status:** Proposed | Accepted | Superseded by ADR-XXX
**Date:** YYYY-MM-DD
**Context:** What is the situation? What forces are at play?
**Decision:** What was decided, in one sentence, plus elaboration.
**Alternatives Rejected:**
  - Alternative A — rejected because …
  - Alternative B — rejected because …
**Consequences:**
  - Positive: …
  - Negative: …
  - Neutral: …
**Lens Notes:** One line per relevant lens (Security / Performance /
                Maintainability / DX / Operability / Cost).
```

For the detail file format, see the existing examples — they
expand each section into prose, code blocks, and concrete
implementation hooks.

## When to write an ADR

Write one for:

- A choice between **two or more reasonable options** where the
  rationale isn't obvious from the code (library choice, protocol
  choice, file layout, command surface).
- A **deviation from a convention** the project would otherwise
  inherit (e.g. choosing Apache 2.0 over MIT — that's
  [ADR-007](../../.design/plans/decisions-log.md)).
- A **constraint that's expensive to discover** but cheap to record
  (e.g. why a dependency floor is what it is — ADR-019).
- A **superseding** of an earlier decision (write the new ADR, mark
  the old one `Superseded by`).

**Don't** write one for:

- Implementation details that don't outlive a single PR.
- Decisions that are obvious from reading the code (naming, file
  organization within a module, indentation).
- Bug fixes (those go in `CHANGELOG.md`).
- One-off operational events (those go in
  [`session-log.md`](../../.design/plans/session-log.md)).

The test: **"if a new contributor in 18 months asks 'why is it like
this?', would the answer be in the ADR, or trivially in the code?"**
If the answer is in the ADR, write it.

## How to scaffold a new ADR

The project ships a generator for the detail-file boilerplate:

```bash
python tools/generators/adr_scaffold.py "Switch to Pydantic v3"
```

Flags:

| Flag | Purpose |
| :--- | :--- |
| `--slug TEXT` | Override the auto-generated slug. |
| `--number N` | Override the auto-detected next number (re-numbering only). |
| `--summary TEXT` | One-line context to seed the Context field. |
| `--dry-run` | Print the target path without writing. |
| `--overwrite` | Allow overwriting an existing file (dangerous). |

`adr_scaffold.py` picks the next available number by scanning
`docs/adr/` + the decisions log. The next slot today is **ADR-034**
(see the "Next ADR slot" section at the bottom of
[`decisions-log.md`](../../.design/plans/decisions-log.md)). After
the file is written, the author:

1. Fills in Context / Decision / Alternatives / Consequences / Lens.
2. Adds a row to the master index in
   [`.design/plans/decisions-log.md`](../../.design/plans/decisions-log.md)
   with the same number + title + status + one-paragraph summary.
3. Bumps the "Next ADR slot" marker.
4. Submits the PR with the ADR as a single commit if possible.

The PR review focuses on:

- Whether the decision is actually as binary as the ADR presents it.
- Whether the rejected alternatives are real and were genuinely
  considered (not strawmen).
- Whether the consequences cover the durable trade-offs, not just
  the immediate win.

## Status lifecycle

```
Proposed ──accepted via PR merge──▶ Accepted
                                         │
                                         │
                                         ▼
                                    Superseded
                                    by ADR-XXX
```

`Proposed` is a transient status the ADR carries while the PR is
open. Merge implicitly transitions it to `Accepted`. The only way
an ADR leaves `Accepted` is by being superseded by a new one — the
old file stays on disk with the updated status line.

## Where to look for examples

| ADR | Why it's a good example |
| :--- | :--- |
| [ADR-001](../../.design/plans/decisions-log.md) | Foundational architectural split (Python core + Laravel UI via JSON-RPC) — minimal but load-bearing. |
| [ADR-007](../../.design/plans/decisions-log.md) | License choice (Apache 2.0). One paragraph, one decision, clear rejected alternative (MIT). |
| [ADR-029](../../.design/plans/decisions-log.md) | "Generate-first then fine-tune" — process ADR, not architecture. Shows the form works for workflow decisions. |
| [ADR-031](../../.design/plans/decisions-log.md) | Audit-trail append-only rule. Shows how an ADR encodes a discipline that touches every other surface. |
| [ADR-032](../adr/0032-variant-matrix-android-studio-inspired.md) | First ADR with a detail file. Shows the expanded format with code blocks + implementation hooks. |
| [ADR-033](../adr/0033-multi-arch-docker.md) | Second detail file. Builds on ADR-032's format but for a smaller-scope decision. |

## Related references

- [`.design/plans/decisions-log.md`](../../.design/plans/decisions-log.md)
  — master index, all 33 accepted ADRs.
- [`docs/adr/`](../adr/) — detail files (currently 0032 + 0033).
- [`tools/generators/adr_scaffold.py`](../../tools/generators/adr_scaffold.py)
  — the scaffolder source.
- [`roadmap.md`](roadmap.md) — where the project is going.
- [`.design/plans/session-log.md`](../../.design/plans/session-log.md)
  — the append-only audit-trail this process is the architectural
  counterpart to.
