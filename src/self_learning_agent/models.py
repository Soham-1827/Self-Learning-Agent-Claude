"""Core data types.

All types are frozen: a fetched document is a fact about the world at a moment,
and nothing downstream is permitted to edit it in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


class TextQuality:
    """How much to trust `SourceDocument.text` for exact names."""

    NATIVE = "native"  # authored text (article, README)
    MANUAL_CAPTIONS = "manual_captions"  # human-written captions
    AUTO_CAPTIONS = "auto_captions"  # ASR; prose is fine, proper nouns are not
    NONE = "none"


@dataclass(frozen=True)
class Chapter:
    start: float  # seconds
    title: str

    @property
    def timestamp(self) -> str:
        m, s = divmod(int(self.start), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@dataclass(frozen=True)
class Link:
    """A URL lifted from human-typed text.

    High trust. Under I1 these are the authoritative spelling of entity names,
    because ASR reliably mangles them ("SkillSpector" -> "Skill Specter").
    """

    url: str
    label: str | None = None

    @property
    def is_github_repo(self) -> bool:
        return "github.com/" in self.url.lower()

    @property
    def repo_slug(self) -> str | None:
        """`owner/name` for a GitHub repo URL, else None."""
        if not self.is_github_repo:
            return None
        tail = self.url.lower().split("github.com/", 1)[1].strip("/")
        parts = [p for p in tail.split("/") if p]
        if len(parts) < 2:
            return None
        # Preserve original casing from the raw URL; the repo name is the entity.
        raw = self.url.split("github.com/", 1)[1].strip("/").split("/")
        return f"{raw[0]}/{raw[1]}"


@dataclass(frozen=True)
class TranscriptSegment:
    """A timestamped line, so claims in a note can cite where they came from."""

    start: float
    text: str

    @property
    def timestamp(self) -> str:
        m, s = divmod(int(self.start), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@dataclass(frozen=True)
class SourceDocument:
    """Normalized output of any Source. The only contract synthesis depends on."""

    source_type: str
    source_id: str
    title: str
    text: str
    text_quality: str
    url: str | None = None
    author: str | None = None
    author_id: str | None = None
    published_at: datetime | None = None
    duration_seconds: float | None = None
    description: str | None = None
    chapters: tuple[Chapter, ...] = ()
    links: tuple[Link, ...] = ()
    segments: tuple[TranscriptSegment, ...] = ()
    fetched_at: datetime | None = None
    extra: dict = field(default_factory=dict)

    @property
    def github_links(self) -> tuple[Link, ...]:
        return tuple(link for link in self.links if link.is_github_repo)

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def segment_at(self, seconds: float) -> TranscriptSegment | None:
        """The segment covering `seconds`, for building evidence citations."""
        found = None
        for seg in self.segments:
            if seg.start <= seconds:
                found = seg
            else:
                break
        return found
