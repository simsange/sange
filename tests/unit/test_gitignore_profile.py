"""Tests for src/sange/core/gitignore/profile.py.

Pure TOML-loading + invariant tests — no subprocess, no filesystem
writes beyond `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sange.core.gitignore.profile import Profile, ProfileError, load_profile


def _write_toml(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


class TestLoadProfile:
    def test_minimal_profile(self, tmp_path: Path) -> None:
        p = tmp_path / "p.toml"
        _write_toml(p, '''
[profile]
name = "lang/python"
category = "lang"

[patterns]
always = ["__pycache__/"]
''')
        prof = load_profile(p)
        assert prof.name == "lang/python"
        assert prof.category == "lang"
        assert prof.display_name == "lang/python"   # falls back to name
        assert prof.patterns_always == ("__pycache__/",)
        assert prof.patterns_dev == ()
        assert prof.patterns_prod == ()
        assert prof.extends == ()
        assert prof.source_path == p.resolve()

    def test_full_profile(self, tmp_path: Path) -> None:
        p = tmp_path / "p.toml"
        _write_toml(p, '''
[profile]
name = "framework/django"
display_name = "Django"
category = "framework"
version = "1.0.0"
maintainer = "Simtabi LLC <opensource@simtabi.com>"
upstream_source = "https://example.test/django"
notes = "Some notes."

[detect]
required_any = ["manage.py"]
boost_any = ["settings.py"]

[patterns]
always = ["*.log"]
dev_only = ["media/", ".env"]
prod_only = ["debug.log"]

[extends]
profiles = ["lang/python"]
''')
        prof = load_profile(p)
        assert prof.display_name == "Django"
        assert prof.version == "1.0.0"
        assert prof.notes == "Some notes."
        assert prof.required_any == ("manage.py",)
        assert prof.boost_any == ("settings.py",)
        assert prof.patterns_dev == ("media/", ".env")
        assert prof.patterns_prod == ("debug.log",)
        assert prof.extends == ("lang/python",)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ProfileError, match="not found"):
            load_profile(tmp_path / "no-such.toml")

    def test_missing_profile_section_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "p.toml"
        _write_toml(p, '[detect]\nrequired_any = []\n')
        with pytest.raises(ProfileError, match=r"missing \[profile\]"):
            load_profile(p)

    def test_missing_name_or_category_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "p.toml"
        _write_toml(p, '[profile]\nname = "x"\n')
        with pytest.raises(ProfileError, match=r"name.*category"):
            load_profile(p)

    def test_invalid_toml_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "p.toml"
        _write_toml(p, '[profile\nname = "broken"')
        with pytest.raises(ProfileError, match="invalid TOML"):
            load_profile(p)

    def test_non_list_patterns_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "p.toml"
        _write_toml(p, '''
[profile]
name = "lang/x"
category = "lang"

[patterns]
always = "not-a-list"
''')
        with pytest.raises(ProfileError, match="expected list"):
            load_profile(p)

    def test_non_string_pattern_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "p.toml"
        _write_toml(p, '''
[profile]
name = "lang/x"
category = "lang"

[patterns]
always = [1, 2, 3]
''')
        with pytest.raises(ProfileError, match="non-string"):
            load_profile(p)

    def test_self_extends_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "p.toml"
        _write_toml(p, '''
[profile]
name = "lang/x"
category = "lang"

[extends]
profiles = ["lang/x"]
''')
        with pytest.raises(ProfileError, match="cannot contain self"):
            load_profile(p)


class TestProfileInvariants:
    def test_non_core_must_have_slash(self) -> None:
        with pytest.raises(ProfileError, match=r"<category>/<topic>"):
            Profile(name="python", display_name="Python", category="lang")

    def test_core_category_allows_no_slash(self) -> None:
        # `_core/anything` and bare `_core` are both legal? per the
        # invariant, the slash check is bypassed only when
        # category="_core".
        prof = Profile(name="anything", display_name="x", category="_core")
        assert prof.category == "_core"


class TestPatternsForStage:
    def _make(self) -> Profile:
        return Profile(
            name="lang/x", display_name="X", category="lang",
            patterns_always=("a1", "a2"),
            patterns_dev=("d1",),
            patterns_prod=("p1",),
        )

    def test_dev_includes_always_plus_dev_only(self) -> None:
        p = self._make()
        assert p.patterns_for_stage("dev") == ("a1", "a2", "d1")

    def test_prod_includes_always_plus_prod_only(self) -> None:
        p = self._make()
        assert p.patterns_for_stage("prod") == ("a1", "a2", "p1")

    def test_unknown_stage_falls_back_to_always(self) -> None:
        p = self._make()
        assert p.patterns_for_stage("staging") == ("a1", "a2")
