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

## Status

- **33 backend tests + Vitest frontend tests pass.** Live uvicorn boots, seeds, serves the
  API + built React app, and produces the Almond Croissant reallocation (Barrio→Centro).
- **Headline metric:** 46.4% waste avoided (€430, 408 units), forecast MAPE 13.8% — see `README.md`.

## Remaining (requires the user's accounts / permissions)

- [ ] Build/run the Docker image locally (needs your user in the `docker` group).
- [ ] Push to GitHub + deploy via Render Blueprint (`render.yaml`) for the running demo URL.
- [ ] Optional: set `LLM_OFFLINE=false` + `ANTHROPIC_API_KEY` for live baker-voice phrasing.
