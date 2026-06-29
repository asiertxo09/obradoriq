# TECH_SPEC.md — ObradorIQ MVP Technical Starting Point

> Bridge document between the product/agent planning docs (`memory.md`, `agents.md`,
> `soul.md`, `tools.md`) and the first line of code. It defines **what we build, with
> what, how we keep it secure, and how we ship it.**

---

## 1. Scope of this document

This covers the **MVP only** — the slice defined in `memory.md → MVP scope`:

- CSV upload of sales history + basic product catalog.
- Daily waste tracking and a simple inventory availability check.
- AI-generated next-day production recommendations with plain-language explanations.
- A weekly summary and a recommendation log.

Explicitly out of scope for v1 (carried over from the PRD): automatic supplier
ordering, automatic POS writes, dynamic pricing, accounting integration,
multi-location optimization.

---

## 2. Architecture at a glance

This is the **implementation view** of the layered agent architecture in
`AGENT_FRAMEWORK.md`. Every agent is a Python **module behind one FastAPI service** (not
microservices) so the whole thing deploys as a single Render free-tier web service.

```
┌──────────────────────────┐   HTTPS/JSON   ┌─────────────────────────────────────────┐
│  Web dashboard           │ ─────────────▶ │  FastAPI service (one Render web service) │
│  (React build, served    │ ◀───────────── │                                           │
│   as static by FastAPI)  │                │  ┌─────────────────────────────────────┐  │
└──────────────────────────┘                │  │ Orchestrator (routes intent)        │  │
                                             │  ├─────────────────────────────────────┤  │
                                             │  │ Agents: Forecast · Planning ·       │  │
                                             │  │ Waste/Inventory · Margin · Reporting│  │
                                             │  ├─────────────────────────────────────┤  │
                                             │  │ Recommender core (pure Python)      │  │
                                             │  ├─────────────────────────────────────┤  │
                                             │  │ Trust Layer (mask·ground·score·log) │  │
                                             │  ├─────────────────────────────────────┤  │
                                             │  │ Data Hub (connectors + validation)  │  │
                                             │  └─────────────────────────────────────┘  │
                                             └───────┬─────────────────────┬─────────────┘
                                                     ▼                     ▼
                                            ┌──────────────┐      ┌────────────────┐
                                            │ PostgreSQL   │      │ Claude API     │
                                            │ (app data)   │      │ (phrasing only)│
                                            └──────────────┘      └────────────────┘
```

