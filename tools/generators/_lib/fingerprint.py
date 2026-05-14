"""Canonical content normalization + sha256 helpers.

These are the primitives every generator's `output_sha256` is built from.
Determinism rules:

  * UTF-8 encoded.
  * LF line endings (no CR; no CRLF).
  * Final newline preserved (do not strip).
  * No trailing whitespace on lines? — NOT enforced here. Trailing whitespace
    inside a generated table cell may be intentional alignment; leave it alone
    and let the markdown linter decide elsewhere.

The `extract_body` function separates a file's YAML frontmatter from its body
so `verify_generated.py` can re-hash the body alone (the frontmatter contains
the `output_sha256` we're verifying against, so it can't be part of the hash
input — that would be circular).

Per ADR-030 these helpers are intentionally small and well-tested; every
catalog appendix's integrity reduces to a sha256 over an output of one of
these functions.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

LF = "\n"
ENCODING = "utf-8"

# The frontmatter block delimiters used by every generated file (per §16.4.1
# of `.design/sange-architecture-prompt.md`). Lower-case `---` on a line by
# itself; first occurrence opens, second occurrence closes.
FRONTMATTER_DELIMITER = "---"


def canonical_bytes(text: str) -> bytes:
    """Return text as UTF-8 bytes with LF line endings.

    Pure function: same input → same output, byte-for-byte. The only state
    is the constants above.
    """

    if "\r\n" in text:
        text = text.replace("\r\n", "\n")
    if "\r" in text:
        text = text.replace("\r", "\n")
    return text.encode(ENCODING)


def sha256_bytes(blob: bytes) -> str:
    """Lower-case hex sha256 of an exact byte string."""

    return hashlib.sha256(blob).hexdigest()


def sha256_text(text: str) -> str:
    """Lower-case hex sha256 of canonically-normalized text."""

    return sha256_bytes(canonical_bytes(text))


def sha256_file(path: Path) -> str:
    """Lower-case hex sha256 of a file's bytes — as-is, no normalization.

    Use this for input fingerprinting (the `input_sha256` field) where the
    file is the source-of-truth and must match byte-for-byte. For body
    fingerprinting (the `output_sha256` field) use `sha256_text` so generated
    files normalized identically to the verifier.
    """

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_body(text: str) -> tuple[str, str]:
    """Split a generated file into (frontmatter, body).

    A "frontmatter" block opens with a line containing only `---` (no
    preceding whitespace) and closes with the next such line. If the file
    does not start with `---`, returns (``, text) — i.e. the entire content
    is body.

    Both the opening and closing `---` delimiter lines are *included* in the
    returned `frontmatter` string. The `body` is everything after the closing
    delimiter, with the leading newline of the body preserved.

    Returns canonical (LF-newlined) strings.
    """

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        return "", text

    # Find the closing delimiter.
    for idx in range(1, len(lines)):
        if lines[idx].strip() == FRONTMATTER_DELIMITER:
            front = "\n".join(lines[: idx + 1]) + "\n"
            body = "\n".join(lines[idx + 1 :])
            # Strip a single leading newline if present so the body sha is
            # stable whether or not the writer left a blank line.
            body = body.lstrip("\n")
            return front, body

    # No closing delimiter — treat as body-only (and let the verifier flag).
    return "", text


def body_sha256(text: str) -> str:
    """Convenience: extract the body from a file's text and sha256 it."""

    _front, body = extract_body(text)
    return sha256_text(body)
