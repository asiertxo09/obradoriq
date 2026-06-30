# ObradorIQ — One-Pager

**Live:** https://obradoriq.onrender.com · demo login `owner@obradoriq.demo` / `bakery123`
**Code:** https://github.com/asiertxo09/obradoriq · 52 backend + 2 frontend tests, CI green

---

## WHAT

An AI **operations partner for small bakery chains (2–4 sites)** that cuts what they throw
away — and turns it into recovered profit. Each morning it tells every shop **how much of
each product to bake**, suggests **shifting planned production between shops**, and answers
plain-language questions in an **Ask ObradorIQ** chat. The owner always decides.

## WHY

A small chain over-bakes at one shop while another sells out, because production is planned
from gut feel and yesterday's leftovers. Waste is money already spent; stockouts are margin
left on the floor — and nobody can see the cross-site imbalance. Existing tools are either
enterprise ERP (too heavy) or generic forecasting (single-site, no chain logic, no interface
a baker will actually use).

## HOW

A layered agent architecture (modeled on Salesforce Agentforce), all behind one service:

1. **Data Hub** — validates and normalizes each site's sales + waste (CSV/paste), with the
   day's weather and holiday flag.
2. **Recommender core (ML/OR, pure Python, grounded)** — the numbers:
   - **Forecast:** recency-weighted same-weekday demand + trend, with **learned weather &
     holiday elasticities** applied to the target day.
   - **Newsvendor optimizer:** bakes each product at its **profit-optimal service level**
     (`CR = Cu/(Cu+Co)`) — high-margin items keep a buffer, low-margin hug the forecast.
   - **Plan-level reallocation:** detects a chronic over-producer vs. a sell-out site and
     shifts *planned* production between them (advisory; no goods moved).
3. **Trust Layer** — masks sensitive data, **grounds every number** (the LLM may only phrase
   figures the math produced; ungrounded output is rejected), scores confidence, audit-logs.
4. **Agent (LLM)** — does what ML can't: conversation, reasoning over context the model can't
   know ("festival Saturday" → an explicit, attributed demand bump), ingesting messy data,
   and drafting actions. It **calls the ML as tools**; provider-agnostic (NVIDIA/Groq/
   Anthropic) and degrades to a deterministic router if the LLM is unavailable.

**Stack:** FastAPI + PostgreSQL + React (served by FastAPI), deployed free on Render; CI on
GitHub Actions. The LLM is cheap and optional; the ML is the source of truth.

## RESULTS (walk-forward backtest vs. true demand, demo chain)

Two fictitious shops on real Madrid streets (Gran Vía; Calle de Bravo Murillo); demand is
driven by **real historical Madrid weather** (Open-Meteo) and real Madrid holidays.

| Strategy | Waste | Profit |
|---|---|---|
| Historical baseline | 933 units | €17,894 |
| Naive bake-to-forecast | 700 units | €18,738 |
| **Newsvendor (ObradorIQ)** | 832 units | **€18,891** |

- **vs. the bakery's own baseline: +€997 profit, −11% waste.**
- vs. a naive forecast rule: **+€153 (0.8%)**, growing with volatility and margin spread.
- **Weather/holiday signal:** forecast error on rainy/holiday days **19.8% → 17.4%**.
- **Cross-site reallocation:** correctly flags the over-baked product at one shop and the
  sell-out at the other, framed in euros recovered.

## HONEST LIMITS / NEXT

Sales/demand are synthetic (no real bakery data yet) but grounded in **real Madrid weather
and holidays**. The newsvendor's edge over a *good* naive forecaster is small on clean data —
the real upside is vs. how chains actually plan today. Next: live POS ingestion, a learning
loop that tunes each product from logged decisions, and richer weather features.
