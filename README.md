# ObradorIQ — Waste-Killer for Small Bakery Chains

> The AI that turns your bakery data into smarter daily decisions.
> **Produce smarter. Sell better. Waste less.**

### 🔗 Live demo: **https://obradoriq.onrender.com**
Sign in with **`owner@obradoriq.demo`** / **`bakery123`**.
*(Free tier sleeps when idle — the first load may take ~30–60s to wake.)*

ObradorIQ is a **waste-reduction tool for small bakery chains (2–4 sites)** that increases
profit directly. It gives each shop a daily, per-site production recommendation framed in
**euros of waste avoided**, and — the differentiator — suggests **plan-level reallocation**
of planned production across sites (something a solo bakery cannot do). The owner always
makes the final call.

- **One-pager (what/why/how/results):** [`docs/ONE_PAGER.md`](docs/ONE_PAGER.md)
- **Concept & idea one-pager:** [`docs/ideas/obradoriq-waste-killer.md`](docs/ideas/obradoriq-waste-killer.md)
- **Agent architecture (Salesforce-Agentforce-style):** [`AGENT_FRAMEWORK.md`](AGENT_FRAMEWORK.md)
- **Technical spec:** [`TECH_SPEC.md`](TECH_SPEC.md)

## How it works

```
1. INGEST   Each site uploads daily sales + end-of-day waste (CSV / POS export), tagged
            with the day's real weather (Open-Meteo) and holiday flag (Madrid calendar).
                         │
2. FORECAST Per (product, site): recency-weighted same-weekday demand + trend,
            with a HIGH/LOW confidence flag.            ← deterministic core
                         │
3. PLAN     Forecast → batch-rounded production, adjusted for waste history and the
            owner's risk preference, expressed as € of waste avoided.
                         │
4. REALLOCATE  Across sites, spot a chronic over-producer vs. a chronic sell-out for
            the same product and suggest shifting *planned* production (no goods moved).
                         │
5. PHRASE   The Trust Layer masks sensitive fields and sends only grounded numbers to
            the LLM (Opus/Sonnet tier, or free Groq/NVIDIA Llama) to write it in the
            owner's voice. If the model alters or invents a number, the output is
            rejected and the grounded text is used instead.
                         │
6. DECIDE   Owner accepts / edits / rejects each suggestion — every decision is logged.
            Weekly review shows total waste and waste-adjusted ("True") margin.
```

**The one rule that makes it trustworthy:** the recommender core computes every number;
the LLM only *phrases* them. A recommendation can never display a figure the math didn't
produce. See [`AGENT_FRAMEWORK.md`](AGENT_FRAMEWORK.md) §5 (Trust Layer).

## Ask ObradorIQ — the conversational agent

The dashboard has an **Ask ObradorIQ** tab: a chat where the agent answers plain-language
questions by **calling the ML as tools** (forecast, newsvendor, reallocation, weekly,
production-sheet draft) and replying with grounded numbers. This is where the LLM earns its
keep — doing what statistics can't:

- **Conversation:** *"How much should I bake tomorrow? Where am I wasting the most?"*
- **Context the model can't know:** *"We have a street festival Saturday"* → the agent sets an
  explicit, attributed `demand_adjustment_pct` and says so.
- **Messy input:** paste any sales/waste rows and it imports them.
- **Action drafts:** a chain production sheet + estimated ingredient spend to approve.

It's **provider-agnostic** (a JSON tool-planning loop over plain completions, so it doesn't
need gated native function-calling) and **degrades gracefully**: if the LLM is offline or a
key fails, a deterministic router still calls the same tools and returns grounded data. The
ML does the numbers; the agent does the language, the context-reasoning, and the doing.

## Headline result (backtest on the demo chain)

Walk-forward backtest against **true (uncensored) demand** — the model trains only on
observed sales, the evaluation knows real demand, so an availability buffer's captured
sales are counted, not just its extra waste. Three strategies compared on realised
**profit** (the unit of value), not waste alone:

| Strategy | Waste (units) | Profit |
|---|---|---|
| Historical baseline (what the bakery baked) | 933 | €17,894 |
| Naive bake-to-forecast | 700 | €18,738 |
| **Newsvendor (ours)** | 832 | **€18,891** |

> **vs. the bakery's baseline: +€997 profit and 11% less waste.**
> vs. a naive forecast rule: +€153 (0.8%) — grows with demand volatility and margin spread.

The newsvendor model sets each product's quantity at its profit-optimal service level
(margin vs. leftover cost): it trades a little extra waste for captured high-demand sales,
netting higher profit — the textbook-correct answer to "how many to bake."

**Weather + holiday signals** (learned elasticities, the edge ML/gut lack): forecast error on
the rainy/holiday days where the signal acts drops **19.8% → 17.4%** (all-days MAPE 15.1% →
14.7%). The model learns each product's rain/holiday sensitivity from its own history and
applies it to the target day. **Weather is real:** the two demo shops sit on real Madrid
streets and the dataset is driven by **actual historical Madrid precipitation** from
Open-Meteo (free, keyless); holidays are real Comunidad de Madrid public holidays.

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

### Generate a full year of data (all tables, minute-stamped sales)
```bash
cd backend
python -m app.generate_data --days 365              # real Madrid weather (Open-Meteo)
python -m app.generate_data --days 365 --no-weather # offline
```
Populates every table — a year of daily sales/waste/inventory plus **~130k transaction-level
`sale_event` rows timestamped to the minute** during opening hours (07:00–20:00), and sample
recommendations/decisions/reallocations/audit logs. (~15 MB; run deliberately against your
`DATABASE_URL` — it is **not** run on startup.)

**Populate the live DB (Render) via the admin endpoint** — token-guarded, default 120 days
(kept modest for the free-tier DB):
```bash
# ADMIN_TOKEN is auto-generated by render.yaml; read it in the Render dashboard.
curl -X POST "https://obradoriq.onrender.com/api/admin/generate?days=120" \
     -H "X-Admin-Token: <ADMIN_TOKEN>"
```
Returns the per-table row counts. Omit/empty `ADMIN_TOKEN` to disable the endpoint entirely.

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
4. For live LLM phrasing with a **free** provider, set `LLM_OFFLINE=false`,
   `LLM_PROVIDER=groq` (or `nvidia`), and `LLM_API_KEY` in the dashboard (see below).

> Free-tier notes: the web service sleeps when idle and the free Postgres expires after
> ~30 days. `SEED_ON_START` re-seeds automatically on a fresh database.

### Live AI phrasing — free providers (Groq / NVIDIA)

The numbers always come from the recommender core; the LLM only phrases them, so any
provider works. The Opus/Sonnet routing is preserved as a reasoning-vs-execution tier:

| `LLM_PROVIDER` | Reasoning model | Execution model | Free key |
|---|---|---|---|
| `groq` | `llama-3.3-70b-versatile` | `llama-3.1-8b-instant` | https://console.groq.com/keys |
| `nvidia` | `meta/llama-3.3-70b-instruct` | `meta/llama-3.1-8b-instruct` | https://build.nvidia.com |
| `anthropic` | `claude-opus-4-8` | `claude-sonnet-4-6` | console.anthropic.com |

Set `LLM_OFFLINE=false`, `LLM_PROVIDER`, and `LLM_API_KEY`. Optionally override models with
`MODEL_REASONING` / `MODEL_EXECUTION`. (`openai_compatible` + `LLM_BASE_URL` works for any
other OpenAI-style endpoint.)

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
