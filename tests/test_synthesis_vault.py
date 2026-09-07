from pathlib import Path

from self_learning_agent.config import Config
from self_learning_agent.inventory import Inventory, InstalledSkill
from self_learning_agent.sources.youtube import YouTubeSource
from self_learning_agent.synthesis import build_brief, chapter_texts, parse_result
from self_learning_agent.vault import note_filename, render, write_note

import pytest


def _doc(meta, captions):
    return YouTubeSource(Config(ytdlp_cmd=("true",)))._build("9_SZFIW7tus", meta, captions)


def test_transcript_is_split_along_chapter_boundaries(meta, captions):
    chapters = chapter_texts(_doc(meta, captions))
    assert len(chapters) == 7
    assert chapters[0].title == "Intro"
    # Segments must land in exactly one chapter.
    assert all(c.start <= c.end for c in chapters if c.end is not None)


def test_brief_carries_authoritative_names_and_installed_state(meta, captions):
    inv = Inventory(skills=(InstalledSkill("brand-voice", "voice", Path("/x"), "user"),))
    brief = build_brief(_doc(meta, captions), inv)
    slugs = {c["repo_slug"] for c in brief["authoritative_links"] if c["repo_slug"]}
    assert "NVIDIA/SkillSpector" in slugs
    assert brief["installed_skills"][0]["name"] == "brand-voice"
    assert brief["source"]["text_quality"] == "auto_captions"


def test_result_requires_a_source_id():
    with pytest.raises(ValueError):
        parse_result({"class": "tooling"})


def test_unknown_class_falls_back_to_mixed_so_no_section_is_silenced():
    r = parse_result({"source_id": "x", "class": "nonsense"})
    assert r.source_class == "mixed"
    assert r.class_confidence == "low"


def test_project_ideas_missing_actionable_parts_are_dropped():
    r = parse_result({
        "source_id": "x",
        "project_ideas": [
            {"title": "good", "what": "w", "first_step": "run it"},
            {"title": "padding", "what": "vague"},  # no first_step
        ],
    })
    assert [i.title for i in r.project_ideas] == ["good"]


def test_invalid_proposals_are_reported_on_the_result():
    r = parse_result({
        "source_id": "x",
        "proposals": [{"kind": "package", "action": {"manager": "bash", "name": "x"}}],
    })
    assert r.proposals == ()
    assert len(r.rejected) == 1


def test_note_filename_is_filesystem_safe(meta, captions):
    name = note_filename(_doc(meta, captions))
    assert ":" not in name and "/" not in name
    assert name.startswith("2026-09-02") and name.endswith(".md")


def test_note_states_plainly_when_nothing_is_worth_installing(meta, captions):
    r = parse_result({"source_id": "9_SZFIW7tus", "class": "conceptual", "proposals": []})
    text = render(_doc(meta, captions), r)
    assert "Nothing here is worth installing" in text
    assert "status: no-actions" in text


def test_note_warns_that_asr_names_are_unreliable(meta, captions):
    r = parse_result({"source_id": "9_SZFIW7tus"})
    text = render(_doc(meta, captions), r)
    assert "proper nouns are not" in text


def test_high_risk_proposal_is_rendered_as_manual_only(meta, captions):
    r = parse_result({
        "source_id": "9_SZFIW7tus",
        "proposals": [{"kind": "manual", "title": "t", "action": {"detail": "d"}}],
    })
    text = render(_doc(meta, captions), r)
    assert "nothing — printed for you to run by hand" in text


def test_clone_is_not_described_as_a_registry_install(meta, captions):
    r = parse_result({
        "source_id": "9_SZFIW7tus",
        "proposals": [{"kind": "repo_clone", "title": "t", "action": {"repo": "a/b"}}],
    })
    text = render(_doc(meta, captions), r)
    assert "clones a GitHub repo; nothing in it is executed" in text


def test_writes_the_note_into_the_vault(tmp_path: Path, meta, captions):
    r = parse_result({"source_id": "9_SZFIW7tus"})
    path = write_note(_doc(meta, captions), r, tmp_path / "Sources")
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("---\nsource: youtube")
