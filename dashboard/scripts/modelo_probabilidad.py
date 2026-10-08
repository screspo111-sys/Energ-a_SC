#!/usr/bin/env python3
"""Probabilidad de apagones generalizados (ESTIMACIÓN PROPIA, NO OFICIAL), al estilo de Ecuanomía
(https://mazar.ecuanomia.com): regresión logística sobre
  - cota diaria de Mazar (m s.n.m.),
  - ln(caudal afluente de Mazar, media móvil 7 días),
  - ln(caudal mediano histórico de los 30 días siguientes para esa época del año).
Etiqueta diaria (2022–2026): 1 si ese día o en los 30 días siguientes hubo apagones/racionamientos
generalizados, según fechas públicas (ver PERIODOS). Los últimos 30 días se excluyen del ajuste porque
su etiqueta todavía no se conoce (no sabemos si habrá cortes en los próximos días).

Uso como módulo: calcular(hist_df, proy_df, hoy) -> dict   (lo llama modelo_deficit.py)
Salidas: modelo/etiquetas_apagones.csv, modelo/logit_coeficientes.json, modelo/probabilidad_apagones.csv
"""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(__file__).resolve().parents[1]; OUT = D / "modelo"
HORIZ_P = 45
VENTANA = 30
# Periodos públicos de racionamientos/apagones generalizados (inicio, fin inclusive, fuente)
PERIODOS = [
    ("2023-10-27", "2023-12-15", "El Universo: racionamientos desde el 27-oct-2023, suspendidos el 15-dic-2023 "
     "https://www.eluniverso.com/noticias/economia/las-crisis-energeticas-que-vivio-ecuador-durante-los-ultimos-32-anos-nota/"),
    ("2024-04-16", "2024-04-30", "El Universo (emergencia y cortes desde el 16-abr-2024) y Expreso (1-may-2024: se suspenden los cortes) "
     "https://www.expreso.ec/actualidad/cortes-luz-suspenden-5-mayo-2024-198707.html"),
    ("2024-09-23", "2024-12-19", "El Universo: 23-sep al 19-dic-2024 (fin para hogares; industria hasta 31-dic) "
     "https://www.eluniverso.com/noticias/economia/fin-apagones-ecuador-crisis-energetica-cuantas-horas-sin-luz-2024-nota/"),
]
# Referencia publicada por Ecuanomía (data.json, asof 2026-10-06), solo para validar
ECUANOMIA = dict(asof="2026-10-06", prob=0.21, fuente="https://mazar.ecuanomia.com (data.json)",
                 coef=dict(a=487.7794779714214, bc=-0.22279134883239693, bq=-1.8964002976989556, be=-2.053939575542083))


def dias_apagon() -> set:
    s = set()
    for a, b, _ in PERIODOS:
        for t in pd.date_range(a, b):
            s.add(t.normalize())
    return s


def clim_exp30(qin: pd.Series) -> np.ndarray:
    """Mediana histórica (todas las fechas a ±7 días del día del año) del caudal medio de los 30 días siguientes."""
    fwd = qin[::-1].rolling(VENTANA, min_periods=VENTANA).mean()[::-1].shift(-1)  # media de t+1..t+30
    fwd = fwd.dropna(); doy = fwd.index.dayofyear.values
    out = np.empty(366)
    for d in range(1, 367):
        dist = np.abs(((doy - d + 183) % 366) - 183)
        out[d - 1] = float(np.median(fwd.values[dist <= 7]))
    return out


def features(c, q7, doy, exp30):
    return np.column_stack([np.ones(len(c)), c, np.log(np.maximum(q7, 1.0)), np.log(exp30[np.asarray(doy) - 1])])


