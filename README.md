# ⚡ Germany — Live Power Grid & Carbon Dashboard

A single-screen, real-time **command-centre** for the German electricity system: what's
generating power right now, how clean it is, what it costs, and how green each federal state
is — all on one page. Built with Streamlit + Plotly on public feeds. **No API key, no
database, no simulation** — every refresh pulls live JSON and renders it.

🔗 **Live demo:** **[germany-power-dashboard.streamlit.app](https://germany-power-dashboard.streamlit.app/)**

---

## What it shows (one screen, live panels)

- **Key-indicator strip** — renewable share, grid carbon intensity, total generation, demand,
  power price, and the greenest federal state, all live.
- **Generation mix** — renewable/fossil/other donut, a live by-source bar, and the day's mix as
  a stacked area with demand overlaid.
- **Live map (centrepiece)** — all **16 federal states** as bubbles coloured by their live
  [Corrently GrünstromIndex](https://corrently.de) (0–100 green-power score), sitting over a
  **live solar-irradiance field** sampled from a ~300-point [Open-Meteo](https://open-meteo.com)
  grid (amber where the sun is strongest right now).
- **Carbon & climate** — a computed grid carbon-intensity gauge (gCO₂/kWh) and its curve through
  the day, plus a renewable-share-vs-2030-target gauge.
- **Prices** — the day-ahead wholesale power price (€/MWh).
- **States** — a "greenest state right now" ranking and a forecast of the greenest upcoming hours
  for a chosen state (the cheapest, lowest-carbon time to run heavy loads).
- **Key figures** — solar, wind, fossil, CO₂ rate (t/h), net export/import, average price.

## Data (all live, no key)

| Feed | Provides |
|------|----------|
| [Energy-Charts](https://energy-charts.info) (Fraunhofer ISE) | national generation mix + day-ahead price |
| [Corrently GrünstromIndex](https://corrently.de) | per-postcode green-power index (sampled at each of the 16 state capitals) |
| [Open-Meteo](https://open-meteo.com) | live solar irradiance + wind (per state, and a ~300-point grid for the heatmap) |

## Why carbon intensity is computed, not fetched

Energy-Charts has no CO₂ endpoint for Germany, so the dashboard derives grid carbon intensity
itself: `intensity = Σ(generationₛ × emission_factorₛ) / Σ(generationₛ)`, using published IPCC
AR5 median lifecycle factors (gCO₂eq/kWh). Every assumption is in `app.py`, so the climate
metric is transparent and auditable.

> Germany shut down its last nuclear plants in April 2023, so there is no nuclear source.

## Run locally

```bash
git clone https://github.com/nishyajoylin-s/germany-power-dashboard.git
cd germany-power-dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)

Push to GitHub, then on [share.streamlit.io](https://share.streamlit.io) create a new app with
**Main file path:** `app.py`. It comes up in seconds — there is no data to download.

## Stack

| Piece | Tool |
|-------|------|
| Data | Energy-Charts · Corrently GrünstromIndex · Open-Meteo (all key-free) |
| Carbon model | IPCC AR5 lifecycle emission factors (in `app.py`) |
| App / charts | Streamlit + Plotly, single-screen command-centre layout |
| Refresh | `streamlit-autorefresh`, every 2 min (matching the 15-min feeds) |

## Roadmap

See [`DECISIONS.md`](DECISIONS.md). Next ideas: clip the solar field to Germany's borders,
genuinely-live regional load via SMARD's 4 TSO control zones, capacity factors (actual vs
installed), and renewable share vs the same weekday last week.
