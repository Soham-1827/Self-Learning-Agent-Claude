---
source: youtube
source_id: 9_SZFIW7tus
url: https://www.youtube.com/watch?v=9_SZFIW7tus
title: "5 GitHub Repos: Kill AI Slop, Go Viral, Make Money"
author: Greg Isenberg
published: 2026-09-02
processed: 2026-09-09T05:36:19+00:00
text_quality: auto_captions
class: tooling
class_confidence: high
status: pending-review
tags: [youtube, greg-isenberg, github, agent-tooling, security]
---

# 5 GitHub Repos: Kill AI Slop, Go Viral, Make Money

[Greg Isenberg](https://www.youtube.com/watch?v=9_SZFIW7tus) · 25 min · classified **tooling** (high confidence)

> Greg treats GitHub as an early-warning system for the agentic era: the tools people will discuss in six months are visible there today. The video reviews five repos that got attention in the last 30 days, and closes with a deliberately small method — install the repo, make one small workflow actually work, then decide whether to productise it or keep it as private leverage.

## TL;DR

- GitHub is where agentic tooling surfaces before it becomes SaaS; watching it is an unfair advantage.
- Scan agent skills before installing them — a skill carries instructions and tool access, not just text.
- Agent-driven video editing turns a creator's repeated edits into something an agent can replay.
- An agentic CRM maintains the relationship graph instead of waiting for you to update it.
- Do not automate the whole workflow on day one; get one small repeatable format working first.

## Tools & resources mentioned

| Tool | Link |
|---|---|
| petergyang/no-ai-slop | https://github.com/petergyang/no-ai-slop |
| trycompai/crm | https://github.com/trycompai/crm |
| browser-use/video-use | https://github.com/browser-use/video-use |
| NVIDIA SkillSpector | https://github.com/NVIDIA/SkillSpector |
| phone-harness | https://github.com/ShawnPana/phone-harness |

## Techniques & patterns

### Scan the tool before you hand it to your agent

Run a security scan over any skill, MCP server or plugin before installing it, checking for prompt injection, hidden instructions, data exfiltration and supply-chain risk.

**When:** Every time you install a capability from GitHub or a marketplace, which is now routine rather than rare.

**Why it works:** A skill is not inert text — it carries instructions, scripts, dependencies and tool access, and it steers an agent that can touch files and call services. As builders assemble many small capabilities, the setup starts behaving like an operating system, and security stops being an enterprise-only concern.

### One small repeatable format before any system

When adopting an agent tool, pick a single narrow output you already produce repeatedly, and make only that work end to end before generalising.

**When:** Day one with any new agentic repo, particularly content and automation tooling.

**Why it works:** Greg Isenberg attributes most failed adoptions to asking for too much immediately. One working format is a system you can trust; an ambitious pipeline that half-works teaches you nothing about whether the tool is good.

### Install, prove, then decide to productise

A three-step method for evaluating any repo: install it, get one small workflow genuinely working, then choose deliberately between turning it into a product and keeping it as private leverage.

**When:** Evaluating any of the repos in this video, or any tool found the same way.

**Why it works:** It forces the productise-or-not question to be answered after evidence rather than during the initial excitement.

## Proposed actions

3 proposed (2 can be applied, 1 manual only).

#### `p1` Add a scan-before-install skill

- **risk:** `none` — writes a skill file into this repo, activated separately
- **kind:** skill
- **why:** You have 256 skills installed and add more from GitHub regularly, which is exactly the exposure SkillSpector exists to address. This captures the procedure as a durable workflow rather than a thing you remember once. Nothing installed currently covers it — security-scan targets application source code, not agent capabilities.
- **undo:** `rm -rf ~/.claude/skills/scan-before-install`
- **evidence (15:15):** > before you hand your AI a new tool, scan the tool

#### `p2` Clone browser-use/video-use to evaluate agent-driven editing

- **risk:** `medium` — clones a GitHub repo; nothing in it is executed
- **kind:** repo_clone
- **why:** Closest of the five to your own goals: it turns repeated editing decisions into something an agent can replay. Your installed video-editing and remotion-video-creation skills cover rendering and programmatic video, not agent-driven editing of raw footage, so this is genuinely new. Cloning only — nothing is executed.
- **would run:** `git clone --depth 1 https://github.com/browser-use/video-use.git`
- **undo:** `rm -rf ./video-use`
- **evidence (10:52):** > it lets you edit videos with coding agents

#### `p3` Install SkillSpector (NVIDIA) to scan skills before installing them

- **risk:** `high` — manual only — never automated
- **kind:** manual
- **why:** The highest-value repo in the video for your setup. It cannot be automated here: the documented install is `uv tool install git+https://github.com/NVIDIA/SkillSpector`, which installs directly from a git URL rather than an allowlisted registry, so it is effectively clone-and-execute. Run it yourself after reading the repo.
- **would run:** nothing — printed for you to run by hand
- **undo:** `uv tool uninstall skillspector`
- **evidence (15:15):** > the quick install is UV tool install git plus, and then you just post the GitHub link

## Project ideas

### Install gate for agent capabilities

A pre-install hook that stages any skill or MCP server, scans it, and refuses activation on high-severity findings — turning the scan-before-install habit into something that cannot be forgotten.

**Why it's interesting:** Greg Isenberg names this as an open opportunity: 'someone's going to need to help them decide what's safe.' It is also the same shape as the approval gate in this very project, so you would be building a general version of a thing you already understand. The non-obvious part is that the gate must run before the skill's text ever reaches an agent's context, not after.

**Stack:** Python, SkillSpector as the scanner, a Claude Code PreToolUse hook (you already have hooks configured in ~/.claude/settings.json)

**First step:** `skillspector scan ~/.claude/skills/scan-before-install`

**Size:** weekend

### One-format clip pipeline for a single niche

Take video-use and make exactly one repeatable transformation work end to end — lecture recording to three short clips with subtitles — then run it on your own material for a month before generalising.

**Why it's interesting:** It follows the video's own advice rather than fighting it, and the constraint is the point: one format that genuinely works is evidence, while a broad pipeline that half-works teaches you nothing. the video explicitly flags the niche version as a business ('every niche needs content, nobody enjoys editing it').

**Stack:** browser-use/video-use, ffmpeg, Claude Code as the driving agent

**First step:** `git clone --depth 1 https://github.com/browser-use/video-use.git`

**Size:** weekend for one format, a month to know if it holds

## Gaps & uncertainty

- Greg demonstrates each repo on screen while the audio says things like 'you just type in' — the exact UI steps and flags are not recoverable from the transcript.
- The auto-transcript renders SkillSpector as 'Skill Specter' and Claude Code as 'Cloud Code'. Names here were taken from the description links instead.
- Setup requirements for the agentic CRM (database, hosting, auth) and phone-harness (a physical iPhone, developer tooling) are not stated in the audio.
- No independent verification of any repo's quality or maintenance status — this note relays what the video claims.
- Transcript is machine-generated: prose is reliable, **proper nouns are not**. Names above come from the description where possible.

## Links from description

- [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop)
- [trycompai/crm](https://github.com/trycompai/crm)
- [browser-use/video-use](https://github.com/browser-use/video-use)
- [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector)
- [phone-harness](https://github.com/ShawnPana/phone-harness)
- [The #1 tool to find startup ideas/trends](https://www.ideabrowser.com)
- [https://latecheckout.agency/](https://latecheckout.agency/)
- [X/Twitter](https://twitter.com/gregisenberg)
- [Instagram](https://instagram.com/gregisenberg/)
- [LinkedIn](https://www.linkedin.com/in/gisenberg/)

## Applied

### 2026-09-18T03:06:59+00:00

- **applied** `p1` Add a scan-before-install skill — copied to /home/sohamchoulwar/.claude/skills/scan-before-install · undo: `rm -rf /home/sohamchoulwar/.claude/skills/scan-before-install`

