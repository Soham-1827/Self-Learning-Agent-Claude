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


def _apply_harness(tmp_path, monkeypatch, skill_name):
    """Drive cmd_apply with one skill proposal, recording where it staged and scanned.

    Writes aimed at the real checkout are redirected, so no test touches the repo.
    """
    from self_learning_agent.scanner import ScanVerdict

    cfg = Config(home=tmp_path / "home")
    store = cfg.home / "proposals"
    store.mkdir(parents=True)
    (store / "abc12345678.json").write_text(json.dumps({
        "source_id": "abc12345678",
        "note_path": None,
        "proposals": [{"kind": "skill", "title": "probe",
                       "action": {"name": skill_name, "content": "# probe"}}],
    }), encoding="utf-8")
    monkeypatch.setattr(cli.config_mod, "load", lambda: cfg)

    class _Source:
        source_type = "youtube"

        def __init__(self, *a, **k):
            pass

        def resolve(self, ref, limit=1):
            return ["abc12345678"]

    monkeypatch.setattr(cli, "YouTubeSource", _Source)

    repo_root = Path(cli.__file__).resolve().parents[2]
    roots = []
    real_stage = cli.stage_skill

    def recording_stage(proposal, root):
        roots.append(Path(root))
        target = tmp_path / "repo" if Path(root) == repo_root else root
        return real_stage(proposal, target)

    monkeypatch.setattr(cli, "stage_skill", recording_stage)

    seen = {}

    def fake_scan(target, use_llm=True):
        skill = Path(target) / "SKILL.md"
        seen["target"] = Path(target)
        seen["mode"] = skill.stat().st_mode if skill.exists() else None
        return ScanVerdict(str(target), 0, "LOW", "CAUTION", (), False, True)

    monkeypatch.setattr(cli.scanner_mod, "available", lambda: True)
    monkeypatch.setattr(cli.scanner_mod, "scan", fake_scan)
    return seen, roots, repo_root


def test_dry_run_writes_nothing_into_the_repo(tmp_path, monkeypatch):
    seen, roots, repo_root = _apply_harness(tmp_path, monkeypatch, "dry-run-probe")
    args = cli.build_parser().parse_args(["apply", "https://youtu.be/abc12345678", "--dry-run"])
    assert cli.cmd_apply(args) == 0

    assert repo_root not in roots                     # no reviewable copy on a dry run
    assert seen["mode"] is not None                   # the scan saw a real file
    assert repo_root not in seen["target"].parents    # staged outside the repo
    assert not seen["target"].exists()                # and cleaned up afterwards


def test_a_real_run_scans_a_scratch_copy_not_the_repo(tmp_path, monkeypatch):
    """Scanning the repo copy made verdicts depend on the checkout's filesystem.

    A Windows drive in WSL reports every file as 0777, SkillSpector treats an
    executable SKILL.md as code, and the same skill scored 9 there and 0 elsewhere.
    """
    seen, roots, repo_root = _apply_harness(tmp_path, monkeypatch, "real-run-probe")
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    args = cli.build_parser().parse_args(["apply", "https://youtu.be/abc12345678"])
    assert cli.cmd_apply(args) == 0

    assert repo_root in roots                         # reviewable copy still written (D7)
    assert repo_root not in seen["target"].parents    # but it is not what gets scanned
    assert seen["mode"] & 0o111 == 0                  # the scanned copy is never executable
    assert not seen["target"].exists()                # scratch cleaned up


def test_no_terminal_to_answer_is_a_no_not_a_crash(tmp_path, monkeypatch, capsys):
    """Claude Code's `!` prefix gives no keyboard; the prompt used to crash on EOF."""
    _apply_harness(tmp_path, monkeypatch, "eof-probe")

    def no_keyboard(prompt=""):
        raise EOFError

    applied = []
    monkeypatch.setattr("builtins.input", no_keyboard)
    monkeypatch.setattr(cli, "apply_decision", lambda *a, **k: applied.append(a))
    args = cli.build_parser().parse_args(["apply", "https://youtu.be/abc12345678"])

    assert cli.cmd_apply(args) == 0
    assert applied == []
    assert "--yes" in capsys.readouterr().out


