import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import ta
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from plotly.subplots import make_subplots

# Refresca cada 60 segundos (60,000 ms)
st_autorefresh(interval=60 * 1000, key="data_refresh")

# --- Configuración de la App ---
st.set_page_config(layout="wide", page_title="📊 Bitácora Twelve Data")
st.title("📈 Bitácora Visual: Momentum + Volumen")

# --- API Key ---
#API_KEY = st.secrets["api"]["twelve_data_key"]
API_KEY = "7a8323602dee4ac382196181cc32a8a7"

# --- Selección de símbolo e intervalo ---
symbols = ['USD/JPY', 'BTC/USD', 'ETH/USD', 'AAPL', 'TSLA', 'EUR/USD']
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
    try:
        response = requests.get(url, params=params)
        data = response.json()

        # Validación de error de respuesta
        if "status" in data and data["status"] == "error":
            st.error(f"🚫 API Error: {data.get('message', 'Desconocido')}")
            return pd.DataFrame()

        if "values" not in data:
            st.warning("⚠️ No se recibieron datos. Verifica el símbolo, intervalo o tu API Key.")
            return pd.DataFrame()

        df = pd.DataFrame(data["values"])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values("datetime")

        # Validación antes de conversión
        campos = ["open", "high", "low", "close", "volume"]
        for campo in campos:
            if campo not in df.columns:
                st.error(f"❌ Faltan datos: campo '{campo}' no encontrado en la respuesta.")
                return pd.DataFrame()

        df[campos] = df[campos].astype(float)
        return df

    except Exception as e:
        st.exception(f"🧨 Error inesperado: {e}")
        return pd.DataFrame()


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

    # Asegurar columnas para señales visuales
    df['ColorEntrada'] = df.apply(
        lambda row: 'verde' if row['close'] > row['open'] else 'roja',
        axis=1
    )

    def clasificar_entrada(row):
        if row['RSI'] > 65 and row['ROC'] > 1:
            return "Momentum fuerte"
        elif row['vol_rel'] > 2 and row['close'] > row['open']:
            return "Breakout con volumen"
        elif row['RSI'] < 60 and row['ROC'] > 0:
            return "Anticipada"
        else:
            return "Otra"

    df['TipoEntrada'] = df.apply(clasificar_entrada, axis=1)
    df['Accion'] = df['ColorEntrada'].apply(lambda c: 'Comprar' if c == 'verde' else 'Vender')
    return df


# --- Visualización ---
df = get_candles(symbol, interval)
if not df.empty:
    df = analizar(df)
    ultima = df.iloc[-1]

    st.subheader(f"{symbol} — Última vela: {ultima['datetime'].strftime('%Y-%m-%d %H:%M')}")

    # Crear subgráficos
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.7, 0.3], vertical_spacing=0.05,
        subplot_titles=("Precio", "Volumen")
    )

    # Gráfico de velas
    fig.add_trace(
        go.Candlestick(
            x=df['datetime'],
            open=df['open'], high=df['high'],
            low=df['low'], close=df['close'],
            name='Precio'
        ),
        row=1, col=1
    )

    # Gráfico de volumen
    fig.add_trace(
        go.Bar(
            x=df['datetime'], y=df['volume'],
            name='Volumen', marker_color='lightblue'
        ),
        row=2, col=1
    )

    # Marcar entradas si existen
    entradas = df[df['Entrada']]
    if not entradas.empty:
        for _, row in entradas.iterrows():
            color = 'limegreen' if row['ColorEntrada'] == 'verde' else 'red'
            fig.add_trace(go.Scatter(
                x=[row['datetime']],
                y=[row['high'] * 1.01],
                mode='markers',
                marker=dict(size=14, color=color, symbol='triangle-up'),
                name=f"Entrada: {row['Accion']}",
                text=f"{row['TipoEntrada']} ({row['Accion']})",
                hoverinfo='text'
            ), row=1, col=1)

    # Layout final
    fig.update_layout(
        height=700,
        showlegend=False,
        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(fig, use_container_width=True)

    # Métricas
    col1, col2, col3 = st.columns(3)
    col1.metric("RSI", f"{ultima['RSI']:.2f}")
    col2.metric("ROC", f"{ultima['ROC']:.2f}%")
    col3.metric("Vol Relativo", f"{ultima['vol_rel']:.2f}x")

    # Señal actual
    if ultima['Entrada']:
        hora = ultima['datetime'].strftime('%Y-%m-%d %H:%M')
        st.success(f"🚀 Entrada {ultima['Accion']} detectada a las {hora}.")
    else:
        st.info("Sin condiciones activas en esta vela.")



