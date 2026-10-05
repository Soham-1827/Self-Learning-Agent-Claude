"""Turn creator videos into vault notes and human-approved setup actions."""

from importlib.metadata import PackageNotFoundError, version as _version

try:
    # Read from installed metadata, so `pyproject.toml` is the only place a
    # Python version is declared. A literal here drifted from it through two
    # releases, and `sla --version` reported 0.1.0 while 0.2.1 was published.
    __version__ = _version("self-learning-agent")
except PackageNotFoundError:  # pragma: no cover - a source tree with no install
    __version__ = "0+unknown"
