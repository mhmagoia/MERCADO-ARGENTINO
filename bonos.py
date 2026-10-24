"""Pestaña Bonos y ONs: tabla con TNA/TIR y gráfico con tasa y eje a elección."""
import plotly.graph_objects as go
import streamlit as st

from calculos import ORDEN, calcular
from fuentes import limitar, traer_rava
from ui import AZUL, CFG, NARANJA, TURQUESA, VERDE, VIOLETA

Y = ["TIR %", "TNA %", "TIR Rava %", "Var. diaria %", "Precio"]
X = {"Días al vencimiento": "Días", "Duration (años)": "Duration"}
COLOR = {"USD": AZUL, "USD (÷ MEP/CCL)": TURQUESA, "Pesos": VERDE,
         "Real (CER constante)": NARANJA, "Según flujos": VIOLETA}


def grafico_bonos(t, nombre):
    con = t.dropna(subset=["TIR %"])
    if len(con) < 2:
        return
    a, b = st.columns(2)
    y = a.selectbox("Tasa a graficar", Y, key=f"y_{nombre}")
    xl = b.selectbox("Eje horizontal", list(X), key=f"x_{nombre}")
    g = con.dropna(subset=[y, X[xl]])
    fig = go.Figure()
    for tasa, gg in g.groupby("Tasa en"):
        fig.add_scatter(x=gg[X[xl]], y=gg[y], name=tasa, text=gg["Ticker"],
                        mode="markers+text" if len(g) <= 30 else "markers", textposition="top center",
                        marker=dict(size=10, color=COLOR.get(tasa, VIOLETA)))
    fig.update_layout(title=dict(text=f"{nombre}: {y} vs. {xl.lower()}", font=dict(size=15)), height=380,
                      xaxis_title=xl, yaxis_title=y, margin=dict(l=8, r=8, t=44, b=8),
                      legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, key=f"g_{nombre}")


def vista_bonos(bonos, ons, tc, cer, lecaps, cers, flujos, mep, ccl, estado):
    for nombre, d in (("Bonos soberanos", bonos), ("Obligaciones negociables", ons)):
        st.markdown(f'<div class="sec" style="--ac:{AZUL}">{nombre}</div>', unsafe_allow_html=True)
        if d is None or d.empty:
            st.warning("Sin datos.")
            continue
        q = st.text_input(f"Filtrar {nombre.lower()}", key=nombre, placeholder="ej: AL30, GD30, YMC")
        if q:
            d = d[d["symbol"].str.contains(q.strip(), case=False, na=False)]
        orden = d.sort_values("v", ascending=False)["symbol"].tolist() if "v" in d else d["symbol"].tolist()
        top = limitar(orden)
        with st.spinner("Leyendo flujos de fondos…"):
            rv_b = traer_rava(top, nombre.split()[0].lower(), estado)
        t = calcular(d, tc, cer, lecaps, cers, flujos, rv_b, {"MEP": mep, "CCL": ccl})
        st.dataframe(t, hide_index=True, column_config=CFG, column_order=ORDEN)
        if len(top) < len(d):
            st.caption(f"Tasas calculadas para {len(top)} de {len(d)} títulos (máx. 80 páginas de Rava por "
                       "vez). Filtrá por ticker para ver el resto.")
        grafico_bonos(t, nombre)
    st.caption("TNA y TIR salen del flujo de fondos publicado por Rava (por cada 100 nominales) y del precio "
               "en vivo. Si Rava no tiene el título o el dato no cierra, queda sin tasa. 'TIR Rava %' es la "
               "que publica Rava, para contrastar. Bonos en USD: filas D/C con su precio en USD; filas en "
               "pesos convertidas a MEP (a CCL los GD). CER: real, con el CER de hoy constante.")

# FIN bonos.py
