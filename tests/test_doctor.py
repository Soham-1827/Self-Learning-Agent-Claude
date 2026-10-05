"""`sla doctor`: every check here exists because something shipped broken.

- A hand-copied skill went stale for three weeks and kept teaching a superseded
  procedure (§26).
- The plugin cache is version-gated, so a repo edit reached nobody (§28).
- `sla --version` reported 0.1.0 for two releases (§29).
- A staged skill landed *inside the installed venv*, in no repository, deleted by
  the next upgrade (§28).
- SkillSpector has three honest states and a new user starts in the one where
  skill proposals are refused.

Each was silent. The point of this command is that each becomes a line.
"""

from __future__ import annotations

import json

import pytest

from self_learning_agent.config import Config
from self_learning_agent.doctor import FAIL, INFO, OK, WARN, run_checks, worst


def _cfg(tmp_path, **kw) -> Config:
    return Config(
        home=tmp_path / "home",
        vault_path=tmp_path / "vault",
        generated_skills_path=tmp_path / "staged",
        **kw,
    )


def _plugin(claude_home, version, *, marketplace="self-learning-agent"):
    """A cached plugin, laid out the way Claude Code actually caches one."""
    d = (claude_home / "plugins" / "cache" / marketplace / "self-learning-agent"
         / version / ".claude-plugin")
    d.mkdir(parents=True, exist_ok=True)
    (d / "plugin.json").write_text(
        json.dumps({"name": "self-learning-agent", "version": version}),
        encoding="utf-8",
    )


def _find(checks, fragment):
    matches = [c for c in checks if fragment.lower() in c.label.lower()]
    assert matches, f"no check labelled like {fragment!r} in {[c.label for c in checks]}"
    return matches[0]


# ------------------------------------------------------------------ versions


def test_matching_cli_and_plugin_versions_are_ok(tmp_path):
    claude = tmp_path / ".claude"
    _plugin(claude, "9.9.9")
    checks = run_checks(_cfg(tmp_path), claude_home=claude, cli_version="9.9.9", ytdlp_version="2026.08.19")
    assert _find(checks, "plugin version").status == OK


def test_version_skew_is_flagged(tmp_path):
    """§28: the cache is version-gated, so skew means the agent reads old text."""
    claude = tmp_path / ".claude"
    _plugin(claude, "0.2.0")
    checks = run_checks(_cfg(tmp_path), claude_home=claude, cli_version="0.2.2", ytdlp_version="2026.08.19")
    skew = _find(checks, "plugin version")
    assert skew.status == WARN
    assert "0.2.0" in skew.value and "0.2.2" in (skew.note or "")


def test_the_newest_cached_plugin_version_is_the_one_reported(tmp_path):
    """Several versions accumulate in the cache; the newest is what loads."""
    claude = tmp_path / ".claude"
    for v in ("0.1.0", "0.2.2", "0.2.10", "0.2.1"):
        _plugin(claude, v)
    checks = run_checks(_cfg(tmp_path), claude_home=claude, cli_version="0.2.10", ytdlp_version="2026.08.19")
    assert "0.2.10" in _find(checks, "plugin version").value


def test_no_plugin_is_information_not_failure(tmp_path):
    """The CLI alone is a legitimate install — a Codex user has exactly this."""
    checks = run_checks(_cfg(tmp_path), claude_home=tmp_path / ".claude",
                        cli_version="0.2.2", ytdlp_version="2026.08.19")
    assert _find(checks, "plugin version").status == INFO


# --------------------------------------------------------------- §26 drift


def test_a_hand_copied_first_party_skill_is_flagged(tmp_path):
    """§26: a hand copy has no update path and silently goes stale."""
    claude = tmp_path / ".claude"
    _plugin(claude, "0.2.2")
    live = claude / "skills" / "learn-from-source"
    live.mkdir(parents=True)
    (live / "SKILL.md").write_text("stale", encoding="utf-8")

    check = _find(run_checks(_cfg(tmp_path), claude_home=claude, cli_version="0.2.2", ytdlp_version="2026.08.19"),
                  "hand-copied skill")
    assert check.status == WARN
    assert "learn-from-source" in check.value


