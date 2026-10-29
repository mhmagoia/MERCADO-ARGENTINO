"""Datos de la pestaña Granos: pizarra (Cámara Arbitral, BCR), dólar futuro (Rava) y futuros.csv."""
import re
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from calculos import TZ, hoy
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


def parse_cierres(filas, campo="settlement"):
    """Precio por contrato: {'dlr'|'soja'|'maiz'|'trigo': {(año, mes): precio}}.
    campo='settlement': el ajuste (si falta, el último operado). campo='close': el último operado (si falta, el ajuste).
    Dólar: DLR102026. Cereales de Rosario: SOJ.ROS/NOV26, MAI.ROS/DIC26, TRI.ROS/ENE27 (USD/tn)."""
    otro = "close" if campo == "settlement" else "settlement"
    out = {"dlr": {}, "soja": {}, "maiz": {}, "trigo": {}}
    for f in filas:
        s, p = f.get("symbol") or "", f.get(campo) or f.get(otro)
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


def rueda_abierta():
    """Lunes a viernes de 10:30 a 17:00, hora de Argentina (no considera feriados)."""
    n = datetime.now(TZ)
    return n.weekday() < 5 and (10, 30) <= (n.hour, n.minute) < (17, 0)


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


def _pedir_dia(segmento, dia):
    """Filas del día; pide primero también los contratos sin volumen y, si la API no lo acepta, solo los operados."""
    for excluir in ("false", "true"):
        try:
            filas = _dia(segmento, dia, excluir)
        except Exception:
            continue
        if filas:
            return filas
    return []


def _dias_recientes(segmento):
    """((día, filas) del último ajuste, (día, filas) del último operado). Con la rueda en curso pueden ser días distintos."""
    ajuste = ultimo = None
    for k in range(8):
        dia = hoy() - timedelta(days=k)
        if dia.weekday() >= 5:
            continue
        filas = _pedir_dia(segmento, dia.isoformat())
        if not filas:
            continue
        if ultimo is None and any((f.get("close") or 0) > 0 for f in filas):
            ultimo = (dia, filas)
        if any((f.get("settlement") or 0) > 0 for f in filas):
            ajuste = (dia, filas)
            break
    if ajuste is None:
        raise ValueError("el CEM no devolvió ajustes")
    return ajuste, ultimo or ajuste


@st.cache_data(ttl=120, show_spinner=False)
def cierres_a3():
    """Dólar futuro y futuros de soja, maíz y trigo (CEM de A3 Mercados): ajuste y último operado, cada uno con su fecha."""
    (a1, fa1), (u1, fu1) = _dias_recientes("Monedas")
    (a2, fa2), (u2, fu2) = _dias_recientes("Agropecuario")
    return {"ajuste": parse_cierres(fa1 + fa2, "settlement"), "ultimo": parse_cierres(fu1 + fu2, "close"),
            "fecha_ajuste": min(a1, a2), "fecha_ultimo": min(u1, u2)}

# FIN granos_datos.py
