"""Identidad visual de Consultora Agrofinanzas Magoia: CSS (claro y oscuro), íconos SVG, cabecera y marca lateral."""
import base64
from datetime import datetime
from pathlib import Path

import streamlit as st

from calculos import TZ

AQUI = Path(__file__).parent
LEMA = "Disciplina hoy, mejores decisiones mañana."
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,.stApp,.stApp p,.stApp label,.stApp li,.stApp button p,.stApp input,.stApp textarea{
 font-family:'Inter',-apple-system,'Segoe UI',sans-serif!important}
.block-container{padding-top:3.2rem;padding-bottom:2.5rem;max-width:1320px}
section[data-testid="stSidebar"]{border-right:1px solid rgba(36,87,230,.18);
 background-image:linear-gradient(180deg,rgba(36,87,230,.09),rgba(36,87,230,.02))}
.marca{text-align:center;padding:.4rem .2rem 1rem}
.marca img{width:104px;height:auto;margin-bottom:.5rem}
.marca-n{font-size:.95rem;font-weight:500;opacity:.85;line-height:1.2}
.marca-m{font-size:1.5rem;font-weight:800;color:#2457E6;line-height:1.15}
.lema{font-style:italic;font-size:.82rem;opacity:.7;text-align:center;margin-top:1.2rem}
.hero{position:relative;overflow:hidden;border-radius:16px;padding:1.5rem 1.7rem 1.25rem;margin-bottom:1rem;
 border:1px solid rgba(36,87,230,.22);background:linear-gradient(105deg,rgba(36,87,230,.17),rgba(36,87,230,.04) 62%,transparent)}
.hero-t{position:relative;z-index:2;font-size:2.1rem;font-weight:800;line-height:1.1;letter-spacing:-.02em}
.hero-t b{color:#2457E6}
.hero-s{position:relative;z-index:2;max-width:60%;margin-top:.5rem;font-size:.92rem;opacity:.8}
.hero-f{position:relative;z-index:2;margin-top:.85rem;font-size:.72rem;font-weight:600;letter-spacing:.09em;text-transform:uppercase;opacity:.6}
.hero-r{position:absolute;top:0;right:0;bottom:0;width:34%;z-index:1;background-size:cover;background-position:center;
 clip-path:polygon(26% 0,100% 0,100% 100%,0 100%)}
.hero-r.sin{background:linear-gradient(120deg,#2457E6,#0B1F4B)}
.hero::before,.hero::after{content:"";position:absolute;top:-10%;bottom:-10%;transform:skewX(-24deg);z-index:1}
.hero::before{right:31%;width:34px;background:linear-gradient(180deg,#2457E6,#1B3FA6)}
.hero::after{right:36%;width:12px;background:#5B8DEF}
.sec{display:flex;align-items:center;gap:.55rem;font-size:1.02rem;font-weight:700;margin:1.3rem 0 .65rem;color:inherit}
.sec svg{color:var(--ac,#2457E6);flex:none}
.sec::after{content:"";flex:1;height:2px;border-radius:2px;background:linear-gradient(90deg,var(--ac,#2457E6),transparent)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(172px,1fr));gap:.7rem}
.card{border:1px solid rgba(127,127,127,.28);border-left:5px solid var(--ac);border-radius:12px;padding:.65rem .85rem;
 background:rgba(127,127,127,.06);
 background:linear-gradient(135deg,color-mix(in srgb,var(--ac) 14%,transparent),rgba(127,127,127,.03));
 box-shadow:0 1px 3px rgba(11,31,75,.08)}
.card .l{display:flex;align-items:center;gap:.4rem;font-size:.68rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;opacity:.8}
.card .l svg{color:var(--ac);flex:none}
.card .v{font-size:1.5rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.35}
.card .d{display:inline-block;margin-top:.1rem;padding:.04rem .5rem;border-radius:999px;font-size:.75rem;font-weight:600}
.card .d.up{background:rgba(39,174,96,.16)}.card .d.down{background:rgba(235,87,87,.16)}
.up{color:#17A673}.down{color:#E5484D}
.spark{display:block;width:100%;height:42px;margin-top:.35rem}
.stTabs [data-baseweb="tab-list"]{gap:.35rem;padding:.3rem;border-radius:12px;background:rgba(36,87,230,.08);border:1px solid rgba(36,87,230,.2)}
.stTabs [data-baseweb="tab"]{height:auto;padding:.45rem 1.05rem;border-radius:9px;font-weight:600;outline:none!important;box-shadow:none!important;border:0!important}
.stTabs [aria-selected="true"]{background:#2457E6}
.stTabs [aria-selected="true"] p{color:#fff!important}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none}
@media (max-width:640px){.hero-t{font-size:1.45rem}.hero-s{max-width:100%}.hero-r,.hero::before,.hero::after{display:none}
 .card .v{font-size:1.25rem}.block-container{padding-left:.7rem;padding-right:.7rem}}
</style>"""

ICONOS = {  # trazos simples, heredan el color del texto
    "cambio": '<polyline points="17 4 21 8 17 12"/><line x1="3" y1="8" x2="21" y2="8"/><polyline points="7 20 3 16 7 12"/><line x1="21" y1="16" x2="3" y2="16"/>',
    "capas": '<polygon points="12 3 3 8 12 13 21 8"/><polyline points="3 13 12 18 21 13"/>',
    "porcentaje": '<line x1="19" y1="5" x2="5" y2="19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/>',
    "escudo": '<path d="M12 3 5 6v5c0 5 3 8.5 7 10 4-1.5 7-5 7-10V6z"/>',
    "banco": '<polyline points="3 10 12 4 21 10"/><line x1="5" y1="10" x2="5" y2="18"/><line x1="10" y1="10" x2="10" y2="18"/><line x1="14" y1="10" x2="14" y2="18"/><line x1="19" y1="10" x2="19" y2="18"/><line x1="3" y1="20" x2="21" y2="20"/>',
    "billete": '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/>',
    "globo": '<circle cx="12" cy="12" r="9"/><line x1="3" y1="12" x2="21" y2="12"/><path d="M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    "dolar": '<circle cx="12" cy="12" r="9"/><text x="12" y="16" text-anchor="middle" font-size="11" font-weight="700" fill="currentColor" stroke="none">$</text>',
    "tendencia": '<polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/>',
    "barras": '<line x1="6" y1="20" x2="6" y2="11"/><line x1="12" y1="20" x2="12" y2="5"/><line x1="18" y1="20" x2="18" y2="14"/>',
    "pulso": '<polyline points="3 12 7 12 10 5 14 19 17 12 21 12"/>',
    "calendario": '<rect x="3" y="5" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="16" y1="3" x2="16" y2="7"/>',
    "arriba": '<line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>',
    "abajo": '<line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>',
}


def icono(nombre, px=18):
    if nombre not in ICONOS:
        return ""
    return (f'<svg viewBox="0 0 24 24" width="{px}" height="{px}" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONOS[nombre]}</svg>')


def spark(serie, color, n=60, w=220, h=42):
    """Mini gráfico de línea (SVG) con los últimos n datos de una serie."""
    if serie is None or len(serie.dropna()) < 3:
        return ""
    s = serie.dropna().tail(n)
    lo, rng = s.min(), (s.max() - s.min()) or 1
    pts = " ".join(f"{i * w / (len(s) - 1):.1f},{h - 3 - (v - lo) / rng * (h - 6):.1f}" for i, v in enumerate(s))
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none"><polyline points="{pts}" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/></svg>')


def _b64(nombre, mime, max_kb=450):
    f = AQUI / nombre
    if not f.exists() or f.stat().st_size > max_kb * 1024:
        return None
    return f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode()


def estilos():
    st.markdown(CSS, unsafe_allow_html=True)


def cabecera():
    """Banner de la consultora. Si existe banner.jpg junto a app.py, se usa como foto a la derecha."""
    foto = _b64("banner.jpg", "image/jpeg")
    fondo = f'<div class="hero-r" style="background-image:url(\'{foto}\')"></div>' if foto else '<div class="hero-r sin"></div>'
    d = datetime.now(TZ)
    st.markdown(f'<div class="hero">{fondo}<div class="hero-t">Consultora Agrofinanzas <b>Magoia</b></div>'
                '<div class="hero-s">Mercados · Finanzas · Agro &nbsp;|&nbsp; Análisis, información y herramientas '
                'para tomar mejores decisiones</div>'
                f'<div class="hero-f">Tablero de renta fija, tasas y granos · {d.day} {MESES[d.month - 1]} {d.year}</div></div>',
                unsafe_allow_html=True)


def marca_lateral():
    logo = _b64("logo.png", "image/png")
    img = f'<img src="{logo}" alt="M">' if logo else ""
    st.markdown(f'<div class="marca">{img}<div class="marca-n">Consultora Agrofinanzas</div>'
                '<div class="marca-m">Magoia</div></div>', unsafe_allow_html=True)


def lema():
    st.markdown(f'<div class="lema">{LEMA}</div>', unsafe_allow_html=True)

# FIN estilo.py
