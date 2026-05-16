"""Tests for src/sange/core/hooks/engine.py + result.py."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from sange.core.hooks import (
    EXIT_PASSED,
    EXIT_SKIPPED,
    EXIT_WARN,
    HookDescriptor,
    HookEngine,
    HookError,
    HookReport,
    HookStatus,
    status_from_exit_code,
)


def _write_hook(
    path: Path, body: str = "exit 0\n", *, executable: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    if executable:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    return r


# --------------------------------------------------------------------------- #
# status_from_exit_code
# --------------------------------------------------------------------------- #


class TestStatusFromExitCode:
    def test_zero_passes(self) -> None:
        assert status_from_exit_code(0) is HookStatus.PASSED

    def test_warn_band(self) -> None:
        assert status_from_exit_code(EXIT_WARN) is HookStatus.WARN

    def test_skipped_band(self) -> None:
        assert status_from_exit_code(EXIT_SKIPPED) is HookStatus.SKIPPED

    def test_everything_else_fails(self) -> None:
        assert status_from_exit_code(1) is HookStatus.FAILED
        assert status_from_exit_code(127) is HookStatus.FAILED
        assert status_from_exit_code(-1) is HookStatus.FAILED


# --------------------------------------------------------------------------- #
# HookDescriptor
# --------------------------------------------------------------------------- #


class TestHookDescriptor:
    def test_basic(self) -> None:
        d = HookDescriptor(name="lint", event="pre-commit", priority=10,
                           path=Path("/tmp/hook"))
        assert d.priority == 10

    def test_priority_out_of_range_rejected(self) -> None:
        with pytest.raises(HookError, match="priority"):
            HookDescriptor(name="x", event="pre-commit", priority=100,
                           path=Path("/tmp/hook"))
        with pytest.raises(HookError, match="priority"):
            HookDescriptor(name="x", event="pre-commit", priority=-1,
                           path=Path("/tmp/hook"))


# --------------------------------------------------------------------------- #
# HookEngine.discover
# --------------------------------------------------------------------------- #


class TestDiscover:
    def test_empty_repo_returns_empty(self, repo: Path) -> None:
        e = HookEngine(repo)
        assert e.discover("pre-commit") == ()

    def test_finds_executable_hooks_sorted_by_priority(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "20-second.sh")
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-first.sh")
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "30-third.sh")
        e = HookEngine(repo)
        ds = e.discover("pre-commit")
        assert [d.priority for d in ds] == [10, 20, 30]
        assert [d.name for d in ds] == ["first.sh", "second.sh", "third.sh"]

    def test_skips_non_executable(self, repo: Path) -> None:
        _write_hook(
            repo / ".sange" / "hooks" / "pre-commit" / "10-script.sh",
            executable=False,
        )
        e = HookEngine(repo)
        assert e.discover("pre-commit") == ()

    def test_skips_files_without_priority_prefix(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "README.md")
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "no-priority.sh")
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "5-only-one-digit.sh")
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-real.sh")
        e = HookEngine(repo)
        ds = e.discover("pre-commit")
        assert len(ds) == 1
        assert ds[0].name == "real.sh"

    def test_separate_events(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-a.sh")
        _write_hook(repo / ".sange" / "hooks" / "pre-push" / "10-b.sh")
        e = HookEngine(repo)
        assert [d.name for d in e.discover("pre-commit")] == ["a.sh"]
        assert [d.name for d in e.discover("pre-push")] == ["b.sh"]

    def test_empty_event_rejected(self, repo: Path) -> None:
        e = HookEngine(repo)
        with pytest.raises(HookError, match="event"):
            e.discover("")

    def test_subdirs_under_event_not_recursed(self, repo: Path) -> None:
        # Discovery is one-level — child directories are ignored.
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "sub" / "10-x.sh")
        e = HookEngine(repo)
        assert e.discover("pre-commit") == ()


# --------------------------------------------------------------------------- #
# HookEngine.run_event
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only shell hooks")
class TestRunEvent:
    def test_passing_hook(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-ok.sh",
                    body='echo "ok"\nexit 0\n')
        e = HookEngine(repo)
        report = e.run_event("pre-commit")
        assert report.total == 1
        assert report.results[0].status is HookStatus.PASSED
        assert report.results[0].exit_code == 0
        assert "ok" in report.results[0].stdout

    def test_failing_hook_aborts_subsequent(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-fail.sh",
                    body='exit 1\n')
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "20-ok.sh",
                    body='exit 0\n')
        e = HookEngine(repo)
        report = e.run_event("pre-commit")
        # abort_on_failed=True (default) stops after the first failure.
        assert report.total == 1
        assert report.results[0].name == "fail.sh"
        assert report.results[0].status is HookStatus.FAILED

    def test_abort_on_failed_false_runs_all(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-fail.sh",
                    body='exit 1\n')
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "20-ok.sh",
                    body='exit 0\n')
        e = HookEngine(repo)
        report = e.run_event("pre-commit", abort_on_failed=False)
        assert report.total == 2
        assert report.any_failed

    def test_warn_does_not_abort(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-warn.sh",
                    body='exit 128\n')
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "20-ok.sh",
                    body='exit 0\n')
        e = HookEngine(repo)
        report = e.run_event("pre-commit")
        assert report.total == 2
        assert report.results[0].status is HookStatus.WARN
        assert report.results[1].status is HookStatus.PASSED

    def test_skipped_does_not_abort(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-skip.sh",
                    body='exit 64\n')
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "20-ok.sh",
                    body='exit 0\n')
        e = HookEngine(repo)
        report = e.run_event("pre-commit")
        assert report.total == 2
        assert report.results[0].status is HookStatus.SKIPPED

    def test_timeout(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-slow.sh",
                    body='sleep 5\nexit 0\n')
        e = HookEngine(repo, hook_timeout_s=0.5)
        report = e.run_event("pre-commit")
        assert report.results[0].status is HookStatus.FAILED
        assert report.results[0].timed_out is True
        assert "timed out" in report.results[0].stderr

    def test_no_hooks_returns_empty_report(self, repo: Path) -> None:
        e = HookEngine(repo)
        report = e.run_event("pre-commit")
        assert report.results == ()
        assert report.all_passed   # vacuously true

    def test_env_propagation(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-env.sh",
                    body='echo "REPO=$SANGE_HOOKS_REPO_ROOT"\nexit 0\n')
        e = HookEngine(repo)
        report = e.run_event("pre-commit")
        assert str(repo.resolve()) in report.results[0].stdout

    def test_caller_env_overrides(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-env.sh",
                    body='echo "GREETING=$GREETING"\nexit 0\n')
        e = HookEngine(repo)
        report = e.run_event("pre-commit", env={"GREETING": "hola"})
        assert "hola" in report.results[0].stdout


# --------------------------------------------------------------------------- #
# HookReport
# --------------------------------------------------------------------------- #


class TestHookReport:
    def test_counts_match_results(self) -> None:
        results = (
            HookResult(name="a", event="pre-commit", priority=10, path="/x",
                       status=HookStatus.PASSED, exit_code=0, duration_ms=5),
            HookResult(name="b", event="pre-commit", priority=20, path="/y",
                       status=HookStatus.WARN, exit_code=128, duration_ms=3),
            HookResult(name="c", event="pre-commit", priority=30, path="/z",
                       status=HookStatus.FAILED, exit_code=1, duration_ms=8),
        )
        report = HookReport(event="pre-commit", results=results)
        assert report.total == 3
        assert report.any_failed
        assert not report.all_passed
        assert report.counts[HookStatus.PASSED] == 1
        assert report.counts[HookStatus.WARN] == 1
        assert report.counts[HookStatus.FAILED] == 1
        assert report.counts[HookStatus.SKIPPED] == 0


# A focused import so the HookResult symbol is available to TestHookReport
# above without the test file needing top-level imports the rest of the
# file doesn't use directly.
from sange.core.hooks import HookResult  # noqa: E402
