"""The approval gate: what may be applied, what must be confirmed, what is refused.

Nothing reaches this module without having passed proposal validation, so the
question here is not "is this well-formed" but "should it happen at all".

Two independent inputs decide:

- the **risk tier**, derived from what the action does (`proposals.derive_risk`)
- the **scan verdict**, derived from what the content contains (SkillSpector)

Either one can block. Neither can grant permission on its own — the user does.
"""

from __future__ import annotations

from dataclasses import dataclass

from .proposals import Proposal, Risk, render_command
from .scanner import DO_NOT_INSTALL, SAFE, ScanVerdict

ALLOW = "allow"
CONFIRM = "confirm"
BLOCK = "block"

# Kinds that put agent-readable instructions on disk. These get scanned: once
# installed they steer an agent with shell access, so they are code.
SCANNABLE_KINDS = frozenset({"skill", "repo_clone"})

# A scan verdict may *block* only where applying the proposal puts content in
# front of an agent. Activating a skill does that: the agent reads it and acts
# on it. Cloning into a staging directory does not — nothing executes, and
# staging exists precisely so the thing can be inspected. Blocking the clone
# would prevent the review it is there to enable.
#
# This matters in practice: scanning a full application repo with a scanner
# built for skills scores it CRITICAL off false positives (a .gitignore listing
# credential filenames reads as "credential access"; a video tool shelling out
# to ffmpeg reads as 17 subprocess findings). A gate that blocks on that gets
# switched off, which is worse than one that reports it.
SCAN_CAN_BLOCK = frozenset({"skill"})

# SkillSpector scans directories, files, git URLs and zips — not npm or PyPI
# packages. An MCP server entry points at a registry package, so it cannot be
# scanned. Blocking it would make the feature unusable; pretending it was
# scanned would be worse. It is confirmed with the gap stated plainly.
UNSCANNABLE_KINDS = frozenset({"mcp_server", "package"})


@dataclass(frozen=True)
class Decision:
    proposal: Proposal
    action: str
    reasons: tuple[str, ...] = ()
    scan: ScanVerdict | None = None

    @property
    def blocked(self) -> bool:
        return self.action == BLOCK

    @property
    def command(self) -> list[str] | None:
        return render_command(self.proposal) if not self.blocked else None


def requires_scan(proposal: Proposal) -> bool:
    return proposal.kind in SCANNABLE_KINDS


def decide(
    proposal: Proposal,
    scan: ScanVerdict | None = None,
    *,
    scanner_available: bool = True,
    scan_error: str | None = None,
) -> Decision:
    """Combine risk tier and scan verdict into one decision.

    Ordering matters: every reason to refuse is checked before any reason to
    proceed, so a single blocking signal cannot be outvoted.
    """
    reasons: list[str] = []

    if proposal.rejected_reason:
        return Decision(proposal, BLOCK, (proposal.rejected_reason,), scan)

    if proposal.risk == Risk.HIGH:
        if proposal.requires_secret:
            reasons.append(
                f"needs secrets ({', '.join(proposal.requires_secret)}) — "
                "never handled automatically"
            )
        elif proposal.kind == "manual":
            reasons.append("manual by nature — the command is printed, not run")
        else:
            reasons.append("outside the allowlist")
        return Decision(proposal, BLOCK, tuple(reasons), scan)

    if requires_scan(proposal):
        if scan_error:
            return Decision(
                proposal, BLOCK, (f"scan failed: {scan_error}",), scan
            )
        if scan is None:
            if not scanner_available:
                return Decision(
                    proposal,
                    BLOCK,
                    (
                        "skillspector is not installed and this installs "
                        "agent-readable instructions — refusing to activate unscanned",
                    ),
                    scan,
                )
            return Decision(proposal, BLOCK, ("not scanned yet",), scan)

        if scan.blocks:
            worst = ", ".join(f"{i.severity} {i.id}" for i in scan.worst(3))
            verdict_line = (
                f"scan says {DO_NOT_INSTALL} "
                f"(score {scan.score}/100, {scan.severity}): {worst}"
            )
            if proposal.kind in SCAN_CAN_BLOCK:
                return Decision(proposal, BLOCK, (verdict_line,), scan)
            # Advisory here: this action does not expose an agent to the content.
            reasons.append(verdict_line)
            reasons.append(
                "not blocked because nothing is executed — it is downloaded for "
                "you to inspect; read the findings before using it"
            )

        if scan.degraded:
            # A low score from a scan that could not run semantic analysis is
            # not evidence of safety, and must not read like it.
            reasons.append(
                "semantic analysis was requested but did not run — "
                "static findings only, treat the score as weak evidence"
            )
        elif not scan.llm_ran:
            reasons.append("static-only scan (no semantic analysis)")

        if scan.recommendation != SAFE and not scan.blocks:
            # A blocking verdict has already been stated above; do not repeat it.
            reasons.append(
                f"scan says {scan.recommendation} (score {scan.score}/100)"
            )
        if scan.issues and not scan.blocks:
            reasons.append(
                f"{len(scan.issues)} finding(s): "
                + ", ".join(f"{i.severity} {i.id}" for i in scan.worst(3))
            )

    if proposal.kind in UNSCANNABLE_KINDS:
        reasons.append(
            "cannot be scanned — SkillSpector does not analyse registry "
            "packages; check the package and publisher yourself"
        )
    if proposal.risk == Risk.MEDIUM:
        reasons.append("runs a command on your machine")
    if proposal.already_have:
        reasons.append(f"you may already have this: {proposal.already_have}")

    # Everything that survives still needs a human (D1). Nothing auto-applies.
    return Decision(proposal, CONFIRM, tuple(reasons), scan)


def summarise(decisions: list[Decision]) -> dict:
    return {
        "total": len(decisions),
        "blocked": sum(1 for d in decisions if d.action == BLOCK),
        "needs_confirmation": sum(1 for d in decisions if d.action == CONFIRM),
        "auto_allowed": sum(1 for d in decisions if d.action == ALLOW),
    }
