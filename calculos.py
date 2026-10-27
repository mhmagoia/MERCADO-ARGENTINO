"""Lógica financiera pura (sin Streamlit): catálogos, TNA/TIR y cálculo por título."""
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

TZ = ZoneInfo("America/Argentina/Buenos_Aires")


def hoy():
    return datetime.now(TZ).date()


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
    t = str(tk)
    if t.startswith("TZX") or re.fullmatch(r"TX\d{2}", t) or t in ("DICP", "PARP"):
        return "CER", None            # cupón cero (TZX…), BONCER (TX26, TX28, TX31) y Discount/Par en pesos
    if t.startswith("TZV"):
        return "Dólar-linked", None   # cupón cero atados al dólar
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
    fl = [(f, m) for f, m in flujos if f > hoy() and m > 0]
    if not fl or not precio or precio <= 0:
        return None, None, None
    t = [(f - hoy()).days / 365 for f, _ in fl]
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


ORDEN = ["Ticker", "Tipo", "Vencimiento", "Días", "Precio", "Var. diaria %", "TNA %", "TIR %", "TIR Rava %",
         "Duration", "Tasa en", "TEM %", "TC breakeven", "Compra", "Venta", "Volumen"]


def calcular(df, tc, cer_s, lecaps, cers, flujos, rava=None, fx=None):
    """Agrega Tipo, Vencimiento, TNA y TIR a cada título según cómo se pueda valuar."""
    filas, rava, fx = [], rava or {}, fx or {}
    for _, r in df.iterrows():
        tk = str(r["symbol"])
        tipo, vto = info_ticker(tk, cers)
        if vto and vto <= hoy():
            continue
        p = precio_de(r)
        f = {"Ticker": tk, "Tipo": tipo or "Bono / otro", "Vencimiento": vto.isoformat() if vto else "—",
             "Días": (vto - hoy()).days if vto else None, "Precio": p, "Var. diaria %": r.get("pct_change"),
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
            c0, c1 = cer_en(cer_s, hab(date.fromisoformat(cers[tk][0]), -10)), cer_en(cer_s, hab(hoy(), -10))
            if c0 and c1 and f["Días"] >= 15:
                fl, f["Tasa en"] = [(vto, 100 * c1 / c0)], "Real (CER constante)"
        elif p and tk in flujos:
            fl, f["Tasa en"] = flujos[tk], "Según flujos"
        elif p and tk in rava:                              # flujo de fondos de Rava + precio en vivo
            rv, usd_row = rava[tk], rava[tk]["base"] != tk
            f["TIR Rava %"] = rv["tir"]
            ult_f = max(d for d, _ in rv["flujos"])
            f["Vencimiento"], f["Días"] = ult_f.isoformat(), (ult_f - hoy()).days
            if rv["pesos"]:                                 # flujos en pesos (CER, tasa fija, dólar-linked)
                etiqueta = ("Real (CER constante)" if tipo == "CER" else "USD" if tipo == "Dólar-linked"
                            else "Pesos" if tipo in ("LECAP", "BONCAP") else ("Real (CER constante)" if rv["cer"] else "Pesos"))
                pc, tasa = (None if usd_row else p), etiqueta
            elif usd_row:                                   # ticker D/C: precio ya está en USD
                pc, tasa = p, "USD"
            else:                                           # ticker en pesos de un bono en USD
                fxv = fx.get("CCL") if tk.startswith("GD") else fx.get("MEP")
                pc, tasa = (p / fxv if fxv else None), "USD (÷ MEP/CCL)"
            if pc and 0.15 < pc / sum(m for _, m in rv["flujos"]) < 2.5:   # descarta monedas mezcladas
                fl, f["Tasa en"] = rv["flujos"], tasa
        if fl:
            tna, tir, dur = rendimiento(pc, fl)
            if tir is not None:
                f["TNA %"], f["TIR %"], f["Duration"] = tna * 100, tir * 100, dur
                if f["Tasa en"] == "Pesos":
                    rend = fl[0][1] / pc - 1
                    f["TEM %"] = ((1 + rend) ** (30 / f["Días"]) - 1) * 100
                    f["TC breakeven"] = tc * (1 + rend) if tc else None
        filas.append(f)
    out = pd.DataFrame(filas)
    for c in ("TNA %", "TIR %", "TIR Rava %", "Duration", "TEM %", "TC breakeven"):
        if c not in out:
            out[c] = None
    return out.reindex(columns=ORDEN)

# FIN calculos.py
