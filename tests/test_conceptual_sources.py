"""Conceptual sources: the paths a tooling video never exercises.

Two real videos, chosen because each lacks something the design leans on:

- gPPT4WpVRZ4 (poker strategy): no chapters, no GitHub links, promo links only.
- UpE5yuhwXXc (StarTalk, periodic table): five chapters, no GitHub links.

Captions are sampled across each whole video rather than truncated, so chapter
alignment is exercised end to end. Fixtures load here, not via conftest, which
is shared with other work.
"""

import json
from pathlib import Path

import pytest

from self_learning_agent.config import Config
from self_learning_agent.inventory import Inventory
from self_learning_agent.models import TextQuality
from self_learning_agent.sources.youtube import YouTubeSource
from self_learning_agent.synthesis import build_brief, chapter_texts, parse_result
from self_learning_agent.vault import render

FIXTURES = Path(__file__).parent / "fixtures"
POKER = "gPPT4WpVRZ4"
STARTALK = "UpE5yuhwXXc"
BOTH = (POKER, STARTALK)


def _load(video_id, kind):
    return json.loads((FIXTURES / f"{video_id}.{kind}.json").read_text(encoding="utf-8"))


def _doc(video_id, captions=None):
    source = YouTubeSource(Config(ytdlp_cmd=("true",)))
    caps = _load(video_id, "captions") if captions is None else captions
    return source._build(video_id, _load(video_id, "meta"), caps)


def _conceptual(video_id, **extra):
    return parse_result({"source_id": video_id, "class": "conceptual",
                         "class_confidence": "high", "proposals": [], **extra})


# -- no chapters -------------------------------------------------------


def test_a_source_without_chapters_becomes_one_block_holding_everything():
    doc = _doc(POKER)
    assert doc.chapters == ()

    blocks = chapter_texts(doc)
    assert len(blocks) == 1
    assert blocks[0].title == "(no chapters)"
    assert blocks[0].end is None
    assert blocks[0].text == doc.text != ""


def test_no_chapters_and_no_captions_gives_no_blocks_at_all():
    """Nothing to align is an empty brief section, not a block of empty text."""
    assert chapter_texts(_doc(POKER, captions={})) == ()


def test_the_brief_carries_the_fallback_block_for_the_agent():
    brief = build_brief(_doc(POKER), Inventory())
    assert [c["title"] for c in brief["chapters"]] == ["(no chapters)"]
    assert brief["chapters"][0]["transcript"]


# -- chapter alignment on a real multi-chapter source ------------------


def test_every_startalk_chapter_gets_its_own_transcript():
    doc = _doc(STARTALK)
    blocks = chapter_texts(doc)

    assert [b.title for b in blocks] == [c.title for c in doc.chapters]
    assert len(blocks) == 5
    assert all(b.text.strip() for b in blocks)


def test_chapter_blocks_tile_the_transcript_with_no_gaps_or_overlaps():
    """Each segment lands in exactly one chapter, in order."""
    doc = _doc(STARTALK)
    blocks = chapter_texts(doc)

    assert " ".join(b.text for b in blocks) == doc.text
    for current, following in zip(blocks, blocks[1:]):
        assert current.end == following.start
    assert blocks[-1].end is None


def test_segments_are_assigned_by_start_time():
    doc = _doc(STARTALK)
    for block in chapter_texts(doc):
        inside = [
            s.text for s in doc.segments
            if s.start >= block.start and (block.end is None or s.start < block.end)
        ]
        assert block.text == " ".join(inside)


# -- no GitHub links ---------------------------------------------------


@pytest.mark.parametrize("video_id", BOTH)
def test_sources_without_github_links_carry_no_repo_slugs(video_id):
    doc = _doc(video_id)
    assert doc.github_links == ()

    links = build_brief(doc, Inventory())["authoritative_links"]
    assert len(links) == len(doc.links) > 0
    assert all(link["repo_slug"] is None for link in links)


@pytest.mark.parametrize("video_id", BOTH)
def test_the_tools_table_is_omitted_when_nothing_is_linked(video_id):
    text = render(_doc(video_id), _conceptual(video_id))
    assert "## Tools & resources mentioned" not in text


# -- conceptual notes --------------------------------------------------


@pytest.mark.parametrize("video_id", BOTH)
def test_a_conceptual_note_says_plainly_that_nothing_is_worth_installing(video_id):
    text = render(_doc(video_id), _conceptual(video_id))
    assert "class: conceptual" in text
    assert "status: no-actions" in text
    assert "## Proposed actions" in text
    assert "Nothing here is worth installing. No actions proposed." in text


def test_conceptual_notes_still_render_project_ideas():
    idea = {"title": "Rediscover the groups", "what": "cluster element properties",
            "why_interesting": "history is the answer key", "stack": "python",
            "first_step": "pip install mendeleev", "size": "weekend"}
    text = render(_doc(STARTALK), _conceptual(STARTALK, project_ideas=[idea]))
    assert "## Project ideas" in text
    assert "Rediscover the groups" in text
    assert "Nothing here is worth installing" in text


@pytest.mark.parametrize("video_id", BOTH)
def test_asr_transcripts_are_flagged_in_the_note(video_id):
    doc = _doc(video_id)
    assert doc.text_quality == TextQuality.AUTO_CAPTIONS
    assert "proper nouns are not" in render(doc, _conceptual(video_id))


# -- promo links -------------------------------------------------------


def test_poker_promo_links_keep_their_labels():
    labels = {link.url: link.label for link in _doc(POKER).links}
    assert labels == {
        "https://www.blackrain79.com/p/free-guide.html": "Get my free poker cheat sheet",
        "https://courses.blackrain79.com/p/elite-poker-university":
            "Enroll in my Elite Poker University",
        "https://courses.blackrain79.com/p/play-fearless-poker": "Join Play Fearless Poker",
    }


def test_startalk_links_keep_labels_where_the_line_has_one():
    labels = {link.url: link.label for link in _doc(STARTALK).links}
    assert labels["https://www.patreon.com/startalkradio"] == "Support us on Patreon"
    assert labels["http://twitter.com/startalkradio"] == "Twitter"
    assert labels["https://www.facebook.com/StarTalk"] == "Facebook"
    # A bare URL on its own line has no label to take — that is not an error.
    assert labels["https://amzn.to/4cCD19e"] is None


@pytest.mark.parametrize("video_id", BOTH)
def test_promo_links_are_listed_in_the_note(video_id):
    doc = _doc(video_id)
    text = render(doc, _conceptual(video_id))
    assert "## Links from description" in text
    assert all(link.url in text for link in doc.links)
