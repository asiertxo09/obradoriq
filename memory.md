# memory.md - ObradorIQ Project Memory

## Refined direction (current — supersedes the generic framing below)

After idea-refinement, ObradorIQ is sharpened to a specific wedge:

- **What:** a **waste-reduction tool for small bakery chains (2–4 sites)** that increases
  profit directly. Frame: *waste reduction = direct profit increase*; every number is
  "€X/day not binned."
- **Differentiator:** cross-site **plan-level reallocation** — reallocating *planned
  production quantities* across sites (no physical goods, advisory). A solo bakery can't do
  this; generic forecasting SaaS doesn't model it.
- **First user:** owner-operator of a 2–4 site chain. **Goal of this effort:** an excellent,
  deployed class submission (React on Render free tier).
- **Models:** Opus (`claude-opus-4-8`) for reasoning (orchestration, reallocation,
  True-Margin); Sonnet (`claude-sonnet-4-6`) for well-defined execution (phrasing,
  formatting, classification). Deterministic core computes all numbers.
- **Canonical docs:** `docs/ideas/obradoriq-waste-killer.md` (one-pager), `AGENT_FRAMEWORK.md`,
  `TECH_SPEC.md`, and the approved build plan.

The PRD/architecture below remains valid background, read through the waste-killer lens.

## Problem statement

Independent bakery owners often decide what and how much to produce using intuition, sales tickets, spreadsheets, and leftover counts. This makes daily production stressful and imprecise, causing avoidable waste, stockouts of popular products, and limited visibility into which products are actually profitable.

## Target user

The target user is an independent bakery owner, pastry shop owner, or bakery operations manager. They work in a small team, make production decisions early in the day or the day before, and need to balance freshness, product availability, ingredient limits, labor capacity, and waste.

## Value proposition

ObradorIQ turns everyday bakery data into simple production, inventory, waste, and profitability recommendations so bakery owners can produce smarter, sell better, and waste less without losing their artisan identity.

## First PRD

### Product purpose

ObradorIQ is an AI-powered planning assistant for bakeries and pastry shops. Its purpose is to help owners make better daily decisions about production quantities, inventory use, waste reduction, and product profitability.

### Target user

Primary user:

- Independent bakery owner.
- Pastry shop owner.
- Bakery operations manager.

User context:

- Makes daily production decisions under time pressure.
- Uses POS data, spreadsheets, inventory checks, and experience.
- Wants better planning without complex enterprise software.
- Needs recommendations that are easy to understand and easy to override.

### User stories

- As a bakery owner, I want to know how much of each product to produce tomorrow so I can reduce leftovers without losing sales.
- As a bakery owner, I want to see which products are frequently wasted so I can adjust production.
- As an operations manager, I want to forecast demand by day and product so I can plan labor and ingredients.
- As a bakery owner, I want to understand which products have strong margins so I can focus production on profitable items.
- As a user, I want recommendations explained in simple language so I can trust the system and still make the final decision.

### Core features

- Daily production recommendation by product.
- Sales history import from POS exports or spreadsheets.
- Inventory and ingredient availability review.
- Waste and leftovers tracking.
- Demand forecast by product and day.
- Product margin visibility.
- Daily planning summary.
- Weekly performance review.

### AI functionality

- Forecast expected product demand using sales history, weekday patterns, seasonality, weather, local events, holidays, and special orders.
- Recommend production quantities by balancing demand, inventory, batch size, waste history, and stockout risk.
- Detect waste patterns and repeated stockouts.
- Explain recommendations in plain business language.
- Learn from accepted, edited, or rejected recommendations over time.
- Flag low-confidence recommendations and ask for missing information.

### Data inputs

Required inputs:

- Product catalog.
- Product prices.
- Historical sales by product and date.
- Current inventory or ingredient availability.
- Waste and leftover records.
- Production batch sizes.

Optional inputs:

- Weather.
- Holidays.
- Local events.
- Supplier costs.
- Labor estimates.
- Special orders.
- Owner risk preferences.

### Success metric

Primary success metric:

- Reduce end-of-day waste without increasing stockouts.

Supporting metrics:

- Fewer stockouts of popular products.
- Faster daily production planning.
- Higher forecast accuracy by product.
- Improved product margin visibility.
- More accepted recommendations over time.

### MVP scope

The MVP should include:

- Manual or CSV upload of sales history.
- Basic product catalog.
- Daily waste tracking.
- Simple inventory availability check.
- AI-generated production recommendations for the next day.
- Plain-language explanation for each recommendation.
- Weekly summary showing waste, sellouts, and top opportunities.

Out of scope for MVP:

- Automatic supplier ordering.
- Automatic POS updates.
- Dynamic pricing.
- Full accounting integration.
- Multi-location optimization.
- Fully automated menu changes.

## Initial architecture idea

### Frontend

A simple web dashboard for the bakery owner.

Main screens:

- Daily plan: recommended quantities by product.
- Product performance: sales, waste, stockouts, and margin indicators.
- Inventory check: key ingredients and product availability.
- Weekly review: trends, accepted recommendations, and improvement areas.
- Settings: product catalog, batch sizes, opening days, and risk preference.

### Backend

An API service that handles:

- User accounts and bakery profiles.
- File uploads and data validation.
- Product, sales, waste, inventory, and recommendation endpoints.
- Recommendation logging.
- Scheduled weekly summaries.

### Database

Core tables:

- Users.
- Bakeries.
- Products.
- Sales records.
- Inventory records.
- Waste records.
- Forecasts.
- Recommendations.
- Recommendation decisions.
- Weekly summaries.

### AI layer

The AI layer combines forecasting, recommendation logic, and natural-language explanation.

It should:

- Prepare demand forecasts from structured bakery data.
- Generate production recommendations.
- Produce simple explanations.
- Assign confidence levels.
- Ask clarifying questions when data is incomplete.
- Store recommendation outcomes for learning.

### Automation

Initial automations:

- Daily reminder to upload or confirm sales and waste data.
- Daily recommendation generation for tomorrow's production.
- Weekly performance summary.
- Low-confidence alert when data is missing or unusual demand is detected.

Later automations:

- Supplier order draft.
- Weather and local event adjustment.
- Multi-week trend detection.
- Suggested product catalog changes for human approval.

## Brand memory

Company name: **ObradorIQ**

Category: AI-powered optimization platform for bakeries and pastry shops.

Positioning statement:

> The AI that turns your bakery data into smarter daily decisions.

Main slogan:

> Produce smarter. Sell better. Waste less.

Brand voice:

- Clear.
- Intelligent.
- Practical.
- Trustworthy.
- Modern.
- Supportive.
- Artisan-aware.
- Data-driven but simple.

Avoid:

- Overly technical AI language.
- Cold automation language.
- Enterprise jargon.
- Claims that the product replaces the baker.

Preferred visual direction:

- Clean B2B SaaS product.
- Technological but still connected to bakeries.
- Professional and trustworthy.
- Minimalist and suitable for business presentations.
