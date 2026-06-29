# MVP Technical Stack & Foundation

## Type

project

## Decision

The ObradorIQ MVP technical foundation is defined in `TECH_SPEC.md` (repo root). Key
locked decisions:

- **Backend:** Python 3.12 + FastAPI; SQLAlchemy 2.x + Alembic.
- **Database:** PostgreSQL 16.
- **Recommendation core:** pure Python (pandas; moving-average + weekday seasonality).
  Deterministic and unit-tested. The LLM never invents the numbers.
- **LLM layer:** Claude `claude-haiku-4-5-20251001`, used only to phrase recommendations
  in the baker's voice; one batched call per recommendation run (cost control).
- **Frontend:** React 18 + Vite + TypeScript + Tailwind, **built static and served by the FastAPI app** (one deployable, no CORS). DECIDED.
- **Auth:** JWT + bcrypt, with strict per-`bakery_id` tenant isolation.
- **Packaging/deploy:** Docker + docker-compose locally; **Render free tier** (single web service + free Postgres via `render.yaml`). A **running deployment is required** for class submission, so CI + blueprint + seed script are in-scope. DECIDED.
- **Architecture:** Salesforce-Agentforce-style layering — see `[[project_agent_framework]]` and root `AGENT_FRAMEWORK.md`. Agents are modules behind one FastAPI service, not microservices.

## Why

Bridges the planning docs to actual code, keeps the AI cheap and explainable (matches
`soul.md`: never present forecasts as guarantees), and treats bakery sales/cost data as
confidential.

## How to apply

When building, follow the ordered build path in `TECH_SPEC.md §10`. Steps 1–5 produce a
demoable MVP with zero LLM cost; the LLM explanation layer is step 6. See `TECH_SPEC.md`
for the data model, API surface, security requirements, and deployment plan.
