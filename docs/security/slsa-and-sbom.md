# SLSA provenance + SBOM

Sange's release pipeline produces three artifacts and three
verifiable claims about them. This file explains what ships today,
what's planned, and how to verify both.

## Why this matters

A binary you didn't build is a binary you're trusting. Sange's
release pipeline gives downstream consumers tools to check three
things independently:

| Claim | Mechanism | What you can prove |
| :--- | :--- | :--- |
| **Provenance** — this artifact was built by Sange's CI from this exact commit. | SLSA-level build provenance attestation, signed by sigstore. | Tamper-evidence between commit and artifact. |
| **Bill of materials** — this artifact contains these dependencies at these versions. | CycloneDX SBOM, attached to the artifact. | Vulnerability scanning + license audit against a known-good list. |
| **Identity** — the publisher is who they claim to be. | Sigstore keyless signing tied to GitHub's OIDC identity. | The artifact came from `github.com/simsange/sange` and not a typosquat. |

The three together let a downstream consumer answer "should I
trust this binary?" without trusting any single party — including
us.

## What ships today (v0.1.0)

The `release.yml` workflow at `.github/workflows/release.yml` runs
when a `v*.*.*` tag is pushed. The relevant supply-chain hooks:

```yaml
permissions:
  contents: write     # for GitHub Release creation
  id-token: write     # for OIDC (PyPI trusted publishing + sigstore)
  packages: write     # for GHCR push
  attestations: write # for sigstore signing

# ...

- name: Build + push multi-arch image
  uses: docker/build-push-action@v7
  with:
    context: .
    platforms: linux/amd64,linux/arm64
    push: true
    tags: |
      ghcr.io/simsange/sange:v0.1.0
      ghcr.io/simsange/sange:latest
    provenance: true   # ← SLSA build provenance, signed via OIDC
    sbom: true         # ← CycloneDX SBOM, attached to the image
```

What that produces, per release:

| Artifact | Where | What's attached |
| :--- | :--- | :--- |
| `sange-0.1.0-py3-none-any.whl` | PyPI (when publisher activates) | Sigstore-signed via OIDC trusted-publisher. |
| `sange-0.1.0.tar.gz` | PyPI | Same. |
| `ghcr.io/simsange/sange:v0.1.0` (linux/amd64) | GHCR | SLSA provenance attestation + CycloneDX SBOM + sigstore signature, all as OCI attestations attached to the image. |
| `ghcr.io/simsange/sange:v0.1.0` (linux/arm64) | GHCR | Same — separate per-arch attestations under one manifest list. |
| `v0.1.0` GitHub Release | GitHub | Auto-extracted from `docs/CHANGELOG.md` `[Unreleased]` section. |

The signing keys are **never** stored as secrets. Sigstore +
GitHub's OIDC produce a per-build, per-workflow identity proof.
Verification proves "this artifact was built by this workflow at
this ref, period" — no signing-key compromise is possible because
no signing key exists.

## How to verify a release

### The Docker image — attestation readout

Sange's release pipeline (`docker/build-push-action@v7` with
`provenance: true` + `sbom: true`) writes attestations as
**BuildKit in-index manifests** (the `unknown/unknown` entry
documented below). This is the format produced by every modern
`docker buildx` build with attestations enabled — it is **not**
the same as the cosign-tag pattern (`<image>.sig` / `<image>.att`).
The right tool to read them is `docker buildx imagetools`:

```bash
# 1. Pull the image.
docker pull ghcr.io/simsange/sange:v0.1.0.post1

# 2. Read the SLSA v1.0 provenance (per platform).
docker buildx imagetools inspect ghcr.io/simsange/sange:v0.1.0.post1 \
    --format '{{json .Provenance}}'
# Look for these fields per platform:
#   runDetails.builder.id       — the exact GitHub Actions run URL
#   buildDefinition.buildType   — BuildKit's SLSA-definitions URI
#   buildDefinition.externalParameters.configSource — Dockerfile + source
#   runDetails.metadata.startedOn / finishedOn

# 3. Read the CycloneDX SBOM (per platform).
docker buildx imagetools inspect ghcr.io/simsange/sange:v0.1.0.post1 \
    --format '{{json .SBOM}}'
# The output is the full CycloneDX JSON for each platform —
# pipe through `jq '.linux_amd64.SPDX // .linux_amd64.SBOM'` etc.
```

If `Provenance` is `null` or missing the `builder.id` of a
`https://github.com/simsange/sange/actions/runs/...` URL, **do not
deploy the image**. The mismatch means either the artifact came
from somewhere else (an attacker), the workflow ran on a
different ref, or the attestations got stripped between push and
pull — investigate before continuing.

