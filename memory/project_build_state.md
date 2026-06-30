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
- **Real weather + Madrid locations (phase 5):** two fictitious shops on real Madrid streets
  with lat/lon (Site gained latitude/longitude + ensure_columns). Fixture demand is driven by
  **real historical Madrid precipitation** fetched from **Open-Meteo archive** (free, keyless;
  OpenWeatherMap historical needs a paid key). `app/data_hub/weather.py` = archive (dataset) +
  forecast (live target, best-effort). Holidays = real Comunidad de Madrid (subdiv MD).
  Backtest on real weather: context-day MAPE 19.8%→17.4%, profit vs baseline +€997.
- **Activate on the EXISTING live demo (one-time):** set `RESEED_ON_START=true` on Render once
  (wipes+reseeds with Madrid coords + weather history), then back to `false`; `WEATHER_AUTOFETCH=true`
  makes the live plan fetch tomorrow's Madrid weather. Fresh deploys/local already have it.
- **NOTE:** generating the fixture (`python data/generate_fixture.py`) calls Open-Meteo (network);
  CI/tests use the committed CSVs and stay offline. One-pager: `docs/ONE_PAGER.md`.
- **JWT TTL** raised 30min → 7 days (`access_token_minutes`) to stop mid-demo "invalid/expired
  token" errors; frontend now clears the token + returns to login on any 401.
- **Full-year data generator (phase 6):** `app/generate_data.py` + new `SaleEvent` table
  (minute-resolution timestamps). `python -m app.generate_data --days 365` fills ALL tables:
  a year of daily sales/waste/inventory + ~130k minute-stamped sale_events (open hours
  07–20, weekday/intraday/weather/holiday patterns) + sample recs/decisions/reallocations/
  audit. NOT run on startup (too heavy for free tier; ~15MB). Removed the frontend paste-CSV box.
- **Admin endpoint:** `POST /api/admin/generate?days=120` (token via `X-Admin-Token` header vs
  `ADMIN_TOKEN` env; empty disables it) populates the live DB on demand. render.yaml auto-generates
  ADMIN_TOKEN. Default 120 days to stay within free-tier limits.
- **Collaborator:** Charles De Wouters added "simulate mode" (public `/api/simulate`, hero banner,
  print sheet, `/simulate` page). Merged cleanly via fast-forward; my changes coexist. Total 59 tests.
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
