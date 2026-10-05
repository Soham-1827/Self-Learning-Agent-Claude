"""The published examples: the evidence a visitor sees before installing anything.

Nobody installs a CLI to find out what it does, so `examples/` is the argument the
README makes and the notes are the evidence for it. That makes a stale claim here
more expensive than anywhere else in the repo, and the failure mode is the one
PLAN §29 named: not a wrong statement, an *absent check*.

So: every link resolves, every file is indexed, every number in the index tables is
the real one, and every proposal published as evidence for §8 Rule 1 still survives
the validator that makes Rule 1 true.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

from self_learning_agent.proposals import ALLOWED_MANAGERS, parse_all, render_command

MD_LINK = re.compile(r"\[(?:[^\]]*)\]\(([^)\s]+)\)")

# The only programs a proposal is ever allowed to turn into.
EXECUTABLES = {"git"} | set(ALLOWED_MANAGERS)
SHELL_METACHARS = re.compile(r"[;&|`$><\n\r\\'\"(){}\[\]*?#~]")


def _repo_root() -> Path | None:
    """The checkout, or None when the tests run against an installed package."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude-plugin" / "plugin.json").is_file():
            return parent
    return None


@pytest.fixture
def examples() -> Path:
    repo = _repo_root()
    if repo is None:
        pytest.skip("not running from a checkout — no examples/ to check")
    directory = repo / "examples"
    if not directory.is_dir():
        pytest.skip("no examples/ in this checkout")
    return directory


def _index(examples: Path) -> str:
    return (examples / "README.md").read_text(encoding="utf-8")


def _published_files(examples: Path) -> list[Path]:
    return sorted(
        path
        for path in examples.rglob("*")
        if path.is_file() and path.name != "README.md"
    )


def _frontmatter(note: Path) -> dict[str, str]:
    lines = note.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"')
    return fields


def _notes_with_proposals(examples: Path) -> list[tuple[Path, Path]]:
    """Each note paired with the proposals file `sla apply` would read for it."""
    pairs = []
    for note in sorted((examples / "notes").glob("*.md")):
        source_id = _frontmatter(note).get("source_id")
        if source_id:
            pairs.append((note, examples / "proposals" / f"{source_id}.json"))
    return pairs


# --------------------------------------------------------------------------- links


def test_every_link_into_the_examples_resolves(examples: Path):
    """A renamed note must not leave a dead link in the page that sells it."""
    repo = examples.parent
    checked = 0
    for page, base in ((examples / "README.md", examples), (repo / "README.md", repo)):
        for target in MD_LINK.findall(page.read_text(encoding="utf-8")):
            path = unquote(target.split("#", 1)[0])
            if not path or "://" in path:
                continue
            resolved = (base / path).resolve()
            if examples not in resolved.parents and resolved != examples:
                continue  # a link to something outside examples/; not ours to police
            assert resolved.exists(), f"{page.name} links to a missing {path}"
            checked += 1
    assert checked >= len(_published_files(examples))


def test_the_index_links_outward_without_breaking(examples: Path):
    """`examples/README.md` points back at the README, PLAN, and the skill."""
    repo = examples.parent
    for target in MD_LINK.findall(_index(examples)):
        path = unquote(target.split("#", 1)[0])
        if not path.startswith("../"):
            continue
        assert (examples / path).resolve().exists(), f"index links to a missing {path}"


def test_the_main_readme_sends_a_visitor_to_the_examples(examples: Path):
    """The whole point of §29 item 1: reachable from the landing page, not buried."""
    readme = (examples.parent / "README.md").read_text(encoding="utf-8")
    assert "(examples/)" in readme


# --------------------------------------------------------------------------- index


def test_every_published_file_is_indexed(examples: Path):
    """Adding a note without listing it is how an index starts lying by omission.

    Compared after decoding, so the check does not depend on how a link happens
    to be percent-encoded.
    """
    linked = {
        (examples / unquote(target.split("#", 1)[0])).resolve()
        for target in MD_LINK.findall(_index(examples))
        if "://" not in target
    }
    for path in _published_files(examples):
        assert path.resolve() in linked, f"{path.name} is not linked from the index"


def test_each_note_has_the_proposals_file_apply_would_read(examples: Path):
    pairs = _notes_with_proposals(examples)
    assert pairs, "no notes with a source_id"
    for note, store in pairs:
        assert store.is_file(), f"{note.name} has no {store.name}"

    paired = {store for _, store in pairs}
    orphans = set((examples / "proposals").glob("*.json")) - paired
    assert not orphans, f"proposals with no note: {sorted(p.name for p in orphans)}"


