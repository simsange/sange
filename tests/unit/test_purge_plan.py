"""Tests for `sange.core.purge.plan` — PurgePlan model + store."""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from sange.core.purge import (
    IllegalTransition,
    PreflightCheck,
    PurgeFilters,
    PurgePlan,
    PurgePlanNotFound,
    PurgePlanStore,
    PurgeState,
    RepoMeta,
    ToolMeta,
    new_plan_id,
)


@pytest.fixture
def filters() -> PurgeFilters:
    return PurgeFilters(paths=["secrets/keys.txt"])


@pytest.fixture
def repo_meta() -> RepoMeta:
    return RepoMeta(path="/tmp/repo", remote="git@github.com:foo/bar.git", slug="foo/bar")


@pytest.fixture
def plan(filters: PurgeFilters, repo_meta: RepoMeta) -> PurgePlan:
    return PurgePlan(
        created_by="alice@cli",
        target_vcs="git",
        target_repo=repo_meta,
        filters=filters,
    )


class TestNewPlanId:
    def test_format_matches_canonical_pattern(self) -> None:
        plan_id = new_plan_id()
        assert re.match(
            r"^purge-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z-[0-9a-f]{8}$",
            plan_id,
        )

    def test_clock_override(self) -> None:
        clock = _dt.datetime(2026, 5, 17, 14, 30, 0, tzinfo=_dt.UTC)
        plan_id = new_plan_id(clock=clock)
        assert plan_id.startswith("purge-2026-05-17T14-30-00Z-")

    def test_two_calls_collide_rarely(self) -> None:
        ids = {new_plan_id() for _ in range(50)}
        # 32-bit nonce — 50 draws should not collide.
        assert len(ids) == 50


class TestPurgeFilters:
    def test_empty_filter_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one of"):
            PurgeFilters()

    def test_paths_only_ok(self) -> None:
        f = PurgeFilters(paths=["a.txt"])
        assert f.paths == ["a.txt"]
        assert f.globs == []
        assert f.replace_text_hashes == []

    def test_globs_only_ok(self) -> None:
        f = PurgeFilters(globs=["*.pem"])
        assert f.globs == ["*.pem"]

    def test_hashes_only_ok(self) -> None:
        f = PurgeFilters(replace_text_hashes=["a" * 64])
        assert f.replace_text_hashes == ["a" * 64]

    def test_all_three_ok(self) -> None:
        f = PurgeFilters(
            paths=["a"], globs=["*.b"], replace_text_hashes=["c" * 64],
        )
        assert f.paths and f.globs and f.replace_text_hashes


class TestPurgePlanConstruction:
    def test_minimal_construction(self, plan: PurgePlan) -> None:
        assert plan.state is PurgeState.PLANNED
        assert plan.target_vcs == "git"
        assert plan.target_repo.path == "/tmp/repo"
        assert plan.dry_run is False
        assert plan.batch is False
        assert plan.tool is None

    def test_default_plan_id_valid(self, plan: PurgePlan) -> None:
        assert plan.plan_id.startswith("purge-")

    def test_explicit_plan_id_validated(
        self, filters: PurgeFilters, repo_meta: RepoMeta,
    ) -> None:
        with pytest.raises(ValidationError, match="canonical format"):
            PurgePlan(
                plan_id="not-a-canonical-id",
                created_by="a",
                target_vcs="git",
                target_repo=repo_meta,
                filters=filters,
            )

    def test_updated_at_before_created_at_rejected(
        self, filters: PurgeFilters, repo_meta: RepoMeta,
    ) -> None:
        with pytest.raises(ValidationError, match="updated_at"):
            PurgePlan(
                created_by="a",
                target_vcs="git",
                target_repo=repo_meta,
                filters=filters,
                created_at="2026-05-17T12:00:00+00:00",
                updated_at="2026-05-17T11:00:00+00:00",
            )

    def test_extra_fields_forbidden(
        self, filters: PurgeFilters, repo_meta: RepoMeta,
    ) -> None:
        with pytest.raises(ValidationError):
            PurgePlan(
                created_by="a",
                target_vcs="git",
                target_repo=repo_meta,
                filters=filters,
                surprise="unexpected",  # type: ignore[call-arg]
            )

    def test_unsupported_vcs_rejected(
        self, filters: PurgeFilters, repo_meta: RepoMeta,
    ) -> None:
        with pytest.raises(ValidationError):
            PurgePlan(
                created_by="a",
                target_vcs="fossil",  # type: ignore[arg-type]
                target_repo=repo_meta,
                filters=filters,
            )


