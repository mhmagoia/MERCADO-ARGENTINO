"""Pestañas Letras y Bonos/ONs."""
import re
from datetime import date

import plotly.graph_objects as go
import streamlit as st

from calculos import ORDEN, calcular, hoy, info_ticker, monto_vto, rendimiento
from fuentes import limitar, traer_rava
from ui import CFG, fmt, metricas


def vista_letras(notes, tc, cer, lecaps, cers, flujos, mep, ccl, estado):
    if notes is None or notes.empty:
        st.warning("No se pudo leer la cotización de letras (data912).")
    else:
        otros = [x for x in notes["symbol"] if info_ticker(x, cers)[0] is None and x not in flujos]
        rv_l = traer_rava(otros, "letras", estado)
        df = calcular(notes, tc, cer, lecaps, cers, flujos, rv_l, {"MEP": mep, "CCL": ccl})
        falta = [t for t, ti in zip(df["Ticker"], df["Tipo"])
                 if (ti in ("LECAP", "BONCAP") and t not in lecaps) or (ti == "CER" and t not in cers)]
        if falta:
            st.warning(f"Letras detectadas sin datos de emisión: {', '.join(falta)}. "
                       "Cargalas en la calculadora de abajo.")
        c = df.dropna(subset=["TIR %"]).sort_values("Días")
        fig = go.Figure()
        for tasa, g in c.groupby("Tasa en"):
            fig.add_scatter(x=g["Días"], y=g["TIR %"], mode="lines+markers+text", text=g["Ticker"],
                            textposition="top center", name=tasa)
        fig.update_layout(title="TIR vs días al vencimiento (cada curva en su moneda)", height=380,
                          xaxis_title="Días", yaxis_title="TIR %", legend=dict(orientation="h", y=-0.25),
                          margin=dict(l=8, r=8, t=40, b=8))
        st.plotly_chart(fig)
        st.dataframe(df.sort_values(["Tipo", "Días"]).round(2), hide_index=True,
                     column_config=CFG, column_order=ORDEN)
        st.caption("TNA = rendimiento simple anualizado. TIR = tasa efectiva anual. "
                   "Pesos: LECAP/BONCAP al pago fijo. USD: dólar-linked con precio ÷ A3500 de hoy. "
                   "Real: letras CER suponiendo el CER de hoy constante hasta el vencimiento. "
                   "En las D y CER no se calcula la tasa con menos de 15 días: el A3500 es de cierre y el "
                   "precio es de ahora, y el resultado es ruido.")

        with st.expander("➕ Calculadora: agregar una letra nueva"):
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

        with st.expander("🧮 Calculadora de TNA / TIR para cualquier instrumento"):
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
                        metricas([("TNA", fmt(tna * 100, 2, suf="%"), None), ("TIR", fmt(tir * 100, 2, suf="%"), None),
                                  ("Duration (años)", fmt(dur, 2), None)], 3)
                except Exception:
                    st.error("Formato inválido. Ejemplo de línea: 2027-03-31; 100")


def vista_bonos(bonos, ons, tc, cer, lecaps, cers, flujos, mep, ccl, estado):
    for nombre, d in (("Bonos soberanos", bonos), ("Obligaciones negociables", ons)):
        st.subheader(nombre)
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
            st.caption(f"Tasas calculadas para {len(top)} de {len(d)} títulos (máx. 80 páginas de Rava por vez). "
                       "Filtrá por ticker para ver el resto.")
    st.caption("TNA y TIR salen del flujo de fondos publicado por Rava (por cada 100 nominales) y del precio en "
               "vivo. Si Rava no tiene el título o el dato no cierra, queda sin tasa. 'TIR Rava %' es la que "
               "publica Rava, para contrastar. Bonos en USD: filas D/C con su precio en USD; filas en pesos "
               "convertidas a MEP (a CCL los GD). CER: real, con el CER de hoy constante.")

# FIN vistas.py
