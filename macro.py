"""Pestaña Macro: pesos, dólar, CER, diferencial dólar-CER y riesgo país."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculos import hoy
from ui import AZUL, NARANJA, ROJO, TURQUESA, VERDE, VIOLETA, grafico


def interanual(s):
    """Variación % contra el mismo día de hace un año (tolera fines de semana y feriados)."""
    if s is None or len(s) < 2:
        return None
    ref = s.shift(freq="365D").reindex(s.index, method="ffill", tolerance=pd.Timedelta(days=7))
    return ((s / ref - 1) * 100).dropna()


def ultimos(s, dias):
    return s[s.index >= s.index[-1] - pd.Timedelta(days=dias)] if s is not None and len(s) else s


def seccion(titulo, color):
    st.markdown(f'<div class="sec" style="--ac:{color}">{titulo}</div>', unsafe_allow_html=True)


def vista_macro(a3500, cer, riesgo, infl, tamar, badlar):
    if cer is not None and len(cer):
        cer = cer[cer.index <= pd.Timestamp(hoy())]  # el BCRA publica CER de fechas futuras
    yd, yc = interanual(a3500), interanual(cer)

    seccion("Pesos", VERDE)
    a, b = st.columns(2)
    with a:
        grafico({"TAMAR": tamar, "BADLAR": badlar}, "Tasas en pesos (TNA %)",
                {"TAMAR": VERDE, "BADLAR": NARANJA}, y="% TNA")
    with b:
        grafico({"Inflación mensual": infl.tail(24) if infl is not None else None},
                "Inflación mensual INDEC (%)", {"Inflación mensual": NARANJA}, barras=True)

    seccion("Dólar", AZUL)
    a, b = st.columns(2)
    with a:
        grafico({"A3500": ultimos(a3500, 730)}, "A3500 ($ por USD)", {"A3500": AZUL})
    with b:
        grafico({"Dólar, var. interanual": ultimos(yd, 730)}, "Dólar A3500: variación interanual (%)",
                {"Dólar, var. interanual": AZUL}, y="%")

    seccion("CER", NARANJA)
    a, b = st.columns(2)
    with a:
        grafico({"CER": ultimos(cer, 730)}, "CER (índice)", {"CER": NARANJA})
    with b:
        grafico({"CER, var. interanual": ultimos(yc, 730)}, "CER: variación interanual (%)",
                {"CER, var. interanual": NARANJA}, y="%")

    seccion("Dólar vs. CER", VIOLETA)
    a, b = st.columns(2)
    if yd is not None and yc is not None:
        dif = (yd - yc).dropna()
        with a:
            fig = go.Figure(go.Bar(x=dif.index, y=dif.values, name="Diferencial",
                                   marker_color=[VIOLETA if v >= 0 else TURQUESA for v in dif.values]))
            fig.add_hline(y=0, line_width=1, line_color="gray")
            fig.update_layout(title=dict(text="Diferencial interanual: dólar menos CER (pp)",
                                         font=dict(size=15)), height=320, showlegend=False,
                              margin=dict(l=8, r=8, t=44, b=8), yaxis_title="puntos porcentuales")
            st.plotly_chart(fig, key="dif")
        rel = (a3500.reindex(cer.index, method="ffill") / cer).dropna()
        rel = ultimos(rel, 730)
        with b:
            grafico({"Dólar / CER": rel / rel.iloc[0] * 100}, "Tipo de cambio ajustado por CER (base 100)",
                    {"Dólar / CER": VIOLETA}, y="índice")
        st.caption("Diferencial positivo, o índice sobre 100: el dólar subió más que el CER, es decir que "
                   "el peso se depreció en términos reales. Negativo o bajo 100: el dólar quedó atrasado "
                   "frente a la inflación medida por CER.")
    else:
        st.warning("Sin datos suficientes de A3500 y CER para calcular el diferencial.")

    seccion("Riesgo país", ROJO)
    grafico({"Riesgo país (pb)": riesgo.tail(365) if riesgo is not None else None},
            "Riesgo país (puntos básicos)", {"Riesgo país (pb)": ROJO})

# FIN macro.py
