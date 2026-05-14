"""Sanity check the package imports and exposes __version__.

This is the minimum-viable test that proves the T-001 scaffolding is wired up
correctly. T-040 onwards will add CLI / domain / adapter tests.
"""

from __future__ import annotations

import re

import sange


def test_package_exposes_version() -> None:
    assert isinstance(sange.__version__, str)
    assert sange.__version__ != ""


def test_version_is_pep440_compliant() -> None:
    # PEP 440 release pattern (intentionally permissive; the dev-release suffix
    # the v0.1 MVP build phase ships with matches the optional `.devN` block).
    pep440 = re.compile(
        r"^"
        r"(?P<release>\d+(?:\.\d+)*)"
        r"(?:[-_.]?(?:a|b|rc|alpha|beta|c|pre|preview)\d*)?"
        r"(?:\.post\d+)?"
        r"(?:\.dev\d+)?"
        r"$",
        re.IGNORECASE,
    )
    assert pep440.match(sange.__version__), (
        f"version {sange.__version__!r} is not PEP 440-compliant"
    )
