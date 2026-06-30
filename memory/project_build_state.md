# Build State — Waste-Killer MVP (built)

## Type

project

## State

The ObradorIQ Waste-Killer MVP is built and passing tests. Layout under `/home/asier/ai_lab`:
`backend/` (FastAPI + recommender core + trust + agents + tests), `frontend/` (React+Vite+TS),
`data/` (synthetic 2-site/10-week fixture + generator), `Dockerfile`, `docker-compose.yml`,
`render.yaml`, `.github/workflows/ci.yml`, `README.md`.

- **Tests:** 42 backend (pytest) + 2 frontend (Vitest) pass. Backend venv at `backend/.venv`.
- **Smarter core (v2):** production rule is the **newsvendor** profit-optimizer
  (`recommender/newsvendor.py`) — CR = Cu/(Cu+Co); high-margin items get a buffer. Backtest
  now uses TRUE uncensored demand (fixture has a `demand` column) and compares profit across
  historical/naive/newsvendor.
- **Headline metric:** vs historical baseline +€1,311 profit & 6.8% less waste; vs naive rule
  +€157 (0.8%, grows with volatility); forecast MAPE 15.2%. Live demo deployed at
  https://obradoriq.onrender.com (NVIDIA Llama phrasing, free).
- **Conversational agent (phase 3):** "Ask ObradorIQ" chat — LLM calls the ML as TOOLS
  (`app/llm/tools.py`) via a provider-agnostic JSON tool-planning loop
  (`app/llm/orchestrator.py`; plain completions, NOT native function-calling — NVIDIA 403s
  on tools). Translates stated context ("festival") → attributed `demand_adjustment_pct`.
  `/chat` + `/ingest/text` endpoints; never breaks (online failure → deterministic offline
  router). Verified live doing real tool-planning. 50 backend + 2 frontend tests.
- **LLM provider gotcha:** NVIDIA free tier gates native tool-calling (403) AND the shared
  key was later revoked. Use plain-completions only (we do) and Groq if native tools needed.
- **Weather + holidays signal (phase 4):** forecast learns per-product rain & holiday
  elasticities from history (`recommender/signals.py`) and applies them to the target day.
  Fixture has precip_mm/is_holiday + true `demand`; backtest shows context-day MAPE 21.5%→19.3%.
  Live wiring: SalesRecord gained precip_mm/is_holiday (+ idempotent `_ensure_columns` ALTER
  for the existing Postgres), ingest parses them, holidays auto-detected via `holidays` lib
  (ES/CT), `rainy` passed by owner/agent. 52 backend tests pass.
- **Activate weather on the EXISTING live demo:** its seeded rows predate the columns, so set
  `RESEED_ON_START=true` on Render once (wipes+reseeds the demo with weather), then set back
  to false. Fresh deploys/local already have it. One-pager: `docs/ONE_PAGER.md`.
- **Demo login:** owner@obradoriq.demo / bakery123. Run: `SEED_ON_START=true uvicorn app.main:app`.
- **Key design:** recommender core is pure Python (computes all numbers); LLM only phrases
  (Trust Layer grounding). Model routing: Opus reasoning / Sonnet execution. Auth is JWT+bcrypt
  with per-bakery tenant isolation. Reallocation is plan-level + advisory.

## Pending (needs the user's accounts/permissions)

- Docker build/run needs the user in the `docker` group (couldn't build in the WSL session).
- Render deploy = push to GitHub + New→Blueprint on `render.yaml` (user action).
- Live LLM phrasing = set `LLM_OFFLINE=false` + `ANTHROPIC_API_KEY`.

## Gotchas fixed during build

- Dropped `passlib` (broke on bcrypt 5.0) → use `bcrypt` directly with 72-byte truncation.
- `EmailStr` needs `email-validator` (added via `pydantic[email]`).
- Reallocation classified a site as both surplus AND shortfall → contradictory A→B/B→A pairs;
  fixed with mutually-exclusive `elif` classification + regression test.

See `[[project_waste_killer_direction]]`, `[[project_agent_framework]]`, `[[project_tech_stack]]`.
