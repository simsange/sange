"""`sange doctor --container` audits per §6.10.3.

Pure check functions — every input is a parameter (env mapping, fs
root, callable for uid lookup) so tests don't need to actually be
inside a container or to monkey with `os.environ` globally.

Findings vs failures:

  * Each function returns a `ContainerCheck` with `ok` + `message` +
    a typed `findings` list. `ok=False` means "this check found
    something the operator should fix"; `findings` holds the
    specific items.
  * `findings` items NEVER include secret VALUES. Env-var values
    are not logged; only NAMES are reported. File mode bits are
    reported as octal strings, never the file content.
"""

from __future__ import annotations

import os
import re
import stat as _stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

# Default container-detection signals per Docker / Podman conventions.
_DEFAULT_CONTAINER_MARKERS: Final[tuple[str, ...]] = (
    "/.dockerenv",       # Docker
    "/run/.containerenv",  # Podman
)

# Heuristic env-var name patterns that LIKELY hold a secret value.
# Case-insensitive. Each pattern is a regex; we test against the
# full env-var name (not a substring search) for clarity. The
# patterns are intentionally conservative — false positives cost
# the operator nothing (they fix a non-issue); false negatives
# leave a secret leaking.
_DEFAULT_SECRET_NAME_PATTERNS: Final[tuple[str, ...]] = (
    r".*_TOKEN$",
    r".*_KEY$",
    r".*_SECRET$",
    r".*_PASSWORD$",
    r".*_PASSWD$",
    r".*_API_KEY$",
    r".*_CREDENTIAL$",
    r".*_CREDENTIALS$",
    r"^TOKEN$",
    r"^API_KEY$",
    r"^SECRET$",
    r"^PASSWORD$",
    # Common provider-specific patterns.
    r"^AWS_SECRET_ACCESS_KEY$",
    r"^GITHUB_TOKEN$",
    r"^GITLAB_TOKEN$",
    r"^NPM_TOKEN$",
    r"^PYPI_TOKEN$",
)

# Allow-list of env vars whose names match a secret pattern but
# whose presence is structural, not sensitive. Stops the noise.
_DEFAULT_SECRET_NAME_ALLOWLIST: Final[frozenset[str]] = frozenset({
    "AWS_DEFAULT_KEY_ALGORITHM",  # config name only
    "SSH_KEY_PATH",               # path only, not the key
})

# Maximum mode bits acceptable for a secret-mount file per §6.10.3.
# Owner read-only is the spec-minimum.
DEFAULT_MAX_SECRET_MODE: Final[int] = 0o400

# SSH client requires 0600 max on private key files.
DEFAULT_MAX_SSH_KEY_MODE: Final[int] = 0o600


@dataclass(frozen=True)
class ContainerCheck:
    """One container-audit check's outcome.

    Fields:
      * `name`     — check identifier (matches the CLI's display key).
      * `ok`      — True iff nothing remediable was found.
      * `message` — short human summary; the CLI prints this verbatim.
      * `findings`— typed details for `--json` consumers. Each item
                    is a dict with check-specific keys; NEVER contains
                    secret values.
    """

    name: str
    ok: bool
    message: str
    findings: list[dict[str, object]] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Check functions
# --------------------------------------------------------------------------- #


def check_in_container(
    env: Mapping[str, str] | None = None,
    marker_paths: Sequence[str] = _DEFAULT_CONTAINER_MARKERS,
) -> ContainerCheck:
    """Verify we're running inside a container.

    Detection signals (any of which is sufficient):
      * `/.dockerenv` exists (Docker).
      * `/run/.containerenv` exists (Podman).
      * `KUBERNETES_SERVICE_HOST` env var set (in-cluster pod).
      * `container=` env var set (systemd-nspawn / LXC convention).

    `--container` mode that runs OUTSIDE a container should produce
    a precise error rather than noisy false positives on the host's
    SSH keys + dev env vars.
    """

    effective_env: Mapping[str, str] = (
        env if env is not None else os.environ
    )

    signals: list[str] = []
    for marker in marker_paths:
        if Path(marker).exists():
            signals.append(marker)
    if effective_env.get("KUBERNETES_SERVICE_HOST"):
        signals.append("env:KUBERNETES_SERVICE_HOST")
    if effective_env.get("container"):
        signals.append("env:container")

    if signals:
        return ContainerCheck(
            name="in-container",
            ok=True,
            message=f"running in container ({', '.join(signals)})",
            findings=[{"signal": s} for s in signals],
        )
    return ContainerCheck(
        name="in-container",
        ok=False,
        message=(
            "not inside a container — `--container` requires a "
            "container runtime. Run via `docker run` / `podman run`."
        ),
    )


