"""Tests for src/sange/core/gitignore/compose.py.

Pure-Python composition tests; no filesystem writes beyond the
in-memory registry the helpers build.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from sange.core.gitignore.compose import VALID_STAGES, CompositionError, compose
from sange.core.gitignore.registry import ProfileRegistry


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _toml(
    name: str,
    category: str = "lang",
    *,
    always: list[str] | None = None,
    dev: list[str] | None = None,
    prod: list[str] | None = None,
    extends: list[str] | None = None,
) -> str:
    def block(label: str, items: list[str] | None) -> str:
        items = items or []
        joined = ", ".join(f'"{x}"' for x in items)
        return f"{label} = [{joined}]"
    ext_block = ""
    if extends:
        joined = ", ".join(f'"{e}"' for e in extends)
        ext_block = f"\n[extends]\nprofiles = [{joined}]\n"
    return (
        f'[profile]\nname = "{name}"\ncategory = "{category}"\n'
        f'[patterns]\n'
        f'{block("always", always)}\n'
        f'{block("dev_only", dev)}\n'
        f'{block("prod_only", prod)}\n'
        f'{ext_block}'
    )


@pytest.fixture
def registry(tmp_path: Path) -> ProfileRegistry:
    _write(tmp_path / "py.toml", _toml(
        "lang/python", "lang",
        always=["__pycache__/", "*.pyc"],
        dev=[".venv/", ".tox/"],
        prod=["/dist/"],
    ))
    _write(tmp_path / "dj.toml", _toml(
        "framework/django", "framework",
        always=["*.log"],
        dev=["media/"],
        extends=["lang/python"],
    ))
    return ProfileRegistry([tmp_path])


_FIXED_CLOCK = _dt.datetime(2026, 5, 16, 12, 0, 0, tzinfo=_dt.UTC)


class TestComposeBasic:
    def test_single_profile_dev(self, registry: ProfileRegistry) -> None:
        text = compose(
            ["lang/python"], stage="dev", registry=registry,
            clock=_FIXED_CLOCK,
        )
        assert "__pycache__/" in text
        assert "*.pyc" in text
        assert ".venv/" in text
        assert ".tox/" in text
        # prod-only must not appear in dev composition.
        assert "/dist/" not in text

    def test_single_profile_prod(self, registry: ProfileRegistry) -> None:
        text = compose(
            ["lang/python"], stage="prod", registry=registry,
            clock=_FIXED_CLOCK,
        )
        assert "__pycache__/" in text
        assert "/dist/" in text
        assert ".venv/" not in text

    def test_header_metadata_present(self, registry: ProfileRegistry) -> None:
        text = compose(
            ["lang/python"], stage="dev", registry=registry,
            clock=_FIXED_CLOCK,
        )
        assert "generated_at:  2026-05-16T12:00:00+00:00" in text
        assert "stage:         dev" in text
        assert "profiles:      lang/python" in text


class TestComposeExtends:
    def test_django_includes_python(self, registry: ProfileRegistry) -> None:
        text = compose(
            ["framework/django"], stage="dev", registry=registry,
            clock=_FIXED_CLOCK,
        )
        # Python patterns appear via extends.
        assert "__pycache__/" in text
        assert ".venv/" in text
        # Django patterns appear in their own section.
        assert "*.log" in text
        assert "media/" in text

    def test_header_lists_extends_chain(self, registry: ProfileRegistry) -> None:
        text = compose(
            ["framework/django"], stage="dev", registry=registry,
            clock=_FIXED_CLOCK,
        )
        assert "(plus extends: lang/python)" in text

    def test_each_profile_emits_its_own_section_header(
        self, registry: ProfileRegistry,
    ) -> None:
        text = compose(
            ["framework/django"], stage="dev", registry=registry,
            clock=_FIXED_CLOCK,
        )
        assert "# --- lang/python (lang/python) ---" in text
        assert "# --- framework/django (framework/django) ---" in text


class TestComposeDedup:
    def test_lines_appearing_in_both_profiles_emit_once(
        self, tmp_path: Path,
    ) -> None:
        _write(tmp_path / "a.toml", _toml(
            "lang/a", "lang", always=["shared-line", "a-only"],
        ))
        _write(tmp_path / "b.toml", _toml(
            "lang/b", "lang", always=["shared-line", "b-only"],
        ))
        reg = ProfileRegistry([tmp_path])
        text = compose(
            ["lang/a", "lang/b"], stage="dev", registry=reg,
            clock=_FIXED_CLOCK,
        )
        # `shared-line` appears exactly once.
        assert text.count("shared-line") == 1
        assert "a-only" in text
        assert "b-only" in text


class TestComposeErrors:
    def test_unknown_stage_raises(self, registry: ProfileRegistry) -> None:
        with pytest.raises(CompositionError, match="stage must be one of"):
            compose(["lang/python"], stage="staging", registry=registry,
                    clock=_FIXED_CLOCK)

    def test_empty_profiles_list_raises(self, registry: ProfileRegistry) -> None:
        with pytest.raises(CompositionError, match="non-empty"):
            compose([], stage="dev", registry=registry, clock=_FIXED_CLOCK)

    def test_valid_stages_published(self) -> None:
        assert "dev" in VALID_STAGES
        assert "prod" in VALID_STAGES


class TestDeterminism:
    def test_same_inputs_same_output(self, registry: ProfileRegistry) -> None:
        a = compose(["lang/python"], stage="dev", registry=registry,
                    clock=_FIXED_CLOCK)
        b = compose(["lang/python"], stage="dev", registry=registry,
                    clock=_FIXED_CLOCK)
        assert a == b
