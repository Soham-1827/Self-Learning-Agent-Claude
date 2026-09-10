"""Config loading and note rendering — the paths a wrong result would be silent in."""

import json
import subprocess
from pathlib import Path

import pytest

from self_learning_agent import config as config_mod
from self_learning_agent import scanner as scanner_mod
from self_learning_agent.config import Config, discover_ytdlp, load
from self_learning_agent.sources.youtube import YouTubeSource
from self_learning_agent.synthesis import parse_result
from self_learning_agent.vault import render


# -- config ------------------------------------------------------------


def test_defaults_work_with_no_config_file(tmp_path):
    cfg = load(home=tmp_path)
    assert cfg.vault_subdir == "Sources"
    assert cfg.install_mode == "copy"


def test_json_config_is_read(tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps({"vault_path": "/vault", "install_mode": "symlink"}), encoding="utf-8"
    )
    cfg = load(home=tmp_path)
    assert cfg.vault_path == Path("/vault")
    assert cfg.install_mode == "symlink"


def test_json_wins_over_toml(tmp_path):
    (tmp_path / "config.json").write_text('{"vault_subdir": "FromJson"}', encoding="utf-8")
    (tmp_path / "config.toml").write_text('vault_subdir = "FromToml"', encoding="utf-8")
    assert load(home=tmp_path).vault_subdir == "FromJson"


def test_toml_config_is_read_when_a_parser_exists(tmp_path):
    (tmp_path / "config.toml").write_text('vault_subdir = "FromToml"', encoding="utf-8")
    assert load(home=tmp_path).vault_subdir == "FromToml"


def test_an_unreadable_toml_raises_instead_of_silently_defaulting(tmp_path, monkeypatch):
    """Falling back to defaults would write notes into the wrong vault."""
    (tmp_path / "config.toml").write_text('vault_subdir = "x"', encoding="utf-8")
    monkeypatch.setattr(config_mod, "_read_toml", lambda p: None)
    with pytest.raises(RuntimeError, match="no TOML parser"):
        load(home=tmp_path)


def test_derived_paths_hang_off_home(tmp_path):
    cfg = Config(home=tmp_path)
    assert cfg.cache_dir.parent == tmp_path
    assert cfg.ledger_path.parent == tmp_path


def test_ytdlp_override_is_honoured(monkeypatch):
    monkeypatch.setenv("SLA_YTDLP", "/custom/yt-dlp --flag")
    assert discover_ytdlp() == ("/custom/yt-dlp", "--flag")


def test_resolved_fills_in_the_discovered_command():
    cfg = Config(ytdlp_cmd=("already", "set"))
    assert cfg.resolved().ytdlp_cmd == ("already", "set")


# -- note rendering ----------------------------------------------------


def _doc(meta, captions):
    return YouTubeSource(Config(ytdlp_cmd=("true",)))._build("9_SZFIW7tus", meta, captions)


def test_a_package_proposal_shows_the_rendered_command(meta, captions):
    r = parse_result({"source_id": "9_SZFIW7tus", "proposals": [
        {"kind": "package", "title": "Install it",
         "action": {"manager": "npm", "name": "@playwright/mcp"}}]})
    text = render(_doc(meta, captions), r)
    assert "npm install -g @playwright/mcp" in text
    assert "installs from an allowlisted registry" in text


def test_secrets_are_named_but_never_valued(meta, captions):
    r = parse_result({"source_id": "9_SZFIW7tus", "proposals": [
        {"kind": "package", "title": "t", "requires_secret": ["OPENAI_API_KEY"],
         "action": {"manager": "npm", "name": "pkg"}}]})
    text = render(_doc(meta, captions), r)
    assert "OPENAI_API_KEY" in text
    assert "never handled here" in text


def test_rejected_proposals_are_shown_in_the_note(meta, captions):
    r = parse_result({"source_id": "9_SZFIW7tus", "proposals": [
        {"kind": "package", "title": "bad", "action": {"manager": "bash", "name": "x"}}]})
    text = render(_doc(meta, captions), r)
    assert "Rejected during validation" in text


def test_already_installed_is_surfaced_in_the_note(meta, captions):
    r = parse_result({"source_id": "9_SZFIW7tus", "proposals": [
        {"kind": "package", "title": "t", "already_have": "brand-voice",
         "action": {"manager": "npm", "name": "pkg"}}]})
    assert "brand-voice" in render(_doc(meta, captions), r)


def test_techniques_and_ideas_render(meta, captions):
    r = parse_result({
        "source_id": "9_SZFIW7tus",
        "techniques": [{"name": "A technique", "what": "does a thing",
                        "when": "sometimes", "why": "because"}],
        "project_ideas": [{"title": "An idea", "what": "build it",
                           "why_interesting": "novel", "stack": "python",
                           "first_step": "run it", "size": "weekend"}],
    })
    text = render(_doc(meta, captions), r)
    assert "A technique" in text and "**When:**" in text
    assert "An idea" in text and "**First step:**" in text


def test_evidence_timestamps_are_rendered(meta, captions):
    r = parse_result({"source_id": "9_SZFIW7tus", "proposals": [
        {"kind": "manual", "title": "t", "action": {"detail": "d"},
         "evidence": {"quote": "they said this", "timestamp": "15:15"}}]})
    text = render(_doc(meta, captions), r)
    assert "(15:15)" in text and "they said this" in text


# -- scanner subprocess boundary ---------------------------------------


class _Proc:
    def __init__(self, code, out="", err=""):
        self.returncode, self.stdout, self.stderr = code, out, err


def test_scan_parses_a_successful_run(monkeypatch, tmp_path):
    payload = {"risk_assessment": {"score": 5, "severity": "LOW", "recommendation": "SAFE"},
               "issues": [], "metadata": {"llm_requested": True, "llm_available": True}}
    monkeypatch.setattr(scanner_mod, "find_scanner", lambda: "/bin/skillspector")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(0, json.dumps(payload)))
    v = scanner_mod.scan(tmp_path)
    assert v.score == 5 and v.recommendation == "SAFE"


def test_scan_raises_on_scanner_error_rather_than_returning_a_pass(monkeypatch, tmp_path):
    monkeypatch.setattr(scanner_mod, "find_scanner", lambda: "/bin/skillspector")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(2, "", "bad input"))
    with pytest.raises(RuntimeError, match="bad input"):
        scanner_mod.scan(tmp_path)


def test_scan_raises_on_unparseable_output(monkeypatch, tmp_path):
    monkeypatch.setattr(scanner_mod, "find_scanner", lambda: "/bin/skillspector")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(0, "not json"))
    with pytest.raises(RuntimeError, match="unparseable"):
        scanner_mod.scan(tmp_path)


def test_missing_scanner_raises_a_named_error(monkeypatch, tmp_path):
    monkeypatch.setattr(scanner_mod, "find_scanner", lambda: None)
    with pytest.raises(scanner_mod.ScannerUnavailable):
        scanner_mod.scan(tmp_path)


def test_no_llm_flag_is_passed_through(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return _Proc(0, json.dumps({"risk_assessment": {"recommendation": "SAFE"},
                                    "metadata": {}}))

    monkeypatch.setattr(scanner_mod, "find_scanner", lambda: "/bin/skillspector")
    monkeypatch.setattr(subprocess, "run", fake_run)
    scanner_mod.scan(tmp_path, use_llm=False)
    assert "--no-llm" in seen["cmd"]