def check_non_root(
    uid_fn: object | None = None,
) -> ContainerCheck:
    """Verify the running process is non-root.

    `uid_fn` is the test-injection hook (callable returning int);
    default `os.geteuid` when available, falls back to "skipped"
    on platforms without `geteuid` (Windows).
    """

    if uid_fn is None:
        uid_fn = getattr(os, "geteuid", None)
    if uid_fn is None:
        return ContainerCheck(
            name="non-root",
            ok=True,
            message="skipped (no os.geteuid on this platform)",
        )

    assert callable(uid_fn)
    uid = uid_fn()
    if uid == 0:
        return ContainerCheck(
            name="non-root",
            ok=False,
            message=(
                "running as root (uid 0) — §6.10.3 mandates non-root. "
                "Fix: ensure the Dockerfile USER directive sets a "
                "non-zero uid (the shipped Dockerfile uses uid 1000)."
            ),
            findings=[{"uid": 0}],
        )
    return ContainerCheck(
        name="non-root",
        ok=True,
        message=f"running as uid {uid}",
        findings=[{"uid": uid}],
    )


def check_leaky_env_vars(
    env: Mapping[str, str] | None = None,
    *,
    name_patterns: Sequence[str] = _DEFAULT_SECRET_NAME_PATTERNS,
    allowlist: frozenset[str] = _DEFAULT_SECRET_NAME_ALLOWLIST,
) -> ContainerCheck:
    """Find env vars whose names look secret-shaped + have values.

    Per §6.10.3: "No environment variables containing secret
    values past startup (early-zeroed)." This check fires after
    startup so any matching env-var-with-value is a leak.

    NEVER reads or returns the value. Only the variable NAME +
    value length appear in the findings (the length is useful
    for distinguishing "set-but-empty" from "set-to-secret"
    without exposing entropy).
    """

    effective_env: Mapping[str, str] = (
        env if env is not None else os.environ
    )
    compiled = [re.compile(p, re.IGNORECASE) for p in name_patterns]

    findings: list[dict[str, object]] = []
    for name, value in effective_env.items():
        if name in allowlist:
            continue
        if not value:
            continue
        if any(p.fullmatch(name) for p in compiled):
            findings.append({
                "var": name,
                "length": len(value),
            })

    if findings:
        return ContainerCheck(
            name="env-vars-secret-shaped",
            ok=False,
            message=(
                f"{len(findings)} env var(s) match a secret-name "
                f"pattern with a non-empty value — see findings "
                f"for names. Replace with file or keyring mounts."
            ),
            findings=findings,
        )
    return ContainerCheck(
        name="env-vars-secret-shaped",
        ok=True,
        message="no secret-shaped env vars with non-empty values",
    )


