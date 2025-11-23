import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import time
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="MAG7 & AMD Live Hub", layout="wide", page_icon="📈")

# --- CSS STYLING ---
st.markdown("""
<style>
    .metric-card {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
        margin-bottom: 10px;
    }
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
        # Nutzung von yf.Ticker().history() ist stabiler für Einzelaktien
        stock = yf.Ticker(ticker)
        # Wir brauchen genug Historie für SMA200 (200 Stunden), daher 3-6 Monate
        df = stock.history(period="6mo", interval="60m")
        
        if df.empty:
            return pd.DataFrame()

        # Bereinigung: Zeitzone entfernen, um Probleme zu vermeiden
        df.index = df.index.tz_localize(None)

        # --- INDIKATOREN BERECHNEN ---
        # Wir prüfen, ob genug Daten da sind, um Fehler zu vermeiden
        if len(df) > 14:
            df.ta.rsi(length=14, append=True)
            df.ta.macd(append=True)
        else:
            df['RSI_14'] = 50 # Fallback
            df['MACD_12_26_9'] = 0

        if len(df) > 20: df.ta.sma(length=20, append=True)
        else: df['SMA_20'] = df['Close']

        if len(df) > 50: df.ta.sma(length=50, append=True)
        else: df['SMA_50'] = df['Close'] # Fallback, falls Aktie zu neu

        if len(df) > 200: df.ta.sma(length=200, append=True)
        else: df['SMA_200'] = df['SMA_50'] # Fallback auf SMA50

        return df
    except Exception as e:
        st.error(f"Fehler beim Laden von {ticker}: {e}")
        return pd.DataFrame()

def calculate_pivot_points(df):
    if df.empty: return {"P": 0, "R1": 0, "S1": 0, "R2": 0, "S2": 0}
    
    # Letzte 8 Stunden als "Tagesersatz" für Intraday Pivots
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
    if pd.isna(value) or pd.isna(reference): return "⚪ N/A"
    
    if type == "rsi":
        if value < 30: return "🟢 BUY (Oversold)"
        elif value > 70: return "🔴 SELL (Overbought)"
        else: return "⚪ NEUTRAL"
    
    if value > reference: return "🟢 BULLISH"
    elif value < reference: return "🔴 BEARISH"
    else: return "⚪ NEUTRAL"

# --- SIDEBAR ---
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

tabs_labels = ["📊 Gesamtübersicht"] + list(TICKERS.keys())
tabs = st.tabs(tabs_labels)

# --- TAB 1: ÜBERSICHT ---
with tabs[0]:
    st.subheader("Marktstimmung (Live)")
    
    overview_data = []
    progress_bar = st.progress(0)
    
    for i, (name, sym) in enumerate(TICKERS.items()):
        df = get_data(sym)
        if not df.empty and 'SMA_50' in df.columns:
            curr = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2]
            pct = ((curr - prev) / prev) * 100
            
            # Sicherstellen, dass RSI existiert
            rsi_val = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 50
            sma50_val = df['SMA_50'].iloc[-1]
            
            trend = "↗️" if curr > sma50_val else "↘️"
            
            overview_data.append({
                "Ticker": name,
                "Kurs": curr,
                "Change %": pct,
                "RSI": rsi_val,
                "Trend": trend
            })
        progress_bar.progress((i + 1) / len(TICKERS))
    
    progress_bar.empty()
    
    if overview_data:
        ov_df = pd.DataFrame(overview_data)
        
        st.dataframe(
            ov_df.style.format({"Kurs": "{:.2f} $", "Change %": "{:+.2f}%", "RSI": "{:.1f}"})
            .applymap(lambda x: 'color: #00ff00' if x > 0 else 'color: #ff4b4b', subset=['Change %']),
            use_container_width=True,
            height=600
        )
    else:
        st.warning("Keine Daten geladen.")

# --- TABS: EINZELWERTE ---
for i, (name, symbol) in enumerate(TICKERS.items()):
    with tabs[i+1]:
        df = get_data(symbol)
        
        if df.empty or 'SMA_50' not in df.columns:
            st.warning(f"Lade Daten für {name}... oder keine Daten verfügbar.")
            continue

        curr = df['Close'].iloc[-1]
        pivots = calculate_pivot_points(df)
        
        # Header Stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preis", f"{curr:.2f} $", f"{curr - df['Close'].iloc[-2]:.2f} $")
        c2.metric("Volumen", f"{df['Volume'].iloc[-1]/1000:.0f}K")
        c3.metric("RSI", f"{df['RSI_14'].iloc[-1]:.1f}")
        c4.metric("SMA 200", f"{df['SMA_200'].iloc[-1]:.2f} $")
        
        st.markdown("---")
        
        # CHEAT SHEET
        st.subheader(f"🧩 {name} Cheat Sheet")
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.markdown("**📉 Trend (SMAs)**")
            sma20 = df['SMA_20'].iloc[-1]
            sma50 = df['SMA_50'].iloc[-1]
            sma200 = df['SMA_200'].iloc[-1]
            
            st.write(f"SMA 20: {sma20:.2f} | {get_signal_color(curr, sma20)}")
            st.write(f"SMA 50: {sma50:.2f} | {get_signal_color(curr, sma50)}")
            st.write(f"SMA 200: {sma200:.2f} | {get_signal_color(curr, sma200)}")

        with col_b:
            st.markdown("**🌊 Momentum**")
            rsi = df['RSI_14'].iloc[-1]
            macd = df['MACD_12_26_9'].iloc[-1]
            macd_s = df['MACDs_12_26_9'].iloc[-1]
            
            st.write(f"RSI: {rsi:.1f} | {get_signal_color(rsi, 0, 'rsi')}")
            st.write(f"MACD: {macd:.3f} | {'🟢 Bull' if macd > macd_s else '🔴 Bear'}")

        with col_c:
            st.markdown("**🧱 Pivots (Support/Res)**")
            st.write(f"R1: {pivots['R1']:.2f} $")
            st.write(f"Pivot: {pivots['P']:.2f} $")
            st.write(f"S1: {pivots['S1']:.2f} $")

        # CHART
        st.subheader("Chart (1h)")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='orange'), name='SMA 50'))
        fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
        
        # PROGNOSE
        score = 0
        if rsi < 30: score+=1
        if rsi > 70: score-=1
        if curr > sma50: score+=1
        if macd > macd_s: score+=1
        
        signal_text = "HOLD ➡️"
        if score >= 2: signal_text = "STRONG BUY 🚀"
        elif score == 1: signal_text = "BUY ↗️"
        elif score <= -2: signal_text = "STRONG SELL 📉"
        elif score == -1: signal_text = "SELL ↘️"
        
        st.info(f"**Prognose für nächste Stunde:** {signal_text}")
