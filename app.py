"""
Germany — Live Power Grid & Carbon Dashboard (single-screen command centre)

Real-time German electricity on one page: the national generation mix, a computed
grid carbon intensity, day-ahead prices, and genuinely-live per-city green power.
All from public feeds — no API key, no database.

Feeds:  Energy-Charts (Fraunhofer ISE) · Corrently GrünstromIndex · Open-Meteo
Carbon: computed from the live mix via IPCC AR5 lifecycle emission factors.
(Germany shut its last nuclear plants in April 2023, so there is no nuclear series.)

Run:    streamlit run app.py
"""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

POWER_API = "https://api.energy-charts.info/public_power?country=de"
PRICE_API = "https://api.energy-charts.info/price?bzn=DE-LU"
REFRESH_MS = 120000
REN_TARGET = 80

# ── cool palette (cyan/blue renewables · magenta/violet fossils) + IPCC factors ──
RENEWABLE = {
    "Solar": ("#22d3ee", 45), "Wind onshore": ("#34d399", 11),
    "Wind offshore": ("#2dd4bf", 12), "Hydro Run-of-River": ("#38bdf8", 24),
    "Hydro water reservoir": ("#60a5fa", 24), "Hydro pumped storage": ("#818cf8", 24),
    "Biomass": ("#a3e635", 230), "Geothermal": ("#5eead4", 38),
}
FOSSIL = {
    "Fossil gas": ("#f0883e", 490), "Fossil hard coal": ("#c084fc", 820),
    "Fossil brown coal / lignite": ("#e879a6", 1075),
    "Fossil coal-derived gas": ("#a78bfa", 820), "Fossil oil": ("#fb7185", 778),
}
OTHER = {"Waste": ("#94a3b8", 580), "Others": ("#64748b", 700)}
META = {**RENEWABLE, **FOSSIL, **OTHER}
COLORS = {k: v[0] for k, v in META.items()}
EF = {k: v[1] for k, v in META.items()}
STACK_ORDER = list(FOSSIL) + list(OTHER) + list(RENEWABLE)
GREEN_SCALE = [[0, "#ff5d8f"], [0.5, "#f6c945"], [1, "#2dd4bf"]]  # dirty → clean
SUN_SCALE = [[0, "#0a2647"], [0.35, "#1f6f9c"], [0.65, "#f0a830"], [1, "#ffe28c"]]  # dark → sunny

# One sample point per federal state = its capital (lat, lon, capital pop k, state, postcode).
# The GrünstromIndex feed is keyed by postcode, so the capital represents its state.
CITIES = [
    ("Stuttgart", 48.775, 9.182, 632, "Baden-Württemberg", "70173"),
    ("Munich", 48.137, 11.575, 1512, "Bavaria", "80331"),
    ("Berlin", 52.520, 13.405, 3677, "Berlin", "10115"),
    ("Potsdam", 52.396, 13.059, 183, "Brandenburg", "14467"),
    ("Bremen", 53.079, 8.802, 567, "Bremen", "28195"),
    ("Hamburg", 53.551, 9.993, 1906, "Hamburg", "20095"),
    ("Wiesbaden", 50.078, 8.240, 278, "Hesse", "65183"),
    ("Hannover", 52.376, 9.732, 535, "Lower Saxony", "30159"),
    ("Schwerin", 53.636, 11.401, 96, "Mecklenburg-Vorpommern", "19053"),
    ("Düsseldorf", 51.227, 6.773, 619, "North Rhine-Westphalia", "40213"),
    ("Mainz", 49.992, 8.247, 218, "Rhineland-Palatinate", "55116"),
    ("Saarbrücken", 49.240, 6.997, 181, "Saarland", "66111"),
    ("Dresden", 51.050, 13.737, 556, "Saxony", "01067"),
    ("Magdeburg", 52.131, 11.640, 238, "Saxony-Anhalt", "39104"),
    ("Kiel", 54.323, 10.135, 247, "Schleswig-Holstein", "24103"),
    ("Erfurt", 50.978, 11.029, 214, "Thuringia", "99084"),
]

st.set_page_config(page_title="Germany — Live Power & Carbon", page_icon="⚡", layout="wide")