def check_secret_mount_perms(
    mount_dir: Path | str = "/run/secrets",
    *,
    max_mode: int = DEFAULT_MAX_SECRET_MODE,
) -> ContainerCheck:
    """Scan a secret-mount dir for files whose mode exceeds `max_mode`.

    BuildKit + Docker secrets land at `/run/secrets/<name>` as
    tmpfs files. The §6.10.3 invariant is 0400 — owner read-only.
    Anything with extra bits set is a deployment bug.

    Returns `ok=True` with a "no mount dir" message when the
    directory doesn't exist — that's not necessarily a failure
    (the container may not use file-mounted secrets). Operators
    who expect secret files should configure the path via the
    eventual `sange.toml`.
    """

    mount_path = Path(mount_dir)
    if not mount_path.is_dir():
        return ContainerCheck(
            name="secret-mount-perms",
            ok=True,
            message=f"skipped (no {mount_path} dir)",
        )

    findings: list[dict[str, object]] = []
    try:
        entries = sorted(mount_path.iterdir())
    except OSError as exc:
        return ContainerCheck(
            name="secret-mount-perms",
            ok=False,
            message=f"cannot list {mount_path}: {exc}",
        )
    for entry in entries:
        if not entry.is_file():
            continue
        try:
            mode = _stat.S_IMODE(entry.stat().st_mode)
        except OSError:
            continue
        # Any bit set beyond the allowed mask is a leak.
        leaked_bits = mode & ~max_mode
        if leaked_bits:
            findings.append({
                "path": str(entry),
                "mode": oct(mode),
                "max_allowed": oct(max_mode),
            })

    if findings:
        return ContainerCheck(
            name="secret-mount-perms",
            ok=False,
            message=(
                f"{len(findings)} secret file(s) exceed mode "
                f"{oct(max_mode)} — chmod each to {oct(max_mode)} "
                f"or fix the mount-time perms."
            ),
            findings=findings,
        )
    return ContainerCheck(
        name="secret-mount-perms",
        ok=True,
        message=f"all secret-mount files within mode {oct(max_mode)}",
    )


def check_ssh_key_perms(
    home: Path | str | None = None,
    *,
    max_mode: int = DEFAULT_MAX_SSH_KEY_MODE,
) -> ContainerCheck:
    """Scan `~/.ssh/id_*` for files whose mode is broader than 0600.

    The SSH client itself enforces this — if a key has world- or
    group-readable bits set, `ssh` refuses to use it. Catching the
    misconfig at doctor-time saves the operator a confusing
    "Permissions are too open" error mid-purge.

    `home=None` defaults to `Path.home()`. A non-existent `~/.ssh`
    returns `ok=True / skipped` (the container may not need SSH).
    """

    if home is None:
        try:
            home = Path.home()
        except RuntimeError:
            return ContainerCheck(
                name="ssh-key-perms",
                ok=True,
                message="skipped (no HOME)",
            )
    ssh_dir = Path(home) / ".ssh"
    if not ssh_dir.is_dir():
        return ContainerCheck(
            name="ssh-key-perms",
            ok=True,
            message=f"skipped (no {ssh_dir} dir)",
        )

    findings: list[dict[str, object]] = []
    for entry in sorted(ssh_dir.iterdir()):
        if not entry.is_file():
            continue
        # Match `id_<algo>` (the SSH-keygen convention). Skip the .pub
        # cousins — those CAN be world-readable.
        if not entry.name.startswith("id_") or entry.name.endswith(".pub"):
            continue
        try:
            mode = _stat.S_IMODE(entry.stat().st_mode)
        except OSError:
            continue
        leaked_bits = mode & ~max_mode
        if leaked_bits:
            findings.append({
                "path": str(entry),
                "mode": oct(mode),
                "max_allowed": oct(max_mode),
            })

    if findings:
        return ContainerCheck(
            name="ssh-key-perms",
            ok=False,
            message=(
                f"{len(findings)} SSH private key(s) exceed mode "
                f"{oct(max_mode)} — `ssh` will refuse to use them. "
                f"Fix: `chmod {oct(max_mode)[2:]} ~/.ssh/id_*`."
            ),
            findings=findings,
        )
    return ContainerCheck(
        name="ssh-key-perms",
        ok=True,
        message=f"all SSH private keys within mode {oct(max_mode)}",
    )


__all__ = [
    "DEFAULT_MAX_SECRET_MODE",
    "DEFAULT_MAX_SSH_KEY_MODE",
    "ContainerCheck",
    "check_in_container",
    "check_leaky_env_vars",
    "check_non_root",
    "check_secret_mount_perms",
    "check_ssh_key_perms",
]
