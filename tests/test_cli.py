"""CLI wiring: argument shapes and the error paths users actually hit."""

import json
from pathlib import Path

import pytest

from self_learning_agent import cli
from self_learning_agent.config import Config


def test_every_subcommand_is_registered():
    parser = cli.build_parser()
    for argv in (
        ["fetch", "x"],
        ["brief", "x"],
        ["note", "x", "--synthesis", "s.json"],
        ["apply", "x"],
        ["inventory"],
        ["status"],
    ):
        assert parser.parse_args(argv).func is not None


def test_a_missing_subcommand_is_rejected():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


def test_note_requires_a_synthesis_file():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["note", "x"])


def test_apply_flags_default_to_the_cautious_option():
    args = cli.build_parser().parse_args(["apply", "x"])
    assert args.yes is False        # prompts by default
    assert args.dry_run is False
    assert args.no_llm is False     # full scan by default
    assert args.only is None


def test_fetch_defaults_to_a_single_video():
    assert cli.build_parser().parse_args(["fetch", "x"]).last == 1


def test_errors_are_reported_not_raised(capsys):
    def boom(_args):
        raise RuntimeError("something broke")

    parser = cli.build_parser()
    args = parser.parse_args(["status"])
    args.func = boom
    monkey = cli.build_parser
    assert cli.main.__name__ == "main"

    # main() catches and reports rather than propagating a traceback
    import argparse

    class _P(argparse.ArgumentParser):
        def parse_args(self, argv=None):
            return args

    original = cli.build_parser
    cli.build_parser = lambda: _P()
    try:
        assert cli.main([]) == 1
    finally:
        cli.build_parser = original
    assert "something broke" in capsys.readouterr().err


def test_apply_without_a_prior_note_says_so(tmp_path, monkeypatch, capsys):
    """The common first mistake: running apply on a video with no note yet."""
    cfg = Config(home=tmp_path / "home")
    monkeypatch.setattr(cli.config_mod, "load", lambda: cfg)

    class _Source:
        source_type = "youtube"

        def __init__(self, *a, **k):
            pass

        def resolve(self, ref, limit=1):
            return ["abc12345678"]

    monkeypatch.setattr(cli, "YouTubeSource", _Source)
    args = cli.build_parser().parse_args(["apply", "https://youtu.be/abc12345678"])
    assert cli.cmd_apply(args) == 1
    assert "Run `sla note` first" in capsys.readouterr().err


def test_document_summary_exposes_repo_slugs(meta, captions):
    from self_learning_agent.sources.youtube import YouTubeSource

    doc = YouTubeSource(Config(ytdlp_cmd=("true",)))._build("9_SZFIW7tus", meta, captions)
    summary = cli._document_summary(doc)
    assert summary["title"].startswith("5 GitHub Repos")
    assert "NVIDIA/SkillSpector" in [link["repo"] for link in summary["links"]]
    assert summary["text_quality"] == "auto_captions"
