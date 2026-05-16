"""Tests for `sange.core.purge.backup` — §6.11.4 gate 3 tarball + sha256."""

from __future__ import annotations

import datetime as _dt
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from sange.core.audit import AuditChain
from sange.core.purge import (
    BackupError,
    PurgeFilters,
    PurgePlan,
    RepoMeta,
    create_backup,
    create_mirror,
    verify_backup,
)

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="POSIX tar + git"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH"),
    pytest.mark.skipif(shutil.which("tar") is None, reason="tar not on PATH"),
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
    (src / "f.txt").write_text("hello\n")
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


class TestCreateBackup:
    def test_writes_tarball(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        result = create_backup(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        assert result.tarball_path.is_file()
        assert result.tarball_path.suffix == ".gz"
        assert result.tarball_path.name.startswith("backup-")
        assert result.tarball_path.name.endswith(".tar.gz")
        assert result.size_bytes > 0

    def test_tarball_in_plan_dir(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        result = create_backup(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        # Tarball lands alongside the mirror under the plan dir.
        assert result.tarball_path.parent == mirror_path.parent
        assert result.tarball_path.parent.name == plan.plan_id

    def test_sidecar_contains_hex_and_filename(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        result = create_backup(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        sidecar_text = result.sidecar_path.read_text(encoding="utf-8")
        assert result.sha256_hex in sidecar_text
        assert result.tarball_path.name in sidecar_text

    def test_sha256_matches_independent_hash(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        import hashlib

        result = create_backup(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        expected = hashlib.sha256(result.tarball_path.read_bytes()).hexdigest()
        assert result.sha256_hex == expected
        assert len(result.sha256_hex) == 64

    def test_tarball_is_valid_gzip(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        result = create_backup(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        # `tarfile` opens valid gzip-compressed tarballs.
        with tarfile.open(result.tarball_path, "r:gz") as tar:
            names = tar.getnames()
        # The mirror dir's name appears as the archive root.
        assert any(name == mirror_path.name or name.startswith(f"{mirror_path.name}/")
                   for name in names)

    def test_audit_chain_has_event(
        self, plan: PurgePlan, mirror_path: Path,
        operator_repo: Path,
    ) -> None:
        # Use a fresh chain so we count only T-111d's events.
        fresh_chain = AuditChain(operator_repo / "fresh-anchor")
        before = fresh_chain.count()
        # Need a fresh mirror under the fresh-anchor location too.
        # Easier: reuse mirror_path but with the fresh chain — works because
        # `create_backup` only needs audit_chain for the tar subprocess audit.
        create_backup(
            plan, mirror_path,
            audit_chain=fresh_chain, actor="a",
        )
        after = fresh_chain.count()
        assert after - before == 1

    def test_event_id_populated(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        result = create_backup(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        assert result.event_id != ""

    def test_clock_override_pins_timestamp(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        clock = _dt.datetime(2026, 5, 17, 18, 30, 45, tzinfo=_dt.UTC)
        result = create_backup(
            plan, mirror_path,
            audit_chain=chain, actor="a",
            clock=clock,
        )
        assert result.tarball_path.name == "backup-2026-05-17T18-30-45Z.tar.gz"


class TestCreateBackupErrors:
    def test_missing_mirror_raises(
        self, plan: PurgePlan, tmp_path: Path, chain: AuditChain,
    ) -> None:
        with pytest.raises(BackupError, match="mirror not found"):
            create_backup(
                plan, tmp_path / "nonexistent",
                audit_chain=chain, actor="a",
            )

    def test_mirror_outside_plan_dir_rejected(
        self, plan: PurgePlan, tmp_path: Path, chain: AuditChain,
    ) -> None:
        # An arbitrary git dir not under <repo>/.sange/purge/<plan_id>/.
        stray = tmp_path / "stray.git"
        stray.mkdir()
        with pytest.raises(BackupError, match="not inside the plan dir"):
            create_backup(
                plan, stray,
                audit_chain=chain, actor="a",
            )

    def test_duplicate_backup_rejected(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        clock = _dt.datetime(2026, 5, 17, 18, 30, 45, tzinfo=_dt.UTC)
        create_backup(
            plan, mirror_path,
            audit_chain=chain, actor="a",
            clock=clock,
        )
        with pytest.raises(BackupError, match="already exists"):
            create_backup(
                plan, mirror_path,
                audit_chain=chain, actor="a",
                clock=clock,
            )


class TestVerifyBackup:
    def test_unchanged_backup_verifies(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        result = create_backup(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        assert verify_backup(result) is True

    def test_mutated_backup_fails_verification(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        result = create_backup(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        # Append a byte to the tarball — sha256 changes.
        with result.tarball_path.open("ab") as fp:
            fp.write(b"x")
        assert verify_backup(result) is False

    def test_missing_backup_fails_verification(
        self, plan: PurgePlan, mirror_path: Path, chain: AuditChain,
    ) -> None:
        result = create_backup(
            plan, mirror_path, audit_chain=chain, actor="a",
        )
        result.tarball_path.unlink()
        assert verify_backup(result) is False
