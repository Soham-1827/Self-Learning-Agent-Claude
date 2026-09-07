"""Command line entry point: `sla <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from . import __version__, config as config_mod
from .cache import Cache
from .inventory import collect as collect_inventory
from .ledger import Ledger
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
