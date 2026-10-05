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
the security model (§8), and field notes from every milestone (§15–§29).

## Status

**v1 (M0–M4) and M5 are complete, released as 0.2.2 and installable by anyone.** 368 tests,
91% coverage, **CI green on Linux, macOS and Windows** across 3.10–3.13 — and a second job
runs the suite against the *installed* package on all three, because `conftest.py` puts
`src/` on `sys.path` and nothing had ever tested the published wheel (§29). The whole loop
has run for real: video → note → scan → owner's `y` → live skill.

**Nobody is using it.** Three days after release: 0 stars, 0 forks, 0 watchers. The install
works — verified from the outside (§28). It has simply never been shown to anyone, which is
the actual next problem and not an engineering one.

**A channel run has now completed end to end (§26).** `@GregIsenberg`, 10 triaged, owner
picked 3, three notes and one digest written, six videos in the ledger. The `HTTP 429` that
blocked the first attempt was never a rate limit — YouTube refuses the translated `en`
auto-caption track and serves `en-orig` (§25). Caption downloads cost one request and
about ten seconds.

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
   the intended result. When a status bullet here becomes false, **delete it in the same
   pass that makes it false** — this file had two bullets four lines apart saying opposite
   things about the same files (§29).
10. **The owner picks what gets read.** Channels are triaged from metadata; the class is
    a guess; nothing processes a whole channel on its own initiative.
11. **A brief states what must be true, never what to return on failure** (§23). Writing
    "yt-dlp failure → `{}`" into a brief produced a silent failure *and* two tests that
    froze it in place. Say what must never happen and leave the mechanism to whoever
    implements it. A brief is as load-bearing as the code it produces.
12. **A failure must never look like an absence** (§23). Empty results get cached and read
    back as fact. If something was expected and did not arrive, raise and say why.
13. **A missing field is not a negative answer** (§24). Triage's `captions` column has a
    fourth value, `unknown`, because metadata cached before the check existed does not
    say "none" — it says nothing. Same rule as 12, one layer up.
14. **Retry only what asking again can fix** (§24). A `429` is sometimes a wait;
    everything else is final, and re-asking spends the budget that caused the failure.
15. **When a failure repeats identically, vary the request before blaming the responder**
    (§25). Six identical 429s over 45 hours read as a hardening block and were one
    unvaried input: the same refused caption track, asked for six times. "It is still
    failing" is a measurement; "we are blocked" is an inference.

## Fixtures — all three committed under `tests/fixtures/`

| Source | Class | Chapters | Links | Proposals |
|---|---|---|---|---|
| `9_SZFIW7tus` Greg Isenberg, 5 GitHub repos | `tooling` | 7 | 5 GitHub | 3 (`p1` applied) |
| `gPPT4WpVRZ4` BlackRain79, poker | `conceptual` | none | promo only | 0 |
| `UpE5yuhwXXc` StarTalk, periodic table | `conceptual` | 5 | promo only | 0 |

Notes for all three are in `/mnt/d/LearningVault/Sources/`.

## What to build next

**1. Put examples in the repo (§29).** Six real notes exist and a visitor can see none of
them, so they cannot tell whether this is worth three commands — and nobody installs a CLI
to find out. Half a day, and the highest-leverage thing left. The Software Factory note
shows a scanned proposal; the WebMCP note shows the `medium` / `manual` split; the Meta
Muse note shows `proposals: []` as a correct answer.

**2. Then tell people**, with the notes as the argument rather than the README.

**3. ~~`sla doctor`~~ — done.** Ten checks, each traceable to something that shipped
broken: CLI and plugin versions with skew flagged, a hand-copied first-party skill (§26),
yt-dlp via the same resolver the fetch path uses, the scanner's three states, detected
harnesses (§31), and the vault and staged-skills paths including a `FAIL` when staging
resolves inside an installed venv (§28). Writes nothing, prints no secret value, exits
non-zero only on a `FAIL`. Two of its own checks were false positives on the first real
run and are now pinned by tests — `shutil.which("yt-dlp")` missed a module-only install,
and `~/.agents/skills` was read as evidence of Codex when it is a vendor-neutral path.

Then, roughly by value:

- **PyPI**, to drop the git URL from the install line. `self-learning-agent` is free.
- **Close the apply-flow gaps** (below) — the last rough edges in a loop that runs for real.
- **M6: scheduled polling.** `sla queue` is the natural core; the open question is how a
  run *without the owner present* respects Rule 10 — likely: queue and digest the triage
  table, never process.
- **M7: the frontend.** Scoped in §27 and **not recommended yet**: ~$0.20 a note, it cannot
  apply anything, and the inventory it would have to drop is 48–68% of every brief *and*
  the part that made the notes good. Host a static showcase of pre-rendered notes instead.
- **A second harness (Codex).** Scoped in §31. Smaller than it looks: Codex skills are
  `<name>/SKILL.md` with the same two frontmatter fields, at `$HOME/.agents/skills`, so
  `kind: skill` ports by changing a directory and Rule 5, §21 and D7 all stay intact. The
  Claude Code coupling is **two files** — `inventory.py` reads and `apply.py` writes — and
  `sla` already runs under Codex today with an empty inventory. The new work is TOML for
  `[mcp_servers.<id>]` and deciding which harness to target. Not before real users.

