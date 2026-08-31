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

### D8 — One screen, read in a Z
The dashboard is a single screen, not a scroll, laid out for how people scan: headline KPIs across
the top, the live map anchoring the centre, the diagonal of trend charts, and the one actionable
chart (when power will be greenest) at the bottom-right where the eye finishes. Metric values use
the condensed Rajdhani font on one line so cards stay equal height; long state names are abbreviated
only in the top KPI strip, and single-panel columns are stretched to equal height so each row lines
up.

## Gotchas worth remembering
- `Densitymapbox` silently renders nothing with a transparent low-end colour scale — use solid
  colours + `opacity`, and keep it the same trace family (`*mapbox`) as the bubbles.
- `add_vline` with a tz-aware pandas Timestamp throws (it averages timestamps); use `add_shape` +
  `add_annotation` with `.to_pydatetime()` instead.

## Resilience: per-feed graceful degradation (2026-08-03)
Energy-Charts (national mix + price) is a single upstream host. Previously, if it failed,
`load_power()` → `st.error()` + `st.stop()` blanked the **entire** dashboard — even though
GrünstromIndex (map, per-state index, forecast) and Open-Meteo (weather) were independent and
live. Now a failed power feed sets `power_ok=False` with `times/series/unix = [], {}, None`;
every power/price-derived panel renders an `_offline()` placeholder while the independent panels
keep working, and a warning banner explains the pause. The app auto-retries every 2 min via the
existing autorefresh + cache TTL. Rule: no single upstream host should be able to take down
panels fed by other sources.

## Plotly 6: MapLibre map traces (2026-08-31)
`requirements.txt` pinned `plotly>=5.20`, so Streamlit Cloud resolved 6.7 and the app died with
`AttributeError: module 'plotly.graph_objects' has no attribute 'Densitymapbox'` — Plotly 6 removed
the deprecated `*mapbox` traces outright. Migrated to `Densitymap`/`Scattermap` with `map_style` /
`map_center` / `map_zoom`, and pinned `plotly>=6.0` so local and deploy can't drift again.
`carto-darkmatter` is native to MapLibre, so the look is unchanged and still needs no token.
The gotcha above still holds, just rename `*mapbox` → `*map`.

## Keeping the app awake (2026-08-31)
Community Cloud sleeps idle apps with no way to disable it. A daily GitHub Actions cron
(`.github/workflows/keep-awake.yml`) loads the app so it looks like a visitor. It uses headless
Chromium, not curl, because every path on `*.streamlit.app` — `/_stcore/health` included — is
redirected through `share.streamlit.io/-/auth/app` and returns the same generic React shell with
HTTP 200. curl never reaches the app container, so it neither counts as traffic nor distinguishes
awake from asleep; a curl check would report green forever while the app slept. The container is
only reached once the page's JS opens its websocket. The assertion searches **frames**, because
Cloud renders the app in an iframe, and matches case-insensitively since the header is uppercased
by CSS. It asserts the app booted, not that data arrived — otherwise an Energy-Charts outage would
fail the ping even though degradation is handled by design.
Unknowns, deliberately: Streamlit doesn't document the inactivity threshold, so daily is a guess —
if the moon icon comes back, lower the cron. And GitHub disables scheduled workflows after 60 days
with no repo commits, which would silently end the pings.

## Ideas for next iterations
- Clip the solar field to Germany's outline (point-in-polygon on a GeoJSON).
- Genuinely-live regional load via SMARD's 4 TSO control zones (50Hertz / Amprion / TenneT / TransnetBW).
- Capacity factors: actual generation vs installed capacity per source.
- Renewable share / carbon intensity vs the same weekday last week.
