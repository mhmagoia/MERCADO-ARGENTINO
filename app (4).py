"""
Dashboard Letras / Mercado AR  ·  Streamlit
Fuentes (sin API key): data912 (letras, bonos, ONs) · BCRA API v4.0 (A3500, bandas, TAMAR,
BADLAR, CER, REM) · dolarapi.com (dólares) · argentinadatos.com (riesgo país, inflación).
"""
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from pathlib import Path
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import urllib3

st.set_page_config(page_title="Letras AR", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")
TZ = ZoneInfo("America/Argentina/Buenos_Aires")
HOY = datetime.now(TZ).date()

# ── Catálogos ────────────────────────────────────────────────────────────────────────────
# LECAP/BONCAP: ticker -> (fecha de emisión, TEM de capitalización). El vencimiento sale del
# ticker (S30N6 = 30/nov/2026) y el monto al vencimiento = 100 × (1+TEM)^(DAYS360/30), como en tu Excel.
# Datos: comunicado "Resultado de la licitación" de la Secretaría de Finanzas. Verificalos.
LECAPS = {
    "S30O6": ("2025-10-31", 0.0255),
    "S13N6": ("2026-06-30", 0.0210),  # emisión deducida del plazo (136 días); TEM según Rava
    "S30N6": ("2025-12-15", 0.0230),
    "T15E7": ("2025-01-31", 0.0205),
    "S29E7": ("2026-08-28", 0.0225),
    "T30A7": ("2025-10-31", 0.0255),
    "T31Y7": ("2025-12-15", 0.0240),
    "T30J7": ("2026-01-13", 0.0258),
}
# CER cupón cero (letras X.. y bonos TZX..): ticker -> (fecha de emisión, vencimiento o None si sale del ticker)
CER = {
    "X30N6": ("2025-12-15", None),
    "X29E7": ("2026-08-13", None),
    "TZXO6": ("2024-10-31", "2026-10-30"),
    "TZXY7": ("2025-12-11", "2027-05-29"),
}
MESES = dict(zip("EFMAYJLGSOND", range(1, 13)))
TIPOS = {"S": "LECAP", "T": "BONCAP", "D": "Dólar-linked", "X": "CER", "M": "TAMAR"}


def parse_ticker(tk):
    """('LECAP', 2026-11-30) a partir de 'S30N6'. Prefijos: S/T tasa fija, D dólar-linked, X CER, M TAMAR."""
    m = re.match(r"^([STDXM])(\d{2})([EFMAYJLGSOND])(\d)$", str(tk))
    if not m:
        return None, None
    try:
        return TIPOS[m[1]], date(2020 + int(m[4]), MESES[m[3]], int(m[2]))
    except ValueError:
        return TIPOS[m[1]], None


def info_ticker(tk, cers):
    if tk in cers and cers[tk][1]:
        return "CER", date.fromisoformat(cers[tk][1])
    if str(tk).startswith("TZX"):
        return "CER", None
    return parse_ticker(tk)


def days360(a, b):  # igual al DAYS360 de Excel (método US, sin casos de fin de febrero)
    d1, d2 = min(a.day, 30), b.day
    if d2 == 31 and d1 == 30:
        d2 = 30
    return (b.year - a.year) * 360 + (b.month - a.month) * 30 + d2 - d1


def monto_vto(emision, tem, vto):
    return 100 * (1 + tem) ** (days360(date.fromisoformat(emision), vto) / 30)


def rendimiento(precio, flujos):
    """TNA y TIR (decimales) de un precio contra flujos [(fecha, monto)] por el mismo VN.
    TIR = tasa efectiva anual (XIRR, base 365). TNA = rendimiento simple anualizado equivalente
    (para un solo pago coincide con (pago/precio-1)×365/días)."""
    fl = [(f, m) for f, m in flujos if f > HOY and m > 0]
    if not fl or not precio or precio <= 0:
        return None, None, None
    t = [(f - HOY).days / 365 for f, _ in fl]
    npv = lambda r: sum(m / (1 + r) ** ti for (_, m), ti in zip(fl, t)) - precio
    lo, hi = -0.9999, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if npv(mid) > 0 else (lo, mid)
    tir = (lo + hi) / 2
    pv = [m / (1 + tir) ** ti for (_, m), ti in zip(fl, t)]
    dur = sum(ti * p for ti, p in zip(t, pv)) / sum(pv)
    return ((1 + tir) ** dur - 1) / dur, tir, dur


def hab(d, n):  # n días hábiles (solo fines de semana; ignora feriados)
    return pd.Timestamp(np.busday_offset(np.datetime64(d), n, roll="backward"))


def cer_en(serie, d):
    v = serie[:pd.Timestamp(d)]
    return float(v.iloc[-1]) if len(v) else None


def precio_de(r):
    return next((float(r[c]) for c in ("c", "px_ask", "px_bid")
                 if c in r and pd.notna(r[c]) and float(r[c]) > 0), None)


COLS = {"symbol": "Ticker", "c": "Precio", "px_bid": "Compra", "px_ask": "Venta",
        "pct_change": "Var. diaria %", "v": "Volumen"}
PCT = lambda t="": st.column_config.NumberColumn(format="%.2f%%", help=t)
CFG = {"Precio": st.column_config.NumberColumn(format="%.2f"),
       "Compra": st.column_config.NumberColumn(format="%.2f"),
       "Venta": st.column_config.NumberColumn(format="%.2f"),
       "Días": st.column_config.NumberColumn(format="%d"),
       "Var. diaria %": PCT(),
       "TIR Rava %": PCT("TIR que publica Rava con su cotización (para contrastar)."),
       "TNA %": PCT("Rendimiento simple anualizado (sin capitalizar)."),
       "TIR %": PCT("Tasa efectiva anual (compuesta, base 365)."),
       "TEM %": PCT("En letras en pesos = devaluación mensual de equilibrio."),
       "TC breakeven": st.column_config.NumberColumn(format="$ %.0f", help="A3500 × (1 + rend. directo)")}
ORDEN = ["Ticker", "Tipo", "Vencimiento", "Días", "Precio", "Var. diaria %", "TNA %", "TIR %", "TIR Rava %",
         "Tasa en", "TEM %", "TC breakeven", "Compra", "Venta", "Volumen"]

# ── Estilo + modo móvil (en pantallas chicas las métricas se acomodan de a 2) ────────────
st.markdown("""<style>
.block-container{padding-top:1.2rem;padding-bottom:2rem}
@media (max-width:640px){
 .block-container{padding-left:.6rem;padding-right:.6rem}
 [data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:wrap;gap:.4rem}
 [data-testid="stColumn"],[data-testid="column"]{min-width:calc(50% - .4rem)!important;flex:1 1 calc(50% - .4rem)!important}
 [data-testid="stMetricValue"]{font-size:1.25rem}
}</style>""", unsafe_allow_html=True)

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
             {"desde": (HOY - timedelta(days=dias)).isoformat(), "hasta": HOY.isoformat(),
              "limit": 3000})
    d = pd.DataFrame(j["results"][0]["detalle"])
    d["fecha"] = pd.to_datetime(d["fecha"])
    return d.set_index("fecha")["valor"].astype(float).sort_index()


