# AGENT_FRAMEWORK.md — ObradorIQ Agentic Architecture

> ObradorIQ's multi-agent architecture, modeled on the layered framework Salesforce
> uses for **Agentforce** (Data Cloud → Atlas reasoning engine → Einstein Trust Layer →
> agents/subagents → actions → guardrails → channels). This document defines **what the
> project is, what the agents do, and how trust, data, guardrails, roles, and channels
> fit together.** Implementation detail and the MVP cut live in `TECH_SPEC.md`.

---

## 1. What the project is (in one paragraph)

**ObradorIQ is a waste-reduction tool for small bakery chains (2–4 sites) that increases
profit directly.** Chain owners over- or under-bake at each site because they plan from gut
feel and leftover counts — and they can't see that one site bins a product while another
sells out. ObradorIQ connects each site's sales and waste data and produces **per-site daily
production recommendations framed in euros of waste avoided**, plus a **plan-level
reallocation** of production across sites (the cross-site move a solo bakery cannot make).
The owner always makes the final call. See `docs/ideas/obradoriq-waste-killer.md`.

## 2. The objective of the agent (its job-to-be-done)

> **Cut what the chain throws away each day — and turn that into recovered profit — by
> recommending how much each site should bake and how to reallocate planned production
> across sites, without adding work to the owner's morning, and never replacing their
> judgment.**

Frame: **waste reduction = direct profit increase.** Every number is "€X/day not binned."
Everything below serves that one objective safely and explainably.

---

## 3. The Salesforce framework, mapped to ObradorIQ

| Salesforce (Agentforce) | ObradorIQ equivalent | Purpose |
|---|---|---|
| **Data Cloud** (unify sources, grounding/RAG) | **Data Hub** (§4) | Connect and normalize POS, spreadsheets, inventory, weather, events. |
| **Atlas Reasoning Engine** | **Orchestrator Agent** (§6) | Interpret the baker's request, route to the right specialist agent, assemble the answer. |
| **Einstein Trust Layer** | **Trust Layer** (§5) | Sit between agents and the LLM: minimize/mask data, ground outputs, score confidence, log everything. |
| **Agents + Subagents/Topics** | **Specialist agents** (§6) | Each owns one job-to-be-done with its own scope + instructions. |
| **Actions** (Apex/Flow/API) | **Tools** (§7, from `tools.md`) | The concrete data reads and computations an agent may call. |
| **Guardrails** (managed + user-defined) | **Guardrails** (§8) | Keep agents on-topic, grounded, and within approval limits. |
| **Channels** (web, email, SMS, Slack) | **Channels** (§9) | Where each agent reaches the baker. |

---

## 4. Data Hub — the data-gathering layer

A single integration layer that pulls from each source, validates it, and normalizes it
into the unified data model (`TECH_SPEC.md §5`). Agents **never** read a raw source
directly — they read from the Hub. This mirrors how Data Cloud grounds Agentforce.

All data is **per-site** — every sales and waste record carries a `site_id`, because the
cross-site view is the whole product.

**Connectors (priority order):**
1. **CSV / spreadsheet upload (per site)** — POS exports, manual daily summaries. *(MVP)*
2. **Waste input (per site)** — fast end-of-day leftovers tally per product. *(MVP)*
3. **Inventory input** — finished-product counts. *(MVP-light)*
4. **Weather API** — daily forecast per site location. *(v2)*
5. **Local events calendar** — holidays, markets, festivals. *(v2)*
6. **Supplier cost feed** — ingredient prices for margin accuracy. *(v2)*
7. **Direct POS API** (Square, etc.) — replaces manual upload. *(later)*

**Hub responsibilities:** schema validation, type coercion, dedupe, rejecting/quarantining
bad rows with clear messages, and exposing a clean read API + **grounding context**
(the exact records a recommendation was based on) to the agents.

---

## 5. Trust Layer — the safety boundary

