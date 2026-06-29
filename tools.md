# tools.md - ProductionIQ Assistant

## Required tools

### Sales data reader

Imports POS exports, spreadsheets, or daily sales summaries.

Allowed use:

- Read product sales by date, time, quantity, and revenue.
- Identify sellouts, slow sellers, and demand patterns.

### Inventory reader

Reads ingredient stock, product counts, and current availability.

Allowed use:

- Check whether recommendations are feasible.
- Flag low ingredients or finished stock.

### Waste tracker

Records unsold products, discarded items, and end-of-day leftovers.

Allowed use:

- Measure waste by product and day.
- Compare recommended production against actual leftovers.

### Demand forecaster

Estimates future demand using recent sales, seasonality, day of week, weather, holidays, and events.

Allowed use:

- Predict expected demand.
- Attach confidence levels to forecasts.

### Production recommender

Suggests daily production quantities by product.

Allowed use:

- Recommend product quantities for tomorrow or the week.
- Adjust recommendations based on waste, sellouts, and inventory constraints.

### Margin analyzer

Compares profitability using sales price, ingredient cost, estimated labor, and waste.

Allowed use:

- Identify high-margin products.
- Flag low-margin or high-waste products for review.

### Report generator

Creates simple planning summaries.

Allowed use:

- Generate daily production plans.
- Generate weekly performance reviews.
- Summarize accepted, edited, and rejected recommendations.

## Optional tools

- Weather lookup.
- Local events calendar.
- Supplier cost importer.
- Dashboard notification tool.

## Actions requiring approval

The agent must ask for human approval before:

- Placing supplier orders.
- Changing production plans for signature or high-volume products.
- Changing prices.
- Editing POS, inventory, or menu records.
- Removing products from the menu.
- Acting on low-confidence forecasts.

## Tool-use rules

- Use the smallest amount of data needed for the recommendation.
- Do not expose private sales, cost, or customer data unnecessarily.
- Explain when a recommendation depends on incomplete data.
- Record every recommendation and user decision in the log.
