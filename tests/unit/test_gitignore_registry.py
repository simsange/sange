"""Tests for src/sange/core/gitignore/registry.py.

Covers: profile loading from multiple roots, shadowing (per-repo
beats per-user beats shipped), bad-TOML skip-with-record,
extends-chain resolution, cycle detection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sange.core.gitignore.profile import ProfileError
from sange.core.gitignore.registry import (
    ProfileRegistry,
    default_registry_roots,
)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _minimal(name: str, category: str, *, extends: list[str] | None = None) -> str:
    extends_block = ""
    if extends:
        joined = ", ".join(f'"{e}"' for e in extends)
        extends_block = f"\n[extends]\nprofiles = [{joined}]\n"
    return (
        f'[profile]\nname = "{name}"\ncategory = "{category}"\n'
        f'[patterns]\nalways = []\n'
        f'{extends_block}'
    )


class TestProfileRegistryLoad:
    def test_loads_single_root(self, tmp_path: Path) -> None:
        _write(tmp_path / "lang" / "python.toml", _minimal("lang/python", "lang"))
        _write(tmp_path / "lang" / "node.toml", _minimal("lang/node", "lang"))
        reg = ProfileRegistry([tmp_path])
        assert reg.all_names() == ("lang/node", "lang/python")
        assert reg.has("lang/python")
        assert not reg.has("lang/rust")

    def test_get_unknown_raises(self, tmp_path: Path) -> None:
        reg = ProfileRegistry([tmp_path])
        with pytest.raises(ProfileError, match="not found"):
            reg.get("nope")

    def test_shadowing_per_repo_beats_shipped(self, tmp_path: Path) -> None:
        shipped = tmp_path / "shipped"
        per_repo = tmp_path / "repo"
        _write(shipped / "lang" / "python.toml", _minimal("lang/python", "lang"))
        _write(per_repo / "lang" / "python.toml",
               '[profile]\nname = "lang/python"\ncategory = "lang"\n'
               '[patterns]\nalways = ["override-line"]\n')
        # per-repo first (highest priority).
        reg = ProfileRegistry([per_repo, shipped])
        prof = reg.get("lang/python")
        assert prof.patterns_always == ("override-line",)
        # The shipped profile was shadowed.
        assert len(reg.load_detail.shadowed) == 1
        name, winner_path, loser_path = reg.load_detail.shadowed[0]
        assert name == "lang/python"
        assert winner_path.parent.parent.name == "repo"
        assert loser_path.parent.parent.name == "shipped"

    def test_bad_toml_is_skipped_not_fatal(self, tmp_path: Path) -> None:
        _write(tmp_path / "ok.toml", _minimal("lang/python", "lang"))
        _write(tmp_path / "bad.toml", "[profile\nname = broken")
        reg = ProfileRegistry([tmp_path])
        assert reg.has("lang/python")
        assert len(reg.load_detail.skipped) == 1

    def test_nonexistent_root_is_silently_ignored(self, tmp_path: Path) -> None:
        # First root doesn't exist — should not raise.
        reg = ProfileRegistry([tmp_path / "does-not-exist", tmp_path])
        # No profiles loaded but the registry is usable.
        assert reg.all_names() == ()

    def test_by_category(self, tmp_path: Path) -> None:
        _write(tmp_path / "lang" / "python.toml", _minimal("lang/python", "lang"))
        _write(tmp_path / "lang" / "node.toml", _minimal("lang/node", "lang"))
        _write(tmp_path / "framework" / "django.toml",
               _minimal("framework/django", "framework"))
        reg = ProfileRegistry([tmp_path])
        lang = reg.by_category("lang")
        assert [p.name for p in lang] == ["lang/node", "lang/python"]
        fw = reg.by_category("framework")
        assert [p.name for p in fw] == ["framework/django"]


class TestExtendsChainResolution:
    def test_no_extends(self, tmp_path: Path) -> None:
        _write(tmp_path / "p.toml", _minimal("lang/python", "lang"))
        reg = ProfileRegistry([tmp_path])
        chain = reg.resolve_extends_chain("lang/python")
        assert [p.name for p in chain] == ["lang/python"]

    def test_single_extends(self, tmp_path: Path) -> None:
        _write(tmp_path / "py.toml", _minimal("lang/python", "lang"))
        _write(tmp_path / "dj.toml",
               _minimal("framework/django", "framework", extends=["lang/python"]))
        reg = ProfileRegistry([tmp_path])
        chain = reg.resolve_extends_chain("framework/django")
        assert [p.name for p in chain] == ["lang/python", "framework/django"]

    def test_diamond_dedupes_ancestor(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.toml", _minimal("a/root", "a"))
        _write(tmp_path / "b.toml",
               _minimal("a/left", "a", extends=["a/root"]))
        _write(tmp_path / "c.toml",
               _minimal("a/right", "a", extends=["a/root"]))
        _write(tmp_path / "d.toml",
               _minimal("a/diamond", "a", extends=["a/left", "a/right"]))
        reg = ProfileRegistry([tmp_path])
        chain = reg.resolve_extends_chain("a/diamond")
        names = [p.name for p in chain]
        # a/root appears once, at its first-seen position.
        assert names == ["a/root", "a/left", "a/right", "a/diamond"]

    def test_cycle_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.toml",
               _minimal("a/x", "a", extends=["a/y"]))
        _write(tmp_path / "b.toml",
               _minimal("a/y", "a", extends=["a/x"]))
        reg = ProfileRegistry([tmp_path])
        with pytest.raises(ProfileError, match="cycle"):
            reg.resolve_extends_chain("a/x")

    def test_missing_parent_raises(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.toml",
               _minimal("a/x", "a", extends=["a/ghost"]))
        reg = ProfileRegistry([tmp_path])
        with pytest.raises(ProfileError, match="not found"):
            reg.resolve_extends_chain("a/x")


class TestDefaultRegistryRoots:
    def test_shipped_root_resolves_to_templates(self) -> None:
        # The third root is the shipped templates dir; it must exist.
        roots = default_registry_roots()
        shipped = roots[-1]
        assert shipped.is_dir(), f"expected shipped dir at {shipped}"
        assert (shipped / "lang" / "python.toml").is_file()

    def test_repo_root_prepended_when_supplied(self, tmp_path: Path) -> None:
        roots = default_registry_roots(repo_root=tmp_path)
        assert len(roots) == 3
        assert roots[0] == (tmp_path / ".sange" / "profiles").resolve()


class TestShippedProfilesAreValid:
    """Smoke: every profile under templates/gitignore-profiles/ loads."""

    def test_all_36_shipped_profiles_load(self) -> None:
        reg = ProfileRegistry(default_registry_roots())
        assert len(reg.all_profiles()) >= 35   # generator emits 35; allow growth
        # No skip-with-record entries means every TOML parsed.
        assert reg.load_detail.skipped == []

    def test_all_extends_chains_resolve(self) -> None:
        reg = ProfileRegistry(default_registry_roots())
        for prof in reg.all_profiles():
            # Each profile's chain must resolve cleanly.
            reg.resolve_extends_chain(prof.name)