Sits between every agent and the Claude API. Adapted from the Einstein Trust Layer.
This is what makes it safe to point an LLM at a small business's private financials.

- **Data minimization & masking:** send the LLM only the numbers and product names needed
  to phrase a recommendation — never raw customer data, never full sales dumps. Mask/omit
  cost and customer fields by default. (`tools.md → Tool-use rules`.)
- **Grounding:** the numeric recommendation is computed by the deterministic recommender
  core (`TECH_SPEC.md §7`). **The LLM only rephrases grounded numbers — it never invents
  them.** This is our anti-hallucination guarantee.
- **Zero training / zero retention:** business data is not used to train external models;
  prompts carry the minimum and aren't persisted at the provider beyond the call.
- **Confidence scoring:** every recommendation carries HIGH/LOW confidence; LOW is flagged
  loudly with "what data is missing" (`soul.md`).
- **Output validation:** check the LLM's text didn't alter the numbers or add unsupported
  claims/promises before showing it to the baker.
- **Audit log:** every recommendation + the data used + the baker's decision is logged
  (`agents.md → Log requirements`). This *is* the trust + learning record.

---

## 6. Agent roles — each agent's job-to-be-done

One **Orchestrator** (Atlas-equivalent) routes work to specialist agents, each with a
narrow scope and its own instructions. This replaces the earlier single "ProductionIQ
Assistant" with a team — clearer, safer, and easier to test.

One **Orchestrator** (Atlas-equivalent) routes work to specialist agents, each with a
narrow scope and its own instructions. This replaces the earlier single "ProductionIQ
Assistant" with a team — clearer, safer, and easier to test. The **model** column applies
the Sonnet/Opus rule: **Opus for reasoning/judgment, Sonnet for well-defined execution**
(see §6a). The deterministic recommender core computes every number; agents reason and phrase.

| Agent | Model | Job-to-be-done (scope) | Produces |
|---|---|---|---|
| **Orchestrator** | **Opus** | Understand owner intent; route to specialists; assemble the final reply in `soul.md` voice. | Routed, voiced answer |
| **Demand Forecast Agent** | core + **Sonnet** | Predict per-site/product demand from history + weekday/seasonality. Numbers from core; Sonnet states confidence/context. | forecast + confidence |
| **Production Planning Agent** | core + **Sonnet** | Turn forecast into a per-site recommended quantity (batch size, waste history, risk pref); phrase as €-waste-avoided. | recommended qty + reason |
| **Reallocation Agent** | core + **Opus** | Cross-site judgment: spot chronic surplus-vs-shortfall for a SKU and decide whether a **plan-level** production reallocation is worth suggesting. | reallocation suggestion + justification |
| **Margin Agent** | core + **Opus** | Compute waste-adjusted ("True") margin; synthesize which products secretly lose money into the weekly profit story. | True-Margin insights |
| **Reporting Agent** | **Sonnet** | Compose the daily plan and weekly review; summarize accepted/edited/rejected recs. | daily/weekly summaries |

Each agent definition = **classification description + scope + instructions + allowed
tools** (the Agentforce "subagent" shape).

### 6a. Model routing (Sonnet/Opus rule)

| Task | Model | Why |
|---|---|---|
| Orchestrator routing; reallocation judgment; low-confidence diagnosis; True-Margin narrative | **Opus** (`claude-opus-4-8`) | Genuine reasoning/judgment. |
| Phrasing one grounded recommendation; CSV column-mapping; report formatting; scope classification | **Sonnet** (`claude-sonnet-4-6`) | Well-defined, schema-bound execution. |

LLMs never compute numbers — that is the Trust Layer grounding guarantee (§5).

---

## 7. Actions / tools

The concrete capabilities agents may call, already enumerated in `tools.md`: Sales data
reader, Inventory reader, Waste tracker, Demand forecaster, Production recommender, Margin
analyzer, Report generator (+ optional Weather, Events, Supplier cost, Notifications).
In this framework those are the agents' **actions** — every external read or computation
goes through one of them, and each is logged.

