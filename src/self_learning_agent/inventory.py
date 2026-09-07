"""What is already installed on this machine.

Runs before synthesis so a note can say "you already have this" instead of
proposing 224 things that are present. The value of this step grows with the
size of the setup: the more installed, the more noise it removes.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

CLAUDE_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))

MCP_CONFIG_PATHS = (
    CLAUDE_HOME / "mcp-configs" / "mcp-servers.json",
    CLAUDE_HOME / "settings.json",
    Path.home() / ".claude.json",
)

# CLIs a video is plausibly going to tell you to install.
KNOWN_CLIS = (
    "git", "gh", "node", "npm", "npx", "pnpm", "yarn", "bun", "deno",
    "python3", "pip", "pipx", "uv", "uvx", "docker", "yt-dlp", "ffmpeg",
    "rg", "jq", "curl", "claude", "cargo", "go",
)

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_DEFAULT_IDF = 3.0
_STOPWORDS = frozenset(
    "the a an and or for to of in on with when use used using this that is are be "
    "it its as at by from you your user should also see if not do does".split()
)


@dataclass(frozen=True)
class InstalledSkill:
    name: str
    description: str
    path: Path
    origin: str  # "user" | "plugin" | "project"

    @property
    def keywords(self) -> frozenset[str]:
        return _keywords(f"{self.name} {self.description}")


@dataclass(frozen=True)
class InstalledMcp:
    name: str
    command: str
    source: Path


@dataclass(frozen=True)
class Inventory:
    skills: tuple[InstalledSkill, ...] = ()
    mcp_servers: tuple[InstalledMcp, ...] = ()
    clis: tuple[str, ...] = ()
    errors: tuple[str, ...] = field(default=())

    # -- lookups used by synthesis -------------------------------------

    def has_skill(self, name: str) -> InstalledSkill | None:
        target = _normalize(name)
        for skill in self.skills:
            if _normalize(skill.name) == target:
                return skill
        return None

    def has_mcp(self, name: str) -> InstalledMcp | None:
        target = _normalize(name)
        for server in self.mcp_servers:
            if _normalize(server.name) == target:
                return server
        return None

    def has_cli(self, name: str) -> bool:
        return name.lower() in {c.lower() for c in self.clis}

    def similar_skills(
        self, text: str, *, limit: int = 3, threshold: float = 0.15
    ) -> tuple[tuple[InstalledSkill, float], ...]:
        """Skills that may already cover `text`, best first.

        Catches what exact-name matching misses: a video pitching a tool under a
        different name than the skill already covering it.

        This is a **shortlist, not a verdict.** Keyword overlap cannot tell that
        two descriptions mean the same thing. Its job is to narrow hundreds of
        skills to a handful that synthesis then reads and judges.
        """
        wanted = _keywords(text)
        if not wanted:
            return ()
        weights = self._idf()
        # Rare words carry the signal. Without this, generic vocabulary
        # ("patterns", "writing", "use") floats unrelated skills to the top.
        total = sum(weights.get(w, _DEFAULT_IDF) for w in wanted)
        if not total:
            return ()
        scored = []
        for skill in self.skills:
            have = skill.keywords
            if not have:
                continue
            shared = wanted & have
            if not shared:
                continue
            score = sum(weights.get(w, _DEFAULT_IDF) for w in shared) / total
            if score >= threshold:
                scored.append((skill, round(score, 3)))
        scored.sort(key=lambda pair: (-pair[1], pair[0].name.lower()))
        return tuple(scored[:limit])

    def _idf(self) -> dict[str, float]:
        """Inverse document frequency across installed skill descriptions."""
        cached = self.__dict__.get("_idf_cache")
        if cached is not None:
            return cached
        counts: dict[str, int] = {}
        for skill in self.skills:
            for word in skill.keywords:
                counts[word] = counts.get(word, 0) + 1
        total = max(len(self.skills), 1)
        weights = {
            word: math.log(total / (1 + n)) + 1.0 for word, n in counts.items()
        }
        object.__setattr__(self, "_idf_cache", weights)
        return weights

    def summary(self) -> dict:
        return {
            "skills": len(self.skills),
            "skills_by_origin": {
                origin: sum(1 for s in self.skills if s.origin == origin)
                for origin in sorted({s.origin for s in self.skills})
            },
            "mcp_servers": len(self.mcp_servers),
            "clis": list(self.clis),
            "errors": list(self.errors),
        }


# -- collection --------------------------------------------------------


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _keywords(text: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9][a-z0-9-]{2,}", (text or "").lower())
    return frozenset(w for w in words if w not in _STOPWORDS)


def parse_frontmatter(content: str) -> dict:
    """Minimal YAML frontmatter reader for `key: value` pairs.

    Deliberately not a YAML dependency: skill frontmatter is flat, and a real
    parser would be a new install for two fields.
    """
    match = _FRONTMATTER.search(content)
    if not match:
        return {}
    data = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace() or ":" not in line:
            continue  # nested value; not needed here
        key, _, value = line.partition(":")
        value = value.strip().strip("'\"")
        if value:
            data[key.strip()] = value
    return data



def _find_skill_files(root: Path, max_depth: int = 6) -> list[Path]:
    """Locate SKILL.md files, following symlinked skill directories.

    `Path.rglob` does not descend into symlinked directories, which silently
    hides skills on real setups — 32 of 224 on the machine this was built on.
    `os.walk(followlinks=True)` sees them, at the cost of needing cycle
    protection, since a symlink can point at an ancestor.
    """
    found: list[Path] = []
    visited: set[str] = set()
    root = Path(root)
    base_depth = len(root.parts)

    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        real = os.path.realpath(dirpath)
        if real in visited:
            dirnames[:] = []  # already walked via another path; do not loop
            continue
        visited.add(real)

        if len(Path(dirpath).parts) - base_depth >= max_depth:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        if "SKILL.md" in filenames:
            found.append(Path(dirpath) / "SKILL.md")
    return found


def _read_skill(path: Path, origin: str) -> InstalledSkill | None:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    meta = parse_frontmatter(content)
    name = meta.get("name") or path.parent.name
    return InstalledSkill(
        name=name,
        description=meta.get("description", ""),
        path=path,
        origin=origin,
    )


def collect_skills(
    claude_home: Path | None = None, project_dir: Path | None = None
) -> tuple[list[InstalledSkill], list[str]]:
    home = claude_home or CLAUDE_HOME
    found: dict[str, InstalledSkill] = {}
    errors: list[str] = []

    roots = [(home / "skills", "user"), (home / "plugins", "plugin")]
    if project_dir:
        roots.append((Path(project_dir) / ".claude" / "skills", "project"))

    for root, origin in roots:
        if not root.exists():
            continue
        try:
            paths = sorted(_find_skill_files(root))
        except OSError as exc:
            errors.append(f"{root}: {exc}")
            continue
        for path in paths:
            skill = _read_skill(path, origin)
            if skill is None:
                errors.append(f"unreadable: {path}")
                continue
            # First origin wins: user skills shadow plugin copies.
            found.setdefault(_normalize(skill.name), skill)
    return list(found.values()), errors


def collect_mcp_servers(paths=None) -> tuple[list[InstalledMcp], list[str]]:
    servers: dict[str, InstalledMcp] = {}
    errors: list[str] = []
    for path in paths or MCP_CONFIG_PATHS:
        path = Path(path)
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        entries = data.get("mcpServers") if isinstance(data, dict) else None
        if not isinstance(entries, dict):
            continue
        for name, spec in entries.items():
            if name in servers:
                continue
            command = ""
            if isinstance(spec, dict):
                command = " ".join(
                    [str(spec.get("command", ""))] + [str(a) for a in spec.get("args", [])]
                ).strip()
            servers[name] = InstalledMcp(name=name, command=command, source=path)
    return list(servers.values()), errors


def collect_clis(candidates=KNOWN_CLIS) -> list[str]:
    return [name for name in candidates if shutil.which(name)]


def collect(
    claude_home: Path | None = None, project_dir: Path | None = None
) -> Inventory:
    skills, skill_errors = collect_skills(claude_home, project_dir)
    servers, mcp_errors = collect_mcp_servers()
    return Inventory(
        skills=tuple(sorted(skills, key=lambda s: s.name.lower())),
        mcp_servers=tuple(sorted(servers, key=lambda s: s.name.lower())),
        clis=tuple(collect_clis()),
        errors=tuple(skill_errors + mcp_errors),
    )
