"""Configuration, with working defaults so the tool runs before it is configured."""

from __future__ import annotations

import os
import shutil
import sys
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_HOME = Path(os.environ.get("SLA_HOME", Path.home() / ".self-learning-agent"))


@dataclass(frozen=True)
class Config:
    home: Path = DEFAULT_HOME
    vault_path: Path = Path.home() / "LearningVault"
    vault_subdir: str = "Sources"
    install_mode: str = "copy"  # D7: "copy" | "symlink"
    ytdlp_cmd: tuple[str, ...] = ()
    # YouTube rate-limits a burst of requests and keeps refusing for a while
    # (§23). Retrying costs a wait; not retrying costs the whole run.
    ytdlp_attempts: int = 3
    ytdlp_backoff_seconds: float = 5.0
    # Where a proposed skill is staged for review before it may activate (D7).
    # None means "work it out" — see `generated_skills_dir`.
    generated_skills_path: Path | None = None

    @property
    def cache_dir(self) -> Path:
        return self.home / "cache"

    @property
    def generated_skills_dir(self) -> Path:
        """Where a proposed skill is written for review before it can activate (D7).

        A source checkout is preferred, because there the staged copy is diffable
        in git, which is the whole point of staging it. An installed copy has no
        repository, so staging belongs under `home` — somewhere the owner can
        actually look at and that survives an upgrade.
        """
        if self.generated_skills_path is not None:
            return self.generated_skills_path
        checkout = _checkout_root()
        return (checkout or self.home) / "generated-skills"

    @property
    def ledger_path(self) -> Path:
        return self.home / "ledger.db"

    @property
    def config_path(self) -> Path:
        return self.home / "config.toml"

    @property
    def json_config_path(self) -> Path:
        """Checked first: needs no TOML parser, so it cannot be silently ignored."""
        return self.home / "config.json"

    def resolved(self) -> "Config":
        """Fill in anything that must be discovered on this machine."""
        return replace(self, ytdlp_cmd=self.ytdlp_cmd or discover_ytdlp())


def _checkout_root() -> Path | None:
    """The repository root when running from a source checkout, else None.

    An editable install leaves this module inside the checkout, so `parents[2]`
    is the repo. A normal install leaves it in site-packages, where `parents[2]`
    is a library directory that the next `uv tool upgrade` deletes — depth alone
    cannot tell those apart, so this asks for evidence of a repository.
    """
    root = Path(__file__).resolve().parents[2]
    if (root / ".git").is_dir() and (root / "pyproject.toml").is_file():
        return root
    return None


def discover_ytdlp() -> tuple[str, ...]:
    """Locate yt-dlp: PATH binary, importable module, or a downloaded zipapp."""
    if override := os.environ.get("SLA_YTDLP"):
        return tuple(override.split())
    if binary := shutil.which("yt-dlp"):
        return (binary,)
    # Probe the interpreter that is actually running, not a hardcoded name.
    # "python3" does not exist on Windows, so hardcoding it hides a yt_dlp that
    # is installed for the very interpreter asking the question.
    probe = subprocess.run(
        [sys.executable, "-c", "import yt_dlp"], capture_output=True, check=False
    )
    if probe.returncode == 0:
        return (sys.executable, "-m", "yt_dlp")
    zipapp = Path.home() / ".local" / "bin" / "yt-dlp.pyz"
    if zipapp.exists():
        return (sys.executable, str(zipapp))
    raise RuntimeError(
        "yt-dlp not found. Install it with `pip install yt-dlp`, or set SLA_YTDLP."
    )


def _read_toml(path: Path) -> dict | None:
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover - interpreter dependent
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return None  # signals "present but unreadable", never "empty"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load(home: Path | None = None) -> Config:
    """Load config.json, else config.toml, else defaults.

    JSON is checked first because it parses with the standard library on every
    supported version. A TOML file that cannot be parsed raises rather than
    falling back to defaults — silently writing notes into the wrong vault is
    worse than failing.
    """
    import json

    cfg = Config(home=home or DEFAULT_HOME)
    data: dict = {}
    if cfg.json_config_path.exists():
        data = json.loads(cfg.json_config_path.read_text(encoding="utf-8"))
    elif cfg.config_path.exists():
        parsed = _read_toml(cfg.config_path)
        if parsed is None:
            raise RuntimeError(
                f"{cfg.config_path} exists but no TOML parser is available on "
                f"Python {sys.version_info.major}.{sys.version_info.minor}. "
                f"Install tomli, or use {cfg.json_config_path.name} instead."
            )
        data = parsed
    if not data:
        return cfg

    return replace(
        cfg,
        vault_path=Path(data.get("vault_path", cfg.vault_path)).expanduser(),
        vault_subdir=data.get("vault_subdir", cfg.vault_subdir),
        install_mode=data.get("install_mode", cfg.install_mode),
        ytdlp_attempts=max(1, int(data.get("ytdlp_attempts", cfg.ytdlp_attempts))),
        ytdlp_backoff_seconds=max(
            0.0, float(data.get("ytdlp_backoff_seconds", cfg.ytdlp_backoff_seconds))
        ),
        generated_skills_path=(
            Path(data["generated_skills_path"]).expanduser()
            if data.get("generated_skills_path")
            else cfg.generated_skills_path
        ),
    )
