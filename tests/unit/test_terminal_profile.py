"""Tests for `sange.utils.terminal` — §7.0.2 TerminalProfile detection."""

from __future__ import annotations

import io

import pytest

from sange.utils import (
    Glyphs,
    TerminalProfile,
    detect_profile,
    glyphs_for,
    truncate_to_width,
)


class _MockStream:
    """Minimal stream stand-in for tty/encoding probes."""

    def __init__(self, *, is_tty: bool, encoding: str = "utf-8") -> None:
        self._is_tty = is_tty
        self.encoding = encoding

    def isatty(self) -> bool:
        return self._is_tty


@pytest.fixture
def utf8_tty() -> _MockStream:
    return _MockStream(is_tty=True, encoding="utf-8")


@pytest.fixture
def cp1252_tty() -> _MockStream:
    return _MockStream(is_tty=True, encoding="cp1252")


@pytest.fixture
def piped() -> _MockStream:
    return _MockStream(is_tty=False, encoding="utf-8")


class TestDetectProfileEnvRules:
    def test_no_color_disables_emoji_and_color(
        self, utf8_tty: _MockStream,
    ) -> None:
        profile = detect_profile(env={"NO_COLOR": "1"}, stream=utf8_tty)
        assert profile.use_emoji is False
        assert profile.color_mode == "none"
        # NO_COLOR keeps Unicode structure (color is noise, not structure).
        assert profile.use_unicode_box_chars is True

    def test_force_color_enables_truecolor(
        self, utf8_tty: _MockStream,
    ) -> None:
        profile = detect_profile(env={"FORCE_COLOR": "1"}, stream=utf8_tty)
        assert profile.color_mode == "truecolor"

    def test_no_color_beats_force_color(
        self, utf8_tty: _MockStream,
    ) -> None:
        profile = detect_profile(
            env={"NO_COLOR": "1", "FORCE_COLOR": "1"},
            stream=utf8_tty,
        )
        assert profile.color_mode == "none"

    def test_ci_disables_emoji(self, utf8_tty: _MockStream) -> None:
        profile = detect_profile(env={"CI": "true"}, stream=utf8_tty)
        assert profile.is_ci is True
        assert profile.use_emoji is False
        # Unicode box chars still on (deterministic non-emoji glyphs in CI).
        assert profile.use_unicode_box_chars is True

    def test_dumb_terminal(self, utf8_tty: _MockStream) -> None:
        profile = detect_profile(env={"TERM": "dumb"}, stream=utf8_tty)
        assert profile.color_mode == "none"


class TestDetectProfileColorMode:
    def test_truecolor_term(self, utf8_tty: _MockStream) -> None:
        profile = detect_profile(
            env={"COLORTERM": "truecolor"}, stream=utf8_tty,
        )
        assert profile.color_mode == "truecolor"

    def test_256color_term(self, utf8_tty: _MockStream) -> None:
        profile = detect_profile(
            env={"TERM": "xterm-256color"}, stream=utf8_tty,
        )
        assert profile.color_mode == "256"

    def test_default_tty_falls_to_16_color(
        self, utf8_tty: _MockStream,
    ) -> None:
        # No COLORTERM, no TERM-256, just a plain TTY.
        profile = detect_profile(env={}, stream=utf8_tty)
        assert profile.color_mode == "16"

    def test_piped_output_color_none(self, piped: _MockStream) -> None:
        profile = detect_profile(env={}, stream=piped)
        assert profile.color_mode == "none"
        assert profile.is_tty is False


class TestDetectProfileEncoding:
    def test_utf8_stream_enables_emoji(
        self, utf8_tty: _MockStream,
    ) -> None:
        profile = detect_profile(env={}, stream=utf8_tty)
        assert profile.has_utf8 is True
        assert profile.use_emoji is True

    def test_cp1252_disables_emoji(
        self, cp1252_tty: _MockStream,
    ) -> None:
        profile = detect_profile(env={}, stream=cp1252_tty)
        assert profile.has_utf8 is False
        assert profile.use_emoji is False

    def test_no_encoding_falls_back(self) -> None:
        stream = io.StringIO()
        # StringIO has no `encoding` attribute by default.
        profile = detect_profile(env={}, stream=stream)
        # Whatever the fallback is, no crash.
        assert isinstance(profile, TerminalProfile)