ESTADO = {}


def safe(nombre, fn, *a):
    try:
        r = fn(*a)
        ESTADO[nombre] = "✅"
        return r
    except Exception as e:
        ESTADO[nombre] = f"❌ {type(e).__name__}"
        return None


# ── Utilidades ───────────────────────────────────────────────────────────────────────────
def fmt(x, dec=2, pre="", suf=""):
    if x is None or pd.isna(x):
        return "s/d"
    x = float(x) + 0.0  # evita "-0,00"
    return pre + f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".") + suf


def ult(s):
    if s is None or len(s) == 0:
        return None, None
    v = s.iloc[-1]
    d = (v / s.iloc[-2] - 1) * 100 if len(s) > 1 and s.iloc[-2] else None
    return v, d


def metricas(items, n=4):
    for i in range(0, len(items), n):
        for col, (lab, val, dlt) in zip(st.columns(n), items[i:i + n]):
            col.metric(lab, val, dlt)


def grafico(series, titulo, h=340, barras=False):
    fig = go.Figure()
    for nombre, s in series.items():
        if s is not None and len(s):
            (fig.add_bar if barras else fig.add_scatter)(x=s.index, y=s.values, name=nombre,
                                                         **({} if barras else {"mode": "lines"}))
    fig.update_layout(title=titulo, height=h, margin=dict(l=8, r=8, t=40, b=8),
                      legend=dict(orientation="h", y=-0.2), hovermode="x unified")
    st.plotly_chart(fig)


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
    fl = [(d, m) for d, m in fl if d > HOY and m > 0]
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
    """Corta por páginas
