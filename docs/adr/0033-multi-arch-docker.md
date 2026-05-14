---
generated_by: tools/generators/adr_scaffold.py
generator_version: 1.0.0
generated_at: 2026-05-15T00:30:00Z
input_sha256: 3341e4710cf8fe14425bd026c346e250107bfd9bcb3b588d9e1860d7f6fff4a6
output_sha256: pending
manual_edits_allowed: true
---
# ADR-0033: Multi-arch Docker + Linux images (amd64 / arm64 / armv7)

**Status:** Accepted
**Date:** 2026-05-15

## Context

Sange ships container images (the `sanged` daemon, the Laravel web-UI container,
CI runner images, the §6.12 kit's `vps-setup/docker/` fragments, and any
installer artifact built via `docker buildx`). It also installs Linux packages
*inside* those containers (Python 3.12+, PHP 8.4, the Laravel + Livewire 4
stack, system tools like `git-filter-repo`, `gitleaks`, `trufflehog`,
`cloudflared`, `cosign`).

Three CPU architectures matter for v1.0 deployment:

  * **`linux/amd64`** — the Intel/AMD-64 default. Most cloud VPS hosts (AWS
    EC2 default, Google Compute Engine default, Azure VMs, Linode/Vultr/OVH/
    DigitalOcean default), classic Intel/AMD developer laptops, and most
    GitHub Actions runners.
  * **`linux/arm64`** — Apple Silicon (M1/M2/M3/M4) developer hosts, AWS
    Graviton EC2 (cheaper compute), Ampere-based VPS providers (Hetzner CCX
    ARM, Oracle Cloud Free Tier A1), Raspberry Pi 4/5, every modern Android
    Linux container.
  * **`linux/arm/v7`** — 32-bit ARM (Raspberry Pi 2/3, older single-board
    computers, low-cost edge devices). v0.5+ aspirational; the §6.12 kit's
    "VPS setup" recipes don't target this tier but `sange doctor --container`
    must still run on it.

A single-arch image (the historical Docker default) breaks every developer
on Apple Silicon and every production deployment on ARM cloud hosts. The
foot-gun is severe: `docker pull` silently emulates the missing arch via
QEMU, which is **20-50× slower** than native execution and has known
correctness gaps for syscalls that ARM and AMD64 implement differently
(e.g. memory ordering, signal delivery).

Per the user directive on 2026-05-15: *"all docker container based [projects],
both docker and the linux version installed, should be able to run on both
arm, and amd and intel processors."*

## Decision

Every Sange-shipped Docker image and every Linux package layer installed by
Sange is **built and tested across `linux/amd64` and `linux/arm64` from v1.0,
and additionally `linux/arm/v7` from v2.0**. Concretely:

  1. **Build via `docker buildx` with multi-platform output** — CI's release
     workflow runs `docker buildx build --platform linux/amd64,linux/arm64
     -t ghcr.io/simtabi/sanged:<tag> --push .`. The resulting image is an
     **OCI manifest list** (one tag, multiple arch manifests); `docker pull`
     selects the host's arch automatically.
  2. **Base-image pinning by digest** — `FROM python:3.12-slim@sha256:...`
     pulls a *multi-arch* manifest by content-addressed digest. The manifest
     itself references per-arch image hashes; verifying it covers all archs.
  3. **Linux distribution choice** — `python:3.12-slim` (Debian-based),
     `php:8.4-fpm-alpine` (Alpine-based), and `caddy:2-alpine` are all
     published multi-arch upstream. We **do not** ship from upstreams that
     are amd64-only.
  4. **Multi-arch CI matrix** — `.github/workflows/ci.yml` runs the unit +
     integration test suite on **both** `ubuntu-24.04` (amd64) and
     `ubuntu-24.04-arm` (arm64, available in GitHub Actions from 2024-Q4).
     A test that depends on arch-specific behavior is a defect by default.
  5. **Native ARM CI for release builds** — release-build jobs use native
     ARM runners (not QEMU emulation) so the resulting images are
     bit-identical to what users get on their Apple Silicon laptops or
     Hetzner Ampere VPS.
  6. **`sange doctor --container` enforces arch awareness** — the doctor
     reports the host's `uname -m`, the running container's `dpkg --print-
     architecture` (or equivalent), and warns if they disagree (indicating
     QEMU emulation). A warning surfaces in `sange status` for as long as
     the mismatch persists.
  7. **Premade kit fragments are multi-arch** — `templates/vps-setup/docker/
     install.sh` pulls the Docker engine via its arch-aware package
     repository; the kit's `templates/scripts/bootstrap/` checks `uname -m`
     and selects the correct upstream archive when a tool publishes
     per-arch tarballs (e.g. `cloudflared`, `git-filter-repo` PyInstaller
     bundles).
  8. **OCI artifact bundles inherit the same rule** — release bundles
     pushed via `sange bundle publish` to an OCI registry are themselves
     multi-arch when they contain binaries; single-arch when the artifact
     is pure source/docs.
  9. **Signature verification works across arches** — `cosign verify-blob`
     and the §6.9.5 public-bundle verification flow are
     architecture-independent (signatures cover the manifest list, not
     individual arch hashes; trusting the manifest list trusts the linked
     arch images by their per-arch digest).
  10. **Reproducible-build claim is per-arch** — SLSA 3 provenance
      attestations record the build platform; the same source produces
      bit-identical output **per arch**. A consumer who downloads the
      arm64 image gets the arm64 attestation; the amd64 user gets the
      amd64 attestation.

