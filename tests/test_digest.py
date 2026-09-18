"""Digest notes: link a batch of notes and gather their proposals by risk."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from self_learning_agent import cli
from self_learning_agent.config import Config
from self_learning_agent.digest import (
    digest_path,
    leading_blockquote,
    note_link,
    write_digest,
)
from self_learning_agent.ledger import Ledger
from self_learning_agent.models import SourceDocument, TextQuality
from self_learning_agent.synthesis import parse_result
from self_learning_agent.vault import write_note

TODAY = date(2026, 9, 17)

SKILL = {"id": "p1", "kind": "skill", "title": "Add a scan skill",
         "action": {"name": "scan-skill", "content": "# body"}}
CLONE = {"id": "p2", "kind": "repo_clone", "title": "Clone a repo",
         "action": {"repo": "acme/kit"}}
MANUAL = {"id": "p3", "kind": "manual", "title": "Install by hand",
          "action": {"detail": "do it yourself"}}
INVALID = {"id": "p9", "kind": "package", "title": "evil",
           "action": {"manager": "bash", "name": "x"}}


def _cfg(tmp_path):
    return Config(home=tmp_path / "home", vault_path=tmp_path / "vault")


def _process(cfg, source_id, *, title="A video", author="Greg Isenberg",
             thesis="The argument of the video.", proposals=(), status=None):
    """Write a note, stored proposals and a ledger row exactly as `sla note` does."""
    doc = SourceDocument(
        source_type="youtube", source_id=source_id, title=title, text="",
        text_quality=TextQuality.AUTO_CAPTIONS, author=author,
        url=f"https://www.youtube.com/watch?v={source_id}",
        published_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    raw = {"source_id": source_id, "class": "tooling" if proposals else "conceptual",
           "class_confidence": "high", "thesis": thesis, "proposals": list(proposals)}
    path = write_note(doc, parse_result(raw), cfg.vault_path / cfg.vault_subdir)
    store = cfg.home / "proposals"
    store.mkdir(parents=True, exist_ok=True)
    (store / f"{source_id}.json").write_text(json.dumps(
        {"source_id": source_id, "note_path": str(path), "proposals": list(proposals)}))
    Ledger(cfg.ledger_path).record(
        "youtube", source_id, title=title, note_path=str(path),
        status=status or ("pending-review" if proposals else "no-actions"))
    return path


def test_every_note_is_wikilinked_with_class_status_and_thesis(tmp_path):
    cfg = _cfg(tmp_path)
    a = _process(cfg, "aaaaaaaaaaa", title="Repos", thesis="Repos are leverage.",
                 proposals=[SKILL])
    b = _process(cfg, "bbbbbbbbbbb", title="Ideas", thesis="Ideas are cheap.")
    path, missing = write_digest(["aaaaaaaaaaa", "bbbbbbbbbbb"], cfg, today=TODAY)
    text = path.read_text(encoding="utf-8")
    assert f"[[{a.stem}]]" in text and f"[[{b.stem}]]" in text
    assert "> Repos are leverage." in text and "> Ideas are cheap." in text
    assert "tooling · pending-review · 1 proposal(s)" in text
    assert "conceptual · no-actions · 0 proposal(s)" in text
    assert missing == []


def test_sources_without_a_note_are_skipped_and_listed(tmp_path):
    cfg = _cfg(tmp_path)
    _process(cfg, "aaaaaaaaaaa")
    path, missing = write_digest(["aaaaaaaaaaa", "zzzzzzzzzzz"], cfg, today=TODAY)
    assert missing == ["zzzzzzzzzzz"]
    text = path.read_text(encoding="utf-8")
    assert "## Skipped — no note found" in text and "`zzzzzzzzzzz`" in text


def test_a_note_file_deleted_after_processing_counts_as_missing(tmp_path):
    cfg = _cfg(tmp_path)
    _process(cfg, "aaaaaaaaaaa")
    _process(cfg, "bbbbbbbbbbb").unlink()
    _, missing = write_digest(["aaaaaaaaaaa", "bbbbbbbbbbb"], cfg, today=TODAY)
    assert missing == ["bbbbbbbbbbb"]


def test_no_digest_is_written_when_no_source_has_a_note(tmp_path):
    cfg = _cfg(tmp_path)
    with pytest.raises(ValueError, match="none of the given sources"):
        write_digest(["zzzzzzzzzzz"], cfg, today=TODAY)
    assert not (cfg.vault_path / cfg.vault_subdir).exists()


def test_proposals_are_grouped_by_risk_tier_in_order(tmp_path):
    cfg = _cfg(tmp_path)
    a = _process(cfg, "aaaaaaaaaaa", proposals=[MANUAL, SKILL])
    b = _process(cfg, "bbbbbbbbbbb", proposals=[CLONE])
    text = write_digest(["aaaaaaaaaaa", "bbbbbbbbbbb"], cfg, today=TODAY)[0].read_text()
    none_at, medium_at, high_at = (text.index("### none"), text.index("### medium"),
                                   text.index("### high"))
    assert none_at < medium_at < high_at
    assert "### low" not in text                           # empty tiers are omitted
    assert f"- [[{a.stem}]] `p1` Add a scan skill" in text
    assert f"- [[{b.stem}]] `p2` Clone a repo" in text
    assert "3 proposal(s)" in text


def test_stored_proposals_are_revalidated_not_trusted(tmp_path):
    cfg = _cfg(tmp_path)
    _process(cfg, "aaaaaaaaaaa", proposals=[SKILL, INVALID])
    text = write_digest(["aaaaaaaaaaa"], cfg, today=TODAY)[0].read_text()
    assert "evil" not in text
    assert "1 rejected on re-validation" in text


def test_no_proposals_says_so(tmp_path):
    cfg = _cfg(tmp_path)
    _process(cfg, "aaaaaaaaaaa")
    text = write_digest(["aaaaaaaaaaa"], cfg, today=TODAY)[0].read_text()
    assert "No proposals across these notes" in text
    assert "## To review" not in text


def test_sources_with_proposals_get_a_dry_run_command(tmp_path):
    cfg = _cfg(tmp_path)
    _process(cfg, "aaaaaaaaaaa", proposals=[SKILL])
    _process(cfg, "bbbbbbbbbbb")
    text = write_digest(["aaaaaaaaaaa", "bbbbbbbbbbb"], cfg, today=TODAY)[0].read_text()
    assert 'sla apply "aaaaaaaaaaa" --dry-run' in text
    assert 'sla apply "bbbbbbbbbbb"' not in text


def test_status_comes_from_the_ledger_once_apply_has_run(tmp_path):
    """`sla apply` updates the ledger, not the note's frontmatter."""
    cfg = _cfg(tmp_path)
    _process(cfg, "aaaaaaaaaaa", proposals=[SKILL])
    Ledger(cfg.ledger_path).record("youtube", "aaaaaaaaaaa", status="applied")
    text = write_digest(["aaaaaaaaaaa"], cfg, today=TODAY)[0].read_text()
    assert "· applied ·" in text


