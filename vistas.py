"""Pestaña Letras: instrumentos del Tesoro agrupados en tasa fija, CER y dólar linked, con sus curvas."""
import re
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculos import ORDEN, calcular, hoy, info_ticker, monto_vto, parse_ticker, rendimiento
from fuentes import traer_rava
from ui import AZUL, CFG, NARANJA, VERDE, fmt, tarjetas

GRUPOS = {"LECAP": "Tasa fija", "BONCAP": "Tasa fija", "CER": "CER", "Dólar-linked": "Dólar linked", "TAMAR": "TAMAR"}
ORDEN_G = {"Tasa fija": 0, "CER": 1, "Dólar linked": 2, "TAMAR": 3}
CURVAS = [("Tasa fija", VERDE), ("CER", NARANJA), ("Dólar linked", AZUL)]
TITULOS = {"Tasa fija": "Letras y bonos del Tesoro a tasa fija", "CER": "Bonos y letras del Tesoro ajustados por CER (TIR real)",
           "Dólar linked": "Bonos y letras del Tesoro atados al dólar (TIR en USD)"}


def _universo(notes, bonos, cers):
    """Solo instrumentos del Tesoro (por familia de ticker): se descartan provinciales y otros bonos."""
    marcos = [d for d in (notes, bonos) if d is not None and len(d)]
    if not marcos:
        return None
    u = pd.concat(marcos).drop_duplicates("symbol")
    return u[[info_ticker(s, cers)[0] in GRUPOS for s in u["symbol"]]]


def _con_rava(tk, tipo, cers, lecaps):
    """Los que no tienen fórmula propia leen su flujo de fondos de Rava."""
    return ((tipo == "CER" and tk not in cers) or (tipo == "Dólar-linked" and parse_ticker(tk)[1] is None)
            or (tipo in ("LECAP", "BONCAP") and tk not in lecaps))


def _curva(d, y, color, titulo, key):
    d = d.dropna(subset=[y, "Duration"]).sort_values("Duration")
    if d.empty:
        st.info("Sin datos para graficar.")
        return
    fig = go.Figure()
    fig.add_scatter(x=d["Duration"], y=d[y], mode="markers+text" if len(d) <= 25 else "markers", text=d["Ticker"],
                    textposition="top center", textfont=dict(size=10), marker=dict(size=10, color=color),
                    hovertemplate="%{text}<br>Duration %{x:.2f} años<br>" + y + " %{y:.2f}<extra></extra>", showlegend=False)
    if len(d) >= 4:  # curva ajustada, como en el informe de ACA
        xs = np.linspace(d["Duration"].min(), d["Duration"].max(), 60)
        fig.add_scatter(x=xs, y=np.polyval(np.polyfit(d["Duration"], d[y], 2), xs), mode="lines",
                        line=dict(color=color, width=2, dash="dot"), hoverinfo="skip", showlegend=False)
    fig.update_layout(title=dict(text=titulo, font=dict(size=15)), height=380, xaxis_title="Duration (años)",
                      yaxis_title=y, margin=dict(l=8, r=8, t=44, b=8))
    st.plotly_chart(fig, key=key)


