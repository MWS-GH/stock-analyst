import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import time
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="MAG7 & AMD Pro Analyst", layout="wide", page_icon="📈")

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
    .stDataFrame { font-size: 14px; }
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

@st.cache_data(ttl=60) # Cache Daten für 60 Sekunden
def get_data(ticker):
    try:
        # Wir nutzen history() für stabilere Daten
        stock = yf.Ticker(ticker)
        # Period 6mo um genug Daten für SMA200 zu haben, Interval 60m für Stunden-Trading
        df = stock.history(period="6mo", interval="60m")
        
        if df.empty: return pd.DataFrame()

        # Zeitzone entfernen (verhindert Plotly/Pandas Konflikte)
        df.index = df.index.tz_localize(None)

        # --- INDIKATOREN BERECHNEN (Pandas TA) ---
        # 1. Standard Indikatoren
        if len(df) > 14:
            df.ta.rsi(length=14, append=True)
            df.ta.macd(append=True)
            df.ta.atr(length=14, append=True) # ATR (Volatilität)
        
        # 2. Gleitende Durchschnitte (Checks falls Aktie zu neu)
        if len(df) > 20: df.ta.sma(length=20, append=True)
        if len(df) > 50: df.ta.sma(length=50, append=True)
        if len(df) > 200: df.ta.sma(length=200, append=True)
        
        # 3. VWAP (Volume Weighted Average Price)
        # Benötigt High, Low, Close, Volume -> haben wir
        try:
            df.ta.vwap(append=True)
        except:
            pass # Falls Berechnung fehlschlägt (z.B. Index ohne Volumen)

        return df
    except Exception as e:
        st.error(f"Fehler bei {ticker}: {e}")
        return pd.DataFrame()

def calculate_pivot_points(df):
    if df.empty: return {"P": 0, "R1": 0, "S1": 0, "R2": 0, "S2": 0}
    
    # Wir nehmen die letzten 8 Stunden (ca. 1 Handelstag) für Intraday Pivots
    recent = df.tail(8)
    high = recent['High'].max()
    low = recent['Low'].min()
    close = recent['Close'].iloc[-1]
    
    p = (high + low + close) / 3
    r1 = (2 * p) - low
    s1 = (2 * p) - high
    r2 = p + (high - low)
    s2 = p - (high - low)
    
    return {"P": p, "R1": r1, "S1": s1, "R2": r2, "S2": s2}

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
st.sidebar.header("⚙️ Steuerung")
auto_refresh = st.sidebar.checkbox("Live Auto-Update (60s)", value=False)
st.sidebar.markdown("---")
st.sidebar.caption(f"Update: {datetime.now().strftime('%H:%M:%S')}")

if auto_refresh:
    time.sleep(60)
    st.rerun()

if st.sidebar.button("Manuell Refresh"):
    st.rerun()

# --- HAUPTBEREICH ---
st.title("🚀 MAG7 & Chips Trading Hub")

# Tabs erstellen
tabs = st.tabs(["📊 Gesamtübersicht"] + list(TICKERS.keys()))

# === TAB 0: GESAMTÜBERSICHT ===
with tabs[0]:
    st.subheader("Marktstimmung (Live)")
    
    # 1. Übersichtstabelle
    overview_data = []
    
    # Ladebalken
    progress = st.progress(0)
    
    # Daten für Matrix sammeln
    all_close_prices = {} 

    for i, (name, sym) in enumerate(TICKERS.items()):
        df = get_data(sym)
        
        if not df.empty and 'SMA_50' in df.columns:
            # Für Matrix speichern
            all_close_prices[name] = df['Close']
            
            # Werte für Tabelle
            curr = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2]
            pct = ((curr - prev) / prev) * 100
            rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 50
            sma50 = df['SMA_50'].iloc[-1]
            
            trend_icon = "↗️" if curr > sma50 else "↘️"
            
            overview_data.append({
                "Ticker": name,
                "Preis": curr,
                "Change %": pct,
                "RSI (1h)": rsi,
                "Trend": trend_icon
            })
        progress.progress((i + 1) / len(TICKERS))
    
    progress.empty()
    
    # Tabelle anzeigen
    if overview_data:
        ov_df = pd.DataFrame(overview_data)
        st.dataframe(
            ov_df.style.format({"Preis": "{:.2f} $", "Change %": "{:+.2f}%", "RSI (1h)": "{:.1f}"})
            .applymap(lambda x: 'color: #00ff00' if x > 0 else 'color: #ff4b4b', subset=['Change %']),
            use_container_width=True
        )
    
    st.markdown("---")
    
    # 2. Korrelations-Matrix
    st.subheader("🔗 Korrelations-Matrix (Heatmap)")
    st.info("Zeigt, wie stark sich Aktien synchron bewegen (1.0 = Identisch, -1.0 = Gegensätzlich)")
    
    if st.button("Matrix berechnen"):
        if all_close_prices:
            corr_df = pd.DataFrame(all_close_prices)
            # Nur gemeinsame Datenpunkte nutzen
            corr_matrix = corr_df.dropna().corr()
            
            st.dataframe(
                corr_matrix.style.background_gradient(cmap="RdYlGn", axis=None).format("{:.2f}"),
                use_container_width=True,
                height=500
            )

