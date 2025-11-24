import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import time
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="MAG7 Pro Analyst V18 (NameError Fix)", layout="wide", page_icon="📈")

# --- CSS STYLING ---
st.markdown("""
<style>
    /* Allgemeine Styles für Metriken und Tabellen */
    .metric-card { background-color: #1e1e1e; padding: 15px; border-radius: 10px; border: 1px solid #333; margin-bottom: 10px; }
    .stDataFrame { font-size: 14px; }
    div[data-testid="stMetricValue"] { font-weight: bold; font-size: 1.2rem; } 

    /* Spezielles Styling für den optimierten Footer */
    .footer-box { padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid #333; }
    .footer-header { font-weight: bold; color: #4CAF50; }
    
    /* WICHTIG: Überschreibt das Streamlit-Button-CSS für die Zeitspannen-Buttons */
    div[data-testid="column"] > div[data-testid="stButton"] button {
        padding: 4px 8px; /* Kleinerer Padding */
        font-size: 0.8rem;
        background-color: #333333;
        border: 1px solid #555555;
        border-radius: 5px;
        color: white;
        width: 100%;
        margin-top: 5px;
        transition: background-color 0.1s, border-color 0.1s;
    }
    
    /* Highlight der aktiven Zeitspannen-Buttons (wird per Script gesetzt) */
    .active-time-button {
        background-color: #4CAF50 !important;
        border-color: #4CAF50 !important;
        font-weight: bold;
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
TICKER_SYMBOLS = list(TICKERS.values())
TICKER_NAMES = list(TICKERS.keys())

# --- TOOLTIP TEXTE ---
TOOLTIPS = {
    "ADX": "Average Directional Index: Misst die STÄRKE eines Trends. Werte über 25 zeigen einen klaren, verlässlichen Trend an (unabhängig von der Richtung).",
    "FIB_0618": "Fibonacci Golden Retracement: Ein psychologisch wichtiges Level (61.8%), oft die stärkste S/R-Linie nach einer großen Bewegung.",
    "PIVOT_P": "Pivot Point: Der zentrale Dreh- und Angelpunkt für den Handelstag. Bestimmt die allgemeine tägliche Tendenz.",
    "R1": "Resistance 1: Das wichtigste erwartete Preisniveau, bei dem der Aufwärtstrend gestoppt werden könnte.",
    "S1": "Support 1: Das wichtigste erwartete Preisniveau, bei dem Kaufinteresse den Kursverfall stoppen könnte.",
    "R2": "Resistance 2: Ein sekundäres, höheres Preisniveau, bei dem Verkaufsdruck erwartet wird.",
    "S2": "Support 2: Ein sekundäres, tieferes Preisniveau, bei dem starker Kaufdruck erwartet wird.",
    "SMA_50": "Simple Moving Average (50): Der gleitende Durchschnitt über die letzten 50 Perioden. Zeigt den mittelfristigen Trend an."
}

# --- DATENFUNKTIONEN ---

# NEU: Cache-Deklaration mit dynamischer TTL (Time-to-live)
def data_fetch_ttl():
    return 30 if st.session_state.get('auto_refresh_active', False) else 60

@st.cache_data(ttl=data_fetch_ttl())
def get_data(ticker, interval):
    try:
        if interval == '1d':
            period = "1y"
        else:
            period = "6mo"

        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval, prepost=True) 
        
        if df.empty: return pd.DataFrame()

        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert('Europe/Berlin')

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

@st.cache_data(ttl=3600) # Längeres Cache für Normalisierte Performance, da 1d Daten
def get_normalized_data(tickers):
    if not tickers:
        return pd.DataFrame()
    
    data = {}
    
    # KORREKTUR: Immer Tages-Intervall (1d) für Normalisierte Performance verwenden
    for symbol in tickers:
        try:
            df = yf.download(
                symbol, 
                period="6mo", 
                interval="1d", # Auf Tages-Intervall fixiert, um Konsistenz zu erhöhen
                prepost=False, 
                show_progress=False
            )['Close']
            
            if not df.empty and df.iloc[0] != 0:
                if df.index.tz is None:
                    df = df.tz_localize('UTC').tz_convert('Europe/Berlin')
                data[symbol] = df
        except Exception:
            pass
            
    if not data:
        return pd.DataFrame()
        
    df_comp = pd.DataFrame(data).dropna()
    
    if df_comp.empty:
        return pd.DataFrame()
        
    normalized = df_comp.div(df_comp.iloc[0]) * 100
    
    return normalized

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
    try:
        last_day_date = df.index[-2].date() 
        last_day_data = df[df.index.date == last_day_date]
        if last_day_data.empty: return {"P": 0, "R1": 0, "S1": 0, "R2": 0, "S2": 0}
        
        high = last_day_data['High'].max()
        low = last_day_data['Low'].min()
        close = last_day_data['Close'].iloc[-1]
    except IndexError:
        return {"P": 0, "R1": 0, "S1": 0, "R2": 0, "S2": 0}
    
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
    if df.index.inferred_freq in ['1d', 'D']:
         return pd.DataFrame()
    heatmap_df = df.tail(200).copy() 
    heatmap_df['Hourly_Change'] = ((heatmap_df['Close'] - heatmap_df['Open']) / heatmap_df['Open']) * 100
    heatmap_df['Datum'] = heatmap_df.index.strftime("%Y-%m-%d") 
    heatmap_df['Uhrzeit'] = heatmap_df.index.strftime("%H:00")
    pivot = heatmap_df.pivot_table(index='Datum', columns='Uhrzeit', values='Hourly_Change')
    pivot = pivot.sort_index(ascending=False)
    
    # Filterung ab 07:00 CET, um die frühe Vorbörse zu inkludieren.
    valid_cols = [c for c in pivot.columns if "07:00" <= c <= "23:00"] 
    pivot = pivot[valid_cols]
    return pivot

def analyze_vertical_patterns(pivot):
    # DIESE FUNKTION WAR WAHRSCHEINLICH AUS VERSEHEN GELÖSCHT
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
    key='interval_select',
    help="Wechsle zwischen Stunden- und Tagesansicht. Die Heatmap ist nur bei Stundenansicht verfügbar."
)

# Setze den Session State, der die TTL der Cache-Funktion steuert
if 'auto_refresh_active' not in st.session_state:
    st.session_state['auto_refresh_active'] = False

auto_refresh = st.sidebar.checkbox("Live Auto-Update (60s)", value=st.session_state['auto_refresh_active'], key='auto_refresh_checkbox')

# Speichere den Zustand im Session State
st.session_state['auto_refresh_active'] = auto_refresh

if auto_refresh:
    time.sleep(60)
    st.rerun()

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()


# --- HAUPTBEREICH ---
st.title(f"💎 MAG7 Trading Dashboard (V18 - {interval} Ansicht)")

tabs = st.tabs(["🚀 SIGNALS & MARKET"] + TICKER_NAMES)

# === TAB 0: SIGNAL ÜBERSICHT & VERGLEICH ===
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
            
            overview_data.append({"Asset": name, "SYMBOL": sym, "SIGNAL": signal, "Preis (€/$)": curr, "Change %": change, "RSI": rsi})
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
    
    st.markdown("---")
    
    st.subheader("📈 Normalisierte Performance im Vergleich (6 Monate / Täglich)")
    
    selection_col, range_col = st.columns([3, 1])
    
    with selection_col:
        selected_names = st.multiselect(
            "Wähle Assets für den Vergleich", 
            options=TICKER_NAMES, 
            default=["NVIDIA", "Microsoft", "Nasdaq"]
        )
    
    selected_symbols = [TICKERS[name] for name in selected_names if name in TICKERS]
    
    if selected_symbols:
        comp_df = get_normalized_data(selected_symbols)
        
        if not comp_df.empty:
            fig_comp = go.Figure()
            
            for symbol in selected_symbols:
                name = [k for k, v in TICKERS.items() if v == symbol][0]
                if symbol in comp_df.columns:
                    fig_comp.add_trace(go.Scatter(x=comp_df.index, y=comp_df[symbol], mode='lines', name=name))
            
            fig_comp.update_layout(
                title='Normalisierte Performance (Start = 100)',
                yaxis_title='Performance (%)',
                legend_title='Asset',
                template="plotly_dark",
                height=500
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.warning("Keine vergleichbaren Daten für die ausgewählten Assets oder das gewählte Intervall verfügbar. (Prüfe die Tickerauswahl und das Intervall)")
    else:
        st.info("Bitte wähle mindestens ein Asset für den Vergleich aus.")


# === TABS: EINZELWERTE MIT ZEITSPANNE ===
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
        
        c3.metric("Resistance (R1)", f"{pivots['R1']:.2f}", help=TOOLTIPS['R1'])
        c4.metric("Support (S1)", f"{pivots['S1']:.2f}", help=TOOLTIPS['S1'])

        st.markdown("---")
        
        # NEU: ZEITSPANNEN-BUTTONS
        range_options = {
            "3M": 90, 
            "1M": 30, 
            "1W": 7, 
            "1D": 1
        }
        
        # Session State auf einen gültigen Key initialisieren
        if f'range_{symbol}' not in st.session_state:
            st.session_state[f'range_{symbol}'] = '3M'
        
        st.subheader(f"📊 Chart Analyse ({interval})")
        
        # Buttons in einer Zeile anzeigen (4 Buttons + 1 Label)
        button_cols = st.columns(len(range_options) + 1)
        
        selected_range_key = st.session_state[f'range_{symbol}']
        
        with button_cols[0]:
            st.markdown("Zeitspanne:")

        # Buttons erstellen
        for idx, (label, days) in enumerate(range_options.items()):
            with button_cols[idx + 1]:
                if st.button(label, key=f"btn_{symbol}_{label}", use_container_width=True):
                    if st.session_state[f'range_{symbol}'] != label:
                        st.session_state[f'range_{symbol}'] = label
                        st.rerun()

        # Manuelle CSS-Hervorhebung für den aktiven Button nach dem Rerun
        st.markdown(f"""
            <script>
                var active_btn = parent.document.querySelector('[data-testid="stButton"] button[key="btn_{symbol}_{selected_range_key}"]');
                if (active_btn) {{
                    active_btn.classList.add('active-time-button');
                }}
            </script>
            """, unsafe_allow_html=True)
            
        st.markdown("---") # Trennung zwischen Buttons und Chart
        
        # Sicherstellen, dass der Key existiert
        try:
            days_to_show = range_options[selected_range_key]
        except KeyError:
            st.session_state[f'range_{symbol}'] = '3M'
            days_to_show = range_options['3M']
        
        start_date = df.index[-1].date() - timedelta(days=days_to_show)
        df_display = df[df.index.date >= start_date]

        # --- CHART ---
        
        fig = go.Figure()
        
        fig.add_trace(go.Candlestick(x=df_display.index, open=df_display['Open'], high=df_display['High'], low=df_display['Low'], close=df_display['Close'], name='Kurs'))
        
        if 'VWAP_D' in df_display.columns:
            fig.add_trace(go.Scatter(x=df_display.index, y=df_display['VWAP_D'], line=dict(color='violet', width=2, dash='dot'), name='VWAP'))
        if 'SMA_50' in df_display.columns:
            fig.add_trace(go.Scatter(x=df_display.index, y=df_display['SMA_50'], line=dict(color='orange', width=1), name='SMA 50'))

        fig.add_hline(y=fibs['0.618'], line_dash="dash", line_color="green", annotation_text="Fib 0.618", annotation_position="bottom right")

        fig.update_layout(height=500, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        
        # --- MUSTER-ERKENNUNG / HEATMAP --- 
        if interval != '1d':
            st.subheader("⏰ Muster-Erkennung (07:00 - 23:00 Uhr CET)")
            heatmap_df = get_hourly_heatmap_data(df)
            
            if not heatmap_df.empty:
                # FUNKTION AUFGERUFEN
                patterns = analyze_vertical_patterns(heatmap_df) 
                if patterns:
                    st.info("💡 **Erkannte Muster:** " + " | ".join(patterns))
                
                st.dataframe(heatmap_df.style.background_gradient(cmap='RdYlGn', vmin=-1.0, vmax=1.0).format("{:+.2f}%").highlight_null(color='#1e1e1e'), use_container_width=True, height=350)
            else:
                st.info("Nicht genügend Daten für das Heatmap-Muster im gewählten Intervall vorhanden.")
        else:
            st.info("Heatmap ist nur für Stunden-Intervalle (30m / 60m) verfügbar.")
        
        st.markdown("---")

        # --- KORRIGIERTES CHEAT SHEET BEREICH ---
        
        st.header("🎯 Strategie-Cheat Sheet")
        
        adx_val = df['ADX_14'].iloc[-1] if 'ADX_14' in df.columns else 0
        rsi_val = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 50
        adx_status = "Starker Trend 📈" if adx_val >= 25 else "Schwacher/Seitwärtstrend 🟡"
        adx_color = "green-status" if adx_val >= 25 else "yellow-status"
        trend_status = '🟢 Bullish' if curr > df['SMA_50'].iloc[-1] else '🔴 Bearish'
        
        col_adx, col_rsi, col_trend = st.columns(3)
        
        with col_adx:
            st.markdown(f'<div class="footer-box">', unsafe_allow_html=True)
            st.markdown(f'<div class="footer-header">TREND STÄRKE (ADX)</div>', unsafe_allow_html=True)
            st.metric(label="ADX (14)", value=f"{adx_val:.2f}", help=TOOLTIPS['ADX'])
            st.markdown(f'<span class="{adx_color}">{adx_status}</span>', unsafe_allow_html=True)
            st.markdown(f'</div>', unsafe_allow_html=True)

        with col_rsi:
            st.markdown(f'<div class="footer-box">', unsafe_allow_html=True)
            st.markdown(f'<div class="footer-header">MOMENTUM (RSI)</div>', unsafe_allow_html=True)
            st.metric(label="RSI (14)", value=f"{rsi_val:.2f}", delta=("ÜBERKAUFT" if rsi_val > 70 else "ÜBERVERKAUFT" if rsi_val < 30 else None))
            st.markdown(f'</div>', unsafe_allow_html=True)

        with col_trend:
            st.markdown(f'<div class="footer-box">', unsafe_allow_html=True)
            st.markdown(f'<div class="footer-header">LANGFR. TREND (SMA)</div>', unsafe_allow_html=True)
            st.metric("SMA 50", f"{df['SMA_50'].iloc[-1] if 'SMA_50' in df.columns else 'N/A':.2f}", help=TOOLTIPS['SMA_50'])
            st.write(f"Status: {trend_status}")
            st.markdown(f'</div>', unsafe_allow_html=True)

        st.markdown("---")

        st.subheader("S/R-Level und wichtige Zonen")
        
        c_pivots, c_fib, c_vwa = st.columns(3)

        with c_pivots:
            st.markdown(f'<div class="footer-box">', unsafe_allow_html=True)
            st.markdown(f'<div class="footer-header">PIVOT PUNKTE (Täglich)</div>', unsafe_allow_html=True)
            
            st.metric(label="R2 (Widerst.) 🔴", value=f"{pivots['R2']:.2f}", help=TOOLTIPS['R2'])
            st.metric(label="R1 (Widerst.) 🔴", value=f"{pivots['R1']:.2f}", help=TOOLTIPS['R1'])
            st.metric(label="Pivot (P)", value=f"{pivots['P']:.2f}", help=TOOLTIPS['PIVOT_P'])
            st.metric(label="S1 (Unterst.) 🟢", value=f"{pivots['S1']:.2f}", help=TOOLTIPS['S1'])
            st.metric(label="S2 (Unterst.) 🟢", value=f"{pivots['S2']:.2f}", help=TOOLTIPS['S2'])
            
            st.markdown(f'</div>', unsafe_allow_html=True)

        with c_fib:
            st.markdown(f'<div class="footer-box">', unsafe_allow_html=True)
            st.markdown(f'<div class="footer-header">FIBONACCI & VWAP</div>', unsafe_allow_html=True)
            
            st.metric(label="Fib 0.618", value=f"{fibs['0.618']:.2f}", help=TOOLTIPS['FIB_0618'])
            
            st.write(f"VWAP: **{df['VWAP_D'].iloc[-1] if 'VWAP_D' in df.columns else 'N/A':.2f}**")
            st.write(f"SMA 200: **{df['SMA_200'].iloc[-1] if 'SMA_200' in df.columns else 'N/A':.2f}**")
            st.markdown(f'</div>', unsafe_allow_html=True)
