import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import datetime

# --- Konfiguration ---
st.set_page_config(page_title="MAG7 & AMD Analyst", layout="wide")

# Ticker Liste
TICKERS = {
    "AMD": "AMD",
    "NVIDIA": "NVDA",
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Google": "GOOG",
    "Amazon": "AMZN",
    "Meta": "META",
    "Tesla": "TSLA",
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "VIX": "^VIX"
}

# --- Funktionen ---

def get_data(ticker_symbol):
    # Holt Daten der letzten 7 Tage im 1-Stunden-Intervall
    # (reicht für 'letzte 2 Wochen' Ansicht, yfinance limitiert 1h oft auf 730 Tage, aber 1mo ist sicher)
    data = yf.download(ticker_symbol, period="1mo", interval="1h", progress=False)
    
    # Bereinigung für Multi-Index Spalten (Problem bei neueren yfinance Versionen)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    return data

def calculate_cheat_sheet(df):
    # Wir nehmen die letzte abgeschlossene Kerze für die Berechnung
    last_close = df.iloc[-1]['Close']
    
    # 1. Moving Averages
    sma20 = df.ta.sma(length=20).iloc[-1]
    sma50 = df.ta.sma(length=50).iloc[-1]
    sma200 = df.ta.sma(length=200).iloc[-1]
    
    # 2. Indikatoren
    rsi = df.ta.rsi(length=14).iloc[-1]
    macd = df.ta.macd()
    macd_val = macd['MACD_12_26_9'].iloc[-1]
    macd_signal = macd['MACDs_12_26_9'].iloc[-1]
    
    # 3. Pivot Points (Fibonacci oder Classic) - Basis: Letzter voller Tag
    # Da wir im 1h Chart sind, approximieren wir Pivot Points basierend auf den High/Lows der letzten 24h
    last_24h = df.tail(8) # ca. ein Handelstag
    high = last_24h['High'].max()
    low = last_24h['Low'].min()
    close = last_24h['Close'].iloc[-1]
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    
    return {
        "Price": last_close,
        "RSI": rsi,
        "MACD": "Bullish" if macd_val > macd_signal else "Bearish",
        "SMA20": sma20,
        "SMA50": sma50,
        "SMA200": sma200,
        "Pivot": pivot,
        "R1": r1,
        "S1": s1,
        "Trend": "Steigend" if last_close > sma50 else "Fallend"
    }

def predict_next_hour(metrics):
    # Einfache Logik für die "Nächste Stunde" Einschätzung
    score = 0
    if metrics['RSI'] < 30: score += 1 # Überverkauft -> könnte steigen
    if metrics['RSI'] > 70: score -= 1 # Überkauft -> könnte fallen
    if metrics['MACD'] == "Bullish": score += 1
    if metrics['Trend'] == "Steigend": score += 1
    if metrics['Price'] > metrics['Pivot']: score += 0.5
    
    if score >= 2: return "STARK STEIGEND 🚀"
    elif score >= 1: return "LEICHT STEIGEND ↗️"
    elif score <= -2: return "STARK FALLEND 📉"
    elif score <= -1: return "LEICHT FALLEND ↘️"
    else: return "NEUTRAL ➡️"

# --- Main App ---

st.title("📊 MAG7 & AMD Master-Analyst")

# Sidebar Auswahl
selected_ticker_name = st.sidebar.selectbox("Wähle Asset", list(TICKERS.keys()))
symbol = TICKERS[selected_ticker_name]

if st.sidebar.button("Daten abrufen / Aktualisieren"):
    with st.spinner(f'Lade Daten für {selected_ticker_name}...'):
        try:
            df = get_data(symbol)
            
            # Aktueller Status
            current_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            delta = current_price - prev_price
            
            # Metriken berechnen
            metrics = calculate_cheat_sheet(df)
            prediction = predict_next_hour(metrics)
            
            # --- OBERER BEREICH: Übersicht & Prognose ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Aktueller Preis", f"{current_price:.2f} $", f"{delta:.2f} $")
            col2.metric("Trend (SMA50)", metrics['Trend'])
            col3.info(f"Prognose nächste Stunde:\n\n**{prediction}**")
            
            st.markdown("---")
            
            # --- CHEAT SHEET BEREICH ---
            st.subheader(f"🧩 {selected_ticker_name} Cheat Sheet")
            
            cs_col1, cs_col2, cs_col3 = st.columns(3)
            
            with cs_col1:
                st.markdown("**Gleitende Durchschnitte**")
                st.write(f"SMA 20: {metrics['SMA20']:.2f} $")
                st.write(f"SMA 50: {metrics['SMA50']:.2f} $")
                st.write(f"SMA 200: {metrics['SMA200']:.2f} $")
                
            with cs_col2:
                st.markdown("**Technische Indikatoren**")
                st.write(f"RSI (14): {metrics['RSI']:.2f}")
                st.write(f"MACD: {metrics['MACD']}")
                
            with cs_col3:
                st.markdown("**Support & Resistance (Pivot)**")
                st.write(f"Res 1: {metrics['R1']:.2f} $")
                st.write(f"Pivot: {metrics['Pivot']:.2f} $")
                st.write(f"Sup 1: {metrics['S1']:.2f} $")
            
            # Signal Interpretation Visualisierung
            st.progress((metrics['RSI']) / 100, text=f"RSI Stärke: {metrics['RSI']:.0f}/100")

            st.markdown("---")

            # --- HISTORISCHE DATEN (Jede Stunde) ---
            st.subheader("📅 Historie: Jede Stunde (Letzte 2 Wochen)")
            
            # Daten für Chart aufbereiten (letzte 14 Tage)
            last_2_weeks = df.tail(14 * 10) # Grob geschätzt Handelsstunden
            
            st.line_chart(last_2_weeks['Close'])
            
            # Detaillierte Tabelle anzeigen (neueste zuerst)
            with st.expander("Detaillierte Datentabelle ansehen"):
                display_df = last_2_weeks[['Open', 'High', 'Low', 'Close', 'Volume']].sort_index(ascending=False)
                st.dataframe(display_df.style.format("{:.2f}"))

        except Exception as e:
            st.error(f"Fehler beim Abruf: {e}")
else:
    st.info("Klicke links auf 'Daten abrufen', um die Analyse zu starten.")
