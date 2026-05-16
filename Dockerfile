# syntax=docker/dockerfile:1.7
# Sange CLI — multi-arch container image (linux/amd64 + linux/arm64).
#
# Per ADR-033: builds from a multi-arch upstream so Apple Silicon, AWS
# Graviton, Hetzner Ampere ARM, and Raspberry Pi 4/5 all run native (no
# QEMU emulation). Multi-stage build keeps the runtime image small +
# free of compilers / build deps.
#
# Build (single-arch, dev):
#   docker build -t sange:dev .
#
# Build (multi-arch, release):
#   docker buildx build \
#     --platform linux/amd64,linux/arm64 \
#     -t ghcr.io/simsange/sange:<tag> \
#     --push .
#
# Run:
#   docker run --rm -v "$PWD":/repo -w /repo sange:dev sange --version
#
# Secret handling per §6.10: SSH key forwarding via the host agent is the
# default; BuildKit secrets (`--mount=type=secret`) are used for tokens
# in CI. NEVER pass tokens via ENV or ARG — they bake into the layer.
#
# TODO (Phase 0d 3/5 release-engineering): pin base image by digest:
#   docker manifest inspect python:3.12-slim
# capture the manifest-list digest, then change line 24 to
#   FROM python:3.12-slim@sha256:<digest> AS builder
# The tag form is already multi-arch upstream; digest pinning closes
# the supply-chain hole (an attacker republishing the tag).

# --------------------------------------------------------------------------- #
# Stage 1 — builder. Installs build deps + builds wheels.
# --------------------------------------------------------------------------- #

FROM python:3.14-slim AS builder

# Build-time deps for any C extensions (cryptography for keyring, etc.).
# Removed in the final stage so the runtime image stays minimal.
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
      build-essential \
      git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Copy build manifests first so dep changes don't bust the source-tree cache.
COPY pyproject.toml ./
COPY src/sange/_version.py ./src/sange/_version.py
COPY src/sange/__init__.py ./src/sange/__init__.py
COPY src/sange/py.typed ./src/sange/py.typed
COPY README.md ./
COPY LICENSE ./

# Resolve + build wheels into /wheels. The runtime stage `pip install`s from
# this directory so no internet access is needed at deploy time.
RUN pip install --no-cache-dir --upgrade pip build wheel \
 && pip wheel --no-cache-dir --wheel-dir /wheels \
      pydantic>=2.0 \
      typer>=0.12 \
      rich>=13.0 \
      questionary>=2.0 \
      structlog>=24.0 \
      shellingham>=1.5 \
      wcwidth \
      keyring>=24.0 \
      tomli-w>=1.0 \
      typing-extensions>=4.10

# --------------------------------------------------------------------------- #
# Stage 2 — runtime. Slim, non-root.
# --------------------------------------------------------------------------- #

FROM python:3.14-slim AS runtime

# Minimal runtime deps: git is needed for the GitDriver subprocess calls.
# Pinned arch-agnostic apt packages: same source on amd64 + arm64.
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
      git \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Non-root user per §6.10.3.
RUN groupadd --system --gid 1000 sange \
 && useradd --system --uid 1000 --gid sange --home-dir /home/sange \
      --shell /bin/bash --create-home sange

# Install pre-built wheels.
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
      pydantic typer rich questionary structlog shellingham wcwidth \
      keyring tomli-w typing-extensions \
 && rm -rf /wheels

# Install the sange package itself.
COPY --chown=sange:sange src/sange /opt/sange/src/sange
COPY --chown=sange:sange pyproject.toml /opt/sange/pyproject.toml
COPY --chown=sange:sange README.md LICENSE /opt/sange/
WORKDIR /opt/sange
RUN pip install --no-cache-dir --no-deps . \
 && rm -rf /opt/sange/.eggs /root/.cache

# Drop to non-root for the actual execution. /repo is the expected mount
# point for the user's working tree (volume-mount at runtime).
USER sange
WORKDIR /repo

# Environment hardening per §6.10.3:
#   - Disable Python's stdout buffering so logs land in real time.
#   - Force UTF-8 to side-step locale-dependent path handling.
#   - PYTHONHASHSEED=random closes a small entropy leak in long-running daemons.
ENV PYTHONUNBUFFERED=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PYTHONHASHSEED=random

# Healthcheck — `sange --version` exits 0 when the package + Python are sane.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD sange --version || exit 1

ENTRYPOINT ["sange"]
CMD ["--help"]