class TestPurgePlanTransition:
    def test_legal_chain(self, plan: PurgePlan) -> None:
        # planned → preflight_passed → analyzed → previewed →
        #     confirmed → executing → verified → completed
        plan.transition(PurgeState.PREFLIGHT_PASSED)
        assert plan.state is PurgeState.PREFLIGHT_PASSED
        plan.transition(PurgeState.ANALYZED)
        plan.transition(PurgeState.PREVIEWED)
        plan.transition(PurgeState.CONFIRMED)
        plan.transition(PurgeState.EXECUTING)
        plan.transition(PurgeState.VERIFIED)
        plan.transition(PurgeState.COMPLETED)
        assert plan.state is PurgeState.COMPLETED

    def test_aborted_records_reason(self, plan: PurgePlan) -> None:
        plan.transition(PurgeState.ABORTED, reason="user cancelled")
        assert plan.state is PurgeState.ABORTED
        assert plan.aborted_reason == "user cancelled"

    def test_rolled_back_records_reason(self, plan: PurgePlan) -> None:
        plan.transition(PurgeState.PREFLIGHT_PASSED)
        plan.transition(PurgeState.ANALYZED)
        plan.transition(PurgeState.PREVIEWED)
        plan.transition(PurgeState.CONFIRMED)
        plan.transition(PurgeState.EXECUTING)
        plan.transition(PurgeState.ROLLED_BACK, reason="fsck red")
        assert plan.state is PurgeState.ROLLED_BACK
        assert plan.rolled_back_reason == "fsck red"

    def test_rolled_back_can_re_enter_planned(self, plan: PurgePlan) -> None:
        plan.transition(PurgeState.PREFLIGHT_PASSED)
        plan.transition(PurgeState.ANALYZED)
        plan.transition(PurgeState.PREVIEWED)
        plan.transition(PurgeState.CONFIRMED)
        plan.transition(PurgeState.EXECUTING)
        plan.transition(PurgeState.ROLLED_BACK)
        plan.transition(PurgeState.PLANNED)
        assert plan.state is PurgeState.PLANNED

    def test_illegal_transition_raises(self, plan: PurgePlan) -> None:
        with pytest.raises(IllegalTransition):
            plan.transition(PurgeState.EXECUTING)  # skipping every gate

    def test_updated_at_advances_on_transition(self, plan: PurgePlan) -> None:
        # Pin both timestamps to an artificially-old baseline so the
        # transition's `_utcnow_iso()` recompute is guaranteed strictly
        # later regardless of how fast the test runs.
        baseline = "2026-01-01T00:00:00+00:00"
        plan.created_at = baseline
        plan.updated_at = baseline
        plan.transition(PurgeState.PREFLIGHT_PASSED)
        assert plan.updated_at > baseline


class TestPurgePlanSerialization:
    def test_json_round_trip(self, plan: PurgePlan) -> None:
        text = plan.model_dump_json()
        parsed = PurgePlan.model_validate_json(text)
        assert parsed.plan_id == plan.plan_id
        assert parsed.state is plan.state
        assert parsed.filters.paths == plan.filters.paths

    def test_state_serializes_as_string(self, plan: PurgePlan) -> None:
        data = json.loads(plan.model_dump_json())
        assert data["state"] == "planned"

    def test_round_trip_through_intermediate_state(
        self, plan: PurgePlan,
    ) -> None:
        plan.transition(PurgeState.PREFLIGHT_PASSED)
        plan.transition(PurgeState.ANALYZED)
        plan.counts = {"affected_commits": 47, "affected_refs": 12}
        plan.scanner_results = {"gitleaks": 0, "trufflehog": 1}
        plan.preflight_checks.append(
            PreflightCheck(name="fresh_mirror", status="green"),
        )
        plan.tool = ToolMeta(name="git filter-repo", version="2.47.0")
        text = plan.model_dump_json()
        parsed = PurgePlan.model_validate_json(text)
        assert parsed.state is PurgeState.ANALYZED
        assert parsed.counts == {"affected_commits": 47, "affected_refs": 12}
        assert parsed.scanner_results == {"gitleaks": 0, "trufflehog": 1}
        assert parsed.preflight_checks[0].name == "fresh_mirror"
        assert parsed.tool is not None
        assert parsed.tool.version == "2.47.0"


