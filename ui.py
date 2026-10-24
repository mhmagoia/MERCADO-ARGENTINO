"""Estilo formal, tarjetas, formatos, gráficos base y la pestaña Resumen."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

AZUL, NARANJA, VERDE, VIOLETA, ROJO, TURQUESA = (
    "#2F80ED", "#F2994A", "#27AE60", "#9B51E0", "#EB5757", "#00A3A3")
PAL = [AZUL, NARANJA, VERDE, VIOLETA, ROJO, TURQUESA]

PCT = lambda t="": st.column_config.NumberColumn(format="%.2f%%", help=t)
NUM2 = lambda t="": st.column_config.NumberColumn(format="%.2f", help=t)
CFG = {"Precio": NUM2(), "Compra": NUM2(), "Venta": NUM2(),
       "Días": st.column_config.NumberColumn(format="%d"),
       "Duration": NUM2("Duration de Macaulay, en años."),
       "Var. diaria %": PCT(),
       "TIR Rava %": PCT("TIR que publica Rava con su cotización (para contrastar)."),
       "TNA %": PCT("Rendimiento simple anualizado (sin capitalizar)."),
       "TIR %": PCT("Tasa efectiva anual (compuesta, base 365)."),
       "TEM %": PCT("En letras en pesos = devaluación mensual de equilibrio."),
       "TC breakeven": st.column_config.NumberColumn(format="$ %.0f", help="A3500 × (1 + rend. directo)")}

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@500;600&display=swap');
html,body,.stApp,.stApp p,.stApp label,.stApp li,.stApp button p,.stApp input,.stApp textarea{
 font-family:'IBM Plex Sans',-apple-system,'Segoe UI',sans-serif!important}
.block-container{padding-top:4rem;padding-bottom:2.5rem;max-width:1280px}
.cab{border-bottom:2px solid rgba(127,127,127,.35);padding-bottom:.7rem;margin-bottom:.9rem}
.cab-t{font-family:'IBM Plex Serif',Georgia,serif;font-size:2rem;font-weight:600;letter-spacing:-.01em;line-height:1.15}
.cab-s{font-size:.9rem;opacity:.7;margin-top:.25rem}
.sec{font-size:.76rem;font-weight:600;letter-spacing:.09em;text-transform:uppercase;
 margin:1.1rem 0 .5rem;padding-bottom:.25rem;border-bottom:2px solid var(--ac,#888)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:.6rem}
.card{border:1px solid rgba(127,127,127,.30);border-left:5px solid var(--ac);border-radius:6px;
 padding:.55rem .8rem;background:rgba(127,127,127,.07);
 background:linear-gradient(135deg,color-mix(in srgb,var(--ac) 15%,transparent),rgba(127,127,127,.05))}
.card .l{font-size:.68rem;letter-spacing:.05em;text-transform:uppercase;opacity:.75}
.card .v{font-size:1.4rem;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.35}
.card .d{font-size:.78rem;font-weight:500}
.up{color:#27AE60}.down{color:#EB5757}
.stTabs [data-baseweb="tab"]{font-weight:500;outline:none!important;box-shadow:none!important;border:0!important}
@media (max-width:640px){.cab-t{font-size:1.45rem}.card .v{font-size:1.2rem}
 .block-container{padding-left:.7rem;padding-right:.7rem}}
</style>"""


def estilos():
    st.markdown(CSS, unsafe_allow_html=True)


def cabecera():
    st.markdown('<div class="cab"><div class="cab-t">Tablero de Renta Fija Argentina</div>'
                '<div class="cab-s">Letras del Tesoro, bonos soberanos y obligaciones negociables · '
                'tipo de cambio, tasas e inflación</div></div>', unsafe_allow_html=True)


def fmt(x, dec=2, pre="", suf=""):
    if x is None or pd.isna(x):
        return "s/d"
    x = round(float(x), dec) + 0.0  # evita "-0,00"
    return pre + f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".") + suf


