"""Datos de la pestaña Granos: pizarra (Cámara Arbitral, BCR), dólar futuro (Rava) y futuros.csv."""
import re
from datetime import timedelta
from html import unescape
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from calculos import hoy
from fuentes import H, NUM, _num

URL_BCR = "https://www.bcr.com.ar/es/mercados/mercado-de-granos/cotizaciones/cotizaciones-locales-0"
URL_RAVA = "https://www.rava.com/?clasica=1"
URL_CEM = "https://apicem.matbarofex.com.ar/api/v2/closing-prices"  # API pública del CEM de A3 Mercados
MESES = dict(zip(["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"], range(1, 13)))
COLS = {"dlr": "Dólar futuro ($)", "soja": "Soja (USD/tn)", "maiz": "Maíz (USD/tn)", "trigo": "Trigo (USD/tn)"}


def _texto(html):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"[\s|*]+", " ", unescape(re.sub(r"<[^>]+>", " ", t)))


def parse_pizarra(html):
    """{'soja': (precio, 'dd/mm/aaaa'), ...} con el último precio operado de cada cultivo."""
    t = _texto(html)
    i = t.find("Trading date")
    sec = t[i: i + 1800] if i >= 0 else ""
    fechas = re.findall(r"\d{2}/\d{2}/\d{4}", sec)[:5]
    out = {}
    for nombre, eng, clave in (("Soja", "Soybean", "soja"), ("Maíz", "Yellow corn", "maiz"), ("Trigo", "Wheat", "trigo")):
        j = sec.find(f"{nombre} {eng}")
        if j < 0 or not fechas:
            continue
        valores = re.findall(r"S/C|\$\s*[\d.,]+", sec[j + len(nombre) + len(eng):])[:len(fechas)]
        for v, f in zip(valores, fechas):
            if v != "S/C":
                out[clave] = (_num(v.replace("$", "").strip()), f)
                break
    return out


def parse_dlr(html):
    """{(año, mes): último precio} de los contratos DLR/MMMAA que lista la portada de Rava."""
    t = _texto(html)
    return {(2000 + int(a), MESES[m]): _num(p)
            for m, a, p in re.findall(rf"DLR/([A-Z]{{3}})(\d{{2}}) ({NUM})", t) if m in MESES}


@st.cache_data(ttl=1800, show_spinner=False)
def pizarra():
    r = requests.get(URL_BCR, headers=H, timeout=15)
    r.raise_for_status()
    d = parse_pizarra(r.text)
    if not d:
        raise ValueError("no se encontró la tabla de pizarra")
    return d


@st.cache_data(ttl=120, show_spinner=False)
def dolar_futuro():
    r = requests.get(URL_RAVA, headers=H, timeout=15)
    r.raise_for_status()
    d = parse_dlr(r.text)
    if not d:
        raise ValueError("no se encontraron contratos DLR")
    return d


def cargar_futuros_csv():
    """futuros.csv opcional (junto a app.py): columnas mes,dolar,soja,maiz,trigo; mes = AAAA-MM."""
    f = Path(__file__).with_name("futuros.csv")
    if not f.exists():
        return None
    d = pd.read_csv(f, dtype={"mes": str})
    return d.set_index("mes") if len(d) else None


AGRO = {"SOJ": "soja", "MAI": "maiz", "TRI": "trigo"}


def parse_cierres(filas):
    """Ajuste (settlement) por contrato: {'dlr'|'soja'|'maiz'|'trigo': {(año, mes): precio}}.
    Dólar: DLR102026. Cereales de Rosario: SOJ.ROS/NOV26, MAI.ROS/DIC26, TRI.ROS/ENE27 (USD/tn)."""
    out = {"dlr": {}, "soja": {}, "maiz": {}, "trigo": {}}
    for f in filas:
        s, p = f.get("symbol") or "", f.get("settlement") or f.get("close")
        if not p or p <= 0:
            continue
        m = re.fullmatch(r"DLR(\d{2})(\d{4})", s)
        if m:
            out["dlr"][(int(m[2]), int(m[1]))] = float(p)
            continue
        m = re.fullmatch(r"(SOJ|MAI|TRI)\.ROS/([A-Z]{3})(\d{2})", s)
        if m and m[2] in MESES:
            out[AGRO[m[1]]][(2000 + int(m[3]), MESES[m[2]])] = float(p)
    return out


def _dia(segmento, dia, excluir_vacios):
    filas, pagina = [], 1
    while True:
        r = requests.get(URL_CEM, params={"segment": segmento, "type": "FUT", "excludeEmptyVol": excluir_vacios,
                                          "from": dia, "to": dia, "page": pagina, "pageSize": 100,
                                          "sortDir": "ASC", "market": "ROFX"}, headers=H, timeout=20)
        r.raise_for_status()
        j = r.json()
        filas += j.get("data") or []
        if not j.get("data") or len(filas) >= j.get("totalEntries", 0) or pagina >= 10:
            return filas
        pagina += 1


def _ultimo_dia(segmento):
    """Último día hábil con ajustes publicados. Primero pide también los contratos sin volumen."""
    for k in range(8):
        dia = hoy() - timedelta(days=k)
        if dia.weekday() >= 5:
            continue
        for excluir in ("false", "true"):
            try:
                filas = _dia(segmento, dia.isoformat(), excluir)
            except Exception:
                continue
            if any((f.get("settlement") or 0) > 0 for f in filas):
                return dia, filas
            if filas:
                break  # rueda en curso, sin ajuste todavía: probar el día anterior
    raise ValueError("el CEM no devolvió ajustes")


@st.cache_data(ttl=600, show_spinner=False)
def cierres_a3():
    """Ajustes del último día hábil: dólar futuro y futuros de soja, maíz y trigo (CEM de A3 Mercados)."""
    f1, filas1 = _ultimo_dia("Monedas")
    f2, filas2 = _ultimo_dia("Agropecuario")
    out = parse_cierres(filas1 + filas2)
    out["fecha"] = min(f1, f2)
    return out

# FIN granos_datos.py
