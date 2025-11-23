import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import time
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="MAG7 & AMD Ultimate", layout="wide", page_icon="⚡")

# --- CSS STYLING ---
st.markdown("""
<style>
    .metric-card { background-color: #1e1e1e; padding: 15px; border-radius: 10px; border: 1px solid #333; margin-bottom: 10px; }
    .stDataFrame { font-size: 13px; }
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
        # Period 1mo für genug Daten für die Heatmap, 60m Interval
        df = stock.history(period="1mo", interval="60m")
        
        if df.empty: return pd.DataFrame()

        # Zeitzone entfernen
        df.index = df.index.tz_localize(None)

        # INDIKATOREN
        if len(df) > 14:
            df.ta.rsi(length=14, append=True)
            df.ta.macd(append=True)
            df.ta.atr(length=14, append=True)
        
        if len(df) > 50: 
            df.ta.sma(length=20, append=True)
            df.ta.sma(length=50, append=True)
            df.ta.sma(length=200, append=True)
        
        try: df.ta.vwap(append=True)
        except: pass

        return df
    except Exception as e:
        return pd.DataFrame()

def calculate_fibonacci(df):
    # Fibonacci basierend auf der High/Low Range der geladenen Daten
    max_p = df['High'].max()
    min_p = df['Low'].min()
    diff = max_p - min_p
    
    return {
        "0.0 (High)": max_p,
        "0.236": max_p - 0.236 * diff,
        "0.382": max_p - 0.382 * diff,
        "0.5 (Mid)": max_p - 0.5 * diff,
        "0.618 (Golden)": max_p - 0.618 * diff,
        "1.0 (Low)": min_p
    }

def get_hourly_heatmap_data(df):
    # Wir berechnen die % Änderung pro Stunde
    # Erstelle Kopie um Warnungen zu vermeiden
    heatmap_df = df.copy()
    
    # Berechne Veränderung innerhalb der Kerze (Close - Open)
    heatmap_df['Hourly_Change'] = ((heatmap_df['Close'] - heatmap_df['Open']) / heatmap_df['Open']) * 100
    
    # Extrahiere Datum und Stunde
    heatmap_df['Date'] = heatmap_df.index.date
    heatmap_df['Hour'] = heatmap_df.index.hour
    
    # Pivot Tabelle: Zeilen=Datum, Spalten=Stunde, Werte=%Change
    pivot = heatmap_df.pivot_table(index='Date', columns='Hour', values='Hourly_Change')
    
    # Sortiere neuestes Datum nach oben
    pivot = pivot.sort_index(ascending=False)
    
    return pivot

def get_signal_color(value, reference, type="standard"):
    if pd.isna(value) or pd.isna(reference): return "⚪"
    if type == "rsi":
        if value < 30: return "🟢 BUY"
        elif value > 70: return "🔴 SELL"
        else: return "⚪"
    if value > reference: return "🟢"
    elif value < reference: return "🔴"
    else: return "⚪"

# --- SIDEBAR ---
st.sidebar.header("⚡ Steuerung")
auto_refresh = st.sidebar.checkbox("Live Auto-Update (60s)", value=False)
st.sidebar.info("💡 **Tipp:** Nutze die Heatmap, um zu sehen, zu welcher Uhrzeit die Aktie normalerweise steigt oder fällt.")

if auto_refresh:
    time.sleep(60)
    st.rerun()

if st.sidebar.button("🔄 Refresh"):
    st.rerun()

# --- HAUPTBEREICH ---
st.title("⚡ MAG7 Time-Analyst V3")

tabs = st.tabs(["📊 Markt & Matrix"] + list(TICKERS.keys()))

# === TAB 0: ÜBERSICHT ===
with tabs[0]:
    st.subheader("Markt-Momentum")
    
    overview_data = []
    prices = {}
    
    for name, sym in TICKERS.items():
        df = get_data(sym)
        if not df.empty:
            prices[name] = df['Close']
            curr = df['Close'].iloc[-1]
            change = ((curr - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
            rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 50
            
            overview_data.append({
                "Asset": name,
                "Preis": curr,
                "Change %": change,
                "RSI": rsi,
                "Volumen-Check": "⚠️ HOCH" if (df['Volume'].iloc[-1] > df['Volume'].mean()*1.5) else "Normal"
            })
            
    if overview_data:
        st.dataframe(
            pd.DataFrame(overview_data).style.format({"Preis": "{:.2f}", "Change %": "{:+.2f}", "RSI": "{:.1f}"})
            .applymap(lambda x: 'color: #00ff00' if x > 0 else 'color: #ff4b4b', subset=['Change %']),
            use_container_width=True
        )
    
    st.markdown("---")
    st.subheader("🔗 Live Korrelation")
    if prices:
        corr = pd.DataFrame(prices).dropna().corr()
        st.dataframe(corr.style.background_gradient(cmap="RdYlGn", axis=None).format("{:.2f}"), use_container_width=True)

# === TABS: EINZELWERTE ===
for i, (name, symbol) in enumerate(TICKERS.items()):
    with tabs[i+1]:
        df = get_data(symbol)
        if df.empty or 'SMA_50' not in df.columns:
            st.warning("Lade Daten...")
            continue

        curr = df['Close'].iloc[-1]
        fibs = calculate_fibonacci(df)
        
        # --- TOP METRICS ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preis", f"{curr:.2f} $", f"{curr - df['Close'].iloc[-2]:.2f} $")
        
        # Volume Anomaly Check
        avg_vol = df['Volume'].mean()
        curr_vol = df['Volume'].iloc[-1]
        vol_state = "🚨 SPIKE!" if curr_vol > avg_vol * 2 else "Normal"
        c2.metric("Volumen Status", vol_state, f"{(curr_vol/avg_vol)*100:.0f}% vom Avg")
        
        c3.metric("RSI (1h)", f"{df['RSI_14'].iloc[-1]:.1f}")
        c4.metric("Fib 0.618 (Golden)", f"{fibs['0.618 (Golden)']:.2f} $")
        
        # --- HEATMAP (Das neue Feature) ---
        st.markdown("---")
        st.subheader("⏰ Stündliche Performance (Heatmap)")
        st.caption("Zeigt die prozentuale Veränderung pro Stunde (Grün = Steigend, Rot = Fallend). Suche nach vertikalen Mustern!")
        
        heatmap_df = get_hourly_heatmap_data(df)
        
        # Heatmap Darstellung mit Farben
        st.dataframe(
            heatmap_df.style
            .background_gradient(cmap='RdYlGn', vmin=-1.5, vmax=1.5) # Farbskala anpassen
            .format("{:+.2f}%")
            .highlight_null(color='grey'),
            use_container_width=True,
            height=300
        )

        # --- CHART MIT FIBONACCI & VWAP ---
        st.subheader("📊 Chart Analyse")
        
        fig = go.Figure()
        
        # Candles
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
        
        # VWAP & SMAs
        if 'VWAP_D' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['VWAP_D'], line=dict(color='violet', width=2, dash='dot'), name='VWAP'))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='orange', width=1), name='SMA 50'))

        # Fibonacci Lines (Nur statisch rechts im Chart wäre besser, aber wir zeichnen sie durchgehend)
        fig.add_hline(y=fibs['0.5 (Mid)'], line_dash="dash", line_color="yellow", annotation_text="Fib 0.5")
        fig.add_hline(y=fibs['0.618 (Golden)'], line_dash="dash", line_color="green", annotation_text="Fib 0.618")

        fig.update_layout(height=500, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- CHEAT SHEET ---
        with st.expander("🧩 Detailliertes Cheat Sheet & Strategie", expanded=True):
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.markdown("**Trend**")
                st.write(f"SMA 50: {df['SMA_50'].iloc[-1]:.2f} | {get_signal_color(curr, df['SMA_50'].iloc[-1])}")
                st.write(f"SMA 200: {df['SMA_200'].iloc[-1]:.2f} | {get_signal_color(curr, df['SMA_200'].iloc[-1])}")
            with sc2:
                st.markdown("**Fibonacci Levels**")
                st.write(f"0.5 Retrace: {fibs['0.5 (Mid)']:.2f} $")
                st.write(f"0.618 Retrace: {fibs['0.618 (Golden)']:.2f} $")
            with sc3:
                st.markdown("**Fazit**")
                score = 0
                if df['RSI_14'].iloc[-1] < 30: score += 1
                if curr > df['SMA_50'].iloc[-1]: score += 1
                if curr > fibs['0.5 (Mid)']: score += 1
                
                sentiment = "HOLD ➡️"
                if score >= 2: sentiment = "BUY ↗️"
                if score <= 0: sentiment = "SELL ↘️"
                st.success(f"Signal: **{sentiment}**")
