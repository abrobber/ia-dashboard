import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import ta
from datetime import datetime

# --- Configuración de la App ---
st.set_page_config(layout="wide", page_title="📊 Bitácora Twelve Data")
st.title("📈 Bitácora Visual: Momentum + Volumen")

# --- API Key ---
API_KEY = st.secrets["api"]["twelve_data_key"]

# --- Selección de símbolo e intervalo ---
symbols = ['BTC/USD', 'ETH/USD', 'AAPL', 'TSLA', 'EUR/USD']
intervals = ['1min', '5min', '15min', '30min', '1h']

col1, col2 = st.columns(2)
symbol = col1.selectbox("Símbolo", options=symbols, index=0)
interval = col2.selectbox("Intervalo", options=intervals, index=0)

# --- Función para obtener datos de Twelve Data ---
@st.cache_data(ttl=60)
def get_candles(symbol, interval, outputsize=100):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": API_KEY
    }
    r = requests.get(url, params=params)
    data = r.json()
    if "values" not in data:
        st.warning(data.get("message", "Error al obtener datos"))
        return pd.DataFrame()
    df = pd.DataFrame(data["values"])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values("datetime")
    df = df.astype({
        "open": float, "high": float, "low": float,
        "close": float, "volume": float
    })
    return df

# --- Análisis técnico y señales ---
def analizar(df):
    df['RSI'] = ta.momentum.RSIIndicator(df['close']).rsi()
    df['ROC'] = ta.momentum.ROCIndicator(df['close']).roc()
    df['vol_mean'] = df['volume'].rolling(window=20).mean()
    df['vol_rel'] = df['volume'] / df['vol_mean']
    df['Entrada'] = (
        (df['RSI'] > 55) &
        (df['ROC'] > 0) &
        (df['vol_rel'] > 1.5)
    )
    return df

# --- Visualización ---
df = get_candles(symbol, interval)
if not df.empty:
    df = analizar(df)
    ultima = df.iloc[-1]

    st.subheader(f"{symbol} — Última vela: {ultima['datetime'].strftime('%Y-%m-%d %H:%M')}")

    fig = go.Figure(data=[
        go.Candlestick(
            x=df['datetime'],
            open=df['open'], high=df['high'],
            low=df['low'], close=df['close'],
            name='Precio'),
        go.Bar(
            x=df['datetime'], y=df['volume'],
            name='Volumen', marker_color='lightblue', yaxis='y2')
    ])
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        yaxis=dict(title='Precio'),
        yaxis2=dict(title='Volumen', overlaying='y', side='right'),
        height=600
    )
    st.plotly_chart(fig, use_container_width=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("RSI", f"{ultima['RSI']:.2f}")
    col2.metric("ROC", f"{ultima['ROC']:.2f}%")
    col3.metric("Vol Relativo", f"{ultima['vol_rel']:.2f}x")

    if ultima['Entrada']:
        st.success("🚀 Entrada detectada: Momentum + Volumen confirmados.")
    else:
        st.info("Sin condiciones activas en esta vela.")
