"""Proposals: what synthesis is allowed to ask for, and what it costs to say yes.

Everything here exists to keep §8 Rule 1 true — the agent reads untrusted
transcript text, so it must never be able to express "run this command".
A proposal names a package on a registry; commands are rendered from templates
by `render_command`, and the risk tier is **re-derived here**, never taken from
what the proposal claims about itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

SCHEMA_VERSION = 1


class Risk:
    NONE = "none"      # writes a file inside this repo
    LOW = "low"        # touches ~/.claude config or skills
    MEDIUM = "medium"  # installs from an allowlisted registry
    HIGH = "high"      # never automated; printed as instructions


_ORDER = {Risk.NONE: 0, Risk.LOW: 1, Risk.MEDIUM: 2, Risk.HIGH: 3}

KINDS = frozenset({"skill", "mcp_server", "package", "repo_clone", "config_edit", "manual"})

# Only these can ever produce an executed command.
ALLOWED_MANAGERS = {
    "npm": ("npm", "install", "-g", "{name}"),
    "pip": ("pip", "install", "{name}"),
    "pipx": ("pipx", "install", "{name}"),
    "uv": ("uv", "tool", "install", "{name}"),
}
ALLOWED_CLONE_HOSTS = frozenset({"github.com"})

# Deliberately strict. A name that cannot match this is not a package name.
PACKAGE_NAME = re.compile(r"^(?!-)[A-Za-z0-9._@/-]{1,120}$")
REPO_SLUG = re.compile(r"^[A-Za-z0-9._-]{1,80}/[A-Za-z0-9._-]{1,100}$")
SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")
_SHELL_METACHARS = re.compile(r"[;&|`$><\n\r\\'\"(){}\[\]*?!#~]")


class ProposalError(ValueError):
    """A proposal that cannot be made safe. Rejected, never repaired."""


@dataclass(frozen=True)
class Evidence:
    quote: str = ""
    timestamp: str | None = None


@dataclass(frozen=True)
class Proposal:
    id: str
    kind: str
    title: str
    rationale: str
    risk: str                      # derived here; never trusted from input
    action: dict[str, Any] = field(default_factory=dict)
    evidence: Evidence | None = None
    already_have: str | None = None
    requires_secret: tuple[str, ...] = ()
    reversible: bool = True
    undo: str | None = None
    rejected_reason: str | None = None

    @property
    def automatable(self) -> bool:
        return self.risk != Risk.HIGH and not self.rejected_reason


def _clean(value: Any, *, field_name: str, limit: int = 400) -> str:
    """Reject shell metacharacters outright rather than escaping them.

    Escaping is a losing game against text an attacker controls; refusing the
    input is not.
    """
    text = str(value or "").strip()
    if len(text) > limit:
        raise ProposalError(f"{field_name} exceeds {limit} characters")
    if _SHELL_METACHARS.search(text):
        raise ProposalError(f"{field_name} contains disallowed characters: {text!r}")
    return text



def _looks_like_a_path(name: str) -> bool:
    """Reject package names that are really filesystem paths.

    `npm install -g ../../etc/passwd` and `pip install /tmp/evil` both install
    from a local path. The characters involved are individually legal in real
    package names, so this has to be checked as a shape, not a charset.
    """
    if ".." in name:
        return True
    if name.startswith(("/", ".", "~")):
        return True
    # A scope is the only legitimate slash: "@scope/name".
    slashes = name.count("/")
    if slashes > 1:
        return True
    return slashes == 1 and not name.startswith("@")


def derive_risk(kind: str, action: dict, requires_secret: tuple[str, ...]) -> str:
    """The single place risk is decided. Input never gets a say."""
    if requires_secret:
        return Risk.HIGH  # a secret means a human must be in the loop
    if kind == "manual":
        return Risk.HIGH
    if kind == "skill":
        return Risk.NONE  # D7: written into this repo, activated separately
    if kind in ("mcp_server", "config_edit"):
        return Risk.LOW
    if kind == "package":
        return Risk.MEDIUM if action.get("manager") in ALLOWED_MANAGERS else Risk.HIGH
    if kind == "repo_clone":
        return Risk.MEDIUM if action.get("host") in ALLOWED_CLONE_HOSTS else Risk.HIGH
    return Risk.HIGH


def _validate_action(kind: str, raw: dict) -> dict:
    """Normalise the action into the only shapes the applier understands."""
    if kind == "package":
        manager = _clean(raw.get("manager"), field_name="manager", limit=20).lower()
        name = _clean(raw.get("name"), field_name="package name", limit=120)
        if not PACKAGE_NAME.match(name) or _looks_like_a_path(name):
            raise ProposalError(f"not a valid package name: {name!r}")
        if manager not in ALLOWED_MANAGERS:
            raise ProposalError(f"package manager not allowlisted: {manager!r}")
        return {"manager": manager, "name": name}

    if kind == "repo_clone":
        slug = _clean(raw.get("repo"), field_name="repo", limit=180)
        if not REPO_SLUG.match(slug):
            raise ProposalError(f"not an owner/name repo slug: {slug!r}")
        host = _clean(raw.get("host") or "github.com", field_name="host", limit=60).lower()
        if host not in ALLOWED_CLONE_HOSTS:
            raise ProposalError(f"clone host not allowlisted: {host!r}")
        return {"repo": slug, "host": host}

    if kind == "skill":
        name = _clean(raw.get("name"), field_name="skill name", limit=64).lower()
        if not SKILL_NAME.match(name):
            raise ProposalError(f"not a valid skill name: {name!r}")
        body = str(raw.get("content") or "")
        if not body.strip():
            raise ProposalError(f"skill {name!r} has no content")
        if len(body) > 60_000:
            raise ProposalError(f"skill {name!r} content is implausibly large")
        return {"name": name, "content": body}

    if kind == "mcp_server":
        name = _clean(raw.get("name"), field_name="mcp name", limit=64)
        manager = _clean(raw.get("manager") or "npx", field_name="manager", limit=20)
        package = _clean(raw.get("package"), field_name="mcp package", limit=120)
        if not PACKAGE_NAME.match(package):
            raise ProposalError(f"not a valid package: {package!r}")
        return {"name": name, "manager": manager, "package": package}

    if kind in ("config_edit", "manual"):
        return {"detail": str(raw.get("detail") or "")[:2000]}

    raise ProposalError(f"unknown proposal kind: {kind!r}")


def parse(raw: dict, *, index: int = 0) -> Proposal:
    """Validate one proposal. Raises ProposalError rather than guessing."""
    kind = str(raw.get("kind") or "").strip().lower()
    if kind not in KINDS:
        raise ProposalError(f"unknown proposal kind: {kind!r}")

    secrets = tuple(
        _clean(s, field_name="secret name", limit=80)
        for s in (raw.get("requires_secret") or [])
    )
    action = _validate_action(kind, raw.get("action") or {})
    risk = derive_risk(kind, action, secrets)

    ev = raw.get("evidence") or {}
    evidence = (
        Evidence(quote=str(ev.get("quote") or "")[:600], timestamp=ev.get("timestamp"))
        if ev
        else None
    )

    return Proposal(
        id=str(raw.get("id") or f"p{index + 1}")[:16],
        kind=kind,
        title=str(raw.get("title") or "")[:200],
        rationale=str(raw.get("rationale") or "")[:1200],
        risk=risk,
        action=action,
        evidence=evidence,
        already_have=(str(raw["already_have"])[:120] if raw.get("already_have") else None),
        requires_secret=secrets,
        reversible=bool(raw.get("reversible", True)),
        undo=(str(raw.get("undo"))[:300] if raw.get("undo") else None),
    )


def parse_all(items: list[dict] | None) -> tuple[list[Proposal], list[str]]:
    """Validate a batch. Invalid proposals are dropped and reported, never applied.

    An empty result is a legitimate outcome (I3), not a failure.
    """
    proposals: list[Proposal] = []
    rejected: list[str] = []
    for i, raw in enumerate(items or []):
        try:
            proposals.append(parse(raw, index=i))
        except ProposalError as exc:
            label = str((raw or {}).get("title") or (raw or {}).get("id") or f"#{i + 1}")
            rejected.append(f"{label}: {exc}")
    proposals.sort(key=lambda p: (_ORDER[p.risk], p.title.lower()))
    return proposals, rejected


def render_command(proposal: Proposal) -> list[str] | None:
    """Build the command from a template. The only place a command is created.

    Returns None when nothing should ever be executed for this proposal.
    """
    if not proposal.automatable:
        return None
    if proposal.kind == "package":
        template = ALLOWED_MANAGERS[proposal.action["manager"]]
        return [part.format(name=proposal.action["name"]) for part in template]
    if proposal.kind == "repo_clone":
        host, slug = proposal.action["host"], proposal.action["repo"]
        return ["git", "clone", "--depth", "1", f"https://{host}/{slug}.git"]
    return None