def _multi_harness(tmp_path, monkeypatch):
    """Three proposals — skill, clone, manual — with applies faked and counted."""
    from self_learning_agent.apply import AppliedRecord
    from self_learning_agent.ledger import Ledger
    from self_learning_agent.scanner import ScanVerdict

    cfg = Config(home=tmp_path / "home")
    store = cfg.home / "proposals" / "abc12345678.json"
    store.parent.mkdir(parents=True)
    store.write_text(json.dumps({
        "source_id": "abc12345678",
        "note_path": None,
        "proposals": [
            {"id": "p1", "kind": "skill", "title": "a skill",
             "action": {"name": "multi-probe", "content": "# x"}},
            {"id": "p2", "kind": "repo_clone", "title": "a clone",
             "action": {"repo": "a/b"}},
            {"id": "p3", "kind": "manual", "title": "by hand",
             "action": {"detail": "d"}},
        ],
    }), encoding="utf-8")
    Ledger(cfg.ledger_path).record("youtube", "abc12345678", title="The title")
    monkeypatch.setattr(cli.config_mod, "load", lambda: cfg)

    class _Source:
        source_type = "youtube"

        def __init__(self, *a, **k):
            pass

        def resolve(self, ref, limit=1):
            return ["abc12345678"]

    repo_root = Path(cli.__file__).resolve().parents[2]
    real_stage = cli.stage_skill
    monkeypatch.setattr(cli, "YouTubeSource", _Source)
    monkeypatch.setattr(cli, "stage_skill", lambda p, root: real_stage(
        p, tmp_path / "repo" if Path(root) == repo_root else root))
    monkeypatch.setattr(cli.scanner_mod, "available", lambda: True)
    monkeypatch.setattr(cli.scanner_mod, "scan", lambda target, use_llm=True: ScanVerdict(
        str(target), 0, "LOW", "CAUTION", (), False, True))

    calls = []

    def fake_apply(decision, cfg_, repo):
        calls.append(decision.proposal.id)
        return AppliedRecord(decision.proposal.id, decision.proposal.title, True, "done")

    monkeypatch.setattr(cli, "apply_decision", fake_apply)
    return cfg, store, calls


def _run_apply(*extra):
    args = cli.build_parser().parse_args(["apply", "https://youtu.be/abc12345678", *extra])
    assert cli.cmd_apply(args) == 0


def test_status_stays_partial_while_another_proposal_awaits_review(tmp_path, monkeypatch):
    """Approving p1 alone used to mark the whole video "applied" with p2 never seen."""
    from self_learning_agent.ledger import Ledger

    cfg, store, _ = _multi_harness(tmp_path, monkeypatch)
    _run_apply("--only", "p1", "--yes")

    row = Ledger(cfg.ledger_path).all()[0]
    assert row["status"] == "partial"
    assert row["title"] == "The title"            # the update no longer erases it
    assert json.loads(store.read_text())["applied"] == ["p1"]


def test_status_is_applied_once_nothing_automatable_is_waiting(tmp_path, monkeypatch):
    from self_learning_agent.ledger import Ledger

    cfg, _, _ = _multi_harness(tmp_path, monkeypatch)
    _run_apply("--only", "p1,p2", "--yes")          # p3 is manual: never waiting
    assert Ledger(cfg.ledger_path).all()[0]["status"] == "applied"


def test_an_applied_proposal_is_not_offered_again(tmp_path, monkeypatch, capsys):
    _, _, calls = _multi_harness(tmp_path, monkeypatch)
    _run_apply("--only", "p1", "--yes")
    capsys.readouterr()
    _run_apply("--only", "p1", "--yes")

    assert calls == ["p1"]                          # applied once, not twice
    out = capsys.readouterr().out
    assert "already applied: p1" in out
    assert "nothing to apply" in out

