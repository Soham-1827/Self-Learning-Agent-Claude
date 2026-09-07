"""Command line entry point: `sla <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from dataclasses import asdict

from . import __version__, config as config_mod
from .cache import Cache
from .inventory import collect as collect_inventory
from .ledger import Ledger
from .synthesis import build_brief, parse_result
from .vault import render, write_note
from .sources import YouTubeSource


def _document_summary(doc) -> dict:
    return {
        "source_id": doc.source_id,
        "title": doc.title,
        "author": doc.author,
        "published": doc.published_at.date().isoformat() if doc.published_at else None,
        "duration_min": round((doc.duration_seconds or 0) / 60, 1),
        "text_quality": doc.text_quality,
        "words": doc.word_count,
        "chapters": [f"{c.timestamp} {c.title}" for c in doc.chapters],
        "links": [
            {"url": link.url, "label": link.label, "repo": link.repo_slug}
            for link in doc.links
        ],
    }


def cmd_fetch(args) -> int:
    cfg = config_mod.load()
    source = YouTubeSource(cfg, Cache(cfg.cache_dir))
    ledger = Ledger(cfg.ledger_path)

    ids = source.resolve(args.ref, limit=args.last)
    if not args.all:
        fresh = ledger.unseen(source.source_type, ids)
        skipped = len(ids) - len(fresh)
        if skipped:
            print(f"skipping {skipped} already-processed source(s)", file=sys.stderr)
        ids = fresh
    if not ids:
        print("nothing new to fetch", file=sys.stderr)
        return 0

    for source_id in ids:
        doc = source.fetch(source_id, refresh=args.refresh)
        if args.json:
            payload = asdict(doc)
            payload["published_at"] = (
                doc.published_at.isoformat() if doc.published_at else None
            )
            payload["fetched_at"] = doc.fetched_at.isoformat() if doc.fetched_at else None
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(_document_summary(doc), ensure_ascii=False, indent=2))
    return 0


def _load_document(cfg, ref: str, refresh: bool = False):
    source = YouTubeSource(cfg, Cache(cfg.cache_dir))
    source_id = source.resolve(ref)[0]
    return source.fetch(source_id, refresh=refresh)


def cmd_brief(args) -> int:
    """Emit everything the agent needs to synthesise. Data only, no instructions."""
    cfg = config_mod.load()
    doc = _load_document(cfg, args.ref)
    brief = build_brief(doc, collect_inventory())
    text = json.dumps(brief, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"brief written: {args.out}  ({len(text):,} bytes)", file=sys.stderr)
    else:
        print(text)
    return 0


def cmd_note(args) -> int:
    """Validate an agent's synthesis JSON and render it into the vault."""
    cfg = config_mod.load()
    raw = json.loads(Path(args.synthesis).read_text(encoding="utf-8"))
    result = parse_result(raw)
    doc = _load_document(cfg, args.ref)
    if result.source_id != doc.source_id:
        raise ValueError(
            f"synthesis is for {result.source_id!r} but ref resolved to {doc.source_id!r}"
        )

    if args.dry_run:
        print(render(doc, result))
        return 0

    vault_dir = cfg.vault_path / cfg.vault_subdir
    path = write_note(doc, result, vault_dir)
    Ledger(cfg.ledger_path).record(
        doc.source_type,
        doc.source_id,
        title=doc.title,
        url=doc.url,
        note_path=str(path),
        status="pending-review" if result.proposals else "no-actions",
    )
    print(f"note written: {path}")
    if result.rejected:
        print(f"rejected {len(result.rejected)} invalid proposal(s):", file=sys.stderr)
        for item in result.rejected:
            print(f"  - {item}", file=sys.stderr)
    return 0


def cmd_inventory(args) -> int:
    inv = collect_inventory()
    if args.against:
        print(f"already installed, possibly covering: {args.against!r}\n")
        for skill, score in inv.similar_skills(args.against, limit=args.limit):
            print(f"  {score:>5}  {skill.name}  ({skill.origin})")
            if skill.description:
                print(f"         {skill.description[:100]}")
        return 0
    print(json.dumps(inv.summary(), indent=2))
    return 0


def cmd_status(args) -> int:
    cfg = config_mod.load()
    rows = Ledger(cfg.ledger_path).all()
    print(f"home        : {cfg.home}")
    print(f"vault       : {cfg.vault_path / cfg.vault_subdir}")
    print(f"install_mode: {cfg.install_mode}")
    print(f"processed   : {len(rows)}")
    for row in rows[:20]:
        print(f"  [{row['status']}] {row['source_id']}  {row['title'] or ''}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sla", description="Self-Learning Agent")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="fetch and cache a source document")
    fetch.add_argument("ref", help="video URL, video id, or @channel handle")
    fetch.add_argument("--last", type=int, default=1, help="videos to take from a channel")
    fetch.add_argument("--refresh", action="store_true", help="bypass the cache")
    fetch.add_argument("--all", action="store_true", help="include already-processed")
    fetch.add_argument("--json", action="store_true", help="emit the full document")
    fetch.set_defaults(func=cmd_fetch)

    brief = sub.add_parser("brief", help="assemble the synthesis input packet")
    brief.add_argument("ref", help="video URL, video id, or @channel handle")
    brief.add_argument("--out", help="write to a file instead of stdout")
    brief.set_defaults(func=cmd_brief)

    note = sub.add_parser("note", help="render validated synthesis into the vault")
    note.add_argument("ref", help="the same reference the brief was built from")
    note.add_argument("--synthesis", required=True, help="path to the agent's JSON")
    note.add_argument("--dry-run", action="store_true", help="print instead of writing")
    note.set_defaults(func=cmd_note)

    inventory = sub.add_parser("inventory", help="what is already installed here")
    inventory.add_argument(
        "--against", help="text to shortlist existing skills against"
    )
    inventory.add_argument("--limit", type=int, default=5)
    inventory.set_defaults(func=cmd_inventory)

    status = sub.add_parser("status", help="show config and processing history")
    status.set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # surfaced, never swallowed
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
