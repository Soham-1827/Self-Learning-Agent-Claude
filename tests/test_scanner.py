"""Scanner wrapper: a scan that did not fully run must never read as clean."""

import pytest

from self_learning_agent.scanner import ScanVerdict, _parse, _resolve


def _payload(**over):
    base = {
        "skill": {"name": "x"},
        "risk_assessment": {"score": 0, "severity": "LOW", "recommendation": "SAFE"},
        "issues": [],
        "metadata": {"llm_requested": True, "llm_available": True},
    }
    base.update(over)
    return base


def test_parses_a_clean_verdict():
    v = _parse(_payload(), "x")
    assert v.score == 0 and v.recommendation == "SAFE"
    assert v.llm_ran and not v.degraded and not v.blocks


def test_llm_available_but_not_requested_is_not_a_semantic_scan():
    """--no-llm means semantic analysis did not run, however available it was."""
    v = _parse(_payload(metadata={"llm_requested": False, "llm_available": True}), "x")
    assert not v.llm_ran
    assert v.scan_mode == "static-only"
    assert not v.degraded  # not asked for, so not degraded


def test_requested_but_unavailable_llm_is_degraded():
    v = _parse(_payload(metadata={"llm_requested": True, "llm_available": False}), "x")
    assert v.degraded
    assert "unavailable" in v.scan_mode


def test_a_missing_recommendation_is_treated_as_blocking():
    """An unparseable verdict must fail closed, never open."""
    v = _parse(_payload(risk_assessment={"score": 0}), "x")
    assert v.recommendation == "DO_NOT_INSTALL"
    assert v.blocks


def test_findings_are_ordered_worst_first():
    v = _parse(_payload(issues=[
        {"id": "L", "severity": "LOW", "category": "c"},
        {"id": "C", "severity": "CRITICAL", "category": "c"},
        {"id": "M", "severity": "MEDIUM", "category": "c"},
    ]), "x")
    assert [i.id for i in v.worst()] == ["C", "M", "L"]


def test_urls_are_passed_through_unresolved():
    assert _resolve("https://github.com/a/b") == "https://github.com/a/b"


def test_local_symlinks_are_resolved(tmp_path):
    """SkillSpector refuses symlinked input; 32 real skills here are symlinks."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    assert _resolve(str(link)) == str(real.resolve())
