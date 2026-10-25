"""Vista de la pestaña Granos y futuros."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculos import calcular
from granos import CULTIVOS, chequeo, tabla_base
from granos_datos import COLS, dolar_futuro, pizarra
from ui import AZUL, VERDE, VIOLETA, fmt, tarjetas

NUM2 = st.column_config.NumberColumn(format="%.2f")
PCT = st.column_config.NumberColumn(format="%.2f%%")


def _sec(t, color):
    st.markdown(f'<div class="sec" style="--ac:{color}">{t}</div>', unsafe_allow_html=True)


def vista_granos(notes, tc, cer, lecaps, cers, flujos, safe):
    piz = safe("BCR · pizarra", pizarra) or {}
    dlr = safe("Rava · dólar futuro", dolar_futuro) or {}
    cards = [(f"{n} · {piz[k][1]}" if k in piz else n, fmt(piz[k][0], 0, "$ ") if k in piz else "s/d", None)
             for n, k in CULTIVOS.items()]
    cards += [(f"{n} en USD (÷ A3500)", fmt(piz[k][0] / tc, 1, "USD ") if k in piz and tc else "s/d", None)
              for n, k in CULTIVOS.items()]
    tarjetas("Pizarra · Cámara Arbitral de Cereales de Rosario ($ por tonelada)", cards, VERDE)

    _sec("Parámetros", VIOLETA)
    cols = st.columns(5)
    disp = {k: cols[i].number_input(f"Disponible {n.lower()} ($/tn)", 0.0, 5e7, float(piz.get(k, (0.0,))[0]), 1000.0,
                                    key=f"disp_{k}_{int(piz.get(k, (0.0,))[0])}")
            for i, (n, k) in enumerate(CULTIVOS.items())}
    com = cols[3].number_input("Comisión sobre el interés (%)", 0.0, 100.0, 4.0, 0.5, key="com")
    iva = cols[4].number_input("IVA sobre la comisión (%)", 0.0, 50.0, 21.0, 0.5, key="iva")

    _sec("Precios de futuros (Matba Rofex / A3), editables", AZUL)
    base = tabla_base(dlr)
    for c in COLS.values():
        base[c] = pd.to_numeric(base[c])
    ed = st.data_editor(base, hide_index=True, disabled=["Mes"], key="fut_editor",
                        column_config={c: NUM2 for c in COLS.values()})
    st.caption("El dólar futuro de los primeros meses viene de Rava (último precio). El resto y los cereales se "
               "cargan acá, o desde futuros.csv; se pueden pegar columnas copiadas del visor de Matba Rofex o de Excel.")
    csv = ed.rename(columns={"Mes": "mes", COLS["dlr"]: "dolar", COLS["soja"]: "soja",
                             COLS["maiz"]: "maiz", COLS["trigo"]: "trigo"}).to_csv(index=False)
    st.download_button("Descargar futuros.csv", csv, "futuros.csv", "text/csv")

    letras = calcular(notes, tc, cer, lecaps, cers, flujos) if notes is not None and len(notes) else pd.DataFrame()
    if not letras.empty:
        letras = letras[(letras["Tasa en"] == "Pesos") & letras["TNA %"].notna()]
    res = {n: chequeo(ed, COLS[k], disp[k], letras, com, iva) for n, k in CULTIVOS.items()}
    if all(d.empty for d in res.values()):
        st.info("Cargá el dólar futuro y el precio de algún cultivo en la tabla para ver el chequeo.")
        return

    _sec("Resumen: futuro vs. disponible + letra (diferencia %)", VERDE)
    resumen = None
    for n, d in res.items():
        if "Dif. %" in d:
            x = d[["Mes", "Letra ref.", "TNA letra %", "Dif. %"]].rename(columns={"Dif. %": f"{n} dif. %"})
            resumen = x if resumen is None else resumen.merge(x[["Mes", f"{n} dif. %"]], on="Mes", how="outer")
    if resumen is not None:
        st.dataframe(resumen.sort_values("Mes"), hide_index=True, column_config={
            **{c: PCT for c in resumen.columns if c.endswith("%")}})
    else:
        st.warning("No hay letras en pesos con tasa para comparar (revisá la pestaña Letras).")

    _sec("Detalle por cultivo", AZUL)
    sel = st.radio("Cultivo", list(CULTIVOS), horizontal=True, key="cultivo")
    d = res[sel]
    if d.empty:
        st.info(f"Falta el precio futuro de {sel.lower()} o el disponible.")
        return
    st.dataframe(d, hide_index=True, column_config={c: (PCT if c.endswith("%") else NUM2)
                                                    for c in d.columns if c not in ("Mes", "Vence", "Días", "Letra ref.")})
    if "Equivalente (USD/tn)" in d:
        fig = go.Figure()
        fig.add_bar(x=d["Mes"], y=d["Futuro (USD/tn)"], name="Precio futuro", marker_color=AZUL)
        fig.add_bar(x=d["Mes"], y=d["Equivalente (USD/tn)"], name="Disponible + letra", marker_color=VERDE)
        fig.update_layout(barmode="group", title=dict(text=f"{sel}: precio futuro vs. equivalente (USD/tn)",
                          font=dict(size=15)), height=360, yaxis_title="USD/tn",
                          margin=dict(l=8, r=8, t=44, b=8), legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, key=f"granos_{sel}")
    st.caption("Futuro en $/tn = precio futuro del cultivo (USD/tn) × dólar futuro del mismo mes. Equivalente = "
               "disponible × (1 + TNA de la letra × días ÷ 365) ÷ dólar futuro − comisión (porcentaje sobre el "
               "interés, más IVA). Diferencia positiva: el futuro paga más que vender hoy el disponible y colocar "
               "en la letra. El vencimiento se toma como el último día hábil del mes, sin feriados.")

# FIN granos_vista.py
