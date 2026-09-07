"""Inventory is what stops the pipeline proposing things you already have."""

from pathlib import Path

from self_learning_agent.inventory import (
    Inventory,
    InstalledMcp,
    InstalledSkill,
    collect_mcp_servers,
    collect_skills,
    parse_frontmatter,
)


def _skill_tree(root: Path, name: str, description: str = "") -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    body = f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n"
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    return d


def test_parses_flat_frontmatter():
    meta = parse_frontmatter('---\nname: x\ndescription: "a: b"\n---\nbody\n')
    assert meta["name"] == "x"
    assert meta["description"] == "a: b"


def test_missing_frontmatter_is_not_an_error():
    assert parse_frontmatter("# just a heading\n") == {}


def test_finds_skills_behind_symlinked_directories(tmp_path: Path):
    """Regression: 32 of 224 real skills were hidden by this.

    Path.rglob does not descend into symlinked directories.
    """
    home = tmp_path / "claude"
    skills = home / "skills"
    skills.mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    _skill_tree(elsewhere, "linked-skill", "lives outside the skills dir")
    (skills / "linked-skill").symlink_to(elsewhere / "linked-skill")
    _skill_tree(skills, "normal-skill")

    found, errors = collect_skills(claude_home=home)
    assert {s.name for s in found} == {"linked-skill", "normal-skill"}
    assert errors == []


def test_symlink_cycle_does_not_hang(tmp_path: Path):
    home = tmp_path / "claude"
    skills = home / "skills"
    skills.mkdir(parents=True)
    _skill_tree(skills, "real")
    (skills / "loop").symlink_to(skills)  # points at its own ancestor

    found, _ = collect_skills(claude_home=home)
    assert "real" in {s.name for s in found}


def test_user_skills_shadow_plugin_copies(tmp_path: Path):
    home = tmp_path / "claude"
    _skill_tree(home / "skills", "dup", "the user copy")
    _skill_tree(home / "plugins" / "cache" / "p" / "skills", "dup", "the plugin copy")

    found, _ = collect_skills(claude_home=home)
    dup = [s for s in found if s.name == "dup"]
    assert len(dup) == 1
    assert dup[0].origin == "user"


def test_reads_mcp_servers_from_config(tmp_path: Path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(
        '{"mcpServers": {"playwright": {"command": "npx", "args": ["-y", "@pw/mcp"]}}}',
        encoding="utf-8",
    )
    servers, errors = collect_mcp_servers([cfg])
    assert servers[0].name == "playwright"
    assert servers[0].command == "npx -y @pw/mcp"
    assert errors == []


def test_malformed_mcp_config_is_reported_not_raised(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    servers, errors = collect_mcp_servers([bad])
    assert servers == []
    assert len(errors) == 1


def test_absent_config_files_are_silently_skipped(tmp_path: Path):
    servers, errors = collect_mcp_servers([tmp_path / "nope.json"])
    assert servers == [] and errors == []


def _inv(*pairs) -> Inventory:
    return Inventory(
        skills=tuple(
            InstalledSkill(n, d, Path("/x"), "user") for n, d in pairs
        )
    )


def test_exact_lookups_are_case_and_punctuation_insensitive():
    inv = Inventory(
        skills=(InstalledSkill("brand-voice", "", Path("/x"), "user"),),
        mcp_servers=(InstalledMcp("playwright", "npx", Path("/y")),),
    )
    assert inv.has_skill("Brand Voice")
    assert inv.has_skill("brand_voice")
    assert inv.has_mcp("Playwright")
    assert inv.has_skill("nonexistent") is None


def test_similar_skills_surfaces_an_overlapping_skill():
    inv = _inv(
        ("security-scan", "scan code for vulnerabilities, injection and secrets"),
        ("remotion-video", "render videos programmatically with react"),
    )
    hits = inv.similar_skills("scan skills for injection and malicious secrets")
    assert hits and hits[0][0].name == "security-scan"


def test_similar_skills_returns_nothing_for_unrelated_text():
    inv = _inv(("remotion-video", "render videos programmatically with react"))
    assert inv.similar_skills("negotiate freight rates with carriers") == ()


def test_empty_query_is_not_a_match():
    assert _inv(("a", "b c d")).similar_skills("") == ()


def test_summary_counts_by_origin():
    inv = Inventory(
        skills=(
            InstalledSkill("a", "", Path("/x"), "user"),
            InstalledSkill("b", "", Path("/x"), "plugin"),
        )
    )
    assert inv.summary()["skills_by_origin"] == {"plugin": 1, "user": 1}
