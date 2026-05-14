"""Sange Adapters — VCS / AI / secrets / containers / MCP transports.

Per §6.2 of the architecture prompt the Adapter layer is the only path
between Sange's VCS-agnostic Domain and the concrete underlying tool
(git, svn, hg, Anthropic, OpenAI, keyring, vault, docker, podman, …).

Sub-packages:

  * `vcs/`        — `VCSDriver` Protocol + per-VCS implementations.
  * `ai/`         — `AIProvider` Protocol + per-provider implementations.
  * `secrets/`    — keyring / vault / 1password / age / gpg resolvers.
  * `containers/` — docker / podman wrappers.
  * `mcp/`        — MCP client + server + transports (stdio / http+sse / streamable_http).
  * `notifiers/`  — desktop notification backends.

The Protocol-driven layout enforces SOLID's dependency-inversion: the
Application + Domain layers depend on Protocols here, never on concrete
implementations.
"""

from __future__ import annotations

__all__: list[str] = []
