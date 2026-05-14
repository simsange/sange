"""Sange — local-first developer-experience layer between humans and their VCS.

This is the top-level package. Concrete subsystems live under:

  - sange.cli         CLI commands (T-040+)
  - sange.tui         Textual TUI app
  - sange.core        Domain + Application layers (config, lifecycle, audit, …)
  - sange.adapters    VCSDriver / AIProvider / Secrets / Container / MCP transports
  - sange.daemon      sanged process (JSON-RPC server, supervisor)
  - sange.ipc         JSON-RPC schema + HMAC / mTLS transports
  - sange.installer   doctor, bootstrap, recover
  - sange.plugins     entry-point loader + signature verification
  - sange.utils       logging, hashing, paths, fluent decorator

See .design/sange-architecture.md §7.1 for the layered architecture diagram.
"""

from sange._version import __version__

__all__ = ["__version__"]