# ── command-centre theme ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Orbitron:wght@600;700&display=swap');
:root{ --cyan:#22d3ee; --cyanb:#67e8f9; --txt:#d4ecff; --muted:#7fa8cf; --brd:rgba(45,170,230,0.30); }
.stApp{ background:
  radial-gradient(1100px 680px at 50% -12%, rgba(36,99,162,.55) 0%, rgba(0,0,0,0) 55%),
  radial-gradient(900px 600px at 88% 8%, rgba(34,211,238,.10) 0%, rgba(0,0,0,0) 45%),
  linear-gradient(180deg, #0d2447 0%, #0a1c39 40%, #061026 70%, #03070f 100%) fixed;
  color:var(--txt); }
[data-testid="stHeader"]{ background:transparent; }
.block-container{ padding:1.4rem 1.6rem 2rem; max-width:100%; }

h1,h2,h3,h4{ font-family:'Rajdhani',sans-serif!important; letter-spacing:.04em; color:#eaf6ff!important; }
.cc-title{ font-family:'Rajdhani'; font-weight:700; font-size:1.7rem; letter-spacing:.06em; color:#eaf6ff;
  text-shadow:0 0 22px rgba(34,211,238,.40); }
.cc-sub{ color:var(--muted); letter-spacing:.18em; text-transform:uppercase; font-size:.72rem; }

/* numbered panel header */
.phdr{ font-family:'Rajdhani'; font-weight:700; letter-spacing:.07em; text-transform:uppercase;
  color:#bfe9ff; font-size:.92rem; margin:.1rem 0 .5rem; display:flex; align-items:center; gap:8px;
  border-bottom:1px solid var(--brd); padding-bottom:6px; }
.pnum{ background:linear-gradient(135deg,#22d3ee,#2563eb); color:#04121f; font-weight:800;
  border-radius:4px; padding:1px 7px; font-size:.78rem; box-shadow:0 0 12px rgba(34,211,238,.5); }

/* metric cards */
[data-testid="stMetric"]{ background:linear-gradient(180deg, rgba(18,42,76,.55), rgba(9,22,44,.30));
  border:1px solid var(--brd); border-radius:8px; padding:10px 14px;
  box-shadow:inset 0 0 22px rgba(15,80,140,.16); }
[data-testid="stMetricValue"]{ font-family:'Rajdhani',sans-serif!important; color:var(--cyanb)!important;
  text-shadow:0 0 13px rgba(34,211,238,.5); font-weight:700; font-size:1.55rem; line-height:1.15;
  white-space:nowrap!important; overflow:visible!important; }
[data-testid="stMetricValue"] *{ white-space:nowrap!important; overflow:visible!important; text-overflow:clip!important; }
[data-testid="stMetricLabel"] p{ color:var(--muted)!important; text-transform:uppercase; letter-spacing:.09em; font-size:.66rem!important; }

/* bordered containers = glowing panels with corner brackets */
[data-testid="stVerticalBlockBorderWrapper"]{
  background:linear-gradient(160deg, rgba(20,46,84,.55) 0%, rgba(10,24,48,.42) 45%, rgba(6,14,30,.40) 100%)!important;
  border:1px solid var(--brd)!important; border-radius:6px;
  box-shadow:inset 0 0 34px rgba(12,44,86,.32), 0 0 18px rgba(15,90,150,.10); position:relative; }
[data-testid="stVerticalBlockBorderWrapper"]::before,[data-testid="stVerticalBlockBorderWrapper"]::after{
  content:''; position:absolute; width:14px; height:14px; border:2px solid var(--cyan); opacity:.85; z-index:3; }
[data-testid="stVerticalBlockBorderWrapper"]::before{ top:-1px; left:-1px; border-right:0; border-bottom:0; }
[data-testid="stVerticalBlockBorderWrapper"]::after{ bottom:-1px; right:-1px; border-left:0; border-top:0; }

[data-testid="stSidebar"]{ background:linear-gradient(180deg,#0a1c38,#060e20); border-right:1px solid var(--brd); }
hr{ border-color:var(--brd)!important; margin:.5rem 0; }
[data-testid="stExpander"]{ border:1px solid var(--brd); border-radius:6px; background:rgba(10,26,50,.4); }
small,[data-testid="stCaptionContainer"]{ color:var(--muted)!important; }
</style>
""", unsafe_allow_html=True)

pio.templates["grid"] = go.layout.Template(layout=dict(
    xaxis=dict(gridcolor="rgba(90,170,220,0.10)", zerolinecolor="rgba(90,170,220,0.20)"),
    yaxis=dict(gridcolor="rgba(90,170,220,0.10)", zerolinecolor="rgba(90,170,220,0.20)"),
))
DARK = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", template="grid",
            font=dict(color="#d4ecff", family="Rajdhani, sans-serif"))


# ── loaders ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def load_power():
    d = requests.get(POWER_API, timeout=25).json()
    unix = d["unix_seconds"]
    times = pd.to_datetime(unix, unit="s", utc=True).tz_convert("Europe/Berlin")
    series = {(s["name"]["en"] if isinstance(s["name"], dict) else s["name"]): s["data"]
              for s in d["production_types"]}
    return times, series, unix


@st.cache_data(ttl=600, show_spinner=False)
def load_price():
    try:
        d = requests.get(PRICE_API, timeout=20).json()
        return d["unix_seconds"], d["price"]
    except Exception:
        return None, None


def _gsi_now(zipc):
    fc = requests.get(f"https://api.corrently.io/v2.0/gsi/prediction?zip={zipc}",
                      timeout=15).json().get("forecast", [])
    if not fc:
        return None
    cur = min(fc, key=lambda x: abs(x.get("epochtime", 0) - time.time()))
    return {"gsi": cur.get("gsi"), "ee": cur.get("eevalue"), "co2": cur.get("co2_g_standard")}


@st.cache_data(ttl=600, show_spinner=False)
def load_city_green():
    out = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_gsi_now, c[5]): c[5] for c in CITIES}
        for fut, zipc in futs.items():
            try:
                out[zipc] = fut.result()
            except Exception:
                out[zipc] = None
    return out


@st.cache_data(ttl=900, show_spinner=False)
def load_city_weather():
    lats = ",".join(str(c[1]) for c in CITIES)
    lons = ",".join(str(c[2]) for c in CITIES)
    r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}"
                     "&current=temperature_2m,shortwave_radiation,wind_speed_10m,cloud_cover",
                     timeout=25).json()
    items = r if isinstance(r, list) else [r]
    return [it.get("current", {}) for it in items]


@st.cache_data(ttl=900, show_spinner=False)
def load_irradiance_grid():
    """One batched Open-Meteo call → a ~300-point live solar/wind grid over Germany."""
    lats, lons = [], []
    la = 47.3
    while la <= 55.1:
        lo = 5.9
        while lo <= 15.1:
            lats.append(round(la, 2)); lons.append(round(lo, 2)); lo += 0.55
        la += 0.45
    r = requests.get("https://api.open-meteo.com/v1/forecast?latitude=" + ",".join(map(str, lats))
                     + "&longitude=" + ",".join(map(str, lons))
                     + "&current=shortwave_radiation,wind_speed_10m", timeout=40).json()
    items = r if isinstance(r, list) else [r]
    irr = [it.get("current", {}).get("shortwave_radiation") for it in items]
    wind = [it.get("current", {}).get("wind_speed_10m") for it in items]
    return lats, lons, irr, wind


@st.cache_data(ttl=600, show_spinner=False)
def load_city_forecast(zipc):
    return requests.get(f"https://api.corrently.io/v2.0/gsi/prediction?zip={zipc}",
                        timeout=15).json().get("forecast", [])


def last_val(arr):
    return float(next((v for v in reversed(arr or []) if v is not None), 0.0))


# ── load everything ───────────────────────────────────────────────────────────
st_autorefresh(interval=REFRESH_MS, key="refresh")
t0 = time.perf_counter()
try:
    times, series, unix = load_power()
except Exception as e:  # noqa: BLE001
    st.error(f"Could not load the Energy-Charts feed: {e}")
    st.stop()
price_unix, price_vals = load_price()
with st.spinner("Fetching live grid, per-state green power, and the solar map…"):
    green, weather = load_city_green(), load_city_weather()
    glat, glon, girr, gwind = load_irradiance_grid()
fetch_ms = (time.perf_counter() - t0) * 1000
N = len(times)

# ── carbon intensity per timestamp ────────────────────────────────────────────
num = [0.0] * N
den = [0.0] * N
for name, ef in EF.items():
    arr = series.get(name)
    if not arr:
        continue
    for t, v in enumerate(arr):
        if v:
            num[t] += v * ef
            den[t] += v
intensity = [(num[t] / den[t]) if den[t] else None for t in range(N)]
co2_rate = [num[t] / 1000.0 for t in range(N)]

# ── national snapshot ─────────────────────────────────────────────────────────
gen_now = {n: last_val(series.get(n)) for n in META if n in series}
total_gen = sum(gen_now.values()) or 1.0
ren_now = sum(v for n, v in gen_now.items() if n in RENEWABLE)
fos_now = sum(v for n, v in gen_now.items() if n in FOSSIL)
oth_now = sum(v for n, v in gen_now.items() if n in OTHER)
ren_share = last_val(series.get("Renewable share of generation")) or (ren_now / total_gen * 100)
solar_now = gen_now.get("Solar", 0.0)
wind_now = gen_now.get("Wind onshore", 0.0) + gen_now.get("Wind offshore", 0.0)
load_now = last_val(series.get("Load"))
trade_now = last_val(series.get("Cross border electricity trading"))  # +import / -export
biggest = max(gen_now, key=gen_now.get) if gen_now else "—"
ci_valid = [(times[t], intensity[t]) for t in range(N) if intensity[t] is not None]
ci_now = ci_valid[-1][1] if ci_valid else 0.0
ci_avg = sum(v for _, v in ci_valid) / len(ci_valid) if ci_valid else 0.0
cleanest = min(ci_valid, key=lambda x: x[1]) if ci_valid else (times[-1], 0)
co2_now = co2_rate[-1] if co2_rate else 0.0
gw = lambda mw: f"{mw / 1000:,.1f} GW"  # noqa: E731

price_now = price_avg = None
p_times = None
if price_unix and price_vals:
    now = time.time()
    price_now = price_vals[min(range(len(price_unix)), key=lambda i: abs(price_unix[i] - now))]
    p_times = pd.to_datetime(price_unix, unit="s", utc=True).tz_convert("Europe/Berlin")
    _vp = [p for p in price_vals if p is not None]
    price_avg = sum(_vp) / len(_vp) if _vp else None

# ── cities dataframe ──────────────────────────────────────────────────────────
rows = []
for i, (city, lat, lon, pop, state, zipc) in enumerate(CITIES):
    g = green.get(zipc) or {}
    w = weather[i] if i < len(weather) else {}
    rows.append(dict(city=city, state=state, lat=lat, lon=lon, pop_k=pop, gsi=g.get("gsi"),
                     ee=g.get("ee"), co2=g.get("co2"), sun=w.get("shortwave_radiation"),
                     wind=w.get("wind_speed_10m")))
cdf = pd.DataFrame(rows)
live = cdf.dropna(subset=["gsi"])
greenest_state = live.loc[live["gsi"].idxmax(), "state"] if not live.empty else "—"
_SHORT_STATE = {"Baden-Württemberg": "Baden-Württ.", "Mecklenburg-Vorpommern": "Meck.-Vorp.",
                "North Rhine-Westphalia": "NRW", "Rhineland-Palatinate": "Rhineland-Pf.",
                "Schleswig-Holstein": "Schleswig-H."}
greenest_short = _SHORT_STATE.get(greenest_state, greenest_state)


# ── helpers ───────────────────────────────────────────────────────────────────
def phdr(num_, title):
    badge = f"<span class='pnum'>{num_:02d}</span>" if num_ else ""
    st.markdown(f"<div class='phdr'>{badge}{title}</div>", unsafe_allow_html=True)


def style(fig, h):
    fig.update_layout(**DARK, height=h, margin=dict(l=6, r=6, t=8, b=6), showlegend=False)
    return fig


# ═══════════════════════════ HEADER (top-left start of the Z) ═════════════════
hL, hR = st.columns([3, 1])
with hL:
    st.markdown("<div class='cc-title'>⚡ GERMANY · NATIONAL POWER GRID</div>"
                f"<div class='cc-sub'>Live · {ren_share:.0f}% renewable now · "
                f"{ci_now:.0f} gCO₂/kWh · greenest: {greenest_state}</div>", unsafe_allow_html=True)
with hR:
    now_b = pd.Timestamp.now(tz="Europe/Berlin")  # real wall-clock, not the server's UTC
    st.markdown(f"<div style='text-align:right'><span class='cc-title' style='font-size:1.4rem'>"
                f"{now_b.strftime('%H:%M')}</span><br><span class='cc-sub'>"
                f"{now_b.strftime('%a %d %b %Y')} · Berlin</span></div>", unsafe_allow_html=True)

# national key-indicator strip (top horizontal scan)
n1, n2, n3, n4, n5, n6 = st.columns(6)
n1.metric("Renewable share", f"{ren_share:.0f}%")
n2.metric("Carbon intensity", f"{ci_now:.0f} g")
n3.metric("Total generation", gw(total_gen))
n4.metric("Demand", gw(load_now))
n5.metric("Power price", f"€{price_now:,.0f}" if price_now is not None else "—")
n6.metric("Greenest state", greenest_short)
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ═══════════ ROW A — mix (left) · MAP anchor (centre) · carbon (right) ═════════
aL, aC, aR = st.columns([1.05, 1.5, 1.05])
with aL:
    with st.container(border=True):
        phdr(1, "Generation mix now")
        fig = go.Figure(go.Pie(labels=["Renewable", "Fossil", "Other"],
                               values=[ren_now, fos_now, oth_now], hole=0.62, sort=False,
                               marker_colors=["#22d3ee", "#e879a6", "#64748b"],
                               hovertemplate="%{label}: %{value:.0f} MW (%{percent})<extra></extra>"))
        fig.update_layout(annotations=[dict(text=f"{ren_share:.0f}%<br>green", showarrow=False,
                                            font=dict(size=18, color="#67e8f9"))],
                          legend=dict(orientation="h", y=-0.08, font=dict(size=10)))
        fig.update_layout(**DARK, height=230, margin=dict(l=6, r=6, t=6, b=6))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Solar {gw(solar_now)} · Wind {gw(wind_now)} · Fossil {gw(fos_now)}")
    with st.container(border=True):
        phdr(2, "By source · live MW")
        ordered = sorted(gen_now.items(), key=lambda kv: kv[1])
        fig = go.Figure(go.Bar(x=[v for _, v in ordered], y=[n for n, _ in ordered],
                               orientation="h", marker_color=[COLORS[n] for n, _ in ordered],
                               hovertemplate="%{y}: %{x:.0f} MW<extra></extra>"))
        st.plotly_chart(style(fig, 300), use_container_width=True)

with aC:
    with st.container(border=True):
        phdr(0, "Live solar glow + green-power · 16 states")
        if live.empty:
            st.warning("Green-power feed is quiet right now — retry shortly.")
        else:
            mp = live.assign(size=(live["pop_k"] / 130).clip(13, 32))
            fig = go.Figure()
            gpts = [(a, o, z) for a, o, z in zip(glat, glon, girr) if z is not None]
            if gpts:
                fig.add_trace(go.Densitymapbox(
                    lat=[p[0] for p in gpts], lon=[p[1] for p in gpts], z=[p[2] for p in gpts],
                    radius=38, zmin=0, zmax=950, opacity=0.38, showscale=False,
                    hoverinfo="skip", colorscale=SUN_SCALE))
            fig.add_trace(go.Scattermapbox(
                lat=mp["lat"], lon=mp["lon"], mode="markers",
                marker=dict(size=mp["size"], color=mp["gsi"], cmin=0, cmax=100,
                            colorscale=GREEN_SCALE, opacity=0.97, showscale=True,
                            colorbar=dict(title="green<br>index", thickness=12, x=0.99)),
                customdata=mp[["state", "city", "gsi", "ee", "co2", "sun", "wind"]],
                hovertemplate="<b>%{customdata[0]}</b>  (%{customdata[1]})"
                              "<br>Green index %{customdata[2]:.0f}/100"
                              "<br>Renewable %{customdata[3]:.0f}%  ·  %{customdata[4]:.0f} gCO₂/kWh"
                              "<br>Sun %{customdata[5]:.0f} W/m²  ·  Wind %{customdata[6]:.0f} km/h<extra></extra>"))
            fig.update_layout(**DARK, height=540, margin=dict(l=0, r=0, t=0, b=0),
                              showlegend=False, mapbox_style="carto-darkmatter",
                              mapbox_center=dict(lat=51.1, lon=10.2), mapbox_zoom=4.95)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Amber glow = live solar irradiance (~300 grid points); "
                       "bubbles = each state's live green-power index.")

with aR:
    with st.container(border=True):
        phdr(3, "Grid carbon intensity")
        g = go.Figure(go.Indicator(mode="gauge+number", value=ci_now, number={"suffix": " g"},
                                   gauge={"axis": {"range": [0, 700]}, "bar": {"color": "#67e8f9"},
                                          "steps": [{"range": [0, 150], "color": "#155e63"},
                                                    {"range": [150, 350], "color": "#7a5a12"},
                                                    {"range": [350, 700], "color": "#7a2348"}]}))
        g.update_layout(**DARK, height=230, margin=dict(l=14, r=14, t=8, b=4))
        st.plotly_chart(g, use_container_width=True)
        st.caption(f"cleanest {cleanest[1]:.0f} g at {cleanest[0].strftime('%H:%M')} · "
                   f"{co2_now:,.0f} t CO₂/h")
    with st.container(border=True):
        phdr(4, "Renewable vs 2030 target")
        g = go.Figure(go.Indicator(mode="gauge+number", value=ren_share, number={"suffix": "%"},
                                   gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#22d3ee"},
                                          "threshold": {"line": {"color": "#67e8f9", "width": 4},
                                                        "thickness": 0.85, "value": REN_TARGET}}))
        g.update_layout(**DARK, height=230, margin=dict(l=14, r=14, t=6, b=4))
        st.plotly_chart(g, use_container_width=True)

# ═══════════ ROW B — trends along the diagonal (mix · carbon · price) ═════════
bL, bC, bR = st.columns(3)
with bL:
    with st.container(border=True):
        phdr(5, "Mix through the day")
        fig = go.Figure()
        for name in STACK_ORDER:
            if name in series:
                fig.add_trace(go.Scatter(x=times, y=[v or 0 for v in series[name]], name=name,
                                         mode="lines", line=dict(width=0.5, color=COLORS[name]),
                                         stackgroup="g",
                                         hovertemplate="%{y:.0f} MW<extra>" + name + "</extra>"))
        if "Load" in series:
            fig.add_trace(go.Scatter(x=times, y=series["Load"], name="Demand", mode="lines",
                                     line=dict(color="#eaf6ff", width=1.6, dash="dot"),
                                     hovertemplate="%{y:.0f} MW<extra>Demand</extra>"))
        fig.update_layout(**DARK, height=230, margin=dict(l=6, r=6, t=6, b=6),
                          showlegend=False, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
with bC:
    with st.container(border=True):
        phdr(6, "Carbon intensity through the day")
        fig = go.Figure(go.Scatter(x=times, y=intensity, mode="lines",
                                   line=dict(color="#22d3ee", width=2), fill="tozeroy",
                                   fillcolor="rgba(34,211,238,0.12)",
                                   hovertemplate="%{y:.0f} gCO₂/kWh<extra></extra>"))
        fig.add_hline(y=ci_avg, line=dict(color="#7fa8cf", dash="dot"),
                      annotation_text=f"avg {ci_avg:.0f}", annotation_position="top left")
        st.plotly_chart(style(fig, 230), use_container_width=True)
with bR:
    with st.container(border=True):
        phdr(7, "Day-ahead power price")
        if p_times is not None:
            fig = go.Figure(go.Scatter(x=p_times, y=price_vals, mode="lines",
                                       line=dict(color="#38bdf8", width=2),
                                       hovertemplate="€%{y:.0f}/MWh<extra></extra>"))
            fig.add_hline(y=0, line=dict(color="#566", width=1))
            st.plotly_chart(style(fig, 230), use_container_width=True)
        else:
            st.info("Price feed unavailable.")

# ═══════ ROW C — final stroke: ranking · key figures · ACTION (bottom-right) ═══
cL, cC, cR = st.columns([1.1, 0.85, 1.15])
with cL:
    with st.container(border=True):
        phdr(8, "Greenest states right now")
        if not live.empty:
            rank = live.sort_values("gsi")
            fig = go.Figure(go.Bar(x=rank["gsi"], y=rank["state"], orientation="h",
                                   marker=dict(color=rank["gsi"], cmin=0, cmax=100,
                                               colorscale=GREEN_SCALE),
                                   hovertemplate="%{y}: %{x:.0f}/100<extra></extra>"))
            st.plotly_chart(style(fig, 320), use_container_width=True)
with cC:
    with st.container(border=True):
        phdr(0, "Key figures")
        r1 = st.columns(2)
        r1[0].metric("Solar", gw(solar_now))
        r1[1].metric("Wind", gw(wind_now))
        r2 = st.columns(2)
        r2[0].metric("Fossil", gw(fos_now))
        r2[1].metric("CO₂ rate", f"{co2_now:,.0f} t/h")
        r3 = st.columns(2)
        flow = "Net export" if trade_now < 0 else "Net import"
        r3[0].metric(flow, gw(abs(trade_now)))
        r3[1].metric("Avg price", f"€{price_avg:,.0f}" if price_avg is not None else "—")
with cR:
    with st.container(border=True):
        phdr(9, "When will power be greenest?")
        pick = st.selectbox("State", [c[4] for c in CITIES], index=1, label_visibility="collapsed")
        fc = load_city_forecast(next(c[5] for c in CITIES if c[4] == pick))
        if fc:
            ft = pd.to_datetime([x["epochtime"] for x in fc], unit="s",
                                utc=True).tz_convert("Europe/Berlin")
            fg = [x.get("gsi") for x in fc]
            best = max(range(len(fg)), key=lambda i: (fg[i] if fg[i] is not None else -1))
            fig = go.Figure(go.Scatter(x=ft, y=fg, mode="lines", line=dict(color="#2dd4bf", width=2),
                                       fill="tozeroy", fillcolor="rgba(45,212,191,0.12)",
                                       hovertemplate="%{y:.0f}/100<extra></extra>"))
            xbest = ft[best].to_pydatetime()
            fig.add_shape(type="line", x0=xbest, x1=xbest, yref="paper", y0=0, y1=1,
                          line=dict(color="#67e8f9", width=1.5, dash="dot"))
            fig.add_annotation(x=xbest, y=1.02, yref="paper", showarrow=False,
                               text=f"greenest {ft[best].strftime('%a %H:%M')}",
                               font=dict(color="#67e8f9", size=11))
            st.plotly_chart(style(fig, 250), use_container_width=True)
            st.caption(f"Greenest in **{pick}**: ~**{ft[best].strftime('%a %H:%M')}** "
                       f"({fg[best]:.0f}/100) — cheapest, lowest-carbon time to charge.")

# ── sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("About")
    st.caption("A single-screen live view of the German power system: national mix, computed "
               "grid carbon intensity (IPCC factors), day-ahead price, and live per-city "
               "green-power (GrünstromIndex) with weather.")
    st.divider()
    st.header("Diagnostics")
    st.caption("The clock (top-right) is live — the app auto-refreshes every 2 min while open. "
               "Streamlit Cloud sleeps when idle, then wakes and re-fetches on the next visit.")
    st.divider()
    st.caption(f"Energy-Charts publishes the national mix ~{max(0, int(time.time() - unix[-1])) // 60} "
               "min behind real time (the source's lag) — GrünstromIndex and weather are live.")
    st.caption(f"States live: {len(live)}/{len(CITIES)} · fetch {fetch_ms:.0f} ms")
    st.caption("Feeds: Energy-Charts · Corrently · Open-Meteo · no key, no DB")
    st.divider()
    st.caption("Germany shut its last nuclear plants in April 2023 — no nuclear in the mix.")
