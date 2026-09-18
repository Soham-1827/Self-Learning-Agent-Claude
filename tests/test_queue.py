"""Channel triage: ranks from metadata alone, and never reads a transcript."""

import json

import pytest

from self_learning_agent import cli
from self_learning_agent.cache import Cache
from self_learning_agent.config import Config
from self_learning_agent.ledger import Ledger, processed_ids, read_rows
from self_learning_agent.sources.youtube import YouTubeError, YouTubeSource, video_id_from_ref
from self_learning_agent.triage import (
    LIKELY_CONCEPTUAL,
    LIKELY_TOOLING,
    build_queue,
    candidate_from_meta,
    format_table,
    guess_class,
    rank,
    to_dict,
)


def _meta(title, upload_date="20260901", duration=1200, chapters=(), description=""):
    return {
        "title": title,
        "upload_date": upload_date,
        "duration": duration,
        "description": description,
        "chapters": [{"start_time": i * 60, "title": t} for i, t in enumerate(chapters)],
    }


class FakeSource:
    """Serves metadata; refuses outright to fetch a transcript."""

    source_type = "youtube"

    def __init__(self, metas, failing=()):
        self.metas = metas
        self.failing = set(failing)
        self.metadata_calls = []

    def resolve(self, ref, limit=1):
        return list(self.metas)[:limit]

    def metadata(self, source_id):
        self.metadata_calls.append(source_id)
        if source_id in self.failing:
            raise YouTubeError("yt-dlp failed (1): video unavailable")
        return self.metas[source_id]

    def fetch(self, *a, **k):  # pragma: no cover - reaching this is the failure
        raise AssertionError("triage must never fetch captions")


# channel order is newest first, as yt-dlp lists it
CHANNEL = {
    "newest00001": _meta("Why founders burn out", "20260915"),
    "tooling0001": _meta("My agent stack", "20260910",
                         description="Repo: https://github.com/acme/agent-kit"),
    "older000001": _meta("Pricing lessons", "20260905"),
    "tooling0002": _meta("Building with Claude Code and MCP", "20260901"),
}


# -- class guess ---------------------------------------------------------


def test_a_github_repo_link_means_likely_tooling():
    likely, signals = guess_class("Anything", (), "", ("acme/kit",))
    assert likely == LIKELY_TOOLING
    assert "1 GitHub repo link" in signals[0]


def test_tool_words_in_title_or_chapters_mean_likely_tooling():
    assert guess_class("Set up an MCP server", (), "", ())[0] == LIKELY_TOOLING
    likely, signals = guess_class("Episode 12", ("The CLI walkthrough",), "", ())
    assert likely == LIKELY_TOOLING
    assert signals == ("tool words in title/chapters: cli",)


def test_one_tool_word_in_a_description_is_not_enough():
    """Descriptions carry sponsor boilerplate; one stray 'API' proves nothing."""
    assert guess_class("Startup ideas", (), "Try our API today", ())[0] == LIKELY_CONCEPTUAL
    assert guess_class("Startup ideas", (), "our API and SDK", ())[0] == LIKELY_TOOLING


def test_no_signals_means_likely_conceptual():
    likely, signals = guess_class("How to beat low stakes poker", (), "cheat sheet", ())
    assert likely == LIKELY_CONCEPTUAL
    assert signals == ("no GitHub links or tool words",)


def test_keywords_match_whole_words_only():
    # "capital" contains "api", "reposition" contains "repo"
    assert guess_class("Capital and reposition", (), "", ())[0] == LIKELY_CONCEPTUAL


def test_candidate_reads_repos_chapters_and_estimates_words():
    c = candidate_from_meta("x" * 11, _meta(
        "t", duration=1200, chapters=("a", "b"),
        description="https://github.com/a/b and again https://github.com/a/b",
    ))
    assert c.github_repos == ("a/b",)        # deduplicated
    assert c.chapter_count == 2
    assert c.estimated_words == 3000          # 20 min x 150 wpm
    assert c.published.isoformat() == "2026-09-01"


# -- ranking and cap -----------------------------------------------------


def test_likely_tooling_ranks_first_then_newest():
    result = build_queue(FakeSource(CHANNEL), "@x", last=10, cap=10)
    assert [c.source_id for c in result.candidates] == [
        "tooling0001", "tooling0002", "newest00001", "older000001",
    ]


def test_cap_limits_the_suggested_picks():
    result = build_queue(FakeSource(CHANNEL), "@x", last=10, cap=2)
    assert [c.source_id for c in result.suggested] == ["tooling0001", "tooling0002"]
    assert len(result.candidates) == 4       # everything is still listed


def test_a_zero_cap_suggests_nothing():
    assert build_queue(FakeSource(CHANNEL), "@x", last=10, cap=0).suggested == ()


def test_undated_videos_sort_after_dated_ones():
    cands = [candidate_from_meta("a" * 11, _meta("x", upload_date=None)),
             candidate_from_meta("b" * 11, _meta("y", upload_date="20200101"))]
    assert [c.source_id for c in rank(cands, 5)] == ["b" * 11, "a" * 11]


@pytest.mark.parametrize("last,cap", [(0, 5), (5, -1)])
def test_invalid_bounds_are_rejected(last, cap):
    with pytest.raises(ValueError):
        build_queue(FakeSource(CHANNEL), "@x", last=last, cap=cap)


def test_last_limits_how_many_videos_are_considered():
    result = build_queue(FakeSource(CHANNEL), "@x", last=2, cap=5)
    assert result.listed == 2


# -- ledger and side effects -------------------------------------------


