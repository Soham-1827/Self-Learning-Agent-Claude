---
source: youtube
source_id: 84q4WA3kA8Q
url: https://www.youtube.com/watch?v=84q4WA3kA8Q
title: "Meta Muse AI Connectors: The App Store for AI?"
author: Greg Isenberg
published: 2026-09-24
processed: 2026-09-26T05:51:24+00:00
text_quality: auto_captions
class: conceptual
class_confidence: high
status: no-actions
tags: [meta-muse, ai-connectors, startup-ideas, distribution, marketplaces, lead-generation, mcp]
---

# Meta Muse AI Connectors: The App Store for AI?

[Greg Isenberg](https://www.youtube.com/watch?v=84q4WA3kA8Q) · 26 min · classified **conceptual** (high confidence)

> Meta opening Muse to third-party connectors creates a distribution moment comparable to the App Store, but with one structural difference worth building around: a connector is reached in the middle of someone else's request rather than being chosen up front. The opportunity is therefore not an app people decide to use, it is being the service that can complete one specific step at the moment money changes hands -- and because nobody yet knows whether the directory produces demand, the whole thing has to be planned around distribution you can already reach.

## TL;DR

- A connector lets Muse use your service when someone asks it for help; Meta runs a submission process, an approved directory, and editorial featuring.
- The structural difference from an app: your service becomes relevant halfway through a larger request, not at the point of choosing software.
- Duffel is the working example named -- flight search and booking management through Muse -- though its billion-dollar figure is company-wide transaction value, not Muse revenue.
- Four ideas, ordered by capital needed: supplier lead gen, home repair dispatch, paddle court and match finding, family dinner planning.
- Distribution cannot assume the directory: creators, product-led sharing, and joining an already-connected marketplace are the routes you control.
- Build the availability check and the quote first, then booking; test the awkward requests before submitting or expect rejection.
- Two open questions stated outright: how many users Muse reaches, and how selective Meta's approval turns out to be.

## Techniques & patterns

### Sell into the middle of a request, not the start of one

Find the step inside a larger job where someone needs a business that can actually deliver and money changes hands -- equipment rental surfacing while someone is booking an event venue.

**When:** Choosing what to build for any agent platform where the user states a goal rather than picking a tool.

**Why it works:** It inverts how software is usually positioned. Nobody will ever decide to use your connector; they will decide to organise an event. That makes the unit of competition a single step performed well, which is a far smaller thing to build than a product someone chooses, and a far harder thing to market directly.

### Order ideas by what you can show before you build

Lead generation goes first on a small budget, because a useful sample can be assembled by hand and shown to a customer before much software exists.

**When:** Picking between several plausible ideas with limited capital.

**Why it works:** The ranking criterion is not market size but how early you can put something real in front of someone who might pay. It is a capital-efficiency test disguised as an idea-selection test, and it quietly rules out anything whose first demo requires the integration to work.

### Freshness and provenance as the product

For a lead product, what is sold is not contacts -- general contact search already exists -- but knowing something timely about a specific market, with a source for each claim and re-verification as facts change.

**When:** Any data product competing against an existing database.

**Why it works:** It names the real work honestly: a planned opening gets delayed, a second location gets announced while you still show the first, so keeping it current is most of the cost and therefore most of the moat. Sell the maintenance, not the list.

### Prefer work whose output is naturally multiplayer

One person books a court and shares a page with three other players showing time and location; the recipients get value before signing up for anything.

**When:** Choosing between two otherwise comparable ideas.

**Why it works:** The sharing has to be the work itself rather than an invite prompt bolted on. A booking that must be communicated to other people carries distribution inside the transaction, which is why this belongs in idea selection rather than in a later growth plan.

### Enter through a marketplace that is already connected

Where an existing marketplace has a connector -- Ticketmaster is the example given -- participating in it can reach the same customer without building or getting a connector approved.

**When:** Your industry already has an aggregator and you are not sure you need your own listing.

**Why it works:** It decouples the opportunity from Meta's approval queue and from your own engineering. The follow-on question is the useful one: for every connected service, ask where its supply comes from, because that is the door.

### Do not plan on being featured

Editorial placement in the directory is treated as upside, not a channel, on the strength of a past App Store feature that arrived unannounced and produced roughly 40,000 downloads a day.

**When:** Writing any distribution plan for a curated platform.

**Why it works:** The anecdote argues against itself deliberately: the feature worked and was also arbitrary, so it cannot be a plan. Every route in the episode is chosen to be one you can point to a named person or channel for.

### Test the awkward requests before submitting

Ask for time that is already booked, use an expired code, repeat a request to check it does not create a second reservation, and try the thing a customer asks next -- moving the booking to another day.

**When:** Before any review submission, and generally before exposing an action to an agent.

**Why it works:** This is the most transferable item in the episode. Three of the four are ordinary integration hygiene -- conflict, expiry, idempotency -- and the fourth is a product question. An agent will reach every one of them faster than a human UI ever did, because it retries without embarrassment.

### Check whether the connector already exists inside your product

If you already ship software, start from what customers can do through your API today.

**When:** You have an existing product and are wondering whether this applies to you.

**Why it works:** It reframes the work as exposure rather than construction. Duffel is cited as precisely this: an existing business becoming reachable through a new interface, not a new business.

## Proposed actions

Nothing here is worth installing. No actions proposed.

## Project ideas

### Timely supplier leads for one trade in one city

A connector that answers "which businesses near me are about to need what I sell" -- restaurants opening soon, for a linen supplier in one city -- returning each candidate with a source, an expected opening date, and a public contact where one is available.

**Why it's interesting:** Contact databases already exist, so the product cannot be the contacts. What is being sold is that a specific fact is true this week, in one market, which is why the episode insists on verifying each entry and on re-checking as openings slip. That makes maintenance the moat rather than coverage -- the opposite of how lead databases usually compete. It is also the one idea here you can validate with no software at all: assemble ten verified openings by hand, show them to one supplier, and ask what a weekly version is worth.

**Stack:** Sources you are permitted to use (local business announcements and filings), a verification pass, a small store keyed by claim with its source and check date, and a connector exposing one query. A spreadsheet is a legitimate first backend.

**First step:** `mkdir -p supplier-leads && printf 'business,city,expected_open,source_url,contact,verified_on\n' > supplier-leads/openings.csv`

**Size:** A weekend to fill that file by hand for one city and one trade, which is the whole validation. Weeks to automate collection and verification. The honest risk is not technical: it is whether the supplier already knows who is opening.

### Same-day repair dispatch for one appliance type in one town

A connector that takes "my dishwasher is broken, find someone who handles this model and can come tomorrow" and returns only providers who service that model and have confirmed availability, charging the provider an agreed fee per qualified introduction or confirmed booking.

**Why it's interesting:** The interesting part is an asymmetry the episode states plainly: the homeowner needs this rarely, the repair company needs flow every day. So the two things to measure are different -- total demand across the local market, and how often one person returns -- and only the first one pays. Thumbtack already proved providers will buy leads, which removes the demand question and leaves the hard one: delivering requests providers actually want, for a specific model, with real availability. Confirmed availability is the product; a list of maybes is what already exists.

**Stack:** A small roster of participating providers with the models each handles; a real availability check (a phone call is an acceptable v1); a connector exposing match-and-dispatch; fee tracking per introduction.

**First step:** `Call five appliance repair companies in one town and ask two questions: which models they will not touch, and what a confirmed same-day job is worth to them.`

**Size:** A week of phone calls before any code, because the roster is the business. A month for a working connector against a handful of providers. Scaling is a recruitment problem in every new town, not an engineering one.

### Paddle court and match finding for one city

A connector answering "find me a game tonight near my level" or "book a court for four", searching participating clubs for open slots, showing cost, and sharing the booking with the other players.

**Why it's interesting:** This is the idea whose distribution is built into the transaction: a booked court has to be communicated to three other people, so each completed job puts the service in front of new users who already have a reason to care. It is also the idea with the most honest dependency, which the episode does not hide -- clubs must agree to expose availability and accept reservations, and some will not. Playtomic is named as an existing option (hedged as "I think it's called"), so the wedge has to be a specific gap: the clubs a player currently has to check separately.

**Stack:** Agreements with a handful of local clubs; whatever each uses for bookings, including none; a shared booking page as the sharing surface; a connector for search and reservation.

**First step:** `Visit or ring every paddle club within range of one neighbourhood and ask how a non-member currently checks whether a court is free tonight.`

**Size:** Days to map the clubs and find out how many will cooperate -- do this before anything else, because a no from the clubs ends it. A few weeks to a working booking flow for two or three of them. Genuinely seasonal and genuinely local.

### Three nights of dinners from what is already in the kitchen

A connector that turns "sort out dinners for three nights, 20 minutes each, we already have rice and broccoli" into a tested plan, adjusts quantities, and hands the missing ingredients to a shoppable grocery list the customer reviews and buys.

**Why it's interesting:** The constraint in the request is the whole idea: time per meal, and what is already in the house. That is the part recipe apps skip and the part a stated request makes available for the first time. Instacart's developer tools are named as the route from plan to checkout, which means the hard part is not commerce but having recipes tested for a specific kind of family and learning what they actually cooked. Weakest of the four on defensibility -- meal planning is a crowded graveyard, and the episode's own aside that a grocery player might simply acquire this is really an admission that the moat is thin.

**Stack:** A small library of recipes you have actually cooked, tagged by time and equipment; quantity scaling; Instacart's developer tools for the shoppable list; a connector taking constraints and returning a plan; a weekly feedback loop on what was cooked.

**First step:** `Cook and time twenty weeknight meals yourself, recording which ones came in under twenty minutes and what had to be bought for each.`

**Size:** A month of real cooking before a line of code, which is the part that cannot be skipped and the reason most people will skip it. A couple of weeks for the connector once the library exists.

## Gaps & uncertainty

- Whether any of this is worth building rests on Muse's reach, which is unknown and said to be unknown: the episode's own open questions are how many users it gets and how selective Meta's approval is, asking whether review will look like YC at 0.01% or like the App Store.
- No connector API documentation is quoted anywhere. The mechanism is explained in plain language -- a request, an availability answer, an approval, a booking -- so nothing here tells you how to actually write one. The starter brief is behind a redirect (startup-ideas-pod.link/muse-connector-prompt) and was not read.
- The submission form is described entirely second-hand, from an account published by Stacktree's founder, and the episode says to check the current form because the programme is new. Treat the details (API or existing MCP server, product information, usage examples, documentation, support) as reported rather than verified.
- Duffel's billion dollars is annual transaction value passing through the whole company, not Muse-attributable revenue -- the episode is explicit about this, and it is the kind of figure that gets requoted without the qualifier.
- "Muse is the number one app in the App Store" is stated as of recording (2026-09-24) and will age immediately.
- Playtomic is hedged in the transcript as "I think it's called Playtomic", so verify the incumbent before assuming the gap.
- The 40,000-downloads-a-day feature is a personal anecdote from earlier app launches, undated and unverifiable.
- Instacart's developer tools and Ticketmaster's connector are both named without links, so their current capabilities were not checked.
- Apple's figures (store opened 2008, a billion dollars paid to developers by June 2010) are repeated in the description and not sourced further.
- Pricing in every idea is hypothetical and labelled as such -- the $99-a-month, 100-customer arithmetic is offered as an example, not a benchmark.
- The host is Greg Isenberg, per the channel and description; the captions render the surname as "Eisenberg". Claude Code and Codex appear as "Cloud Code" and "Codeax" in places, and are corrected from the description.
- Transcript is machine-generated: prose is reliable, **proper nouns are not**. Names above come from the description where possible.

## Links from description

- [Muse Connector Prompt](https://startup-ideas-pod.link/muse-connector-prompt)
- [The #1 tool to find startup ideas/trends](https://www.ideabrowser.com)
- [https://latecheckout.agency/](https://latecheckout.agency/)
- [X/Twitter](https://twitter.com/gregisenberg)
- [Instagram](https://instagram.com/gregisenberg/)
- [LinkedIn](https://www.linkedin.com/in/gisenberg/)

## Applied

_Nothing applied yet._
