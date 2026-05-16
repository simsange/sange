"""Tests for src/sange/core/audit/verify.py — chain integrity verification."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from sange.core.audit.chain import AuditChain
from sange.core.audit.event import EventKind
from sange.core.audit.verify import (
    VerificationReport,
    verify_chain,
    verify_repo,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    return r


def _build_chain(repo: Path, n: int = 3) -> AuditChain:
    chain = AuditChain(repo)
    for i in range(n):
        chain.append(EventKind.COMMIT_DRAFT, actor="alice",
                     payload={"counter": i + 1})
    return chain


class TestVerifyChain:
    def test_clean_chain_verifies(self, repo: Path) -> None:
        chain = _build_chain(repo, n=3)
        shard = next(iter(chain.audit_dir.glob("*.jsonl")))
        report = verify_chain(shard)
        assert report.verified
        assert report.records_checked == 3
        assert report.failure_kind == ""

    def test_empty_shard_returns_zero(self, repo: Path) -> None:
        chain = AuditChain(repo)
        chain.audit_dir.mkdir(parents=True)
        empty = chain.audit_dir / "2026-W20.jsonl"
        empty.write_text("", encoding="utf-8")
        report = verify_chain(empty)
        assert report.verified
        assert report.records_checked == 0

    def test_missing_shard_reports_malformed(self, repo: Path) -> None:
        report = verify_chain(repo / "nonexistent.jsonl")
        assert not report.verified
        assert report.failure_kind == "malformed"
        assert "not found" in report.failure_message

    def test_malformed_line_detected(self, repo: Path) -> None:
        chain = _build_chain(repo, n=2)
        shard = next(iter(chain.audit_dir.glob("*.jsonl")))
        lines = shard.read_text(encoding="utf-8").splitlines()
        lines.insert(1, "{NOT VALID JSON")
        shard.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = verify_chain(shard)
        assert not report.verified
        assert report.failure_kind == "malformed"
        assert report.failure_index == 1

    def test_tampered_record_detected(self, repo: Path) -> None:
        chain = _build_chain(repo, n=3)
        shard = next(iter(chain.audit_dir.glob("*.jsonl")))
        lines = shard.read_text(encoding="utf-8").splitlines()
        # Mutate the actor of record 1 (mid-chain) — this_hash won't match.
        rec = json.loads(lines[1])
        rec["actor"] = "attacker"
        lines[1] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
        shard.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = verify_chain(shard)
        assert not report.verified
        assert report.failure_kind == "hash-mismatch"
        assert report.failure_index == 1

    def test_broken_prev_hash_detected(self, repo: Path) -> None:
        chain = _build_chain(repo, n=3)
        shard = next(iter(chain.audit_dir.glob("*.jsonl")))
        lines = shard.read_text(encoding="utf-8").splitlines()
        # Mutate the prev_hash of record 2 — but we have to also fix
        # its this_hash so the test isolates "chain-break" (not also
        # "hash-mismatch"). Easier: just verify a record whose
        # prev_hash doesn't match the previous record's this_hash by
        # surgery on record 1 + recompute its this_hash.
        from sange.core.audit.event import AuditEvent, compute_hash
        e = AuditEvent.from_json(lines[1])
        e_with_bad_prev = AuditEvent(
            id=e.id, kind=e.kind, timestamp=e.timestamp, actor=e.actor,
            payload=e.payload, prev_hash="deadbeef" * 8,
        )
        # Recompute this_hash so the only failure is the prev_hash linkage.
        e_with_bad_prev = AuditEvent(
            id=e.id, kind=e.kind, timestamp=e.timestamp, actor=e.actor,
            payload=e.payload, prev_hash="deadbeef" * 8,
            this_hash=compute_hash(e_with_bad_prev),
        )
        lines[1] = e_with_bad_prev.to_json()
        shard.write_text("\n".join(lines) + "\n", encoding="utf-8")

        report = verify_chain(shard)
        assert not report.verified
        assert report.failure_kind == "chain-break"
        assert report.failure_index == 1

    def test_starting_prev_hash_threads_across_shards(self, repo: Path) -> None:
        # If we feed a wrong starting_prev_hash, the first record fails
        # chain-break.
        chain = _build_chain(repo, n=1)
        shard = next(iter(chain.audit_dir.glob("*.jsonl")))
        report = verify_chain(shard, starting_prev_hash="not-the-right-hash")
        assert not report.verified
        assert report.failure_kind == "chain-break"
        assert report.failure_index == 0


class TestVerifyRepo:
    def test_empty_audit_dir_vacuously_verifies(self, repo: Path) -> None:
        report = verify_repo(repo)
        assert report.verified
        assert report.records_checked == 0

    def test_single_shard_chain(self, repo: Path) -> None:
        _build_chain(repo, n=4)
        report = verify_repo(repo)
        assert report.verified
        assert report.records_checked == 4
        assert report.shards_checked == 1

    def test_multi_shard_chain(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        week_a = _dt.datetime(2026, 5, 11, 12, 0, tzinfo=_dt.UTC)
        week_b = _dt.datetime(2026, 5, 18, 12, 0, tzinfo=_dt.UTC)

        chain_a = AuditChain(repo, clock=week_a)
        chain_a.append(EventKind.COMMIT_DRAFT, actor="alice",
                       timestamp=week_a.isoformat())
        chain_a.append(EventKind.COMMIT_APPROVE, actor="alice",
                       timestamp=week_a.isoformat())

        chain_b = AuditChain(repo, clock=week_b)
        chain_b.append(EventKind.COMMIT_PUSH, actor="alice",
                       timestamp=week_b.isoformat())

        report = verify_repo(repo)
        assert report.verified
        assert report.records_checked == 3
        assert report.shards_checked == 2

    def test_multi_shard_tampering_detected(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        week_a = _dt.datetime(2026, 5, 11, 12, 0, tzinfo=_dt.UTC)
        week_b = _dt.datetime(2026, 5, 18, 12, 0, tzinfo=_dt.UTC)

        chain_a = AuditChain(repo, clock=week_a)
        chain_a.append(EventKind.COMMIT_DRAFT, actor="alice",
                       timestamp=week_a.isoformat())
        chain_b = AuditChain(repo, clock=week_b)
        chain_b.append(EventKind.COMMIT_APPROVE, actor="alice",
                       timestamp=week_b.isoformat())

        # Tamper with shard B.
        shards = sorted(chain_b.audit_dir.glob("*.jsonl"))
        lines = shards[1].read_text(encoding="utf-8").splitlines()
        rec = json.loads(lines[0])
        rec["actor"] = "attacker"
        lines[0] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
        shards[1].write_text("\n".join(lines) + "\n", encoding="utf-8")

        report = verify_repo(repo)
        assert not report.verified
        assert report.failure_kind == "hash-mismatch"
        assert report.shards_checked == 2   # both shards examined before break
