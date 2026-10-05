# Changelog

Versions are plugin versions; the CLI and the plugin ship together and share one
number. `claude plugin update self-learning-agent` moves you between them.

Design decisions and the reasoning behind each change live in
[PLAN.md](PLAN.md) — the section numbers below point there.

## Unreleased

### Fixed
- **`sla apply` could not activate a skill on Windows at all.** `Path.write_text`
  translates `\n` to `os.linesep`, so the staged `SKILL.md` never held the bytes
  that were scanned, and the §21 byte comparison refused every activation as
  *"changed after it was scanned"* — a correct operation reported as tampering.
  Both skill writes now use `write_bytes`, so what lands on disk is byte-for-byte
  what was scanned on every platform. The check itself was deliberately left
  strict. (§30)
- Ten test call sites read or wrote text without an explicit encoding, which
  Windows decodes as cp1252 and which mangled every em dash and middot. (§30)

### Added
- **PyPI packaging, prepared but not published.** The listing metadata an index
  needs — summary, SPDX licence, author without an address, keywords,
  classifiers, project URLs — plus guards that the declared Pythons match
  `requires-python`, that no deprecated `License ::` classifier returns, and that
  no email is published. `self-learning-agent` is unregistered on PyPI and
  TestPyPI; the first upload is the maintainer's to trigger.
- `RELEASING.md`, because the release process was tribal knowledge and forgetting
  one of its steps caused two of the bugs in §28–§29.
- `.github/workflows/release.yml` — publishes on a `self-learning-agent--v*` tag
  via Trusted Publishing (OIDC), so no API token is ever stored. It refuses to
  publish if the tag and `pyproject.toml` disagree, and is inert until a trusted
  publisher is configured.
- A CI job that builds the distribution and runs `twine check --strict` on every
  push. A listing that fails to render is otherwise only discoverable after
  publishing, and an index filename can never be reused.
- **`sla doctor`** — ten checks on what is actually installed here, each
  traceable to something that shipped broken: CLI and plugin versions with skew
  flagged, a hand-copied first-party skill (§26), yt-dlp resolved the same way
  the fetch path resolves it, the scanner's three states, detected harnesses
  (§31), and the vault and staged-skills paths, with a `FAIL` when staging
  resolves inside an installed venv (§28). Writes nothing, prints no secret
  value, exits non-zero only on a `FAIL`.
- `examples/` — the six real notes and the six `proposals.json` stores they came
  with, copied byte for byte out of the author's vault, plus an index explaining
  what each one demonstrates. Half of them propose nothing, which is the output
  worth showing. Linked from the first screen of the README, because the gap this
  closes is that nobody installs a CLI to find out what it produces. (§29)
- Guards for that directory (`tests/test_examples.py`): every link resolves, every
  published file is indexed, the proposal and idea counts quoted in both READMEs
  match the files, and every published proposal still passes the validator and
  renders no arbitrary command. Nine tests, each checked by mutation — introduce
  the bug and exactly that test fails.
- **CI runs on macOS and Windows**, not only Linux, and the packaged job runs on
  all three. This is what found the bug above; the project had only ever been run
  on WSL. (§30)
- `tests/test_portability.py`: the staged skill must hold exactly the scanned
  bytes, a CRLF staged copy must still be refused, skill content must never be
  written through text mode, and an AST pass forbids text I/O anywhere in `src/`
  or `tests/` without an explicit encoding.
- `pytest-github-actions-annotate-failures`, because job logs need admin rights
  and a failure on a platform the maintainer cannot run was otherwise unreadable.
- PLAN §31 scopes a second harness (Codex) and corrects an earlier wrong claim:
  Codex skills are `<name>/SKILL.md` with the same frontmatter, so the hard part
  turned out to be identical and the coupling is two files.

## 0.2.2 — 2026-10-05

### Fixed
- `sla --version` reported `0.1.0` while 0.2.1 was published. The version was a
  literal in `__init__.py` and had been missed by both releases; it is now read
  from installed metadata, so `pyproject.toml` is the only place a Python version
  is declared. (§29)

### Added
- Packaging guards (`tests/test_packaging.py`): the declared versions must agree
  across `pyproject.toml`, `plugin.json` and the marketplace entry; `author` must
  be an object; declared component paths must exist; no version literal may
  return. Each was checked by mutation — reintroduce the bug and exactly one test
  fails.
- A CI job that installs non-editable and runs the suite against `site-packages`
  with no `src/` in reach, plus a step asserting the reported version matches the
  declared one. `conftest.py` puts `src/` on `sys.path`, so until now nothing in
  CI had ever tested the published artifact. (§29)
- This changelog.

## 0.2.1 — 2026-10-02

### Fixed
- A staged skill — D7's *reviewable* copy, the one you are meant to read before
  activating — was written to `Path(__file__).parents[2]`, which in an installed
  copy is a library directory inside the tool's own venv: in no repository,
  invisible to its owner, and deleted by the next `uv tool upgrade`. The path is
  now decided by `Config.generated_skills_dir`, preferring an explicit
  `generated_skills_path`, then a real checkout, then `SLA_HOME`. (§28)
- Never a hole in the gate: scans always read a scratch copy, and activation read
  back what it had just written, so skills activated and matched what was scanned.
  What broke was the review.

### Added
- `generated_skills_path` in `config.json`.

## 0.2.0 — 2026-10-02

The first version that can actually be installed.

### Fixed
- `.claude-plugin/plugin.json` had carried `"author"` as a string since the first
  milestone, where an object is required, and there was no `marketplace.json` at
  all — so this had never been installable as a plugin, and copying `skills/` into
  `~/.claude/` by hand was the only thing that worked. That copy has no update
  path and silently taught a superseded procedure for three weeks. (§26, §28)
- Caption downloads. `--sub-langs "en.*"` matched two tracks and spent two
  requests, and YouTube refuses the translated `en` auto-caption track
  indefinitely while serving `en-orig` normally — a per-track refusal wearing an
  `HTTP 429`. One track is now requested, `-orig` first, with a fall-through to
  the next when one is refused. (§23, §25)
- A failed caption download is no longer cached as "this video has no captions",
  and a rate limit is retried with bounded backoff rather than failing the run.
  (§23, §24)

### Added
- `sla queue` reports caption availability (`manual` / `auto` / `none` /
  `unknown`), ranks videos with no captions last, and shows `—` rather than an
  invented word estimate for them. (§24)
- `ytdlp_attempts` and `ytdlp_backoff_seconds` in `config.json`.
- Install as a plugin: `claude plugin marketplace add` plus
  `claude plugin install`, and `uv tool install` for the CLI.

## 0.1.0 — unreleased

Milestones M0–M5 were built under this number, and it was never installable: the
plugin manifest was invalid for its whole life. Listed for completeness; nothing
ever shipped with it.
