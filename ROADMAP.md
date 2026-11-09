# Roadmap

What I plan to add next, roughly in order. The first three are the current focus.

## Next

### Battery storage next to solar PPAs
Right now any solar output above the factory's load in a given hour is lost, which limits how large a solar contract is worth signing (the optimizer settles on about 30% of consumption in most cases). A battery could store that midday surplus and use it in the evening.

- Simple charge/discharge rule on the hourly residual: charge from surplus, discharge when load exceeds generation
- Battery described by energy capacity (MWh), power (MW) and round-trip efficiency
- Annualised battery cost per MWh of capacity, added to the contract cost
- Battery sizes added to the candidate grid so the optimizer can pick solar + storage like any other contract
- Tests on a synthetic load and generation profile, and battery inputs in the dashboard

Prices in the model are annual averages, so the battery only earns by reducing wasted surplus, not by buying cheap hours and selling expensive ones. Price arbitrage needs hourly prices (see Later).

### Upload real meter data
Let a buyer upload a CSV of hourly consumption instead of choosing a synthetic industry profile. Needs input checks (length, gaps, negative values, time zone) and a clear error when the file doesn't fit.

### Export results
Download the recommended portfolio, the cost and risk figures and the rationale as an Excel file.

## Later

- Editable assumptions in the dashboard: strike prices, counterparty spread, sleeving margin, discount rate
- Hourly price shapes, so the residual is bought at the price of the hours it falls in and batteries can do price arbitrage
- Indexed strikes, floors and caps, and inflation
- Single-axis tracking for solar
- Continuous contract sizing instead of the six fixed shares
