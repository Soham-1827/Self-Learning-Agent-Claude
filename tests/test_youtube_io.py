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
    """One attempt, no backoff: retrying is exercised by its own tests below.

    Left at the shipped default, every rate-limit test here would sleep out the
    real backoff schedule.
    """
    return YouTubeSource(
        Config(home=tmp_path, ytdlp_cmd=("yt-dlp",), ytdlp_attempts=1,
               ytdlp_backoff_seconds=0),
        Cache(tmp_path / "cache"),
    )


@pytest.fixture
def retrying_source(tmp_path, monkeypatch):
    """A source with retries on, and `time.sleep` replaced by a recorder."""
    sleeps: list[float] = []
    monkeypatch.setattr(yt, "time", SimpleNamespace(sleep=sleeps.append))
    src = YouTubeSource(
        Config(home=tmp_path, ytdlp_cmd=("yt-dlp",), ytdlp_attempts=3,
               ytdlp_backoff_seconds=2),
        Cache(tmp_path / "cache"),
    )
    return src, sleeps


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
    "categories", "_has_manual_en", "_has_auto_en", "_en_manual", "_en_auto",
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


def test_run_failure_keeps_the_final_error_line_when_stderr_is_long(source, monkeypatch):
    noisy = "WARNING: some notice about the extractor\n" * 30
    _install(monkeypatch, lambda cmd: _Proc(
        1, stderr=noisy + "ERROR: [youtube] abcdefghijk: Video unavailable\n"))
    with pytest.raises(YouTubeError, match="Video unavailable"):
        source._run(["x"])


# -- _run: rate limiting -----------------------------------------------


def test_a_rate_limited_call_is_retried_with_growing_backoff(retrying_source, monkeypatch):
    """429 is a wait, not a verdict. Only the last attempt's failure is final."""
    src, sleeps = retrying_source
    replies = [
        _Proc(1, stderr="ERROR: HTTP Error 429: Too Many Requests"),
        _Proc(1, stderr="ERROR: HTTP Error 429: Too Many Requests"),
        _Proc(0, stdout="finally"),
    ]
    fake = _install(monkeypatch, lambda cmd: replies.pop(0))

    assert src._run(["x"]) == "finally"
    assert len(fake.calls) == 3
    assert sleeps == [2, 8]  # backoff grows; it does not hammer


def test_retrying_gives_up_and_reports_the_rate_limit(retrying_source, monkeypatch):
    src, sleeps = retrying_source
    fake = _install(monkeypatch, lambda cmd: _Proc(1, stderr="ERROR: HTTP Error 429"))

    with pytest.raises(YouTubeError, match="429"):
        src._run(["x"])
    assert len(fake.calls) == 3      # attempts, not one more
    assert len(sleeps) == 2          # and no sleep after the last one


def test_the_wait_stays_bounded_however_many_attempts_are_configured(tmp_path, monkeypatch):
    """`ytdlp_attempts` is the owner's to set; 4** would otherwise park a run for hours."""
    sleeps: list[float] = []
    monkeypatch.setattr(yt, "time", SimpleNamespace(sleep=sleeps.append))
    src = YouTubeSource(
        Config(home=tmp_path, ytdlp_cmd=("yt-dlp",), ytdlp_attempts=8,
               ytdlp_backoff_seconds=5),
        Cache(tmp_path / "cache"),
    )
    _install(monkeypatch, lambda cmd: _Proc(1, stderr="ERROR: HTTP Error 429"))

    with pytest.raises(YouTubeError):
        src._run(["x"])
    assert sleeps == [5, 20, 80, 120, 120, 120, 120]
    assert sum(sleeps) < 20 * 60


def test_a_failure_that_is_not_a_rate_limit_is_not_retried(retrying_source, monkeypatch):
    """Retrying a video that does not exist just wastes the request budget."""
    src, sleeps = retrying_source
    fake = _install(monkeypatch, lambda cmd: _Proc(1, stderr="ERROR: Video unavailable"))

    with pytest.raises(YouTubeError, match="Video unavailable"):
        src._run(["x"])
    assert len(fake.calls) == 1 and sleeps == []


