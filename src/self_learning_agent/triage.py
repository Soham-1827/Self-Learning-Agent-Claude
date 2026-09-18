"""Channel triage: decide which videos deserve a full read, from metadata alone.

A channel's latest ten videos can run to several hundred thousand words of
transcript. Reading them all to find the two worth acting on is the expensive
way round. Title, chapters, duration and the description's links usually say
enough to rank them — I1 applied to *selection* rather than to names — so triage
reads only those and leaves every transcript unfetched until the owner picks.

Nothing here writes: not the ledger, not the vault. It lists and suggests.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, replace
from datetime import date
from typing import Protocol

from .sources.youtube import _parse_date, extract_links, parse_chapters

WORDS_PER_MINUTE = 150
LIKELY_TOOLING = "likely tooling"
LIKELY_CONCEPTUAL = "likely conceptual"

# Words that tend to mean "this video demonstrates something you could install".
# Kept narrow on purpose: broad words like "tools" or "workflow" appear in almost
# every AI video title and would make the guess say "tooling" for everything.
_TOOL_KEYWORDS = (
    "github", "repo", "repos", "mcp", "claude code", "cursor", "codex", "cli",
    "open source", "open-source", "install", "skill", "skills", "sdk", "n8n",
    "plugin", "plugins", "api",
)
_KEYWORD_RE = re.compile(
    r"(?<![\w-])(" + "|".join(re.escape(k) for k in _TOOL_KEYWORDS) + r")(?![\w-])",
    re.IGNORECASE,
)
# Descriptions carry sponsor and link boilerplate, so a single hit there means
# little. Titles and chapters are written about this video specifically.
_DESCRIPTION_KEYWORDS_NEEDED = 2

# Errors from one video's metadata that must not sink the rest of the queue.
_PER_VIDEO_ERRORS = (RuntimeError, ValueError, OSError, subprocess.SubprocessError)


class MetadataSource(Protocol):
    source_type: str

    def resolve(self, ref: str, limit: int = 1) -> list[str]: ...

    def metadata(self, source_id: str) -> dict: ...


@dataclass(frozen=True)
class Candidate:
    source_id: str
    title: str
    published: date | None
    duration_seconds: float | None
    chapter_count: int
    github_repos: tuple[str, ...]
    likely_class: str
    signals: tuple[str, ...]
    suggested: bool = False

    @property
    def minutes(self) -> int:
        return round((self.duration_seconds or 0) / 60)

    @property
    def estimated_words(self) -> int:
        return round((self.duration_seconds or 0) / 60 * WORDS_PER_MINUTE)

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.source_id}"


@dataclass(frozen=True)
class QueueResult:
    ref: str
    listed: int
    already_processed: tuple[str, ...]
    candidates: tuple[Candidate, ...]
    failures: tuple[tuple[str, str], ...] = ()

    @property
    def suggested(self) -> tuple[Candidate, ...]:
        return tuple(c for c in self.candidates if c.suggested)

    @property
    def suggested_words(self) -> int:
        return sum(c.estimated_words for c in self.suggested)


def _keywords_in(text: str) -> tuple[str, ...]:
    found = {m.group(1).lower() for m in _KEYWORD_RE.finditer(text or "")}
    return tuple(sorted(found))


def guess_class(
    title: str,
    chapter_titles: tuple[str, ...],
    description: str,
    github_repos: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    """A cheap guess at tooling vs conceptual, with the signals behind it.

    Only ever a guess: synthesis reads the transcript and classifies for real.
    The signals are returned so the owner can see why, and overrule it.
    """
    if github_repos:
        noun = "link" if len(github_repos) == 1 else "links"
        return LIKELY_TOOLING, (f"{len(github_repos)} GitHub repo {noun} in the description",)

    headline = _keywords_in(" ".join((title, *chapter_titles)))
    if headline:
        return LIKELY_TOOLING, (f"tool words in title/chapters: {', '.join(headline)}",)

    in_description = _keywords_in(description)
    if len(in_description) >= _DESCRIPTION_KEYWORDS_NEEDED:
        return LIKELY_TOOLING, (f"tool words in description: {', '.join(in_description)}",)

    return LIKELY_CONCEPTUAL, ("no GitHub links or tool words",)


def candidate_from_meta(source_id: str, meta: dict) -> Candidate:
    description = meta.get("description") or ""
    chapters = parse_chapters(meta.get("chapters"))
    repos = tuple(
        dict.fromkeys(l.repo_slug for l in extract_links(description) if l.repo_slug)
    )
    title = (meta.get("title") or source_id).strip()
    likely, signals = guess_class(
        title, tuple(c.title for c in chapters), description, repos
    )
    published = _parse_date(meta.get("upload_date"))
    return Candidate(
        source_id=source_id,
        title=title,
        published=published.date() if published else None,
        duration_seconds=meta.get("duration"),
        chapter_count=len(chapters),
        github_repos=repos,
        likely_class=likely,
        signals=signals,
    )


def rank(candidates, cap: int) -> tuple[Candidate, ...]:
    """Likely-tooling first, then newest; the first `cap` become suggested picks.

    Tooling leads because it is what turns into approvable setup. The sort is
    stable, so ties keep the channel's own newest-first order.
    """
    if cap < 0:
        raise ValueError("cap cannot be negative")

    def key(c: Candidate):
        undated = c.published is None
        return (
            c.likely_class != LIKELY_TOOLING,
            undated,
            -(c.published.toordinal() if c.published else 0),
        )

    ordered = sorted(candidates, key=key)
    return tuple(replace(c, suggested=i < cap) for i, c in enumerate(ordered))


def build_queue(
    source: MetadataSource,
    ref: str,
    *,
    last: int,
    cap: int,
    processed: frozenset[str] = frozenset(),
) -> QueueResult:
    """List a channel's latest videos, drop processed ones, and rank the rest.

    Reads metadata only. One video whose metadata fails is reported in
    `failures` rather than aborting the whole queue.
    """
    if last < 1:
        raise ValueError("--last must be at least 1")
    if cap < 0:
        raise ValueError("--cap cannot be negative")

    ids = list(dict.fromkeys(source.resolve(ref, limit=last)))
    done = tuple(i for i in ids if i in processed)
    candidates, failures = [], []
    for source_id in ids:
        if source_id in processed:
            continue
        try:
            meta = source.metadata(source_id)
        except _PER_VIDEO_ERRORS as exc:
            failures.append((source_id, str(exc).strip()[:200] or type(exc).__name__))
            continue
        candidates.append(candidate_from_meta(source_id, meta))

    return QueueResult(
        ref=ref,
        listed=len(ids),
        already_processed=done,
        candidates=rank(candidates, cap),
        failures=tuple(failures),
    )


def to_dict(result: QueueResult) -> dict:
    return {
        "ref": result.ref,
        "listed": result.listed,
        "already_processed": list(result.already_processed),
        "failures": [{"source_id": s, "reason": r} for s, r in result.failures],
        "suggested": [c.source_id for c in result.suggested],
        "suggested_words": result.suggested_words,
        "class_is_a_guess": True,
        "candidates": [
            {
                "rank": i,
                "source_id": c.source_id,
                "url": c.url,
                "title": c.title,
                "published": c.published.isoformat() if c.published else None,
                "minutes": c.minutes,
                "chapters": c.chapter_count,
                "github_repos": list(c.github_repos),
                "estimated_words": c.estimated_words,
                "likely_class": c.likely_class,
                "signals": list(c.signals),
                "suggested": c.suggested,
            }
            for i, c in enumerate(result.candidates, start=1)
        ],
    }


def _clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def format_table(result: QueueResult) -> str:
    new = len(result.candidates)
    header = (
        f"{result.ref} — {result.listed} latest video(s): "
        f"{len(result.already_processed)} already processed, {new} new"
        + (f", {len(result.failures)} failed" if result.failures else "")
    )
    lines = [header, ""]

    if not result.candidates:
        lines.append("Nothing new to triage.")
    else:
        lines.append(
            f"{'pick':<4} {'#':>2}  {'id':<11}  {'published':<10} {'min':>4} {'ch':>3} "
            f"{'gh':>3} {'~words':>7}  {'guess':<17}  title"
        )
        for i, c in enumerate(result.candidates, start=1):
            published = c.published.isoformat() if c.published else "—"
            lines.append(
                f"{'✓' if c.suggested else '':<4} {i:>2}  {c.source_id:<11}  {published:<10} "
                f"{c.minutes:>4} {c.chapter_count:>3} {len(c.github_repos):>3} "
                f"{c.estimated_words:>7,}  {c.likely_class:<17}  {_clip(c.title, 52)}"
            )
        lines += ["", "Why each suggested pick:"]
        for i, c in enumerate(result.candidates, start=1):
            if c.suggested:
                lines.append(f"  {i:>2}. {'; '.join(c.signals)}")
        lines += [
            "",
            f"Suggested: {len(result.suggested)} video(s), "
            f"~{result.suggested_words:,} words of transcript.",
            "The class column is a guess from metadata only; synthesis classifies "
            "each video for real.",
        ]

    for source_id, reason in result.failures:
        lines.append(f"failed  {source_id}: {reason}")
    return "\n".join(lines)
