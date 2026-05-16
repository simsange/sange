"""Tests for `sange.core.purge.scanners` — §6.11.4 gate 8 pre-run."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sange.core.audit import AuditChain
from sange.core.purge import (
    PurgeFilters,
    PurgePlan,
    RepoMeta,
    ScannerError,
    create_mirror,
    run_gitleaks,
    run_scanners,
    run_trufflehog,
)

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="POSIX scanners"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH"),
]


def _git(cwd: Path, *argv: str, env_home: Path) -> None:
    subprocess.run(
        ["git", *argv],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(env_home),
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        },
    )


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    src = tmp_path / "source"
    src.mkdir()
    _git(src, "init", "--initial-branch=main", "--quiet", env_home=tmp_path)
    (src / "f.txt").write_text("hi\n")
    _git(src, "add", "f.txt", env_home=tmp_path)
    _git(src, "commit", "-m", "init", env_home=tmp_path)
    return src


@pytest.fixture
def operator_repo(tmp_path: Path) -> Path:
    op = tmp_path / "operator"
    op.mkdir()
    return op


@pytest.fixture
def chain(operator_repo: Path) -> AuditChain:
    return AuditChain(operator_repo)


@pytest.fixture
def plan(source_repo: Path) -> PurgePlan:
    return PurgePlan(
        created_by="alice@cli",
        target_vcs="git",
        target_repo=RepoMeta(path=str(source_repo)),
        filters=PurgeFilters(paths=["f.txt"]),
    )


@pytest.fixture
def mirror_path(
    plan: PurgePlan, source_repo: Path, operator_repo: Path,
    chain: AuditChain,
) -> Path:
    result = create_mirror(
        plan, operator_repo,
        audit_chain=chain, actor="a",
        source_url=f"file://{source_repo}",
    )
    return result.path


def _make_fake_tool(
    tmp_path: Path,
    name: str,
    *,
    stdout: str,
    exit_code: int = 0,
) -> Path:
    """Drop a sh script that echoes the given stdout and exits the given code."""

    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / name
    payload = stdout.replace("'", "'\\''")
    # No indentation in the script body — the shebang must be at byte 0,
    # and a `textwrap.dedent` over a multiline heredoc whose embedded
    # payload contains an unindented line fails to strip the leading
    # spaces from the others.
    script.write_text(
        f"#!/bin/sh\nprintf '%s' '{payload}'\nexit {exit_code}\n"
    )
    script.chmod(0o755)
    return script


class TestGitleaks:
    def test_runs_against_mirror_with_fake_binary(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        # Fake gitleaks exits 0 with empty array (no findings).
        fake = _make_fake_tool(tmp_path, "fake-gitleaks", stdout="[]\n")
        result = run_gitleaks(
            plan, mirror_path,
            audit_chain=chain, actor="a",
            tool_path=fake,
        )
        assert result.name == "gitleaks"
        assert result.available is True
        assert result.returncode == 0
        assert result.findings_count == 0
        assert result.event_id != ""
        assert result.succeeded is True

    def test_parses_findings_count(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        finding_json = (
            '[{"description":"AWS key","line":42},'
            '{"description":"Slack token","line":99},'
            '{"description":"GitHub PAT","line":7}]'
        )
        # gitleaks exits 1 when findings present.
        fake = _make_fake_tool(
            tmp_path, "fake-gitleaks-2", stdout=finding_json, exit_code=1,
        )
        result = run_gitleaks(
            plan, mirror_path,
            audit_chain=chain, actor="a",
            tool_path=fake,
        )
        assert result.findings_count == 3
        assert result.returncode == 1
        # gitleaks exit 1 = "found stuff" — succeeded is False (strict check)
        # but findings are still meaningful.
        assert result.succeeded is False

    def test_malformed_json_returns_zero(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        fake = _make_fake_tool(tmp_path, "fake-gitleaks-3", stdout="{not json")
        result = run_gitleaks(
            plan, mirror_path,
            audit_chain=chain, actor="a",
            tool_path=fake,
        )
        assert result.findings_count == 0

    def test_not_available_when_not_on_path(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Set PATH to a directory with nothing in it — no gitleaks.
        empty_bin = mirror_path.parent / "empty-bin"
        empty_bin.mkdir()
        monkeypatch.setenv("PATH", str(empty_bin))
        result = run_gitleaks(
            plan, mirror_path,
            audit_chain=chain, actor="a",
            # No tool_path override → uses shutil.which("gitleaks") → None.
        )
        assert result.available is False
        assert result.returncode == -1
        assert result.findings_count == 0
        assert result.event_id == ""
        assert result.succeeded is False

    def test_not_available_appends_no_chain_event(
        self, plan: PurgePlan, mirror_path: Path,
        operator_repo: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fresh_chain = AuditChain(operator_repo / "fresh-anchor-gl")
        empty_bin = mirror_path.parent / "empty-bin-2"
        empty_bin.mkdir()
        monkeypatch.setenv("PATH", str(empty_bin))
        before = fresh_chain.count()
        run_gitleaks(
            plan, mirror_path,
            audit_chain=fresh_chain, actor="a",
        )
        after = fresh_chain.count()
        assert after - before == 0


class TestTrufflehog:
    def test_parses_ndjson_findings(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        ndjson = (
            '{"SourceMetadata":{"git":{"file":"a"}},"DetectorName":"Slack"}\n'
            '{"SourceMetadata":{"git":{"file":"b"}},"DetectorName":"AWS"}\n'
            '\n'  # blank line (heartbeat) — should be skipped
            '{}\n'  # empty object — skipped
            '{"SourceMetadata":{"git":{"file":"c"}},"DetectorName":"GitHub"}\n'
        )
        fake = _make_fake_tool(
            tmp_path, "fake-trufflehog", stdout=ndjson, exit_code=183,
        )
        result = run_trufflehog(
            plan, mirror_path,
            audit_chain=chain, actor="a",
            tool_path=fake,
        )
        # 3 non-empty objects (blank line + `{}` filtered).
        assert result.findings_count == 3
        assert result.name == "trufflehog"
        assert result.available is True
        assert result.returncode == 183

    def test_empty_stdout_returns_zero(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        fake = _make_fake_tool(tmp_path, "fake-trufflehog-2", stdout="")
        result = run_trufflehog(
            plan, mirror_path,
            audit_chain=chain, actor="a",
            tool_path=fake,
        )
        assert result.findings_count == 0
        assert result.available is True
        assert result.returncode == 0

    def test_malformed_ndjson_skipped_silently(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        ndjson = (
            'not-json-at-all\n'
            '{"DetectorName":"AWS"}\n'
            'truncated-{\n'
            '{"DetectorName":"Slack"}\n'
        )
        fake = _make_fake_tool(
            tmp_path, "fake-trufflehog-3", stdout=ndjson,
        )
        result = run_trufflehog(
            plan, mirror_path,
            audit_chain=chain, actor="a",
            tool_path=fake,
        )
        # 2 valid objects, 2 malformed lines skipped.
        assert result.findings_count == 2

    def test_not_available_returns_unavailable_result(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        empty_bin = mirror_path.parent / "empty-th-bin"
        empty_bin.mkdir()
        monkeypatch.setenv("PATH", str(empty_bin))
        result = run_trufflehog(
            plan, mirror_path,
            audit_chain=chain, actor="a",
        )
        assert result.available is False
        assert result.findings_count == 0


class TestRunScanners:
    def test_returns_both_results_in_order(
        self, plan: PurgePlan, mirror_path: Path,
        operator_repo: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        chain = AuditChain(operator_repo / "both-scanners-anchor")
        # Neither tool available — both return available=False.
        empty_bin = mirror_path.parent / "empty-both"
        empty_bin.mkdir()
        monkeypatch.setenv("PATH", str(empty_bin))
        gitleaks_r, trufflehog_r = run_scanners(
            plan, mirror_path,
            audit_chain=chain, actor="a",
        )
        assert gitleaks_r.name == "gitleaks"
        assert trufflehog_r.name == "trufflehog"
        assert gitleaks_r.available is False
        assert trufflehog_r.available is False


class TestErrors:
    def test_missing_mirror_raises(
        self, plan: PurgePlan, chain: AuditChain, tmp_path: Path,
    ) -> None:
        with pytest.raises(ScannerError, match="mirror not found"):
            run_gitleaks(
                plan, tmp_path / "no-mirror",
                audit_chain=chain, actor="a",
                tool_path=Path("/bin/true"),  # would work if mirror existed
            )


class TestTranscriptPathing:
    def test_transcript_lives_under_audit_dir(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        fake = _make_fake_tool(tmp_path, "fake-gl-tpath", stdout="[]")
        result = run_gitleaks(
            plan, mirror_path,
            audit_chain=chain, actor="a",
            tool_path=fake,
        )
        # Transcript lives under <audit_dir>/transcripts/<event_id>.log.
        assert result.transcript_path.is_file()
        assert result.transcript_path.parent == chain.audit_dir / "transcripts"
        assert result.transcript_path.name == f"{result.event_id}.log"
        # 0600 from the streaming helper.
        import stat as _stat
        mode = _stat.S_IMODE(result.transcript_path.stat().st_mode)
        assert mode == 0o600