def vista_letras(notes, bonos, tc, cer, lecaps, cers, flujos, mep, ccl, estado):
    univ = _universo(notes, bonos, cers)
    if univ is None or univ.empty:
        st.warning("No se pudo leer la cotización de letras (data912).")
    else:
        pedir = [s for s in univ["symbol"] if _con_rava(s, info_ticker(s, cers)[0], cers, lecaps) and s not in flujos]
        rv_l = traer_rava(pedir, "del Tesoro", estado)
        df = calcular(univ, tc, cer, lecaps, cers, flujos, rv_l, {"MEP": mep, "CCL": ccl})
        df.insert(0, "Grupo", df["Tipo"].map(GRUPOS))
        falta = [t for t, ti, tir in zip(df["Ticker"], df["Tipo"], df["TIR %"]) if ti in ("LECAP", "BONCAP") and pd.isna(tir)]
        if falta:
            st.warning(f"Letras sin tasa (no están en el catálogo y Rava no tiene su flujo): {', '.join(falta)}. "
                       "Cargalas en la calculadora de abajo.")
        presentes = [(g, col) for g, col in CURVAS if ((df["Grupo"] == g) & df["TIR %"].notna()).any()]
        if presentes:
            for tab, (g, col) in zip(st.tabs([f"Curva {g}" for g, _ in presentes]), presentes):
                with tab:
                    y = "TIR %"
                    if g == "Tasa fija":
                        y = st.radio("Tasa a graficar", ["TIR %", "TNA %", "TEM %"], horizontal=True, key="y_fija")
                    _curva(df[df["Grupo"] == g], y, col, TITULOS[g] + f" ({y})" if g == "Tasa fija" else TITULOS[g], f"curva_{g}")
        tabla = df.sort_values(["Grupo", "Días"], key=lambda s: s.map(ORDEN_G) if s.name == "Grupo" else s)
        st.dataframe(tabla.round(2), hide_index=True, column_config=CFG, column_order=["Grupo"] + ORDEN)
        st.caption("Solo instrumentos del Tesoro. TNA = rendimiento simple anualizado. TIR = tasa efectiva anual. "
                   "Tasa fija: LECAP/BONCAP con su pago al vencimiento. Dólar linked: precio ÷ A3500 de hoy, o el flujo "
                   "de Rava para los bonos. CER: con el CER de hoy constante hasta el vencimiento. Los que no tienen "
                   "fórmula propia usan el flujo de fondos de Rava. En D y CER sin flujo de Rava no se calcula la tasa "
                   "con menos de 15 días: el resultado sería ruido.")

        with st.expander("Calculadora: agregar una letra nueva"):
            st.caption("LECAP/BONCAP: fecha de emisión y 'capitaliza a una TEM de X%' (comunicado de "
                       "licitación). CER: solo fecha de emisión (el CER sale del BCRA). Queda cargada "
                       "hasta que se reinicie la app; para dejarla fija pegá la línea en LECAPS o CER.")
            if "ultima" in st.session_state:
                st.success(st.session_state["ultima"][0])
                st.code(st.session_state["ultima"][1], language="python")
            with st.form("nueva_letra"):
                tk = st.text_input("Ticker", value=falta[0] if falta else "", placeholder="S13N6").upper().strip()
                emi = st.date_input("Fecha de emisión", value=hoy())
                tem = st.number_input("TEM de capitalización % (solo LECAP/BONCAP)", 0.0, 20.0, 2.0, 0.01)
                vtxt = st.text_input("Vencimiento AAAA-MM-DD (solo si el ticker no lo trae, ej. TZX…)")
                ok = st.form_submit_button("Agregar")
            if ok:
                tipo, vto = info_ticker(tk, cers)
                if vtxt.strip():
                    try:
                        vto = date.fromisoformat(vtxt.strip())
                    except ValueError:
                        vto = None
                if tipo in ("LECAP", "BONCAP") and vto:
                    st.session_state.setdefault("extra", {})[tk] = (emi.isoformat(), tem / 100)
                    msg = f"{tk} agregada: vence {vto:%d/%m/%Y}, paga {monto_vto(emi.isoformat(), tem / 100, vto):.4f} cada 100 VN."
                    linea = f'"{tk}": ("{emi.isoformat()}", {tem / 100:.4f}),'
                elif tipo == "CER" and vto:
                    st.session_state.setdefault("extra_cer", {})[tk] = (emi.isoformat(), vto.isoformat())
                    msg = f"{tk} agregada (CER): vence {vto:%d/%m/%Y}."
                    linea = f'"{tk}": ("{emi.isoformat()}", "{vto.isoformat()}"),'
                else:
                    msg = None
                    st.error("No pude identificar la letra o su vencimiento. Formato: S30N6, T15E7, X29E7 "
                             "(o completá el vencimiento).")
                if msg:
                    st.session_state["ultima"] = (msg, linea)
                    st.rerun()

        with st.expander("Calculadora de TNA y TIR para cualquier instrumento"):
            st.caption("Para bonos u ONs con cupones: precio y flujos por el mismo VN y en la misma moneda "
                       "(usar punto decimal). Los precios del mercado local suelen ser sucios (con intereses).")
            pr = st.number_input("Precio", 0.0, 1e9, 100.0, 0.01, key="cp")
            txt = st.text_area("Flujos: una línea por pago, 'AAAA-MM-DD; monto'", "2027-03-31; 100", key="cf")
            if st.button("Calcular", key="cb"):
                try:
                    fl = []
                    for ln in filter(None, (x.strip() for x in txt.splitlines())):
                        a_, b_ = re.split(r"[;,\t ]+", ln)[:2]
                        fl.append((date.fromisoformat(a_), float(b_)))
                    tna, tir, dur = rendimiento(pr, fl)
                    if tir is None:
                        st.error("No se pudo calcular (revisá fechas futuras y montos).")
                    else:
                        tarjetas("Resultado", [("TNA", fmt(tna * 100, 2, suf="%"), None),
                                           ("TIR", fmt(tir * 100, 2, suf="%"), None),
                                           ("Duration (años)", fmt(dur, 2), None)], AZUL)
                except Exception:
                    st.error("Formato inválido. Ejemplo de línea: 2027-03-31; 100")

# FIN vistas.py
