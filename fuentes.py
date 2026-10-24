"""Fuentes de datos: data912, dolarapi, argentinadatos, BCRA v4 y flujos de fondos de Rava."""
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import urllib3

from calculos import hoy

# ── Capa de datos ────────────────────────────────────────────────────────────────────────
H = {"User-Agent": "Mozilla/5.0 (dashboard-letras)"}


def _get(url, params=None):
    try:
        r = requests.get(url, params=params, headers=H, timeout=20)
    except requests.exceptions.SSLError:  # algunos sitios .gob.ar tienen cadenas de cert. incompletas
        urllib3.disable_warnings()
        r = requests.get(url, params=params, headers=H, timeout=20, verify=False)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=45, show_spinner=False)
def panel(nombre):  # arg_notes (letras), arg_bonds, arg_corp (ONs)
    return pd.DataFrame(_get(f"https://data912.com/live/{nombre}"))


@st.cache_data(ttl=60, show_spinner=False)
def dolares():
    return pd.DataFrame(_get("https://dolarapi.com/v1/dolares")).set_index("casa")


@st.cache_data(ttl=600, show_spinner=False)
def serie_ad(path):
    d = pd.DataFrame(_get(f"https://api.argentinadatos.com/v1/finanzas/indices/{path}"))
    d["fecha"] = pd.to_datetime(d["fecha"])
    return d.set_index("fecha")["valor"].astype(float).sort_index()


@st.cache_data(ttl=3600, show_spinner=False)
def bcra_vars():
    return pd.DataFrame(_get("https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias",
                             {"limit": 3000})["results"])


