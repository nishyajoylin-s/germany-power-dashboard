# Germany Live Power Grid — Decisions

## Context
A single-screen, genuinely-live dashboard of the German power system, built as a climate
portfolio piece. Everything is stitched from public, key-free feeds using the same
fetch-JSON → pandas → Plotly pattern, then laid out as a command-centre (numbered panels,
glowing cyan/navy theme, map centrepiece).

## Decisions

### D1 — One national endpoint
Energy-Charts `public_power?country=de` returns every generation source **plus** the official
"Renewable share of generation", so the headline share uses the API's own figure. `price?bzn=DE-LU`
adds the day-ahead wholesale price.

### D2 — Classify the series, don't plot all of them
The feed mixes generation with metrics (Load, Residual load, Cross-border trading, pumped-storage
consumption, share %). We stack only true generation sources; Load is drawn as a separate dotted
"demand" line; cross-border trading becomes the net export/import figure.

### D3 — Carbon intensity is computed, not fetched
Energy-Charts exposes no CO₂ endpoint for DE (`/co2_emissions` returns 404), so grid intensity is
derived from the live mix with IPCC AR5 lifecycle factors (gCO₂eq/kWh). Transparent and auditable
beats a black-box number for a climate audience.

### D4 — 16 states, sampled at their capitals
The GrünstromIndex feed is keyed by **postcode**, so to cover all 16 federal states we use one
postcode per state (its capital). Picking the "biggest cities" instead clustered 5 points in NRW
and left 7 states empty — the capitals give full, even national coverage.

### D5 — Solar heatmap via a batched grid, not 2,000 calls
A live per-town green-power map would need ~2,000 GrünstromIndex calls per refresh (rate-limited,
slow). Instead, one batched Open-Meteo call returns a ~300-point solar-irradiance grid in ~350 ms,
rendered as a `Densitymapbox` field behind the state bubbles — dense *and* cheap.

### D6 — Command-centre palette
Cyan/teal/blue for renewables, magenta/violet for fossils, on a navy gradient with glowing
panels. The green-index map uses a magenta→amber→teal scale (dirty→clean) so it still reads at a
glance while matching the theme.

### D7 — No nuclear, on purpose
Germany shut its last reactors in April 2023, so there is no nuclear series. The sidebar says so,
so the absence reads as accurate, not a bug.

## Gotchas worth remembering
- `Densitymapbox` silently renders nothing with a transparent low-end colour scale — use solid
  colours + `opacity`, and keep it the same trace family (`*mapbox`) as the bubbles.
- `add_vline` with a tz-aware pandas Timestamp throws (it averages timestamps); use `add_shape` +
  `add_annotation` with `.to_pydatetime()` instead.

## Ideas for next iterations
- Clip the solar field to Germany's outline (point-in-polygon on a GeoJSON).
- Genuinely-live regional load via SMARD's 4 TSO control zones (50Hertz / Amprion / TenneT / TransnetBW).
- Capacity factors: actual generation vs installed capacity per source.
- Renewable share / carbon intensity vs the same weekday last week.
