# Agentic Architecture (Salesforce-Agentforce-inspired)

## Type

project

## Decision

ObradorIQ's architecture is modeled on Salesforce Agentforce's layered framework. Full
detail in root `AGENT_FRAMEWORK.md`. The layers:

- **Data Hub** (= Data Cloud): connectors to POS/CSV, inventory, waste (MVP) + weather,
  events, supplier costs (v2). Validates and normalizes into the unified data model;
  agents read only from the Hub, never raw sources.
- **Orchestrator** (= Atlas reasoning engine): interprets intent, routes to specialists,
  assembles the voiced reply.
- **Trust Layer** (= Einstein Trust Layer): data minimization/masking, grounding (LLM only
  rephrases deterministic numbers — never invents them), confidence scoring, output
  validation, audit logging.
- **Specialist agents** (= subagents/topics), each a job-to-be-done: Demand Forecast,
  Production Planning, Waste & Inventory, Margin, Reporting.
- **Actions/tools** (= Apex/Flows): the 7 tools from `tools.md`.
- **Guardrails**: managed (grounding, scope, confidence, tenant isolation) + user-defined
  human-in-the-loop approvals. MVP is **advisory only** — never writes to source systems.
- **Channels**: Web dashboard + email (MVP); WhatsApp/SMS (v2); Slack (later).

## Why

Gives the class submission a credible, industry-aligned architecture while keeping the MVP
honest: agents are **modules behind one FastAPI service**, not microservices, so it stays
deployable on Render free tier. See `[[project_tech_stack]]`.

## How to apply

Treat `AGENT_FRAMEWORK.md` as the target architecture and `TECH_SPEC.md §11` as the MVP
cut. The agent objective to optimize for: reduce end-of-day waste without increasing
stockouts, faster planning, never replace the baker's judgment.
