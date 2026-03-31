import streamlit as st
import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "trading.duckdb")


@st.cache_data(ttl=300)
def load_metrics() -> pd.DataFrame:
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        df = con.execute("SELECT * FROM mart.trading_metrics ORDER BY trade_date").df()
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


df = load_metrics()

st.markdown(
    '<h1 style="text-align:center; margin-bottom:1.5rem;">Trading Analysis Dashboard</h1>',
    unsafe_allow_html=True,
)
st.divider()

if df.empty:
    st.warning("No data found. Run the pipeline first: `bruin run pipelines/trading_pipeline`")
    st.stop()

# ── Section 1: VVIX/VIX Ratio Trend ──────────────────────────────────────────

latest = df.iloc[-1]
prev = df.iloc[-2] if len(df) > 1 else None
delta = round(float(latest["vvix_vix_ratio"] - prev["vvix_vix_ratio"]), 4) if prev is not None else None
current_ratio = float(latest["vvix_vix_ratio"])

# Determine signal config
if current_ratio < 5:
    _label = "Low Ratio (&lt; 5)"
    _title = "Peak Stress / Turning Point"
    _body = (
        "VIX is elevated—fear has been realized—but VVIX lags, suggesting traders aren't expecting "
        "further chaos. This regime often marks peak stress, and the market may be near a turning point. "
        "Volatility could mean-revert or stabilize soon."
    )
    _accent = "#7c8aff"
    _bg = "rgba(124,138,255,0.08)"
    _icon = "🔵"
elif current_ratio <= 6:
    _label = "Mid Range (5–6)"
    _title = "Neutral Zone"
    _body = (
        "VVIX and VIX are proportionally aligned, and the market's volatility expectations match "
        "current conditions. No strong signal, but worth watching for directional drift."
    )
    _accent = "#8c8c8c"
    _bg = "rgba(140,140,140,0.08)"
    _icon = "⚪"
else:
    _label = "High Ratio (&gt; 6)"
    _title = "Calm Before the Storm"
    _body = (
        "VIX is low—markets appear calm—but VVIX is rising. Traders are aggressively pricing in "
        "future volatility. Hidden stress is building, and the ratio often spikes ahead of major "
        "volatility events or sharp market corrections."
    )
    _accent = "#e8a838"
    _bg = "rgba(232,168,56,0.10)"
    _icon = "🟡"

delta_color = "#00c853" if delta and delta > 0 else "#ff5252" if delta and delta < 0 else "#888"
delta_arrow = "▲" if delta and delta > 0 else "▼" if delta and delta < 0 else ""
delta_str = f"{delta:+.4f}" if delta is not None else "—"
latest_date = pd.to_datetime(latest["trade_date"]).strftime("%b %d, %Y")

st.markdown(
    f"""
    <div style="display:flex; align-items:flex-end; gap:24px; margin-bottom:4px;">
        <h2 style="margin:0; padding:0; line-height:1;">VVIX / VIX Ratio</h2>
        <span style="font-size:2rem; font-weight:700; line-height:1;">{current_ratio:.4f}</span>
        <span style="font-size:0.95rem; color:{delta_color}; font-weight:600; line-height:1; padding-bottom:3px;">
            {delta_arrow} {delta_str}
        </span>
        <span style="font-size:0.8rem; color:#888; line-height:1; padding-bottom:4px;">
            as of {latest_date}
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Signal alert — prominent, full-width
st.markdown(
    f"""
    <div style="background:{_bg}; border:1px solid {_accent}33; border-left:4px solid {_accent};
                border-radius:8px; padding:12px 16px; margin:8px 0 4px 0;">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
            <span style="font-size:1.1rem;">{_icon}</span>
            <span style="font-size:0.85rem; font-weight:700; color:{_accent}; text-transform:uppercase;
                         letter-spacing:0.5px;">{_label}</span>
            <span style="color:#999; font-size:0.85rem;">—</span>
            <span style="color:#ddd; font-size:0.85rem; font-weight:600;">{_title}</span>
        </div>
        <span style="color:#aaa; font-size:0.82rem; line-height:1.5;">{_body}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# General info — muted, collapsible
with st.expander("What is the VVIX/VIX Ratio?", expanded=False):
    st.caption(
        "Think of the VVIX/VIX ratio as a seismograph for the options market. "
        "When it's high, smart money expects the ground to start shaking—even if the surface looks steady. "
        "When it's low and VIX is high, the worst may be behind, and calmer times could be ahead."
    )

tab_ratio, tab_vix, tab_vvix = st.tabs(["VVIX/VIX Ratio", "VIX", "VVIX"])

with tab_ratio:
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=df["trade_date"],
        y=df["vvix_vix_ratio"],
        mode="lines+markers",
        name="VVIX/VIX Ratio",
        line=dict(color="#636EFA"),
    ))
    fig1.update_layout(
        xaxis_title="Date",
        yaxis_title="VVIX / VIX Ratio",
        hovermode="x unified",
        height=400,
    )
    st.plotly_chart(fig1, width='stretch')

