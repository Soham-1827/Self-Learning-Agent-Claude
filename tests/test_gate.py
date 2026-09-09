"""The gate decides what may run. Every path that could permit something is tested."""

import pytest

from self_learning_agent.gate import (
    BLOCK,
    CONFIRM,
    SCAN_CAN_BLOCK,
    decide,
    requires_scan,
    summarise,
)
from self_learning_agent.proposals import parse
from self_learning_agent.scanner import Issue, ScanVerdict


def _skill():
    return parse({"kind": "skill", "title": "t",
                  "action": {"name": "my-skill", "content": "# x"}})


def _clone():
    return parse({"kind": "repo_clone", "title": "t",
                  "action": {"repo": "a/b", "host": "github.com"}})


def _package():
    return parse({"kind": "package", "title": "t",
                  "action": {"manager": "npm", "name": "pkg"}})


def _verdict(**over):
    base = dict(
        target="x", score=0, severity="LOW", recommendation="CAUTION",
        issues=(), llm_requested=True, llm_available=True,
    )
    base.update(over)
    return ScanVerdict(**base)


# -- nothing is ever applied without a human ---------------------------


@pytest.mark.parametrize("proposal", [_skill(), _clone(), _package()])
def test_nothing_is_auto_allowed(proposal):
    d = decide(proposal, _verdict())
    assert d.action in (CONFIRM, BLOCK)
    assert d.action != "allow"


# -- blocking paths ----------------------------------------------------


def test_high_risk_is_always_blocked():
    manual = parse({"kind": "manual", "title": "t", "action": {"detail": "d"}})
    assert decide(manual).action == BLOCK


def test_secrets_block_and_say_so():
    p = parse({"kind": "package", "title": "t",
               "action": {"manager": "npm", "name": "pkg"},
               "requires_secret": ["OPENAI_API_KEY"]})
    d = decide(p)
    assert d.action == BLOCK
    assert "OPENAI_API_KEY" in d.reasons[0]


def test_unscanned_scannable_content_is_blocked():
    assert decide(_skill(), None).action == BLOCK


def test_missing_scanner_blocks_scannable_content():
    d = decide(_skill(), None, scanner_available=False)
    assert d.action == BLOCK
    assert "not installed" in d.reasons[0]


def test_a_failed_scan_blocks_rather_than_passing():
    d = decide(_skill(), None, scan_error="network unreachable")
    assert d.action == BLOCK
    assert "scan failed" in d.reasons[0]


def test_blocking_verdict_blocks_skill_activation():
    bad = _verdict(score=78, severity="HIGH", recommendation="DO_NOT_INSTALL",
                   issues=(Issue("E2", "HIGH", "exfil", "env harvesting"),))
    assert decide(_skill(), bad).action == BLOCK


# -- the download / activation distinction -----------------------------


def test_only_activation_can_be_blocked_by_a_scan():
    assert SCAN_CAN_BLOCK == {"skill"}


def test_blocking_verdict_does_not_block_a_clone():
    """Cloning to staging is how you inspect something.

    Nothing executes on clone, so blocking it would prevent the review that
    staging exists for. Scanning a full app repo with a skill scanner scores
    CRITICAL off false positives, and a gate that blocks on that gets disabled.
    """
    bad = _verdict(score=100, severity="CRITICAL", recommendation="DO_NOT_INSTALL",
                   issues=(Issue("PE3", "HIGH", "priv", "credential access"),))
    d = decide(_clone(), bad)
    assert d.action == CONFIRM
    assert any("nothing is executed" in r for r in d.reasons)


def test_a_blocking_verdict_is_stated_once_not_twice():
    bad = _verdict(score=100, severity="CRITICAL", recommendation="DO_NOT_INSTALL",
                   issues=(Issue("PE3", "HIGH", "priv", "x"),))
    reasons = decide(_clone(), bad).reasons
    assert sum("DO_NOT_INSTALL" in r for r in reasons) == 1


# -- degraded scans ----------------------------------------------------


def test_a_degraded_scan_is_flagged_as_weak_evidence():
    degraded = _verdict(llm_requested=True, llm_available=False)
    d = decide(_skill(), degraded)
    assert d.action == CONFIRM
    assert any("weak evidence" in r for r in d.reasons)


def test_static_only_scan_is_labelled():
    static = _verdict(llm_requested=False, llm_available=True)
    assert any("static-only" in r for r in decide(_skill(), static).reasons)


# -- unscannable kinds -------------------------------------------------


def test_registry_packages_are_not_scanned_but_say_so():
    assert not requires_scan(_package())
    assert any("cannot be scanned" in r for r in decide(_package()).reasons)


def test_already_installed_is_surfaced():
    p = parse({"kind": "package", "title": "t", "already_have": "brand-voice",
               "action": {"manager": "npm", "name": "pkg"}})
    assert any("brand-voice" in r for r in decide(p).reasons)


def test_summarise_counts_actions():
    manual = parse({"kind": "manual", "title": "t", "action": {"detail": "d"}})
    out = summarise([decide(manual), decide(_package())])
    assert out == {"total": 2, "blocked": 1, "needs_confirmation": 1, "auto_allowed": 0}
