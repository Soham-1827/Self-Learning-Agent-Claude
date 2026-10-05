---
source: youtube
source_id: _LCeJZFIsd4
url: https://www.youtube.com/watch?v=_LCeJZFIsd4
title: "Building a Software Factory that actually works (Full Course)"
author: Greg Isenberg
published: 2026-09-14
processed: 2026-09-26T05:42:04+00:00
text_quality: auto_captions
class: tooling
class_confidence: high
status: pending-review
tags: [software-factory, agent-workflow, git-worktrees, evidence-driven-testing, code-review, parallel-agents, agents-md]
---

# Building a Software Factory that actually works (Full Course)

[Greg Isenberg](https://www.youtube.com/watch?v=_LCeJZFIsd4) · 31 min · classified **tooling** (high confidence)

> A "software factory" is not a product, a harness, or a model: it is a four-step workflow (isolate, build, prove, ship) written as markdown skills that an agent reads before every message. What makes it a factory rather than a checklist is that two of the steps can send the agent back a step on their own -- a failed after-state returns it to build, and so does a low score from an external reviewer -- so the human enters only once, at merge, and reviews visual proof instead of code.

## TL;DR

- The whole system is five or six markdown files, deliberately model- and harness-agnostic.
- agents.md should carry the workflow the agent lacks, not facts about the codebase it can already read.
- Isolate: every feature starts in a fresh git worktree branched from origin main; never build on main.
- Prove: the agent records a before state and an after state and embeds both in the PR; when the after shows a gap it returns to build unprompted.
- Ship: an external reviewer returns a score, and anything below the top score sends the agent back through build and prove.
- Ras Mic reports running up to 15 features in parallel this way, reviewing the proof rather than the code.

## Techniques & patterns

### A worktree per feature, branched from origin main

A skill called "new feature" starts every task in a fresh git worktree off origin main, and merges it back when the work is done. Four terminal tabs, four features, one app.

**When:** Any time more than one agent works on a repository, or one agent works on more than one thing.

**Why it works:** The failure it prevents is specific and common: two agents on the same branch, one told to redo how a page calls an API while the other is mid-redesign of that page. The agent is not misbehaving when it deletes the other's work, it is doing what it was told with no isolation.

### agents.md carries workflow, not codebase facts

The instruction file injected ahead of every message holds the process the agent cannot infer, rather than a description of the code.

**When:** Writing or auditing any always-on instruction file.

**Why it works:** Ras Mic's claim is that most of these files are useless because they restate what the agent will read from the code anyway. Workflow is the part that is genuinely absent from the repository.

### A code-structure skill, so output survives a reader

An opinionated instruction to write in a service-layer architecture, applied while the code is being written rather than as a later cleanup.

**When:** Any codebase that a hired developer, the author months later, or a fresh agent with no context will have to open.

**Why it works:** The stated failure mode is not incapacity but indifference: "if it could get it done in a sloppy way, it'll get it done in a sloppy way." Working and well-written are different acceptance criteria, and only one of them is checked by tests.

### Evidence-driven proof, captured as an artifact

Record the state before the change and after it -- video or screenshots -- and embed both in the PR. Where the surface is invisible, supply the measured pair instead.

**When:** Every change with an inspectable surface.

**Why it works:** It answers the failure where an agent reports success it never verified. It also changes who can review: the owner describes skimming less and less code and reviewing the proof instead.

### The agent re-enters the build step on its own

When the after-state capture does not show the claim, the skill's own criteria send the agent back to building, with no one asking it to.

**When:** Designing any multi-step agent workflow where a later step can fail.

**Why it works:** This is the difference between a checklist and a loop. The interesting part is that the re-entry condition lives in the step's success criteria rather than in a supervisor, so nothing needs to be watching.

### A scalar score is what lets the loop terminate

An external review agent returns feedback plus a confidence score out of five. Three of five sends the agent back through build, prove and ship; five of five is when the human appears and merges.

**When:** Any automated loop that has to decide for itself whether it is finished.

**Why it works:** Prose feedback cannot end a loop -- something has to be comparable against a threshold. The score, not the feedback, is the part doing the work, and it is also what keeps the human out of every iteration but the last.

### Review the proof, not the diff

The reviewer looks at before and after captures in sequence and merges on that basis, explicitly not reading most of the code.

**When:** When the person accountable for the merge did not write the code and will not read it.

**Why it works:** Worth adopting deliberately rather than by drift, because it moves the guarantee entirely onto the quality of the proof and the external reviewer. It works exactly as well as those two things do, and no better.

## Proposed actions

2 proposed (1 can be applied, 1 manual only).

#### `p1` Add a before/after proof skill

- **risk:** `none` — writes a skill file into this repo, activated separately
- **kind:** skill
- **why:** The proof discipline is the part of this workflow that is not already installed here. browser-qa automates visual checks and verification-before-completion gates the claim of being done, but neither produces the paired artifact this video is built around, and neither says to re-enter the build step when the after state does not show the claim. The other three steps of the factory are already covered: using-git-worktrees is isolate almost exactly, coding-standards and hexagonal-architecture cover build, and requesting-code-review covers ship. This is the gap worth filling, and it is written to be read before opening a PR.
- **undo:** `rm -rf ~/.claude/skills/before-after-proof`
- **evidence (14:48):** > It will literally record the before state, meaning before the feature, or let's say you're trying to fix a bug, it will record the bug in action. And what it will do after is after it's done fixing, it will record a working version after.

#### `p2` Consider an automated PR reviewer that returns a score

- **risk:** `high` — manual only — never automated
- **kind:** manual
- **you already have:** requesting-code-review, receiving-code-review, /code-review ultra
- **why:** The loop in this video terminates on a number, and nothing installed here produces one. requesting-code-review and receiving-code-review cover asking for and acting on a review, and /code-review ultra runs a multi-agent review on demand -- but all three are triggered by a person and return prose, so an agent cannot decide from them whether it is finished. Greptile is the service named in the video; Code Rabbit and Macroscope are named as alternatives. This is left as manual on purpose: it means an account with a third party and granting it read access to repositories, which is a decision to make deliberately rather than a package to install. Worth weighing against simply requiring your existing review command before merge, which costs nothing new.
- **would run:** nothing — printed for you to run by hand
- **undo:** `Revoke the service's GitHub app access and delete the account.`
- **evidence (22:25):** > Greptile not only gives feedback, it gives a confidence score... before the feedback was addressed, this score was a three out of five. What that tells my agent is that there are things that it missed.

## Project ideas

### Proof-gate the pull request instead of trusting the agent to prove

A CI check that fails any PR whose description lacks a before/after proof block -- two labelled images, a video link, or a measured pair with units -- so the evidence step cannot be quietly skipped.

**Why it's interesting:** The video treats proof as agent behaviour: the skill tells the agent to capture a before and after, and the agent mostly complies. But the same segment admits the agent sometimes "thinks it worked" without checking, which is precisely the case where it would also skip the proof. Moving the check from the agent's instructions to the repository's merge gate inverts who has to be disciplined, and it is the one part of this workflow that survives a model swap, a harness change, or an agent having a bad day. The video does not suggest it -- it is what is missing once you notice the loop depends on the agent policing itself.

**Stack:** GitHub Actions plus a small check script (Python or Node) reading the PR body through the REST API; branch protection to make the check required; optionally Playwright for capture.

**First step:** `gh pr list --state merged --limit 20 --json number,body --jq '.[] | select(.body | ascii_downcase | contains("before") | not) | .number'`

**Size:** An evening to measure the gap and write the check; a weekend to make it required and to handle the honest "no inspectable surface" case without it becoming a rubber stamp.

## Gaps & uncertainty

- The five or six markdown files are the substance of the video and were shown on screen, not read out. They are offered behind a redirect (startup-ideas-pod.link/ras-software-factory), so their actual text is not in this note and was not verified.
- Everything demonstrated was visual: pull requests, before/after screenshots, a performance table, four terminal tabs, and diagrams drawn live. None of it is recoverable from the transcript.
- The guest is treated here as Ras Mic on the strength of the linked handles (x.com/Rasmic, youtube.com/@rasmic). The captions render the name as "Ross Mike", "Mickey" and "Mike Schmollis", and the description itself says "Michael" in one summary paragraph.
- The harness running the four parallel agents is named once and mangled by the captions to "four tabs of Bezel". It is not identifiable, so the parallel setup cannot be reproduced exactly.
- The performance figures disagree between sources: the description says about 815ms to about 61ms, the transcript says 850ms at one point and "817 61" at another. No measurement method was given for any of them.
- Greptile, Code Rabbit and Macroscope are named in the description but never linked, so the products were not confirmed from an authoritative URL. Spellings follow the description.
- GPT-6 Astra is named in the description. "Fable" and "GPT-5.6 soul" appear only in the captions, so those two are ASR spellings and the second is probably garbled.
- No claim here was independently tested. The parallel-feature count, the hallucination ranking of the models, and the review scores are all as reported in the video.
- Transcript is machine-generated: prose is reliable, **proper nouns are not**. Names above come from the description where possible.

## Links from description

- [https://startup-ideas-pod.link/brex_SIP](https://startup-ideas-pod.link/brex_SIP)
- [Create your own Software Factory](https://startup-ideas-pod.link/ras-software-factory)
- [The #1 tool to find startup ideas/trends](https://www.ideabrowser.com)
- [https://latecheckout.agency/](https://latecheckout.agency/)
- [X/Twitter](https://twitter.com/gregisenberg)
- [Instagram](https://instagram.com/gregisenberg/)
- [LinkedIn](https://www.linkedin.com/in/gisenberg/)
- [X/Twitter](https://x.com/Rasmic)
- [Youtube](https://www.youtube.com/@rasmic)

## Applied

_Nothing applied yet._
