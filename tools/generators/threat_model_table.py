"""Generate docs/security/stride.md — the canonical STRIDE threat model.

T-G-012 — emits the full STRIDE-classified threat catalog from a structured
Python data source. Per §11 of `.design/sange-architecture-prompt.md` and
§17 outline item §39 (Threat Model — STRIDE).

STRIDE categories (Microsoft's canonical six):
  * Spoofing — impersonating an identity.
  * Tampering — unauthorized modification.
  * Repudiation — denying actions taken.
  * Information_Disclosure — leaking data the attacker shouldn't see.
  * Denial_of_Service — degrading availability.
  * Elevation_of_Privilege — gaining unauthorized capabilities.

Determinism (ADR-023):
  * Inputs are static module constants.
  * Re-runs are byte-identical for the same clock.
  * Threat IDs are stable per release (changing one is a SemVer-major change).

The catalog is sourced from:
  * The §11 threat table of the architecture prompt (the explicit
    "Concern | Mitigation" rows).
  * Per-section `🔴 Red-Team Pass` blocks throughout the prompt (each pass
    surfaces 4-8 failure modes; the most architecturally-significant ones
    are promoted into this table).
"""

from __future__ import annotations

import datetime as _dt
import enum
import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _lib import markdown  # noqa: E402
from _lib.fingerprint import sha256_text  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)

GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/threat_model_table.py"
OUTPUT_PATH = REPO_ROOT / "docs" / "security" / "stride.md"


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


class Stride(str, enum.Enum):
    SPOOFING = "Spoofing"
    TAMPERING = "Tampering"
    REPUDIATION = "Repudiation"
    INFORMATION_DISCLOSURE = "Information Disclosure"
    DENIAL_OF_SERVICE = "Denial of Service"
    ELEVATION_OF_PRIVILEGE = "Elevation of Privilege"