---

## 8. Guardrails (managed + user-defined)

**Managed (always on):**
- **Grounding guardrail** — numbers come from the recommender core, not the LLM (§5).
- **Scope guardrail** — agents answer bakery-operations questions only; off-topic requests are declined.
- **Confidence guardrail** — LOW-confidence recommendations are flagged and de-emphasized, never presented as certainty.
- **Tenant guardrail** — every action is scoped to the caller's `bakery_id` (and `site_id` within it); no cross-bakery data (`TECH_SPEC.md §8`).
- **Reallocation guardrail** — reallocation is **plan-level only** (shifts *planned production quantities* across sites, never physical goods) and **advisory** (owner approves); never executed automatically.

**User-defined / human-in-the-loop (from `agents.md` & `tools.md`):** the agent must get
explicit human approval before any of these — and the MVP simply **cannot** perform the
ones marked ✗write:
- Placing supplier orders. *(✗write in MVP)*
- Changing production plans for signature/high-volume products.
- Changing prices. *(✗write)*
- Editing POS/inventory/menu records. *(✗write)*
- Removing products from the menu. *(✗write)*
- Acting on a LOW-confidence forecast.

The MVP is **advisory only** — it recommends and logs; it never writes back to source
systems. This is the strongest possible guardrail for v1.

---

## 9. Channels — where each agent works

| Channel | Status | Used by | For |
|---|---|---|---|
| **Web dashboard** | MVP | All (via Orchestrator) | Daily plan, performance, weekly review, settings, decision capture. |
| **Email** | MVP-light | Reporting Agent | Daily "upload/confirm data" reminder; weekly summary. |
| **WhatsApp / SMS** | v2 | Reporting + Planning | Morning push of the day's plan; one-tap accept/edit reply. |
| **Slack** | later | Reporting | Team-facing summaries (larger shops). |

An agent is only reachable on the channels listed for it; the Orchestrator is the entry
point on the web dashboard.

---

## 10. End-to-end flow (a single day)

```
Owner uploads each site's sales + waste (Web / CSV)
        │
        ▼
   DATA HUB  ── validates, normalizes per-site, exposes grounding context
        │
        ▼
 ORCHESTRATOR (Opus) ── "plan tomorrow" ──┐
        │                                 ▼
        │            Demand Forecast Agent ─► per-site forecast + confidence
        │                                 │
        │            Production Planning Agent ─► qty per site (grounded; €-waste-avoided)
        │                                 │
        │            Reallocation Agent (Opus) ─► "shift 12 of X: Site 2 → Site 1"
        │                                 ▼
        └──────────────────► TRUST LAYER (mask • ground • score • validate • log)
                                   │
                                   ▼
                Claude API — Sonnet phrases the grounded plan in the owner's voice
                                   │
                                   ▼
   Per-site daily plan on Web: qty • €-waste-avoided • reallocation • confidence
                                   │
                          Owner: accept / edit / reject / defer  ──► logged → learning
```

---

## 11. MVP cut vs. full framework (be honest for the class)

This framework is the **target architecture**; the MVP on Render free tier implements a
pragmatic subset:

- **In the MVP:** multi-site Data Hub (per-site CSV/waste connectors), Trust Layer
  (masking, grounding, confidence, audit log), Orchestrator + Forecast + Planning +
  **Reallocation** + Reporting agents (modules, not separate services), all guardrails,
  Web + email channels, the **2-site** demo chain.
- **Deferred (named, not built):** weather/events/supplier connectors, full Margin depth
  beyond the weekly True-Margin view, WhatsApp/SMS/Slack channels, direct POS API,
  physical inter-site transfer logistics, >4 sites.

Implementing all agents as **modules behind one FastAPI service** (not microservices)
keeps it deployable on a single Render free-tier web service while preserving the layered
design.
