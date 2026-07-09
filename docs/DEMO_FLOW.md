# Demo flow — class presentation (~5 minutes)

Live demo of ObradorIQ at **https://obradoriq.onrender.com**.
Login: `owner@obradoriq.demo` / `bakery123`.

## Before class (10 minutes ahead)

1. **Wake the service** — open https://obradoriq.onrender.com. The free tier sleeps when
   idle; first load takes ~30–60 s. Keep the tab open.
2. **Sign in** and click through all four tabs once so every view is cached and loads
   instantly on stage.
3. **Backup plan** if Render is down: run locally and demo at http://localhost:8000 —
   ```bash
   cd backend && . .venv/bin/activate
   SEED_ON_START=true uvicorn app.main:app
   ```

## The script

### 1. Hook — the public simulator (30 s)

Open **https://obradoriq.onrender.com/simulate** (no login needed).

> "Small bakery chains throw away 10–20% of what they bake. This is what that costs —
> and what an AI planner recovers."

Run one simulation, point at the euros recovered, then switch to the signed-in app.

### 2. The hero number (30 s)

Sign in. The banner shows **"Waste avoided this week"** in euros.

> "Everything in this product is expressed in one unit the owner cares about: euros."

### 3. Ask ObradorIQ — the agent (90 s)

Open the **Ask ObradorIQ** tab. Two questions, in this order:

1. *"How much should I bake tomorrow?"* — the agent calls the forecasting and newsvendor
   models as **tools** and answers with grounded numbers.
2. *"We have a street festival on Saturday."* — the key moment: the agent turns context
   **no statistical model can know** into an explicit, attributed demand adjustment.

> "The one rule that makes this trustworthy: the math computes every number; the LLM only
> phrases them. If the model invents a figure, the answer is rejected and the grounded
> text is shown instead. And if the LLM is down, a deterministic router calls the same
> tools — the demo cannot break."

### 4. Daily plan + print sheet (60 s)

Open **Daily plan**: per-site, per-product quantities with predicted leftover.
Click **Print plan** — a clean production sheet for the bakers' wall.

> "The output isn't a dashboard for analysts — it's tomorrow's bake list."

### 5. Reallocation — the differentiator (60 s)

Open **Reallocation**: the same product chronically over-produced at one site and selling
out at another → shift *planned* production between sites (no goods are moved).

> "A solo bakery can't do this. A 2–4 site chain can — that's the moat."

### 6. Proof — the backtest (45 s)

Open **Weekly review** (total waste + True Margin), then close on the headline result:

> "Walk-forward backtest against true demand: **+€997 profit and 11% less waste** vs.
> what the bakery actually baked. Weather and holiday signals — real Madrid rain from
> Open-Meteo, real Madrid holidays — cut forecast error on those days from 19.8% to 17.4%."

### 7. Close (15 s)

> "Deterministic core, agentic language layer, owner always decides. Produce smarter.
> Sell better. Waste less."

## Likely questions

- **"Is the AI making the numbers up?"** No — the Trust Layer grounds every figure; the
  LLM only phrases (see `AGENT_FRAMEWORK.md` §5).
- **"What if demand is weird (festival, weather)?"** Weather/holiday elasticities are
  learned per product; unknown context comes in through the chat as an attributed
  adjustment.
- **"Why newsvendor instead of bake-to-forecast?"** Profit-optimal service level per
  product: a little more waste on high-margin items buys captured sell-outs — +€153 over
  the naive rule, growing with volatility.
- **"Is this real data?"** Synthetic chain, but driven by real historical Madrid
  precipitation and real Madrid holidays; 59 backend + 2 frontend tests pass.