def test_a_rate_limit_that_exits_zero_is_retried_too(retrying_source, monkeypatch):
    """The subtitle path's 429 arrives with returncode 0 — see §23."""
    src, sleeps = retrying_source
    replies = [
        _Proc(0, stderr="ERROR: Unable to download video subtitles for 'en': "
                        "HTTP Error 429: Too Many Requests"),
        _Proc(0, stdout="ok"),
    ]
    fake = _install(monkeypatch, lambda cmd: replies.pop(0))

    assert src._run(["x"]) == "ok"
    assert len(fake.calls) == 2 and sleeps == [2]


def test_triage_metadata_survives_a_passing_rate_limit(retrying_source, monkeypatch):
    """Triage spends one metadata request per candidate; 429 must not sink one."""
    src, _ = retrying_source
    replies = [
        _Proc(1, stderr="ERROR: HTTP Error 429: Too Many Requests"),
        _Proc(0, stdout=json.dumps(FULL_METADATA)),
    ]
    _install(monkeypatch, lambda cmd: replies.pop(0))
    assert src.metadata(VIDEO)["title"] == "A video"


def test_a_warning_mentioning_429_does_not_trigger_a_retry(retrying_source, monkeypatch):
    """yt-dlp retries internally and says so; only its ERROR line is a failure."""
    src, sleeps = retrying_source
    fake = _install(monkeypatch, lambda cmd: _Proc(
        0, stdout="fine", stderr="WARNING: Got error: HTTP Error 429. Retrying (1/10)"))

    assert src._run(["x"]) == "fine"
    assert len(fake.calls) == 1 and sleeps == []


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


def test_metadata_that_never_answered_the_question_is_not_read_as_a_no(source, monkeypatch):
    """The oldest cache entries predate the flags. {} there would cache a silence."""
    fake = _install(monkeypatch, lambda cmd: pytest.fail("yt-dlp must not be called"))
    with pytest.raises(YouTubeError, match="predates the caption check"):
        source._fetch_captions(VIDEO, {"title": "old entry"})
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


def test_a_failed_caption_download_raises_instead_of_looking_like_no_captions(
    source, monkeypatch
):
    """Returning {} here is how a rate-limit became "this video has no transcript".

    The empty result is cached, so the failure outlives the rate-limit and every
    later run reads the absence back out of the cache.
    """
    _install(monkeypatch, lambda cmd: _Proc(1, stderr="ERROR: HTTP Error 429"))
    with pytest.raises(YouTubeError, match="429"):
        source._fetch_captions(VIDEO, {"_has_auto_en": True})


def test_an_error_that_exits_zero_is_still_an_error(source, monkeypatch):
    """yt-dlp prints ERROR and exits 0 when a subtitle download is rate-limited.

    Observed live on 2026-09-24: "Unable to download video subtitles for 'en':
    HTTP Error 429", exit status 0, and no file written.
    """
    _install(monkeypatch, lambda cmd: _Proc(0, stderr=(
        "[info] Writing video subtitles to: /tmp/x/cap.en.json3\n"
        "ERROR: Unable to download video subtitles for 'en': "
        "HTTP Error 429: Too Many Requests")))
    with pytest.raises(YouTubeError, match="429"):
        source._fetch_captions(VIDEO, {"_has_auto_en": True})


# -- _fetch_captions: one track, not a pattern -------------------------


def _capture_langs(fake):
    return [cmd[cmd.index("--sub-langs") + 1] for cmd in fake.calls]


def test_metadata_records_which_english_tracks_exist(source, monkeypatch):
    """`--sub-langs "en.*"` cost two subtitle requests per video (§23).

    Choosing one track needs their names, so metadata keeps them.
    """
    payload = {**FULL_METADATA,
               "subtitles": {"en": [{}], "en-GB": [{}], "fr": [{}]},
               "automatic_captions": {"en": [{}], "en-orig": [{}], "de": [{}]}}
    _install(monkeypatch, lambda cmd: _Proc(0, stdout=json.dumps(payload)))
    meta = source._fetch_metadata(VIDEO)

    assert meta["_en_manual"] == ["en", "en-GB"]
    assert meta["_en_auto"] == ["en-orig", "en"]   # the original, not a translation
    assert meta["_has_manual_en"] is True and meta["_has_auto_en"] is True


def test_a_track_list_with_no_english_leaves_both_empty(source, monkeypatch):
    payload = {**FULL_METADATA, "subtitles": {"fr": [{}]}, "automatic_captions": {"eng-x": [{}]}}
    _install(monkeypatch, lambda cmd: _Proc(0, stdout=json.dumps(payload)))
    meta = source._fetch_metadata(VIDEO)
    assert meta["_en_manual"] == [] and meta["_en_auto"] == []
    assert meta["_has_auto_en"] is False