class Blast(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


STRIDE_ORDER = (
    Stride.SPOOFING,
    Stride.TAMPERING,
    Stride.REPUDIATION,
    Stride.INFORMATION_DISCLOSURE,
    Stride.DENIAL_OF_SERVICE,
    Stride.ELEVATION_OF_PRIVILEGE,
)

BLAST_ORDER = (Blast.CRITICAL, Blast.HIGH, Blast.MEDIUM, Blast.LOW)


@dataclass(frozen=True)
class Threat:
    """A single STRIDE-classified threat.

    Fields:
      * `id`              — `T-NNN`, stable per release (SemVer-major to change).
      * `title`           — short noun-phrase ("Curl-pipe-sh installer compromise").
      * `category`        — one of the six STRIDE categories.
      * `attack_vector`   — how the attacker reaches the target.
      * `blast_radius`    — Critical / High / Medium / Low.
      * `mitigations`     — list of controls Sange ships against this threat.
      * `affected`        — Sange subsystems implicated (`§ anchors`, ADR refs).
      * `references`      — pointers to the prompt's owning section.
    """

    id: str
    title: str
    category: Stride
    attack_vector: str
    blast_radius: Blast
    mitigations: tuple[str, ...]
    affected: tuple[str, ...] = ()
    references: tuple[str, ...] = ()


def _t(
    id_: str,
    title: str,
    *,
    category: Stride,
    attack_vector: str,
    blast: Blast,
    mitigations: Iterable[str],
    affected: Iterable[str] = (),
    references: Iterable[str] = (),
) -> Threat:
    return Threat(
        id=id_,
        title=title,
        category=category,
        attack_vector=attack_vector,
        blast_radius=blast,
        mitigations=tuple(mitigations),
        affected=tuple(affected),
        references=tuple(references),
    )


# --------------------------------------------------------------------------- #
# The threat catalog
# --------------------------------------------------------------------------- #


THREATS: tuple[Threat, ...] = (
    # ===================== Spoofing =====================
    _t(
        "T-001",
        "Curl-pipe-sh installer compromise",
        category=Stride.SPOOFING,
        attack_vector=(
            "Attacker hosts a malicious binary at the installer URL or "
            "MITMs the connection to substitute their own script."
        ),
        blast=Blast.CRITICAL,
        mitigations=(
            "Pinned checksums for every installer artifact",
            "Sigstore signatures verified before execution",
            "Mirror plan with hash-pinned secondary distribution channel",
            "Reproducible builds with SLSA 3 provenance",
            "TLS 1.3 + HSTS on the install host",
        ),
        affected=("§7.1 Installer", "§14.3 v1.0 release engineering"),
        references=("§11", "§7.1"),
    ),
    _t(
        "T-002",
        "Hostile MCP server impersonation",
        category=Stride.SPOOFING,
        attack_vector=(
            "Malicious MCP server poses as a trusted one and feeds the prompt-enhancer "
            "instructions designed to exfiltrate repo content or run arbitrary tools."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "Allowlist of permitted MCP servers per project",
            "Capability prompts before each tool call",
            "Response-shape validation before execution",
            "Revocable per-project; audit-logged",
        ),
        affected=("§6.7 MCP", "§8.2.12 AI Configuration"),
        references=("§11", "§6.7"),
    ),
    _t(
        "T-003",
        "Cloudflare Tunnel token theft",
        category=Stride.SPOOFING,
        attack_vector=(
            "Leaked tunnel token allows an attacker to bind a hostile cloudflared "
            "process to the user's tunnel, intercepting Web UI traffic."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "Tunnel tokens stored in OS keychain only",
            "Rotation supported (and surfaced as a doctor recommendation)",
            "Tunnel bound to a single Sange instance (sange identity check)",
            "Anomalous session detection (impossible travel, new device)",
        ),
        affected=("§8.5.1 Cloudflare Tunnel", "§8.2.11 Secrets"),
        references=("§11", "§8.5.5"),
    ),
    _t(
        "T-004",
        "Web UI passkey/PIN spoofing",
        category=Stride.SPOOFING,
        attack_vector=(
            "Attacker brute-forces the PIN fallback or replays a captured WebAuthn assertion."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "WebAuthn passkey primary (replay-resistant by design)",
            "PIN fallback rate-limited with abuse-lockout",
            "Optional TOTP second factor on PIN",
            "Password alternative uses Argon2id + HIBP k-anonymity check",
        ),
        affected=("§8.3 Web UI Security", "§8.1 Auth stack"),
        references=("§11", "§8.3"),
    ),
    # ===================== Tampering =====================
    _t(
        "T-010",
        "Prompt injection via repo content",
        category=Stride.TAMPERING,
        attack_vector=(
            "Malicious commit messages, file contents, dependency READMEs, "
            "hostile diffs, or compromised MCP-server responses contain "
            "instructions that hijack the LLM's behavior."
        ),
        blast=Blast.CRITICAL,
        mitigations=(
            "Delimiter discipline: untrusted input wrapped in <untrusted_input> blocks",
            "Output validation: response shape enforced before execution",
            "Confirmation gates for any repo-modifying action",
            "Content firewall scans LLM input AND output for known patterns",
            "Defense-in-depth: ≥3 independent controls per the prompt's §5.3 mandate",
        ),
        affected=("§6.7 AI subsystem", "§6.7.1 Prompt enhancer"),
        references=("§11", "§5.3", "§6.7"),
    ),
    _t(
        "T-011",
        "Config tampering (host-side)",
        category=Stride.TAMPERING,
        attack_vector=(
            "Another process on the user's machine writes to `~/.sange/` or "
            "the per-repo `.sange/config.toml`, redirecting AI providers, "
            "secret resolvers, or audit destinations."
        ),
        blast=Blast.MEDIUM,
        mitigations=(
            "`~/.sange/` mode `0700`",
            "Optional signed-config feature for paranoid setups",
            "Doctor warns on permission drift",
        ),
        affected=("§6.3 Config", "§7.1 Doctor"),
        references=("§11",),
    ),
    _t(
        "T-012",
        "Symlink / path traversal in `.sange/` ops",
        category=Stride.TAMPERING,
        attack_vector=(
            "Attacker plants a symlink inside the repo (`.sange/audit` → `/etc/passwd`) "
            "and lets Sange's write helpers follow the link."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "Path canonicalization before every write",
            "Refusal of paths that escape the repo root",
            "Atomic write helpers use `os.replace` semantics, not `open(symlink, 'w')`",
        ),
        affected=("§6.4 `.sange/` folder", "§7.0.6 subprocess streaming"),
        references=("§11",),
    ),
    _t(
        "T-013",
        "Commit-JSON tampering",
        category=Stride.TAMPERING,
        attack_vector=(
            "Attacker (or accidental editor save) modifies a `.sange/commits/NNNN-*.json` "
            "to bypass the §6.8 lifecycle's review gate."
        ),
        blast=Blast.MEDIUM,
        mitigations=(
            "Sidecar integrity hash in `.sange/commits/.audit/`",
            "CAS update on the `status` field",
            "Warning + audit-log entry on hash mismatch",
            "Status transitions are forward-only except via explicit `sange commits reopen`",
        ),
        affected=("§6.8 Commit lifecycle",),
        references=("§11", "§6.8"),
    ),
    _t(
        "T-014",
        "Audit-log tampering",
        category=Stride.TAMPERING,
        attack_vector=(
            "Attacker edits the `.sange/audit/*.jsonl` hash chain or redirects future "
            "writes to `/dev/null` to hide their tracks."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "Append-only files with sha256 hash chain (`prev_hash` link)",
            "`sange audit verify` replays the chain and detects any mismatch",
            "Refusal to write when audit destination is `/dev/null`",
            "Dual-write to per-repo + global audit stores",
            "Optional forward to external SIEM",
        ),
        affected=("§7.0.7 Hash-chained audit",),
        references=("§11", "§7.0.7", "§6.11.6"),
    ),
    _t(
        "T-015",
        "Race conditions on gitignore-swap",
        category=Stride.TAMPERING,
        attack_vector=(
            "Two `sange publish` invocations or a concurrent `git` command corrupt "
            "the dev↔prod gitignore swap."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "File lock + atomic rename for the swap operation",
            "Abort on detected concurrent VCS op",
            "SIGKILL recovery file on disk (replayed by `sange recover`)",
            "Per-§6.5.2 variant matrix: stage-locked operations refuse mismatched variants",
        ),
        affected=("§6.5 Gitignore-swap", "§6.5.2 Variant matrix", "§7.10 `sange recover`"),
        references=("§11", "§6.5"),
    ),
    _t(
        "T-016",
        "Bundle signature substitution",
        category=Stride.TAMPERING,
        attack_vector=(
            "Compromised CI substitutes a malicious binary while keeping the signature file."
        ),
        blast=Blast.CRITICAL,
        mitigations=(
            "Sigstore + cosign signing of every bundle artifact",
            "SLSA 3 provenance attestation",
            "`sange bundle verify-remote <url>` checks signature against canonical key",
            "Bundle channels are monotonic; `stable` cannot regress to `beta`",
        ),
        affected=("§6.9 Release bundling",),
        references=("§11", "§6.9"),
    ),
    _t(
        "T-017",
        "Supply chain dependency compromise",
        category=Stride.TAMPERING,
        attack_vector=(
            "Malicious update to a dependency (pip, composer, npm) lands and Sange "
            "pulls it on the next install."
        ),
        blast=Blast.CRITICAL,
        mitigations=(
            "SLSA 3 builds with reproducible provenance",
            "SBOM per release (CycloneDX)",
            "Dependency pinning in pyproject.toml + composer.json + package.json",
            "`pip-audit`, `composer audit`, `npm audit` in CI",
            "OpenSSF Scorecard ≥ 8.0 target",
        ),
        affected=("§14 release engineering", "§8.4 Web UI ADRs"),
        references=("§11", "§5.2"),
    ),
    _t(
        "T-018",
        "Malicious plugin injection",
        category=Stride.TAMPERING,
        attack_vector=(
            "Third-party plugin runs arbitrary code with Sange's privileges, "
            "or a build-time injection bypasses signature checks."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "Signed plugin manifests (per ADR-020)",
            "Capability declarations reviewed at install",
            "Network/FS access denied-by-default",
            "Sandboxed execution surface for third-party code",
            "Signature check at install AND runtime",
        ),
        affected=("§7.9 Plugin system",),
        references=("§11",),
    ),
    # ===================== Repudiation =====================
    _t(
        "T-020",
        "Operator denies a destructive purge ran",
        category=Stride.REPUDIATION,
        attack_vector=(
            "After a `sange purge execute` rewrites history and force-pushes, the "
            "operator denies it was them (claiming a compromised account or shared terminal)."
        ),
        blast=Blast.MEDIUM,
        mitigations=(
            "Hash-chained audit JSONL records actor, timestamp, typed-phrase verbatim",
            "Per-session nonce in the typed phrase (§7.0.5) — non-replayable",
            "Dual-store audit: per-repo + global mirror under `~/.sange/audit/`",
            "Optional SIEM forward for tamper-evident off-host record",
        ),
        affected=("§6.11 Purge subsystem", "§7.0.5 Typed-phrase gates"),
        references=("§11", "§6.11.6"),
    ),
    _t(
        "T-021",
        "AI-generated commit lacks provenance",
        category=Stride.REPUDIATION,
        attack_vector=(
            "Hard to determine after the fact whether a commit message came from "
            "a human or from the AI subsystem."
        ),
        blast=Blast.LOW,
        mitigations=(
            "Every AI-generated commit JSON records provider, model, prompt_version, "
            "template_id, cost_estimate, token counts",
            "Audit chain entry on every commit lifecycle transition",
            "`sange ai preview` shows the exact prompt that would be sent",
        ),
        affected=("§6.7 AI subsystem", "§6.8 Commit lifecycle"),
        references=("§11", "§6.8.3"),
    ),
    # ===================== Information Disclosure =====================
    _t(
        "T-030",
        "Secret exfiltration via AI provider",
        category=Stride.INFORMATION_DISCLOSURE,
        attack_vector=(
            "Diffs containing secrets, API keys, or PII are sent to an external "
            "AI provider as part of a commit-message generation request."
        ),
        blast=Blast.CRITICAL,
        mitigations=(
            "Redaction layer scrubs diffs before egress (high-entropy strings, "
            "known secret patterns, configurable PII patterns)",
            "Variant-aware AI provider selection: production stages can pin "
            "internal-only providers (Bedrock, Ollama)",
            "`sange ai preview` shows the exact payload before sending",
            "Per-variant provider selection (§6.5.2.8)",
        ),
        affected=("§6.7 AI subsystem", "§6.7.1 Prompt enhancer", "§12 Telemetry"),
        references=("§11", "§6.7"),
    ),
    _t(
        "T-031",
        "Container VCS secret leak",
        category=Stride.INFORMATION_DISCLOSURE,
        attack_vector=(
            "Secrets baked into image layers, leaked via env vars, exposed in "
            "process memory via core dumps, or hijacked from the SSH agent socket."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "BuildKit secrets mounted as tmpfs (never in image layers)",
            "Env vars zeroed-out after startup",
            "`mlock` to prevent swap of secret-bearing memory",
            "`RLIMIT_CORE=0` to disable core dumps",
            "`sange doctor --container` audits the running container",
        ),
        affected=("§6.10 Container VCS Secret Mgmt",),
        references=("§11", "§6.10"),
    ),
    _t(
        "T-032",
        "DNS rebinding against `sange.test`",
        category=Stride.INFORMATION_DISCLOSURE,
        attack_vector=(
            "Attacker controls a domain that resolves first to a public IP, then "
            "(after the user's browser caches CORS) to `127.0.0.1`, allowing "
            "malicious JS to make requests to the local Sange web UI."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "Host-header validation against allowlist (only `sange.test`, `localhost`, "
            "user-configured LAN/remote names)",
            "Same-origin only (CORS disabled by default)",
            "Strict Origin/Referer validation",
        ),
        affected=("§8.3 Web UI security",),
        references=("§11", "§8.3"),
    ),
    _t(
        "T-033",
        "Token theft from web UI credential store",
        category=Stride.INFORMATION_DISCLOSURE,
        attack_vector=(
            "Compromise of `~/.sange/web.db` or the OS keychain entries exposes "
            "VCS access tokens (GitHub PAT, GitLab token, etc.)."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "OS keychain default; database stores metadata + scoped references only",
            "Scoped tokens with minimum-privilege scopes",
            "Rotation reminders surfaced in `sange doctor`",
            "Never logged; redacted in audit chain",
        ),
        affected=("§6.10 Secrets", "§8.2.11 Secrets module"),
        references=("§11", "§6.10"),
    ),
    _t(
        "T-034",
        "IPC tampering",
        category=Stride.INFORMATION_DISCLOSURE,
        attack_vector=(
            "Local malware intercepts unauthenticated JSON-RPC between CLI/UI and "
            "the `sanged` daemon, leaking commit content or secret references."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "HMAC-signed JSON-RPC for local IPC; rotating shared secret in memory only",
            "mTLS for remote daemon access (mandatory in remote mode)",
            "Bind address `127.0.0.1` by default",
            "`sange web remote audit` refuses to start if mTLS missing in remote mode",
        ),
        affected=("§6.1 IPC", "§8.5.5 Remote-mode obligations"),
        references=("§11", "§8.5"),
    ),
    # ===================== Denial of Service =====================
    _t(
        "T-040",
        "Daemon resource exhaustion (local)",
        category=Stride.DENIAL_OF_SERVICE,
        attack_vector=(
            "A loop in user code or a malicious local actor floods the `sanged` "
            "JSON-RPC endpoint with requests."
        ),
        blast=Blast.LOW,
        mitigations=(
            "Per-route, per-IP rate limiting on the daemon",
            "Daemon runs as user (not root); no setuid",
            "Capability dropping post-start",
        ),
        affected=("§6.1 IPC", "§7.0.6 subprocess discipline"),
        references=("§11",),
    ),
    _t(
        "T-041",
        "Audit-log filesystem exhaustion",
        category=Stride.DENIAL_OF_SERVICE,
        attack_vector=(
            "Attacker spams operations to balloon the audit JSONL until disk fills."
        ),
        blast=Blast.LOW,
        mitigations=(
            "Audit log rotation by configurable size/age (default weekly)",
            "Doctor warns on disk-low",
            "Telemetry rolled at 7-day boundary by default",
        ),
        affected=("§7.0.7 audit", "§13 Observability"),
        references=("§11",),
    ),
    # ===================== Elevation of Privilege =====================
    _t(
        "T-050",
        "Daemon privilege escalation",
        category=Stride.ELEVATION_OF_PRIVILEGE,
        attack_vector=(
            "Hostile input to the daemon exploits a vulnerability to escape its "
            "user-level sandbox."
        ),
        blast=Blast.CRITICAL,
        mitigations=(
            "Run as user, no setuid binary anywhere in the install",
            "Capability dropping where applicable (CAP_NET_BIND, etc.)",
            "Strict input validation on every IPC method",
            "Pydantic v2 schema enforcement on every payload",
        ),
        affected=("§6.1 Daemon", "§6.2 Adapter Protocol"),
        references=("§11",),
    ),
    _t(
        "T-051",
        "IPC daemon accidentally exposed on 0.0.0.0",
        category=Stride.ELEVATION_OF_PRIVILEGE,
        attack_vector=(
            "Misconfiguration binds `sanged` to all interfaces, letting any "
            "network peer drive Sange operations."
        ),
        blast=Blast.CRITICAL,
        mitigations=(
            "Bind `127.0.0.1` by default; remote mode requires explicit opt-in + setup wizard",
            "`sange web remote audit` checks bind address before allowing remote mode",
            "HMAC required for local; mTLS required for remote",
        ),
        affected=("§8.5 Remote topologies",),
        references=("§11",),
    ),
    _t(
        "T-052",
        "Tailscale tagged-device escalation",
        category=Stride.ELEVATION_OF_PRIVILEGE,
        attack_vector=(
            "Attacker compromises a low-privileged tagged device in the user's "
            "tailnet and uses it to reach the Sange remote UI."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "ACLs for fine-grained device/user access on Tailscale",
            "MFA mandatory on at least one role in remote mode",
            "IP allowlist optional but recommended even within tailnet",
            "Anomalous-session detection (impossible travel)",
        ),
        affected=("§8.5.2 Tailscale", "§8.5.5 Remote obligations"),
        references=("§11", "§8.5"),
    ),
    _t(
        "T-053",
        "VPS provider control-plane compromise",
        category=Stride.ELEVATION_OF_PRIVILEGE,
        attack_vector=(
            "Hetzner/DigitalOcean/AWS console takeover exposes the VPS hosting Sange's "
            "remote web UI to attacker."
        ),
        blast=Blast.HIGH,
        mitigations=(
            "mTLS mandatory in remote mode (defense beyond provider)",
            "MFA mandatory on the cloud account",
            "Backups stored off-provider (per §6.12 kit recommendation)",
            "Audit log forwarded to external SIEM where possible",
        ),
        affected=("§8.5.4 VPS reverse-proxy",),
        references=("§11",),
    ),
)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _summary_rows() -> list[list[str]]:
    grouped: dict[Stride, int] = defaultdict(int)
    blast_by_cat: dict[Stride, dict[Blast, int]] = defaultdict(lambda: defaultdict(int))
    for threat in THREATS:
        grouped[threat.category] += 1
        blast_by_cat[threat.category][threat.blast_radius] += 1

    rows: list[list[str]] = []
    for cat in STRIDE_ORDER:
        breakdown = blast_by_cat.get(cat, {})
        breakdown_str = " / ".join(
            f"{breakdown.get(b, 0)} {b.value}"
            for b in BLAST_ORDER
            if breakdown.get(b, 0)
        ) or "—"
        rows.append([cat.value, str(grouped.get(cat, 0)), breakdown_str])
    return rows


def _build_body() -> str:
    parts: list[str] = []
    parts.append(markdown.heading(1, "Sange threat model — STRIDE"))
    parts.append(
        "> Generated by `tools/generators/threat_model_table.py` (T-G-012). "
        "Source: §11 of `.design/sange-architecture-prompt.md` + per-section "
        "`🔴 Red-Team Pass` blocks promoted into the canonical catalog. "
        "Stable IDs (T-NNN) per ADR-023; renaming an ID is a SemVer-major change.\n"
    )
    parts.append(
        "**Defense-in-depth invariant** (per §5.3 + §11): every threat carries at "
        "least one mitigation; threats with `blast_radius=Critical` carry ≥3 "
        "independent mitigations. Tests in `tests/unit/test_threat_model.py` "
        "enforce this contract.\n"
    )

    parts.append(markdown.heading(2, "Summary by STRIDE category"))
    parts.append(
        markdown.table(
            ["STRIDE category", "Threat count", "Blast-radius breakdown"],
            _summary_rows(),
            alignments=["left", "right", "left"],
        )
    )
    parts.append("")

    parts.append(markdown.heading(2, "Threat catalog"))
    grouped: dict[Stride, list[Threat]] = defaultdict(list)
    for t in THREATS:
        grouped[t.category].append(t)

    for category in STRIDE_ORDER:
        ts = grouped.get(category, [])
        if not ts:
            continue
        parts.append(markdown.heading(3, f"{category.value} ({len(ts)})"))
        rows = []
        for t in sorted(ts, key=lambda x: (BLAST_ORDER.index(x.blast_radius), x.id)):
            rows.append(
                [
                    t.id,
                    t.title,
                    t.blast_radius.value,
                    f"{len(t.mitigations)} mitigation(s)",
                    ", ".join(t.affected) or "—",
                ]
            )
        parts.append(
            markdown.table(
                ["ID", "Title", "Blast", "Mitigations", "Affected subsystems"],
                rows,
            )
        )
        parts.append("")

    parts.append(markdown.heading(2, "Full threat details"))
    parts.append(
        "Each threat below names its attack vector, blast radius, full mitigation "
        "list, affected subsystems, and prompt-anchor references.\n"
    )
    for t in sorted(THREATS, key=lambda x: (STRIDE_ORDER.index(x.category), BLAST_ORDER.index(x.blast_radius), x.id)):
        parts.append(markdown.heading(3, f"`{t.id}` — {t.title}"))
        parts.append(f"- **Category:** {t.category.value}")
        parts.append(f"- **Blast radius:** {t.blast_radius.value}")
        parts.append(f"- **Attack vector:** {t.attack_vector}")
        parts.append(f"- **Affected:** {', '.join(t.affected) or '—'}")
        parts.append(f"- **References:** {', '.join(t.references) or '—'}")
        parts.append("")
        parts.append("**Mitigations:**")
        parts.append("")
        for m in t.mitigations:
            parts.append(f"  - {m}")
        parts.append("")

    parts.append(markdown.heading(2, "Mitigation index"))
    parts.append(
        "Cross-reference: which threats does each Sange subsystem defend against?\n"
    )
    by_subsystem: dict[str, list[str]] = defaultdict(list)
    for t in THREATS:
        for subsystem in t.affected:
            by_subsystem[subsystem].append(t.id)
    rows = sorted(
        ([subsystem, ", ".join(sorted(ids))] for subsystem, ids in by_subsystem.items()),
        key=lambda r: r[0],
    )
    parts.append(
        markdown.table(
            ["Subsystem / §-anchor", "Defending threats"],
            rows,
        )
    )
    parts.append("")

    parts.append(markdown.heading(2, "How to extend the catalog"))
    parts.append(
        markdown.bullet_list(
            [
                "Add a new threat → append a `_t(...)` literal to `THREATS` in "
                "`tools/generators/threat_model_table.py`. Use the next free `T-NNN` "
                "in the block (Spoofing T-001..T-009, Tampering T-010..T-019, etc.).",
                "Add a new mitigation to an existing threat → edit the threat's "
                "`mitigations` tuple; the test suite enforces ≥1 mitigation.",
                "Add a new STRIDE category — refuse. The six categories are canonical.",
                "Regenerate → `python tools/generators/all.py --only T-G-012 --write`.",
                "Verify integrity → `python tools/generators/verify_generated.py`.",
            ]
        )
    )
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Generator entry-point
# --------------------------------------------------------------------------- #


def _input_sha256() -> str:
    payload = {
        "generator_version": GENERATOR_VERSION,
        "threats": [
            {
                "id": t.id,
                "title": t.title,
                "category": t.category.value,
                "attack_vector": t.attack_vector,
                "blast_radius": t.blast_radius.value,
                "mitigations": list(t.mitigations),
                "affected": list(t.affected),
                "references": list(t.references),
            }
            for t in sorted(THREATS, key=lambda x: x.id)
        ],
    }
    return sha256_text(json.dumps(payload, sort_keys=True))


def run(
    *,
    mode: WriteMode,
    clock: _dt.datetime,
    output_path: Path | None = None,
) -> list[WriteOutcome]:
    """Generator entry-point."""

    target = output_path or OUTPUT_PATH
    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=_input_sha256(),
        manual_edits_allowed=False,
        generated_at=clock,
    )
    body = _build_body()
    return [write_generated_file(target, body, meta, mode=mode)]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        args.write = True
    mode = WriteMode.WRITE if args.write else WriteMode.CHECK

    results = run(mode=mode, clock=_dt.datetime.now(tz=_dt.timezone.utc))
    rc = 0
    for r in results:
        if r.result is not None and r.result.value != "match":
            rc = 66
        line = f"[{mode.value}] {r.path}  sha256={r.output_sha256}"
        if r.result is not None:
            line += f"  ({r.result.value})"
        print(line)
    raise SystemExit(rc)
