"""`.git/hooks/<event>` shim writer.

Per §7.4, Sange never installs hook content directly into
`.git/hooks/` — that directory isn't committed, so hook content
there is invisible to the team. Instead, the executable hooks
live at `<repo>/.sange/hooks/<event>/<NN-name>` (committable,
visible in git history), and Sange writes tiny shims into
`.git/hooks/<event>` that delegate to `sange hooks run <event>`.

A shim looks like this:

    #!/usr/bin/env bash
    # SANGE-HOOK-SHIM v1 — managed by `sange hooks install`. Do not edit.
    # To remove: `sange hooks uninstall` or delete this file.
    exec sange hooks run pre-commit "$@"

The marker comment lets `uninstall_git_shims` find Sange-managed
shims and skip any pre-existing user-authored hooks. The `exec`
ensures the shim's process is replaced by the engine — stdin,
stdout, stderr, and the exit code all pass through cleanly.

`install_git_shims` is idempotent: re-running it overwrites
existing Sange-managed shims (so the marker version bumps stay
honest) but never touches non-shim hook files.
"""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# The set of git lifecycle events Sange knows about. The shim writer
# scans `.sange/hooks/<event>/` for each one and writes a shim only
# when the directory has at least one executable hook.
GIT_HOOK_EVENTS: tuple[str, ...] = (
    "applypatch-msg",
    "pre-applypatch",
    "post-applypatch",
    "pre-commit",
    "pre-merge-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
    "pre-rebase",
    "post-checkout",
    "post-merge",
    "pre-push",
    "post-update",
    "push-to-checkout",
    "pre-receive",
    "update",
    "proc-receive",
    "post-receive",
)

SHIM_MARKER = "# SANGE-HOOK-SHIM v1 — managed by `sange hooks install`. Do not edit."
SHIM_SHEBANG = "#!/usr/bin/env bash"


class ShimError(Exception):
    """Raised when the shim writer can't proceed (no .git/, perms, etc.)."""


@dataclass(frozen=True)
class ShimInstallResult:
    """One shim's outcome from `install_git_shims`."""

    event: str
    path: Path
    status: str
    # status ∈ {
    #   "installed",       — Sange wrote a new shim where none existed
    #   "updated",         — Sange overwrote an existing Sange shim
    #   "skipped-foreign", — a non-Sange hook file existed; left alone
    #   "skipped-no-hooks",— no executable hooks under .sange/hooks/<event>/
    # }


def install_git_shims(
    repo_root: Path,
    *,
    events: Iterable[str] | None = None,
    force: bool = False,
) -> tuple[ShimInstallResult, ...]:
    """Write `.git/hooks/<event>` shims for every event with hooks.

    Args:
      repo_root: the repo (must contain `.git/`).
      events:    restrict to a subset of `GIT_HOOK_EVENTS`. None =
                 all known events.
      force:     when True, overwrite existing non-Sange hook files
                 too. Use sparingly — this clobbers pre-existing
                 hook scripts the user may have set up by hand.

    Raises:
      ShimError: `.git/` doesn't exist, or `.git/hooks/` can't be
                 created.
    """

    git_dir = Path(repo_root).resolve() / ".git"
    if not git_dir.is_dir():
        raise ShimError(
            f"{repo_root} is not a git working tree (no .git/)"
        )
    hooks_target = git_dir / "hooks"
    try:
        hooks_target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ShimError(f"cannot create {hooks_target}: {exc}") from exc

    chosen_events = tuple(events) if events is not None else GIT_HOOK_EVENTS

    sange_hooks = Path(repo_root).resolve() / ".sange" / "hooks"

    results: list[ShimInstallResult] = []
    for event in chosen_events:
        event_dir = sange_hooks / event
        has_hooks = _event_has_executable_hooks(event_dir)
        shim_path = hooks_target / event
        if not has_hooks:
            results.append(ShimInstallResult(
                event=event, path=shim_path, status="skipped-no-hooks",
            ))
            continue

        if shim_path.exists():
            existing = _read_text_safely(shim_path)
            if existing is not None and SHIM_MARKER in existing:
                _write_executable(shim_path, _build_shim(event))
                results.append(ShimInstallResult(
                    event=event, path=shim_path, status="updated",
                ))
                continue
            if not force:
                results.append(ShimInstallResult(
                    event=event, path=shim_path, status="skipped-foreign",
                ))
                continue

        _write_executable(shim_path, _build_shim(event))
        results.append(ShimInstallResult(
            event=event, path=shim_path, status="installed",
        ))

    return tuple(results)


def uninstall_git_shims(
    repo_root: Path,
    *,
    events: Iterable[str] | None = None,
) -> tuple[ShimInstallResult, ...]:
    """Remove every `.git/hooks/<event>` that carries the Sange marker.

    Foreign (non-Sange) hook files are left untouched. Returns one
    `ShimInstallResult` per event considered, with status ∈
    `{"removed", "skipped-foreign", "skipped-absent"}`.
    """

    git_dir = Path(repo_root).resolve() / ".git"
    if not git_dir.is_dir():
        raise ShimError(
            f"{repo_root} is not a git working tree (no .git/)"
        )
    hooks_target = git_dir / "hooks"

    chosen_events = tuple(events) if events is not None else GIT_HOOK_EVENTS

    results: list[ShimInstallResult] = []
    for event in chosen_events:
        shim_path = hooks_target / event
        if not shim_path.exists():
            results.append(ShimInstallResult(
                event=event, path=shim_path, status="skipped-absent",
            ))
            continue
        existing = _read_text_safely(shim_path)
        if existing is None or SHIM_MARKER not in existing:
            results.append(ShimInstallResult(
                event=event, path=shim_path, status="skipped-foreign",
            ))
            continue
        try:
            shim_path.unlink()
        except OSError as exc:
            raise ShimError(f"cannot remove {shim_path}: {exc}") from exc
        results.append(ShimInstallResult(
            event=event, path=shim_path, status="removed",
        ))

    return tuple(results)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _event_has_executable_hooks(event_dir: Path) -> bool:
    if not event_dir.is_dir():
        return False
    for child in event_dir.iterdir():
        if not child.is_file():
            continue
        if os.access(child, os.X_OK):
            return True
    return False


def _read_text_safely(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _build_shim(event: str) -> str:
    """Compose the per-event shim script content."""

    return (
        f"{SHIM_SHEBANG}\n"
        f"{SHIM_MARKER}\n"
        f"# To remove: `sange hooks uninstall` or delete this file.\n"
        f"exec sange hooks run {event} \"$@\"\n"
    )


def _write_executable(target: Path, content: str) -> None:
    """tmp+rename+chmod write. Idempotent + safe under SIGKILL."""

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".shim-tmp",
        dir=str(target.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        # chmod +x for user/group/other read+execute. Permissive on
        # purpose — `git` runs hooks as the current user.
        os.chmod(
            tmp_path,
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
            | stat.S_IRGRP | stat.S_IXGRP
            | stat.S_IROTH | stat.S_IXOTH,
        )
        os.replace(tmp_path, target)
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


__all__ = [
    "GIT_HOOK_EVENTS",
    "SHIM_MARKER",
    "ShimError",
    "ShimInstallResult",
    "install_git_shims",
    "uninstall_git_shims",
]
