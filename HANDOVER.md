# Handover

Paste this file to a new session to pick the project up cold.

---

## What this is

`self-learning-agent` — a pipeline that watches a creator's video (Greg Isenberg and
others), writes a note into an Obsidian vault explaining what it teaches and what to
use, then installs and configures the worthwhile parts **behind an explicit human
approval gate**.

Open source, MIT. Repo: https://github.com/Soham-1827/Self-Learning-Agent-Claude
Owner: @Soham-1827 — an AI student who wants to build projects from what these videos teach.

**Read [PLAN.md](PLAN.md) first.** It is the source of truth: decisions D1–D7,
improvements I1–I4, the security model, and field notes from each milestone.

## Where things stand

| M | What | Status |
|---|---|---|
| M0 | Repo skeleton, CI (py3.10–3.12), MIT | ✅ done |
| M1 | `sla fetch` — resolve, fetch, cache, dedupe | ✅ done |
| M2 | `sla inventory` — installed skills / MCP / CLIs | ✅ done |
| M3 | `/learn` — synthesis into a vault note + `proposals.json` | ✅ done |
| M4 | Approval gate + `sla apply` | ✅ done |
| M5–M7 | Channel batch, scheduling, frontend | not started |

**v1 = M0–M4, complete.** 169 tests passing, 80% coverage.

## How to run it

```bash
cd /mnt/d/Self-Learning-Agent
PYTHONPATH=src python3 -m self_learning_agent.cli fetch "https://www.youtube.com/watch?v=9_SZFIW7tus"
PYTHONPATH=src python3 -m self_learning_agent.cli inventory
PYTHONPATH=src python3 -m self_learning_agent.cli inventory --against "audits skills for prompt injection"
PYTHONPATH=src python3 -m self_learning_agent.cli apply "<same-url>" --dry-run
PYTHONPATH=src python3 -m self_learning_agent.cli status
```

Once `pip` exists: `pip install -e ".[dev]"` then plain `sla ...` and `pytest`.

## Environment gotchas (this machine, WSL2)

1. **System `python3` is 3.10 with no `pip` and no `ensurepip`** — Ubuntu splits those
   into `python3-venv`, which is not installed. **Do not reach for `sudo`**: `uv` is
   already installed and solves this without a password, and it supplies its own
   interpreter, which also clears the 3.10 problem.

   ```bash
   uv venv --python 3.14 .venv
   uv pip install --python .venv/bin/python -e ".[dev]"
   .venv/bin/sla status          # or: source .venv/bin/activate && sla status
   .venv/bin/python -m pytest    # 169 tests, 80% coverage
   ```

   Never work around a missing pip by piping a downloaded script into Python — that is
   the exact pattern this project classifies as risk tier `high`.
2. **The venv is at `.venv/` (gitignored).** Tests run under Python 3.14.7 there, while
   CI covers 3.10–3.12.
3. **`yt-dlp` is a zipapp** at `~/.local/bin/yt-dlp.pyz`, not a pip package.
   `config.discover_ytdlp()` finds it. Override with `SLA_YTDLP`.
4. **Python is 3.10.12** and yt-dlp warns 3.10 is deprecated. CI covers 3.10–3.12.
5. **Git pushes work** via the Windows Git Credential Manager, wired up during setup
   (`credential.helper` in global git config). `gh` is not installed.
6. Project lives on `/mnt/d` (v9fs); `~/.claude` is on ext4. This matters for symlinks.

## Running it on Windows vs WSL

Both work. They have complementary gaps, and this is worth knowing before debugging
a "broken" install:

| | Windows (Git Bash / PowerShell) | WSL |
|---|---|---|
| `pip` | present | **missing** (needs `sudo apt install python3-pip`) |
| Python | 3.12 | 3.10 — deprecated by yt-dlp, below SkillSpector's 3.12 floor |
| The 256 installed skills | **not visible** (1 skill in the Windows `~/.claude`) | all of them |
| Claude Code | — | runs here |

State is **not shared**: config, ledger, cache and stored proposals live under each
platform's own home, so a note written in WSL cannot be applied from Windows. Point
`SLA_HOME` at a shared path if you need one environment to see the other's work.

Windows Python cannot read WSL's `~/.claude` through the `\\wsl$` share when invoked
from inside WSL, so `CLAUDE_CONFIG_DIR` is not a workaround for the inventory gap.

