"""The yt-dlp boundary: every path that would otherwise need the network.

yt-dlp is replaced by rebinding the `subprocess` name inside the youtube module
only. The global `subprocess` module is never touched — patching interpreter-wide
state in a test is how a small test bug once took down CI (PLAN §12).
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from self_learning_agent.cache import Cache
from self_learning_agent.config import Config
from self_learning_agent.models import TextQuality
from self_learning_agent.sources import youtube as yt
from self_learning_agent.sources.youtube import YouTubeError, YouTubeSource

VIDEO = "abcdefghijk"


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class FakeYtDlp:
    """Records every invocation; answers each by a handler chosen on the args."""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def run(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        return self.handler(list(cmd))


@pytest.fixture
def source(tmp_path):
    return YouTubeSource(
        Config(home=tmp_path, ytdlp_cmd=("yt-dlp",)), Cache(tmp_path / "cache")
    )


def _install(monkeypatch, handler):
    fake = FakeYtDlp(handler)
    monkeypatch.setattr(yt, "subprocess", SimpleNamespace(run=fake.run))
    return fake


def _write_json3(cmd, payload, lang="en"):
    """Write captions where yt-dlp would: next to the path given with -o."""
    out = Path(cmd[cmd.index("-o") + 1])
    Path(f"{out}.{lang}.json3").write_text(json.dumps(payload), encoding="utf-8")


FULL_METADATA = {
    "id": VIDEO, "title": "A video", "description": "see https://github.com/a/b",
    "channel": "Chan", "uploader": "Up", "uploader_id": "@chan", "channel_id": "UC1",
    "upload_date": "20260101", "duration": 600, "view_count": 5,
    "webpage_url": f"https://www.youtube.com/watch?v={VIDEO}",
    "chapters": [{"start_time": 0, "title": "Intro"}], "tags": ["t"], "categories": ["c"],
    # Everything below is what trimming exists to drop.
    "formats": [{"format_id": str(i)} for i in range(50)],
    "thumbnails": [{"url": "x"}], "http_headers": {"User-Agent": "x"},
    "subtitles": {"en": [{}]},
    "automatic_captions": {"en-orig": [{}], "fr": [{}]},
}
KEPT_FIELDS = {
    "id", "title", "description", "channel", "uploader", "uploader_id", "channel_id",
    "upload_date", "duration", "view_count", "webpage_url", "chapters", "tags",
    "categories", "_has_manual_en", "_has_auto_en",
}


# -- _run --------------------------------------------------------------


def test_run_prepends_the_configured_command_and_returns_stdout(source, monkeypatch):
    fake = _install(monkeypatch, lambda cmd: _Proc(0, stdout="hello"))
    assert source._run(["--version"]) == "hello"
    assert fake.calls == [["yt-dlp", "--no-warnings", "--version"]]


def test_run_failure_raises_with_the_exit_code_and_stderr(source, monkeypatch):
    _install(monkeypatch, lambda cmd: _Proc(1, stderr="ERROR: Video unavailable\n"))
    with pytest.raises(YouTubeError, match=r"yt-dlp failed \(1\): ERROR: Video unavailable"):
        source._run(["x"])


def test_run_failure_detail_is_bounded(source, monkeypatch):
    _install(monkeypatch, lambda cmd: _Proc(2, stderr="x" * 5000))
    with pytest.raises(YouTubeError) as excinfo:
        source._run(["x"])
    assert len(str(excinfo.value)) < 500


@pytest.mark.xfail(strict=True, reason=(
    "_run keeps the FIRST 400 chars of stderr; yt-dlp prints its ERROR line last, "
    "after warnings and notices such as the Python 3.10 deprecation, so the real "
    "cause is cut off whenever stderr is long"
))
def test_run_failure_keeps_the_final_error_line_when_stderr_is_long(source, monkeypatch):
    noisy = "WARNING: some notice about the extractor\n" * 30
    _install(monkeypatch, lambda cmd: _Proc(
        1, stderr=noisy + "ERROR: [youtube] abcdefghijk: Video unavailable\n"))
    with pytest.raises(YouTubeError, match="Video unavailable"):
        source._run(["x"])


# -- _fetch_metadata ---------------------------------------------------


def test_metadata_is_trimmed_to_the_fields_the_pipeline_uses(source, monkeypatch):
    fake = _install(monkeypatch, lambda cmd: _Proc(0, stdout=json.dumps(FULL_METADATA)))
    meta = source._fetch_metadata(VIDEO)

    assert set(meta) == KEPT_FIELDS
    assert "formats" not in meta and "automatic_captions" not in meta
    assert meta["title"] == "A video"
    assert fake.calls[0][-3:] == [
        "--skip-download", "--dump-single-json", f"https://www.youtube.com/watch?v={VIDEO}",
    ]


def test_caption_availability_flags_only_count_english(source, monkeypatch):
    payload = {**FULL_METADATA, "subtitles": {"fr": [{}]}, "automatic_captions": {"en-orig": [{}]}}
    _install(monkeypatch, lambda cmd: _Proc(0, stdout=json.dumps(payload)))
    meta = source._fetch_metadata(VIDEO)
    assert meta["_has_manual_en"] is False
    assert meta["_has_auto_en"] is True


def test_missing_caption_maps_mean_no_captions(source, monkeypatch):
    payload = {**FULL_METADATA, "subtitles": None, "automatic_captions": None}
    _install(monkeypatch, lambda cmd: _Proc(0, stdout=json.dumps(payload)))
    meta = source._fetch_metadata(VIDEO)
    assert meta["_has_manual_en"] is False and meta["_has_auto_en"] is False


# -- _fetch_captions ---------------------------------------------------

CAPTIONS = {"events": [{"tStartMs": 0, "segs": [{"utf8": "hello world"}]}]}


def test_no_captions_available_returns_empty_without_calling_ytdlp(source, monkeypatch):
    fake = _install(monkeypatch, lambda cmd: pytest.fail("yt-dlp must not be called"))
    assert source._fetch_captions(VIDEO, {"_has_manual_en": False, "_has_auto_en": False}) == {}
    assert fake.calls == []


def test_human_captions_are_preferred_over_asr(source, monkeypatch):
    def handler(cmd):
        _write_json3(cmd, CAPTIONS)
        return _Proc(0)

    fake = _install(monkeypatch, handler)
    result = source._fetch_captions(VIDEO, {"_has_manual_en": True, "_has_auto_en": True})

    assert "--write-subs" in fake.calls[0]
    assert "--write-auto-subs" not in fake.calls[0]
    assert result["_quality"] == TextQuality.MANUAL_CAPTIONS


def test_asr_captions_are_used_when_no_human_ones_exist(source, monkeypatch):
    def handler(cmd):
        _write_json3(cmd, CAPTIONS)
        return _Proc(0)

    fake = _install(monkeypatch, handler)
    result = source._fetch_captions(VIDEO, {"_has_manual_en": False, "_has_auto_en": True})

    assert "--write-auto-subs" in fake.calls[0]
    assert result["_quality"] == TextQuality.AUTO_CAPTIONS


def test_caption_json3_is_parsed_from_where_ytdlp_wrote_it(source, monkeypatch):
    def handler(cmd):
        assert cmd[cmd.index("--sub-format") + 1] == "json3"
        _write_json3(cmd, CAPTIONS, lang="en-orig")
        return _Proc(0)

    _install(monkeypatch, handler)
    result = source._fetch_captions(VIDEO, {"_has_auto_en": True})
    assert result["events"] == CAPTIONS["events"]


def test_a_failed_caption_download_degrades_to_no_captions(source, monkeypatch):
    _install(monkeypatch, lambda cmd: _Proc(1, stderr="ERROR: HTTP Error 429"))
    assert source._fetch_captions(VIDEO, {"_has_auto_en": True}) == {}


def test_a_download_that_writes_no_file_degrades_to_no_captions(source, monkeypatch):
    _install(monkeypatch, lambda cmd: _Proc(0))
    assert source._fetch_captions(VIDEO, {"_has_auto_en": True}) == {}


# -- _channel_video_ids ------------------------------------------------


def _flat(*entries):
    return "\n".join(json.dumps(e) if isinstance(e, dict) else e for e in entries) + "\n"


def test_a_handle_is_expanded_to_the_channels_videos_tab(source, monkeypatch):
    fake = _install(monkeypatch, lambda cmd: _Proc(0, stdout=_flat({"id": "v1"})))
    source._channel_video_ids("@GregIsenberg", limit=3)

    cmd = fake.calls[0]
    assert cmd[-1] == "https://www.youtube.com/@GregIsenberg/videos"
    assert cmd[cmd.index("--playlist-end") + 1] == "3"
    assert "--flat-playlist" in cmd and "--dump-json" in cmd


@pytest.mark.parametrize("ref", [
    "https://www.youtube.com/@chan/videos",
    "https://www.youtube.com/@chan/videos/",
    "https://www.youtube.com/@chan",
])
def test_channel_urls_resolve_to_one_videos_suffix(source, monkeypatch, ref):
    fake = _install(monkeypatch, lambda cmd: _Proc(0, stdout=_flat({"id": "v1"})))
    source._channel_video_ids(ref, limit=1)
    assert fake.calls[0][-1] == "https://www.youtube.com/@chan/videos"


def test_flat_playlist_lines_are_parsed_skipping_blanks_and_idless_entries(source, monkeypatch):
    out = _flat({"id": "v1"}, "", "   ", {"title": "no id"}, {"id": "v2"})
    _install(monkeypatch, lambda cmd: _Proc(0, stdout=out))
    assert source._channel_video_ids("@chan", limit=10) == ["v1", "v2"]


def test_the_limit_is_respected_even_if_ytdlp_returns_more(source, monkeypatch):
    out = _flat(*({"id": f"v{i}"} for i in range(8)))
    _install(monkeypatch, lambda cmd: _Proc(0, stdout=out))
    assert source._channel_video_ids("@chan", limit=3) == ["v0", "v1", "v2"]


def test_resolve_routes_a_handle_to_the_channel_listing(source, monkeypatch):
    _install(monkeypatch, lambda cmd: _Proc(0, stdout=_flat({"id": "v1"}, {"id": "v2"})))
    assert source.resolve("@chan", limit=2) == ["v1", "v2"]


def test_a_failed_channel_listing_raises(source, monkeypatch):
    _install(monkeypatch, lambda cmd: _Proc(1, stderr="ERROR: channel not found"))
    with pytest.raises(YouTubeError, match="channel not found"):
        source._channel_video_ids("@nobody", limit=5)


# -- fetch and the cache -----------------------------------------------


def _full_handler(cmd):
    if "--dump-single-json" in cmd:
        return _Proc(0, stdout=json.dumps(FULL_METADATA))
    _write_json3(cmd, CAPTIONS)
    return _Proc(0)


def test_fetch_downloads_once_then_serves_from_the_cache(source, monkeypatch):
    fake = _install(monkeypatch, _full_handler)

    first = source.fetch(VIDEO)
    assert len(fake.calls) == 2  # metadata + captions
    second = source.fetch(VIDEO)
    assert len(fake.calls) == 2  # nothing new

    assert first.title == second.title == "A video"
    assert second.text == "hello world"
    assert second.text_quality == TextQuality.MANUAL_CAPTIONS


def test_refresh_bypasses_the_cache(source, monkeypatch):
    fake = _install(monkeypatch, _full_handler)
    source.fetch(VIDEO)
    source.fetch(VIDEO, refresh=True)
    assert len(fake.calls) == 4


def test_a_video_with_no_captions_is_not_refetched_every_time(source, monkeypatch):
    """An empty caption result is cached too, rather than read as a cache miss."""
    no_caps = {**FULL_METADATA, "subtitles": {}, "automatic_captions": {}}
    fake = _install(monkeypatch, lambda cmd: _Proc(0, stdout=json.dumps(no_caps)))

    doc = source.fetch(VIDEO)
    source.fetch(VIDEO)
    assert len(fake.calls) == 1  # metadata only, once
    assert doc.text == "" and doc.text_quality == TextQuality.NONE


def test_fetched_document_extracts_description_links(source, monkeypatch):
    _install(monkeypatch, _full_handler)
    doc = source.fetch(VIDEO)
    assert [link.repo_slug for link in doc.github_links] == ["a/b"]
    assert doc.published_at.date().isoformat() == "2026-01-01"


# -- small helpers the network paths depend on -------------------------


@pytest.mark.parametrize("ref,expected", [
    ("https://www.youtube.com/watch?v=abcdefghijk", True),
    ("https://youtu.be/abcdefghijk", True),
    ("@chan", True),
    ("abcdefghijk", True),
    ("https://example.com/video", False),
    ("not a reference", False),
])
def test_handles_recognises_youtube_references(source, ref, expected):
    assert source.handles(ref) is expected


@pytest.mark.parametrize("value", [None, "", "2026", "20261399", "notadate"])
def test_unparseable_upload_dates_become_none(value):
    assert yt._parse_date(value) is None
