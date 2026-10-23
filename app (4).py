"""
Dashboard Letras / Mercado AR  ·  Streamlit
Fuentes (sin API key): data912 (letras, bonos, ONs) · BCRA API v4.0 (A3500, bandas, TAMAR,
BADLAR, CER, REM) · dolarapi.com (dólares) · argentinadatos.com (riesgo país, inflación).
"""
import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import urllib3

st.set_page_config(page_title="Letras AR", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")
TZ = ZoneInfo("America/Argentina/Buenos_Aires")
HOY = datetime.now(TZ).date()

# ── Catálogo de letras: ticker -> (fecha de emisión, TEM de capitalización) ──────────────
# El vencimiento se deduce solo del ticker (S30N6 = 30/nov/2026) y el monto al vencimiento se
# calcula igual que en tu Excel: 100 × (1+TEM)^(DAYS360/30). Los datos de cada letra nueva están en
# el comunicado "Resultado de la licitación" de la Secretaría de Finanzas ("capitaliza a una TEM de X%").
LECAPS = {
    "S30O6": ("2025-10-31", 0.0255),
    "S30N6": ("2025-12-15", 0.0230),
    "T15E7": ("2025-01-31", 0.0205),
    "S29E7": ("2026-08-28", 0.0225),
    "T30A7": ("2025-10-31", 0.0255),
    "T31Y7": ("2025-12-15", 0.0240),
    "T30J7": ("2026-01-13", 0.0258),
}
MESES = dict(zip("EFMAYJLGSOND", range(1, 13)))
TIPOS = {"S": "LECAP", "T": "BONCAP", "D": "Dólar-linked", "X": "CER", "M": "TAMAR"}


def parse_ticker(tk):
    """Devuelve (tipo, vencimiento) a partir del ticker, ej. 'S30N6' -> ('LECAP', 2026-11-30)."""
    m = re.match(r"^([STDXM])(\d{2})([EFMAYJLGSOND])(\d)$", str(tk))
    if not m:
        return None, None
    try:
        return TIPOS[m[1]], date(2020 + int(m[4]), MESES[m[3]], int(m[2]))
    except ValueError:
        return TIPOS[m[1]], None


def days360(a, b):  # igual al DAYS360 de Excel (método US, sin casos de fin de febrero)
    d1, d2 = min(a.day, 30), b.day
    if d2 == 31 and d1 == 30:
        d2 = 30
    return (b.year - a.year) * 360 + (b.month - a.month) * 30 + d2 - d1


def monto_vto(emision, tem, vto):
    return 100 * (1 + tem) ** (days360(date.fromisoformat(emision), vto) / 30)


COLS = {"symbol": "Ticker", "c": "Precio", "px_bid": "Compra", "px_ask": "Venta",
        "pct_change": "Var. diaria %", "v": "Volumen"}
CFG = {"Precio": st.column_config.NumberColumn(format="%.2f"),
       "Compra": st.column_config.NumberColumn(format="%.2f"),
       "Venta": st.column_config.NumberColumn(format="%.2f"),
       "Var. diaria %": st.column_config.NumberColumn(format="%.2f%%")}

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


def analizar_letras(notes, tc, lecaps):
    px = notes.set_index("symbol")
    filas = []
    for tk, (emi, tem) in lecaps.items():
        _, vto = parse_ticker(tk)
        if vto is None or tk not in px.index or (vto - HOY).days <= 0:
            continue
        dias, pago = (vto - HOY).days, monto_vto(emi, tem, vto)
        r = px.loc[tk]
        p = next((float(r[c]) for c in ("c", "px_ask", "px_bid")
                  if c in r and pd.notna(r[c]) and float(r[c]) > 0), None)
        if p is None:
            continue
        if p < 5:  # algunas fuentes cotizan por VN 1 en vez de VN 100
            p *= 100
        rend = pago / p - 1
        filas.append({"Letra": tk, "Vencimiento": vto.isoformat(), "Días": dias, "Precio": p,
                      "Venta": r.get("px_ask"), "Var. diaria %": r.get("pct_change"),
                      "Pago al vto": pago, "Rend. directo %": rend * 100,
                      "TNA %": rend * 365 / dias * 100,
                      "TEA %": ((1 + rend) ** (365 / dias) - 1) * 100,
                      "TEM %": ((1 + rend) ** (30 / dias) - 1) * 100,
                      "TC breakeven": tc * (1 + rend) if tc else None})
    return pd.DataFrame(filas)


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
    cer = safe("BCRA · CER", bcra_serie, ids["cer"])
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
            lecaps = {**LECAPS, **st.session_state.get("extra", {})}
            df = analizar_letras(notes, tc, lecaps)
            if df.empty:
                st.info("Ninguna letra del catálogo cotiza hoy. Revisá LECAPS en app.py.")
            else:
                st.dataframe(df.round(2), hide_index=True, column_config={**CFG,
                    "Rend. directo %": st.column_config.NumberColumn(format="%.2f%%"),
                    "TNA %": st.column_config.NumberColumn(format="%.2f%%"),
                    "TEA %": st.column_config.NumberColumn(format="%.2f%%"),
                    "TEM %": st.column_config.NumberColumn(format="%.2f%%",
                                                           help="= devaluación mensual de equilibrio"),
                    "TC breakeven": st.column_config.NumberColumn(format="$ %.0f",
                                                                  help="A3500 × (1 + rend. directo)")})
                fig = go.Figure(go.Scatter(x=df["Días"], y=df["TNA %"], mode="lines+markers+text",
                                           text=df["Letra"], textposition="top center"))
                fig.update_layout(title="Curva de letras: TNA vs días al vencimiento", height=360,
                                  xaxis_title="Días", yaxis_title="TNA %",
                                  margin=dict(l=8, r=8, t=40, b=8))
                st.plotly_chart(fig)
                st.caption("TNA/TEA con base 365 sobre el último precio operado. "
                           "TC breakeven: el A3500 al vencimiento que iguala el rendimiento de la letra.")

            o = notes[~notes["symbol"].isin(lecaps)].copy()
            pt = o["symbol"].map(parse_ticker)
            o["Tipo"] = [p[0] or "Otro" for p in pt]
            o["Vencimiento"] = [p[1].isoformat() if p[1] else "—" for p in pt]
            o["TNA / TIR"] = ["⚠️ falta cargar TEM (calculadora)" if t in ("LECAP", "BONCAP")
                              else "no calculada" for t in o["Tipo"]]
            pend = [x for x, t in zip(o["symbol"], o["Tipo"]) if t in ("LECAP", "BONCAP")]
            if pend:
                st.warning(f"Letras detectadas sin tasa cargada: {', '.join(pend)}. "
                           "Cargalas en la calculadora de abajo.")
            with st.expander("➕ Calculadora: agregar una letra nueva"):
                st.caption("Datos en el comunicado de licitación de la Secretaría de Finanzas: fecha de "
                           "emisión y 'capitaliza a una TEM de X%'. El vencimiento sale del ticker. "
                           "Queda cargada mientras no se reinicie la app; para dejarla fija, pegá la "
                           "línea que se genera dentro de LECAPS en app.py.")
                if "ultima" in st.session_state:
                    st.success(st.session_state["ultima"][0])
                    st.code(st.session_state["ultima"][1], language="python")
                with st.form("nueva_letra"):
                    tk = st.text_input("Ticker", value=pend[0] if pend else "",
                                       placeholder="ej: S13N6").upper().strip()
                    emi = st.date_input("Fecha de emisión", value=HOY)
                    tem = st.number_input("TEM de capitalización (%)", 0.0, 20.0, 2.0, 0.01)
                    ok = st.form_submit_button("Calcular y agregar")
                if ok:
                    tipo, vto = parse_ticker(tk)
                    if tipo not in ("LECAP", "BONCAP") or vto is None:
                        st.error("Ticker no reconocido. Formato esperado: S30N6 o T15E7.")
                    else:
                        st.session_state.setdefault("extra", {})[tk] = (emi.isoformat(), tem / 100)
                        pago = monto_vto(emi.isoformat(), tem / 100, vto)
                        st.session_state["ultima"] = (
                            f"{tk} agregada: vence {vto:%d/%m/%Y}, paga {pago:.4f} cada 100 VN.",
                            f'"{tk}": ("{emi.isoformat()}", {tem / 100:.4f}),')
                        st.rerun()
            with st.expander(f"Otras letras y bonos cortos en vivo ({len(o)})"):
                t = o[[c for c in COLS if c in o] + ["Tipo", "Vencimiento", "TNA / TIR"]].rename(columns=COLS)
                orden = ["Ticker", "Tipo", "Vencimiento", "Precio", "Var. diaria %", "TNA / TIR",
                         "Compra", "Venta", "Volumen"]
                st.dataframe(t[[c for c in orden if c in t]], hide_index=True, column_config=CFG)
                st.caption("Dólar-linked, CER y TAMAR dependen de variables futuras (A3500, inflación, "
                           "tasa), por eso no se calcula una tasa fija.")

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
            st.dataframe(d[[c for c in COLS if c in d]].rename(columns=COLS), hide_index=True,
                         column_config=CFG)

    with st.expander("Estado de las fuentes"):
        st.write("  \n".join(f"{v} {k}" for k, v in ESTADO.items()))
    st.caption(f"Última actualización: {datetime.now(TZ):%d/%m/%Y %H:%M:%S} (hora Argentina)")


tablero()
