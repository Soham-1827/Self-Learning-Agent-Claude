"""What gets published: the manifests, and the one place a version may live.

Every bug these guard against shipped. `plugin.json` carried `"author"` as a
string for five milestones, so the plugin could never be installed at all; and a
hardcoded `__version__` drifted from `pyproject.toml` through two releases, so
`sla --version` reported 0.1.0 while 0.2.1 was on GitHub.
"""

import json
import re
from pathlib import Path

import pytest

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _repo_root() -> Path | None:
    """The checkout, or None when the tests run against an installed package."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude-plugin" / "plugin.json").is_file():
            return parent
    return None


@pytest.fixture
def root():
    repo = _repo_root()
    if repo is None:
        pytest.skip("not running from a checkout — nothing to check consistency against")
    return repo


def _pyproject_version(root: Path) -> str:
    for line in (root / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    raise AssertionError("pyproject.toml declares no version")


def _manifests(root: Path) -> tuple[dict, dict]:
    plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    return plugin, market


def test_every_declared_version_agrees(root):
    """Three files declare it. A fourth used to, and that is what broke."""
    plugin, market = _manifests(root)
    entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
    assert _pyproject_version(root) == plugin["version"] == entry["version"]


def test_the_version_is_a_plain_semver(root):
    plugin, _ = _manifests(root)
    assert SEMVER.match(plugin["version"]), plugin["version"]
    assert SEMVER.match(_pyproject_version(root))


def test_the_package_declares_no_version_of_its_own(root):
    """`__version__` is read from installed metadata, so pyproject is the source.

    A literal here is a second source of truth and drifted silently twice.
    """
    text = (root / "src" / "self_learning_agent" / "__init__.py").read_text(encoding="utf-8")
    literal = re.search(r'"\d+\.\d+\.\d+"', text)
    assert literal is None, f"a version literal is back: {literal.group()}"


def test_author_is_an_object_not_a_string(root):
    """`claude plugin validate` rejects a string, which made this uninstallable."""
    plugin, market = _manifests(root)
    for manifest in (plugin, *market["plugins"]):
        author = manifest.get("author")
        assert isinstance(author, dict), f"{manifest['name']}: author is {type(author).__name__}"
        assert author.get("name")
    assert isinstance(market.get("owner"), dict) and market["owner"].get("name")


def test_the_marketplace_lists_this_plugin_at_the_repo_root(root):
    plugin, market = _manifests(root)
    entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
    assert entry["source"] == "./"


@pytest.mark.parametrize("key", ["skills", "commands"])
def test_declared_component_paths_exist(root, key):
    """A typo here ships a plugin with no components and no error."""
    plugin, _ = _manifests(root)
    for declared in plugin[key]:
        assert (root / declared).is_dir(), f"{key}: {declared} does not exist"


def test_no_secret_shaped_fields_in_the_published_manifests(root):
    """These two files are public. An email here is published, not configured."""
    for name in ("plugin.json", "marketplace.json"):
        text = (root / ".claude-plugin" / name).read_text(encoding="utf-8")
        assert "@gmail" not in text and "email" not in text.lower(), name
