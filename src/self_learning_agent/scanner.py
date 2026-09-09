"""SkillSpector integration: scan agent-facing content before it is activated.

A skill is not inert text — it carries instructions and tool access, and once
installed it steers an agent that has shell access. Installing one is running
someone else's code, so it gets scanned first.

Two properties this module is careful about:

1. **A degraded scan is not a clean scan.** If LLM analysis was requested but
   unavailable, a low score means "the static checks found nothing", not "this
   is safe". SkillSpector exposes `llm_requested` / `llm_available` precisely so
   the two cannot be confused, and `ScanVerdict.degraded` carries that forward.
2. **Symlinks are resolved before scanning.** SkillSpector refuses symlinked
   input, and 32 of the skills on the development machine are symlinks.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SAFE = "SAFE"
CAUTION = "CAUTION"
DO_NOT_INSTALL = "DO_NOT_INSTALL"

# Observed with SkillSpector 2.11.1: a static-only scan returns CAUTION even at
# score 0 with zero findings — the documented LOW -> SAFE mapping only applies
# once semantic analysis has run. So CAUTION is the ordinary --no-llm outcome,
# and a gate that treats it as anomalous would block everything.

# Exit 2 is an error; 0 and 1 are both completed scans (see SkillSpector docs).
_ERROR_EXIT = 2
_DEFAULT_TIMEOUT = 900


class ScannerUnavailable(RuntimeError):
    """SkillSpector is not installed. Callers decide whether that blocks."""


@dataclass(frozen=True)
class Issue:
    id: str
    severity: str
    category: str
    message: str
    file: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class ScanVerdict:
    target: str
    score: int
    severity: str
    recommendation: str
    issues: tuple[Issue, ...] = ()
    llm_requested: bool = False
    llm_available: bool = False
    llm_error: str | None = None
    version: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def degraded(self) -> bool:
        """LLM analysis was asked for but did not run.

        Static-only findings are weaker evidence. A low score here must not be
        reported as a clean full scan.
        """
        return self.llm_requested and not self.llm_available

    @property
    def blocks(self) -> bool:
        return self.recommendation == DO_NOT_INSTALL

    @property
    def llm_ran(self) -> bool:
        """Semantic analysis actually executed — not merely that it could have."""
        return self.llm_requested and self.llm_available

    @property
    def scan_mode(self) -> str:
        if self.degraded:
            return "static-only (LLM requested but unavailable)"
        return "static + semantic" if self.llm_ran else "static-only"

    def worst(self, limit: int = 5) -> tuple[Issue, ...]:
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        return tuple(
            sorted(self.issues, key=lambda i: order.get(i.severity.upper(), 9))
        )[:limit]


def find_scanner() -> str | None:
    if override := os.environ.get("SLA_SKILLSPECTOR"):
        return override
    return shutil.which("skillspector")


def available() -> bool:
    return find_scanner() is not None


def _resolve(target: str) -> str:
    """Follow symlinks for local paths; leave URLs untouched.

    SkillSpector refuses symlinked input, and a scan that never ran is far
    worse than one that had to resolve a path first.
    """
    if "://" in target:
        return target
    path = Path(target).expanduser()
    return str(path.resolve()) if path.exists() else target


def _parse(payload: dict, target: str) -> ScanVerdict:
    assessment = payload.get("risk_assessment") or {}
    meta = payload.get("metadata") or {}
    issues = tuple(
        Issue(
            id=str(i.get("id") or ""),
            severity=str(i.get("severity") or "").upper(),
            category=str(i.get("category") or ""),
            message=str(i.get("message") or i.get("explanation") or "")[:400],
            file=(i.get("location") or {}).get("file"),
            line=(i.get("location") or {}).get("start_line"),
        )
        for i in (payload.get("issues") or [])
    )
    return ScanVerdict(
        target=target,
        score=int(assessment.get("score") or 0),
        severity=str(assessment.get("severity") or "UNKNOWN").upper(),
        # Absent recommendation is treated as blocking, never as safe.
        recommendation=str(assessment.get("recommendation") or DO_NOT_INSTALL).upper(),
        issues=issues,
        llm_requested=bool(meta.get("llm_requested")),
        llm_available=bool(meta.get("llm_available")),
        llm_error=meta.get("llm_error"),
        version=meta.get("skillspector_version"),
        raw=payload,
    )


def scan(
    target: str | Path,
    *,
    use_llm: bool = True,
    timeout: int = _DEFAULT_TIMEOUT,
    env: dict | None = None,
) -> ScanVerdict:
    """Scan a directory, file, git URL, or zip. Raises on scanner failure.

    Never returns a permissive verdict for a scan that did not complete — a
    failed scan must not read as a pass.
    """
    binary = find_scanner()
    if binary is None:
        raise ScannerUnavailable(
            "skillspector not found. Install it with "
            "`uv tool install git+https://github.com/NVIDIA/skillspector.git`, "
            "or set SLA_SKILLSPECTOR."
        )

    resolved = _resolve(str(target))
    cmd = [binary, "scan", resolved, "--format", "json"]
    if not use_llm:
        cmd.append("--no-llm")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, **(env or {})},
    )
    if proc.returncode == _ERROR_EXIT or not proc.stdout.strip():
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise RuntimeError(
            "skillspector failed: " + (detail[-1] if detail else "no output")
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"skillspector returned unparseable JSON: {exc}") from exc
    return _parse(payload, resolved)
