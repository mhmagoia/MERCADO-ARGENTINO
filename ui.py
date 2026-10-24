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