**Recommendation: WSL, once `pip` is installed there.** It is where the skills and
Claude Code live, and inventory is the step that makes notes useful rather than noisy.

```bash
# Git Bash / VS Code terminal on Windows
PYTHONPATH=src python -m self_learning_agent.cli fetch "<url>"

# PowerShell
$env:PYTHONPATH="src"; python -m self_learning_agent.cli fetch "<url>"

# WSL
PYTHONPATH=src python3 -m self_learning_agent.cli fetch "<url>"
```

## The two findings that shaped the design

### 1. Descriptions beat transcripts for names (PLAN §15)

Auto-captions are clean, punctuated prose — but proper nouns break:
`SkillSpector` → "Skill Specter", `Claude Code` → "Cloud Code". Those are exactly the
tokens needed to find a repo. The description holds the correct URLs verbatim.

> **The description is authoritative for entity names. The transcript is
> authoritative for reasoning about them.**

`Link.repo_slug` preserves URL casing for this reason and is regression-tested.

### 2. `Path.rglob` hides symlinked skills (PLAN §16)

32 of 224 skill directories on this machine are symlinks. `rglob` does not descend
into them, so the first inventory silently found 191 of 223. Fixed with
`os.walk(followlinks=True)` plus realpath cycle protection. Regression-tested.

Side effect: this **proves Claude Code follows symlinks** for skill discovery, which
resolved an open question. Copy is still the default install mode (D7) for
cross-platform reasons, but `install_mode = "symlink"` is now known to work.

## What to build next: M5 (channel batch)

Turn a `SourceDocument` + `Inventory` into a vault note and `proposals.json`.

The pieces already exist: `sources.YouTubeSource.fetch()` gives the document,
`inventory.collect()` gives what is installed. M3 is the synthesis step plus
`vault.py` to render and write the note.

Specified in PLAN.md §7 (note format), §7.1 (classification), §7.2 (project-idea
quality bar), §9 (`proposals.json` schema).

**Do not skip these when implementing M3:**

- **Entity reconciliation, not extraction.** Candidate names come from description
  links; transcript discussion is aligned to them by chapter position. A tool named
  only in speech and never linked is low-confidence **by construction** and belongs in
  `## Gaps & uncertainty`, never in a proposal.
- **`proposals: []` is a correct, common output** (I3). If synthesis is expected to
  produce actions it will invent them. Conceptual videos usually have nothing to install.
- **The agent never emits a shell string** (§8 Rule 1). A proposal names a package on a
  registry; Python renders the command from a template.
- **`similar_skills()` is a shortlist, not a verdict.** Keyword overlap cannot tell that
  two descriptions mean the same thing; it narrows 256 skills to ~3 for the agent to
  read and judge. `has_skill` / `has_mcp` / `has_cli` are the exact, reliable checks.

## Test fixture

`9_SZFIW7tus` — Greg Isenberg, *"5 GitHub Repos: Kill AI Slop, Go Viral, Make Money"*,
24.7 min, 7 chapters, 5 GitHub repos in the description, 4150 words of auto-captions.
Trimmed metadata and captions are committed under `tests/fixtures/`, so the suite runs
offline. It is an ideal `tooling`-class example. **A `conceptual`-class fixture is still
needed** to test the other branch of §7.1.

## Open questions (PLAN §14)

- Exact folder structure inside the vault
- Per-run token/cost cap for batch mode (M5)
- Whether `none`-risk auto-apply is opt-in or always-confirm

## Prompt to paste into a new session

> I'm building `self-learning-agent`, an open-source pipeline that turns YouTube videos
> into Obsidian notes plus human-approved tool setup. Read `HANDOVER.md` and `PLAN.md`
> in this repo — PLAN.md is the source of truth for decisions.
>
> M0–M2 are done (fetch, cache, dedupe, inventory), 45 tests passing. Next is M3:
> synthesis into a vault note plus `proposals.json`, specified in PLAN.md §7, §7.1,
> §7.2 and §9.
>
> Two rules that are load-bearing, not stylistic: the video description is
> authoritative for entity names while the transcript is authoritative for reasoning
> about them (§15), and the agent must never emit a shell string — proposals name
> registry packages and Python renders the command (§8 Rule 1).
>
> Note `pip` is not installed on this machine and installing it needs sudo.
