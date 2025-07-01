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

def calcular_perfil_volumen(df, precision=0.5):
    # Redondeamos precios al múltiplo de "precision"
    df['nivel'] = (df['close'] / precision).round(0) * precision
    vol_por_nivel = df.groupby('nivel')['volume'].sum().sort_values(ascending=False)
    
    # POC
    poc = vol_por_nivel.idxmax()
    
    # Área de valor (70%)
    total_vol = vol_por_nivel.sum()
    vol_acum = vol_por_nivel.cumsum()
    niveles_area_valor = vol_acum[vol_acum <= total_vol * 0.7].index

    val = min(niveles_area_valor)
    vah = max(niveles_area_valor)

    return poc, val, vah, vol_por_nivel

def perfil_volumen(df, precision=0.5):
    df['nivel'] = (df['close'] / precision).round(0) * precision
    volumen_por_precio = df.groupby('nivel')['volume'].sum()
    volumen_por_precio = volumen_por_precio.sort_index(ascending=True)

    total = volumen_por_precio.sum()
    sorted_vols = volumen_por_precio.sort_values(ascending=False)
    poc = sorted_vols.idxmax()
    vol_acum = sorted_vols.cumsum()
    niveles_70 = vol_acum[vol_acum <= total * 0.7].index
    val, vah = min(niveles_70), max(niveles_70)

    return volumen_por_precio, poc, val, vah


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

    poc, val, vah, _ = calcular_perfil_volumen(df)
    # Añadir líneas horizontales
    fig.add_hline(y=poc, line_dash="dash", line_color="orange", annotation_text="POC", row=1, col=1)
    fig.add_hline(y=val, line_dash="dot", line_color="gray", annotation_text="VAL", row=1, col=1)
    fig.add_hline(y=vah, line_dash="dot", line_color="gray", annotation_text="VAH", row=1, col=1)


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

    #st.plotly_chart(fig, use_container_width=True)
    st.plotly_chart(vol_fig, use_container_width=True)

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


    # Calcular perfil
    precision = 0.5  # Ajustable según resolución de precios
    vol_profile, poc, val, vah = perfil_volumen(df)

    import plotly.express as px

    # Convertir volumen por precio a DataFrame
    vp_df = vol_profile.reset_index()
    vp_df.columns = ['nivel', 'volume']
    
    # Crear gráfico lateral
    vol_fig = go.Figure()
    vol_fig.add_trace(go.Bar(
        x=vp_df['volume'],
        y=vp_df['nivel'],
        orientation='h',
        marker=dict(color=vp_df['volume'], colorscale='Blues'),
        showlegend=False
    ))
    
    vol_fig.update_layout(
        height=700,
        title="Perfil de Volumen por Precio",
        yaxis_title="Precio",
        xaxis_title="Volumen",
        template="plotly_white",
        margin=dict(t=40, l=80, r=20, b=40),
        yaxis=dict(autorange="reversed")  # para que los precios altos estén arriba
    )

    
    # Añadir líneas horizontales en gráfico de velas
    fig.add_hline(y=poc, line_dash="dash", line_color="orange", annotation_text="POC", row=1, col=1)
    fig.add_hline(y=val, line_dash="dot", line_color="gray", annotation_text="VAL", row=1, col=1)
    fig.add_hline(y=vah, line_dash="dot", line_color="gray", annotation_text="VAH", row=1, col=1)
    
    # Añadir gráfico lateral de volumen horizontal (estilo VA-MOD)
    from plotly import graph_objects as go
    
    # Solo para el rango visible
    max_vol = vol_profile.max()
    for nivel, vol in vol_profile.items():
        fig.add_shape(
            type="rect",
            x0=df['datetime'].min(),
            x1=df['datetime'].min() + pd.Timedelta(minutes=1),  # invisible ancho
            y0=nivel - precision / 2,
            y1=nivel + precision / 2,
            xref="x", yref="y",
            line=dict(width=0),
            fillcolor="rgba(150, 150, 255, {:.2f})".format(vol / max_vol),
            layer="below"
        )