def ult(s):
    if s is None or len(s) == 0:
        return None, None
    v = s.iloc[-1]
    d = (v / s.iloc[-2] - 1) * 100 if len(s) > 1 and s.iloc[-2] else None
    return v, d


def tarjetas(titulo, items, color):
    """Grilla de tarjetas (etiqueta, valor, variación numérica o None) con color de acento."""
    h = [f'<div class="sec" style="--ac:{color}">{titulo}</div><div class="grid">']
    for lab, val, dlt in items:
        d = ""
        if dlt is not None and not pd.isna(dlt):
            cls, flecha = ("up", "▲") if dlt >= 0 else ("down", "▼")
            d = f'<div class="d {cls}">{flecha} {fmt(abs(dlt), 2, suf="%")}</div>'
        h.append(f'<div class="card" style="--ac:{color}"><div class="l">{lab}</div>'
                 f'<div class="v">{val}</div>{d}</div>')
    st.markdown("".join(h) + "</div>", unsafe_allow_html=True)


def grafico(series, titulo, colores=None, h=320, barras=False, y=None):
    fig = go.Figure()
    for i, (nombre, s) in enumerate(series.items()):
        if s is None or len(s) == 0:
            continue
        col = (colores or {}).get(nombre, PAL[i % len(PAL)])
        if barras:
            fig.add_bar(x=s.index, y=s.values, name=nombre, marker_color=col)
        else:
            fig.add_scatter(x=s.index, y=s.values, name=nombre, mode="lines",
                            line=dict(color=col, width=2.2))
    fig.update_layout(title=dict(text=titulo, font=dict(size=15)), height=h, yaxis_title=y,
                      margin=dict(l=8, r=8, t=44, b=8), hovermode="x unified",
                      legend=dict(orientation="h", y=-0.18))
    st.plotly_chart(fig, key=titulo)


def vista_resumen(tc, tc_d, ofi, mep, ccl, blue, brecha, sup, inf_, rp, rp_d, t, bd, c, c_d,
                  im, rm, a3500, b_sup, b_inf):
    margen = lambda b: fmt((b / tc - 1) * 100, 1, suf="%") if b and tc else "s/d"
    tarjetas("Tipo de cambio", [
        ("A3500 mayorista", fmt(tc, 2, "$ "), tc_d), ("Oficial (venta)", fmt(ofi, 2, "$ "), None),
        ("MEP", fmt(mep, 2, "$ "), None), ("CCL", fmt(ccl, 2, "$ "), None),
        ("Blue", fmt(blue, 2, "$ "), None), ("Brecha CCL / oficial", fmt(brecha, 1, suf="%"), None)], AZUL)
    tarjetas("Bandas cambiarias", [
        ("Banda superior", fmt(sup, 2, "$ "), None), ("Banda inferior", fmt(inf_, 2, "$ "), None),
        ("Margen a banda superior", margen(sup), None), ("Margen a banda inferior", margen(inf_), None)],
        VIOLETA)
    tarjetas("Tasas e inflación", [
        ("TAMAR (TNA)", fmt(t, 2, suf="%"), None), ("BADLAR (TNA)", fmt(bd, 2, suf="%"), None),
        ("CER", fmt(c, 4), c_d), ("Inflación mensual INDEC", fmt(im, 1, suf="%"), None),
        ("REM 12 meses", fmt(rm, 1, suf="%"), None)], VERDE)
    tarjetas("Riesgo soberano", [("Riesgo país", fmt(rp, 0, suf=" pb"), rp_d)], ROJO)
    u365 = lambda s: s[s.index >= s.index[-1] - pd.Timedelta(days=365)] if s is not None and len(s) else s
    grafico({"A3500": u365(a3500), "Banda superior": u365(b_sup), "Banda inferior": u365(b_inf)},
            "A3500 y bandas cambiarias ($ por USD)",
            {"A3500": AZUL, "Banda superior": VIOLETA, "Banda inferior": NARANJA})

# FIN ui.py
