"""Tests for src/sange/core/audit/chain.py — AuditChain writer."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from sange.core.audit.chain import AuditChain
from sange.core.audit.event import AuditEvent, EventKind


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    return r


class TestAppend:
    def test_first_append_creates_shard(self, repo: Path) -> None:
        chain = AuditChain(repo)
        e = chain.append(EventKind.COMMIT_DRAFT, actor="alice")
        assert chain.audit_dir.is_dir()
        # Shard file exists.
        shards = list(chain.audit_dir.glob("*.jsonl"))
        assert len(shards) == 1
        # The event was written.
        line = shards[0].read_text(encoding="utf-8").strip()
        loaded = AuditEvent.from_json(line)
        assert loaded.this_hash == e.this_hash

    def test_subsequent_appends_link(self, repo: Path) -> None:
        chain = AuditChain(repo)
        e1 = chain.append(EventKind.COMMIT_DRAFT, actor="alice")
        e2 = chain.append(EventKind.COMMIT_APPROVE, actor="alice")
        e3 = chain.append(EventKind.COMMIT_PUSH, actor="alice")
        # prev_hash chains correctly.
        assert e1.prev_hash == ""
        assert e2.prev_hash == e1.this_hash
        assert e3.prev_hash == e2.this_hash

    def test_count_matches(self, repo: Path) -> None:
        chain = AuditChain(repo)
        for _ in range(5):
            chain.append(EventKind.AI_CALL, actor="alice")
        assert chain.count() == 5

    def test_iso_week_sharding(self, tmp_path: Path) -> None:
        # Two appends at the same ISO week land in the same shard.
        repo = tmp_path / "repo"
        repo.mkdir()
        clock = _dt.datetime(2026, 5, 17, 12, 0, tzinfo=_dt.UTC)
        chain = AuditChain(repo, clock=clock)
        chain.append(EventKind.COMMIT_DRAFT, actor="a", timestamp=clock.isoformat())
        chain.append(EventKind.COMMIT_APPROVE, actor="a", timestamp=clock.isoformat())
        shards = sorted(chain.audit_dir.glob("*.jsonl"))
        assert len(shards) == 1
        # Shard name carries year + week.
        iso_year, iso_week, _ = clock.isocalendar()
        assert shards[0].name == f"{iso_year:04d}-W{iso_week:02d}.jsonl"

    def test_payload_round_trips(self, repo: Path) -> None:
        chain = AuditChain(repo)
        payload = {
            "counter": 7,
            "subject": "feat(auth): add SSO",
            "nested": {"actor_role": "approver"},
            "list": ["a", "b"],
        }
        e = chain.append(EventKind.COMMIT_PUSH, actor="alice", payload=payload)
        assert e.payload == payload

    def test_last_hash_empty_initially(self, repo: Path) -> None:
        chain = AuditChain(repo)
        assert chain.last_hash() == ""

    def test_last_hash_after_appends(self, repo: Path) -> None:
        chain = AuditChain(repo)
        chain.append(EventKind.COMMIT_DRAFT, actor="alice")
        e2 = chain.append(EventKind.COMMIT_APPROVE, actor="alice")
        assert chain.last_hash() == e2.this_hash

    def test_iter_events_chronological(self, repo: Path) -> None:
        chain = AuditChain(repo)
        e1 = chain.append(EventKind.COMMIT_DRAFT, actor="alice")
        e2 = chain.append(EventKind.COMMIT_APPROVE, actor="alice")
        e3 = chain.append(EventKind.COMMIT_PUSH, actor="alice")
        ids = [e.id for e in chain.iter_events()]
        assert ids == [e1.id, e2.id, e3.id]


class TestMultipleShards:
    def test_chain_across_shards(self, tmp_path: Path) -> None:
        # Write into week A's shard, then advance clock to week B,
        # write another → chain links across.
        repo = tmp_path / "repo"
        repo.mkdir()
        week_a = _dt.datetime(2026, 5, 11, 12, 0, tzinfo=_dt.UTC)  # ISO 2026-W20
        week_b = _dt.datetime(2026, 5, 18, 12, 0, tzinfo=_dt.UTC)  # ISO 2026-W21

        chain_a = AuditChain(repo, clock=week_a)
        e_a = chain_a.append(EventKind.COMMIT_DRAFT, actor="alice",
                             timestamp=week_a.isoformat())

        chain_b = AuditChain(repo, clock=week_b)
        e_b = chain_b.append(EventKind.COMMIT_APPROVE, actor="alice",
                             timestamp=week_b.isoformat())

        # Each in its own shard.
        shards = sorted(chain_b.audit_dir.glob("*.jsonl"))
        assert len(shards) == 2
        # Chain links: e_b.prev_hash == e_a.this_hash.
        assert e_b.prev_hash == e_a.this_hash
        # iter_events walks both shards.
        ids = [e.id for e in chain_b.iter_events()]
        assert ids == [e_a.id, e_b.id]
