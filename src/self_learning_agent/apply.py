"""Carry out approved proposals, and record enough to undo them."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import os

from .config import Config
from .gate import Decision
from .inventory import CLAUDE_HOME
from .proposals import Proposal, render_command

_TIMEOUT = 600


@dataclass(frozen=True)
class AppliedRecord:
    proposal_id: str
    title: str
    ok: bool
    detail: str
    undo: str | None = None
    at: str = ""

    def line(self) -> str:
        mark = "applied" if self.ok else "FAILED"
        undo = f" · undo: `{self.undo}`" if self.undo else ""
        return f"- **{mark}** `{self.proposal_id}` {self.title} — {self.detail}{undo}"


def _is_windows() -> bool:
    """Indirection so tests can vary the platform without touching `os.name`.

    Patching `os.name` globally changes how `pathlib` builds every Path in the
    process, which on Python <=3.12 makes `Path()` raise NotImplementedError
    for the rest of the run — including inside pytest's own error reporting.
    """
    return os.name == "nt"


def _remove_cmd(path: Path, *, windows: bool | None = None) -> str:
    """A delete command the user can actually paste into their own shell."""
    if windows is None:
        windows = _is_windows()
    if windows:
        return f'Remove-Item -Recurse -Force "{path}"'
    return f"rm -rf {path}"


def _restore_cmd(backup: Path, path: Path, *, windows: bool | None = None) -> str:
    if windows is None:
        windows = _is_windows()
    return f'Copy-Item "{backup}" "{path}"' if windows else f"cp {backup} {path}"


def staging_dir(config: Config) -> Path:
    path = config.home / "staging"
    path.mkdir(parents=True, exist_ok=True)
    return path


def stage_skill(proposal: Proposal, repo_root: Path) -> Path:
    """Write a proposed skill into the repo, where it is reviewable in git (D7).

    This is staging, not activation: the file exists and can be diffed, but no
    agent loads it until it is copied into the skills directory.
    """
    name = proposal.action["name"]
    target = Path(repo_root) / "generated-skills" / name
    target.mkdir(parents=True, exist_ok=True)
    skill_file = target / "SKILL.md"
    skill_file.write_text(proposal.action["content"], encoding="utf-8")
    return target


def scan_target(proposal: Proposal, staged: Path | None) -> str | None:
    """What SkillSpector should look at, before anything is activated."""
    if proposal.kind == "skill":
        return str(staged) if staged else None
    if proposal.kind == "repo_clone":
        # Scan the URL, so a blocking verdict lands before anything is cloned.
        return f"https://{proposal.action['host']}/{proposal.action['repo']}"
    return None


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=_TIMEOUT, cwd=cwd
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, (tail[-1] if tail else f"exit {proc.returncode}")
    return True, " ".join(cmd)


def _activate_skill(proposal: Proposal, config: Config, repo_root: Path) -> AppliedRecord:
    name = proposal.action["name"]
    source = Path(repo_root) / "generated-skills" / name
    target = CLAUDE_HOME / "skills" / name
    if target.exists():
        return _record(proposal, False, f"{target} already exists — not overwritten")

    if config.install_mode == "symlink":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source)
        return _record(proposal, True, f"symlinked {target} -> {source}",
                       undo=_remove_cmd(target))

    shutil.copytree(source, target)
    return _record(proposal, True, f"copied to {target}", undo=_remove_cmd(target))


def _clone_repo(proposal: Proposal, config: Config) -> AppliedRecord:
    command = render_command(proposal)
    if command is None:
        return _record(proposal, False, "no command available")
    dest = staging_dir(config) / proposal.action["repo"].split("/")[-1]
    if dest.exists():
        return _record(proposal, False, f"{dest} already exists — not overwritten")
    ok, detail = _run([*command, str(dest)])
    return _record(
        proposal, ok, f"cloned to {dest}" if ok else detail,
        undo=_remove_cmd(dest) if ok else None,
    )


def _install_package(proposal: Proposal) -> AppliedRecord:
    command = render_command(proposal)
    if command is None:
        return _record(proposal, False, "no command available")
    ok, detail = _run(command)
    return _record(proposal, ok, f"ran `{' '.join(command)}`" if ok else detail,
                   undo=proposal.undo)


def _add_mcp_server(proposal: Proposal) -> AppliedRecord:
    path = CLAUDE_HOME / "mcp-configs" / "mcp-servers.json"
    if not path.exists():
        return _record(proposal, False, f"{path} not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    servers = data.setdefault("mcpServers", {})
    name = proposal.action["name"]
    if name in servers:
        return _record(proposal, False, f"MCP server {name!r} already configured")

    backup = path.with_suffix(f".json.bak-{datetime.now(timezone.utc):%Y%m%d%H%M%S}")
    shutil.copy2(path, backup)
    servers[name] = {
        "command": proposal.action["manager"],
        "args": ["-y", proposal.action["package"]],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return _record(proposal, True, f"added MCP server {name!r} (backup: {backup.name})",
                   undo=_restore_cmd(backup, path))


def _record(p: Proposal, ok: bool, detail: str, undo: str | None = None) -> AppliedRecord:
    return AppliedRecord(
        proposal_id=p.id,
        title=p.title,
        ok=ok,
        detail=detail,
        undo=undo,
        at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def apply_decision(
    decision: Decision, config: Config, repo_root: Path
) -> AppliedRecord:
    """Perform one approved action. Blocked decisions are never executed."""
    proposal = decision.proposal
    if decision.blocked:
        return _record(proposal, False, "blocked by the gate — not applied")

    if proposal.kind == "skill":
        return _activate_skill(proposal, config, repo_root)
    if proposal.kind == "repo_clone":
        return _clone_repo(proposal, config)
    if proposal.kind == "package":
        return _install_package(proposal)
    if proposal.kind == "mcp_server":
        return _add_mcp_server(proposal)
    return _record(proposal, False, f"nothing to do for kind {proposal.kind!r}")


def append_to_note(note_path: Path, records: list[AppliedRecord]) -> None:
    """Record what happened in the note, so the vault stays the source of truth."""
    if not records or not note_path.exists():
        return
    text = note_path.read_text(encoding="utf-8")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    block = "\n".join([f"### {stamp}", ""] + [r.line() for r in records] + [""])
    if "_Nothing applied yet._" in text:
        text = text.replace("_Nothing applied yet._", block)
    else:
        text = text.rstrip() + "\n\n" + block
    note_path.write_text(text, encoding="utf-8")
