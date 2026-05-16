"""Tests for `sange.core.streaming` — the §7.0.6 subprocess streaming helper."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

from sange.core.audit import AuditChain, EventKind
from sange.core.streaming import StreamResult, run_streamed
from sange.core.streaming.streamer import StreamingError

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX-only: shell-style argv + 0600 mode + SIGTERM semantics",
)


@pytest.fixture
def chain(tmp_path: Path) -> AuditChain:
    return AuditChain(tmp_path)


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path


class TestBasicInvocation:
    def test_echo_captures_stdout(self, chain: AuditChain) -> None:
        echo = shutil.which("echo") or "/bin/echo"
        result = run_streamed(
            [echo, "hello world"],
            audit_chain=chain,
            actor="alice@cli",
        )
        assert isinstance(result, StreamResult)
        assert result.returncode == 0
        assert result.succeeded
        assert result.stdout_lines == 1
        assert result.stderr_lines == 0
        assert result.timed_out is False
        assert result.signal_cascade == ()

    def test_nonzero_exit_reports_returncode(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["false"],
            audit_chain=chain,
            actor="alice@cli",
        )
        assert result.returncode != 0
        assert result.succeeded is False
        assert result.timed_out is False

    def test_stderr_only(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["sh", "-c", "echo to-stderr >&2"],
            audit_chain=chain,
            actor="alice@cli",
        )
        assert result.returncode == 0
        assert result.stdout_lines == 0
        assert result.stderr_lines == 1

    def test_both_streams(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["sh", "-c", "echo out; echo err >&2; echo out2"],
            audit_chain=chain,
            actor="alice@cli",
        )
        assert result.returncode == 0
        assert result.stdout_lines == 2
        assert result.stderr_lines == 1

    def test_executable_not_found_raises(self, chain: AuditChain) -> None:
        with pytest.raises(StreamingError, match="executable not found"):
            run_streamed(
                ["/no/such/binary/anywhere-12345"],
                audit_chain=chain,
                actor="alice@cli",
            )

    def test_empty_argv_raises(self, chain: AuditChain) -> None:
        with pytest.raises(StreamingError, match="argv must be non-empty"):
            run_streamed([], audit_chain=chain, actor="alice@cli")


class TestTranscriptFile:
    def test_transcript_path_format(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["echo", "hi"],
            audit_chain=chain,
            actor="alice@cli",
        )
        expected = chain.audit_dir / "transcripts" / f"{result.event_id}.log"
        assert result.transcript_path == expected
        assert result.transcript_path.is_file()

    def test_transcript_is_mode_0600(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["echo", "hi"],
            audit_chain=chain,
            actor="alice@cli",
        )
        mode = stat.S_IMODE(result.transcript_path.stat().st_mode)
        assert mode == 0o600

    def test_transcript_contains_both_streams(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["sh", "-c", "echo OUT_LINE; echo ERR_LINE >&2"],
            audit_chain=chain,
            actor="alice@cli",
        )
        contents = result.transcript_path.read_text(encoding="utf-8")
        assert "[stdout] OUT_LINE\n" in contents
        assert "[stderr] ERR_LINE\n" in contents

    def test_transcript_lines_marked_per_stream(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["sh", "-c", "echo a; echo b >&2; echo c"],
            audit_chain=chain,
            actor="alice@cli",
        )
        lines = result.transcript_path.read_text(encoding="utf-8").splitlines()
        # Three lines total: two stdout + one stderr.
        assert sum(1 for line in lines if line.startswith("[stdout] ")) == 2
        assert sum(1 for line in lines if line.startswith("[stderr] ")) == 1


class TestTranscriptHash:
    def test_hash_is_sha256_hex(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["echo", "deterministic"],
            audit_chain=chain,
            actor="alice@cli",
        )
        # sha256 hex digest is always 64 chars.
        assert len(result.transcript_hash) == 64
        int(result.transcript_hash, 16)  # well-formed hex

    def test_hash_matches_concatenated_streams(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["echo", "abc"],
            audit_chain=chain,
            actor="alice@cli",
        )
        expected = hashlib.sha256(b"abc\n").hexdigest()
        assert result.transcript_hash == expected

    def test_hash_orders_stdout_then_stderr(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["sh", "-c", "echo S1; echo E1 >&2"],
            audit_chain=chain,
            actor="alice@cli",
        )
        expected = hashlib.sha256(b"S1\n" + b"E1\n").hexdigest()
        assert result.transcript_hash == expected


class TestAuditChainIntegration:
    def test_appends_exactly_one_event(self, chain: AuditChain) -> None:
        assert chain.count() == 0
        run_streamed(
            ["echo", "hi"],
            audit_chain=chain,
            actor="alice@cli",
        )
        assert chain.count() == 1

    def test_event_payload_carries_streaming_metadata(
        self, chain: AuditChain,
    ) -> None:
        result = run_streamed(
            ["sh", "-c", "echo hi; echo bye >&2; exit 3"],
            audit_chain=chain,
            actor="alice@cli",
            payload={"caller": "test_suite"},
        )
        events = list(chain.iter_events())
        assert len(events) == 1
        ev = events[0]
        assert ev.id == result.event_id
        assert ev.payload["caller"] == "test_suite"  # caller field preserved
        assert ev.payload["returncode"] == 3
        assert ev.payload["transcript_hash"] == result.transcript_hash
        assert ev.payload["stdout_lines"] == 1
        assert ev.payload["stderr_lines"] == 1
        assert ev.payload["timed_out"] is False
        assert ev.payload["signal_cascade"] == []
        assert ev.payload["argv"][0] == "sh"

    def test_event_kind_default_is_generic(self, chain: AuditChain) -> None:
        run_streamed(
            ["echo", "x"],
            audit_chain=chain,
            actor="alice@cli",
        )
        ev = next(iter(chain.iter_events()))
        assert ev.kind == EventKind.GENERIC.value

    def test_event_kind_override(self, chain: AuditChain) -> None:
        run_streamed(
            ["echo", "x"],
            audit_chain=chain,
            actor="alice@cli",
            event_kind=EventKind.HOOK_RUN,
        )
        ev = next(iter(chain.iter_events()))
        assert ev.kind == EventKind.HOOK_RUN.value

    def test_chain_links_two_consecutive_invocations(
        self, chain: AuditChain,
    ) -> None:
        r1 = run_streamed(["echo", "1"], audit_chain=chain, actor="a")
        r2 = run_streamed(["echo", "2"], audit_chain=chain, actor="a")
        events = list(chain.iter_events())
        assert len(events) == 2
        # The second event's prev_hash links to the first's this_hash.
        assert events[1].prev_hash == events[0].this_hash
        # Both transcripts exist and are independent files.
        assert r1.transcript_path != r2.transcript_path


class TestLineCallback:
    def test_callback_fires_per_line(self, chain: AuditChain) -> None:
        seen: list[tuple[str, str]] = []
        run_streamed(
            ["sh", "-c", "echo aa; echo bb >&2; echo cc"],
            audit_chain=chain,
            actor="a",
            line_callback=lambda name, line: seen.append((name, line)),
        )
        assert ("stdout", "aa") in seen
        assert ("stderr", "bb") in seen
        assert ("stdout", "cc") in seen


class TestTimeoutAndSignalCascade:
    def test_timeout_sends_sigterm(self, chain: AuditChain) -> None:
        # `sleep 10` with timeout 0.3s exits quickly via SIGTERM.
        result = run_streamed(
            ["sleep", "10"],
            audit_chain=chain,
            actor="a",
            timeout=0.3,
        )
        assert result.timed_out is True
        assert "SIGTERM" in result.signal_cascade

    def test_sigterm_alone_is_enough_for_normal_processes(
        self, chain: AuditChain,
    ) -> None:
        # Normal `sleep` honors SIGTERM — no SIGKILL needed.
        result = run_streamed(
            ["sleep", "10"],
            audit_chain=chain,
            actor="a",
            timeout=0.3,
            sigterm_grace=2.0,
        )
        assert result.timed_out is True
        assert "SIGKILL" not in result.signal_cascade

    def test_sigkill_fires_when_child_ignores_sigterm(
        self, chain: AuditChain,
    ) -> None:
        # Trap SIGTERM to no-op so the cascade has to escalate.
        result = run_streamed(
            ["sh", "-c", "trap '' TERM; sleep 10"],
            audit_chain=chain,
            actor="a",
            timeout=0.3,
            sigterm_grace=0.2,
        )
        assert result.timed_out is True
        assert result.signal_cascade == ("SIGTERM", "SIGKILL")

    def test_negative_grace_rejected(self, chain: AuditChain) -> None:
        with pytest.raises(StreamingError, match="sigterm_grace"):
            run_streamed(
                ["echo", "x"],
                audit_chain=chain,
                actor="a",
                sigterm_grace=-1.0,
            )


class TestEnvAndCwd:
    def test_env_extra_visible_to_child(self, chain: AuditChain) -> None:
        result = run_streamed(
            ["sh", "-c", "echo $SANGE_TEST_VAR"],
            audit_chain=chain,
            actor="a",
            env={"SANGE_TEST_VAR": "abc123"},
        )
        contents = result.transcript_path.read_text(encoding="utf-8")
        assert "abc123" in contents

    def test_cwd_used_for_child(self, chain: AuditChain, tmp_path: Path) -> None:
        workdir = tmp_path / "elsewhere"
        workdir.mkdir()
        result = run_streamed(
            ["pwd"],
            audit_chain=chain,
            actor="a",
            cwd=workdir,
        )
        contents = result.transcript_path.read_text(encoding="utf-8")
        # macOS resolves /private/var/folders/... — accept either form.
        assert str(workdir) in contents or os.path.realpath(workdir) in contents

    def test_env_none_inherits_full_parent_env(
        self, chain: AuditChain, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SANGE_INHERITED_VAR", "parent-value")
        result = run_streamed(
            ["sh", "-c", "echo $SANGE_INHERITED_VAR"],
            audit_chain=chain,
            actor="a",
            env=None,
        )
        contents = result.transcript_path.read_text(encoding="utf-8")
        assert "parent-value" in contents
