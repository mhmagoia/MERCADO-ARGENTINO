"""Datos de la pestaña Granos: pizarra (Cámara Arbitral, BCR), dólar futuro (Rava) y futuros.csv."""
import re
from html import unescape
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from fuentes import H, NUM, _num

URL_BCR = "https://www.bcr.com.ar/es/mercados/mercado-de-granos/cotizaciones/cotizaciones-locales-0"
URL_RAVA = "https://www.rava.com/?clasica=1"
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

# FIN granos_datos.py
