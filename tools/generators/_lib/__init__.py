"""Shared helpers for the deterministic generator pipeline.

Modules:

  * `fingerprint` — sha256 + canonical content normalization.
  * `output`      — GeneratorMetadata + frontmatter rendering + atomic write.
  * `markdown`    — table builders, anchor helpers, code blocks.
  * `manpage`     — git / svn man-page parsing utilities.

Every helper here is pure-stdlib (no third-party deps), so the generator
pipeline can run inside CI before the project's full dependency tree is
installed. This is the entry-point bootstrap discipline of ADR-029.
"""

from __future__ import annotations