class TestDetectProfileWindows:
    def test_legacy_windows_ascii(self) -> None:
        cp1252_stream = _MockStream(is_tty=True, encoding="cp1252")
        profile = detect_profile(
            env={"OS": "Windows_NT"}, stream=cp1252_stream,
        )
        assert profile.is_windows is True
        assert profile.is_modern_windows_terminal is False
        assert profile.use_emoji is False
        assert profile.use_unicode_box_chars is False

    def test_modern_windows_terminal_enables_emoji(
        self, utf8_tty: _MockStream,
    ) -> None:
        profile = detect_profile(
            env={"OS": "Windows_NT", "WT_SESSION": "abc-123"},
            stream=utf8_tty,
        )
        assert profile.is_windows is True
        assert profile.is_modern_windows_terminal is True
        assert profile.use_emoji is True


class TestGlyphsFor:
    def test_emoji_profile(self, utf8_tty: _MockStream) -> None:
        profile = detect_profile(env={}, stream=utf8_tty)
        g = glyphs_for(profile)
        assert g.success == "✅"
        assert g.failure == "❌"

    def test_no_color_unicode_glyphs(
        self, utf8_tty: _MockStream,
    ) -> None:
        profile = detect_profile(
            env={"NO_COLOR": "1"}, stream=utf8_tty,
        )
        g = glyphs_for(profile)
        # NO_COLOR turns off emoji but keeps Unicode arrows.
        assert g.success == "✓"
        assert g.failure == "✗"
        assert g.tree_branch == "├──"

    def test_ascii_glyphs_for_legacy_windows(self) -> None:
        cp1252_stream = _MockStream(is_tty=True, encoding="cp1252")
        profile = detect_profile(
            env={"OS": "Windows_NT"}, stream=cp1252_stream,
        )
        g = glyphs_for(profile)
        assert g.success == "[OK]"
        assert g.failure == "[FAIL]"
        assert g.tree_branch == "+--"
        assert g.tree_last == "\\--"

    def test_glyphs_returns_frozen_dataclass(
        self, utf8_tty: _MockStream,
    ) -> None:
        profile = detect_profile(env={}, stream=utf8_tty)
        g = glyphs_for(profile)
        assert isinstance(g, Glyphs)
        with pytest.raises(Exception):
            g.success = "X"  # type: ignore[misc]


class TestTruncateToWidth:
    def test_short_string_returned_as_is(self) -> None:
        assert truncate_to_width("hello", 10) == "hello"

    def test_truncates_with_ellipsis(self) -> None:
        result = truncate_to_width("hello world", 8)
        # 7 chars budget for content + 1 char for the … ellipsis = 8.
        assert result.endswith("…")
        assert len(result) <= 8

    def test_zero_width_returns_empty(self) -> None:
        assert truncate_to_width("hello", 0) == ""

    def test_negative_width_returns_empty(self) -> None:
        assert truncate_to_width("hello", -1) == ""

    def test_wide_chars_count_as_two(self) -> None:
        # CJK chars are width 2. "日本" = width 4.
        result = truncate_to_width("日本語", 5)
        # 5 - 1 (suffix) = 4 budget; "日本" takes exactly 4 → fits.
        assert result == "日本…"

    def test_custom_suffix(self) -> None:
        result = truncate_to_width("hello world", 8, suffix="...")
        assert result.endswith("...")
        assert len(result) <= 8

    def test_exact_fit(self) -> None:
        # Width exactly matches → no truncation.
        assert truncate_to_width("hello", 5) == "hello"


class TestTerminalProfileFrozen:
    def test_profile_is_frozen(self, utf8_tty: _MockStream) -> None:
        profile = detect_profile(env={}, stream=utf8_tty)
        with pytest.raises(Exception):
            profile.color_mode = "none"  # type: ignore[misc]


class TestDetectProfileWidth:
    def test_width_is_int(self, utf8_tty: _MockStream) -> None:
        profile = detect_profile(env={}, stream=utf8_tty)
        assert isinstance(profile.width, int)
        assert profile.width > 0  # at least the 80-col fallback
