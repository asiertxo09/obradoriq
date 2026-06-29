# ObradorIQ — Waste-Killer for Small Bakery Chains

> The AI that turns your bakery data into smarter daily decisions.
> **Produce smarter. Sell better. Waste less.**

ObradorIQ is a **waste-reduction tool for small bakery chains (2–4 sites)** that increases
profit directly. It gives each shop a daily, per-site production recommendation framed in
**euros of waste avoided**, and — the differentiator — suggests **plan-level reallocation**
of planned production across sites (something a solo bakery cannot do). The owner always
makes the final call.

- **Concept & one-pager:** [`docs/ideas/obradoriq-waste-killer.md`](docs/ideas/obradoriq-waste-killer.md)
- **Agent architecture (Salesforce-Agentforce-style):** [`AGENT_FRAMEWORK.md`](AGENT_FRAMEWORK.md)
- **Technical spec:** [`TECH_SPEC.md`](TECH_SPEC.md)

## Headline result (backtest on the demo chain)

Walk-forward backtest of the forecast vs. the bakery's own historical baseline:

| Metric | Value |
|---|---|
| Forecast error (MAPE) | **13.8%** |
| Baseline waste | 879 units (€704) |
| Model waste | 471 units (€274) |
| **Waste avoided** | **408 units · €430 · 46.4%** |

Reproduce: `cd backend && python -m app.recommender.backtest`

## Architecture (one FastAPI service)

```
React dashboard (built static, served by FastAPI)
        │  /api
FastAPI ├─ Orchestrator (Opus) → Forecast · Planning · Reallocation (Opus) · Reporting (Sonnet)
        ├─ Recommender core (pure Python — computes every number)
        ├─ Trust Layer (mask · ground · score · audit)
        └─ Data Hub (per-site CSV ingestion)
        ▼
PostgreSQL                         Claude API (phrasing only; grounded)
```

**Model routing (Sonnet/Opus rule):** Opus for reasoning (orchestration, reallocation,
True-Margin), Sonnet for well-defined execution (phrasing, formatting). The LLM never
computes numbers — that's the Trust Layer grounding guarantee.

## Run it locally

### Backend + tests (no Docker)
```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q                 # 33 tests
python -m app.seed                  # seed the demo chain into ./obradoriq.db
SEED_ON_START=true uvicorn app.main:app --reload   # http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev        # dev server, proxies /api to :8000
npm run build      # production build -> frontend/dist (served by FastAPI)
```

### Whole stack with Docker
```bash
docker compose up --build          # http://localhost:8000  (API + UI + Postgres)
```
> Requires your user to have Docker access (be in the `docker` group).

**Demo login:** `owner@obradoriq.demo` / `bakery123`

## Deploy to Render (free tier)

1. Push this repo to GitHub.
2. In Render: **New → Blueprint**, point at the repo. [`render.yaml`](render.yaml) provisions
   one free web service (API + UI) and a free PostgreSQL database.
3. `JWT_SECRET` is auto-generated; `SEED_ON_START=true` loads the demo chain on first boot.
4. For live LLM phrasing, set `LLM_OFFLINE=false` and add `ANTHROPIC_API_KEY` in the dashboard.

> Free-tier notes: the web service sleeps when idle and the free Postgres expires after
> ~30 days. `SEED_ON_START` re-seeds automatically on a fresh database.

## Project layout
```
backend/   FastAPI app, recommender core, trust layer, agents, tests
frontend/  React + Vite + TS dashboard
data/      synthetic 2-site, 10-week fixture + generator
docs/      idea one-pager
```

## Tests
- **Backend (33):** recommender (normal/sparse/spike), reallocation invariants + no
  contradictory pairs, backtest reproducibility, Trust Layer grounding + masking, model
  routing, auth + **cross-tenant isolation**, CSV validation, and an end-to-end demo flow.
- **Frontend:** Vitest unit tests + production build.
- **CI:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs all of it on push.
