"""Platform assumptions, and the two bugs the macOS/Windows matrix found.

The project had only ever run on WSL. Adding macOS and Windows to CI failed five
tests on Windows on the first run, from two causes:

1. `Path.write_text` opens in text mode, which translates `\n` to `os.linesep`.
   The staged `SKILL.md` on Windows therefore never held the bytes that were
   scanned, and `_unscanned_changes` compares raw bytes — so `sla apply` refused
   to activate **any** skill, reporting the staged copy as "changed after it was
   scanned". A failure wearing tampering's clothes, which is rule 12 inverted.
2. Tests calling `read_text()` with no encoding. Windows decodes as cp1252, so
   a digest containing `·` and `—` came back as mojibake and an assertion on
   `"· applied ·"` failed. A test bug, but one only a non-UTF-8 default reveals.

Both are guarded here. The encoding guard is an AST pass over the whole repo,
because the fix for one call site is worthless if the next one reintroduces it.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from self_learning_agent.apply import stage_skill
from self_learning_agent.proposals import parse

TEXT_IO = {"read_text", "write_text"}

# Deliberately contains the characters that broke on Windows: a multi-line body
# (CRLF translation) and non-ASCII (cp1252 decoding).
CONTENT = (
    "---\nname: demo\ndescription: a demo skill\n---\n\n"
    "# Demo\n\nFirst line — with an em dash.\nSecond line · with a middot.\n"
)


def _proposal():
    return parse({
        "id": "p1", "kind": "skill", "title": "t", "rationale": "r",
        "action": {"name": "demo", "content": CONTENT},
    })


def _repo_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude-plugin" / "plugin.json").is_file():
            return parent
    return None


# ------------------------------------------------- §21, independent of platform


def test_a_staged_skill_holds_exactly_the_scanned_bytes(tmp_path):
    """What activates is what was scanned — byte for byte, on any platform.

    This is the regression guard for the Windows bug. It passes on POSIX either
    way, so it is a statement of the invariant rather than a local reproduction;
    the simulation below is what bites everywhere.
    """
    staged = stage_skill(_proposal(), tmp_path / "generated-skills")
    assert (staged / "SKILL.md").read_bytes() == CONTENT.encode("utf-8")


def test_a_staged_skill_has_no_platform_line_endings(tmp_path):
    staged = stage_skill(_proposal(), tmp_path / "generated-skills")
    raw = (staged / "SKILL.md").read_bytes()
    assert b"\r\n" not in raw, "text-mode translation is back"
    assert raw.count(b"\n") == CONTENT.count("\n")


def test_crlf_in_the_staged_copy_is_still_detected_as_a_change(tmp_path):
    """The fix must not weaken the check into ignoring newlines.

    A staged copy someone rewrote with CRLF genuinely is not the scanned bytes,
    and must still refuse. This is the half that would break if the comparison
    were 'fixed' by normalising instead of by writing bytes.
    """
    from self_learning_agent.apply import _unscanned_changes

    proposal = _proposal()
    staged = stage_skill(proposal, tmp_path / "generated-skills")
    skill_file = staged / "SKILL.md"
    with open(skill_file, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(CONTENT)  # exactly what Windows text mode used to produce

    problem = _unscanned_changes(proposal, staged)
    assert problem is not None and "changed after it was scanned" in problem


def test_a_staged_skill_is_never_executable(tmp_path):
    """On a filesystem with POSIX modes. Windows has no execute bit to clear."""
    staged = stage_skill(_proposal(), tmp_path / "generated-skills")
    mode = (staged / "SKILL.md").stat().st_mode
    if os.name == "nt":
        pytest.skip("no POSIX execute bit on Windows — §21's mode half cannot apply")
    assert mode & 0o111 == 0


def test_skill_content_is_never_written_through_text_mode():
    """The two guards above cannot fail on POSIX, so assert the mechanism too.

    `write_text` and `write_bytes` are indistinguishable on Linux and macOS, so
    a revert to text mode would go unnoticed everywhere except the platform that
    cannot run locally. This guard bites on any of them.
    """
    root = _repo_root()
    if root is None:
        pytest.skip("not running from a checkout — no sources to scan")
    source = (root / "src" / "self_learning_agent" / "apply.py").read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in source.splitlines()
        if ".write_text(" in line and "content" in line
    ]
    assert not offenders, (
        "skill content must be written with write_bytes, so what lands on disk is "
        "what was scanned on every platform:\n  " + "\n  ".join(offenders)
    )


# --------------------------------------------------------- the encoding class


def _text_io_without_encoding(root: Path) -> list[str]:
    offenders = []
    for path in sorted(root.glob("src/**/*.py")) + sorted(root.glob("tests/**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name not in TEXT_IO and name != "open":
                continue
            if "encoding" in {k.arg for k in node.keywords}:
                continue
            # Where `encoding` sits positionally differs per call, and getting
            # this wrong once already made this guard pass a mutation it should
            # have failed: `write_text(data)` was read as "encoding supplied".
            if name == "read_text" and len(node.args) >= 1:
                continue  # read_text("utf-8")
            if name == "write_text" and len(node.args) >= 2:
                continue  # write_text(data, "utf-8")
            if name == "open":
                mode = node.args[1] if len(node.args) > 1 else None
                if isinstance(mode, ast.Constant) and "b" in str(mode.value):
                    continue  # binary mode needs none
                if len(node.args) >= 4:
                    continue  # open(path, mode, buffering, encoding)
            offenders.append(f"{path.relative_to(root).as_posix()}:{node.lineno} {name}()")
    return offenders


def test_no_text_file_io_relies_on_the_platform_default_encoding():
    """Windows defaults to cp1252, so an omitted encoding is a latent bug.

    Every note, digest and rationale this project writes contains em dashes and
    middots. One call site without an encoding is enough to mangle them.
    """
    root = _repo_root()
    if root is None:
        pytest.skip("not running from a checkout — no sources to scan")
    offenders = _text_io_without_encoding(root)
    assert not offenders, "text I/O with no explicit encoding:\n  " + "\n  ".join(offenders)
