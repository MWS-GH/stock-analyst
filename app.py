import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import matplotlib.pyplot as plt 
import time
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="MAG7 Pro Analyst V8", layout="wide", page_icon="📈")

# --- CSS STYLING ---
st.markdown("""
<style>
    .metric-card { background-color: #1e1e1e; padding: 15px; border-radius: 10px; border: 1px solid #333; margin-bottom: 10px; }
    .stDataFrame { font-size: 14px; }
    div[data-testid="stMetricValue"] { font-weight: bold; font-size: 1.2rem; } 
    /* Style für Tooltip-Marker */
    span[title] { border-bottom: 1px dotted #888; cursor: help; }
</style>
""", unsafe_allow_html=True)

# --- TICKER LISTE ---
TICKERS = {
    "AMD": "AMD", "NVIDIA": "NVDA", "Apple": "AAPL", 
    "Microsoft": "MSFT", "Google": "GOOG", "Amazon": "AMZN", 
    "Meta": "META", "Tesla": "TSLA", "S&P 500": "^GSPC", 
    "Nasdaq": "^IXIC", "VIX": "^VIX"
}

# --- FUNKTIONEN ---

# NEU: HELPER FUNKTION FÜR TOOLTIPS
def create_tooltip(text, explanation):
    """Erzeugt einen HTML-String mit einem Tooltip (Mouseover Text)."""
    # Das ❓-Zeichen dient als visueller Hinweis
    html = f'<span title="{explanation}" style="cursor: help;">{text} ❓</span>'
    # Streamlit muss dies als Markdown/HTML rendern
    return html

@st.cache_data(ttl=60)
def get_data(ticker, interval):
    try:
        if interval == '1d':
            period = "1y"
        else:
            period = "6mo"

        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval, prepost=(interval != '1d')) 
        
        if df.empty: return pd.DataFrame()

        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert('Europe/Berlin')

        # INDIKATOREN
        if len(df) > 14:
            df.ta.rsi(length=14, append=True)
            df.ta.macd(append=True)
            df.ta.atr(length=14, append=True)
            df.ta.adx(length=14, append=True)
        
        if len(df) > 20: df.ta.sma(length=20, append=True)
        if len(df) > 50: df.ta.sma(length=50, append=True)
        if len(df) > 200: df.ta.sma(length=200, append=True)
        
        try: df.ta.vwap(append=True)
        except: pass

        return df
    except Exception as e:
        return pd.DataFrame()

# ... (Die Funktionen calculate_fibonacci, calculate_pivot_points, get_market_signal bleiben unverändert) ...

def calculate_fibonacci(df):
    last_window = df.tail(160)
    if last_window.empty: last_window = df
    max_p = last_window['High'].max()
    min_p = last_window['Low'].min()
    diff = max_p - min_p
    return {
        "0.5": max_p - 0.5 * diff,
        "0.618": max_p - 0.618 * diff,
    }

def calculate_pivot_points(df):
    if df.empty or len(df) < 20: return {"P": 0, "R1": 0, "S1": 0, "R2": 0, "S2": 0}
    
    last_day_date = df.index[-2].date() 
    last_day_data = df[df.index.date == last_day_date]
    
    if last_day_data.empty:
        return {"P": 0, "R1": 0, "S1": 0, "R2": 0, "S2": 0}

    high = last_day_data['High'].max()
    low = last_day_data['Low'].min()
    close = last_day_data['Close'].iloc[-1]
    
    p = (high + low + close) / 3
    r1 = (2 * p) - low
    s1 = (2 * p) - high
    r2 = p + (high - low)
    s2 = p - (high - low)
    
    return {"P": p, "R1": r1, "S1": s1, "R2": r2, "S2": s2}

def get_market_signal(df, curr):
    score = 0
    if 'RSI_14' in df.columns:
        if df['RSI_14'].iloc[-1] < 30: score += 2 
        elif df['RSI_14'].iloc[-1] > 70: score -= 2
    
    if 'SMA_50' in df.columns:
        if curr > df['SMA_50'].iloc[-1]: score += 1
        else: score -= 1
        
    if 'VWAP_D' in df.columns:
        if curr > df['VWAP_D'].iloc[-1]: score += 1
        else: score -= 1

    if score >= 3: return "💎 STRONG BUY"
    elif score >= 1: return "🟢 BUY"
    elif score <= -3: return "🔥 STRONG SELL"
    elif score <= -1: return "🔴 SELL"
    return "🟡 WAIT"

