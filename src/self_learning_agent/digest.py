"""A digest note: one page that links a batch of notes and gathers their proposals.

Written after a channel batch so the owner reviews one page instead of five.
It only reads — the notes, the stored proposals, and the ledger — and writes a
single new file. It never edits a note and never touches the ledger.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import Config
from .inventory import parse_frontmatter
from .ledger import read_rows
from .proposals import Proposal, Risk, parse_all
from .sources.youtube import video_id_from_ref
from .vault import risk_note

_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f#^\[\]]')
# Characters that break an Obsidian [[wikilink]]; such notes get a markdown link.
_WIKILINK_BREAKERS = re.compile(r"[#^\[\]|]")

_TIERS = (
    (Risk.NONE, "none — written into the repo first, activated separately"),
    (Risk.LOW, "low — touches Claude config"),
    (Risk.MEDIUM, "medium — runs an allowlisted command"),
    (Risk.HIGH, "high — manual only, never automated"),
)


@dataclass(frozen=True)
class DigestEntry:
    source_id: str
    note_path: Path
    title: str
    author: str | None
    source_class: str
    status: str
    thesis: str | None
    proposals: tuple[Proposal, ...]
    rejected: int


def note_link(note_path: Path) -> str:
    """An Obsidian link to a note that survives any title.

    Filenames keep characters such as '#' that a [[wikilink]] would read as a
    heading reference, so those notes get a markdown link to the file instead.
    """
    stem = note_path.stem
    if _WIKILINK_BREAKERS.search(stem):
        return f"[{stem}](<{note_path.name}>)"
    return f"[[{stem}]]"


def leading_blockquote(text: str) -> str | None:
    """The note's thesis: the first blockquote before any `## ` section."""
    body = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)
    quoted: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            break
        if line.startswith(">"):
            quoted.append(line.lstrip(">").strip())
        elif quoted:
            break
    joined = " ".join(q for q in quoted if q)
    return joined or None


def _stored(cfg: Config, source_id: str) -> dict | None:
    path = cfg.home / "proposals" / f"{source_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_entry(cfg: Config, source_id: str, ledger_row: dict | None) -> DigestEntry | None:
    stored = _stored(cfg, source_id) or {}
    candidates = [stored.get("note_path"), (ledger_row or {}).get("note_path")]
    note_path = next((Path(p) for p in candidates if p and Path(p).exists()), None)
    if note_path is None:
        return None

    text = note_path.read_text(encoding="utf-8")
    meta = parse_frontmatter(text)
    # Re-validate rather than trusting what an earlier run wrote to disk.
    proposals, rejected = parse_all(stored.get("proposals"))
    return DigestEntry(
        source_id=source_id,
        note_path=note_path,
        title=meta.get("title") or (ledger_row or {}).get("title") or note_path.stem,
        author=meta.get("author") or None,
        source_class=meta.get("class", "unknown"),
        # The ledger is updated by `sla apply`; the note's frontmatter is not.
        status=(ledger_row or {}).get("status") or meta.get("status", "unknown"),
        thesis=leading_blockquote(text),
        proposals=tuple(proposals),
        rejected=len(rejected),
    )


def _default_title(entries: list[DigestEntry]) -> str:
    authors = {e.author for e in entries}
    if len(authors) == 1 and None not in authors:
        return next(iter(authors))
    return f"{len(entries)} sources"


def digest_path(vault_dir: Path, title: str, today: date) -> Path:
    safe = re.sub(r"\s+", " ", _UNSAFE_FILENAME.sub("", title)).strip()[:80].rstrip(". ")
    safe = safe or "Digest"
    base = f"{today.isoformat()} Digest - {safe}"
    path = vault_dir / f"{base}.md"
    n = 2
    while path.exists():  # never overwrite an earlier digest
        path = vault_dir / f"{base} ({n}).md"
        n += 1
    return path


def render_digest(
    entries: list[DigestEntry], missing: list[str], title: str, today: date
) -> str:
    total = sum(len(e.proposals) for e in entries)
    lines = [
        "---",
        "type: digest",
        f"created: {today.isoformat()}",
        "sources: [" + ", ".join(e.source_id for e in entries) + "]",
        "tags: [digest]",
        "---",
        "",
        f"# Digest — {title}",
        "",
        f"{today.isoformat()} · {len(entries)} note(s) · {total} proposal(s)",
        "",
        "## Notes",
        "",
    ]
    for e in entries:
        count = f"{len(e.proposals)} proposal(s)"
        if e.rejected:
            count += f", {e.rejected} rejected on re-validation"
        lines += [f"### {note_link(e.note_path)}", "", f"{e.source_class} · {e.status} · {count}", ""]
        lines += [f"> {e.thesis}" if e.thesis else "_No thesis found in the note._", ""]

    lines += ["## Proposals by risk", ""]
    if total == 0:
        lines += ["No proposals across these notes — nothing to install.", ""]
    for tier, label in _TIERS:
        items = [(e, p) for e in entries for p in e.proposals if p.risk == tier]
        if not items:
            continue
        lines += [f"### {label}", ""]
        lines += [
            f"- {note_link(e.note_path)} `{p.id}` {p.title} — {risk_note(p.kind, p.risk)}"
            for e, p in items
        ]
        lines.append("")

    pending = [e for e in entries if e.proposals]
    if pending:
        lines += [
            "## To review",
            "",
            "Nothing here has been applied. Per source, preview then decide:",
            "",
            "```bash",
            *[f'sla apply "{e.source_id}" --dry-run' for e in pending],
            "```",
            "",
        ]

    if missing:
        lines += ["## Skipped — no note found", ""]
        lines += [f"- `{m}` — run `sla note` for it first" for m in missing]
        lines.append("")
    return "\n".join(lines)


def write_digest(
    refs: list[str],
    cfg: Config,
    *,
    title: str | None = None,
    today: date | None = None,
) -> tuple[Path, list[str]]:
    """Write a digest for the given video ids or URLs. Returns (path, missing ids)."""
    today = today or date.today()
    ids = list(dict.fromkeys(video_id_from_ref(r) or r.strip() for r in refs))
    rows = {r["source_id"]: r for r in read_rows(cfg.ledger_path)}

    entries: list[DigestEntry] = []
    missing: list[str] = []
    for source_id in ids:
        entry = load_entry(cfg, source_id, rows.get(source_id))
        if entry is None:
            missing.append(source_id)
        else:
            entries.append(entry)

    if not entries:
        raise ValueError(
            "none of the given sources has a note yet: " + ", ".join(missing)
        )

    title = title or _default_title(entries)
    vault_dir = cfg.vault_path / cfg.vault_subdir
    vault_dir.mkdir(parents=True, exist_ok=True)
    path = digest_path(vault_dir, title, today)
    path.write_text(render_digest(entries, missing, title, today), encoding="utf-8")
    return path, missing
