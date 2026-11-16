"""Sección de precios reales (ajustados por inflación) de la pestaña Agro mundial."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculos import hoy
from estilo import MESES
from granos_tablas import sec
from mundo_datos import ACTIVOS, COLORES, deflactar, mensual, recorte, serie_activo
from ui import VIOLETA, fmt, tarjetas

VERSION = 1
DEFLACTORES = {"IPP de commodities (el que usa tu Excel)": "IPP", "IPC consumidor (CPI-U)": "IPC"}
ICONOS = {"Soja": "barras", "Trigo": "barras", "Maíz": "barras", "Oro": "dolar", "S&P 500": "tendencia"}


def _lineas(series, titulo, y):
    fig = go.Figure()
    for n, s in series.items():
        nominal = n.endswith("(nominal)")
        fig.add_scatter(x=s.index, y=s.values, name=n, mode="lines",
                        line=dict(color=COLORES[n.replace(" (nominal)", "")], width=1.4 if nominal else 2.2,
                                  dash="dot" if nominal else "solid"))
    fig.update_layout(title=dict(text=titulo, font=dict(size=15)), height=340, yaxis_title=y, hovermode="x unified",
                      margin=dict(l=8, r=8, t=44, b=8), legend=dict(orientation="h", y=-0.18))
    st.plotly_chart(fig, key=titulo)


def vista_real(S, fmi, anios):
    sec("Cotizaciones ajustadas por inflación (precios constantes)", VIOLETA)
    c1, c2, c3 = st.columns([3, 3, 2])
    etiqueta = c1.radio("Deflactor", list(DEFLACTORES), key="r_defl")
    anio = c2.select_slider("Base: enero de", options=list(range(1980, hoy().year + 1)), value=2000, key="r_base")
    con_nominal = c3.checkbox("Mostrar nominal", key="r_nom")
    defl = S.get(DEFLACTORES[etiqueta])
    if defl is None or defl.empty:
        st.warning(f"No se pudo leer el índice «{etiqueta}».")
        return
    base, reales, nominales, items = pd.Timestamp(anio, 1, 1), {}, {}, []
    for n in ACTIVOS:
        s = serie_activo(S, n, fmi)
        if s is None or s.empty:
            continue
        m = mensual(s)
        r = deflactar(m, defl, base)
        if r.empty:
            continue
        reales[n], nominales[n] = recorte(r, anios), recorte(m, anios)
        vs = (r.iloc[-1] / r.median() - 1) * 100
        items.append((n, ("+" if vs > 0 else "") + fmt(vs, 1, suf="%"), None, ICONOS[n]))
    if not reales:
        st.warning("No hay cotizaciones disponibles para ajustar.")
        return
    tarjetas("Precio real de hoy vs. su mediana histórica", items, VIOLETA, "pulso")
    ref = f"ene-{anio}"

    def grupo(nombres, titulo, y):
        ser = {n: reales[n] for n in nombres if n in reales}
        if con_nominal:
            ser.update({f"{n} (nominal)": nominales[n] for n in nombres if n in nominales})
        if ser:
            _lineas(ser, titulo, y)
    grupo(["Soja", "Trigo", "Maíz"], f"Granos: precio real en USD de {ref} por tonelada", "USD/t constantes")
    a, b = st.columns(2)
    with a:
        grupo(["Oro"], f"Oro: precio real en USD de {ref} por onza", "USD/oz constantes")
    with b:
        grupo(["S&P 500"], f"S&P 500: valor real en puntos de {ref}", "puntos constantes")
    u = defl.index[-1]
    st.caption(f"Precio real = precio nominal × índice del mes base ÷ índice de cada mes (la cuenta de tu Excel). "
               f"Deflactor: {etiqueta}; último dato publicado: {MESES[u.month - 1]}-{u.year}, y los meses posteriores usan ese valor. "
               "La mediana se calcula sobre todo el historial disponible de cada fuente (Chicago desde 2000, FMI desde 1980). "
               "Tu Excel ajusta con el IPP de commodities (PPIACO), que no es el IPC de consumidores.")

# FIN mundo_real.py