### Why `cosign verify-attestation` doesn't find them

`cosign verify-attestation` and `slsa-verifier verify-image`
discover attestations via the cosign tag-prefix pattern (a
`sha256-<digest>.att` tag alongside the image). BuildKit's
`provenance: true` doesn't write those tags — it writes the
attestations as in-index manifests under the same `subject` tag,
which is exactly the `unknown/unknown` entry GHCR shows.

Both verifier tools return `no matching attestations` against
this build, even though the attestations are real and readable
via the buildx path above. To get `cosign verify-attestation`
to work would require running `cosign attest --predicate <file>
--type slsaprovenance ...` as a separate step in `release.yml`,
which means writing the BuildKit attestations + re-emitting them
via cosign. That's a meaningful pipeline change for v0.5+
(tracked in [`../governance/roadmap.md`](../governance/roadmap.md)).

For v0.1, the verification posture is: **use `docker buildx
imagetools inspect` for BuildKit-format attestations; the
attestations are signed by the GHCR registry's OIDC identity
chain**. This is the same trust model — different verifier tool.

### The PyPI wheel

The PyPI trusted-publisher upload through `pypa/gh-action-pypi-publish`
attaches PEP 740 sigstore attestations server-side; verification:

```bash
# Download the wheel without installing.
pip download --no-deps sange==0.1.0.post1 --dest /tmp/sange-verify

# Install sigstore CLI if needed: pip install sigstore
# Verify the bundled attestation against the trusted-publisher
# identity that uploaded the wheel.
sigstore verify identity /tmp/sange-verify/sange-0.1.0.post1-py3-none-any.whl \
    --cert-identity-regexp \
        'https://github.com/simsange/sange/.github/workflows/release.yml@refs/tags/v.*' \
    --cert-oidc-issuer 'https://token.actions.githubusercontent.com'
```

The wheel + sigstore-bundle pair lives at
<https://pypi.org/project/sange/0.1.0.post1/#sange-0.1.0.post1-py3-none-any.whl>.
If `sigstore verify identity` succeeds, you've cryptographically
confirmed the artifact was uploaded by the `release.yml`
workflow on a tag matching `v*`, not by anyone holding a
stolen PyPI password. (PyPI's trusted-publisher model
deliberately precludes password-based uploads for projects with
a configured publisher.)

## Why GHCR shows `unknown/unknown`

When you browse <https://github.com/orgs/simsange/packages/container/sange>
you'll see three entries under **OS / Arch**:

| Entry | What it is |
| :--- | :--- |
| `linux/amd64` | The runnable x86-64 image. `docker pull` on Intel/AMD picks this. |
| `linux/arm64` | The runnable arm64 image. `docker pull` on Apple Silicon / Graviton / ARM cloud hosts picks this. |
| `unknown/unknown` | **The SLSA provenance attestation + CycloneDX SBOM**. Not a misconfigured platform — this is the OCI manifest carrying the attestations, referencing the two platform manifests as its `subject`. |

The `unknown/unknown` label comes from the OCI spec: attestation
manifests aren't platform-specific (they're metadata *about* the
platform images), so they declare `platform: { architecture:
"unknown", os: "unknown" }`. The GHCR UI lists every manifest in
the index without special-casing attestations; Docker Hub's
recently-updated UI hides them.

It is **the artifact that makes `cosign verify-attestation` work**.
Dropping it (by setting `provenance: false` + `sbom: false` in
`release.yml`) would clean up the UI at the cost of every supply-
chain claim documented in this file.

The modern alternative — OCI 1.1 referrers attached as separate
tags via `cosign attest` rather than as in-index manifests —
requires a meaningful rewrite of the build pipeline and breaks the
single-tag `cosign verify-attestation <image>` syntax for
consumers. Not worth the trade for the GHCR cosmetic.

If GHCR's UI is the only complaint, the answer is **wait** —
their UI will catch up with attestation-manifest detection
(Docker Hub did in 2024).

## The SBOM

The CycloneDX SBOM attached to each release records:

- Every Python wheel in the final image (`sange` + dependencies).
- Every OS-level package in the `python:3.12-slim` base layer.
- The build environment (Python version, base image digest).
- Source provenance back to this repo's commit SHA.

To scan the SBOM against a vulnerability database:

```bash
# Pull the SBOM (see above), then:
syft attest ghcr.io/simsange/sange:v0.1.0 \
    | grype --add-cpes-if-none --fail-on high
```

