# Handover

Paste this to a new session to pick the project up cold.

---

## What this is

`self-learning-agent` — point a coding agent at a video or a channel; get an Obsidian
note worth keeping and a set of setup actions you explicitly approve before anything
installs.

- Repo: https://github.com/Soham-1827/Self-Learning-Agent-Claude (MIT)
- Owner: **@Soham-1827**, an AI student who wants to build projects from what these
  videos teach. Notes should serve that, not just summarise.

**[PLAN.md](PLAN.md) is the source of truth.** Decisions D1–D7, improvements I1–I4,
the security model (§8), and field notes from every milestone (§15–§22).

## Status

**v1 (M0–M4) and M5 are complete.** 284 tests, 91% coverage, CI green on 3.10–3.13.
The whole loop has run for real: video → note → scan → owner's `y` → live skill.

| M | | |
|---|---|---|
| M0 | Repo, CI, MIT | ✅ |
| M1 | `sla fetch` — resolve, fetch, cache, dedupe | ✅ |
| M2 | `sla inventory` — installed skills / MCP / CLIs | ✅ |
| M3 | `/learn-from` — synthesis → vault note + proposals | ✅ |
| M4 | Approval gate + `sla apply`, SkillSpector scanning | ✅ |
| M5 | Channel triage (`sla queue`) + batch digest (`sla digest`) | ✅ |
| M6 | Scheduled polling | ⬅ candidate |
| M7 | Web frontend | candidate |

## Environment (WSL, Ubuntu-22.04)

Everything is installed. **Do not reach for `sudo`** — system `python3` is 3.10 with no
`pip`, but `uv` supplies both the installer and its own interpreter.

- **`sla` is on PATH** — symlinked from `.venv/bin/sla` into `~/.local/bin`, so it always
  runs the **main checkout's** code, never a worktree's.
- **`/learn-from <url | @handle>`** works in any Claude Code session. Named `learn-from`,
  not `learn`, because `everything-claude-code` owns `/learn`.
- **Tests:** `.venv/bin/python -m pytest` (3.14). For the CI matrix, build throwaway venvs
  with `uv venv --python 3.11 <dir>` and `uv pip install -e .` — dev passing on 3.14 has
  hidden real failures on ≤3.12 before (§12). The scratchpad is cleared between sessions,
  so rebuild them rather than assuming they exist.
- **`skillspector`** via uv. `SKILLSPECTOR_PROVIDER=openai` and `OPENAI_API_KEY` live in
  `~/.profile`, so non-login shells lack them — scan via `bash -lc`.
- **The checkout is on `/mnt/d`, a DrvFs mount without `metadata`.** Every file reports
  `0777` and `chmod` is ignored. Never scan a file whose mode came from here (§21).
- **Git pushes** use the Windows Credential Manager. `couldn't set refs/heads/main` is a
  transient v9fs hiccup — retry.
- **The owner sometimes edits on GitHub.** `git pull --ff-only` before committing.

## Commands

```bash
sla queue "@handle" [--last 10] [--cap 5]   # triage a channel: metadata only
sla fetch "<url>"                           # resolve + cache one video
sla brief "<url>" --out b.json              # the agent's input packet
sla note  "<url>" --synthesis s.json        # render the note, store proposals
sla digest <id> <id> ... [--title T]        # one note linking a processed batch
sla apply "<url>" --dry-run                 # scan and decide; change nothing
sla apply "<url>" [--only p1]               # scan, decide, prompt per proposal
sla inventory [--against "text"]
sla status
```

`sla apply` is the owner's to run. **An agent must never pass `--yes` or answer its
prompts on the owner's behalf.** Redirecting stdin from `/dev/null` is a safe way to
exercise it: end of input now means "no" for everything left.

## Working in parallel

Worktrees live at `~/.config/superpowers/worktrees/Self-Learning-Agent/<name>`, on the
Linux filesystem (about 13× faster than `D:`). The M5 round (§22) showed what makes it
work:

- Pick tasks that touch **disjoint files**, and write the file ownership into each brief.
- Each worktree gets its **own venv**; `sla` on PATH runs main's code, not the branch's.
- A bug one agent finds in code another owns is marked `xfail(strict=True)` and reported,
  not fixed in place. It is fixed on main after the merges.
- Leave PLAN / README / HANDOVER for one pass after merging — that is where branches
  collide.
- Review each branch before merging: scope (`git diff --name-status`), the numbers
  reproduced independently, and no forbidden files.

