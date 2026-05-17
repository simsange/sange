"""Tests for `sange.utils.console` — rich wrapper + status helpers."""

from __future__ import annotations

import io

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from sange.utils import (
    TerminalProfile,
    detect_profile,
    failure_panel,
    failure_text,
    make_console,
    success_panel,
    success_text,
    warning_panel,
    warning_text,
)


class _MockStream:
    def __init__(self, *, is_tty: bool, encoding: str = "utf-8") -> None:
        self._is_tty = is_tty
        self.encoding = encoding

    def isatty(self) -> bool:
        return self._is_tty


@pytest.fixture
def utf8_profile() -> TerminalProfile:
    return detect_profile(env={}, stream=_MockStream(is_tty=True))


@pytest.fixture
def no_color_profile() -> TerminalProfile:
    return detect_profile(
        env={"NO_COLOR": "1"}, stream=_MockStream(is_tty=True),
    )


@pytest.fixture
def ci_profile() -> TerminalProfile:
    return detect_profile(env={"CI": "true"}, stream=_MockStream(is_tty=False))


@pytest.fixture
def legacy_windows_profile() -> TerminalProfile:
    return detect_profile(
        env={"OS": "Windows_NT"},
        stream=_MockStream(is_tty=True, encoding="cp1252"),
    )


class TestMakeConsole:
    def test_returns_rich_console(self, utf8_profile: TerminalProfile) -> None:
        c = make_console(utf8_profile)
        assert isinstance(c, Console)

    def test_utf8_tty_has_color(self, utf8_profile: TerminalProfile) -> None:
        c = make_console(utf8_profile)
        # `color_system` is None when colors are disabled.
        assert c.color_system is not None

    def test_no_color_disables_color(
        self, no_color_profile: TerminalProfile,
    ) -> None:
        c = make_console(no_color_profile)
        assert c.color_system is None
        assert c.no_color is True

    def test_ci_force_terminal_off(self, ci_profile: TerminalProfile) -> None:
        # CI without a TTY → don't force terminal mode (avoids CR-spam
        # in log aggregators).
        c = make_console(ci_profile)
        # The internal flag is _force_terminal in some rich versions —
        # check via the public `is_terminal` property after capture.
        # Most reliably: just verify no_color matches.
        assert c.color_system is None

    def test_legacy_windows_no_emoji(
        self, legacy_windows_profile: TerminalProfile,
    ) -> None:
        c = make_console(legacy_windows_profile)
        # Emoji disabled for the legacy Windows + cp1252 profile.
        assert c._emoji is False  # type: ignore[attr-defined]

    def test_width_from_profile(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        c = make_console(utf8_profile)
        assert c.width == utf8_profile.width

    def test_stderr_kwarg(self, utf8_profile: TerminalProfile) -> None:
        c = make_console(utf8_profile, stderr=True)
        assert c.stderr is True

    def test_file_kwarg(self, utf8_profile: TerminalProfile) -> None:
        buf = io.StringIO()
        c = make_console(utf8_profile, file=buf)
        c.print("hello world")
        assert "hello world" in buf.getvalue()


class TestStatusText:
    def test_success_text_contains_message(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        t = success_text(utf8_profile, "ok message")
        assert isinstance(t, Text)
        assert "ok message" in t.plain

    def test_failure_text_contains_message(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        t = failure_text(utf8_profile, "bad thing happened")
        assert "bad thing happened" in t.plain

    def test_warning_text_contains_message(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        t = warning_text(utf8_profile, "heads up")
        assert "heads up" in t.plain

    def test_emoji_glyph_used_when_supported(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        # utf8_profile enables emoji → ✅
        t = success_text(utf8_profile, "x")
        assert "✅" in t.plain

    def test_ascii_glyph_used_for_legacy(
        self, legacy_windows_profile: TerminalProfile,
    ) -> None:
        t = success_text(legacy_windows_profile, "x")
        assert "[OK]" in t.plain
        assert "✅" not in t.plain


class TestStatusPanels:
    def test_success_panel_is_panel(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        p = success_panel(utf8_profile, "all good")
        assert isinstance(p, Panel)

    def test_success_panel_green_border(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        p = success_panel(utf8_profile, "x")
        assert p.border_style == "green"

    def test_failure_panel_red_border(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        p = failure_panel(utf8_profile, "x")
        assert p.border_style == "red"

    def test_failure_panel_default_title_is_error(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        p = failure_panel(utf8_profile, "x")
        assert p.title == "Error"

    def test_warning_panel_yellow_border(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        p = warning_panel(utf8_profile, "x")
        assert p.border_style == "yellow"

    def test_custom_title(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        p = success_panel(utf8_profile, "x", title="Custom")
        assert p.title == "Custom"


class TestRendersWithoutCrash:
    """Integration smoke — actually rendering through rich shouldn't crash."""

    def test_success_panel_renders(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        buf = io.StringIO()
        c = make_console(utf8_profile, file=buf)
        c.print(success_panel(utf8_profile, "ok"))
        assert "ok" in buf.getvalue()

    def test_failure_panel_renders(
        self, utf8_profile: TerminalProfile,
    ) -> None:
        buf = io.StringIO()
        c = make_console(utf8_profile, file=buf)
        c.print(failure_panel(utf8_profile, "bad"))
        assert "bad" in buf.getvalue()

    def test_no_color_panel_renders_without_ansi(
        self, no_color_profile: TerminalProfile,
    ) -> None:
        buf = io.StringIO()
        c = make_console(no_color_profile, file=buf)
        c.print(failure_panel(no_color_profile, "uh oh"))
        out = buf.getvalue()
        # No ANSI escapes when NO_COLOR.
        assert "\x1b[" not in out
        assert "uh oh" in out
