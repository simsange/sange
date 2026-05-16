"""Tests for `sange.core.purge.analyzer` — read-only `--analyze` capability."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sange.core.audit import AuditChain
from sange.core.purge import (
    AnalysisError,
    PurgeFilters,
    PurgePlan,
    RepoMeta,
    analyze_mirror,
    create_mirror,
)

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="POSIX git assumed"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH"),
]


def _git(cwd: Path, *argv: str, env_home: Path) -> str:
    """Run git with hermetic env; return stdout."""

    result = subprocess.run(
        ["git", *argv],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(env_home),
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        },
    )
    return result.stdout


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    """Ephemeral source: 4 commits touching `secret.txt`, `readme.md`, `notes/keys.pem`."""

    src = tmp_path / "source"
    src.mkdir()
    _git(src, "init", "--initial-branch=main", "--quiet", env_home=tmp_path)

    # Commit 1: README (NOT a target).
    (src / "readme.md").write_text("hello\n")
    _git(src, "add", "readme.md", env_home=tmp_path)
    _git(src, "commit", "-m", "c1: readme", env_home=tmp_path)

    # Commit 2: secret.txt v1.
    (src / "secret.txt").write_text("v1-content\n")
    _git(src, "add", "secret.txt", env_home=tmp_path)
    _git(src, "commit", "-m", "c2: add secret v1", env_home=tmp_path)

    # Commit 3: secret.txt v2 (different blob).
    (src / "secret.txt").write_text("v2-different-content\n")
    _git(src, "add", "secret.txt", env_home=tmp_path)
    _git(src, "commit", "-m", "c3: secret v2", env_home=tmp_path)

    # Commit 4: keys.pem under notes/.
    (src / "notes").mkdir()
    (src / "notes" / "keys.pem").write_text("-----BEGIN-----\n")
    _git(src, "add", "notes/keys.pem", env_home=tmp_path)
    _git(src, "commit", "-m", "c4: keys", env_home=tmp_path)

    return src


@pytest.fixture
def operator_repo(tmp_path: Path) -> Path:
    operator = tmp_path / "operator"
    operator.mkdir()
    return operator


@pytest.fixture
def chain(operator_repo: Path) -> AuditChain:
    return AuditChain(operator_repo)


def _new_plan(source_repo: Path, **filter_kwargs: object) -> PurgePlan:
    return PurgePlan(
        created_by="alice@cli",
        target_vcs="git",
        target_repo=RepoMeta(path=str(source_repo)),
        filters=PurgeFilters(**filter_kwargs),  # type: ignore[arg-type]
    )


@pytest.fixture
def mirror_path(
    source_repo: Path, operator_repo: Path, chain: AuditChain,
) -> Path:
    plan = _new_plan(source_repo, paths=["secret.txt"])
    result = create_mirror(
        plan, operator_repo,
        audit_chain=chain, actor="a",
        source_url=f"file://{source_repo}",
    )
    return result.path


class TestAnalyzeMirrorExactPath:
    def test_finds_two_blob_versions_of_secret(
        self, source_repo: Path, operator_repo: Path,
        chain: AuditChain, mirror_path: Path,
    ) -> None:
        plan = _new_plan(source_repo, paths=["secret.txt"])
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        # 2 versions of secret.txt → 2 distinct blob shas.
        assert result.deleted_objects == 2
        assert result.matched_paths == ("secret.txt",)

    def test_affected_commits_count(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(source_repo, paths=["secret.txt"])
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        # secret.txt appeared in commits c2 + c3 = 2 commits.
        assert result.affected_commits == 2

    def test_size_delta_negative(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(source_repo, paths=["secret.txt"])
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        # "v1-content\n" + "v2-different-content\n" = 11 + 21 = 32 bytes.
        assert result.size_delta_bytes == -(11 + 21)

    def test_no_match_returns_zero_counts(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(source_repo, paths=["nonexistent.txt"])
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        assert result.deleted_objects == 0
        assert result.affected_commits == 0
        assert result.size_delta_bytes == 0
        assert result.matched_paths == ()
        assert result.matched_blob_shas == ()
        # No git-log subprocess fired when matched_paths is empty.
        assert result.log_event_id == ""


class TestAnalyzeMirrorGlob:
    def test_glob_matches_subdir(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(source_repo, globs=["notes/*"])
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        assert "notes/keys.pem" in result.matched_paths
        assert result.deleted_objects == 1

    def test_glob_matches_extension(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(source_repo, globs=["*.pem"])
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        # `*.pem` against `notes/keys.pem`: fnmatch treats `*` as
        # "anything including /" so it matches.
        assert "notes/keys.pem" in result.matched_paths

    def test_path_and_glob_unioned(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(
            source_repo,
            paths=["secret.txt"],
            globs=["notes/*"],
        )
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        assert set(result.matched_paths) == {"secret.txt", "notes/keys.pem"}
        # 2 versions of secret + 1 keys.pem = 3 blobs.
        assert result.deleted_objects == 3


class TestAnalyzeMirrorCounts:
    def test_as_counts_dict_shape(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(source_repo, paths=["secret.txt"])
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        counts = result.as_counts()
        assert counts["affected_commits"] == 2
        assert counts["deleted_objects"] == 2
        assert counts["size_delta_bytes"] == -32
        # `affected_refs` intentionally NOT in this slice — T-111d.
        assert "affected_refs" not in counts

    def test_audit_chain_has_three_events_when_matched(
        self, source_repo: Path, operator_repo: Path,
    ) -> None:
        # Fresh chain to count only T-111c's events (mirror_path fixture
        # uses a shared chain that already has 3 from create_mirror).
        fresh_chain = AuditChain(operator_repo / "fresh-audit-anchor")
        plan = _new_plan(source_repo, paths=["secret.txt"])
        # Create a separate mirror anchored in the fresh chain location.
        mirror_result = create_mirror(
            plan, operator_repo / "fresh-audit-anchor",
            audit_chain=fresh_chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        before = fresh_chain.count()
        analyze_mirror(
            plan, mirror_result.path,
            audit_chain=fresh_chain, actor="a",
        )
        after = fresh_chain.count()
        # 3 subprocesses (rev-list + cat-file + log) → 3 audit events.
        assert after - before == 3

    def test_audit_chain_two_events_when_no_match(
        self, source_repo: Path, operator_repo: Path,
    ) -> None:
        # No-match case skips git log entirely → 2 events instead of 3.
        fresh_chain = AuditChain(operator_repo / "no-match-anchor")
        plan = _new_plan(source_repo, paths=["never-existed.bin"])
        mirror_result = create_mirror(
            plan, operator_repo / "no-match-anchor",
            audit_chain=fresh_chain, actor="a",
            source_url=f"file://{source_repo}",
        )
        before = fresh_chain.count()
        analyze_mirror(
            plan, mirror_result.path,
            audit_chain=fresh_chain, actor="a",
        )
        after = fresh_chain.count()
        assert after - before == 2

    def test_event_ids_populated(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(source_repo, paths=["secret.txt"])
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        assert result.revlist_event_id != ""
        assert result.catfile_event_id != ""
        assert result.log_event_id != ""
        # Three distinct event ids.
        assert len({
            result.revlist_event_id,
            result.catfile_event_id,
            result.log_event_id,
        }) == 3


class TestAnalyzeMirrorErrors:
    def test_non_git_vcs_rejected(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        svn_plan = PurgePlan(
            created_by="a",
            target_vcs="svn",
            target_repo=RepoMeta(path=str(source_repo)),
            filters=PurgeFilters(paths=["secret.txt"]),
        )
        with pytest.raises(AnalysisError, match="only supports git"):
            analyze_mirror(
                svn_plan, mirror_path, audit_chain=chain, actor="a",
            )

    def test_missing_mirror_raises(
        self, source_repo: Path, tmp_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(source_repo, paths=["secret.txt"])
        with pytest.raises(AnalysisError, match="mirror not found"):
            analyze_mirror(
                plan, tmp_path / "no-such-mirror",
                audit_chain=chain, actor="a",
            )


class TestAnalysisResultProperties:
    def test_deleted_objects_property(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(source_repo, paths=["secret.txt"])
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        assert result.deleted_objects == len(result.matched_blob_shas)

    def test_matched_blob_shas_sorted(
        self, source_repo: Path, mirror_path: Path, chain: AuditChain,
    ) -> None:
        plan = _new_plan(source_repo, paths=["secret.txt"])
        result = analyze_mirror(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        assert list(result.matched_blob_shas) == sorted(result.matched_blob_shas)