## Rules that are load-bearing, not stylistic

1. **The description is authoritative for entity names; the transcript for reasoning
   about them** (§15).
2. **The agent never emits a shell string** (§8 Rule 1). Proposals name registry
   packages; Python renders commands. Claimed risk is discarded and recomputed.
3. **A scan gates activation, not download** (§18). `SCAN_CAN_BLOCK == {"skill"}`.
4. **Empty output is correct output.** `proposals: []` (I3) and zero project ideas (§7.2)
   are both valid. A target count is an instruction to invent.
5. **A project idea must be load-bearing** — writable without watching means decoration.
6. **With no authoritative text**, mention-frequency is the fallback check, and nothing
   the source never says goes in the note (§20).
7. **Never infer a creator's pronouns** from a name, handle, or voice.
8. **What activates is exactly what was scanned**, including file mode (§21).
9. **Edit with exact-match replacements that fail loudly.** A silent `str.replace` hid
   stale references *and* a live padding quota for a week (§22). Verify by grepping for
   the intended result.
10. **The owner picks what gets read.** Channels are triaged from metadata; the class is
    a guess; nothing processes a whole channel on its own initiative.

## Fixtures — all three committed under `tests/fixtures/`

| Source | Class | Chapters | Links | Proposals |
|---|---|---|---|---|
| `9_SZFIW7tus` Greg Isenberg, 5 GitHub repos | `tooling` | 7 | 5 GitHub | 3 (`p1` applied) |
| `gPPT4WpVRZ4` BlackRain79, poker | `conceptual` | none | promo only | 0 |
| `UpE5yuhwXXc` StarTalk, periodic table | `conceptual` | 5 | promo only | 0 |

Notes for all three are in `/mnt/d/LearningVault/Sources/`.

## What to build next

No milestone is locked. Candidates, roughly by value:

- **Close the apply-flow gaps** (below) — small, and they are the last rough edges in a
  loop that now runs for real.
- **M6: scheduled polling.** `sla queue` is the natural core; the open question is how a
  run *without the owner present* respects Rule 10 — likely: queue and digest the triage
  table, never process.
- **M7: the frontend** the owner asked for at the start. Needs a design conversation first.

Open questions (PLAN §14): vault folder structure; whether `none`-risk auto-apply is
opt-in or always-confirm.

## Known unfinished

- **Re-running `sla note` resets a video.** It rewrites the note (clearing the Applied
  section) and the stored proposals (clearing applied tracking), and sets status back to
  `pending-review`.
- **Restaging overwrites the repo copy.** `sla apply` rewrites
  `generated-skills/<name>/SKILL.md` from the proposal each run, so a hand edit there is
  lost rather than scanned.
- **The drift check promised in PLAN §8 Rule 6 is not implemented** — `sla status` does
  not diff repo copies against live skills.
- **`p2` on the Greg note is still awaiting review** (status `partial`).
- Triage's class guess is heuristic and misfires at the margin (§22).
- Coverage gap is mostly `cli.py` at 70%.
- Vision on video frames is deferred.

## Prompt for a new session

> I'm building `self-learning-agent`, an open-source pipeline that turns YouTube videos
> and channels into Obsidian notes plus human-approved tool setup. Read `HANDOVER.md` and
> `PLAN.md` in this repo — PLAN.md is the source of truth for decisions.
>
> v1 (M0–M4) and M5 are complete: fetch, inventory, synthesis, an approval gate that
> scans with SkillSpector before activating anything, and channel triage with batch
> digests. 284 tests, 91% coverage, CI green on 3.10–3.13. The full loop has run for real.
> `sla` is on PATH and `/learn-from <url | @handle>` works in any session. No next
> milestone is locked — HANDOVER lists the candidates.
>
> Load-bearing rules: the description is authoritative for entity names and the
> transcript for reasoning (§15); the agent never emits a shell string (§8 Rule 1); a
> scan blocks activation, never a download (§18); empty output beats invented output
> (I3, §7.2); what activates is exactly what was scanned (§21); edits use exact-match
> replacements that fail loudly (§22); and I pick what gets read.
>
> Environment: WSL, checkout on `/mnt/d` (DrvFs — files read 0777, chmod ignored). Use the
> uv venv at `.venv`; never sudo. Verify on the CI matrix, not just 3.14. `git pull
> --ff-only` before committing. Never run `sla apply --yes` or answer its prompts for me.