def _n(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


# Las variables del BCRA se buscan por descripción (si cambia un ID, la app lo encuentra igual)
BUSCAR = {"a3500": ["mayorista", "3500"], "banda_sup": ["bandas", "superior"],
          "banda_inf": ["bandas", "inferior"], "tamar": ["tamar", "n.a."],
          "badlar": ["badlar", "n.a."], "cer": ["cer", "base"],
          "rem": ["inflacion esperada", "rem"]}
FALLBACK = {"a3500": 5, "cer": 30, "badlar": 7, "tamar": 44}


def var_id(clave):
    try:
        df = bcra_vars()
        desc = df["descripcion"].map(_n)
        m = df[[all(k in d for k in BUSCAR[clave]) for d in desc]]
        if len(m):
            return int(m.iloc[m["descripcion"].str.len().argmin()]["idVariable"])
    except Exception:
        pass
    return FALLBACK.get(clave)


@st.cache_data(ttl=900, show_spinner=False)
def bcra_serie(vid, dias=400):
    if vid is None:
        return pd.Series(dtype=float)
    j = _get(f"https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/{vid}",
             {"desde": (hoy() - timedelta(days=dias)).isoformat(), "hasta": hoy().isoformat(),
              "limit": 3000})
    d = pd.DataFrame(j["results"][0]["detalle"])
    d["fecha"] = pd.to_datetime(d["fecha"])
    return d.set_index("fecha")["valor"].astype(float).sort_index()


@st.cache_data(ttl=300, show_spinner=False)
def cargar_flujos():
    """flujos.csv (opcional, junto a app.py): columnas ticker,fecha,monto  -> bonos/ONs con cupones."""
    f = Path(__file__).with_name("flujos.csv")
    if not f.exists():
        return {}
    d = pd.read_csv(f)
    d["fecha"] = pd.to_datetime(d["fecha"]).dt.date
    return {k: list(zip(g["fecha"], g["monto"])) for k, g in d.groupby("ticker")}


# ── Flujo de fondos desde Rava (bonos, ONs y letras sin fórmula propia) ────────────────
NUM = r"-?\d[\d.]*(?:,\d+)?"


def _num(x):
    return float(x.replace(".", "").replace(",", "."))


def parse_rava(html, base):
    """Lee de rava.com/perfil/<TICKER> la tabla 'Flujo de fondos' (por cada 100 nominales) y su TIR."""
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    t = unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[\s|*]+", " ", t)
    fin = t.find("Flujo actualizado")
    ini = t.rfind("Flujo de fondos", 0, fin if fin > 0 else len(t))
    if ini < 0:
        return None
    sec = t[ini: fin if fin > 0 else ini + 8000]
    fl = [(datetime.strptime(d, "%d/%m/%Y").date(), _num(tot))
          for d, _i, _a, tot in re.findall(rf"(\d{{2}}/\d{{2}}/\d{{4}}) ({NUM}) ({NUM}) ({NUM})", sec)]
    fl = [(d, m) for d, m in fl if d > hoy() and m > 0]
    if not fl:
        return None
    tir = re.search(rf"TIR\s*({NUM})\s*%", sec)
    return {"base": base, "flujos": fl, "tir": _num(tir[1]) if tir else None,
            "pesos": "en pesos" in sec.lower(),      # AO28: "Pagos futuros cada 100 nominales."  (USD)
            "cer": "CER" in sec}                     # TX28: "...en pesos ajustados por CER o tipo de cambio"


@st.cache_resource
def _store():
    return {}  # base -> (timestamp, datos|None); sobrevive entre recargas


def _rava_pagina(base, store):
    """(datos, estado). Estados: ok | sin_flujo (Rava no lo publica) | error (red/bloqueo: se reintenta en 2 min)."""
    hit = store.get(base)
    if hit and time.time() - hit[0] < hit[2]:
        return hit[1], hit[3]
    datos, estado, ttl = None, "error", 120
    for _ in range(2):
        try:
            r = requests.get(f"https://www.rava.com/perfil/{base}", headers=H, timeout=12)
        except Exception:
            time.sleep(0.7)
            continue
        if r.status_code == 200:
            datos = parse_rava(r.text, base)
            estado, ttl = ("ok", 6 * 3600) if datos else ("sin_flujo", 3600)
            break
        if r.status_code == 404:
            estado, ttl = "sin_flujo", 6 * 3600
            break
        time.sleep(0.7)  # 403/429/5xx: reintenta una vez
    store[base] = (time.time(), datos, ttl, estado)
    return datos, estado


def candidatos(tk):
    """AE38D/AE38C -> página AE38; ON: YMCID -> YMCI o YMCIO."""
    if len(tk) > 3 and tk[-1] in "DC":
        return [tk[:-1], tk[:-1] + "O"]
    return [tk]


def limitar(tickers, max_paginas=80):
    """Corta por páginas de Rava distintas (AE38, AE38C y AE38D comparten una), no por cantidad de tickers."""
    out, bases = [], set()
    for tk in tickers:
        b = candidatos(tk)[0]
        if b in bases or len(bases) < max_paginas:
            bases.add(b)
            out.append(tk)
    return out


def traer_rava(tickers, etiqueta, estado):
    store, res, estados = _store(), {}, {}
    pend = {tk: candidatos(tk) for tk in tickers}
    for _ in range(2):
        need = sorted({c[0] for c in pend.values() if c})
        if not need:
            break
        with ThreadPoolExecutor(8) as ex:
            datos = dict(zip(need, ex.map(lambda b: _rava_pagina(b, store), need)))
        estados.update({b: e for b, (_d, e) in datos.items()})
        for tk, c in list(pend.items()):
            if datos[c[0]][0]:
                res[tk] = datos[c[0]][0]
                pend.pop(tk)
            else:
                c.pop(0)
                if not c:
                    pend.pop(tk)
    if tickers:
        n_err = sum(1 for e in estados.values() if e == "error")
        estado[f"Rava · flujos {etiqueta}: {len(res)} de {len(tickers)} títulos con datos, "
               f"{n_err} páginas con error de conexión"] = ("✅" if not n_err else "⚠️") if res else "❌"
    return res

# FIN fuentes.py