def test_no_hand_copy_is_the_healthy_case(tmp_path):
    claude = tmp_path / ".claude"
    _plugin(claude, "0.2.2")
    check = _find(run_checks(_cfg(tmp_path), claude_home=claude, cli_version="0.2.2", ytdlp_version="2026.08.19"),
                  "hand-copied skill")
    assert check.status == OK


# -------------------------------------------------------------- the scanner


def test_no_scanner_warns_that_skill_proposals_are_blocked(tmp_path):
    checks = run_checks(_cfg(tmp_path), claude_home=tmp_path / ".claude",
                        cli_version="0.2.2", scanner=None, ytdlp_version="2026.08.19")
    check = _find(checks, "scanner")
    assert check.status == WARN
    assert "block" in (check.note or "").lower()


def test_a_scanner_without_a_provider_is_static_only(tmp_path):
    checks = run_checks(_cfg(tmp_path), claude_home=tmp_path / ".claude",
                        cli_version="0.2.2", scanner="/usr/bin/skillspector", env={}, ytdlp_version="2026.08.19")
    check = _find(checks, "scanner")
    assert check.status == WARN
    assert "static" in (check.note or "").lower()


def test_a_scanner_with_a_provider_and_key_is_ok(tmp_path):
    checks = run_checks(
        _cfg(tmp_path), claude_home=tmp_path / ".claude", cli_version="0.2.2",
        scanner="/usr/bin/skillspector",
        env={"SKILLSPECTOR_PROVIDER": "openai", "OPENAI_API_KEY": "x"},
        ytdlp_version="2026.08.19",
    )
    assert _find(checks, "scanner").status == OK


def test_a_provider_with_no_key_is_not_reported_as_ready(tmp_path):
    checks = run_checks(
        _cfg(tmp_path), claude_home=tmp_path / ".claude", cli_version="0.2.2",
        scanner="/usr/bin/skillspector", env={"SKILLSPECTOR_PROVIDER": "openai"},
        ytdlp_version="2026.08.19",
    )
    assert _find(checks, "scanner").status == WARN


def test_ollama_needs_no_key(tmp_path):
    """ollama runs locally, so demanding a key would be wrong."""
    checks = run_checks(
        _cfg(tmp_path), claude_home=tmp_path / ".claude", cli_version="0.2.2",
        scanner="/usr/bin/skillspector", env={"SKILLSPECTOR_PROVIDER": "ollama"},
        ytdlp_version="2026.08.19",
    )
    assert _find(checks, "scanner").status == OK


def test_no_secret_value_is_ever_printed(tmp_path):
    """Rule 4: secrets are never handled. A doctor report gets pasted into issues."""
    secret = "sk-do-not-print-this"
    checks = run_checks(
        _cfg(tmp_path), claude_home=tmp_path / ".claude", cli_version="0.2.2",
        scanner="/usr/bin/skillspector",
        env={"SKILLSPECTOR_PROVIDER": "openai", "OPENAI_API_KEY": secret},
        ytdlp_version="2026.08.19",
    )
    rendered = "\n".join(f"{c.label}{c.value}{c.note or ''}" for c in checks)
    assert secret not in rendered


# ----------------------------------------------------------------- yt-dlp


def test_missing_ytdlp_is_a_failure(tmp_path):
    """Nothing works without it — this is the one hard dependency."""
    checks = run_checks(_cfg(tmp_path), claude_home=tmp_path / ".claude",
                        cli_version="0.2.2", ytdlp_version=None)
    assert _find(checks, "yt-dlp").status == FAIL
    assert worst(checks) == FAIL


# ------------------------------------------------------- paths, and §28's bug


def test_a_staged_dir_inside_a_venv_is_a_failure(tmp_path):
    """§28: staging landed in the tool's own lib dir — invisible, and wiped on upgrade."""
    venv_staged = tmp_path / "venv" / "lib" / "python3.12" / "site-packages" / "generated-skills"
    venv_staged.mkdir(parents=True)
    cfg = Config(home=tmp_path / "home", vault_path=tmp_path / "vault",
                 generated_skills_path=venv_staged)
    check = _find(run_checks(cfg, claude_home=tmp_path / ".claude", cli_version="0.2.2", ytdlp_version="2026.08.19"),
                  "staged skills")
    assert check.status == FAIL
    assert "site-packages" in (check.note or "") or "venv" in (check.note or "")