def fit_logit(X, y, l2=1e-4, it=100):
    mu, sd = X[:, 1:].mean(0), X[:, 1:].std(0)
    Z = np.column_stack([X[:, 0], (X[:, 1:] - mu) / sd])
    w = np.zeros(Z.shape[1]); R = np.eye(Z.shape[1]) * l2; R[0, 0] = 0
    for _ in range(it):
        p = 1 / (1 + np.exp(-Z @ w)); W = p * (1 - p)
        H = Z.T @ (Z * W[:, None]) + R; g = Z.T @ (y - p) - R @ w
        step = np.linalg.solve(H, g); w += step
        if np.abs(step).max() < 1e-9: break
    b = w[1:] / sd; a = w[0] - (b * mu).sum()   # coeficientes en escala original
    return np.r_[a, b]


def prob(beta, X):
    return 1 / (1 + np.exp(-(X @ beta)))


def calcular(hist: pd.DataFrame, proy: pd.DataFrame, hoy: date, escenarios=("seco", "normal", "humedo", "actual")) -> dict:
    """hist: index fecha diario, columnas qin (afluente Mazar m3/s) y z (cota m s.n.m.).
    proy: modelo/proyeccion_escenarios.csv (escenario, fecha, cota_mazar, afluente_mazar_m3s)."""
    h = hist[["qin", "z"]].dropna().asfreq("D")
    h["q7"] = h.qin.rolling(7, min_periods=5).mean()
    exp30 = clim_exp30(h.qin.interpolate(limit=3))
    ap = dias_apagon()
    idx = h.index
    lab = np.array([any((t + pd.Timedelta(days=k)) in ap for k in range(VENTANA + 1)) for t in idx], dtype=float)
    ult = h.dropna().index.max()
    corte = ult - pd.Timedelta(days=VENTANA)   # etiquetas conocidas solo hasta aquí
    m = (~h.q7.isna() & ~h.z.isna() & (idx >= "2022-01-01") & (idx <= corte)).values
    X = features(h.z.values[m], h.q7.values[m], idx.dayofyear.values[m], exp30)
    y = lab[m]
    beta = fit_logit(X, y)
    p_in = prob(beta, X)
    # métricas de ajuste (dentro de muestra)
    auc = None
    pos, neg = p_in[y == 1], p_in[y == 0]
    if len(pos) and len(neg):
        auc = float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())
    alto = p_in > 0.2
    prec20 = float(y[alto].mean()) if alto.any() else None
    et = pd.DataFrame({"fecha": idx.date, "cota_mazar": h.z.values, "afluente_m3s": h.qin.values, "q7_m3s": h.q7.round(2).values,
                       "exp30_m3s": exp30[idx.dayofyear.values - 1].round(2), "apagon_ese_dia": [t in ap for t in idx],
                       "etiqueta_apagon_0_30d": lab.astype(int), "usado_en_ajuste": m,
                       "prob_modelo": np.round(prob(beta, features(h.z.values, h.q7.values, idx.dayofyear.values, exp30)), 4)})
    et.to_csv(OUT / "etiquetas_apagones.csv", index=False)

    # validación vs Ecuanomía (6-oct-2026): nuestro modelo y sus coeficientes con NUESTROS datos
    val = {}
    tv = pd.Timestamp(ECUANOMIA["asof"])
    if tv in h.index and not np.isnan(h.q7.loc[tv]):
        xv = features(np.array([h.z.loc[tv]]), np.array([h.q7.loc[tv]]), [tv.dayofyear], exp30)
        ce = ECUANOMIA["coef"]; be = np.array([ce["a"], ce["bc"], ce["bq"], ce["be"]])
        val = dict(fecha=ECUANOMIA["asof"], cota=round(float(h.z.loc[tv]), 2), q7=round(float(h.q7.loc[tv]), 2),
                   exp30=round(float(exp30[tv.dayofyear - 1]), 2), prob_modelo_propio=round(float(prob(beta, xv)[0]), 3),
                   prob_coef_ecuanomia_con_nuestros_datos=round(float(prob(be, xv)[0]), 3),
                   prob_publicada_ecuanomia=ECUANOMIA["prob"], fuente=ECUANOMIA["fuente"])

    # hoy (último dato observado)
    x0 = features(np.array([h.z.loc[ult]]), np.array([h.q7.loc[ult]]), [ult.dayofyear], exp30)
    p_hoy = float(prob(beta, x0)[0])

    # proyección diaria 45 días por escenario
    rows, primer50 = [], {}
    obs_q = h.qin.loc[ult - pd.Timedelta(days=6): ult]
    for esc in escenarios:
        q = proy[proy.escenario == esc].copy()
        if q.empty: continue
        q["fecha"] = pd.to_datetime(q.fecha); q = q.set_index("fecha").sort_index()
        serie = pd.concat([obs_q, q.afluente_mazar_m3s])
        q7p = serie.rolling(7, min_periods=5).mean().loc[q.index]
        q = q[(q.index.date >= hoy) & (q.index.date < hoy + timedelta(days=HORIZ_P))]
        q7p = q7p.loc[q.index]
        pp = prob(beta, features(q.cota_mazar.values, q7p.values, q.index.dayofyear.values, exp30))
        primer50[esc] = None
        for t, c, a7, p in zip(q.index, q.cota_mazar.values, q7p.values, pp):
            rows.append(dict(escenario=esc, fecha=t.date().isoformat(), cota_mazar=round(float(c), 2), q7_m3s=round(float(a7), 1),
                             exp30_m3s=round(float(exp30[t.dayofyear - 1]), 1), prob_apagon=round(float(p), 4)))
            if primer50[esc] is None and p > 0.5:
                primer50[esc] = dict(dias=(t.date() - hoy).days, fecha=t.date().isoformat())
    pp_df = pd.DataFrame(rows); pp_df.to_csv(OUT / "probabilidad_apagones.csv", index=False)
    res = dict(
        rotulo="Estimación propia, no oficial",
        metodo="Regresión logística (IRLS, L2 mínima) sobre cota Mazar, ln(afluente media 7 d), ln(mediana histórica del afluente de los 30 días siguientes, ±7 días del día del año). "
               "Etiqueta = apagones generalizados ese día o en los 30 siguientes.",
        coeficientes=dict(a=float(beta[0]), b_cota=float(beta[1]), b_ln_q7=float(beta[2]), b_ln_exp30=float(beta[3])),
        periodos_apagon=[dict(inicio=a, fin=b, fuente=f) for a, b, f in PERIODOS],
        n_dias_apagon=len(ap), n_entrenamiento=int(m.sum()), n_positivos=int(y.sum()),
        ajuste_hasta=corte.date().isoformat(), auc_en_muestra=auc, precision_cuando_p_mayor_20=prec20,
        fecha_dato=ult.date().isoformat(), prob_hoy=round(p_hoy, 3),
        cota_hoy=round(float(h.z.loc[ult]), 2), q7_hoy=round(float(h.q7.loc[ult]), 2), exp30_hoy=round(float(exp30[ult.dayofyear - 1]), 2),
        primer_dia_mayor_50=primer50, horizonte_dias=HORIZ_P, validacion_ecuanomia=val,
        prob_max_45d={e: float(pp_df[pp_df.escenario == e].prob_apagon.max()) for e in pp_df.escenario.unique()},
        limitaciones=["Solo 3 crisis (2023, abril 2024, sep–dic 2024) para aprender: muy pocos eventos, la probabilidad es orientativa.",
                      "Ajuste y métricas dentro de muestra (sin validación fuera de muestra).",
                      "No incluye Coca Codo, térmicas, importaciones ni decisiones del Gobierno; solo el estado hidrológico de Mazar."])
    (OUT / "logit_coeficientes.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    return res


if __name__ == "__main__":
    import sys
    sys.exit("Se ejecuta desde modelo_deficit.py (necesita la proyección de escenarios).")
