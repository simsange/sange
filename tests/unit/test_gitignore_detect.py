"""Tests for src/sange/core/gitignore/detect.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from sange.core.gitignore.detect import DetectionResult, detect_profiles
from sange.core.gitignore.registry import ProfileRegistry


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _profile_toml(
    name: str,
    *,
    required: list[str],
    boost: list[str] | None = None,
) -> str:
    req = ", ".join(f'"{x}"' for x in required)
    bst = ", ".join(f'"{x}"' for x in (boost or []))
    return (
        f'[profile]\nname = "{name}"\ncategory = "lang"\n'
        f'[detect]\nrequired_any = [{req}]\nboost_any = [{bst}]\n'
        f'[patterns]\nalways = []\n'
    )


@pytest.fixture
def small_registry(tmp_path: Path) -> ProfileRegistry:
    profile_root = tmp_path / "profiles"
    _write(profile_root / "py.toml", _profile_toml(
        "lang/python",
        required=["pyproject.toml", "setup.py"],
        boost=["poetry.lock", ".python-version"],
    ))
    _write(profile_root / "node.toml", _profile_toml(
        "lang/node",
        required=["package.json"],
        boost=["yarn.lock", "pnpm-lock.yaml"],
    ))
    _write(profile_root / "rust.toml", _profile_toml(
        "lang/rust",
        required=["Cargo.toml"],
        boost=["Cargo.lock"],
    ))
    return ProfileRegistry([profile_root])


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    return r


class TestDetectProfiles:
    def test_python_repo_matches_python_only(
        self, repo: Path, small_registry: ProfileRegistry,
    ) -> None:
        _write(repo / "pyproject.toml", "")
        results = detect_profiles(repo, small_registry)
        assert len(results) == 1
        assert results[0].profile.name == "lang/python"
        assert results[0].matched_required == ("pyproject.toml",)
        assert results[0].confidence == 2  # 1 required x 2pts

    def test_python_repo_with_boost(
        self, repo: Path, small_registry: ProfileRegistry,
    ) -> None:
        _write(repo / "pyproject.toml", "")
        _write(repo / "poetry.lock", "")
        _write(repo / ".python-version", "3.13")
        results = detect_profiles(repo, small_registry)
        assert len(results) == 1
        assert results[0].confidence == 4  # 1 reqx2 + 2 boostx1
        assert sorted(results[0].matched_boost) == [".python-version", "poetry.lock"]

    def test_multi_language_repo(
        self, repo: Path, small_registry: ProfileRegistry,
    ) -> None:
        _write(repo / "pyproject.toml", "")
        _write(repo / "package.json", "{}")
        _write(repo / "Cargo.toml", "")
        results = detect_profiles(repo, small_registry)
        names = [r.profile.name for r in results]
        assert sorted(names) == ["lang/node", "lang/python", "lang/rust"]
        # All three tied at confidence=2; tiebreak is alphabetical.
        assert [r.confidence for r in results] == [2, 2, 2]
        assert names == ["lang/node", "lang/python", "lang/rust"]

    def test_empty_repo_returns_no_candidates(
        self, repo: Path, small_registry: ProfileRegistry,
    ) -> None:
        assert detect_profiles(repo, small_registry) == ()

    def test_unrelated_files_return_no_candidates(
        self, repo: Path, small_registry: ProfileRegistry,
    ) -> None:
        _write(repo / "README.md", "")
        _write(repo / "LICENSE", "")
        assert detect_profiles(repo, small_registry) == ()

    def test_walk_depth_zero_skips_subdirs(
        self, repo: Path, small_registry: ProfileRegistry,
    ) -> None:
        _write(repo / "subdir" / "pyproject.toml", "")
        # depth=0 stops at repo root; nothing matches.
        assert detect_profiles(repo, small_registry, walk_depth=0) == ()
        # depth=1 finds the nested file.
        results = detect_profiles(repo, small_registry, walk_depth=1)
        assert len(results) == 1

    def test_skip_dirs_ignored(
        self, repo: Path, small_registry: ProfileRegistry,
    ) -> None:
        # pyproject inside .git should not count.
        _write(repo / ".git" / "pyproject.toml", "")
        _write(repo / "node_modules" / "package.json", "{}")
        assert detect_profiles(repo, small_registry, walk_depth=2) == ()

    def test_negative_depth_rejected(
        self, repo: Path, small_registry: ProfileRegistry,
    ) -> None:
        with pytest.raises(ValueError, match="walk_depth"):
            detect_profiles(repo, small_registry, walk_depth=-1)

    def test_returns_dataclass_result(
        self, repo: Path, small_registry: ProfileRegistry,
    ) -> None:
        _write(repo / "Cargo.toml", "")
        results = detect_profiles(repo, small_registry)
        assert isinstance(results[0], DetectionResult)
        # All fields populated.
        assert results[0].profile.name == "lang/rust"
        assert results[0].matched_required == ("Cargo.toml",)


class TestDetectProfilesGlobs:
    def test_glob_pattern_in_required_matches(self, tmp_path: Path) -> None:
        profile_root = tmp_path / "profiles"
        _write(profile_root / "p.toml", _profile_toml(
            "lang/php",
            required=["*.php"],
        ))
        repo = tmp_path / "repo"
        _write(repo / "index.php", "")
        reg = ProfileRegistry([profile_root])
        results = detect_profiles(repo, reg)
        assert len(results) == 1
        assert results[0].profile.name == "lang/php"

    def test_no_required_means_no_candidate(self, tmp_path: Path) -> None:
        # `_core/*` profiles tend to omit required_any. They should not
        # show up in detect_profiles output.
        profile_root = tmp_path / "profiles"
        _write(profile_root / "p.toml",
               '[profile]\nname = "_core/x"\ncategory = "_core"\n'
               '[detect]\nrequired_any = []\n'
               '[patterns]\nalways = []\n')
        repo = tmp_path / "repo"
        _write(repo / "anything.txt", "")
        reg = ProfileRegistry([profile_root])
        assert detect_profiles(repo, reg) == ()


class TestDetectAgainstShippedProfiles:
    """Smoke against the 36 shipped profiles."""

    def test_python_repo_matches_python_profile(self, tmp_path: Path) -> None:
        from sange.core.gitignore import default_registry_roots
        reg = ProfileRegistry(default_registry_roots())
        _write(tmp_path / "pyproject.toml", "")
        results = detect_profiles(tmp_path, reg)
        names = [r.profile.name for r in results]
        assert "lang/python" in names

    def test_django_repo_matches_django_profile(self, tmp_path: Path) -> None:
        from sange.core.gitignore import default_registry_roots
        reg = ProfileRegistry(default_registry_roots())
        _write(tmp_path / "manage.py", "")
        results = detect_profiles(tmp_path, reg)
        names = [r.profile.name for r in results]
        assert "framework/django" in names
