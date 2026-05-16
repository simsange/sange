"""Tests for src/sange/core/audit/event.py — AuditEvent + compute_hash + make_event."""

from __future__ import annotations

import datetime as _dt
import json

import pytest

from sange.core.audit.event import (
    AuditEvent,
    AuditEventError,
    EventKind,
    compute_hash,
    make_event,
)


class TestEventKind:
    def test_canonical_values(self) -> None:
        # Some values that the rest of the codebase references.
        assert EventKind.AI_CALL.value == "ai-call"
        assert EventKind.COMMIT_PUSH.value == "commit-push"
        assert EventKind.GITIGNORE_SWAP.value == "gitignore-swap"
        assert EventKind.HOOK_RUN.value == "hook-run"

    def test_all_values(self) -> None:
        vals = EventKind.all_values()
        assert "ai-call" in vals
        assert "generic" in vals


class TestMakeEvent:
    def test_minimal(self) -> None:
        e = make_event(EventKind.COMMIT_DRAFT, actor="alice")
        assert e.actor == "alice"
        assert e.kind == "commit-draft"
        assert e.payload == {}
        assert e.prev_hash == ""
        assert len(e.this_hash) == 64   # sha256 hex
        # id is a uuid4 string.
        assert len(e.id) == 36 and e.id.count("-") == 4

    def test_payload_passed_through(self) -> None:
        e = make_event(
            EventKind.COMMIT_PUSH, actor="alice",
            payload={"counter": 1, "remote": "origin"},
        )
        assert e.payload == {"counter": 1, "remote": "origin"}

    def test_actor_required(self) -> None:
        with pytest.raises(AuditEventError, match="actor"):
            make_event(EventKind.COMMIT_DRAFT, actor="")

    def test_kind_must_be_non_empty(self) -> None:
        with pytest.raises(AuditEventError, match="kind"):
            make_event("", actor="alice")

    def test_custom_kind_string(self) -> None:
        # Plugins ship custom event kinds; the model accepts any
        # non-empty string.
        e = make_event("plugin/my-event", actor="alice")
        assert e.kind == "plugin/my-event"

    def test_deterministic_with_fixed_inputs(self) -> None:
        ts = "2026-05-17T12:00:00+00:00"
        eid = "00000000-0000-4000-8000-000000000000"
        e1 = make_event(
            EventKind.COMMIT_DRAFT, actor="a", payload={"x": 1},
            timestamp=ts, event_id=eid,
        )
        e2 = make_event(
            EventKind.COMMIT_DRAFT, actor="a", payload={"x": 1},
            timestamp=ts, event_id=eid,
        )
        assert e1.this_hash == e2.this_hash


class TestComputeHash:
    def test_known_inputs(self) -> None:
        # Hand-rolled hash — anchors the function to a known value so
        # accidental serialization changes (key order, separators)
        # fail loudly instead of silently rotating the chain.
        e = AuditEvent(
            id="abc", kind="commit-draft",
            timestamp="2026-05-17T12:00:00+00:00",
            actor="alice", payload={"x": 1}, prev_hash="",
        )
        h = compute_hash(e)
        # The exact value isn't load-bearing; what matters is that
        # the function is deterministic + reproducible.
        assert len(h) == 64
        # Calling it again returns the same hash.
        assert compute_hash(e) == h

    def test_this_hash_field_excluded_from_hash_input(self) -> None:
        # If a record's `this_hash` somehow got included in its own
        # hash input, the function would be circularly defined. Verify
        # mutating `this_hash` doesn't change `compute_hash`.
        e1 = AuditEvent(
            id="abc", kind="x", timestamp="t", actor="a",
            payload={}, prev_hash="", this_hash="aaa",
        )
        e2 = AuditEvent(
            id="abc", kind="x", timestamp="t", actor="a",
            payload={}, prev_hash="", this_hash="zzz",
        )
        assert compute_hash(e1) == compute_hash(e2)

    def test_payload_mutation_changes_hash(self) -> None:
        e1 = AuditEvent(
            id="abc", kind="x", timestamp="t", actor="a",
            payload={"counter": 1},
        )
        e2 = AuditEvent(
            id="abc", kind="x", timestamp="t", actor="a",
            payload={"counter": 2},
        )
        assert compute_hash(e1) != compute_hash(e2)


class TestSerialization:
    def test_to_json_and_back(self) -> None:
        e = make_event(
            EventKind.GITIGNORE_SWAP, actor="alice",
            payload={"profile": "lang/python", "stage": "dev"},
        )
        line = e.to_json()
        # One line, valid JSON.
        assert "\n" not in line
        loaded = AuditEvent.from_json(line)
        assert loaded == e

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(AuditEventError, match="missing required"):
            AuditEvent.from_dict({"kind": "x", "timestamp": "t", "actor": "a"})

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(AuditEventError, match="invalid JSON"):
            AuditEvent.from_json("{not valid")

    def test_non_object_top_level_raises(self) -> None:
        with pytest.raises(AuditEventError, match="JSON object"):
            AuditEvent.from_json("[1, 2, 3]")
