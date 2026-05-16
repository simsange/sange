"""`sange.core.doctor` — pure check functions for the doctor CLI.

The CLI wrapper in `src/sange/cli/doctor.py` orchestrates these checks;
the functions themselves are pure (env / fs / mapping → result) so
they can be unit-tested without spawning a container.

Container-mode checks per §6.10.3:

  * `check_in_container(env, marker_paths)` — verify we're actually
    running inside a container; called before the other container
    checks fire so a misinvoked `sange doctor --container` on a
    bare host produces a precise error rather than a noisy fail.
  * `check_non_root(uid_fn)` — §6.10.3 mandates the container runs
    as non-root.
  * `check_leaky_env_vars(env, secret_name_patterns)` — flag env
    vars whose names look secret-shaped and have non-empty values.
    The value itself NEVER appears in the result.
  * `check_secret_mount_perms(mount_dir, max_mode)` — scan a
    secret-mount dir (default `/run/secrets/`) for files whose
    mode bits exceed the §6.10 0400 max.
  * `check_ssh_key_perms(home)` — scan `~/.ssh/id_*` for files
    that fail the 0600 SSH-client requirement.

All checks return `ContainerCheck` (separate type from the CLI's
`CheckResult` so the core layer doesn't depend on the typer
sub-app).
"""

from __future__ import annotations

from sange.core.doctor.container import (
    ContainerCheck,
    check_in_container,
    check_leaky_env_vars,
    check_non_root,
    check_secret_mount_perms,
    check_ssh_key_perms,
)

__all__ = [
    "ContainerCheck",
    "check_in_container",
    "check_leaky_env_vars",
    "check_non_root",
    "check_secret_mount_perms",
    "check_ssh_key_perms",
]