class TestPurgePlanStore:
    @pytest.fixture
    def store(self, tmp_path: Path) -> PurgePlanStore:
        return PurgePlanStore(tmp_path)

    def test_root_dir_is_dotsange_purge(
        self, store: PurgePlanStore, tmp_path: Path,
    ) -> None:
        assert store.root_dir == tmp_path / ".sange" / "purge"

    def test_save_and_load(
        self, store: PurgePlanStore, plan: PurgePlan,
    ) -> None:
        target = store.save(plan)
        assert target.is_file()
        loaded = store.load(plan.plan_id)
        assert loaded.plan_id == plan.plan_id
        assert loaded.target_vcs == "git"

    def test_save_is_atomic_no_tmp_residue(
        self, store: PurgePlanStore, plan: PurgePlan,
    ) -> None:
        store.save(plan)
        # No .plan-*.tmp files left behind.
        residues = list(store.plan_dir(plan.plan_id).glob(".plan-*.tmp"))
        assert residues == []

    def test_save_overwrites_existing(
        self, store: PurgePlanStore, plan: PurgePlan,
    ) -> None:
        store.save(plan)
        plan.transition(PurgeState.PREFLIGHT_PASSED)
        store.save(plan)
        loaded = store.load(plan.plan_id)
        assert loaded.state is PurgeState.PREFLIGHT_PASSED

    def test_load_missing_raises(self, store: PurgePlanStore) -> None:
        with pytest.raises(PurgePlanNotFound):
            store.load("purge-2026-01-01T00-00-00Z-deadbeef")

    def test_list_empty(self, store: PurgePlanStore) -> None:
        assert store.list_plans() == []

    def test_list_returns_sorted_ids(
        self, store: PurgePlanStore, filters: PurgeFilters,
        repo_meta: RepoMeta,
    ) -> None:
        ids = [
            "purge-2026-05-17T08-00-00Z-aaaaaaaa",
            "purge-2026-05-17T09-00-00Z-bbbbbbbb",
            "purge-2026-05-17T10-00-00Z-cccccccc",
        ]
        for pid in ids:
            p = PurgePlan(
                plan_id=pid,
                created_by="a",
                target_vcs="git",
                target_repo=repo_meta,
                filters=filters,
            )
            store.save(p)
        assert store.list_plans() == ids

    def test_list_skips_non_plan_dirs(
        self, store: PurgePlanStore, plan: PurgePlan,
    ) -> None:
        store.save(plan)
        # Create a sibling that isn't a plan dir.
        (store.root_dir / "scratch").mkdir()
        (store.root_dir / "scratch" / "notes.txt").write_text("hi")
        assert store.list_plans() == [plan.plan_id]

    def test_list_skips_plan_dir_without_plan_json(
        self, store: PurgePlanStore,
    ) -> None:
        empty_pid = "purge-2026-05-17T08-00-00Z-deadbeef"
        (store.root_dir / empty_pid).mkdir(parents=True)
        # No plan.json inside.
        assert store.list_plans() == []

    def test_invalid_plan_id_for_dir_lookup_rejected(
        self, store: PurgePlanStore,
    ) -> None:
        with pytest.raises(ValueError, match="invalid plan_id"):
            store.plan_dir("not-a-canonical-id")

    def test_exists(
        self, store: PurgePlanStore, plan: PurgePlan,
    ) -> None:
        assert store.exists(plan.plan_id) is False
        store.save(plan)
        assert store.exists(plan.plan_id) is True
