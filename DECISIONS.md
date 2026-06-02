# Germany Live Power Grid — Decisions

## Context
A genuinely-live German counterpart to the Citi Bike app, for someone based in Munich.
Energy-Charts (Fraunhofer ISE) publishes the national generation mix every 15 minutes
with no API key, so it fits the same fetch-JSON → pandas → Plotly pattern.

## Decisions

### D1 — One endpoint does it all
`public_power?country=de` already returns every source **plus** the official
"Renewable share of generation", so we don't need the separate `ren_share` endpoint.
We use the API's share figure for the headline number rather than recomputing it.

### D2 — Classify series, don't plot all of them
The feed mixes generation with metrics (Load, Residual load, Cross-border trading,
pumped-storage consumption, share %). We stack only true generation sources and draw
Load as a separate dotted "demand" line over the top.

### D3 — No nuclear, on purpose
Germany shut its last reactors in April 2023, so there is no nuclear series. The
sidebar says so, so the absence reads as accurate rather than as a bug.

### D4 — Colour by energy type
Renewables green/blue, fossils brown/grey, so the stacked area and the right-now bar
read at a glance: a tall green band = a clean grid.

## Ideas for next iterations
- CO2 intensity (gCO2/kWh) via the Energy-Charts `co2_emissions` endpoint.
- Compare today's renewable share to the same weekday last week.
- Spot price overlay (`price?bzn=DE-LU`) to show when green = cheap.
