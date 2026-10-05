"""What is actually installed here, and where it disagrees with itself.

A two-part install (CLI plus plugin), an optional scanner with three states, and a
separately-versioned plugin have between them produced four install-shaped
failures, every one of them silent:

- a hand-copied skill that went stale for three weeks and kept teaching a
  superseded procedure (§26)
- a version-gated plugin cache, so a repo edit reached nobody (§28)
- a staged skill written *inside the installed venv*, in no repository, deleted by
  the next upgrade (§28)
- `sla --version` reporting 0.1.0 while 0.2.1 was published and tagged (§29)

None of those were wrong code so much as absent checks (§29). This module is the
check: one command that turns each into a line, and says which ones are skew.

Nothing here writes anything, and no secret value is ever printed — a doctor
report is the thing people paste into bug reports (Rule 4).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config

OK = "ok"
WARN = "warn"
FAIL = "fail"
INFO = "info"

_RANK = {INFO: 0, OK: 0, WARN: 1, FAIL: 2}
_MARK = {OK: "ok  ", WARN: "warn", FAIL: "FAIL", INFO: "--  "}

# The skill this project ships. A copy of it under ~/.claude/skills means a hand
# install, which has no update path (§26).
FIRST_PARTY_SKILL = "learn-from-source"

# ollama runs locally and needs no credential; the rest do.
_KEYLESS_PROVIDERS = frozenset({"ollama"})
_PROVIDER_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "bedrock": "AWS_ACCESS_KEY_ID",
    "azure_openai": "AZURE_OPENAI_API_KEY",
}


@dataclass(frozen=True)
class Check:
    label: str
    value: str
    status: str
    note: str | None = None

    def render(self) -> str:
        line = f"[{_MARK[self.status]}] {self.label:<22} {self.value}"
        return f"{line}\n{'':29}{self.note}" if self.note else line


def worst(checks: list[Check]) -> str:
    """The most severe status present. `info` never escalates anything."""
    return max((c.status for c in checks), key=lambda s: _RANK[s], default=OK) \
        if any(_RANK[c.status] for c in checks) else OK


def _parse_version(text: str) -> tuple[int, ...]:
    parts = []
    for chunk in text.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def installed_plugin_version(claude_home: Path) -> str | None:
    """The newest version in the plugin cache — which is the one that loads.

    Versions accumulate: this machine had 0.1.0, 0.2.0, 0.2.1 and 0.2.2 side by
    side. `claude plugin update` compares versions, so the cache is the truth
    about what the agent will read, not the repo (§28).
    """
    cache = claude_home / "plugins" / "cache"
    if not cache.is_dir():
        return None
    found = []
    for manifest in cache.glob("*/self-learning-agent/*/.claude-plugin/plugin.json"):
        found.append(manifest.parent.parent.name)
    return max(found, key=_parse_version) if found else None


def _ytdlp_version(cfg: Config) -> str | None:
    """Ask the same resolver the fetch path uses — never a second guess at it.

    The first version of this check did `shutil.which("yt-dlp")` and reported
    "not found" on a machine where yt-dlp was installed in the venv and working:
    `discover_ytdlp` falls back to `sys.executable -m yt_dlp`, and to a zipapp,
    neither of which is on PATH. A check that re-derives what it is checking
    will disagree with it, which is §21's lesson about a verdict depending on
    where the thing happens to live.
    """
    from .config import discover_ytdlp

    cmd = list(cfg.ytdlp_cmd)
    if not cmd:
        try:
            cmd = list(discover_ytdlp())
        except RuntimeError:
            return None
    try:
        proc = subprocess.run([*cmd, "--version"], capture_output=True,
                              text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return (proc.stdout.strip() or None) if proc.returncode == 0 else None


def _check_cli(cli_version: str) -> Check:
    if cli_version == "0+unknown":
        return Check("cli version", cli_version, WARN,
                     "not installed — running from a source tree, so this reports nothing "
                     "useful. `uv tool install` or `pip install -e .`")
    return Check("cli version", cli_version, OK)


def _check_plugin(claude_home: Path, cli_version: str) -> Check:
    plugin = installed_plugin_version(claude_home)
    if plugin is None:
        return Check("plugin version", "not installed", INFO,
                     "the CLI works alone; without the plugin there is no "
                     "/learn-from command and no bundled skill")
    if plugin != cli_version and cli_version != "0+unknown":
        return Check("plugin version", plugin, WARN,
                     f"skew: the CLI is {cli_version}. They ship together and share one "
                     "number. Run `claude plugin update self-learning-agent` "
                     "(and `marketplace update` first)")
    return Check("plugin version", plugin, OK)


def _check_hand_copy(claude_home: Path) -> Check:
    live = claude_home / "skills" / FIRST_PARTY_SKILL
    if live.exists():
        return Check("hand-copied skill", str(live), WARN,
                     "a hand copy has no update path and goes stale silently — it kept "
                     "teaching a superseded procedure for three weeks. Delete it and let "
                     "the plugin own this skill")
    return Check("hand-copied skill", "none", OK)


def _check_scanner(scanner: str | None, env: dict[str, str]) -> Check:
    if scanner is None:
        return Check("scanner", "not installed", WARN,
                     "skill proposals will be BLOCKED — `sla apply` refuses to activate "
                     "unscanned agent-readable instructions. repo_clone and package still "
                     "work. Install: uv tool install git+https://github.com/NVIDIA/skillspector.git")
    provider = (env.get("SKILLSPECTOR_PROVIDER") or "").strip().lower()
    if not provider:
        return Check("scanner", scanner, WARN,
                     "static-only: no SKILLSPECTOR_PROVIDER, so a clean scan is weak "
                     "evidence rather than a pass")
    if provider in _KEYLESS_PROVIDERS:
        return Check("scanner", f"{scanner} ({provider})", OK)
    key = _PROVIDER_KEYS.get(provider)
    # Presence only. The value is never read, printed, or recorded (Rule 4).
    if key and not env.get(key):
        return Check("scanner", f"{scanner} ({provider})", WARN,
                     f"static-only: {provider} is selected but {key} is not set")
    return Check("scanner", f"{scanner} ({provider})", OK)


def _check_staged(cfg: Config) -> Check:
    staged = cfg.generated_skills_dir
    parts = {p.lower() for p in staged.parts}
    # §28: resolved from __file__, this became .../lib/python3.x/ on a real
    # install — in no repository, invisible to its owner, and wiped on upgrade.
    if "site-packages" in parts or {"lib", "bin"} & parts and "python" in str(staged).lower():
        return Check("staged skills", str(staged), FAIL,
                     "this is inside an installed environment (site-packages), so the "
                     "reviewable copy D7 promises is invisible and will be deleted by the "
                     "next upgrade. Set generated_skills_path in config.json")
    return Check("staged skills", str(staged), OK)


def _check_vault(cfg: Config) -> Check:
    notes = cfg.vault_path / cfg.vault_subdir
    if notes.is_dir():
        return Check("vault", str(notes), OK)
    existing = next((p for p in [notes, *notes.parents] if p.exists()), None)
    if existing is not None and not os.access(existing, os.W_OK):
        return Check("vault", str(notes), WARN,
                     f"does not exist and {existing} is not writable")
    return Check("vault", str(notes), OK, "does not exist yet; created on the first note")


def _check_harnesses(claude_home: Path, home_dir: Path) -> Check:
    found = []
    if claude_home.is_dir():
        found.append("claude-code")
    # Codex means ~/.codex or the binary. `$HOME/.agents/skills` is deliberately
    # NOT evidence: it is a vendor-neutral path (§31) and it already exists on a
    # machine with no Codex installed, where the first version of this check
    # reported Codex as detected.
    if (home_dir / ".codex").is_dir() or shutil.which("codex"):
        found.append("codex")
    if not found:
        return Check("harness", "none detected", WARN,
                     "notes and triage still work, but the inventory will be empty, and "
                     "the inventory is the step that makes a note specific to you")
    note = None
    if "codex" in found and "claude-code" in found:
        note = "inventory and apply currently target Claude Code only (PLAN §31)"
    elif found == ["codex"]:
        note = ("Codex detected but not yet supported for inventory or apply (PLAN §31) — "
                "notes will not know what you already have installed")
    return Check("harness", ", ".join(found), OK if "claude-code" in found else WARN, note)


def run_checks(
    cfg: Config,
    *,
    claude_home: Path | None = None,
    cli_version: str | None = None,
    scanner: str | None = ...,  # type: ignore[assignment]
    env: dict[str, str] | None = None,
    ytdlp_version: str | None = ...,  # type: ignore[assignment]
    home_dir: Path | None = None,
) -> list[Check]:
    """Every check, in the order a reader should see them.

    The keyword arguments exist so the probes can be injected in tests; each
    defaults to asking the real machine.
    """
    from . import __version__
    from . import scanner as scanner_mod
    from .inventory import CLAUDE_HOME

    claude_home = CLAUDE_HOME if claude_home is None else claude_home
    cli_version = __version__ if cli_version is None else cli_version
    env = dict(os.environ) if env is None else env
    home_dir = Path.home() if home_dir is None else home_dir
    if scanner is ...:
        scanner = scanner_mod.find_scanner()
    if ytdlp_version is ...:
        ytdlp_version = _ytdlp_version(cfg)

    yt = (Check("yt-dlp", ytdlp_version, OK) if ytdlp_version
          else Check("yt-dlp", "not found", FAIL,
                     "nothing can be fetched without it; it is a declared dependency, so "
                     "this usually means a broken install"))

    return [
        _check_cli(cli_version),
        _check_plugin(claude_home, cli_version),
        _check_hand_copy(claude_home),
        yt,
        _check_scanner(scanner, env),
        _check_harnesses(claude_home, home_dir),
        Check("home", str(cfg.home), OK if cfg.home.is_dir() else INFO,
              None if cfg.home.is_dir() else "created on first use"),
        _check_vault(cfg),
        _check_staged(cfg),
        Check("install_mode", cfg.install_mode, OK),
    ]


def report(checks: list[Check]) -> str:
    lines = [c.render() for c in checks]
    summary = {
        OK: "everything checks out",
        WARN: "usable, with the warnings above",
        FAIL: "something is broken — see the FAIL lines",
    }[worst(checks)]
    return "\n".join([*lines, "", summary])
