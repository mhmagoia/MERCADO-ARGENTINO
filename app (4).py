"""
Dashboard Letras & Mercado AR (Streamlit).
Archivos: app.py, calculos.py, fuentes.py, ui.py, vistas.py, requirements.txt, flujos.csv
"""
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image

_ICONO = Path(__file__).with_name("icono.png")
st.set_page_config(page_title="Consultora Agrofinanzas Magoia", layout="wide", initial_sidebar_state="auto",
                   page_icon=Image.open(_ICONO) if _ICONO.exists() else None)

try:
    from calculos import CER, LECAPS, TZ
    from fuentes import (BUSCAR, FALLBACK, bcra_serie, bcra_vars, cargar_flujos, dolares,
                         panel, serie_ad, var_id)
    from bonos import vista_bonos
    from estilo import cabecera, estilos, lema, marca_lateral
    from granos_vista import vista_granos
    from icono_movil import icono_movil
    from macro import vista_macro
    from ui import ult, vista_resumen
    from vistas import vista_letras
    from mundo_vista import vista_mundo
except ImportError as e:
    st.error(f"Falta subir o actualizar un archivo del repositorio ({e}). Subí todos los archivos del ZIP, no solo algunos.")
    st.stop()

import importlib  # noqa: E402

REQUERIDAS = {n: 1 for n in ("calculos", "fuentes", "ui", "estilo", "vistas", "macro", "bonos", "granos", "granos_datos",
                             "granos_tablas", "granos_vista", "icono_movil", "mundo_datos", "mundo_real", "mundo_vista")}
viejos = [n for n, v in REQUERIDAS.items() if getattr(importlib.import_module(n), "VERSION", 0) < v]
if viejos:
    st.error("Hay archivos desactualizados en el repositorio: " + ", ".join(f"{n}.py" for n in viejos)
             + ". Subí la versión nueva de cada uno (el ZIP los trae todos).")
    st.stop()

estilos()
icono_movil()
ESTADO = {}


def safe(nombre, fn, *a):
    try:
        r = fn(*a)
        ESTADO[nombre] = "❌ sin datos" if getattr(r, "empty", False) else "✅"
        return r
    except Exception as e:
        ESTADO[nombre] = f"❌ {type(e).__name__}"
        return None


# ── Barra lateral ────────────────────────────────────────────────────────────────────────
with st.sidebar:
    marca_lateral()
    st.header("Opciones")
    refresco = st.select_slider("Actualizar cada", ["30s", "1m", "2m", "5m"], "1m")
    if st.button("Actualizar ahora"):
        st.cache_data.clear()
    st.caption("Los datos de mercado pueden tener demora. Esto no es asesoramiento financiero.")
    lema()

cabecera()


@st.fragment(run_every=refresco)
def tablero():
    ESTADO.clear()
    ids = {k: None for k in BUSCAR}
    if safe("BCRA · variables", bcra_vars) is not None:
        ids = {k: var_id(k) for k in BUSCAR}
    else:
        ids = {k: FALLBACK.get(k) for k in BUSCAR}
    a3500 = safe("BCRA · A3500", bcra_serie, ids["a3500"], 1100)
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

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Resumen", "Letras", "Macro", "Bonos y ONs", "Granos y futuros", "Agro mundial"])
    with tab1:
        vista_resumen(tc, tc_d, ofi, mep, ccl, blue, brecha, sup, inf_, rp, rp_d, t, bd, c, c_d,
                      im, rm, a3500, b_sup, b_inf, riesgo)
    with tab2:
        vista_letras(notes, bonos, tc, cer, lecaps, cers, flujos, mep, ccl, ESTADO)
    with tab3:
        vista_macro(a3500, cer, riesgo, infl, tamar, badlar)
    with tab4:
        vista_bonos(bonos, ons, tc, cer, lecaps, cers, flujos, mep, ccl, ESTADO)
    with tab5:
        vista_granos(notes, bonos, tc, cer, lecaps, cers, flujos, safe)
    with tab6:
        vista_mundo(safe)

    with st.expander("Estado de las fuentes"):
        for k, v in ESTADO.items():
            st.write(f"{v.replace('✅', 'OK').replace('⚠️', 'Aviso').replace('❌', 'Error')} · {k}")
    st.caption(f"Última actualización: {datetime.now(TZ):%d/%m/%Y %H:%M:%S} (hora Argentina) · Consultora Agrofinanzas Magoia · Gestión agropecuaria integral")


tablero()

# FIN app.py
