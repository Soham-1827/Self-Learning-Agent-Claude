"""SourceDocument is the contract every later phase depends on (I4)."""

import dataclasses

import pytest

from self_learning_agent.models import (
    Link,
    SourceDocument,
    TextQuality,
    TranscriptSegment,
)
from self_learning_agent.sources.youtube import YouTubeSource
from self_learning_agent.config import Config


def _doc(**kw):
    base = dict(
        source_type="youtube",
        source_id="x",
        title="t",
        text="a b c",
        text_quality=TextQuality.AUTO_CAPTIONS,
    )
    base.update(kw)
    return SourceDocument(**base)


def test_document_is_immutable():
    doc = _doc()
    with pytest.raises(dataclasses.FrozenInstanceError):
        doc.title = "changed"


def test_github_links_filters_out_other_urls():
    doc = _doc(
        links=(
            Link("https://github.com/a/b"),
            Link("https://www.ideabrowser.com"),
        )
    )
    assert [l.repo_slug for l in doc.github_links] == ["a/b"]


def test_segment_at_finds_the_covering_segment():
    doc = _doc(
        segments=(
            TranscriptSegment(0, "intro"),
            TranscriptSegment(104, "repo one"),
            TranscriptSegment(320, "repo two"),
        )
    )
    assert doc.segment_at(150).text == "repo one"
    assert doc.segment_at(0).text == "intro"
    assert doc.segment_at(-5) is None


def test_builds_a_full_document_from_fixtures(meta, captions):
    source = YouTubeSource(Config(ytdlp_cmd=("true",)))
    doc = source._build("9_SZFIW7tus", meta, captions)

    assert doc.title == "5 GitHub Repos: Kill AI Slop, Go Viral, Make Money"
    assert doc.author == "Greg Isenberg"
    assert doc.published_at.date().isoformat() == "2026-09-02"
    assert doc.text_quality == TextQuality.AUTO_CAPTIONS
    assert len(doc.chapters) == 7
    assert len(doc.github_links) == 5
    assert doc.word_count > 100


def test_auto_caption_quality_is_recorded_so_synthesis_can_distrust_names(meta, captions):
    source = YouTubeSource(Config(ytdlp_cmd=("true",)))
    doc = source._build("9_SZFIW7tus", meta, captions)
    # The pipeline must know the transcript is ASR, because it renders
    # "SkillSpector" as "Skill Specter" while the description has it right.
    assert doc.text_quality == TextQuality.AUTO_CAPTIONS
    assert "NVIDIA/SkillSpector" in {l.repo_slug for l in doc.github_links}


def test_document_with_no_captions_still_builds(meta):
    source = YouTubeSource(Config(ytdlp_cmd=("true",)))
    doc = source._build("9_SZFIW7tus", meta, {})
    assert doc.text == ""
    assert doc.text_quality == TextQuality.NONE
    assert len(doc.github_links) == 5  # description alone still carries the repos
