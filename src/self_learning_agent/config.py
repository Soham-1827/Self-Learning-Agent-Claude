"""Configuration, with working defaults so the tool runs before it is configured."""

from __future__ import annotations

import os
import shutil
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


def load(home: Path | None = None) -> Config:
    """Load config.toml if present; otherwise use defaults."""
    cfg = Config(home=home or DEFAULT_HOME)
    if not cfg.config_path.exists():
        return cfg
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover - depends on interpreter
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return cfg  # config present but unreadable here; defaults still work

    data = tomllib.loads(cfg.config_path.read_text(encoding="utf-8"))
    return replace(
        cfg,
        vault_path=Path(data.get("vault_path", cfg.vault_path)).expanduser(),
        vault_subdir=data.get("vault_subdir", cfg.vault_subdir),
        install_mode=data.get("install_mode", cfg.install_mode),
    )
