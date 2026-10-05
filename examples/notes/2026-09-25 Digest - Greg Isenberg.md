---
type: digest
created: 2026-09-25
sources: [_LCeJZFIsd4, EoNH3Tn8wYE, 84q4WA3kA8Q]
tags: [digest]
---

# Digest — Greg Isenberg

2026-09-25 · 3 note(s) · 4 proposal(s)

## Notes

### [[2026-09-14 Building a Software Factory that actually works (Full Course) (_LCeJZFIsd4)]]

tooling · pending-review · 2 proposal(s)

> A "software factory" is not a product, a harness, or a model: it is a four-step workflow (isolate, build, prove, ship) written as markdown skills that an agent reads before every message. What makes it a factory rather than a checklist is that two of the steps can send the agent back a step on their own -- a failed after-state returns it to build, and so does a low score from an external reviewer -- so the human enters only once, at merge, and reviews visual proof instead of code.

### [[2026-08-26 WebMCP Let AI Agents pay you money (EoNH3Tn8wYE)]]

mixed · pending-review · 2 proposal(s)

> WebMCP lets a website hand an agent a short list of actions instead of making it read the page, and the consequence is architectural rather than cosmetic: because the tools are declared by the site and gated on the ordinary browser session, the user brings their own agent and the site needs no API keys, no tokens and no agent of its own. It sits between headless APIs, which cannot touch the UI, and in-app agents, which cannot carry the user's context -- and it keeps the visual interface most people actually want.

### [[2026-09-24 Meta Muse AI Connectors The App Store for AI (84q4WA3kA8Q)]]

conceptual · no-actions · 0 proposal(s)

> Meta opening Muse to third-party connectors creates a distribution moment comparable to the App Store, but with one structural difference worth building around: a connector is reached in the middle of someone else's request rather than being chosen up front. The opportunity is therefore not an app people decide to use, it is being the service that can complete one specific step at the moment money changes hands -- and because nobody yet knows whether the directory produces demand, the whole thing has to be planned around distribution you can already reach.

## Proposals by risk

### none — written into the repo first, activated separately

- [[2026-09-14 Building a Software Factory that actually works (Full Course) (_LCeJZFIsd4)]] `p1` Add a before/after proof skill — writes a skill file into this repo, activated separately

### medium — runs an allowlisted command

- [[2026-08-26 WebMCP Let AI Agents pay you money (EoNH3Tn8wYE)]] `p1` Clone the WebMCP espresso store reference implementation — clones a GitHub repo; nothing in it is executed

### high — manual only, never automated

- [[2026-09-14 Building a Software Factory that actually works (Full Course) (_LCeJZFIsd4)]] `p2` Consider an automated PR reviewer that returns a score — manual only — never automated
- [[2026-08-26 WebMCP Let AI Agents pay you money (EoNH3Tn8wYE)]] `p2` Chrome flags needed before any of this runs -- including one worth thinking about — manual only — never automated

## To review

Nothing here has been applied. Per source, preview then decide:

```bash
sla apply "_LCeJZFIsd4" --dry-run
sla apply "EoNH3Tn8wYE" --dry-run
```