# === TABS: EINZELWERTE ===
for i, (name, symbol) in enumerate(TICKERS.items()):
    with tabs[i+1]:
        df = get_data(symbol)
        
        # Sicherheitscheck
        if df.empty or 'SMA_50' not in df.columns:
            st.warning("Lade Daten... (oder nicht genügend Historie)")
            continue

        # Letzte Werte
        curr = df['Close'].iloc[-1]
        pivots = calculate_pivot_points(df)
        
        # Header Stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preis", f"{curr:.2f} $", f"{curr - df['Close'].iloc[-2]:.2f} $")
        c2.metric("Volumen", f"{df['Volume'].iloc[-1]/1e6:.2f}M")
        c3.metric("RSI (1h)", f"{df['RSI_14'].iloc[-1]:.1f}")
        
        # ATR Metrik (Volatilität)
        atr_val = df['ATRr_14'].iloc[-1] if 'ATRr_14' in df.columns else 0
        c4.metric("ATR (Range)", f"{atr_val:.2f} $")
        
        st.markdown("---")
        
        # --- CHEAT SHEET ---
        st.subheader(f"🧩 {name} Strategie-Board")
        cs1, cs2, cs3 = st.columns(3)
        
        with cs1:
            st.markdown("**📈 Trend**")
            sma20 = df['SMA_20'].iloc[-1] if 'SMA_20' in df.columns else 0
            sma50 = df['SMA_50'].iloc[-1]
            sma200 = df['SMA_200'].iloc[-1] if 'SMA_200' in df.columns else 0
            
            st.write(f"SMA 20: {sma20:.2f} | {get_signal_color(curr, sma20)}")
            st.write(f"SMA 50: {sma50:.2f} | {get_signal_color(curr, sma50)}")
            st.write(f"SMA 200: {sma200:.2f} | {get_signal_color(curr, sma200)}")

        with cs2:
            st.markdown("**🌊 Momentum**")
            rsi = df['RSI_14'].iloc[-1]
            macd = df['MACD_12_26_9'].iloc[-1]
            macd_s = df['MACDs_12_26_9'].iloc[-1]
            
            st.write(f"RSI: {rsi:.1f} | {get_signal_color(rsi, 0, 'rsi')}")
            st.write(f"MACD: {macd:.3f} | {'🟢 Bull' if macd > macd_s else '🔴 Bear'}")
            st.progress(rsi/100)

        with cs3:
            st.markdown("**⚡ Profi-Indikatoren**")
            # VWAP Check
            vwap_val = df['VWAP_D'].iloc[-1] if 'VWAP_D' in df.columns else 0
            vwap_col = "🟢 BULLISH" if curr > vwap_val else "🔴 BEARISH"
            
            st.write(f"VWAP: {vwap_val:.2f} $ | {vwap_col}")
            st.write(f"Pivot: {pivots['P']:.2f} $")
            st.caption(f"Erwartete Range (ATR): +/- {atr_val:.2f}$")

        # --- CHART ---
        st.subheader("📊 Chart (1h) mit VWAP")
        
        fig = go.Figure()
        
        # Candles
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name='Price'
        ))
        
        # SMAs
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='orange', width=1), name='SMA 50'))
        if 'SMA_200' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='blue', width=1), name='SMA 200'))
        
        # VWAP (Lila Linie)
        if 'VWAP_D' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['VWAP_D'], line=dict(color='violet', width=2, dash='dot'), name='VWAP'))

        fig.update_layout(height=500, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # --- FAZIT ---
        score = 0
        if rsi < 30: score+=1
        if rsi > 70: score-=1
        if curr > sma50: score+=1
        if macd > macd_s: score+=1
        if vwap_val > 0 and curr > vwap_val: score+=1 # VWAP Bonus
        
        sentiment = "HOLD ➡️"
        if score >= 3: sentiment = "STRONG BUY 🚀"
        elif score >= 1: sentiment = "BUY ↗️"
        elif score <= -2: sentiment = "STRONG SELL 📉"
        elif score <= -1: sentiment = "SELL ↘️"
        
        st.info(f"**Algo-Fazit:** {sentiment} (Score: {score})")