def test_one_caption_request_asks_for_a_single_named_track(source, monkeypatch):
    def handler(cmd):
        _write_json3(cmd, CAPTIONS, lang="en-orig")
        return _Proc(0)

    fake = _install(monkeypatch, handler)
    source._fetch_captions(VIDEO, {"_has_auto_en": True, "_en_auto": ["en-orig", "en"]})

    assert _capture_langs(fake) == ["en-orig"]   # one request, not "en.*"
    assert len(fake.calls) == 1


def test_a_track_that_yields_nothing_falls_back_to_the_next(source, monkeypatch):
    """A listed track can still come back empty; that is not "no captions"."""
    def handler(cmd):
        if cmd[cmd.index("--sub-langs") + 1] == "en-orig":
            return _Proc(0, stderr="ERROR: Requested format is not available")
        _write_json3(cmd, CAPTIONS)
        return _Proc(0)

    fake = _install(monkeypatch, handler)
    result = source._fetch_captions(VIDEO, {"_has_auto_en": True, "_en_auto": ["en-orig", "en"]})

    assert _capture_langs(fake) == ["en-orig", "en"]
    assert result["events"] == CAPTIONS["events"]


def test_a_rate_limit_does_not_burn_the_fallback_track(source, monkeypatch):
    """429 refuses the video, not the track: asking again only spends requests."""
    fake = _install(monkeypatch, lambda cmd: _Proc(
        0, stderr="ERROR: Unable to download video subtitles for 'en-orig': "
                  "HTTP Error 429: Too Many Requests"))

    with pytest.raises(YouTubeError, match="429"):
        source._fetch_captions(VIDEO, {"_has_auto_en": True, "_en_auto": ["en-orig", "en"]})
    assert _capture_langs(fake) == ["en-orig"]


def test_every_listed_track_failing_raises_rather_than_reading_as_absence(source, monkeypatch):
    fake = _install(monkeypatch, lambda cmd: _Proc(0, stderr="ERROR: no subtitles"))

    with pytest.raises(YouTubeError, match="no subtitles"):
        source._fetch_captions(VIDEO, {"_has_auto_en": True, "_en_auto": ["en-orig", "en"]})
    assert _capture_langs(fake) == ["en-orig", "en"]


def test_metadata_cached_before_track_names_existed_still_narrows(source, monkeypatch):
    """Old cache entries carry only the flags — ask for `en`, keep `en.*` as the fallback."""
    def handler(cmd):
        if cmd[cmd.index("--sub-langs") + 1] == "en":
            return _Proc(0, stderr="ERROR: Requested format is not available")
        _write_json3(cmd, CAPTIONS, lang="en-orig")
        return _Proc(0)

    fake = _install(monkeypatch, handler)
    result = source._fetch_captions(VIDEO, {"_has_auto_en": True})

    assert _capture_langs(fake) == ["en", "en.*"]
    assert result["_quality"] == TextQuality.AUTO_CAPTIONS


def test_human_captions_choose_from_the_manual_tracks(source, monkeypatch):
    def handler(cmd):
        _write_json3(cmd, CAPTIONS)
        return _Proc(0)

    fake = _install(monkeypatch, handler)
    source._fetch_captions(VIDEO, {
        "_has_manual_en": True, "_has_auto_en": True,
        "_en_manual": ["en-GB"], "_en_auto": ["en-orig"],
    })
    assert _capture_langs(fake) == ["en-GB"]
    assert "--write-subs" in fake.calls[0]


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


def test_a_caption_failure_is_never_cached(source, monkeypatch):
    """Caching the empty result is what made a transient failure permanent."""
    meta = {**FULL_METADATA, "subtitles": {}, "automatic_captions": {"en": [{"ext": "json3"}]}}

    def handler(cmd):
        if "--dump-single-json" in cmd:
            return _Proc(0, stdout=json.dumps(meta))
        return _Proc(0, stderr="ERROR: HTTP Error 429: Too Many Requests")

    _install(monkeypatch, handler)
    with pytest.raises(YouTubeError):
        source.fetch(VIDEO)
    assert source.cache.get("youtube", VIDEO, "captions") is None

