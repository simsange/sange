"""Sange v3 deterministic generators.

Per ADR-023 (generate-first, fine-tune-second) and ADR-029 (generators scaffold
everything), the generators under this package emit catalog appendices, kit
fragments, the docs index, schema references, the STRIDE table, and most of
the surrounding scaffolding the v3 codebase needs — deterministically, with
hash-emitting frontmatter, verifiable by `tools/generators/verify_generated.py`.

Layout:

    tools/generators/
    ├── _lib/                shared helpers (fingerprint, output, markdown, manpage)
    ├── verify_generated.py  CI integrity check
    ├── all.py               orchestrator (run every generator in dependency order)
    └── <name>.py            one file per T-G-NNN task

Generators emit YAML frontmatter per §16.4.1 of `.design/sange-architecture-prompt.md`:

    ---
    generated_by: tools/generators/<name>.py
    generator_version: <semver>
    generated_at: <ISO-8601 UTC>
    input_sha256: <hash of input>
    output_sha256: <hash of body — re-verified by verify_generated.py>
    manual_edits_allowed: false
    ---

Disciplines (per ADR-023):

  * Deterministic — same input → same output. No LLM in the loop.
  * Versioned — bump `generator_version` on every change.
  * Hash-emitting — output is integrity-verifiable.
  * No randomness — UUIDs forbidden; timestamps come from a single `--clock`
    flag defaulting to the input-data mtime.
"""

from __future__ import annotations

__all__: list[str] = []
