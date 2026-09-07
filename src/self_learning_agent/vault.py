"""Render a SynthesisResult into an Obsidian note and write it to the vault."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from .models import SourceDocument
from .proposals import Proposal, render_command
from .synthesis import SynthesisResult

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

_RISK_NOTE = {
    "none": "writes a file in this repo",
    "low": "touches Claude config",
    "medium": "runs an allowlisted command",
    "high": "manual only — never automated",
}
# The tier alone is too coarse to describe honestly: a clone and a registry
# install are both `medium` but are not the same act.
_KIND_NOTE = {
    "skill": "writes a skill file into this repo, activated separately",
    "repo_clone": "clones a GitHub repo; nothing in it is executed",
    "package": "installs from an allowlisted registry",
    "mcp_server": "adds an MCP server entry to Claude config",
    "config_edit": "edits Claude config",
    "manual": "manual only — never automated",
}


def risk_note(kind: str, risk: str) -> str:
    return _KIND_NOTE.get(kind) or _RISK_NOTE.get(risk, "")


def note_filename(doc: SourceDocument) -> str:
    date = doc.published_at.date().isoformat() if doc.published_at else "undated"
    title = _UNSAFE.sub("", doc.title).strip()[:80].rstrip(". ")
    return f"{date} {title} ({doc.source_id}).md"


def _yaml_list(values) -> str:
    return "[" + ", ".join(str(v) for v in values) + "]"


def _frontmatter(doc: SourceDocument, result: SynthesisResult) -> list[str]:
    published = doc.published_at.date().isoformat() if doc.published_at else ""
    return [
        "---",
        f"source: {doc.source_type}",
        f"source_id: {doc.source_id}",
        f"url: {doc.url or ''}",
        f'title: "{doc.title.replace(chr(34), chr(39))}"',
        f"author: {doc.author or ''}",
        f"published: {published}",
        f"processed: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"text_quality: {doc.text_quality}",
        f"class: {result.source_class}",
        f"class_confidence: {result.class_confidence}",
        "status: pending-review" if result.proposals else "status: no-actions",
        f"tags: {_yaml_list(result.tags or ['youtube'])}",
        "---",
        "",
    ]


def _proposal_block(p: Proposal) -> list[str]:
    lines = [f"#### `{p.id}` {p.title}", ""]
    lines.append(f"- **risk:** `{p.risk}` — {risk_note(p.kind, p.risk)}")
    lines.append(f"- **kind:** {p.kind}")
    if p.already_have:
        lines.append(f"- **you already have:** {p.already_have}")
    if p.rationale:
        lines.append(f"- **why:** {p.rationale}")
    if command := render_command(p):
        lines.append(f"- **would run:** `{' '.join(command)}`")
    elif p.risk == "high":
        lines.append("- **would run:** nothing — printed for you to run by hand")
    if p.requires_secret:
        lines.append(f"- **needs secrets:** {', '.join(p.requires_secret)} (never handled here)")
    if p.undo:
        lines.append(f"- **undo:** `{p.undo}`")
    if p.evidence and p.evidence.quote:
        stamp = f" ({p.evidence.timestamp})" if p.evidence.timestamp else ""
        lines.append(f"- **evidence{stamp}:** > {p.evidence.quote}")
    lines.append("")
    return lines


def render(doc: SourceDocument, result: SynthesisResult) -> str:
    lines = _frontmatter(doc, result)
    lines += [f"# {doc.title}", ""]
    if doc.url:
        meta = f"[{doc.author or 'source'}]({doc.url})"
        if doc.duration_seconds:
            meta += f" · {round(doc.duration_seconds / 60)} min"
        meta += f" · classified **{result.source_class}** ({result.class_confidence} confidence)"
        lines += [meta, ""]
    if result.thesis:
        lines += [f"> {result.thesis}", ""]

    if result.tldr:
        lines += ["## TL;DR", ""] + [f"- {item}" for item in result.tldr] + [""]

    if doc.github_links:
        lines += ["## Tools & resources mentioned", ""]
        lines += ["| Tool | Link |", "|---|---|"]
        for link in doc.github_links:
            lines.append(f"| {link.label or link.repo_slug} | {link.url} |")
        lines.append("")

    if result.techniques:
        lines += ["## Techniques & patterns", ""]
        for t in result.techniques:
            lines += [f"### {t.name}", "", t.what, ""]
            if t.when:
                lines += [f"**When:** {t.when}", ""]
            if t.why:
                lines += [f"**Why it works:** {t.why}", ""]

    lines += ["## Proposed actions", ""]
    if result.proposals:
        automatable = [p for p in result.proposals if p.automatable]
        manual = [p for p in result.proposals if not p.automatable]
        lines += [
            f"{len(result.proposals)} proposed "
            f"({len(automatable)} can be applied, {len(manual)} manual only).",
            "",
        ]
        for p in result.proposals:
            lines += _proposal_block(p)
    else:
        # I3: an empty result is correct, not a failure to be padded.
        lines += ["Nothing here is worth installing. No actions proposed.", ""]

    if result.rejected:
        lines += ["### Rejected during validation", ""]
        lines += [f"- {r}" for r in result.rejected] + [""]

    if result.project_ideas:
        lines += ["## Project ideas", ""]
        for idea in result.project_ideas:
            lines += [f"### {idea.title}", "", idea.what, ""]
            if idea.why_interesting:
                lines += [f"**Why it's interesting:** {idea.why_interesting}", ""]
            if idea.stack:
                lines += [f"**Stack:** {idea.stack}", ""]
            if idea.first_step:
                lines += [f"**First step:** `{idea.first_step}`", ""]
            if idea.size:
                lines += [f"**Size:** {idea.size}", ""]

    lines += ["## Gaps & uncertainty", ""]
    if result.gaps:
        lines += [f"- {g}" for g in result.gaps]
    else:
        lines += ["- None recorded."]
    if doc.text_quality == "auto_captions":
        lines += [
            "- Transcript is machine-generated: prose is reliable, **proper nouns are not**. "
            "Names above come from the description where possible.",
        ]
    lines.append("")

    if doc.links:
        lines += ["## Links from description", ""]
        for link in doc.links:
            lines.append(f"- [{link.label or link.url}]({link.url})")
        lines.append("")

    lines += ["## Applied", "", "_Nothing applied yet._", ""]
    return "\n".join(lines)


def write_note(
    doc: SourceDocument, result: SynthesisResult, vault_dir: Path
) -> Path:
    vault_dir = Path(vault_dir)
    vault_dir.mkdir(parents=True, exist_ok=True)
    path = vault_dir / note_filename(doc)
    path.write_text(render(doc, result), encoding="utf-8")
    return path
