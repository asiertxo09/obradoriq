# todo.md - ObradorIQ Submission Todo

## Current sprint goal

Build the **ObradorIQ Waste-Killer MVP** — a waste-reduction tool for 2–4 site bakery chains
with cross-site plan-level reallocation, deployed on Render. Contract-first parallel tracks.
Plan: approved build plan; concept: `docs/ideas/obradoriq-waste-killer.md`; specs:
`AGENT_FRAMEWORK.md` + `TECH_SPEC.md`.

## Completed

- [x] Define problem statement.
- [x] Define target user.
- [x] Define value proposition.
- [x] Draft first PRD.
- [x] Sketch initial architecture idea.
- [x] Generate `agents.md`.
- [x] Generate `memory.md`.
- [x] Generate `todo.md`.
- [x] Set up persistent `memory/` folder.
- [x] Set up `tasks/todo.md` for active sprint planning.

## Next work

- [ ] Validate assumptions with 2-3 bakery owners or operators.
- [ ] Create a sample product catalog and mock sales dataset.
- [ ] Design the first dashboard wireframe.
- [ ] Decide MVP data upload format.
- [ ] Define the first recommendation formula before adding advanced AI.
- [ ] Prepare a short demo flow for class presentation.

## MVP build order — contract-first parallel tracks

- [x] Phase 0: scaffold repo + freeze contracts (multi-site schema, Pydantic schemas,
      recommender signatures, Trust Layer interface, 2-site/10-week fixture).
- [x] Track A: Data Hub + persistence (per-site ingestion, seed).
- [x] Track B: Recommender core + reallocation + backtest harness (pure Python — the IP).
- [x] Track C: Agent layer + Trust Layer + Opus/Sonnet routing (LLM mocked in tests).
- [x] Track D: API + Auth + tenant isolation (cross-tenant test).
- [x] Track E: Frontend dashboard (served by FastAPI).
- [x] Track F: Deploy (Dockerfile + docker-compose + render.yaml) + CI.
- [x] Integration + E2E on seeded 2-site demo; headline metric recorded.

## Intraday "living plan" phase — contract-first parallel multi-agent build

Opus coordinated (froze contracts, integrated); Sonnet/Haiku sub-agents built the tracks.

- [x] Track 0 (Opus): freeze contracts — `IntradaySignal`/`SiteCapability` in `types.py`,
      `IntradaySignalOut` in `schemas.py`, stub signatures.
- [x] Track A (Sonnet): pure-Python intraday core — pace curve, end-of-day projection,
      sellout time, `intraday_signal` (bake_more/move/markdown/hold). `test_intraday.py`.
- [x] Track B (Sonnet): walk-forward intraday backtest + headline metric. `test_intraday_backtest.py`.
- [x] Track C (Haiku): `backfill_sale_events` in `seed()` so the demo has minute-level data
      out-of-the-box (deterministic). `test_intraday_seed.py`.
- [x] Track D (Sonnet): `intraday_status` service, `GET /api/intraday`, `get_intraday_status`
      tool, grounded `phrase_intraday`, offline keyword route. `test_intraday_api.py`.
- [x] Track E (Sonnet): Live tab + time scrubber (07:00→20:00) + `getIntraday` client.
- [x] Integration (Opus): full gate green; fixed Live demo-day anchor to a day with same-day
      events (06-28, not 06-29); tidied the seed identity-map SAWarning.

## Status

- **102 backend tests + Vitest frontend tests (3) pass; frontend build green.** Live uvicorn
  boots, seeds (now incl. minute-stamped `sale_event`s), serves the API + built React app,
  produces the Almond Croissant reallocation (Barrio→Centro), and the Live intraday plan.
- **Dawn-plan headline:** 46.4% waste avoided (€430, 408 units), forecast MAPE 13.8%.
- **Intraday headline:** an 11:00 check-in recovers ≈ **€1,154** across the chain vs. €0
  do-nothing baseline (`python -m app.recommender.intraday_backtest`). See `README.md`.

## Remaining (requires the user's accounts / permissions)

- [ ] Build/run the Docker image locally (needs your user in the `docker` group).
- [ ] Push to GitHub + deploy via Render Blueprint (`render.yaml`) for the running demo URL.
- [ ] Optional: set `LLM_OFFLINE=false` + `ANTHROPIC_API_KEY` for live baker-voice phrasing.