@pytest.mark.parametrize("column", ["Proposals", "Ideas"])
def test_the_numbers_in_the_index_tables_are_the_real_ones(examples: Path, column: str):
    """Counts are quoted in two READMEs. Both are checked against the files."""
    repo = examples.parent
    counted = 0
    for page, base in ((examples / "README.md", examples), (repo / "README.md", repo)):
        for note, claimed in _claimed_counts(page, base, examples, column):
            actual = (
                len(json.loads(_store_for(note, examples).read_text("utf-8"))["proposals"])
                if column == "Proposals"
                else _idea_count(note)
            )
            assert claimed == actual, (
                f"{page.name} claims {claimed} {column.lower()} for {note.name}, "
                f"the file has {actual}"
            )
            counted += 1
    assert counted >= 6, f"only {counted} {column} cells checked"


def _store_for(note: Path, examples: Path) -> Path:
    return examples / "proposals" / f"{_frontmatter(note)['source_id']}.json"


def _idea_count(note: Path) -> int:
    ideas, inside = 0, False
    for line in note.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Project ideas"
        elif inside and line.startswith("### "):
            ideas += 1
    return ideas


def _claimed_counts(page: Path, base: Path, examples: Path, column: str):
    """Yield (note, number) for each table row quoting `column` for a real note."""
    index_of = None
    for line in page.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            index_of = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        headers = [c.strip("* ") for c in cells]
        if column in headers:
            index_of = headers.index(column)
            continue
        if index_of is None or index_of >= len(cells):
            continue
        links = MD_LINK.findall(cells[0])
        if not links:
            continue
        note = (base / unquote(links[0])).resolve()
        if not note.is_file() or not _frontmatter(note).get("source_id"):
            continue  # the digest row, or a link to something else
        if not _store_for(note, examples).is_file():
            continue
        number = cells[index_of].strip("* ").replace(",", "")
        if number.isdigit():
            yield note, int(number)


# ------------------------------------------------------------------ §8 Rule 1 holds


def test_every_published_proposal_still_validates(examples: Path):
    """These files are published as evidence. The validator must still accept them.

    If the schema tightens and this goes red, the repo is shipping proof of a
    contract its own code no longer honours.
    """
    for store in sorted((examples / "proposals").glob("*.json")):
        raw = json.loads(store.read_text(encoding="utf-8"))["proposals"]
        parsed, rejected = parse_all(raw)
        assert not rejected, f"{store.name}: {rejected}"
        assert len(parsed) == len(raw), f"{store.name} lost a proposal in validation"


def test_no_published_proposal_can_become_an_arbitrary_command(examples: Path):
    """§8 Rule 1, asserted against the exact bytes the README offers as proof."""
    rendered = 0
    for store in sorted((examples / "proposals").glob("*.json")):
        raw = json.loads(store.read_text(encoding="utf-8"))["proposals"]
        parsed, _ = parse_all(raw)
        for proposal in parsed:
            command = render_command(proposal)
            if command is None:
                continue  # manual, or a skill — nothing is ever executed
            assert command[0] in EXECUTABLES, f"{store.name} renders {command[0]!r}"
            for part in command:
                assert not SHELL_METACHARS.search(part), f"{store.name}: {part!r}"
            rendered += 1
    assert rendered, "no example renders a command; this test would pass vacuously"


def test_every_quote_in_the_index_is_verbatim(examples: Path):
    """The index argues from quotations, so a paraphrase there is a fabrication.

    Compared with whitespace collapsed, since the index rewraps what the notes
    write on one line.
    """
    corpus = " ".join(
        " ".join(path.read_text(encoding="utf-8").split())
        for path in sorted((examples / "notes").glob("*.md"))
    )
    quotes, current = [], []
    for line in _index(examples).splitlines():
        if line.startswith(">"):
            current.append(line[1:].strip())
        elif current:
            quotes.append(" ".join(current))
            current = []
    if current:
        quotes.append(" ".join(current))

    assert len(quotes) >= 5, f"only {len(quotes)} quotes found to check"
    for quote in quotes:
        needle = " ".join(quote.split()).strip("`")
        assert needle in corpus, f"not found verbatim in any note: {needle[:90]!r}"
