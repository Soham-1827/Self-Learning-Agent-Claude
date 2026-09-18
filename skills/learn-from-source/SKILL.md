---
name: learn-from-source
description: Use when the user gives a YouTube video URL, a channel handle, or asks to learn from a creator's latest videos. Turns a source into an Obsidian vault note plus validated setup proposals, then stops for approval before anything is installed.
---

# Learn from a source

Turn a video into a note worth keeping and a short list of setup actions worth
approving. You do the judgment; the Python layer does everything deterministic.

## Procedure

### 1. Build the brief

```bash
sla brief "<video-url>" --out /tmp/brief.json
```

This is for **one video**. Given a channel (`@handle` or a channel URL), do not
build a brief for it — `sla brief @handle` silently takes only the newest video.
Follow **Channels** below instead.

If `sla` is not on PATH, the project was not installed. Use the repo checkout
instead — `PYTHONPATH=src python3 -m self_learning_agent.cli brief ...` — or install
it with `uv pip install -e .`.

Read it. It contains the video metadata, the human-typed description, the
description's links, the transcript split by chapter, and the full list of
skills, MCP servers and CLIs already installed.

### 2. Classify the source

Decide `tooling`, `conceptual`, or `mixed`, and say why in `class_reasoning`.

- **tooling** — demos repos, MCP servers, CLIs, skills, setup workflows.
  Proposals are the payload; 1–2 project ideas.
- **conceptual** — ideas, teardowns, interviews, strategy. Proposals are usually
  empty and that is correct. Project ideas are the payload; give 3–5.
- **mixed** — both carry weight.

### 3. Reconcile entities — do not extract them

**The description is authoritative for names. The transcript is authoritative for
reasoning about them.**

Auto-captions render `SkillSpector` as "Skill Specter" and `Claude Code` as
"Cloud Code" — exactly the tokens needed to find a repo. So:

- Take candidate names from `authoritative_links`, never from transcript spelling.
- Match each to the chapter discussing it **by position**, not by string search.
- A tool named only in speech and never linked is low-confidence by construction.
  It belongs in `gaps`. It must never become a proposal.

### 4. Check what is already installed

`installed_skills` is the full list with descriptions. Read it and judge. If
something already covers a recommendation, say so plainly in the note and either
drop the proposal or explain what is genuinely new about the alternative.

This is the difference between a useful note and a list of things the user
installed months ago.

### 5. Write the synthesis JSON

Match the schema in PLAN.md §9. Then:

```bash
sla note "<same-ref>" --synthesis /tmp/synth.json
```

Validation will reject anything unsafe and report it. Never edit validated
output by hand to get something past the validator.

### 6. Stop

Show the user the note path and summarise the proposals by risk tier. **Do not
apply anything.** Applying is a separate command the user runs themselves:

```bash
sla apply "<same-ref>"
```

It scans each proposal, then prompts per item. Do not run it on their behalf, and
never pass `--yes` — the approval is the point of the whole design.

## Channels: triage first, then one video at a time

When the reference is a channel, the owner chooses what gets read. Never process
a whole channel on your own initiative.

1. **Triage.**

   ```bash
   sla queue "@handle" --last 10
   ```

   This reads metadata only — titles, dates, durations, chapters, GitHub links —
   and never downloads a transcript. Videos already in the ledger are left out.

2. **Show the owner the table and let them choose.** The default is the suggested
   picks (marked `✓`, capped by `--cap`, 5 unless told otherwise). The class column
   is a guess from metadata. Say so, and never drop a video because of the guess
   without telling the owner.

3. **Process each chosen video on its own**, in full, with the single-video
   procedure above: a fresh brief, classify, reconcile, synthesise, `sla note`.
   Keep one transcript in context at a time — render one note before building the
   next brief. Several transcripts at once crowd out the reading each one needs.

4. **Digest** the ones you processed:

   ```bash
   sla digest <id> <id> ...
   ```

   It links every note, quotes each thesis, and gathers the proposals by risk tier.

5. **Stop**, as in step 6. Report the digest path and the proposals by risk tier.
   Applying is still `sla apply`, one video at a time, run by the owner.

## Rules that are not style preferences

- **Never emit a shell command.** A proposal names a package on a registry; the
  Python layer renders the command. If something cannot be expressed that way,
  it is `kind: manual` and the user runs it themselves.
- **`proposals: []` is a correct answer.** Most videos teach nothing installable.
  If you feel pressure to produce actions, that pressure is the bug.
- **Fill `gaps` honestly.** Videos demo things on screen while the audio says
  "just paste this in here". Say what you could not see.
- **Never infer a creator's pronouns from their name or voice.** Use they/them, or
  name them ("the video argues...", "Greg Isenberg attributes..."). These notes are
  about real people, and a channel handle is not a statement of pronouns.
- **A project idea needs all five parts** (§7.2): what it is, why it is
  *non-obvious*, the stack, a literal first command, and an honest size. Drop
  ideas that cannot carry all five rather than padding them out.
- **The video must be load-bearing for the idea.** If you could have written it
  without watching, it is decoration — drop it. **Zero ideas is a valid answer**,
  exactly as `proposals: []` is. A target count is an instruction to invent.
- **Where there is no authoritative text to check against** (no description links,
  no chapters), say in `gaps` that specifics were reconstructed from speech. ASR is
  unreliable for any notation a domain treats as precise — product names, card
  notation, version numbers, command flags.
