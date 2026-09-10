# Handover

Paste this to a new session to pick the project up cold.

---

## What this is

`self-learning-agent` — point a coding agent at a video; get an Obsidian note worth
keeping and a set of setup actions you explicitly approve before anything installs.

- Repo: https://github.com/Soham-1827/Self-Learning-Agent-Claude (MIT)
- Owner: **@Soham-1827**, an AI student who wants to build projects from what these
  videos teach. Notes should serve that, not just summarise.

**[PLAN.md](PLAN.md) is the source of truth.** Decisions D1–D7, improvements I1–I4,
the security model (§8), and field notes from every milestone (§15–§20).

## Status

**v1 (M0–M4) is complete.** 169 tests, 80% coverage.

| M | | |
|---|---|---|
| M0 | Repo, CI (3.10–3.12), MIT | ✅ |
| M1 | `sla fetch` — resolve, fetch, cache, dedupe | ✅ |
| M2 | `sla inventory` — installed skills / MCP / CLIs | ✅ |
| M3 | `/learn-from` — synthesis → vault note + proposals | ✅ |
| M4 | Approval gate + `sla apply`, SkillSpector scanning | ✅ |
| M5 | Channel batch: `--last 5` | ⬅ **next** |
| M6 | Scheduled polling | |
| M7 | Web frontend | |

## Environment (WSL, Ubuntu-22.04)

Everything is installed. **Do not reach for `sudo`** — system `python3` is 3.10 with no
`pip` and no `ensurepip`, but `uv` is present and solves it without a password while
supplying its own interpreter.

```bash
uv venv --python 3.14 .venv                              # already done
uv pip install --python .venv/bin/python -e ".[dev]"     # already done
```

- **`sla` is on PATH** — symlinked from `.venv/bin/sla` into `~/.local/bin`.
- **`/learn-from <url>`** works in any Claude Code session. Named `learn-from`, *not*
  `learn`, because `everything-claude-code` owns `/learn`; installing over it would
  have clobbered a working command.
- **Tests:** `.venv/bin/python -m pytest` (Python 3.14.7; CI covers 3.10–3.12).
- **`yt-dlp`** is a zipapp at `~/.local/bin/yt-dlp.pyz`; `SLA_YTDLP` overrides.
- **`skillspector`** via uv. `SKILLSPECTOR_PROVIDER=openai` + `OPENAI_API_KEY` are in
  `~/.profile`, so they are absent from non-login shells — run scans via a login shell.
- **Git pushes** work through the Windows Credential Manager. `/mnt/d` is v9fs and
  occasionally fails a ref write; **retry the commit, it is transient**.
- Never work around a missing pip by piping a downloaded script into Python. That is
  the exact pattern the project classifies as risk tier `high`.

**Windows also works** (`pip`, Python 3.12) but cannot see the 257 skills that make
inventory worth running, and state is per-platform — a note written in WSL cannot be
applied from Windows. WSL is the right home.

## Commands

```bash
sla fetch "<url|@handle>"          # resolve + cache a source
sla brief "<url>" --out b.json     # the agent's input packet
sla note  "<url>" --synthesis s.json
sla apply "<url>" [--dry-run]      # scan, decide, prompt per proposal
sla inventory [--against "text"]
sla status
```

## Rules that are load-bearing, not stylistic

1. **The description is authoritative for entity names; the transcript is
   authoritative for reasoning about them** (§15). ASR renders `SkillSpector` as
   "Skill Specter" and `Claude Code` as "Cloud Code" — exactly the tokens needed to
   find a repo. `Link.repo_slug` preserves URL casing and is regression-tested.
2. **The agent never emits a shell string** (§8 Rule 1). A proposal names a package on
   a registry; Python renders the command from a template. Claimed risk is discarded
   and recomputed by `derive_risk`.
3. **A scan gates activation, not download** (§18). `SCAN_CAN_BLOCK == {"skill"}`.
   Cloning to staging executes nothing and is how you inspect a repo — blocking it
   prevents the review it exists for. SkillSpector scores full application repos
   CRITICAL on false positives, and a gate that blocks on that gets switched off.
4. **Empty output is correct output.** `proposals: []` (I3) and zero project ideas
   (§7.2) are both valid. A target count is an instruction to invent.
5. **A project idea must be load-bearing** — if it could be written without watching,
   it is decoration. Drop it (§19, demonstrated §20).
6. **Where no authoritative text exists**, mention-frequency in the transcript is the
   fallback check, and anything the source never says stays out of the note however
   plausible (§20).
7. **Never infer a creator's pronouns** from a name, handle, or voice.

## Fixtures — all three are real, processed sources

| Source | Class | Chapters | Links | Proposals |
|---|---|---|---|---|
| `9_SZFIW7tus` Greg Isenberg, 5 GitHub repos | `tooling` | 7 | 5 GitHub | 3 |
| `gPPT4WpVRZ4` BlackRain79, poker | `conceptual` | none | none | 0 |
| `UpE5yuhwXXc` StarTalk, periodic table | `conceptual` | 5 | none | 0 |

Only the first is committed under `tests/fixtures/`. Notes for all three are in
`/mnt/d/LearningVault/Sources/`.

## What to build next: M5

`sla brief "@GregIsenberg" --last 5`. `YouTubeSource._channel_video_ids` already
exists and works; the ledger already dedupes. What is missing is batch orchestration
and a per-run cost cap, since five 45-minute transcripts is a lot of tokens.

Open questions (PLAN §14):
- Folder structure inside the vault
- Per-run token/cost cap for batch mode
- Whether `none`-risk auto-apply is opt-in or always-confirm

## Known unfinished

- **`sla apply` has never been run to completion.** Only `--dry-run`. Nothing has been
  installed through the gate yet. `p1` on the Greg note (the `scan-before-install`
  skill, risk `none`, scans clean) is the natural first candidate.
- `cli.py` is at 35% coverage and `youtube.py` at 56% — the remainder is network I/O.
- Vision on sampled frames is deferred. Videos demo things on screen while the audio
  says "just paste this in here"; description links only partly cover it.

## Prompt for a new session

> I'm building `self-learning-agent`, an open-source pipeline that turns YouTube
> videos into Obsidian notes plus human-approved tool setup. Read `HANDOVER.md` and
> `PLAN.md` in this repo — PLAN.md is the source of truth for decisions.
>
> v1 (M0–M4) is complete: fetch, inventory, synthesis, and an approval gate that scans
> with SkillSpector before activating anything. 169 tests at 80% coverage. `sla` is on
> PATH and `/learn-from <url>` works in any session. Next is M5, batch channel
> processing.
>
> Four rules are load-bearing rather than stylistic: the video description is
> authoritative for entity names while the transcript is authoritative for reasoning
> about them (§15); the agent must never emit a shell string — proposals name registry
> packages and Python renders the command (§8 Rule 1); a scan blocks activation but
> never a download, because cloning to staging is how you inspect something (§18); and
> empty output is correct output — no proposals, or no project ideas, beats inventing
> either (I3, §7.2).
>
> Environment: WSL, use the venv at `.venv` (created with uv — do not use sudo or
> pip-bootstrap scripts). Run tests with `.venv/bin/python -m pytest`. SkillSpector
> needs a login shell to see `OPENAI_API_KEY`. If a git commit fails with "couldn't set
> refs/heads/main", it is a transient v9fs issue — just retry.
