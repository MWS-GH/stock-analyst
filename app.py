import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import time
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="MAG7 & AMD Live Hub", layout="wide", page_icon="📈")

# --- CSS STYLING (Für den Barchart-Look) ---
st.markdown("""
<style>
    .metric-card {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
        margin-bottom: 10px;
    }
    .bullish { color: #00ff00; font-weight: bold; }
    .bearish { color: #ff4b4b; font-weight: bold; }
    .neutral { color: #888888; }
    .big-font { font-size: 20px !important; }
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

# Cache für 1 Minute, damit es schnell bleibt, aber aktuell ist
@st.cache_data(ttl=60)
def get_data(ticker):
    # Holt Daten: 5 Tage Intraday (für genaue Indikatoren) + Heute
    # 60m Intervall ist gut für "Stündliche" Analyse
    df = yf.download(ticker, period="5d", interval="60m", progress=False)
    
    # MultiIndex Bereinigung
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Indikatoren berechnen (pandas_ta)
    df.ta.rsi(length=14, append=True)
    df.ta.macd(append=True)
    df.ta.sma(length=20, append=True)
    df.ta.sma(length=50, append=True)
    df.ta.sma(length=200, append=True)
    df.ta.bbands(length=20, std=2, append=True) # Bollinger Bands
    
    return df

def calculate_pivot_points(df):
    # Pivot Points basieren normalerweise auf dem VORTAG (High/Low/Close)
    # Wir suchen den letzten kompletten Tag
    last_day = df.index[-1].date()
    # Daten filtern (Achtung: Intraday Daten haben Datum+Uhrzeit im Index)
    # Vereinfacht: Wir nehmen die letzten 8 Kerzen (ca. 1 Handelstag)
    recent_data = df.tail(8)
    
    high = recent_data['High'].max()
    low = recent_data['Low'].min()
    close = recent_data['Close'].iloc[-1]
    
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    
    return {"P": pivot, "R1": r1, "S1": s1, "R2": r2, "S2": s2}

def get_signal_color(value, reference, type="standard"):
    # Helper für Farben
    if type == "rsi":
        if value < 30: return "🟢 BUY (Oversold)"
        elif value > 70: return "🔴 SELL (Overbought)"
        else: return "⚪ NEUTRAL"
    
    if value > reference: return "🟢 BULLISH"
    elif value < reference: return "🔴 BEARISH"
    else: return "⚪ NEUTRAL"

# --- SIDEBAR (Auto-Refresh Steuerung) ---
st.sidebar.header("⚙️ Einstellungen")
auto_refresh = st.sidebar.checkbox("Live Auto-Update (60s)", value=False)

if auto_refresh:
    time.sleep(60)
    st.rerun()

if st.sidebar.button("Manuell Aktualisieren"):
    st.rerun()

st.sidebar.markdown(f"Letztes Update: {datetime.now().strftime('%H:%M:%S')}")

# --- HAUPTBEREICH ---

st.title("🚀 Live Trading Hub: MAG7 & Chips")

# Reiter erstellen
tabs_labels = ["📊 Gesamtübersicht"] + list(TICKERS.keys())
tabs = st.tabs(tabs_labels)

# --- TAB 1: GESAMTÜBERSICHT ---
with tabs[0]:
    st.subheader("Marktstimmung auf einen Blick")
    
    overview_data = []
    
    # Ladebalken für UX
    progress_bar = st.progress(0)
    total_tickers = len(TICKERS)
    
    for i, (name, sym) in enumerate(TICKERS.items()):
        df = get_data(sym)
        if not df.empty:
            curr = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2]
            pct_change = ((curr - prev) / prev) * 100
            rsi = df['RSI_14'].iloc[-1]
            trend = "↗️" if curr > df['SMA_50'].iloc[-1] else "↘️"
            
            overview_data.append({
                "Name": name,
                "Kurs ($)": f"{curr:.2f}",
                "Change (%)": pct_change, # Als Zahl lassen für Färbung
                "RSI (1h)": f"{rsi:.1f}",
                "Trend (SMA50)": trend
            })
        progress_bar.progress((i + 1) / total_tickers)
    
    progress_bar.empty()
    
    # DataFrame Styling
    overview_df = pd.DataFrame(overview_data)
    
    def color_change(val):
        color = '#00ff00' if val > 0 else '#ff4b4b' if val < 0 else 'white'
        return f'color: {color}'

    st.dataframe(
        overview_df.style.applymap(color_change, subset=['Change (%)'])
                         .format({'Change (%)': "{:+.2f}%"}),
        use_container_width=True,
        height=500
    )

# --- TABS FÜR EINZELAKTIEN ---
# Wir iterieren durch die restlichen Tabs (Index 1 bis Ende)
for i, (name, symbol) in enumerate(TICKERS.items()):
    with tabs[i+1]:
        # Daten holen (schon gecached)
        df = get_data(symbol)
        
        if df.empty:
            st.error("Keine Daten verfügbar.")
            continue

        # Letzte Werte
        current_price = df['Close'].iloc[-1]
        pivots = calculate_pivot_points(df)
        
        # Layout: Header mit Metriken
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Preis", f"{current_price:.2f} $", f"{(current_price - df['Close'].iloc[-2]):.2f} $")
        m2.metric("High (24h)", f"{df.tail(8)['High'].max():.2f} $")
        m3.metric("Low (24h)", f"{df.tail(8)['Low'].min():.2f} $")
        m4.metric("Volumen", f"{df['Volume'].iloc[-1] / 1e6:.1f}M")
        
        st.markdown("---")
        
        # --- CHEAT SHEET SEKTION ---
        st.subheader(f"🧩 {name} Cheat Sheet")
        
        c1, c2, c3 = st.columns(3)
        
        # Spalte 1: Moving Averages & Trend
        with c1:
            st.markdown("### 📈 Trend Indikatoren")
            sma20 = df['SMA_20'].iloc[-1]
            sma50 = df['SMA_50'].iloc[-1]
            sma200 = df['SMA_200'].iloc[-1]
            
            st.markdown(f"""
            | Indikator | Wert | Signal |
            | :--- | :--- | :--- |
            | **SMA 20** | {sma20:.2f} | {get_signal_color(current_price, sma20)} |
            | **SMA 50** | {sma50:.2f} | {get_signal_color(current_price, sma50)} |
            | **SMA 200** | {sma200:.2f} | {get_signal_color(current_price, sma200)} |
            """)
            
        # Spalte 2: Oszillatoren
        with c2:
            st.markdown("### 🌊 Momentum / Stärke")
            rsi = df['RSI_14'].iloc[-1]
            macd = df['MACD_12_26_9'].iloc[-1]
            macd_s = df['MACDs_12_26_9'].iloc[-1]
            
            macd_signal = "🟢 BULLISH" if macd > macd_s else "🔴 BEARISH"
            
            st.markdown(f"""
            | Indikator | Wert | Status |
            | :--- | :--- | :--- |
            | **RSI (14)** | {rsi:.1f} | {get_signal_color(rsi, 0, 'rsi')} |
            | **MACD** | {macd:.3f} | {macd_signal} |
            """)
            
            st.progress(rsi/100, text="RSI Meter")

        # Spalte 3: Support & Resistance (Pivot)
        with c3:
            st.markdown("### 🧱 Support & Resistance")
            st.markdown(f"""
            | Level | Preis |
            | :--- | :--- |
            | **Res 2** | {pivots['R2']:.2f} $ |
            | **Res 1** | {pivots['R1']:.2f} $ |
            | **PIVOT** | **{pivots['P']:.2f} $** |
            | **Sup 1** | {pivots['S1']:.2f} $ |
            | **Sup 2** | {pivots['S2']:.2f} $ |
            """)

        st.markdown("---")
        
        # --- CHART SEKTION (Plotly) ---
        st.subheader("📊 Interaktiver Chart (1h Kerzen)")
        
        fig = go.Figure()
        
        # Candlestick
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'],
            name='Preis'
        ))
        
        # SMA Linien hinzufügen
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='orange', width=1), name='SMA 50'))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='blue', width=1), name='SMA 200'))

        fig.update_layout(
            height=500, 
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            margin=dict(l=0, r=0, t=0, b=0)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # --- ANALYSE FAZIT ---
        score = 0
        if rsi < 30: score += 1
        if rsi > 70: score -= 1
        if current_price > sma50: score += 1
        if current_price > pivots['P']: score += 1
        if macd > macd_s: score += 1
        
        if score >= 2: sentiment = "STRONG BUY 🚀"
        elif score >= 1: sentiment = "BUY ↗️"
        elif score <= -2: sentiment = "STRONG SELL 📉"
        elif score <= -1: sentiment = "SELL ↘️"
        else: sentiment = "HOLD ➡️"
        
        st.info(f"**Algorithmus Fazit für die nächste Stunde:** {sentiment} (Score: {score})")
