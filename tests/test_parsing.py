from self_learning_agent.models import Chapter, TextQuality
from self_learning_agent.sources.youtube import (
    parse_chapters,
    parse_json3,
    YouTubeError,
)
import pytest

from self_learning_agent.config import Config
from self_learning_agent.sources.youtube import YouTubeSource


def test_parses_timestamped_segments(captions):
    segments = parse_json3(captions)
    assert segments
    assert all(seg.text for seg in segments)
    assert segments == tuple(sorted(segments, key=lambda s: s.start))


def test_no_captions_yields_no_segments():
    assert parse_json3(None) == ()
    assert parse_json3({}) == ()


def test_chapters_match_the_creators_own_timestamps(meta):
    chapters = parse_chapters(meta["chapters"])
    assert [c.timestamp for c in chapters][:3] == ["0:00", "1:44", "5:20"]
    assert chapters[4].title == "Repo 4: SkillSpector"


def test_chapter_timestamp_formats_hours():
    assert Chapter(3725, "x").timestamp == "1:02:05"


def test_missing_chapters_is_not_an_error():
    assert parse_chapters(None) == ()


@pytest.mark.parametrize(
    "ref",
    [
        "https://www.youtube.com/watch?v=9_SZFIW7tus",
        "https://youtu.be/9_SZFIW7tus",
        "https://www.youtube.com/watch?list=PL1&v=9_SZFIW7tus",
        "https://www.youtube.com/shorts/9_SZFIW7tus",
        "9_SZFIW7tus",
    ],
)
def test_resolve_accepts_every_common_reference_form(ref):
    source = YouTubeSource(Config(ytdlp_cmd=("true",)))
    assert source.resolve(ref) == ["9_SZFIW7tus"]


def test_unresolvable_reference_raises_rather_than_guessing():
    source = YouTubeSource(Config(ytdlp_cmd=("true",)))
    with pytest.raises(YouTubeError):
        source.resolve("https://example.com/not-a-video")