def get_hourly_heatmap_data(df):
    heatmap_df = df.tail(200).copy() 
    heatmap_df['Hourly_Change'] = ((heatmap_df['Close'] - heatmap_df['Open']) / heatmap_df['Open']) * 100
    
    heatmap_df['Datum'] = heatmap_df.index.strftime("%Y-%m-%d") 
    heatmap_df['Uhrzeit'] = heatmap_df.index.strftime("%H:00")
    
    pivot = heatmap_df.pivot_table(index='Datum', columns='Uhrzeit', values='Hourly_Change')
    pivot = pivot.sort_index(ascending=False)
    
    valid_cols = [c for c in pivot.columns if "07:00" <= c <= "23:00"] 
    pivot = pivot[valid_cols]
    
    return pivot

def analyze_vertical_patterns(pivot):
    hints = []
    for col in pivot.columns:
        col_data = pivot[col].dropna()
        if len(col_data) > 5:
            pos_ratio = (col_data > 0).sum() / len(col_data)
            neg_ratio = (col_data < 0).sum() / len(col_data)
            
            if pos_ratio > 0.65:
                hints.append(f"⏰ **{col} Uhr:** Bullish Tendenz! ({pos_ratio*100:.0f}% grün)")
            elif neg_ratio > 0.65:
                hints.append(f"⏰ **{col} Uhr:** Bearish Tendenz! ({neg_ratio*100:.0f}% rot)")
    return hints

# --- SIDEBAR ---
st.sidebar.header("💎 Steuerung")
interval = st.sidebar.selectbox(
    "Zeitfenster (Interval)",
    ('60m', '30m', '1d'),
    index=0,
    help="Wechsle zwischen Stunden- und Tagesansicht. Heatmap nur bei Stundenansicht verfügbar."
)
auto_refresh = st.sidebar.checkbox("Live Auto-Update (60s)", value=False)
if auto_refresh:
    time.sleep(60)
    st.rerun()
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()


# --- HAUPTBEREICH ---
st.title(f"💎 MAG7 Trading Dashboard (V8 - {interval} Ansicht)")

tabs = st.tabs(["🚀 SIGNALS & MARKET"] + list(TICKERS.keys()))

# === TAB 0: SIGNAL ÜBERSICHT ===
with tabs[0]:
    st.subheader("Aktuelle Trading Signale (Live)")
    overview_data = []
    prog = st.progress(0)
    
    def color_signals(val):
        if "STRONG BUY" in val: return 'background-color: #004d00; color: white; font-weight: bold'
        if "BUY" in val: return 'color: #00ff00'
        if "STRONG SELL" in val: return 'background-color: #4d0000; color: white; font-weight: bold'
        if "SELL" in val: return 'color: #ff4b4b'
        return 'color: gray'

    for i, (name, sym) in enumerate(TICKERS.items()):
        df = get_data(sym, interval)
        if not df.empty and len(df) > 20:
            curr = df['Close'].iloc[-1]
            change = ((curr - df['Close'].iloc[-2]) / curr) * 100
            signal = get_market_signal(df, curr)
            rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 50
            
            overview_data.append({"Asset": name, "SIGNAL": signal, "Preis (€/$)": curr, "Change %": change, "RSI": rsi})
        prog.progress((i+1)/len(TICKERS))
    prog.empty()
    
    if overview_data:
        st.dataframe(
            pd.DataFrame(overview_data).style
            .format({"Preis (€/$)": "{:.2f}", "Change %": "{:+.2f}%", "RSI": "{:.1f}"})
            .applymap(color_signals, subset=['SIGNAL'])
            .applymap(lambda x: 'color: #00ff00' if x > 0 else 'color: #ff4b4b', subset=['Change %']),
            use_container_width=True, height=600
        )

