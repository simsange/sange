"""Tests for `sange.core.purge.mirror` — §6.11.4 gate 2 mirror clone."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sange.core.audit import AuditChain, EventKind
from sange.core.purge import (
    MirrorError,
    PurgeFilters,
    PurgePlan,
    RepoMeta,
    create_mirror,
    verify_mirror,
)

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="POSIX git assumed"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH"),
]


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    """Create an ephemeral source repo with 2 commits, 1 tag, 1 branch."""

    src = tmp_path / "source"
    src.mkdir()

    def run(*argv: str) -> None:
        subprocess.run(
            argv,
            cwd=src,
            check=True,
            env={
                "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                "HOME": str(tmp_path),
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
                "GIT_TERMINAL_PROMPT": "0",
                "LC_ALL": "C",
            },
            capture_output=True,
        )

    run("git", "init", "--initial-branch=main", "--quiet")
    (src / "README.md").write_text("hello\n")
    run("git", "add", "README.md")
    run("git", "commit", "-m", "initial")
    (src / "secret.txt").write_text("a-secret\n")
    run("git", "add", "secret.txt")
    run("git", "commit", "-m", "add secret")
    run("git", "tag", "v1.0")
    run("git", "branch", "feature/x")
    return src


@pytest.fixture
def chain(tmp_path: Path) -> AuditChain:
    return AuditChain(tmp_path / "operator-repo")


@pytest.fixture
def plan(source_repo: Path) -> PurgePlan:
    return PurgePlan(
        created_by="alice@cli",
        target_vcs="git",
        target_repo=RepoMeta(path=str(source_repo)),
        filters=PurgeFilters(paths=["secret.txt"]),
    )


def _operator_repo(tmp_path: Path) -> Path:
    """Where `.sange/purge/<plan_id>/work.git/` lands — distinct from source."""

    operator = tmp_path / "operator-repo"
    operator.mkdir()
    return operator


class TestCreateMirror:
    def test_creates_mirror_dir(
        self, plan: PurgePlan, source_repo: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        result = create_mirror(
            plan,
            operator,
            audit_chain=chain,
            actor="alice@cli",
            source_url=f"file://{source_repo}",
        )
        assert result.path.is_dir()
        assert result.path == operator / ".sange" / "purge" / plan.plan_id / "work.git"
        assert (result.path / "HEAD").is_file()
        # Mirror clone produces a bare repo (no working tree).
        assert not (result.path / ".git").exists()

    def test_refs_match_source(
        self, plan: PurgePlan, source_repo: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        result = create_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        ref_names = {ref for ref, _ in result.refs}
        assert "refs/heads/main" in ref_names
        assert "refs/heads/feature/x" in ref_names
        assert "refs/tags/v1.0" in ref_names
        # 3 refs (2 branches + 1 tag) — no more, no less.
        assert result.ref_count == 3

    def test_fsck_passed(
        self, plan: PurgePlan, source_repo: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        result = create_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        assert result.fsck_passed is True
        assert result.fsck_event_id != ""

    def test_audit_chain_has_three_events(
        self, plan: PurgePlan, source_repo: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        create_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        events = list(chain.iter_events())
        # clone + fsck + for-each-ref = 3 events.
        assert len(events) == 3
        phases = [e.payload.get("phase") for e in events]
        assert phases == ["mirror-clone", "mirror-fsck", "mirror-for-each-ref"]
        # Chain integrity — each event prev_hash threads through.
        assert events[0].prev_hash == ""
        assert events[1].prev_hash == events[0].this_hash
        assert events[2].prev_hash == events[1].this_hash

    def test_clone_event_kind_is_generic(
        self, plan: PurgePlan, source_repo: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        create_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        events = list(chain.iter_events())
        # Streamed subprocesses use GENERIC kind — the higher-level
        # purge state-transition events (PURGE_PLAN) are appended by
        # the CLI layer separately.
        assert all(e.kind == EventKind.GENERIC.value for e in events)

    def test_refuses_to_clobber_existing_mirror(
        self, plan: PurgePlan, source_repo: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        create_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        with pytest.raises(MirrorError, match="already exists"):
            create_mirror(
                plan, operator,
                audit_chain=chain, actor="a",
                source_url=f"file://{source_repo}",
            )

    def test_non_git_vcs_rejected(
        self, source_repo: Path, chain: AuditChain, tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        svn_plan = PurgePlan(
            created_by="a",
            target_vcs="svn",
            target_repo=RepoMeta(path=str(source_repo)),
            filters=PurgeFilters(paths=["secret.txt"]),
        )
        with pytest.raises(MirrorError, match="only supports git"):
            create_mirror(
                svn_plan, operator,
                audit_chain=chain, actor="a",
                source_url=f"file://{source_repo}",
            )

    def test_bad_source_url_raises(
        self, plan: PurgePlan, chain: AuditChain, tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        with pytest.raises(MirrorError, match="git clone --mirror exited"):
            create_mirror(
                plan, operator,
                audit_chain=chain, actor="a",
                source_url=f"file://{tmp_path}/nonexistent-source",
            )

    def test_source_url_falls_back_to_plan_remote(
        self, source_repo: Path, chain: AuditChain, tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        plan = PurgePlan(
            created_by="a",
            target_vcs="git",
            target_repo=RepoMeta(
                path=str(source_repo),
                remote=f"file://{source_repo}",
            ),
            filters=PurgeFilters(paths=["secret.txt"]),
        )
        result = create_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            # No source_url override — should use plan.target_repo.remote.
        )
        assert result.source_url == f"file://{source_repo}"


class TestVerifyMirror:
    def test_unchanged_mirror_passes(
        self, plan: PurgePlan, source_repo: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        result = create_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        verification = verify_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            baseline_refs=result.refs,
        )
        assert verification.passed is True
        assert verification.added_refs == ()
        assert verification.removed_refs == ()
        assert verification.changed_refs == ()

    def test_added_ref_detected(
        self, plan: PurgePlan, source_repo: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        result = create_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        # Pretend a ref was deleted between create + verify by feeding a
        # baseline with an EXTRA ref that's now "missing" in the current
        # snapshot — exercises the removed_refs path.
        synthetic_baseline = (
            *result.refs,
            ("refs/heads/fake-baseline", "0" * 40),
        )
        verification = verify_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            baseline_refs=synthetic_baseline,
        )
        assert verification.passed is False
        assert "refs/heads/fake-baseline" in verification.removed_refs

    def test_changed_ref_detected(
        self, plan: PurgePlan, source_repo: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        result = create_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        # Construct a baseline where every sha is faked — every existing
        # ref appears as "changed".
        fake_baseline = tuple((ref, "deadbeef" * 5) for ref, _ in result.refs)
        verification = verify_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            baseline_refs=fake_baseline,
        )
        assert verification.passed is False
        # Every ref changed.
        assert len(verification.changed_refs) == result.ref_count
        ref_names = {entry[0] for entry in verification.changed_refs}
        assert "refs/heads/main" in ref_names

    def test_missing_mirror_raises(
        self, plan: PurgePlan, chain: AuditChain, tmp_path: Path,
    ) -> None:
        operator = _operator_repo(tmp_path)
        with pytest.raises(MirrorError, match="mirror not found"):
            verify_mirror(
                plan, operator,
                audit_chain=chain, actor="a",
                baseline_refs=(),
            )

    def test_added_ref_after_create(
        self, plan: PurgePlan, source_repo: Path, chain: AuditChain,
        tmp_path: Path,
    ) -> None:
        """Concurrent write: a new ref appears in the mirror post-clone.

        Simulated by injecting a ref directly into the mirror's
        `packed-refs` (or via `git update-ref` against the mirror).
        """

        operator = _operator_repo(tmp_path)
        result = create_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        # Inject a new ref via git update-ref against the mirror.
        head_sha = next(sha for ref, sha in result.refs if ref == "refs/heads/main")
        subprocess.run(
            ["git", "--git-dir", str(result.path), "update-ref",
             "refs/heads/injected", head_sha],
            check=True,
        )
        verification = verify_mirror(
            plan, operator,
            audit_chain=chain, actor="a",
            baseline_refs=result.refs,
        )
        assert verification.passed is False
        assert "refs/heads/injected" in verification.added_refs