def test_processed_videos_are_left_out():
    result = build_queue(FakeSource(CHANNEL), "@x", last=10, cap=5,
                         processed=frozenset({"tooling0001"}))
    assert "tooling0001" not in [c.source_id for c in result.candidates]
    assert result.already_processed == ("tooling0001",)
    assert result.listed == 4


def test_captions_are_never_fetched_and_processed_metadata_is_never_read():
    source = FakeSource(CHANNEL)  # its fetch() raises
    build_queue(source, "@x", last=10, cap=5, processed=frozenset({"older000001"}))
    assert sorted(source.metadata_calls) == sorted(set(CHANNEL) - {"older000001"})


def test_the_real_source_metadata_call_never_requests_subtitles(tmp_path, monkeypatch):
    src = YouTubeSource(Config(home=tmp_path, ytdlp_cmd=("true",)), Cache(tmp_path / "c"))
    calls = []

    def fake_run(args):
        calls.append(args)
        return json.dumps({"id": "abcdefghijk", "title": "t", "automatic_captions": {"en": []}})

    monkeypatch.setattr(src, "_run", fake_run)
    meta = src.metadata("abcdefghijk")
    src.metadata("abcdefghijk")                      # served from cache
    assert meta["title"] == "t" and len(calls) == 1
    flat = [a for call in calls for a in call]
    assert not {"--write-subs", "--write-auto-subs", "--sub-langs"} & set(flat)
    src.metadata("abcdefghijk", refresh=True)
    assert len(calls) == 2


def test_one_failing_video_does_not_sink_the_queue():
    result = build_queue(FakeSource(CHANNEL, failing={"older000001"}), "@x", last=10, cap=5)
    assert [s for s, _ in result.failures] == ["older000001"]
    assert len(result.candidates) == 3


def test_duplicate_ids_from_the_channel_are_listed_once():
    class Dupes(FakeSource):
        def resolve(self, ref, limit=1):
            return ["tooling0001", "tooling0001"]
    assert build_queue(Dupes(CHANNEL), "@x", last=10, cap=5).listed == 1


def test_processed_ids_reads_without_creating_a_ledger(tmp_path):
    path = tmp_path / "ledger.db"
    assert processed_ids(path, "youtube") == frozenset()
    assert read_rows(path) == []
    assert not path.exists()


def test_processed_ids_never_writes_an_existing_ledger(tmp_path):
    path = tmp_path / "ledger.db"
    Ledger(path).record("youtube", "a" * 11, title="A")
    Ledger(path).record("article", "b" * 11)
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    assert processed_ids(path, "youtube") == frozenset({"a" * 11})
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_a_file_that_is_not_a_ledger_reads_as_empty(tmp_path):
    import sqlite3
    path = tmp_path / "other.db"
    sqlite3.connect(path).close()
    assert read_rows(path) == []


# -- output --------------------------------------------------------------


def test_table_marks_picks_and_says_the_class_is_a_guess():
    text = format_table(build_queue(FakeSource(CHANNEL), "@x", last=10, cap=2))
    assert "4 latest video(s): 0 already processed, 4 new" in text
    assert text.count("✓") == 2
    assert "guess" in text and "tooling0001" in text
    assert "Suggested: 2 video(s)" in text


def test_table_reports_failures_and_an_empty_queue():
    empty = build_queue(FakeSource(CHANNEL, failing=set(CHANNEL)), "@x", last=10, cap=5)
    text = format_table(empty)
    assert "Nothing new to triage." in text
    assert text.count("failed  ") == 4


def test_json_output_shape():
    data = to_dict(build_queue(FakeSource(CHANNEL), "@x", last=10, cap=1))
    assert data["suggested"] == ["tooling0001"]
    assert data["class_is_a_guess"] is True
    first = data["candidates"][0]
    assert first["rank"] == 1 and first["url"].endswith("tooling0001")
    assert first["github_repos"] == ["acme/agent-kit"]


# -- CLI -----------------------------------------------------------------


def test_cli_queue_prints_json_and_creates_no_ledger(tmp_path, monkeypatch, capsys):
    cfg = Config(home=tmp_path / "home")
    monkeypatch.setattr(cli.config_mod, "load", lambda: cfg)
    monkeypatch.setattr(cli, "YouTubeSource", lambda *a, **k: FakeSource(CHANNEL))
    args = cli.build_parser().parse_args(["queue", "@x", "--last", "3", "--cap", "1", "--json"])
    assert cli.cmd_queue(args) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["listed"] == 3 and len(data["suggested"]) == 1
    assert not cfg.ledger_path.exists()


def test_cli_queue_prints_a_table_by_default(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.config_mod, "load", lambda: Config(home=tmp_path))
    monkeypatch.setattr(cli, "YouTubeSource", lambda *a, **k: FakeSource(CHANNEL))
    assert cli.cmd_queue(cli.build_parser().parse_args(["queue", "@x"])) == 0
    assert "Suggested:" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["queue", "@x", "--last", "0"], ["queue", "@x", "--cap", "-1"]])
def test_cli_rejects_nonsense_bounds(argv):
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(argv)


def test_video_id_from_ref_recognises_ids_and_urls():
    assert video_id_from_ref("9_SZFIW7tus") == "9_SZFIW7tus"
    assert video_id_from_ref("https://youtu.be/9_SZFIW7tus") == "9_SZFIW7tus"
    assert video_id_from_ref("https://www.youtube.com/watch?v=9_SZFIW7tus&t=3") == "9_SZFIW7tus"
    assert video_id_from_ref("@GregIsenberg") is None
    assert video_id_from_ref("") is None
