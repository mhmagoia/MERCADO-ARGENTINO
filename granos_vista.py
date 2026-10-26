"""Vista de la pestaña Granos y futuros."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculos import calcular
from granos import CULTIVOS, chequeo, tabla_base
from granos_datos import COLS, cierres_a3, dolar_futuro, pizarra
from ui import AZUL, VERDE, VIOLETA, fmt, tarjetas

NUM2 = st.column_config.NumberColumn(format="%.2f")
PCT = st.column_config.NumberColumn(format="%.2f%%")


def _estilo(df, formato):
    """Tabla con las diferencias en verde (el futuro paga más) o rojo (conviene disponible + letra)."""
    dif = [c for c in df.columns if c.endswith("dif. %") or c.endswith("dif. $")]
    color = lambda x: ("" if pd.isna(x) else "background-color: rgba(39,174,96,.30)" if x > 0
                       else "background-color: rgba(235,87,87,.30)" if x < 0 else "")
    s = df.style
    s = (s.map if hasattr(s, "map") else s.applymap)(color, subset=dif)
    return s.format(formato, na_rep="—")


def _resumen(res, cols, extra):
    """Une por mes las columnas elegidas de cada cultivo (cols = {columna: sufijo}) más datos comunes del mes."""
    out, info = None, []
    for n, d in res.items():
        if "Dif. %" in d:
            info.append(d[["Mes"] + extra])
            x = d[["Mes"] + list(cols)].rename(columns={c: f"{n} {s}" for c, s in cols.items()})
            out = x if out is None else out.merge(x, on="Mes", how="outer")
    if out is None:
        return None
    out = out.merge(pd.concat(info).drop_duplicates("Mes"), on="Mes", how="left")
    return out[["Mes"] + extra + [c for c in out.columns if c not in ["Mes"] + extra]].sort_values("Mes")


def _sec(t, color):
    st.markdown(f'<div class="sec" style="--ac:{color}">{t}</div>', unsafe_allow_html=True)


def vista_granos(notes, tc, cer, lecaps, cers, flujos, safe):
    piz = safe("BCR · pizarra", pizarra) or {}
    auto = safe("A3 · ajustes de futuros (CEM)", cierres_a3)
    if not auto:  # respaldo: solo el dólar de los primeros meses desde Rava
        auto = {"fecha": None, "dlr": safe("Rava · dólar futuro", dolar_futuro) or {}, "soja": {}, "maiz": {}, "trigo": {}}
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
    com = cols[3].number_input("Comisión sobre el interés (%)", 0.0, 100.0, 0.0, 0.5, key="com_v2",
                               help="Costo de operar la letra, aplicado sobre el interés ganado y no sobre el capital. "
                                    "Tu Excel usaba 4 % (celda L91: 'le puse 4 % de comisión'). En 0 se ve el cálculo sin costos.")
    iva = cols[4].number_input("IVA sobre la comisión (%)", 0.0, 50.0, 21.0, 0.5, key="iva",
                               help="Solo se aplica si la comisión es mayor que 0.")

    fecha = auto.get("fecha")
    _sec("Precios de futuros (Matba Rofex / A3)" + (f" · ajuste del {fecha:%d/%m/%Y}" if fecha else "") + ", editables", AZUL)
    base = tabla_base(auto)
    for c in COLS.values():
        base[c] = pd.to_numeric(base[c])
    ed = st.data_editor(base, hide_index=True, disabled=["Mes"], key="fut_editor", height=330,
                        column_config={c: NUM2 for c in COLS.values()})
    st.caption("Ajustes del CEM de A3 Mercados (dólar y soja, maíz y trigo de Rosario). Si un contrato no cotiza, la celda "
               "queda vacía: completala acá o en futuros.csv. Cualquier valor se puede pisar a mano. Los resultados "
               "aparecen debajo de esta tabla.")
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

    mejores = []
    for n, d in res.items():
        if "Dif. %" in d and d["Dif. %"].notna().any():
            r = d.loc[d["Dif. %"].idxmax()]
            mejores.append((f"{n} · mejor mes {r['Mes']}",
                            f"USD {fmt(r['Futuro (USD/tn)'], 1)} vs {fmt(r['Equivalente neto (USD/tn)'], 1)}", r["Dif. %"]))
    if mejores:
        tarjetas("Mejor oportunidad por cultivo: precio futuro vs. disponible + letra (USD/tn)", mejores, VERDE)

    _sec("Comparación rápida por mes (verde: conviene el futuro · rojo: conviene disponible + letra)", VERDE)
    usd = _resumen(res, {"Futuro (USD/tn)": "futuro", "Equivalente neto (USD/tn)": "equiv.", "Dif. %": "dif. %"},
                   ["Letra ref.", "TNA letra %"])
    if usd is None:
        st.warning("No hay letras en pesos con tasa para comparar (revisá la pestaña Letras).")
    else:
        st.dataframe(_estilo(usd, {c: ("{:+.2f}%" if c.endswith("dif. %") else "{:.2f}%" if c.endswith("%") else "{:.1f}")
                                   for c in usd.columns if c not in ("Mes", "Letra ref.")}), hide_index=True)
        _sec("Comparación rápida por mes en pesos ($ por tonelada)", VIOLETA)
        pes = _resumen(res, {"Futuro en $/tn": "futuro $", "Equivalente neto ($/tn)": "equiv. $", "Dif. ($/tn)": "dif. $"},
                       ["Letra ref.", "TNA letra %", "Dólar fut. ($)"])
        num, sg = (lambda x: fmt(x, 0)), (lambda x: ("+" if x > 0 else "") + fmt(x, 0))
        st.dataframe(_estilo(pes, {c: (sg if c.endswith("dif. $") else "{:.2f}%" if c == "TNA letra %" else num)
                                   for c in pes.columns if c not in ("Mes", "Letra ref.")}), hide_index=True)
        st.caption("Es la misma comparación en pesos: el porcentaje de diferencia es idéntico al de dólares, porque ambos "
                   "lados se convierten con el mismo dólar futuro. Futuro $ = precio en USD × dólar futuro. Equivalente $ = "
                   "disponible llevado a vencimiento con la letra, menos la comisión si la hay.")

    _sec("Detalle por cultivo", AZUL)
    sel = st.radio("Cultivo", list(CULTIVOS), horizontal=True, key="cultivo")
    d = res[sel]
    if d.empty:
        st.info(f"Falta el precio futuro de {sel.lower()} o el disponible.")
        return
    cfg = lambda cs: {c: (PCT if c.endswith("%") else NUM2) for c in cs if c not in ("Mes", "Vence", "Días", "Letra ref.")}
    p1 = ["Mes", "Vence", "Días", "Dólar fut. ($)", "Futuro (USD/tn)", "Futuro en $/tn", "Disponible $/tn",
          "Retorno implícito %", "TNA implícita %"]
    st.markdown("**Paso 1 · Valor del futuro en pesos**: precio futuro del cultivo (USD/tn) × dólar futuro del mismo mes.")
    st.dataframe(d[p1], hide_index=True, column_config=cfg(p1))
    p2 = ["Mes", "Letra ref.", "TNA letra %", "Disponible $/tn", "Disponible a vto ($/tn)", "Dólar fut. ($)",
          "Equivalente sin comisión (USD/tn)", "Comisión (USD/tn)", "Equivalente neto (USD/tn)", "Futuro (USD/tn)",
          "Dif. (USD/tn)", "Dif. %"]
    if "Disponible a vto ($/tn)" in d:
        st.markdown("**Paso 2 · Disponible llevado a vencimiento con la letra**: pesos a vencimiento ÷ dólar futuro = "
                    "USD/tn a los que estarías vendiendo el cultivo. Se compara con el precio del futuro.")
        st.dataframe(d[p2], hide_index=True, column_config=cfg(p2))
        r = d.iloc[0]
        st.info(f"Ejemplo {r['Mes']}: {fmt(r['Disponible $/tn'], 0, '$ ')} × (1 + {fmt(r['TNA letra %'], 1, suf='%')} × "
                f"{int(r['Días'])}/365) = {fmt(r['Disponible a vto ($/tn)'], 0, '$ ')} a vencimiento "
                f"(letra {r['Letra ref.']}). Dividido el dólar futuro de {fmt(r['Dólar fut. ($)'], 0, '$ ')} da "
                f"USD {fmt(r['Equivalente sin comisión (USD/tn)'], 1)}/tn, contra USD {fmt(r['Futuro (USD/tn)'], 1)}/tn del futuro.")
    if "Equivalente neto (USD/tn)" in d:
        fig = go.Figure()
        fig.add_bar(x=d["Mes"], y=d["Futuro (USD/tn)"], name="Precio futuro", marker_color=AZUL)
        fig.add_bar(x=d["Mes"], y=d["Equivalente neto (USD/tn)"], name="Disponible + letra", marker_color=VERDE)
        fig.update_layout(barmode="group", title=dict(text=f"{sel}: precio futuro vs. equivalente (USD/tn)",
                          font=dict(size=15)), height=360, yaxis_title="USD/tn",
                          margin=dict(l=8, r=8, t=44, b=8), legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, key=f"granos_{sel}")
    st.caption("Diferencia positiva: el precio del futuro paga más que vender hoy el disponible y colocar los pesos en la "
               "letra; negativa: conviene lo segundo. La letra de referencia es la LECAP o BONCAP con vencimiento más "
               "cercano al del futuro. El vencimiento se toma como el último día hábil del mes, sin feriados.")

# FIN granos_vista.py