## Alternatives Rejected

  * **Ship amd64-only and rely on QEMU emulation** — rejected. QEMU is 20-50×
    slower and has known correctness gaps. Apple Silicon developers see
    50-second startup times for what should be 1-second container boots.
    Production ARM VPS deployments would burn cash on emulation overhead.
  * **Build amd64 + arm64 only (drop armv7)** — accepted as the v1.0 default;
    armv7 lands in v2.0. Reason: armv7 is a long-tail userbase (Raspberry Pi
    2/3 holdouts) and the build matrix doubles; the cost is real but the
    deferment is short.
  * **Use a single tag per arch (`:1.0-amd64`, `:1.0-arm64`)** — rejected.
    Forces users to know their arch and edit their `docker-compose.yml`
    accordingly. OCI manifest lists are the standard mechanism for "one tag,
    many arches" and every Docker / Podman / containerd client supports them.
  * **Cross-compile via QEMU in CI** — rejected for release-builds. QEMU is
    fine for syntax checks and small build steps, but the *integration* test
    suite must run on native silicon to catch arch-specific bugs. GitHub's
    `ubuntu-24.04-arm` runner (2024-Q4 GA) makes native ARM CI free.
  * **Defer the requirement to v2.0** — rejected. The user's directive is
    explicit; v1.0 ships multi-arch from day one.

## Consequences

**Positive:**
  * Apple Silicon developers (Sange's primary author + many of the seven
    personas in §3) get native-speed containers; no QEMU surprises.
  * Production deployments on Hetzner Ampere ARM VPS (≈40% cheaper than
    AMD64 equivalents) work out of the box.
  * Raspberry Pi 4/5 edge deployments work without extra effort.
  * Reduces the support load — no "why is Sange so slow on my Mac?" issues.

**Negative:**
  * CI build matrix doubles (every build is now amd64 + arm64). Each release
    takes ~2× the runner-minutes. Mitigated by GitHub Actions' native ARM
    runners (no QEMU emulation cost).
  * Pinning by digest is stricter — when an upstream rebases their base
    image we have to re-pin both arch manifests. Mitigated by Dependabot
    weekly Mon 06:00 (per the global CLAUDE.md schedule).
  * Some upstream tools don't ship arm64 binaries (`git-filter-repo`'s
    PyInstaller bundle is amd64-only as of 2025-12-31). When that happens,
    we install from source (slower bootstrap but functional). Documented
    per-tool in the §6.11 purge subsystem.

**Neutral:**
  * armv7 deferred to v2.0 — soft commitment; revisited based on telemetry
    once v1.0 ships.

## Lens Notes

  * **Security:** Multi-arch images mean signing covers every arch a user
    might pull; no "the signature was made on amd64 but I'm on arm64" gap.
    Sigstore + cosign manifest-list verification handles this natively.
  * **Performance:** Eliminates 20-50× QEMU overhead on the most common
    developer host (Apple Silicon) and the cheapest production host
    (Ampere ARM). Wins both audiences simultaneously.
  * **Maintainability:** One CI workflow handles every arch via buildx
    matrix; no per-arch fork. The kit's `templates/vps-setup/docker/`
    fragments are arch-aware via `uname -m` branching, not hardcoded.
  * **Developer Experience:** "It just works" on Mac M1+, on Linux laptops,
    on Hetzner Ampere VPS, on Raspberry Pi. No "your arch is unsupported"
    discoverability failures.
  * **Operability:** `sange doctor --container` surfaces arch mismatches
    (QEMU emulation detected) so the operator can fix them before
    production. The hash-chained audit log records the running arch on
    every state-changing event.
  * **Cost:** ~2× CI runner-minutes per release (mitigated by free GitHub
    ARM runners). Avoided cost: every support hour on "why is Sange slow
    on Mac" tickets, and every ARM VPS user who would otherwise be locked
    to the more-expensive AMD64 SKU.

## References

  * [Docker buildx multi-platform builds](https://docs.docker.com/build/building/multi-platform/) — primary tooling reference.
  * [OCI image manifest spec](https://github.com/opencontainers/image-spec/blob/main/manifest.md) — the manifest-list format that makes "one tag, many arches" work.
  * [GitHub Actions — Larger and ARM runners](https://docs.github.com/en/actions/using-github-hosted-runners/about-larger-runners) — `ubuntu-24.04-arm` GA reference.
  * [Hetzner Cloud — CCX ARM instances](https://www.hetzner.com/cloud) — production ARM target.
  * `.design/sange-architecture-prompt.md` §6.1 (stack picks), §6.6 (container lifecycle), §6.10 (container secret mgmt), §6.12 (kit's docker fragments) — affected sections of the prompt.
  * `.design/plans/decisions-log.md` row ADR-033 — index entry.

---

*Authored by the responding model + reviewer. Added to `.design/plans/decisions-log.md`
as ADR-033 on 2026-05-15.*
