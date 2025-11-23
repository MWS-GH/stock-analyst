import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import matplotlib.pyplot as plt 
import time
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="MAG7 Pro Analyst V4", layout="wide", page_icon="💎")

# --- CSS STYLING ---
st.markdown("""
<style>
    .metric-card { background-color: #1e1e1e; padding: 15px; border-radius: 10px; border: 1px solid #333; margin-bottom: 10px; }
    .stDataFrame { font-size: 14px; }
    /* Highlight für starke Signale */
    div[data-testid="stMetricValue"] { font-weight: bold; }
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

@st.cache_data(ttl=60)
def get_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        # Period 6mo für SMA200
        df = stock.history(period="6mo", interval="60m")
        
        if df.empty: return pd.DataFrame()

        # Zeitzone: Von US/UTC auf Berlin konvertieren
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC') # Annahme UTC falls keine Info
        df.index = df.index.tz_convert('Europe/Berlin')

        # INDIKATOREN
        if len(df) > 14:
            df.ta.rsi(length=14, append=True)
            df.ta.macd(append=True)
            df.ta.atr(length=14, append=True)
        
        if len(df) > 20: df.ta.sma(length=20, append=True)
        if len(df) > 50: df.ta.sma(length=50, append=True)
        if len(df) > 200: df.ta.sma(length=200, append=True)
        
        try: df.ta.vwap(append=True)
        except: pass

        return df
    except Exception as e:
        return pd.DataFrame()

def calculate_fibonacci(df):
    last_month = df.tail(160)
    if last_month.empty: last_month = df
    max_p = last_month['High'].max()
    min_p = last_month['Low'].min()
    diff = max_p - min_p
    return {
        "0.5": max_p - 0.5 * diff,
        "0.618": max_p - 0.618 * diff,
    }

def get_market_signal(df, curr):
    # Logik für das "Gesamt-Signal" in der Übersicht
    score = 0
    if 'RSI_14' in df.columns:
        if df['RSI_14'].iloc[-1] < 30: score += 2 # Strong Buy Signal
        elif df['RSI_14'].iloc[-1] > 70: score -= 2 # Strong Sell Signal
    
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
    # Nur letzte 30 Tage
    heatmap_df = df.tail(200).copy() 
    heatmap_df['Hourly_Change'] = ((heatmap_df['Close'] - heatmap_df['Open']) / heatmap_df['Open']) * 100
    
    # Deutsche Formatierung
    heatmap_df['Datum_Wochentag'] = heatmap_df.index.strftime("%Y-%m-%d (%a)")
    heatmap_df['Uhrzeit'] = heatmap_df.index.strftime("%H:00")
    
    pivot = heatmap_df.pivot_table(index='Datum_Wochentag', columns='Uhrzeit', values='Hourly_Change')
    pivot = pivot.sort_index(ascending=False)
    
    # Filtere Spalten (nur Handelszeiten, falls Datenmüll dabei ist)
    valid_cols = [c for c in pivot.columns if "09" <= c <= "22"]
    pivot = pivot[valid_cols]
    
    return pivot

def analyze_vertical_patterns(pivot):
    # Findet Stunden, die > 70% grün oder rot sind
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
auto_refresh = st.sidebar.checkbox("Live Auto-Update (60s)", value=False)
if auto_refresh:
    time.sleep(60)
    st.rerun()
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# --- HAUPTBEREICH ---
st.title("💎 MAG7 Trading Dashboard V4")

tabs = st.tabs(["🚀 SIGNALS & MARKET"] + list(TICKERS.keys()))

# === TAB 0: SIGNAL ÜBERSICHT ===
with tabs[0]:
    st.subheader("Aktuelle Trading Signale (Live)")
    
    overview_data = []
    
    # Progress Bar
    prog = st.progress(0)
    
    for i, (name, sym) in enumerate(TICKERS.items()):
        df = get_data(sym)
        if not df.empty and len(df) > 20:
            curr = df['Close'].iloc[-1]
            change = ((curr - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
            
            # Smart Signal berechnen
            signal = get_market_signal(df, curr)
            
            # RSI
            rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 50
            
            overview_data.append({
                "Asset": name,
                "SIGNAL": signal,  # <-- Das ist neu!
                "Preis (€/$)": curr,
                "Change %": change,
                "RSI": rsi,
            })
        prog.progress((i+1)/len(TICKERS))
    prog.empty()
    
    if overview_data:
        ov_df = pd.DataFrame(overview_data)
        
        # Styling für die Signale
        def color_signals(val):
            if "STRONG BUY" in val: return 'background-color: #004d00; color: white; font-weight: bold'
            if "BUY" in val: return 'color: #00ff00'
            if "STRONG SELL" in val: return 'background-color: #4d0000; color: white; font-weight: bold'
            if "SELL" in val: return 'color: #ff4b4b'
            return 'color: gray'

        st.dataframe(
            ov_df.style
            .format({"Preis (€/$)": "{:.2f}", "Change %": "{:+.2f}%", "RSI": "{:.1f}"})
            .applymap(color_signals, subset=['SIGNAL'])
            .applymap(lambda x: 'color: #00ff00' if x > 0 else 'color: #ff4b4b', subset=['Change %']),
            use_container_width=True,
            height=600
        )

# === TABS: EINZELWERTE ===
for i, (name, symbol) in enumerate(TICKERS.items()):
    with tabs[i+1]:
        df = get_data(symbol)
        
        if df.empty or len(df) < 20:
            st.warning("Lade Daten... (Warte auf Marktöffnung oder API)")
            continue

        curr = df['Close'].iloc[-1]
        fibs = calculate_fibonacci(df)
        signal = get_market_signal(df, curr)
        
        # --- HEADER METRICS ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preis (DE Zeit)", f"{curr:.2f}", f"{curr - df['Close'].iloc[-2]:.2f}")
        c2.metric("SIGNAL", signal.replace("💎", "").replace("🔥",""))
        
        rsi_val = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 50
        c3.metric("RSI (1h)", f"{rsi_val:.1f}")
        c4.metric("Fib Golden Zone", f"{fibs['0.618']:.2f}")

        st.markdown("---")
        
        # --- INTELLIGENTE HEATMAP ---
        st.subheader("⏰ Muster-Erkennung (DE Zeit)")
        heatmap_df = get_hourly_heatmap_data(df)
        
        if not heatmap_df.empty:
            # 1. Automatische Analyse anzeigen
            patterns = analyze_vertical_patterns(heatmap_df)
            if patterns:
                st.info("💡 **Erkannte Muster:** " + " | ".join(patterns))
            else:
                st.caption("Keine extremen stündlichen Muster erkannt.")

            # 2. Die Heatmap selbst
            st.dataframe(
                heatmap_df.style
                .background_gradient(cmap='RdYlGn', vmin=-1.0, vmax=1.0)
                .format("{:+.2f}%")
                .highlight_null(color='#1e1e1e'),
                use_container_width=True,
                height=350
            )
        
        # --- CHART ---
        st.subheader("📊 Chart Analyse")
        fig = go.Figure()
        
        # Candles
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Kurs'))
        
        # Indikatoren
        if 'VWAP_D' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['VWAP_D'], line=dict(color='violet', width=2, dash='dot'), name='VWAP'))
        if 'SMA_50' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='orange', width=1), name='SMA 50'))

        # Fibs
        fig.add_hline(y=fibs['0.5'], line_dash="dash", line_color="yellow", annotation_text="Fib 0.5")
        fig.add_hline(y=fibs['0.618'], line_dash="dash", line_color="green", annotation_text="Fib 0.618")

        fig.update_layout(height=500, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- CHEAT SHEET (Kompakt) ---
        with st.expander("🧩 Strategie-Details", expanded=False):
            sc1, sc2 = st.columns(2)
            with sc1:
                st.write(f"**Trend (SMA50):** {'🟢 Bullish' if curr > df['SMA_50'].iloc[-1] else '🔴 Bearish'}")
                st.write(f"**Volumen:** {df['Volume'].iloc[-1]/1000:.0f}k")
            with sc2:
                st.write(f"**ATR (Range):** {df['ATRr_14'].iloc[-1]:.2f}")
                st.write(f"**VWAP:** {df['VWAP_D'].iloc[-1] if 'VWAP_D' in df.columns else 'N/A'}")
