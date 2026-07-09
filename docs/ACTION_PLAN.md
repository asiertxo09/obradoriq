# ObradorIQ — Updated Action Plan

**Date:** 2026-07-03
**Team (7):** Charles de Wouters, Asier Gomez, Ivan Delgado, Vicente Giner, Jon Uria,
Erik Conejo, Juan Carneiro

## Where we are

The MVP is built and pushed to GitHub (`github.com/asiertxo09/obradoriq`), CI green,
100+ backend tests and the frontend build all passing. The full feature set is in the
codebase: ingestion, forecasting, the newsvendor production planner, cross-site
reallocation, the Trust-Layer-grounded chat agent, the intraday "living plan," and a
rehearsed demo script (`docs/DEMO_FLOW.md`).

What's not yet done: the app isn't confirmed live on the internet, the agent still runs
on deterministic offline stubs instead of a live model, and we haven't rehearsed the
demo end-to-end on the deployed version.

## Three priorities

### 1. Deploy & verify the live demo — Owner: Asier Gomez

Push the Render Blueprint live (`render.yaml` is already configured), confirm
`/api/health` responds, sign in as the demo user, and click through all four tabs so
nothing breaks on stage.

**Why #1:** everything else — validation, rehearsal — depends on having a real URL to
point people at.

### 2. Wire up live LLM phrasing — Owner: Ivan Delgado, Vicente Giner, Jon Uria

Get a free Groq (or NVIDIA) API key, set `LLM_OFFLINE=false` + `LLM_PROVIDER=groq` +
`LLM_API_KEY` in the Render dashboard, and confirm the "Ask ObradorIQ" tab replies with
live, model-generated phrasing instead of the deterministic offline stubs — while
checking the Trust Layer still rejects any answer that alters a grounded number.

**Why #2:** right now the agent demo runs entirely on canned text; this is the
difference between showing a chatbot template and showing the actual AI feature working
live, and it's a config change, not new engineering.

### 3. Local build + final rehearsal — Owner: Charles de Wouters, Erik Conejo, Juan Carneiro

Build and run the Docker image locally, then do one full run-through of
`docs/DEMO_FLOW.md` end-to-end as if presenting live, fixing anything that breaks.

**Why #3:** catches integration issues the deployed Render free tier can hide (cold
starts, env var drift) before we're live in front of the class.

## Next deadline

**Proposed: Wednesday, 2026-07-08** as an internal checkpoint for all three
items above.


