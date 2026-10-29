"""Piezas de la pestaña Granos: tablas con colores, resumen por mes y elección del precio de los futuros."""
import pandas as pd
import streamlit as st

from calculos import hoy

NUM2 = st.column_config.NumberColumn(format="%.2f")
PCT = st.column_config.NumberColumn(format="%.2f%%")


def estilo_tabla(df, formato):
    """Tabla con las diferencias en verde (el futuro paga más) o rojo (conviene disponible + letra)."""
    dif = [c for c in df.columns if c.endswith("dif. %") or c.endswith("dif. $")]
    color = lambda x: ("" if pd.isna(x) else "background-color: rgba(39,174,96,.30)" if x > 0
                       else "background-color: rgba(235,87,87,.30)" if x < 0 else "")
    s = df.style
    s = (s.map if hasattr(s, "map") else s.applymap)(color, subset=dif)
    return s.format(formato, na_rep="—")


def resumen_mes(res, cols, extra):
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


def sec(t, color):
    st.markdown(f'<div class="sec" style="--ac:{color}">{t}</div>', unsafe_allow_html=True)


def elegir_precios(a3, rava_dlr, abierta, modo):
    """Precios de los futuros según el modo. Devuelve (precios, fecha, usa_ultimo, texto de estado).
    Automático: con la rueda abierta, el último operado (y el ajuste donde no operó); cerrada, el ajuste."""
    ultimo = modo == "Último operado" or (modo == "Automático" and abierta)
    if not a3:  # respaldo: solo el dólar de los primeros meses desde Rava
        return {"dlr": rava_dlr, "soja": {}, "maiz": {}, "trigo": {}}, None, ultimo, ""
    aj, ul = a3["ajuste"], a3["ultimo"]
    sel = {k: {**aj[k], **ul[k]} for k in aj} if ultimo else aj   # sin operaciones: queda el ajuste
    fecha = a3["fecha_ultimo"] if ultimo else a3["fecha_ajuste"]
    precios = {**sel, "dlr": {**sel["dlr"], **(rava_dlr if ultimo else {})}}  # Rava: dólar de los primeros meses, más fresco
    estado = "Rueda abierta" if abierta else "Mercado cerrado"
    if not ultimo:
        return precios, fecha, ultimo, f"{estado}: ajuste oficial del {fecha:%d/%m/%Y} (CEM de A3)."
    texto = (f"{estado}: último operado del {fecha:%d/%m/%Y} (CEM de A3); los contratos sin operaciones usan su ajuste"
             + (" y el dólar de los primeros meses viene de Rava." if rava_dlr else "."))
    if abierta and fecha < hoy():
        texto += " El CEM todavía no publicó operaciones de hoy, así que no hay precios más frescos que esos."
    return precios, fecha, ultimo, texto

# FIN granos_tablas.py
