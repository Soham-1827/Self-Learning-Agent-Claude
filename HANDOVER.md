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
the security model (§8), and field notes from every milestone (§15–§21).

## Status

**v1 (M0–M4) is complete.** 178 tests, 83% coverage, CI green on Python 3.10–3.13.

| M | | |
|---|---|---|
| M0 | Repo, CI, MIT | ✅ |
| M1 | `sla fetch` — resolve, fetch, cache, dedupe | ✅ |
| M2 | `sla inventory` — installed skills / MCP / CLIs | ✅ |
| M3 | `/learn-from` — synthesis → vault note + proposals | ✅ |
| M4 | Approval gate + `sla apply`, SkillSpector scanning | ✅ |
| M5 | Channel batch: `--last 5` | ⬅ **next** |
| M6 | Scheduled polling | |
| M7 | Web frontend | |

## Environment (WSL, Ubuntu-22.04)

Everything is installed. **Do not reach for `sudo`** — system `python3` is 3.10 with no
`pip`, but `uv` is present and supplies both the installer and its own interpreter.

- **`sla` is on PATH** — symlinked from `.venv/bin/sla` into `~/.local/bin`.
- **`/learn-from <url>`** works in any Claude Code session. Named `learn-from`, *not*
  `learn`, because `everything-claude-code` owns `/learn`.
- **Tests:** `.venv/bin/python -m pytest` (3.14). For the CI matrix, build throwaway
  venvs with `uv venv --python 3.11 <dir>` — **dev passing on 3.14 has hidden real
  failures on ≤3.12 before** (PLAN §12).
- **`skillspector`** via uv. `SKILLSPECTOR_PROVIDER=openai` and `OPENAI_API_KEY` live in
  `~/.profile`, so non-login shells lack them — scan via `bash -lc`.
- **The checkout is on `/mnt/d`, a DrvFs mount without `metadata`.** Every file reports
  mode `0777` and `chmod` is silently ignored. This changed scan verdicts (§21); never
  scan a file whose mode came from this filesystem.
- **Git pushes** use the Windows Credential Manager. A commit failing with
  `couldn't set refs/heads/main` is a transient v9fs hiccup — retry it.
- **The owner sometimes edits on GitHub directly.** `git pull --ff-only` before
  committing, or the push is rejected.

Windows Python also works but cannot see the skills in WSL, and state is per-platform.

## Commands

```bash
sla fetch "<url|@handle>"           # resolve + cache a source
sla brief "<url>" --out b.json      # the agent's input packet
sla note  "<url>" --synthesis s.json
sla apply "<url>" --dry-run         # scan and decide; change nothing
sla apply "<url>" [--only p1]       # scan, decide, prompt per proposal
sla inventory [--against "text"]
sla status
```

`sla apply` must be run by the owner in a real terminal. **An agent must never run it
with `--yes` or answer its prompts on the owner's behalf.** Piping `n` to every prompt
is an acceptable way to exercise the path without applying anything.

## Rules that are load-bearing, not stylistic

1. **The description is authoritative for entity names; the transcript is
   authoritative for reasoning about them** (§15).
2. **The agent never emits a shell string** (§8 Rule 1). Proposals name registry
   packages; Python renders commands. Claimed risk is discarded and recomputed.
3. **A scan gates activation, not download** (§18). `SCAN_CAN_BLOCK == {"skill"}`.
4. **Empty output is correct output.** `proposals: []` (I3) and zero project ideas
   (§7.2) are both valid. A target count is an instruction to invent.
5. **A project idea must be load-bearing** — writable without watching means decoration.
6. **With no authoritative text**, mention-frequency is the fallback check, and nothing
   the source never says goes in the note (§20).
7. **Never infer a creator's pronouns** from a name, handle, or voice.
8. **What activates is exactly what was scanned** (§21). Scan targets are written by us
   with fixed content *and* mode; activation writes the scanned content and refuses if
   the staged copy changed or gained files.
9. **Replace text with exact-match edits that fail loudly.** A silent `str.replace` left
   five stale `/learn` references in the docs for a week.

## Fixtures — three real, processed sources

| Source | Class | Chapters | Links | Proposals |
|---|---|---|---|---|
| `9_SZFIW7tus` Greg Isenberg, 5 GitHub repos | `tooling` | 7 | 5 GitHub | 3 |
| `gPPT4WpVRZ4` BlackRain79, poker | `conceptual` | none | none | 0 |
| `UpE5yuhwXXc` StarTalk, periodic table | `conceptual` | 5 | none | 0 |

Only the first is committed under `tests/fixtures/`. All three notes are in
`/mnt/d/LearningVault/Sources/`.

## What to build next: M5

`/learn-from @GregIsenberg --last 5`. `YouTubeSource._channel_video_ids` exists and the
ledger dedupes. Missing: batch orchestration, and a per-run token cap — five
45-minute transcripts is a lot of context.

Open questions (PLAN §14): vault folder structure; the batch cost cap; whether
`none`-risk auto-apply is opt-in or always-confirm.

## Known unfinished

- **Nothing has been approved through the gate on a real machine yet.** The prompt path
  has run for real (every answer "no"), and activation is unit-tested, but no `y` has
  ever been given. `p1` on the Greg note (`scan-before-install`, risk `none`, scans
  0/100) is the natural first real approval.
- **Restaging overwrites the repo copy.** `sla apply` rewrites
  `generated-skills/<name>/SKILL.md` from the proposal each run, so a hand edit made
  there before running is lost rather than scanned.
- **The drift check described in PLAN §8 Rule 6 is not implemented** — `sla status` does
  not diff repo copies against live skills.
- Coverage gaps are network I/O: `youtube.py` 56%, `cli.py` 58%.
- Vision on video frames is deferred.

## Prompt for a new session

> I'm building `self-learning-agent`, an open-source pipeline that turns YouTube
> videos into Obsidian notes plus human-approved tool setup. Read `HANDOVER.md` and
> `PLAN.md` in this repo — PLAN.md is the source of truth for decisions.
>
> v1 (M0–M4) is complete: fetch, inventory, synthesis, and an approval gate that scans
> with SkillSpector before activating anything. 178 tests, 83% coverage, CI green on
> 3.10–3.13. `sla` is on PATH and `/learn-from <url>` works in any session. Next is M5,
> batch channel processing.
>
> Rules that are load-bearing rather than stylistic: the video description is
> authoritative for entity names and the transcript for reasoning about them (§15);
> the agent never emits a shell string (§8 Rule 1); a scan blocks activation but never
> a download (§18); empty output beats invented output (I3, §7.2); and what activates
> must be exactly what was scanned, including file mode (§21).
>
> Environment: WSL, checkout on `/mnt/d` (DrvFs — every file reads 0777 and chmod is
> ignored). Use the uv venv at `.venv`; never sudo. Verify changes on the CI matrix,
> not just 3.14. `git pull --ff-only` before committing. Never run `sla apply --yes`
> or answer its prompts for me.
