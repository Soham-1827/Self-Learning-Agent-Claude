"""Link extraction is the load-bearing part of I1.

ASR renders "SkillSpector" as "Skill Specter"; the description holds the real
URL. If casing or slugs break here, every downstream lookup searches for a
repo that does not exist.
"""

from self_learning_agent.models import Link
from self_learning_agent.sources.youtube import extract_links


def test_extracts_every_github_repo_from_a_real_description(description):
    repos = {link.repo_slug for link in extract_links(description) if link.repo_slug}
    assert repos == {
        "petergyang/no-ai-slop",
        "trycompai/crm",
        "browser-use/video-use",
        "NVIDIA/SkillSpector",
        "ShawnPana/phone-harness",
    }


def test_preserves_casing_that_asr_destroys(description):
    slugs = [link.repo_slug for link in extract_links(description)]
    assert "NVIDIA/SkillSpector" in slugs
    assert "nvidia/skillspector" not in slugs


def test_captures_the_human_written_label(description):
    labelled = {
        link.repo_slug: link.label
        for link in extract_links(description)
        if link.repo_slug
    }
    assert labelled["NVIDIA/SkillSpector"] == "NVIDIA SkillSpector"


def test_deduplicates_urls_repeated_in_the_description(description):
    links = extract_links(description)
    assert len({link.url for link in links}) == len(links)


def test_strips_trailing_sentence_punctuation():
    links = extract_links("See https://github.com/a/b.")
    assert links[0].url == "https://github.com/a/b"


def test_empty_description_is_not_an_error():
    assert extract_links(None) == ()
    assert extract_links("") == ()


def test_non_github_url_has_no_repo_slug():
    assert Link("https://www.ideabrowser.com").repo_slug is None


def test_github_url_without_repo_name_has_no_slug():
    assert Link("https://github.com/NVIDIA").repo_slug is None