# === TABS: EINZELWERTE ===
for i, (name, symbol) in enumerate(TICKERS.items()):
    with tabs[i+1]:
        df = get_data(symbol, interval)
        
        if df.empty or len(df) < 20:
            st.warning("Lade Daten... (Warte auf Marktöffnung, API, oder wähle passendes Intervall)")
            continue

        curr = df['Close'].iloc[-1]
        fibs = calculate_fibonacci(df)
        pivots = calculate_pivot_points(df) 
        signal = get_market_signal(df, curr)
        
        # --- HEADER METRICS (Mit R1 und S1) ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preis (DE Zeit)", f"{curr:.2f}", f"{curr - df['Close'].iloc[-2]:.2f}")
        c2.metric("SIGNAL", signal.replace("💎", "").replace("🔥",""))
        
        c3.metric("Resistance (R1)", f"{pivots['R1']:.2f}")
        c4.metric("Support (S1)", f"{pivots['S1']:.2f}")

        st.markdown("---")
        
        # --- HEATMAP & ADX ---
        if interval != '1d':
            st.subheader("⏰ Muster-Erkennung (07:00 - 23:00 Uhr CET)")
            heatmap_df = get_hourly_heatmap_data(df)
            
            if not heatmap_df.empty:
                patterns = analyze_vertical_patterns(heatmap_df)
                if patterns:
                    st.info("💡 **Erkannte Muster:** " + " | ".join(patterns))
                
                st.dataframe(heatmap_df.style.background_gradient(cmap='RdYlGn', vmin=-1.0, vmax=1.0).format("{:+.2f}%").highlight_null(color='#1e1e1e'), use_container_width=True, height=350)
        else:
            st.info("Heatmap ist nur für Stunden-Intervalle (30m / 60m) verfügbar.")
        
        # --- CHART ---
        st.subheader(f"📊 Chart Analyse ({interval})")
        fig = go.Figure()
        
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Kurs'))
        
        if 'VWAP_D' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['VWAP_D'], line=dict(color='violet', width=2, dash='dot'), name='VWAP'))
        if 'SMA_50' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='orange', width=1), name='SMA 50'))

        fig.add_hline(y=fibs['0.618'], line_dash="dash", line_color="green", annotation_text="Fib 0.618")

        fig.update_layout(height=500, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- CHEAT SHEET (Detailliert) ---
        with st.expander("🎯 S/R-Levels & Strategie-Details", expanded=False):
            st.markdown("### Erklärung der Level")
            s1, s2, s3 = st.columns(3)

            # S/R LEVELS MIT TOOLTIPS
            with s1:
                st.markdown("**WIDERSTAND (R)**")
                st.markdown(create_tooltip(f"R2: **{pivots['R2']:.2f}** 🔴", "Widerstand 2: Ein sekundäres, höheres Preisniveau, bei dem Verkaufsdruck erwartet wird."), unsafe_allow_html=True)
                st.markdown(create_tooltip(f"R1: **{pivots['R1']:.2f}** 🔴", "Widerstand 1: Das wichtigste erwartete Preisniveau, bei dem der Aufwärtstrend gestoppt werden könnte."), unsafe_allow_html=True)
                st.markdown(create_tooltip(f"Pivot (P): **{pivots['P']:.2f}**", "Pivot Point: Der zentrale Dreh- und Angelpunkt für den Handelstag. Bestimmt die allgemeine tägliche Tendenz."), unsafe_allow_html=True)
            
            with s2:
                st.markdown("**UNTERSTÜTZUNG (S)**")
                st.markdown(create_tooltip(f"S1: **{pivots['S1']:.2f}** 🟢", "Unterstützung 1: Das wichtigste erwartete Preisniveau, bei dem Kaufinteresse den Kursverfall stoppen könnte."), unsafe_allow_html=True)
                st.markdown(create_tooltip(f"S2: **{pivots['S2']:.2f}** 🟢", "Unterstützung 2: Ein sekundäres, tieferes Preisniveau, bei dem starker Kaufdruck erwartet wird."), unsafe_allow_html=True)
                st.markdown("---")
                
                # FIBONACCI MIT TOOLTIP
                fib_text = f"Fib 0.618: {fibs['0.618']:.2f}"
                fib_exp = "Fibonacci Golden Retracement: Ein psychologisch wichtiges Level (61.8%), oft die stärkste S/R-Linie nach einer großen Bewegung."
                st.markdown(create_tooltip(fib_text, fib_exp), unsafe_allow_html=True)

            with s3:
                # ADX MIT TOOLTIP
                st.markdown("**TRENDSTÄRKE**")
                adx_val = df['ADX_14'].iloc[-1] if 'ADX_14' in df.columns else 0
                adx_status = "Starker Trend" if adx_val >= 25 else "Schwacher/Seitwärtstrend"
                adx_text = f"ADX (14): **{adx_val:.2f}**"
                adx_exp = "Average Directional Index: Misst die STÄRKE eines Trends. Werte über 25 zeigen einen klaren, verlässlichen Trend an (unabhängig von der Richtung)."
                st.markdown(create_tooltip(adx_text, adx_exp), unsafe_allow_html=True)
                st.write(f"Status: *{adx_status}*")
                
                st.markdown("---")
                st.markdown("**ZUSAMMENFASSUNG**")
                st.write(f"**Trend (SMA50):** {'🟢 Bullish' if curr > df['SMA_50'].iloc[-1] else '🔴 Bearish'}")
                st.write(f"**VWAP:** {df['VWAP_D'].iloc[-1] if 'VWAP_D' in df.columns else 'N/A'}")