def test_default_title_is_the_shared_channel_else_a_count(tmp_path):
    cfg = _cfg(tmp_path)
    _process(cfg, "aaaaaaaaaaa", author="Greg Isenberg")
    _process(cfg, "bbbbbbbbbbb", author="Greg Isenberg")
    _process(cfg, "ccccccccccc", author="StarTalk")
    one = write_digest(["aaaaaaaaaaa", "bbbbbbbbbbb"], cfg, today=TODAY)[0]
    mixed = write_digest(["aaaaaaaaaaa", "ccccccccccc"], cfg, today=TODAY)[0]
    assert one.name == "2026-09-17 Digest - Greg Isenberg.md"
    assert mixed.name == "2026-09-17 Digest - 2 sources.md"


def test_an_existing_digest_is_never_overwritten(tmp_path):
    cfg = _cfg(tmp_path)
    _process(cfg, "aaaaaaaaaaa")
    first = write_digest(["aaaaaaaaaaa"], cfg, title="Batch", today=TODAY)[0]
    second = write_digest(["aaaaaaaaaaa"], cfg, title="Batch", today=TODAY)[0]
    assert first.name == "2026-09-17 Digest - Batch.md"
    assert second.name == "2026-09-17 Digest - Batch (2).md"
    assert first.exists() and second.exists()


def test_titles_are_made_filesystem_and_wikilink_safe(tmp_path):
    path = digest_path(tmp_path, 'C#: "agents" / [tools]?', TODAY)
    assert path.name == "2026-09-17 Digest - C agents tools.md"


def test_urls_are_accepted_in_place_of_ids(tmp_path):
    cfg = _cfg(tmp_path)
    _process(cfg, "aaaaaaaaaaa")
    _, missing = write_digest(["https://youtu.be/aaaaaaaaaaa"], cfg, today=TODAY)
    assert missing == []


def test_a_title_that_breaks_wikilinks_gets_a_markdown_link():
    assert note_link(Path("/v/2026-09-01 C# agents (x).md")) == \
        "[2026-09-01 C# agents (x)](<2026-09-01 C# agents (x).md>)"
    assert note_link(Path("/v/plain title.md")) == "[[plain title]]"


def test_a_real_note_title_with_a_hash_links_correctly(tmp_path):
    cfg = _cfg(tmp_path)
    note = _process(cfg, "aaaaaaaaaaa", title="C# for agents")
    text = write_digest(["aaaaaaaaaaa"], cfg, today=TODAY)[0].read_text()
    assert f"(<{note.name}>)" in text and f"[[{note.stem}]]" not in text


def test_leading_blockquote_is_the_thesis_not_later_evidence_quotes():
    text = "---\nk: v\n---\n# T\n\nmeta\n\n> the thesis\n\n## S\n\n> not this\n"
    assert leading_blockquote(text) == "the thesis"
    assert leading_blockquote("---\nk: v\n---\n# T\n\n## S\n> late\n") is None


def test_cli_digest_writes_and_reports_skips(tmp_path, monkeypatch, capsys):
    cfg = _cfg(tmp_path)
    _process(cfg, "aaaaaaaaaaa")
    monkeypatch.setattr(cli.config_mod, "load", lambda: cfg)
    args = cli.build_parser().parse_args(["digest", "aaaaaaaaaaa", "zzzzzzzzzzz", "--title", "T"])
    assert cli.cmd_digest(args) == 0
    out = capsys.readouterr()
    assert "digest written:" in out.out and "Digest - T" in out.out
    assert "skipped zzzzzzzzzzz" in out.err
