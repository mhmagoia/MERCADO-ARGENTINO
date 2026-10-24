"""Piezas de interfaz: estilos, formatos, gráficos y las pestañas Resumen y Macro."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PCT = lambda t="": st.column_config.NumberColumn(format="%.2f%%", help=t)
CFG = {"Precio": st.column_config.NumberColumn(format="%.2f"),
       "Compra": st.column_config.NumberColumn(format="%.2f"),
       "Venta": st.column_config.NumberColumn(format="%.2f"),
       "Días": st.column_config.NumberColumn(format="%d"),
       "Var. diaria %": PCT(),
       "TIR Rava %": PCT("TIR que publica Rava con su cotización (para contrastar)."),
       "TNA %": PCT("Rendimiento simple anualizado (sin capitalizar)."),
       "TIR %": PCT("Tasa efectiva anual (compuesta, base 365)."),
       "TEM %": PCT("En letras en pesos = devaluación mensual de equilibrio."),
       "TC breakeven": st.column_config.NumberColumn(format="$ %.0f", help="A3500 × (1 + rend. directo)")}


def estilos():
    st.markdown("""<style>
.block-container{padding-top:1.2rem;padding-bottom:2rem}
@media (max-width:640px){
 .block-container{padding-left:.6rem;padding-right:.6rem}
 [data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:wrap;gap:.4rem}
 [data-testid="stColumn"],[data-testid="column"]{min-width:calc(50% - .4rem)!important;flex:1 1 calc(50% - .4rem)!important}
 [data-testid="stMetricValue"]{font-size:1.25rem}
}</style>""", unsafe_allow_html=True)


def fmt(x, dec=2, pre="", suf=""):
    if x is None or pd.isna(x):
        return "s/d"
    x = round(float(x), dec) + 0.0  # evita "-0,00"
    return pre + f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".") + suf


def ult(s):
    if s is None or len(s) == 0:
        return None, None
    v = s.iloc[-1]
    d = (v / s.iloc[-2] - 1) * 100 if len(s) > 1 and s.iloc[-2] else None
    return v, d


def metricas(items, n=4):
    for i in range(0, len(items), n):
        for col, (lab, val, dlt) in zip(st.columns(n), items[i:i + n]):
            col.metric(lab, val, dlt)


def grafico(series, titulo, h=340, barras=False):
    fig = go.Figure()
    for nombre, s in series.items():
        if s is not None and len(s):
            (fig.add_bar if barras else fig.add_scatter)(x=s.index, y=s.values, name=nombre,
                                                         **({} if barras else {"mode": "lines"}))
    fig.update_layout(title=titulo, height=h, margin=dict(l=8, r=8, t=40, b=8),
                      legend=dict(orientation="h", y=-0.2), hovermode="x unified")
    st.plotly_chart(fig)


def vista_resumen(tc, tc_d, ofi, mep, ccl, blue, brecha, sup, inf_, rp, rp_d, t, bd, c, c_d,
                  im, rm, a3500, b_sup, b_inf):
    metricas([("A3500 mayorista", fmt(tc, 2, "$ "), fmt(tc_d, 2, suf="%") if tc_d else None),
              ("Oficial (venta)", fmt(ofi, 2, "$ "), None), ("MEP", fmt(mep, 2, "$ "), None),
              ("CCL", fmt(ccl, 2, "$ "), None), ("Blue", fmt(blue, 2, "$ "), None),
              ("Brecha CCL/oficial", fmt(brecha, 1, suf="%"), None),
              ("Banda superior", fmt(sup, 2, "$ "), None), ("Banda inferior", fmt(inf_, 2, "$ "), None),
              ("Riesgo país", fmt(rp, 0, suf=" pb"), fmt(rp_d, 2, suf="%") if rp_d else None),
              ("TAMAR (TNA)", fmt(t, 2, suf="%"), None), ("BADLAR (TNA)", fmt(bd, 2, suf="%"), None),
              ("CER", fmt(c, 4), fmt(c_d, 2, suf="%") if c_d else None),
              ("Inflación mensual (INDEC)", fmt(im, 1, suf="%"), None),
              ("REM 12m (inflación esperada)", fmt(rm, 1, suf="%"), None)])
    grafico({"A3500": a3500, "Banda sup.": b_sup, "Banda inf.": b_inf},
            "A3500 vs bandas cambiarias ($ por USD)")


def vista_macro(riesgo, infl, tamar, badlar, cer):
    grafico({"Riesgo país (pb)": riesgo.tail(365) if riesgo is not None else None}, "Riesgo país")
    grafico({"Inflación mensual %": infl.tail(24) if infl is not None else None},
            "Inflación mensual (INDEC)", barras=True)
    grafico({"TAMAR": tamar, "BADLAR": badlar}, "Tasas en pesos (TNA %)")
    grafico({"CER": cer}, "CER")

# FIN ui.py
