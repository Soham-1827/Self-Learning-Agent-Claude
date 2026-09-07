"""The seam between deterministic code and agent judgment.

`build_brief` assembles everything the agent needs to reason about a source.
`parse_result` validates what comes back. The agent never writes files and never
produces a command — it returns JSON, which is validated here and rendered by
`vault`. That is what makes §8 Rule 1 structural rather than aspirational.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .inventory import Inventory
from .models import SourceDocument
from .proposals import Proposal, parse_all

SCHEMA_VERSION = 1

CLASSES = ("tooling", "conceptual", "mixed")
CONFIDENCES = ("high", "medium", "low")


@dataclass(frozen=True)
class ChapterText:
    """A chapter with the transcript that falls inside it.

    Position is how entity reconciliation works (§15): a repo linked in the
    description is matched to the chapter discussing it, rather than to a
    string search of ASR text that renders "SkillSpector" as "Skill Specter".
    """

    title: str
    start: float
    end: float | None
    timestamp: str
    text: str


def chapter_texts(doc: SourceDocument) -> tuple[ChapterText, ...]:
    if not doc.chapters:
        return (
            ChapterText("(no chapters)", 0.0, None, "0:00", doc.text),
        ) if doc.text else ()

    bounds = list(doc.chapters) + [None]
    out = []
    for i, chapter in enumerate(doc.chapters):
        nxt = bounds[i + 1]
        end = nxt.start if nxt is not None else None
        inside = [
            seg.text
            for seg in doc.segments
            if seg.start >= chapter.start and (end is None or seg.start < end)
        ]
        out.append(
            ChapterText(
                title=chapter.title,
                start=chapter.start,
                end=end,
                timestamp=chapter.timestamp,
                text=" ".join(inside),
            )
        )
    return tuple(out)


def build_brief(doc: SourceDocument, inventory: Inventory) -> dict:
    """Everything the agent reasons over, and nothing it must go looking for."""
    candidates = []
    for link in doc.links:
        name = link.repo_slug or link.label or link.url
        short = (link.repo_slug or "").split("/")[-1] or (link.label or "")
        already = inventory.has_skill(short) or None
        mcp = inventory.has_mcp(short) or None
        candidates.append(
            {
                "name": name,
                "url": link.url,
                "label_in_description": link.label,
                "repo_slug": link.repo_slug,
                # Exact matches are authoritative; the shortlist is advisory.
                "already_installed_skill": already.name if already else None,
                "already_installed_mcp": mcp.name if mcp else None,
                "possibly_covered_by": [
                    {"skill": s.name, "score": score, "description": s.description[:180]}
                    for s, score in inventory.similar_skills(
                        f"{link.label or ''} {short}", limit=3
                    )
                ],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "source_id": doc.source_id,
            "source_type": doc.source_type,
            "title": doc.title,
            "author": doc.author,
            "url": doc.url,
            "published": doc.published_at.date().isoformat() if doc.published_at else None,
            "duration_min": round((doc.duration_seconds or 0) / 60, 1),
            "text_quality": doc.text_quality,
            "word_count": doc.word_count,
        },
        # Human-typed and therefore authoritative for names (§15).
        "description": doc.description,
        "authoritative_links": candidates,
        "chapters": [
            {"timestamp": c.timestamp, "title": c.title, "transcript": c.text}
            for c in chapter_texts(doc)
        ],
        "installed": inventory.summary(),
        # The full list, not a fuzzy shortlist. Deduping against what is already
        # owned is the whole point of M2, and keyword overlap is too weak to do
        # it (§16) — so the agent reads the descriptions and judges.
        "installed_skills": [
            {"name": s.name, "description": s.description[:160], "origin": s.origin}
            for s in inventory.skills
        ],
        "installed_mcp_servers": [s.name for s in inventory.mcp_servers],
        "installed_clis": list(inventory.clis),
    }


@dataclass(frozen=True)
class ProjectIdea:
    title: str
    what: str
    why_interesting: str
    stack: str
    first_step: str
    size: str


@dataclass(frozen=True)
class Technique:
    name: str
    what: str
    when: str = ""
    why: str = ""


@dataclass(frozen=True)
class SynthesisResult:
    source_id: str
    source_class: str
    class_confidence: str
    class_reasoning: str = ""
    thesis: str = ""
    tldr: tuple[str, ...] = ()
    techniques: tuple[Technique, ...] = ()
    project_ideas: tuple[ProjectIdea, ...] = ()
    gaps: tuple[str, ...] = ()
    proposals: tuple[Proposal, ...] = ()
    rejected: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


def _strs(values, limit: int = 20) -> tuple[str, ...]:
    return tuple(str(v).strip() for v in (values or [])[:limit] if str(v).strip())


def parse_result(raw: dict) -> SynthesisResult:
    """Validate the agent's JSON. Unknown values are corrected, not trusted."""
    if not isinstance(raw, dict):
        raise ValueError("synthesis result must be a JSON object")
    source_id = str(raw.get("source_id") or "").strip()
    if not source_id:
        raise ValueError("synthesis result is missing source_id")

    source_class = str(raw.get("class") or "").strip().lower()
    if source_class not in CLASSES:
        source_class = "mixed"  # an unrecognised class must not silence a section
    confidence = str(raw.get("class_confidence") or "").strip().lower()
    if confidence not in CONFIDENCES:
        confidence = "low"

    proposals, rejected = parse_all(raw.get("proposals"))

    ideas = tuple(
        ProjectIdea(
            title=str(i.get("title") or "").strip(),
            what=str(i.get("what") or "").strip(),
            why_interesting=str(i.get("why_interesting") or "").strip(),
            stack=str(i.get("stack") or "").strip(),
            first_step=str(i.get("first_step") or "").strip(),
            size=str(i.get("size") or "").strip(),
        )
        for i in (raw.get("project_ideas") or [])[:8]
    )
    # §7.2: an idea missing its actionable parts is padding. Drop it.
    ideas = tuple(i for i in ideas if i.title and i.what and i.first_step)

    techniques = tuple(
        Technique(
            name=str(t.get("name") or "").strip(),
            what=str(t.get("what") or "").strip(),
            when=str(t.get("when") or "").strip(),
            why=str(t.get("why") or "").strip(),
        )
        for t in (raw.get("techniques") or [])[:12]
    )
    techniques = tuple(t for t in techniques if t.name and t.what)

    return SynthesisResult(
        source_id=source_id,
        source_class=source_class,
        class_confidence=confidence,
        class_reasoning=str(raw.get("class_reasoning") or "").strip()[:600],
        thesis=str(raw.get("thesis") or "").strip()[:2000],
        tldr=_strs(raw.get("tldr"), limit=8),
        techniques=techniques,
        project_ideas=ideas,
        gaps=_strs(raw.get("gaps"), limit=12),
        proposals=tuple(proposals),
        rejected=tuple(rejected),
        tags=_strs(raw.get("tags"), limit=10),
    )
