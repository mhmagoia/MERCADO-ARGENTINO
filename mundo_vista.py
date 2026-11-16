"""Pestaña Agro mundial: Chicago, oro y S&P 500; inflación, tasas y dólar de EEUU; y precios reales."""
import streamlit as st

from estilo import MESES
from mundo_datos import ACTIVOS, COLORES, datos_mundo, interanual, recorte, serie_activo
from mundo_real import vista_real
from ui import AZUL, INDIGO, NARANJA, VERDE, fmt, grafico, tarjetas, ult

VERSION = 1
PERIODOS = {"1 año": 1, "5 años": 5, "10 años": 10, "Máximo": None}
ICONOS = {"Soja": "barras", "Trigo": "barras", "Maíz": "barras", "Oro": "dolar", "S&P 500": "tendencia"}
TASAS = [("Fed", "Tasa de la Fed (fondos federales)", 2, "%", "banco"), ("UST2", "Tesoro a 2 años", 2, "%", "tendencia"),
         ("UST10", "Tesoro a 10 años", 2, "%", "tendencia"), ("Spread", "Curva 10 años menos 2 años", 2, " pp", "barras"),
         ("Real10", "Tasa real a 10 años (TIPS)", 2, "%", "porcentaje"), ("BE10", "Inflación esperada a 10 años", 2, "%", "pulso"),
         ("Desempleo", "Desempleo", 1, "%", "calendario"), ("Dolar", "Dólar amplio (índice)", 1, "", "globo")]


def _mes(s):
    return f"{MESES[s.index[-1].month - 1]}-{s.index[-1].year}"


def vista_mundo(safe):
    datos = safe("Yahoo Finance y FRED (mundo)", datos_mundo)
    if not datos:
        st.warning("No se pudieron leer Yahoo Finance ni FRED en este momento. Probá con «Actualizar ahora» en la barra lateral.")
        return
    S, E = datos["series"], datos["errores"]
    c1, c2, c3 = st.columns([3, 2, 3])
    anios = PERIODOS[c1.radio("Período", list(PERIODOS), index=2, horizontal=True, key="m_per")]
    vista = c2.radio("Vista", ["Precio", "Base 100"], horizontal=True, key="m_vista")
    fmi = c3.radio("Granos", ["Chicago (diario)", "FMI (mensual, desde 1980)"], horizontal=True, key="m_fuente").startswith("FMI")
    if E:
        st.caption("Sin datos de: " + ", ".join(sorted(E)) + ".")
    faltan = [n for n in ("Soja", "Trigo", "Maíz") if n not in S]
    if faltan and not fmi:
        st.info(f"Chicago no respondió para {', '.join(faltan)}: se muestra el precio global del FMI (promedio mensual).")

    series = {n: serie_activo(S, n, fmi) for n in ACTIVOS}
    series = {n: s for n, s in series.items() if s is not None and not s.empty}
    items = []
    for n, s in series.items():
        v, d = ult(s)
        items.append((f"{n} ({ACTIVOS[n][3]})", fmt(v, 0 if v >= 1000 else 1), d, ICONOS[n]))
    tarjetas("Cotizaciones de Chicago, oro y S&P 500", items, AZUL, "tendencia")
    if series:
        u = max(s.index[-1] for s in series.values())
        st.caption(f"Último dato: {u:%d/%m/%Y}. Chicago: futuros del primer vencimiento (CBOT) convertidos a USD por tonelada. "
                   "Datos de Yahoo Finance y FRED; pueden tener demora y no son oficiales.")
    rec = {n: recorte(s, anios) for n, s in series.items()}
    if vista == "Base 100":
        grafico({n: s / s.iloc[0] * 100 for n, s in rec.items()}, "Cotizaciones comparadas (base 100 al inicio del período)", COLORES, y="índice")
    else:
        g = {n: rec[n] for n in ("Soja", "Trigo", "Maíz") if n in rec}
        if g:
            grafico(g, "Granos: USD por tonelada" + (" (FMI, mensual)" if fmi else " (Chicago)"), COLORES, y="USD/t")
        a, b = st.columns(2)
        with a:
            if "Oro" in rec:
                grafico({"Oro": rec["Oro"]}, "Oro: USD por onza", COLORES, y="USD/oz")
        with b:
            if "S&P 500" in rec:
                grafico({"S&P 500": rec["S&P 500"]}, "S&P 500: puntos", COLORES)

    inf = []
    for k, nom, ic in (("IPC", "IPC consumidor (CPI-U)", "pulso"), ("IPP", "IPP de commodities", "barras")):
        m = S.get(k)
        if m is not None and len(m) > 13:
            inf += [(f"{nom} · interanual ({_mes(m)})", fmt((m.iloc[-1] / m.iloc[-13] - 1) * 100, 1, suf="%"),
                     (m.iloc[-1] / m.iloc[-2] - 1) * 100, ic), (f"{nom} · índice", fmt(m.iloc[-1], 1), None, "banco")]
    if inf:
        tarjetas("Inflación de EEUU (la flecha es la variación del último mes)", inf, NARANJA, "pulso")
    tas = [(nom, fmt(S[k].iloc[-1], dec, suf=suf), None, ic) for k, nom, dec, suf, ic in TASAS if k in S]
    if tas:
        tarjetas("Tasas, dólar y empleo de EEUU", tas, VERDE, "porcentaje")
        if "UST10" in S:
            st.caption(f"Tasas y curva al {S['UST10'].index[-1]:%d/%m/%Y}; inflación y desempleo según el último mes publicado por FRED.")
    a, b = st.columns(2)
    with a:
        ser = {nom: recorte(interanual(S[k]), anios) for k, nom in (("IPC", "IPC consumidor"), ("IPP", "IPP de commodities")) if k in S}
        if ser:
            grafico(ser, "Inflación de EEUU: variación interanual (%)", {"IPC consumidor": NARANJA, "IPP de commodities": INDIGO}, y="%")
    with b:
        ser = {nom: recorte(S[k], anios) for k, nom in (("UST10", "Tesoro 10 años"), ("UST2", "Tesoro 2 años"), ("Fed", "Tasa de la Fed")) if k in S}
        if ser:
            grafico(ser, "Tasas de EEUU (%)", {"Tesoro 10 años": AZUL, "Tesoro 2 años": VERDE, "Tasa de la Fed": NARANJA}, y="%")
    a, b = st.columns(2)
    with a:
        if "Dolar" in S:
            grafico({"Dólar amplio": recorte(S["Dolar"], anios)}, "Dólar amplio: índice", {"Dólar amplio": AZUL})
    with b:
        if "Spread" in S:
            grafico({"10 años − 2 años": recorte(S["Spread"], anios)}, "Curva de tasas: 10 años menos 2 años (pp)", {"10 años − 2 años": INDIGO}, y="pp")
    vista_real(S, fmi, anios)

# FIN mundo_vista.py
