"""
Dashboard Letras / Mercado AR  ·  Streamlit
Fuentes (sin API key): data912 (letras, bonos, ONs) · BCRA API v4.0 (A3500, bandas, TAMAR,
BADLAR, CER, REM) · dolarapi.com (dólares) · argentinadatos.com (riesgo país, inflación).
"""
import re
import unicodedata
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
       "TNA %": PCT("Rendimiento simple anualizado (sin capitalizar)."),
       "TIR %": PCT("Tasa efectiva anual (compuesta, base 365)."),
       "TEM %": PCT("En letras en pesos = devaluación mensual de equilibrio."),
       "TC breakeven": st.column_config.NumberColumn(format="$ %.0f", help="A3500 × (1 + rend. directo)")}
ORDEN = ["Ticker", "Tipo", "Vencimiento", "Días", "Precio", "Var. diaria %", "TNA %", "TIR %",
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


def calcular(df, tc, cer_s, lecaps, cers, flujos):
    """Agrega Tipo, Vencimiento, TNA y TIR a cada título según cómo se pueda valuar."""
    filas = []
    for _, r in df.iterrows():
        tk = str(r["symbol"])
        tipo, vto = info_ticker(tk, cers)
        if vto and vto <= HOY:
            continue
        p = precio_de(r)
        f = {"Ticker": tk, "Tipo": tipo or "Otro", "Vencimiento": vto.isoformat() if vto else "—",
             "Días": (vto - HOY).days if vto else None, "Precio": p, "Var. diaria %": r.get("pct_change"),
             "Tasa en": "—", "Compra": r.get("px_bid"), "Venta": r.get("px_ask"), "Volumen": r.get("v")}
        fl, pc = None, p
        if p and tk in lecaps and vto:                      # LECAP / BONCAP: pago fijo en pesos
            pc = p * 100 if p < 5 else p
            fl, f["Tasa en"] = [(vto, monto_vto(*lecaps[tk], vto))], "Pesos"
        elif p and tipo == "Dólar-linked" and vto and tc:   # paga 100 USD: precio en USD = precio / A3500
            pc = p / tc
            if 50 < pc < 150 and f["Días"] >= 15:
                fl, f["Tasa en"] = [(vto, 100.0)], "USD"
        elif p and tk in cers and vto and cer_s is not None and len(cer_s):  # CER constante hasta vto
            c0, c1 = cer_en(cer_s, hab(date.fromisoformat(cers[tk][0]), -10)), cer_en(cer_s, hab(HOY, -10))
            if c0 and c1 and f["Días"] >= 15:
                fl, f["Tasa en"] = [(vto, 100 * c1 / c0)], "Real (CER constante)"
        elif p and tk in flujos:
            fl, f["Tasa en"] = flujos[tk], "Según flujos"
        if fl:
            tna, tir, _ = rendimiento(pc, fl)
            if tir is not None:
                f["TNA %"], f["TIR %"] = tna * 100, tir * 100
                if f["Tasa en"] == "Pesos":
                    rend = fl[0][1] / pc - 1
                    f["TEM %"] = ((1 + rend) ** (30 / f["Días"]) - 1) * 100
                    f["TC breakeven"] = tc * (1 + rend) if tc else None
        filas.append(f)
    out = pd.DataFrame(filas)
    for c in ("TNA %", "TIR %", "TEM %", "TC breakeven"):
        if c not in out:
            out[c] = None
    return out.reindex(columns=ORDEN)


# ── Barra lateral ────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Opciones")
    refresco = st.select_slider("Actualizar cada", ["30s", "1m", "2m", "5m"], "1m")
    if st.button("🔄 Actualizar ahora"):
        st.cache_data.clear()
    st.caption("Los datos de mercado pueden tener demora. Esto no es asesoramiento financiero.")

st.title("📈 Letras & Mercado AR")


@st.fragment(run_every=refresco)
def tablero():
    ids = {k: None for k in BUSCAR}
    if safe("BCRA · variables", bcra_vars) is not None:
        ids = {k: var_id(k) for k in BUSCAR}
    else:
        ids = {k: FALLBACK.get(k) for k in BUSCAR}
    a3500 = safe("BCRA · A3500", bcra_serie, ids["a3500"])
    b_sup = safe("BCRA · banda sup.", bcra_serie, ids["banda_sup"])
    b_inf = safe("BCRA · banda inf.", bcra_serie, ids["banda_inf"])
    tamar = safe("BCRA · TAMAR", bcra_serie, ids["tamar"])
    badlar = safe("BCRA · BADLAR", bcra_serie, ids["badlar"])
    cer = safe("BCRA · CER", bcra_serie, ids["cer"], 1100)
    rem = safe("BCRA · REM", bcra_serie, ids["rem"])
    dol = safe("dolarapi", dolares)
    riesgo = safe("argentinadatos · riesgo país", serie_ad, "riesgo-pais")
    infl = safe("argentinadatos · inflación", serie_ad, "inflacion")
    notes = safe("data912 · letras", panel, "arg_notes")
    bonos = safe("data912 · bonos", panel, "arg_bonds")
    ons = safe("data912 · ONs", panel, "arg_corp")

    def dv(casa):
        try:
            return float(dol.loc[casa, "venta"])
        except Exception:
            return None

    tc, tc_d = ult(a3500)
    tc = tc or dv("mayorista")  # respaldo si falla el BCRA
    ofi, mep, ccl, blue = dv("oficial"), dv("bolsa"), dv("contadoconliqui"), dv("blue")
    brecha = (ccl / ofi - 1) * 100 if ccl and ofi else None
    rp, rp_d = ult(riesgo)
    t, _ = ult(tamar)
    bd, _ = ult(badlar)
    c, c_d = ult(cer)
    im = infl.iloc[-1] if infl is not None and len(infl) else None
    rm, _ = ult(rem)
    sup, _ = ult(b_sup)
    inf_, _ = ult(b_inf)

    lecaps = {**LECAPS, **st.session_state.get("extra", {})}
    cers = {**CER, **st.session_state.get("extra_cer", {})}
    flujos = safe("flujos.csv", cargar_flujos) or {}

    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Resumen", "🧾 Letras", "📊 Macro", "🏦 Bonos y ONs"])

    with tab1:
        metricas([("A3500 mayorista", fmt(tc, 2, "$ "), fmt(tc_d, 2, suf="%") if tc_d else None),
                  ("Oficial (venta)", fmt(ofi, 2, "$ "), None), ("MEP", fmt(mep, 2, "$ "), None),
                  ("CCL", fmt(ccl, 2, "$ "), None), ("Blue", fmt(blue, 2, "$ "), None),
                  ("Brecha CCL/oficial", fmt(brecha, 1, suf="%"), None),
                  ("Banda superior", fmt(sup, 2, "$ "), None), ("Banda inferior", fmt(inf_, 2, "$ "), None),
                  ("Riesgo país", fmt(rp, 0, suf=" pb"), fmt(rp_d, 2, suf="%") if rp_d else None),
                  ("TAMAR (TNA)", fmt(t, 2, suf="%"), None), ("BADLAR (TNA)", fmt(bd, 2, suf="%"), None),
                  ("CER", fmt(c, 4), fmt(c_d, 2, suf="%") if c_d else None),
                  ("Inflación mensual (INDEC)", fmt(im, 1, suf="%"), None),
                  ("REM 12m (inflación esperada)", fmt(rm, 1, suf="%"), None)])
        grafico({"A3500": a3500, "Banda sup.": b_sup, "Banda inf.": b_inf},
                "A3500 vs bandas cambiarias ($ por USD)")

    with tab2:
        if notes is None or notes.empty:
            st.warning("No se pudo leer la cotización de letras (data912).")
        else:
            df = calcular(notes, tc, cer, lecaps, cers, flujos)
            falta = [t for t, ti in zip(df["Ticker"], df["Tipo"])
                     if (ti in ("LECAP", "BONCAP") and t not in lecaps) or (ti == "CER" and t not in cers)]
            if falta:
                st.warning(f"Letras detectadas sin datos de emisión: {', '.join(falta)}. "
                           "Cargalas en la calculadora de abajo.")
            c = df.dropna(subset=["TIR %"]).sort_values("Días")
            fig = go.Figure()
            for tasa, g in c.groupby("Tasa en"):
                fig.add_scatter(x=g["Días"], y=g["TIR %"], mode="lines+markers+text", text=g["Ticker"],
                                textposition="top center", name=tasa)
            fig.update_layout(title="TIR vs días al vencimiento (cada curva en su moneda)", height=380,
                              xaxis_title="Días", yaxis_title="TIR %", legend=dict(orientation="h", y=-0.25),
                              margin=dict(l=8, r=8, t=40, b=8))
            st.plotly_chart(fig)
            st.dataframe(df.sort_values(["Tipo", "Días"]).round(2), hide_index=True,
                         column_config=CFG, column_order=ORDEN)
            st.caption("TNA = rendimiento simple anualizado. TIR = tasa efectiva anual. "
                       "Pesos: LECAP/BONCAP al pago fijo. USD: dólar-linked con precio ÷ A3500 de hoy. "
                       "Real: letras CER suponiendo el CER de hoy constante hasta el vencimiento. "
                       "En las D y CER no se calcula la tasa con menos de 15 días: el A3500 es de cierre y el "
                       "precio es de ahora, y el resultado es ruido.")

            with st.expander("➕ Calculadora: agregar una letra nueva"):
                st.caption("LECAP/BONCAP: fecha de emisión y 'capitaliza a una TEM de X%' (comunicado de "
                           "licitación). CER: solo fecha de emisión (el CER sale del BCRA). Queda cargada "
                           "hasta que se reinicie la app; para dejarla fija pegá la línea en LECAPS o CER.")
                if "ultima" in st.session_state:
                    st.success(st.session_state["ultima"][0])
                    st.code(st.session_state["ultima"][1], language="python")
                with st.form("nueva_letra"):
                    tk = st.text_input("Ticker", value=falta[0] if falta else "", placeholder="S13N6").upper().strip()
                    emi = st.date_input("Fecha de emisión", value=HOY)
                    tem = st.number_input("TEM de capitalización % (solo LECAP/BONCAP)", 0.0, 20.0, 2.0, 0.01)
                    vtxt = st.text_input("Vencimiento AAAA-MM-DD (solo si el ticker no lo trae, ej. TZX…)")
                    ok = st.form_submit_button("Agregar")
                if ok:
                    tipo, vto = info_ticker(tk, cers)
                    if vtxt.strip():
                        try:
                            vto = date.fromisoformat(vtxt.strip())
                        except ValueError:
                            vto = None
                    if tipo in ("LECAP", "BONCAP") and vto:
                        st.session_state.setdefault("extra", {})[tk] = (emi.isoformat(), tem / 100)
                        msg = f"{tk} agregada: vence {vto:%d/%m/%Y}, paga {monto_vto(emi.isoformat(), tem / 100, vto):.4f} cada 100 VN."
                        linea = f'"{tk}": ("{emi.isoformat()}", {tem / 100:.4f}),'
                    elif tipo == "CER" and vto:
                        st.session_state.setdefault("extra_cer", {})[tk] = (emi.isoformat(), vto.isoformat())
                        msg = f"{tk} agregada (CER): vence {vto:%d/%m/%Y}."
                        linea = f'"{tk}": ("{emi.isoformat()}", "{vto.isoformat()}"),'
                    else:
                        msg = None
                        st.error("No pude identificar la letra o su vencimiento. Formato: S30N6, T15E7, X29E7 "
                                 "(o completá el vencimiento).")
                    if msg:
                        st.session_state["ultima"] = (msg, linea)
                        st.rerun()

            with st.expander("🧮 Calculadora de TNA / TIR para cualquier instrumento"):
                st.caption("Para bonos u ONs con cupones: precio y flujos por el mismo VN y en la misma moneda "
                           "(usar punto decimal). Los precios del mercado local suelen ser sucios (con intereses).")
                pr = st.number_input("Precio", 0.0, 1e9, 100.0, 0.01, key="cp")
                txt = st.text_area("Flujos: una línea por pago, 'AAAA-MM-DD; monto'", "2027-03-31; 100", key="cf")
                if st.button("Calcular", key="cb"):
                    try:
                        fl = []
                        for ln in filter(None, (x.strip() for x in txt.splitlines())):
                            a_, b_ = re.split(r"[;,\t ]+", ln)[:2]
                            fl.append((date.fromisoformat(a_), float(b_)))
                        tna, tir, dur = rendimiento(pr, fl)
                        if tir is None:
                            st.error("No se pudo calcular (revisá fechas futuras y montos).")
                        else:
                            metricas([("TNA", fmt(tna * 100, 2, suf="%"), None), ("TIR", fmt(tir * 100, 2, suf="%"), None),
                                      ("Duration (años)", fmt(dur, 2), None)], 3)
                    except Exception:
                        st.error("Formato inválido. Ejemplo de línea: 2027-03-31; 100")

    with tab3:
        grafico({"Riesgo país (pb)": riesgo.tail(365) if riesgo is not None else None}, "Riesgo país")
        grafico({"Inflación mensual %": infl.tail(24) if infl is not None else None},
                "Inflación mensual (INDEC)", barras=True)
        grafico({"TAMAR": tamar, "BADLAR": badlar}, "Tasas en pesos (TNA %)")
        grafico({"CER": cer}, "CER")

    with tab4:
        for nombre, d in (("Bonos soberanos", bonos), ("Obligaciones negociables", ons)):
            st.subheader(nombre)
            if d is None or d.empty:
                st.warning("Sin datos.")
                continue
            q = st.text_input(f"Filtrar {nombre.lower()}", key=nombre, placeholder="ej: AL30, GD30, YMC")
            if q:
                d = d[d["symbol"].str.contains(q.strip(), case=False, na=False)]
            t = calcular(d, tc, cer, lecaps, cers, flujos)
            st.dataframe(t, hide_index=True, column_config=CFG, column_order=ORDEN)
        st.caption("TNA y TIR aparecen donde se pueden calcular con datos confiables: tickers cargados en "
                   "flujos.csv (ticker, fecha, monto). Usá la calculadora de la pestaña Letras para el resto.")

    with st.expander("Estado de las fuentes"):
        st.write("  \n".join(f"{v} {k}" for k, v in ESTADO.items()))
    st.caption(f"Última actualización: {datetime.now(TZ):%d/%m/%Y %H:%M:%S} (hora Argentina)")


tablero()