def test_an_unwritable_vault_parent_is_reported(tmp_path):
    cfg = Config(home=tmp_path / "home", vault_path=tmp_path / "nope" / "vault",
                 generated_skills_path=tmp_path / "staged")
    check = _find(run_checks(cfg, claude_home=tmp_path / ".claude", cli_version="0.2.2", ytdlp_version="2026.08.19"),
                  "vault")
    assert check.status in (OK, WARN)  # created on first write; must not be a failure
    assert str(cfg.vault_path / cfg.vault_subdir) in check.value


# ------------------------------------------------------- harnesses (§31)


def test_the_detected_harnesses_are_listed(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (tmp_path / ".codex").mkdir()
    checks = run_checks(_cfg(tmp_path), claude_home=claude, cli_version="0.2.2",
                        home_dir=tmp_path, ytdlp_version="2026.08.19")
    value = _find(checks, "harness").value
    assert "claude" in value.lower() and "codex" in value.lower()


def test_no_harness_at_all_warns_rather_than_failing(tmp_path):
    """`sla` still produces notes; only the inventory goes empty."""
    checks = run_checks(_cfg(tmp_path), claude_home=tmp_path / "absent",
                        cli_version="0.2.2", home_dir=tmp_path, ytdlp_version="2026.08.19")
    assert _find(checks, "harness").status == WARN


# ----------------------------------------------------------------- summary


def test_worst_orders_failure_above_warning_above_ok():
    from self_learning_agent.doctor import Check

    assert worst([Check("a", "", OK)]) == OK
    assert worst([Check("a", "", OK), Check("b", "", WARN)]) == WARN
    assert worst([Check("a", "", WARN), Check("b", "", FAIL)]) == FAIL
    assert worst([Check("a", "", INFO)]) == OK
    assert worst([]) == OK


@pytest.mark.parametrize("version", ["0.2.2", "0+unknown"])
def test_an_unknown_cli_version_is_itself_a_finding(tmp_path, version):
    """§29: a tool wrong about its own version makes everything it says arguable."""
    checks = run_checks(_cfg(tmp_path), claude_home=tmp_path / ".claude",
                        cli_version=version, ytdlp_version="2026.08.19")
    check = _find(checks, "cli version")
    assert check.status == (WARN if version == "0+unknown" else OK)


# ------------------------------- the two false positives this check once had


def test_agents_skills_alone_does_not_mean_codex(tmp_path):
    """`$HOME/.agents/skills` is a vendor-neutral path (§31).

    It exists on the development machine, which has no Codex installed, and the
    first version of this check reported Codex as detected because of it.
    """
    claude = tmp_path / ".claude"
    claude.mkdir()
    (tmp_path / ".agents" / "skills").mkdir(parents=True)
    checks = run_checks(_cfg(tmp_path), claude_home=claude, cli_version="0.2.2",
                        home_dir=tmp_path, ytdlp_version="2026.08.19")
    assert "codex" not in _find(checks, "harness").value.lower()


def test_a_codex_home_does_mean_codex(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (tmp_path / ".codex").mkdir()
    checks = run_checks(_cfg(tmp_path), claude_home=claude, cli_version="0.2.2",
                        home_dir=tmp_path, ytdlp_version="2026.08.19")
    assert "codex" in _find(checks, "harness").value.lower()


def test_ytdlp_is_found_when_it_is_only_importable(tmp_path):
    """Not on PATH, but runnable as a module — which is how the fetch path runs it.

    The first version of this check used `shutil.which` and reported "not found"
    on a machine where yt-dlp was installed and working.
    """
    import sys

    from self_learning_agent.doctor import _ytdlp_version

    cfg = Config(home=tmp_path / "home", vault_path=tmp_path / "vault",
                 generated_skills_path=tmp_path / "staged",
                 ytdlp_cmd=(sys.executable, "-m", "yt_dlp"))
    assert _ytdlp_version(cfg) is not None


def test_a_broken_ytdlp_command_reports_not_found_rather_than_raising(tmp_path):
    cfg = Config(home=tmp_path / "home", vault_path=tmp_path / "vault",
                 generated_skills_path=tmp_path / "staged",
                 ytdlp_cmd=(str(tmp_path / "no-such-binary"),))
    from self_learning_agent.doctor import _ytdlp_version

    assert _ytdlp_version(cfg) is None
