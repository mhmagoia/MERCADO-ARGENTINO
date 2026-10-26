"""Pestaña Granos y futuros: valor de los cultivos a vencimiento y su equivalente disponible + letra."""
import calendar
from datetime import date, timedelta

import pandas as pd

from calculos import hoy
from granos_datos import COLS, cargar_futuros_csv

CULTIVOS = {"Soja": "soja", "Maíz": "maiz", "Trigo": "trigo"}
CSV_COLS = {"dolar": COLS["dlr"], "soja": COLS["soja"], "maiz": COLS["maiz"], "trigo": COLS["trigo"]}


def fin_habil(y, m):
    """Último día hábil del mes (solo fines de semana), vencimiento de los futuros DLR y agro."""
    d = date(y, m, calendar.monthrange(y, m)[1])
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def proximos_meses(n=14):
    h, out, y, m = hoy(), [], hoy().year, hoy().month
    while len(out) < n:
        if fin_habil(y, m) > h:
            out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def tabla_base(auto):
    """Tabla editable: ajustes de A3 (automáticos) y, donde falten, lo cargado en futuros.csv."""
    csv, filas, nan = cargar_futuros_csv(), [], float("nan")
    for y, m in proximos_meses():
        mes = f"{y}-{m:02d}"
        f = {"Mes": mes, **{COLS[k]: auto.get(k, {}).get((y, m), nan) for k in ("dlr", "soja", "maiz", "trigo")}}
        if csv is not None and mes in csv.index:
            for k, c in CSV_COLS.items():
                if k in csv.columns and pd.notna(csv.loc[mes, k]) and pd.isna(f[c]):
                    f[c] = float(csv.loc[mes, k])
        filas.append(f)
    return pd.DataFrame(filas)


def letra_ref(letras, venc):
    """(ticker, TNA %) de la LECAP/BONCAP en pesos con vencimiento más cercano al del futuro."""
    if letras.empty:
        return None
    d = letras.assign(dist=[abs((date.fromisoformat(v) - venc).days) for v in letras["Vencimiento"]])
    r = d.sort_values("dist").iloc[0]
    return r["Ticker"], float(r["TNA %"])


def chequeo(fut, col, disp, letras, com, iva):
    """Por mes: valor del futuro en pesos y equivalente en USD/tn de vender disponible + comprar la letra."""
    filas = []
    for _, r in fut.iterrows():
        y, m = map(int, r["Mes"].split("-"))
        venc = fin_habil(y, m)
        dias, dlr, f = (venc - hoy()).days, r[COLS["dlr"]], r[col]
        if dias <= 0 or pd.isna(dlr) or pd.isna(f) or not disp:
            continue
        pesos = f * dlr
        fila = {"Mes": r["Mes"], "Vence": venc.isoformat(), "Días": dias, "Dólar fut. ($)": dlr,
                "Futuro (USD/tn)": f, "Futuro en $/tn": pesos, "Disponible $/tn": disp,
                "Retorno implícito %": (pesos / disp - 1) * 100,
                "TNA implícita %": (pesos / disp - 1) * 365 / dias * 100}
        ref = letra_ref(letras, venc)
        if ref:
            tk, tna = ref
            interes = tna / 100 * dias / 365
            disp_vto = disp * (1 + interes)                       # pesos que tendría a vencimiento con la letra
            sin = disp_vto / dlr                                  # ese monto expresado en USD al dólar futuro
            comision = disp * interes * com / 100 * (1 + iva / 100) / dlr   # costo sobre el interés, con IVA
            neto = sin - comision
            neto_p = disp_vto - disp * interes * com / 100 * (1 + iva / 100)   # lo mismo, en pesos por tonelada
            fila.update({"Letra ref.": tk, "TNA letra %": tna, "Spread TNA (pp)": fila["TNA implícita %"] - tna,
                         "Disponible a vto ($/tn)": disp_vto, "Equivalente sin comisión (USD/tn)": sin,
                         "Comisión (USD/tn)": comision, "Equivalente neto (USD/tn)": neto,
                         "Dif. (USD/tn)": f - neto, "Dif. %": (f / neto - 1) * 100,
                         "Equivalente neto ($/tn)": neto_p, "Dif. ($/tn)": pesos - neto_p})
        filas.append(fila)
    return pd.DataFrame(filas)

# FIN granos.py
