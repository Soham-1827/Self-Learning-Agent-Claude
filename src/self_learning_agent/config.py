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

    @property
    def cache_dir(self) -> Path:
        return self.home / "cache"

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


def discover_ytdlp() -> tuple[str, ...]:
    """Locate yt-dlp: PATH binary, importable module, or a downloaded zipapp."""
    if override := os.environ.get("SLA_YTDLP"):
        return tuple(override.split())
    if binary := shutil.which("yt-dlp"):
        return (binary,)
    probe = subprocess.run(
        ["python3", "-c", "import yt_dlp"], capture_output=True, check=False
    )
    if probe.returncode == 0:
        return ("python3", "-m", "yt_dlp")
    zipapp = Path.home() / ".local" / "bin" / "yt-dlp.pyz"
    if zipapp.exists():
        return ("python3", str(zipapp))
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
    )
