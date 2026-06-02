# ⚡ Germany — Live Power Grid & Carbon Dashboard

A real-time dashboard for the German electricity system: **what is generating power right
now, how clean it is, and what it costs.** Built with Streamlit and Plotly on top of the
public [Energy-Charts](https://energy-charts.info) API (Fraunhofer ISE). No API key, no
database, no simulation — every refresh pulls live JSON and renders it.

🔗 **Live demo:** _deploying — link to follow_

---

## What it shows

**⚡ Live Mix** — the generation mix in real time: a stacked area of every source through the
day with demand overlaid, the current breakdown by source, and a renewable-vs-fossil split.

**🌱 Carbon & Climate** — a **grid carbon-intensity** figure (gCO₂/kWh) computed from the live
mix using IPCC AR5 lifecycle emission factors, the CO₂ emission rate (tonnes/hour), a carbon
gauge, a **renewable-share-vs-2030-target** gauge, and carbon intensity through the day.

**💶 Prices & Market** — the day-ahead wholesale power price (€/MWh) and a *"greener grid,
cheaper power?"* view showing how price moves with the renewable share.

**🗺 Federal states** — genuinely live data for **all 16 German states** (sampled at each state
capital): the [Corrently GrünstromIndex](https://corrently.de) (how green each postcode's power
is right now, 0–100, plus local CO₂) on a dark map, a "greenest state now" ranking, live
solar/wind per state from [Open-Meteo](https://open-meteo.com), and a forecast of the greenest
upcoming hours. The whole thing is a single-screen command-centre layout.

## Why carbon intensity is computed, not fetched

Energy-Charts has no CO₂ endpoint for Germany, so the dashboard derives grid carbon intensity
itself: `intensity = Σ(generationₛ × emission_factorₛ) / Σ(generationₛ)`, using published IPCC
AR5 median lifecycle factors (gCO₂eq/kWh). This makes the climate metric transparent and
auditable — every assumption is in `app.py`.

> Note: Germany shut down its last nuclear plants in April 2023, so there is no nuclear source.

## Run locally

```bash
git clone https://github.com/nishyajoylin-s/germany-power-dashboard.git
cd germany-power-dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)

Push to GitHub, then on [share.streamlit.io](https://share.streamlit.io) create a new app
with **Main file path:** `app.py`. It comes up in seconds — there is no data to download.

## Stack

| Piece | Tool |
|-------|------|
| Data | Energy-Charts (national generation + price) · Corrently GrünstromIndex (per-city green power) · Open-Meteo (per-city weather) |
| Carbon model | IPCC AR5 lifecycle emission factors |
| App / charts | Streamlit + Plotly |
| Refresh | `streamlit-autorefresh` (every 2 min, matching the 15-min feed) |

## Ideas / roadmap

See [`DECISIONS.md`](DECISIONS.md) for design rationale and next steps (CO₂ intensity vs. last
week, spot-price overlays, capacity factors).
