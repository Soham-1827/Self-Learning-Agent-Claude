---
source: youtube
source_id: EoNH3Tn8wYE
url: https://www.youtube.com/watch?v=EoNH3Tn8wYE
title: "WebMCP: Let AI Agents pay you money"
author: Greg Isenberg
published: 2026-08-26
processed: 2026-09-26T05:46:45+00:00
text_quality: auto_captions
class: mixed
class_confidence: high
status: pending-review
tags: [webmcp, mcp, agent-native, browser-agents, ecommerce, startup-ideas, chrome-experimental]
---

# WebMCP: Let AI Agents pay you money

[Greg Isenberg](https://www.youtube.com/watch?v=EoNH3Tn8wYE) · 29 min · classified **mixed** (high confidence)

> WebMCP lets a website hand an agent a short list of actions instead of making it read the page, and the consequence is architectural rather than cosmetic: because the tools are declared by the site and gated on the ordinary browser session, the user brings their own agent and the site needs no API keys, no tokens and no agent of its own. It sits between headless APIs, which cannot touch the UI, and in-app agents, which cannot carry the user's context -- and it keeps the visual interface most people actually want.

## TL;DR

- WebMCP is MCP tools declared inside the browser UI: the site tells the agent how to search, compare, add to cart, apply a coupon.
- The login state is the auth layer. Tools are conditional on the browser session, so no API keys or tokens change hands.
- It replaces screenshot- and DOM-scraping approaches, which Vinny calls slow and fragile, with a concise declared tool list.
- Positioned in the middle of an agent-native map: raw API and MCP server (headless) -> computer use and browser MCP (reading) -> WebMCP -> in-app agent (bound to the vendor).
- Experimental in Chrome, described as a joint Microsoft and Google effort launched in February, from a proposal made about two years earlier.
- First markets named: compatibility-driven commerce, SaaS admin and analytics consoles, read-only tools in regulated sectors, and internal tools.
- Two costed ideas close the episode: an agent-readiness agency, and a service that tests whether agents can finish the journeys that matter.

## Tools & resources mentioned

| Tool | Link |
|---|---|
| vincanger/webmcp-espresso-store | https://github.com/vincanger/webmcp-espresso-store |

## Techniques & patterns

### Declare the actions instead of letting the agent infer them

The site exposes a short, explicit tool list -- the demo store has 16 -- so the agent calls a named action rather than reading the whole DOM and deciding where to click.

**When:** Any flow where an agent currently has to interpret a page to act on it.

**Why it works:** The cost being removed is interpretation, not clicking. Screenshot and DOM approaches are described as slow and fragile because every run re-derives what the page affords; a declared list is the same information, stated once, by the party that actually knows it.

### Let the browser session be the auth layer

Tools are conditional on login state: logged out, the demo exposes three; logged in, the full set appears. The agent inherits the session rather than holding a credential.

**When:** Exposing anything authenticated to an agent.

**Why it works:** It removes the hardest part of the usual agent integration -- issuing, scoping, storing and rotating tokens -- by reusing an auth decision the user already made in the browser. Worth noting the flip side the episode does not dwell on: any agent driving that browser inherits everything the session can do, so the blast radius is the session, not a scoped key.

### Place an integration on the headless-to-bound axis before choosing one

A map from fully headless (raw API, MCP server) through reading approaches (computer use, browser MCP) to WebMCP and finally in-app agents, which are bound to the vendor's own assistant.

**When:** Deciding how a product should be reachable by agents at all.

**Why it works:** It turns a technology choice into two explicit trade-offs: who pays for tokens, and whether the user's agent keeps its context. In-app agents lose the second even when they win the first, which is the complaint the episode is answering.

### Read-only tools as the way into a regulated flow

Where actions are too sensitive to expose, ship tools that only retrieve and explain -- find the right form, pull the right figure -- and none that change state.

**When:** Insurance, banking self-service, or any console where a wrong write is expensive.

**Why it works:** It separates the value of being agent-readable from the risk of being agent-actionable, which is usually the blocker. Most of the benefit in a guided flow is navigation, and navigation is read-only.

### SEO, then AEO, then whether the agent finishes the job

Three questions in sequence: can a crawler understand the page, will a model cite it, can an agent complete the transaction.

**When:** Framing why agent-readiness is a budget line rather than an experiment.

**Why it works:** It is a sales frame more than a technical one, and it is effective because each step is something the buyer has already paid for once. The third is the only one that touches revenue directly.

### Build for the standard while it is still experimental

Treat an experimental feature as an arbitrage window: learn it before adoption, and sell the expertise as adoption arrives.

**When:** Deliberately, with an exit condition -- not as a default posture.

**Why it works:** The argument given is that the window closes when the thing becomes popular. The honest counterweight is that experimental standards also change or get withdrawn, and the episode's own evidence for persistence is that Google has backed it for a couple of years, which is suggestive rather than binding.

## Proposed actions

2 proposed (1 can be applied, 1 manual only).

#### `p1` Clone the WebMCP espresso store reference implementation

- **risk:** `medium` — clones a GitHub repo; nothing in it is executed
- **kind:** repo_clone
- **why:** This is the only place the actual API surface exists -- the episode never speaks a function or manifest name, so the tool declarations cannot be learned from the transcript. The repo is offered for exactly this in the description, and it carries 16 working tools including the conditional logged-in set, which is the mechanism worth reading. Nothing installed here overlaps: playwright, browser-use and browserbase are MCP servers for driving a browser, and browser-qa automates visual checks -- all of them the reading end of this episode's own map. WebMCP is the opposite side, something a site declares about itself, so there is no client to install and a repo is the only artifact.
- **would run:** `git clone --depth 1 https://github.com/vincanger/webmcp-espresso-store.git`
- **undo:** `rm -rf webmcp-espresso-store`
- **evidence (26:11):** > You can also click on the GitHub repo button down there next to the WebMCP tools pill and you can clone this repo and you can play around with it, make your own version, whatever.

#### `p2` Chrome flags needed before any of this runs -- including one worth thinking about

- **risk:** `high` — manual only — never automated
- **kind:** manual
- **why:** The demo does not work in a default browser, and the episode gives the two settings in passing at 26:11. The second one deserves more care than it gets there: allowing remote debugging opens a control channel to your browser that any local process can attach to, and that browser is the one holding your logged-in sessions -- which is the same session WebMCP deliberately uses as its auth layer. Convenient for the demo, and a wide door. Left manual so the decision is yours, and so it is a deliberate act rather than something a tool did for you.
- **would run:** nothing — printed for you to run by hand
- **undo:** `Disable the WebMCP flag in chrome://flags and turn remote debugging back off, or delete the throwaway profile.`
- **evidence (26:11):** > Go into Chrome flags, enable WebMCP support and go into Chrome inspect and allow remote debugging. So these are the things that you'll want to enable so that you can start using these experimental features.

## Project ideas

### Agent-readiness agency for businesses that will never build this themselves

Add a small set of WebMCP tools -- request a quote, book a consult, check availability -- to the websites of law firms, HVAC and home services, med spas and dental practices. Sold as setup plus a monitoring retainer, and packaged alongside a conventional MCP server so the offer survives the standard changing.

**Why it's interesting:** The non-obvious part is not the agency, it is Vinny's reframing of what you sell: not WebMCP, but the expert seat on a standard nobody has hired for yet, with WebMCP as one item in a package that also covers MCP servers and internal tools. That makes the offer robust to the very thing that should worry you -- an experimental Chrome feature changing shape -- because the retainer is for staying current, not for a specific API. The target list is also chosen against the grain: these are businesses with no engineering function, which is exactly why a two-tool V1 is worth thousands.

**Stack:** The reference repo as the delivery template; whatever CMS or site builder each client already runs; a conventional MCP server for the headless half of the package; uptime and eval monitoring for the retainer.

**First step:** `gh repo clone vincanger/webmcp-espresso-store`

**Size:** Read the repo in an evening to see how few lines one tool costs -- that number is your margin. Weeks to a first paying client, since the bottleneck is sales to non-technical owners, not delivery. Treat the retainer as the product and the setup fee as customer acquisition.

### Mystery shopper for agent journeys

Run the journeys that actually matter -- buy the item, book the consult, file the claim, reorder -- as an agent would, on a schedule, and report where it stalled: which step failed, which descriptions were unreadable, which tools were missing, and what that costs in conversion.

**Why it's interesting:** It sells a number to people who currently have no way to get one: nobody knows whether an agent can check out on their store, and analytics cannot tell them because a stalled agent looks like a bounced visitor. The reason it has to be a real browser rather than a crawl is specific to this technology -- WebMCP tools are declared at runtime by the page's own code, so there is no manifest to fetch and no way to audit a site from the outside without driving it. That also makes the finding durable: the first report on almost any site is "zero tools exposed", which is both the diagnosis and the sales pitch for fixing it.

**Stack:** Playwright or an equivalent driver in Chrome with WebMCP enabled; an agent to attempt each journey; a scheduler; a report template; and, as the repeat findings accumulate, a fix library that turns into the actual software.

**First step:** `npx playwright open --device="Desktop Chrome" https://example-target-store.com`

**Size:** A weekend to produce one honest hand-run report for a single site, which is enough to sell the second one. Months to automate scheduling, scoring and regression across clients -- and that automation is the business, not the reports.

## Gaps & uncertainty

- The live demo store is the thing to actually try, and its URL is not recoverable: the captions render it as "crema andco uh clientfly.dev" and the promised show-notes link is absent from the description. The repo is linked, the running store is not.
- No WebMCP API surface appears anywhere in the transcript -- no function, object or manifest name is spoken. How a tool is declared has to be read from the repo; nothing about it is asserted here.
- Everything was a screen share: the tool list appearing and shrinking on logout, the side-by-side comparison, the cart and coupon, and the agent-native diagram. None of it is in the text.
- The guest is Vinny per the description and its FIND VINNY ON SOCIAL block, with the repo under the handle vincanger. The captions also say "Vince" and "Vinnie" throughout.
- Setup pricing disagrees between sources: the description says $2,000 to $10,000, the transcript says "$200 to $10,000". The description is treated as authoritative and the discrepancy is noted rather than resolved.
- Espresso machine names come from captions only ("Mara X", "Lit Bianca") and are unreliable as spelled. They are incidental to the point being demonstrated.
- Agent product names are mangled in the captions -- "Grockbot", "Claude Co-work", "Chatg GPT work" -- so the list of agents said to work with this is not quotable.
- The tweet that frames the in-app-agent complaint is attributed in the captions to "Dylan from Cloudflare". Unverified, and not in the description.
- The February launch date, the two-year-old proposal, and the joint Microsoft and Google attribution are all as stated in the episode. The description repeats them, so they are internally consistent but not independently checked.
- No claim about efficiency is measured. That declared tools beat DOM scraping is argued from first principles and demonstrated once, not benchmarked.
- Transcript is machine-generated: prose is reliable, **proper nouns are not**. Names above come from the description where possible.

## Links from description

- [https://github.com/vincanger/webmcp-espresso-store](https://github.com/vincanger/webmcp-espresso-store)
- [The #1 tool to find startup ideas/trends](https://www.ideabrowser.com)
- [https://latecheckout.agency/](https://latecheckout.agency/)
- [X/Twitter](https://twitter.com/gregisenberg)
- [Instagram](https://instagram.com/gregisenberg/)
- [LinkedIn](https://www.linkedin.com/in/gisenberg/)
- [X/Twitter](https://x.com/hot_town)
- [Youtube](https://www.youtube.com/channel/UCHP5Hdx0X-sM0uv2bl_OOqg)

## Applied

_Nothing applied yet._