The **recommendation core** is plain Python (deterministic, testable, cheap). The
**LLM is only used to phrase the recommendation in the baker's voice** — it never
invents the numbers (the Trust Layer's grounding guardrail). This keeps cost low, output
explainable, and matches the `soul.md` rule "do not present forecasts as guarantees."
See `AGENT_FRAMEWORK.md` for the role/trust/guardrail/channel design.

---

## 3. Technology stack (decisions, not options)

| Layer | Choice | Why |
|-------|--------|-----|
| Backend API | **Python 3.12 + FastAPI** | Best fit for data/AI work; async; auto OpenAPI docs; fast to build. |
| Data / forecasting | **pandas + a simple statistical model** | Moving average + weekday seasonality is enough for v1. No ML training pipeline needed yet. |
| LLM layer | **Claude API — routed: Opus (`claude-opus-4-8`) for reasoning, Sonnet (`claude-sonnet-4-6`) for well-defined execution** | Opus = orchestration/reallocation/True-Margin judgment; Sonnet = phrasing/formatting/classification. See `AGENT_FRAMEWORK.md §6a`. (Haiku optional cost-lever for trivial formatting.) |
| Database | **PostgreSQL 16** | Relational data model is already sketched in `memory.md`; transactional integrity matters for sales/waste records. |
| ORM / migrations | **SQLAlchemy 2.x + Alembic** | Typed models, versioned schema changes. |
| Frontend | **React 18 + Vite + TypeScript**, built to static files and **served by FastAPI** | Standard SPA; serving the build from the same FastAPI app = one Render service, no second deploy, no CORS. |
| Styling | **Tailwind CSS** | Fast to build the clean B2B look the brand wants. |
| Auth | **JWT access tokens + bcrypt password hashing** | Stateless, simple, standard. |
| Background jobs | **APScheduler** (in-process for MVP) | Daily reminder + weekly summary. Move to a real queue later. |
| Packaging | **Docker + docker-compose** | One command to run the whole stack locally and in deploy. |
| Tests | **pytest** (backend), **Vitest** (frontend) | Forecast logic must be unit-tested — it's the product. |

> **Decided:** React frontend, built to static assets and served by the FastAPI app as
> one deployable. (Vanilla JS would also work, but React keeps the dashboard components
> clean and is the stronger submission; the single-service serving model removes the
> usual React deploy overhead.)

---

## 4. Proposed repository structure

```
ai_lab/
├── docs/                      # the existing planning docs move here
│   ├── memory.md  agents.md  soul.md  tools.md  ...
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + router wiring
│   │   ├── core/              # config, security, settings
│   │   ├── models/            # SQLAlchemy models (tables from §5)
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── api/               # route handlers
│   │   ├── recommender/       # forecast + production logic (pure Python)
│   │   └── llm/               # Claude client + prompt for explanations
│   ├── alembic/               # migrations
│   ├── tests/
│   └── pyproject.toml
├── frontend/                  # React + Vite app
├── data/                      # sample CSVs for demo/testing
├── docker-compose.yml
└── .env.example
```

---

## 5. Data model (MVP tables)

Derived from `memory.md → Database`, trimmed to what the MVP actually uses.

- **bakery** — `id, name, risk_preference, created_at` *(the chain)*
- **site** — `id, bakery_id, name, location` *(a shop in the chain — multi-site is core)*
- **user** — `id, bakery_id, email, password_hash, role, created_at`
- **product** — `id, bakery_id, name, category, price, ingredient_cost, batch_size`
- **sales_record** — `id, product_id, site_id, date, quantity_sold, revenue, sold_out (bool)`
- **waste_record** — `id, product_id, site_id, date, quantity_wasted`
- **inventory_record** — `id, product_id, site_id, date, quantity_available`
- **recommendation** — `id, product_id, site_id, target_date, forecast_qty, recommended_qty, confidence, predicted_waste_eur, reason, created_at`
- **reallocation** — `id, bakery_id, product_id, target_date, from_site_id, to_site_id, quantity, eur_waste_avoided, justification, created_at`
- **recommendation_decision** — `id, recommendation_id, decision (accepted|edited|rejected|deferred), final_qty, note, decided_at`

Every recommendation row must capture the fields listed in `agents.md → Log
requirements` (data used, forecast, reason, decision, actual results). The
`recommendation` + `recommendation_decision` pair is the audit log.

---

## 6. Core API endpoints (MVP)

```
POST   /auth/register                     create bakery (chain) + first user
POST   /auth/login                        -> JWT
GET    /sites                             list the chain's sites
POST   /sites                             add a site
GET    /products                          list catalog
POST   /products                          add product
POST   /uploads/sales                     per-site CSV upload -> validated sales_records
POST   /waste                             record per-site end-of-day waste
GET    /recommendations/{date}            per-site next-day plan (generates if absent)
GET    /recommendations/{date}/reallocation   plan-level cross-site reallocation suggestions
POST   /recommendations/{id}/decision     accept/edit/reject/defer
GET    /summary/weekly                    weekly review: waste, €-avoided, True-Margin
```

All routes except `/auth/*` require a valid JWT and are **scoped to the caller's
`bakery_id`** (and `site_id` where relevant) (see §7).

---

## 7. Technical requirements

### Functional (acceptance criteria for "done")
- A user can upload a **per-site** sales CSV and see it validated (bad rows rejected with a clear message, not silently dropped).
- Given ≥14 days of sales history, the system produces a next-day quantity **per product per site**, each with a **predicted-waste-€-avoided** figure.
- For a chain, the system surfaces ≥1 **plan-level reallocation** suggestion (shift planned production from a chronic-surplus site to a chronic-shortfall site) with euros avoided and a justification.
- Each recommendation shows: recommended qty, the data it used, € waste avoided, and a confidence flag.
- The user can accept / edit / reject / defer each recommendation, and the choice is logged.
- A weekly summary lists total waste, € avoided, and **waste-adjusted (True) margin** per product.

### Non-functional
- **Performance:** recommendation generation for a typical catalog (≤100 products) returns in < 3 s. The forecast is computed in Python; the LLM call (one batched call for all products' phrasing) is the only network latency.
- **Cost control:** one LLM call per recommendation run, not one per product. Cap output tokens. Forecast math never calls the LLM.
- **Explainability:** the numeric recommendation must be reproducible from the data without the LLM. The LLM only rephrases.
- **Data integrity:** sales/waste/inventory are append-only history; corrections create new rows, never destructive edits.
- **Testability:** `recommender/` is pure functions with unit tests covering normal, sparse-data, and unusual-spike cases.

### Production rule: newsvendor profit-optimization (v2)
The recommended quantity is the **profit-optimal newsvendor quantity** — the CR-quantile
of the demand distribution, where `CR = Cu/(Cu+Co)`, `Cu = price − unit_cost` (lost margin),
`Co = unit_cost` (leftover cost). So high-margin products keep an availability buffer and
low-margin products hug the forecast; `risk_preference` tilts CR. Demand ~ Normal(mean, σ)
with σ from same-weekday history; `q* = mean + z(CR)·σ`, batch-rounded. See
`backend/app/recommender/newsvendor.py`. The backtest compares this against the naive rule
below on **realised profit** using true demand. (`app.recommender.backtest`.)

### The forecast formula (v1 — kept as the naive baseline)
```
base_forecast   = weighted_avg(last 4 same-weekday sales)      # e.g. last 4 Tuesdays
trend_adjust    = recent 7-day average / prior 7-day average
forecast        = base_forecast * trend_adjust
recommended_qty = round_to_batch(forecast, batch_size)

# adjust for the owner's risk preference (from `memory.md → risk tolerance`)
if waste_rate(product) high:     recommended_qty -= one batch
if sold_out_recently(product):   recommended_qty += one batch (if risk_preference favors availability)

confidence = HIGH if >=8 same-weekday samples and low variance else LOW

predicted_waste_eur = max(0, current_plan - forecast) * (ingredient_cost or price_proxy)
```
Flag `LOW` confidence loudly and state what data is missing — this is the
`soul.md`/`agents.md` supervision rule, enforced in code.

### Plan-level reallocation (the differentiator, v1)
```
for each product, target_date, across the chain's sites:
  surplus_sites  = sites where forecast < current_plan      (predicted waste)
  shortfall_sites= sites where recently sold_out and forecast > current_plan
  for each (surplus, shortfall) pair, same product:
    qty = round_to_batch(min(surplus_excess, shortfall_gap), batch_size)
    if qty > 0 and both forecasts are HIGH confidence:
      suggest "shift {qty} of {product} planned production: {surplus} -> {shortfall}"
      eur_waste_avoided = qty * (ingredient_cost or price_proxy)
```
Plan-level only (shifts *planned quantities*, not physical goods) and **advisory** — the
Reallocation Agent (Opus) decides whether a suggestion is worth surfacing and justifies it;
the numbers above are deterministic. `reallocate_across_sites` is a pure function (Track B).

### Frontend screens (MVP)
- **Daily plan (per site):** recommended qty per product, headline **€ waste avoided**, confidence.
- **Reallocation view:** "shift N of X: Site 2 → Site 1", euros avoided, justification, approve/dismiss.
- **Weekly review:** total waste, € avoided, **waste-adjusted (True) margin** per product.
- **Waste tally:** fast end-of-day per-site input.
- **Settings:** sites, product catalog, batch sizes, risk preference.

---

## 8. Security requirements

The data here is sensitive: a small business's sales, costs, and margins. Treat it
as confidential per `tools.md → Tool-use rules`.

**Authentication & access**
- Passwords hashed with **bcrypt** (cost ≥ 12). Never stored or logged in plaintext.
- JWT access tokens, short-lived (e.g. 30 min) + refresh token. Signing secret from env, never committed.
- **Tenant isolation:** every query filters by the authenticated `bakery_id`. A user must never read another bakery's data. Add an automated test that asserts cross-tenant access returns 404/403.

**Transport & storage**
- HTTPS only in deployment (TLS terminated at the platform/proxy). HSTS on.
- Database not publicly exposed; reachable only from the API service.
- Secrets (`DATABASE_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`) injected via environment, listed in `.env.example` with dummy values, real `.env` git-ignored.

**Input handling**
- CSV uploads: enforce max file size, validate column schema and types, reject/quarantine malformed rows, cap row count. Never `eval` or trust cell contents.
- All request bodies validated by Pydantic schemas. Parameterized queries only (SQLAlchemy) — no string-built SQL.

**LLM-specific**
- Send the **minimum** data needed to phrase a recommendation (product name, numbers, reason) — not raw customer data, not full sales dumps.
- Treat any free-text that could reach a prompt as untrusted; don't let uploaded data carry instructions into the system prompt (prompt-injection hygiene).

**Operational**
- Rate-limit `/auth/login` and upload endpoints.
- Structured logs **without** secrets, passwords, or full tokens.
- Dependency scanning (`pip-audit`, `npm audit`) before submission/deploy.
- Document a basic data-deletion path (a bakery can request its data removed) — relevant for privacy expectations even at MVP.

---

## 9. Deployment

**Local / development**
- `docker-compose up` brings up Postgres + API (+ frontend dev server).
- `.env` from `.env.example`. `alembic upgrade head` runs migrations on start.
- Seed script loads `data/` sample bakery so the demo works immediately.

**Hosted MVP — Render free tier (decided)**
- A **`render.yaml` blueprint** defines two resources:
  - **Web service** (free): the FastAPI Docker image. It serves the API *and* the built
    React static files, so there is only one public URL and no CORS config.
  - **PostgreSQL** (free tier): `DATABASE_URL` injected into the web service automatically.
- Secrets (`JWT_SECRET`, `ANTHROPIC_API_KEY`) set as environment variables in the Render
  dashboard, not committed.
- **Build step:** `npm --prefix frontend run build` → output copied into the path FastAPI
  serves as static. **Release step:** `alembic upgrade head`, then the seed script (first
  deploy only) so the demo bakery is present.
- HTTPS is provided by Render automatically.
- **Free-tier caveat to plan around:** the web service sleeps after inactivity and the
  free Postgres database expires after ~30 days — fine for a class demo, but note it and
  keep the seed script handy to re-seed.

**CI (lightweight, optional but recommended for the grade)**
- GitHub Actions: on push → run `pytest`, `pip-audit`, frontend `vitest` + build. Block merge on failure.

**Promotion path:** local (compose) → staging (PaaS free tier) → demo. No
blue/green or autoscaling needed for the MVP; note it as future work.

---

## 10. Build order — contract-first parallel tracks

See the approved plan for full detail. **Phase 0** freezes shared contracts (multi-site
schema, Pydantic schemas, recommender function signatures, Trust Layer interface, the
2-site/10-week fixture), after which six tracks run in parallel, then integrate:

- **A** Data Hub + persistence (per-site ingestion, migrations, seed).
- **B** Recommender core + **reallocation** + backtest harness (pure Python — the IP).
- **C** Agent layer + Trust Layer + Opus/Sonnet model routing (LLM mocked in tests).
- **D** API + Auth + tenant isolation (cross-tenant test).
- **E** Frontend dashboard (served by FastAPI).
- **F** Deploy (`render.yaml`) + CI.

Tracks A + B alone (no LLM) are a defensible, demoable MVP. The integration phase runs the
E2E path on the seeded 2-site demo and records the backtest **headline metric** (€/waste
avoided) for the submission.

---

## 11. Decisions (resolved)

- **Frontend:** React (Vite + TS), built static and served by FastAPI. ✓
- **Hosting:** Render free tier, single web service + free Postgres via `render.yaml`. ✓
- **Submission:** a **running deployment** is required → CI + the Render blueprint and seed
  script are in-scope, not optional. ✓
- Agent/trust/guardrail/channel design: see `AGENT_FRAMEWORK.md`.
