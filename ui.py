"""Tarjetas, formatos, gráficos base y la pestaña Resumen."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from estilo import icono, spark

AZUL, NARANJA, VERDE, VIOLETA, ROJO, TURQUESA = "#2457E6", "#F59E0B", "#17A673", "#6D4AFF", "#E5484D", "#00A3A3"
CELESTE, INDIGO = "#4FA3FF", "#4338CA"
PAL = [AZUL, CELESTE, INDIGO, VERDE, VIOLETA, NARANJA]

PCT = lambda t="": st.column_config.NumberColumn(format="%.2f%%", help=t)
NUM2 = lambda t="": st.column_config.NumberColumn(format="%.2f", help=t)
CFG = {"Precio": NUM2(), "Compra": NUM2(), "Venta": NUM2(),
       "Días": st.column_config.NumberColumn(format="%d"),
       "Duration": NUM2("Duration de Macaulay, en años."),
       "Var. diaria %": PCT(),
       "TIR Rava %": PCT("TIR que publica Rava con su cotización (para contrastar)."),
       "TNA %": PCT("Rendimiento simple anualizado (sin capitalizar)."),
       "TIR %": PCT("Tasa efectiva anual (compuesta, base 365)."),
       "TEM %": PCT("En letras en pesos = devaluación mensual de equilibrio."),
       "TC breakeven": st.column_config.NumberColumn(format="$ %.0f", help="A3500 × (1 + rend. directo)")}

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


def tarjetas(titulo, items, color, ic=None):
    """Grilla de tarjetas. items: (etiqueta, valor, variación numérica o None[, ícono[, html extra]])."""
    h = [f'<div class="sec" style="--ac:{color}">{icono(ic, 20) if ic else ""}{titulo}</div><div class="grid">']
    for it in items:
        lab, val, dlt = it[:3]
        ci = icono(it[3], 14) if len(it) > 3 and it[3] else ""
        extra = it[4] if len(it) > 4 else ""
        d = ""
        if dlt is not None and not pd.isna(dlt):
            cls, flecha = ("up", "▲") if dlt >= 0 else ("down", "▼")
            d = f'<div class="d {cls}">{flecha} {fmt(abs(dlt), 2, suf="%")}</div>'
        h.append(f'<div class="card" style="--ac:{color}"><div class="l">{ci}{lab}</div>'
                 f'<div class="v">{val}</div>{d}{extra}</div>')
    st.markdown("".join(h) + "</div>", unsafe_allow_html=True)


def grafico(series, titulo, colores=None, h=320, barras=False, y=None):
    fig = go.Figure()
    for i, (nombre, s) in enumerate(series.items()):
        if s is None or len(s) == 0:
            continue
        col = (colores or {}).get(nombre, PAL[i % len(PAL)])
        if barras:
            fig.add_bar(x=s.index, y=s.values, name=nombre, marker_color=col)
        else:
            fig.add_scatter(x=s.index, y=s.values, name=nombre, mode="lines",
                            line=dict(color=col, width=2.2))
    fig.update_layout(title=dict(text=titulo, font=dict(size=15)), height=h, yaxis_title=y,
                      margin=dict(l=8, r=8, t=44, b=8), hovermode="x unified",
                      legend=dict(orientation="h", y=-0.18))
    st.plotly_chart(fig, key=titulo)


def vista_resumen(tc, tc_d, ofi, mep, ccl, blue, brecha, sup, inf_, rp, rp_d, t, bd, c, c_d,
                  im, rm, a3500, b_sup, b_inf, riesgo=None):
    margen = lambda b: fmt((b / tc - 1) * 100, 1, suf="%") if b and tc else "s/d"
    tarjetas("Tipo de cambio", [
        ("A3500 mayorista", fmt(tc, 2, "$ "), tc_d, "banco"), ("Oficial (venta)", fmt(ofi, 2, "$ "), None, "billete"),
        ("MEP", fmt(mep, 2, "$ "), None, "cambio"), ("CCL", fmt(ccl, 2, "$ "), None, "globo"),
        ("Blue", fmt(blue, 2, "$ "), None, "dolar"), ("Brecha CCL / oficial", fmt(brecha, 1, suf="%"), None, "porcentaje")],
        AZUL, "cambio")
    tarjetas("Bandas cambiarias", [
        ("Banda superior", fmt(sup, 2, "$ "), None, "arriba"), ("Banda inferior", fmt(inf_, 2, "$ "), None, "abajo"),
        ("Margen a banda superior", margen(sup), None, "porcentaje"),
        ("Margen a banda inferior", margen(inf_), None, "porcentaje")], VIOLETA, "capas")
    tarjetas("Tasas e inflación", [
        ("TAMAR (TNA)", fmt(t, 2, suf="%"), None, "tendencia"), ("BADLAR (TNA)", fmt(bd, 2, suf="%"), None, "barras"),
        ("CER", fmt(c, 4), c_d, "pulso"), ("Inflación mensual INDEC", fmt(im, 1, suf="%"), None, "porcentaje"),
        ("REM 12 meses", fmt(rm, 1, suf="%"), None, "calendario")], VERDE, "porcentaje")
    tarjetas("Riesgo soberano", [("Riesgo país", fmt(rp, 0, suf=" pb"), rp_d, "escudo", spark(riesgo, ROJO))], ROJO, "escudo")
    u365 = lambda s: s[s.index >= s.index[-1] - pd.Timedelta(days=365)] if s is not None and len(s) else s
    grafico({"A3500": u365(a3500), "Banda superior": u365(b_sup), "Banda inferior": u365(b_inf)},
            "A3500 y bandas cambiarias ($ por USD)",
            {"A3500": AZUL, "Banda superior": INDIGO, "Banda inferior": CELESTE})

# FIN ui.py
