"""Datos de la pestaña Agro mundial: Yahoo Finance (Chicago, oro, S&P 500) y FRED (inflación, tasas, precios del FMI)."""
import io
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import streamlit as st

VERSION = 1
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
DESDE = "1980-01-01"
# nombre: (símbolo de Yahoo, factor a la unidad mostrada, serie del FMI en FRED, unidad)
# Chicago cotiza en centavos de USD por bushel: soja y trigo 36,7437 bu/t y maíz 39,3683 bu/t -> USD por tonelada.
ACTIVOS = {"Soja": ("ZS=F", 0.367437, "PSOYBUSDM", "USD/t"), "Trigo": ("ZW=F", 0.367437, "PWHEAMTUSDM", "USD/t"),
           "Maíz": ("ZC=F", 0.393683, "PMAIZMTUSDM", "USD/t"), "Oro": ("GC=F", 1.0, None, "USD/oz"),
           "S&P 500": ("^GSPC", 1.0, "SP500", "pts")}
FRED = {"IPC": "CPIAUCNS", "IPP": "PPIACO", "Fed": "DFF", "UST2": "DGS2", "UST10": "DGS10", "Spread": "T10Y2Y",
        "Real10": "DFII10", "BE10": "T10YIE", "Desempleo": "UNRATE", "Dolar": "DTWEXBGS"}
COLORES = {"Soja": "#17A673", "Trigo": "#F59E0B", "Maíz": "#6D4AFF", "Oro": "#D4A017", "S&P 500": "#2457E6"}


def _fred(id_, desde=DESDE):
    r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": id_, "cosd": desde}, headers=UA, timeout=30)
    r.raise_for_status()
    d = pd.read_csv(io.StringIO(r.text))
    d.columns = ["fecha", "valor"]
    d["fecha"], d["valor"] = pd.to_datetime(d["fecha"]), pd.to_numeric(d["valor"], errors="coerce")
    return d.dropna().set_index("fecha")["valor"].sort_index()


def _yahoo(simbolo, factor, desde=DESDE):
    p1, p2 = int(pd.Timestamp(desde).timestamp()), int(time.time()) + 86400
    ultimo = "sin respuesta"
    for host in ("query1", "query2"):
        for _ in range(2):
            try:
                r = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{simbolo}", headers=UA, timeout=25,
                                 params={"period1": p1, "period2": p2, "interval": "1d", "events": "history"})
                if r.status_code == 200:
                    res = r.json()["chart"]["result"][0]
                    zona = (res.get("meta") or {}).get("exchangeTimezoneName") or "UTC"
                    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(zona).tz_localize(None).normalize()
                    s = pd.Series(res["indicators"]["quote"][0]["close"], index=idx, dtype="float64").dropna()
                    s = s[~s.index.duplicated(keep="last")].sort_index() * factor
                    if len(s):
                        return s
                ultimo = f"HTTP {r.status_code}"
            except Exception as e:
                ultimo = type(e).__name__
            time.sleep(1.0)
    raise RuntimeError(ultimo)


@st.cache_data(ttl=900, show_spinner="Cargando datos de Chicago, EEUU y el FMI…")
def datos_mundo():
    """{'series': {nombre: Series}, 'errores': {nombre: motivo}}. Cada fuente que falla queda en 'errores'."""
    tareas = {}
    for n, (sim, fac, fmi, _) in ACTIVOS.items():
        tareas[n] = lambda sim=sim, fac=fac: _yahoo(sim, fac)
        if fmi:
            tareas[f"FMI {n}"] = lambda fmi=fmi: _fred(fmi)
    for n, i in FRED.items():
        tareas[n] = lambda i=i: _fred(i)

    def correr(item):
        n, fn = item
        try:
            return n, fn(), None
        except Exception as e:
            return n, None, f"{type(e).__name__}: {e}"
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(correr, tareas.items()))
    series = {n: s for n, s, _ in res if s is not None}
    if not series:
        raise RuntimeError("ninguna fuente respondió")
    return {"series": series, "errores": {n: e for n, s, e in res if s is None}}


def serie_activo(S, n, fmi):
    """Serie del activo: Chicago (diaria) o FMI (mensual). Si falta Yahoo, usa el respaldo de FRED
    (precio global del FMI en los granos; el S&P 500 de FRED, con unos 10 años de historia)."""
    if n in ("Soja", "Trigo", "Maíz") and (fmi or n not in S):
        return S.get(f"FMI {n}")
    if n not in S:
        return S.get(f"FMI {n}")
    return S.get(n)


def recorte(s, anios):
    return s if anios is None or s is None or s.empty else s[s.index >= s.index[-1] - pd.DateOffset(years=anios)]


def mensual(s):
    """Último dato de cada mes (el mes en curso queda con la última cotización)."""
    m = s.groupby(s.index.to_period("M")).last()
    m.index = m.index.to_timestamp()
    return m


def interanual(m):
    return ((m / m.shift(12) - 1) * 100).dropna()


def deflactar(m, defl, base):
    """Precios constantes del mes 'base': real = nominal × deflactor(base) / deflactor(mes).
    Los meses sin dato del deflactor (los últimos) usan el último disponible."""
    d = defl.reindex(defl.index.union(m.index)).ffill().reindex(m.index)
    b = defl.asof(base)
    b = defl.iloc[0] if pd.isna(b) else b
    return (m * b / d).dropna()

# FIN mundo_datos.py