This is the recommended pattern for downstream consumers who want
to block deployment on a CVE threshold. The SBOM is a static
artifact attached to the image; it doesn't change after release.

## What's planned

The v0.1 supply-chain posture covers the Sange-shipped artifacts.
The broader release-engineering vision (`sange release bundle` to
6 destinations) lands in v0.5+ and v1.0+ per
[`../governance/roadmap.md`](../governance/roadmap.md):

| Capability | Target | Description |
| :--- | :--- | :--- |
| `sange release` CLI | v0.5+ | Tag + changelog + bundle in one verb, semver-aware, with rollback for channels that support it. |
| `templates/MANIFEST.toml.sig` | v0.5+ | The kit manifest gets cosign-signed in CI; `sange scaffold` refuses to materialize a kit fragment when the signature fails. See [`tools/generators/kit_manifest.py`](../../tools/generators/kit_manifest.py) for the cosign-verification regex pattern. |
| 6-destination bundling | v1.0 | The same SLSA + sigstore + SBOM posture, applied to GitHub Releases / GitLab Releases / OCI artifact registries / S3 / generic registries / filesystem (air-gapped). |
| Reproducible-build attestation | v1.0 | Per-arch reproducibility proof. ADR-033 commits to this; the verification harness lands with the release engine. |
| SLSA Level 4 | v2.0+ candidate | Requires hermetic builds + two-party review on every release-pipeline change. Sange targets L3 for v1.0 GA; L4 if customer demand materializes. |
| OpenSSF Scorecard ≥ 8.0 | v1.0 exit-criteria | Already public at the scorecard badge in the root [`README.md`](../../README.md); the exit-criteria pin is "stable score ≥ 8.0". |

## What this posture does NOT cover

Honest about the boundary:

- **Source-code integrity before the tag push.** Sange uses tag
  protection on `v*` patterns (per `docs/release.md::Repo
  settings`); a compromised maintainer with admin access can still
  cut a release. The OIDC identity-regex in the verification
  commands constrains *which workflow* can produce a release, but
  not who can push the tag.
- **Dependency compromise.** If `pydantic` itself ships a malicious
  release, the SBOM correctly records the version but doesn't
  block deployment. The SBOM is a tool for *detection* (post-hoc
  vulnerability scanning); blocking is downstream policy.
- **Build-environment compromise.** GitHub-hosted runners are
  trusted as the build environment. A GitHub-side compromise (or
  a supply-chain attack on a GitHub Action we use) breaks the
  provenance claim. Dependabot keeps action versions current; the
  `Verification before pinning` discipline in CLAUDE.md keeps
  pinned SHAs honest.
- **Post-release artifact mutation.** The provenance attestation
  proves the artifact *was* built by this workflow; it doesn't
  prove the artifact you're holding hasn't been swapped after
  upload. The signature check addresses that — but only if you
  actually run it.

## Operator playbook

For maintainers cutting a release, the supply-chain checklist
lives in [`../release.md::Step 0 — Pre-flight checklist`](../release.md#step-0--pre-flight-checklist).
The relevant rows:

- PyPI trusted-publisher record is **active** (not pending) →
  proves the sigstore-OIDC chain works for the PyPI side.
- GHCR write access → proves the image-side OIDC works.
- Verify post-release that `cosign verify` + `cosign
  verify-attestation` both succeed against the freshly pushed
  image before announcing the release.

The verification is fast (~3 seconds per command); make it part
of the release announcement template.

## Cross-references

- [`../release.md`](../release.md) — operator-facing release recipe;
  the supply-chain steps are interleaved with the publication steps.
- [`stride.md`](stride.md) — STRIDE threat model; the
  "Tampering" + "Repudiation" columns map to this file's claims.
- [`prompt-injection.md`](prompt-injection.md) — the
  redaction-layer companion file; the audit-chain mentioned there
  is a different integrity surface (commit-lifecycle records, not
  release artifacts).
- [`../adr/0033-multi-arch-docker.md`](../adr/0033-multi-arch-docker.md)
  — multi-arch + SLSA 3 commitments per arch.
- [`../governance/roadmap.md`](../governance/roadmap.md) — v0.5
  and v1.0 supply-chain milestones.
- [Sigstore docs](https://docs.sigstore.dev/) — `cosign`,
  `sigstore-python`, the OIDC trust model.
- [SLSA spec](https://slsa.dev/) — the levels + the
  build-provenance schema.
- [CycloneDX spec](https://cyclonedx.org/) — the SBOM format
  attached to every release.