with tab_vix:
    fig_vix = go.Figure()
    fig_vix.add_trace(go.Scatter(
        x=df["trade_date"],
        y=df["vix_close"],
        mode="lines+markers",
        name="VIX",
        line=dict(color="#EF553B"),
    ))
    fig_vix.update_layout(
        xaxis_title="Date",
        yaxis_title="VIX Close",
        hovermode="x unified",
        height=400,
    )
    st.plotly_chart(fig_vix, width='stretch')

with tab_vvix:
    fig_vvix = go.Figure()
    fig_vvix.add_trace(go.Scatter(
        x=df["trade_date"],
        y=df["vvix_close"],
        mode="lines+markers",
        name="VVIX",
        line=dict(color="#00CC96"),
    ))
    fig_vvix.update_layout(
        xaxis_title="Date",
        yaxis_title="VVIX Close",
        hovermode="x unified",
        height=400,
    )
    st.plotly_chart(fig_vvix, width='stretch')

# ── Section 2: ADR + VVIX/VIX Overlay ────────────────────────────────────────

st.header("VVIX/VIX Ratio & NQ ADR Overlay")

fig2 = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    row_heights=[0.6, 0.4],
    vertical_spacing=0.08,
    subplot_titles=("VVIX / VIX Ratio", "NQ Average Daily Range (ADR)"),
)
fig2.add_trace(go.Scatter(
    x=df["trade_date"], y=df["vvix_vix_ratio"],
    mode="lines+markers", name="VVIX/VIX",
    line=dict(color="#00CC96"),
), row=1, col=1)
fig2.add_trace(go.Bar(
    x=df["trade_date"], y=df["adr_nq"],
    name="NQ ADR", marker_color="#EF553B", opacity=0.7,
), row=2, col=1)
fig2.update_layout(hovermode="x unified", height=600)
fig2.update_yaxes(title_text="Ratio", row=1, col=1)
fig2.update_yaxes(title_text="ADR (pts)", row=2, col=1)
fig2.update_xaxes(title_text="Date", row=2, col=1)

st.plotly_chart(fig2, width='stretch')

# ── Section 3: QQQ → NQ Level Calculator ─────────────────────────────────────

st.header("QQQ → NQ Level Calculator")

ratio = float(latest["nq_qqq_ratio"])
st.metric("Latest NQ/QQQ Ratio", f"{ratio:.4f}")

input_text = st.text_area(
    "Paste QQQ levels (comma-separated key-value pairs):",
    placeholder="Call Resistance, 630, Put Support, 560, HVL, 600, ...",
    height=100,
)

if input_text.strip():
    tokens = [t.strip() for t in input_text.split(",")]

    if len(tokens) % 2 != 0:
        st.error("Invalid input: expected an even number of comma-separated tokens (label, value pairs).")
    else:
        output_parts = []
        error = False
        for i in range(0, len(tokens), 2):
            label = tokens[i]
            try:
                qqq_val = float(tokens[i + 1])
            except (ValueError, IndexError):
                st.error(f"Cannot parse value for '{label}': '{tokens[i + 1]}'")
                error = True
                break

            nq_val = qqq_val * ratio
            if nq_val == int(nq_val):
                formatted = str(int(nq_val))
            else:
                formatted = f"{nq_val:.2f}"
            output_parts.append(f"{label}, {formatted}")

        if not error:
            output_str = ", ".join(output_parts)
            st.code(output_str, language=None)

            # Copy-to-clipboard via embedded JS
            escaped = output_str.replace("\\", "\\\\").replace("`", "\\`").replace("'", "\\'")
            copy_html = f"""
            <button onclick="
                navigator.clipboard.writeText('{escaped}').then(function() {{
                    document.getElementById('copyBtn').innerText='Copied!';
                    setTimeout(function(){{ document.getElementById('copyBtn').innerText='Copy to Clipboard'; }}, 1500);
                }});
            " id="copyBtn" style="
                padding: 0.4em 1em;
                font-size: 1em;
                cursor: pointer;
                border-radius: 4px;
                border: 1px solid #ccc;
                background: #f0f0f0;
            ">Copy to Clipboard</button>
            """
            st.components.v1.html(copy_html, height=50)
