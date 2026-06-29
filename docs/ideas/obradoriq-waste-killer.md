# ObradorIQ — Waste-Killer for Small Bakery Chains

## Problem Statement
**How might we** help a 2–4 site bakery chain cut what it throws away each day — by telling
each shop how much to bake *and* how to reallocate planned production across sites — without
adding work to anyone's morning?

## Recommended Direction
A daily, per-site production recommendation engine whose unit of value is **avoided waste in
euros**, framed explicitly as **profit recovered**. Every output is loss prevented:
*"Cut Site 2's morning croissant batch by 12 (~€18/day) and shift 8 of that planned batch to
Site 1, which sold out by 11am twice this week."*

The wedge is **waste**; the framing is **waste reduction = direct profit increase**; the
differentiator is **cross-site plan-level reallocation** — reallocating *planned production
quantities* across sites (no physical goods moved, no logistics). A solo bakery physically
cannot do this and a generic forecasting SaaS doesn't model it. The adoption strategy is
**near-zero input**: sales flow from POS exports; the only human action is a fast end-of-day
waste tally per site. The weekly view escalates to **waste-adjusted ("True") margin** so the
owner sees which products are secretly unprofitable once waste is counted.

This keeps the agentic architecture (`AGENT_FRAMEWORK.md`) fully relevant — Data Hub unifies
the sites, Forecast + Planning agents run per site, a reallocation step reasons across sites
(Opus), the Trust Layer grounds every euro figure, Reporting tells the profit story (Sonnet)
— but pointed at one sharp outcome instead of "everything."

## Key Assumptions to Validate
- [ ] A simple weekday+trend forecast beats the owner's gut by enough to dent waste — *test: backtest on the synthetic multi-site dataset; report waste avoided + forecast error.*
- [ ] A chain owner will actually *reduce* a batch on the system's say-so — *test: show 3 owners a mock recommendation; would they act?*
- [ ] Per-site sales data can be obtained without daily manual upload — *test: check Square/typical POS export format (deferred; seed CSV for v1).*
- [ ] Plan-level reallocation reads as useful, not confusing, to the owner — *test: qualitative review of the reallocation view.*

## MVP Scope (for the class demo)
**In:** multi-site sample dataset (2 sites); per-site next-day production recommendation framed
in €-waste-avoided; one **plan-level reallocation suggestion** between sites; fast waste-tally
input; weekly waste + waste-adjusted-margin (True-Margin) report; the deployed dashboard on
Render.
**Out:** real POS integration (use CSV/seed), physical transfer logistics, >4 sites,
ingredient-level inventory, pricing/menu changes, native mobile app.

## Not Doing (and why)
- **Solo-baker market** — kills the reallocation differentiator; the chain is the whole point.
- **Full inventory/ingredient tracking** — huge data burden, not the wound. Waste of *finished product* is.
- **Demand-maximization / "sell more"** — dilutes the message. One wound: waste → profit.
- **Physical inter-site transfer logistics** — chose plan-level reallocation; no van scheduling.
- **Real-time POS integration in v1** — adoption-critical eventually, distraction for a graded demo; seed data tells the story.
- **5 separate agent microservices** — modules behind one FastAPI service (Render free-tier reality).

## Open Questions
- Owner-facing emotional frame: lead with **waste** (hook) and escalate to **profit** (weekly review)? (Current decision: yes — waste daily, profit weekly.)
- Is the reallocation suggestion automatic or owner-initiated in the demo? (Current decision: **advisory** — surfaced, owner approves.)