**Platform: now tested on three, driven by hand on one (§30).** The matrix found that
macOS was already fine and that Windows could not activate a skill at all — `write_text`
translates `\n` to `\r\n`, so the staged `SKILL.md` never matched the bytes §21 compares,
and every activation refused as if the file had been tampered with. Fixed by writing
bytes. Still unverified by a human: the end-to-end flow on Windows, `install_mode =
"symlink"` on a non-administrator account, and `_remove_cmd`'s PowerShell branch as an
actual command.

Open questions (PLAN §14): vault folder structure; whether `none`-risk auto-apply is
opt-in or always-confirm.

## Known unfinished

- **Re-running `sla note` resets a video.** It rewrites the note (clearing the Applied
  section) and the stored proposals (clearing applied tracking), and sets status back to
  `pending-review`.
- **Restaging overwrites the staged copy.** `sla apply` rewrites
  `<generated_skills_dir>/<name>/SKILL.md` from the proposal each run, so a hand edit
  there is lost rather than scanned. The directory is `Config.generated_skills_dir` — the
  checkout's `generated-skills/` here, `SLA_HOME/generated-skills` for an installed copy
  (§28).
- **The drift check promised in PLAN §8 Rule 6 is not implemented** — `sla status` does
  not diff staged copies against live skills. Less urgent for the first-party skill now
  that the plugin owns updates, but *generated* skills are still copied into
  `~/.claude/skills/` with nothing comparing them afterwards.
- **`p2` on the Greg note is still awaiting review** (status `partial`).
- **Four proposals from the 2026-09-25 batch are unreviewed** — `_LCeJZFIsd4` `p1` (a
  before/after proof skill, risk `none`) and `p2` (a scoring PR reviewer, `high`/manual);
  `EoNH3Tn8wYE` `p1` (clone the WebMCP reference repo, `medium`) and `p2` (Chrome flags,
  `high`/manual, and one of them opens remote debugging on the browser holding your
  sessions). Both notes are `pending-review`; `sla apply` is the owner's to run.
- **This machine now installs from GitHub like everyone else.** The hand copies are gone
  and the marketplace points at `Soham-1827/Self-Learning-Agent-Claude`, so your own edits
  reach you only after a push plus a version bump. That is deliberate — it means you test
  the path strangers use — but it does make the dev loop slower than editing in place.
- **Editing a skill does not change the installed plugin until the version bumps.** The
  plugin is a versioned copy in `~/.claude/plugins/cache/.../<version>/`, and
  `claude plugin update` compares versions, so a repo edit alone reaches nobody. Bump
  `version` in both manifests (`claude plugin tag` checks they agree), then
  `marketplace update` and `plugin update` (§28).
- Triage's class guess is heuristic and misfires at the margin (§22, §26).
- Coverage gap is mostly `cli.py` at 70%.
- Vision on video frames is deferred.

## Prompt for a new session

Paste this verbatim. It is written for a session where you want to **ask questions**, not
start work.

> I'm building `self-learning-agent`, an open-source Claude Code plugin that turns YouTube
> videos and channels into Obsidian notes plus human-approved tool setup. Read
> `HANDOVER.md` and `PLAN.md` in this repo first — **PLAN.md is the source of truth** for
> every decision, and §15–§29 are field notes from each milestone and each thing that went
> wrong.
>
> **I want to ask you questions about this project. Answer them. Do not start building
> anything, do not refactor, and do not change files unless I ask you to.** If a question
> needs you to read code or run something read-only to answer it accurately, do that —
> I'd rather you check than guess, and this project's field notes exist because guessing
> has cost it real time.
>
> Where it stands: v1 (M0–M4) and M5 are complete and **released as 0.2.2**, installable by
> anyone with `uv tool install git+https://github.com/Soham-1827/Self-Learning-Agent-Claude.git`
> plus `claude plugin marketplace add Soham-1827/Self-Learning-Agent-Claude`. 328 tests, 91%
> coverage, CI green on 3.10–3.13 with a second job that tests the installed wheel. A full
> channel run has completed for real — `@GregIsenberg`, 10 triaged, 3 picked, three notes
> and a digest. **And nobody uses it: 0 stars, 0 forks, 0 watchers.** The install works;
> it has never been shown to anyone.
>
> What's queued, in order: examples in the repo so a visitor can see a note before
> installing; then telling people; then `sla doctor`; then PyPI, M6 scheduled polling, and
> M7 — which §27 scopes and argues against for now. Four proposals from the 2026-09-25
> batch are unreviewed and `sla apply` is **mine** to run, never yours.
>
> Load-bearing rules, all earned the hard way: the description is authoritative for entity
> names and the transcript for reasoning (§15); the agent never emits a shell string (§8
> Rule 1); a scan blocks activation, never a download (§18); empty output beats invented
> output — one of those three notes correctly proposed nothing (I3, §7.2); what activates
> is exactly what was scanned (§21); edits use exact-match replacements that fail loudly
> (§22); a failure must never look like an absence, and a missing field is not a negative
> answer (§23, §24); when a failure repeats identically, vary the request before blaming
> the responder (§25); a guard written after its bug is worth nothing until you prove it
> can fail (§29); and **I pick what gets read**.
>
> Environment: WSL, checkout on `/mnt/d` (DrvFs — files read 0777, `chmod` ignored). Use
> the uv venv at `.venv`; never `sudo`. Verify on the CI matrix, not just the dev
> interpreter. `git pull --ff-only` before committing. Changing a skill needs a version
> bump in both manifests plus a push before it reaches even my own machine, because the
> plugin installs from GitHub here like everyone else. Never run `sla apply --yes` or
> answer its prompts for me.
