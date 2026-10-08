#!/usr/bin/env python3
"""Modelo propio (NO oficial): días estimados hasta (a) Mazar en cota mínima operativa y
(b) oferta de energía < demanda del SNI, por escenario hidrológico.

Entradas (todas en dashboard/ del repositorio):
  hidrologia_celec_sur.csv, generacion_diaria_celec_sur.csv  (CELEC SUR ORDS)
  demanda_sni.csv, oferta_sni_diaria.csv                     (CENACE Info Operativa)
  cenace_mensual_tecnologia.csv                              (CENACE indicadores)
  referencias.csv                                            (cotas, potencias, BNEE)
Salidas:
  modelo/curva_mazar_empirica.csv, modelo/proyeccion_escenarios.csv,
  modelo/supuestos.csv, kpi_deficit.json, kpi_deficit.html
Balance en ENERGÍA diaria (MWh/día). No modela potencia de punta horaria salvo un chequeo.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd

TZ = ZoneInfo("America/Guayaquil")
D = Path(__file__).resolve().parents[1]; OUT = D / "modelo"; OUT.mkdir(exist_ok=True)
URL_CSR = "https://generacioncsr.celec.gob.ec/graficasproduccion/ (ORDS generacioncsr.celec.gob.ec:8443/ords/csr)"
URL_MAZ = "https://www.celec.gob.ec/celecsur/informacion-tecnica/central-hidroelectrica-paute-mazar/"
URL_IO = "https://www.cenace.gob.ec/info-operativa/InformacionOperativa.htm"
URL_BNEE = "https://arconel.gob.ec/wp-content/uploads/downloads/2026/10/BNEE_julio_2026.xls"
HORIZ = 365
TRANS = 14  # días de transición del caudal actual al del escenario (SUPUESTO)
SUP = []  # supuestos / parámetros con fuente


def sup(clave, valor, unidad, tipo, fuente, nota=""):
    SUP.append(dict(clave=clave, valor=valor, unidad=unidad, tipo=tipo, fuente=fuente, nota=nota))
    return valor


# ---------------- datos ----------------
ref = pd.read_csv(D / "referencias.csv").drop_duplicates("clave").set_index("clave")
ZMIN = sup("cota_min_operativa_mazar", float(ref.loc["cota_operacion_MAZAR_min_msnm", "valor"]), "m s.n.m.", "DATO",
           URL_MAZ, "Cota mínima de operación según ficha técnica CELEC SUR")
ZMAX = float(ref.loc["cota_operacion_MAZAR_max_msnm", "valor"])
h = pd.read_csv(D / "hidrologia_celec_sur.csv", parse_dates=["fecha"]).pivot_table(index="fecha", columns=["central", "metrica"], values="valor")
g = pd.read_csv(D / "generacion_diaria_celec_sur.csv", parse_dates=["fecha"]).pivot_table(index="fecha", columns="planta", values="energia_MWh")
df = pd.DataFrame({"qin": h[("MAZAR", "caudal_m3s")], "z": h[("MAZAR", "cota_msnm")], "za": h[("MOLINO", "cota_msnm")],
                   "qcuenca": h[("CUENCA_PAUTE", "caudal_m3s")], "Emaz": g.get("MAZAR"), "Emol": g.get("MOLINO"), "Esop": g.get("SOPLADORA")})
df = df.dropna(subset=["qin", "z"])
ETA = sup("eficiencia_mazar", 0.90, "-", "SUPUESTO", "valor típico turbina+generador", "Para convertir MWh de Mazar en caudal turbinado")
df["H"] = df.z - df.za
df["qt"] = df.Emaz / 24 * 1e6 / (1000 * 9.81 * df.H * ETA)
df["qint"] = (df.qcuenca - df.qin).clip(lower=0)
df["dz2"] = (df.z.shift(-1) - df.z.shift(1)) / 2
df["net_hm3"] = (df.qin - df.qt) * 86400 / 1e6
ult = df.dropna(subset=["Emaz"]).index.max()
# última fecha con energía completa: descartar días con generación agregada parcial (día en curso)
fechas_ok = df.dropna(subset=["Emaz", "z"]).index
ult = fechas_ok.max()

# ------------- curva cota-volumen EMPÍRICA (no hay curva oficial publicada) -------------
x = df.dropna(subset=["dz2", "net_hm3"]); x = x[x.z < ZMAX - 2]
bins = list(range(int(ZMIN), int(ZMAX) + 1, 5))
curva = []
for lo in bins[:-1]:
    s = x[(x.z >= lo) & (x.z < lo + 5)]
    if len(s) >= 20:
        b = np.polyfit(s.net_hm3, s.dz2, 1)
        curva.append(dict(cota_desde=lo, cota_hasta=lo + 5, area_hm3_por_m=1 / b[0], perdida_m_dia=b[1], n_dias=len(s),
                          r=np.corrcoef(s.net_hm3, s.dz2)[0, 1]))
cv = pd.DataFrame(curva)
# extrapolación hacia abajo (sin datos < ~2107): SUPUESTO, se usa el área del tramo más bajo con datos
low = cv.iloc[0]; lo_min = cv.cota_desde.min()
for lo in bins[:-1]:
    if lo < lo_min:
        cv = pd.concat([pd.DataFrame([dict(cota_desde=lo, cota_hasta=lo + 5, area_hm3_por_m=low.area_hm3_por_m, perdida_m_dia=low.perdida_m_dia,
                                          n_dias=0, r=np.nan)]), cv])
cv = cv.sort_values("cota_desde").reset_index(drop=True)
cv["volumen_util_acum_hm3"] = (cv.area_hm3_por_m * 5).cumsum()
cv["tipo"] = np.where(cv.n_dias > 0, "ESTIMADO de datos (regresión Δcota vs caudal neto)", "SUPUESTO (extrapolado, sin datos)")
cv.to_csv(OUT / "curva_mazar_empirica.csv", index=False)
sup("curva_cota_volumen_mazar", "empírica", "hm3/m por tramo", "ESTIMADO/SUPUESTO", "modelo/curva_mazar_empirica.csv",
    "CELEC no publica la curva cota-volumen en las fuentes revisadas; se estimó con 2023–2026 (r≈0,9–0,98). Bajo ~2107 m se extrapola.")


def area(z):
    r = cv[(cv.cota_desde <= z) & (cv.cota_hasta > z)]
    r = r.iloc[0] if len(r) else (cv.iloc[0] if z < ZMIN + 1 else cv.iloc[-1])
    return r.area_hm3_por_m, r.perdida_m_dia


# ------------- energía cascada aguas abajo (Molino+Sopladora) por m3/s -------------
y = df.dropna(subset=["Emol", "Esop", "qt"]); y = y[(y.Emol + y.Esop) > 1000]
flow = (y.qt + y.qint)
k_ms = sup("k_molino_sopladora", float(((y.Emol + y.Esop).sum()) / flow.sum()), "MWh/día por m3/s", "ESTIMADO",
           URL_CSR, "Energía Molino+Sopladora / (turbinado Mazar + aporte intermedio cuenca Paute), 2023–2026")
CAP_MS = (1100 + 487) * 24
CAP_MAZ = 170 * 24

# ------------- escenarios de caudal (afluente Mazar e intermedio) -------------
hist = df.loc[: ult]
N = 14
win = hist.loc[ult - timedelta(days=N - 1): ult]
q_act, qi_act = win.qin.mean(), win.qint.mean()
qt_pol = sup("turbinado_mazar_politica", float(win.qt.mean()), "m3/s", "SUPUESTO",
             URL_CSR, f"Se mantiene el turbinado medio de Mazar de los últimos {N} días (derivado de energía y salto)")
sup("transicion_escenarios", 14, "días", "SUPUESTO", "propio", "Los escenarios seco/normal/húmedo/2024 pasan linealmente del caudal actual al del escenario en 14 días")
sup("caudal_afluente_mazar_actual", float(q_act), "m3/s", "DATO", URL_CSR, f"Promedio {win.index.min().date()}–{ult.date()}")
doy = hist.index.dayofyear


def clim(serie, q, d):
    m = np.abs(((doy - d + 182) % 365) - 182) <= 15
    return float(np.nanpercentile(serie[m], q))


# ------------- resto hidro (Coca Codo, Agoyán, San Francisco, Delsitanisagua, otras), térmica, etc. -------------
dem = pd.read_csv(D / "demanda_sni.csv", parse_dates=["fecha"])
ofe = pd.read_csv(D / "oferta_sni_diaria.csv", parse_dates=["fecha"])
mtd = dem[dem.granularidad == "mes_a_la_fecha"].sort_values("fecha").iloc[-1]
od = ofe[ofe.fecha == ofe.fecha.max()].set_index("componente").valor
f_io = ofe.fecha.max()
resto_act = od["TOTAL_hidraulica"] - od.get("Paute", 0) - od.get("Sopladora", 0) - od.get("Mazar", 0)
sup("resto_hidro_actual", float(resto_act), "MWh/día", "DATO", URL_IO, f"Hidráulica SNI − Paute − Sopladora − Mazar, día {f_io.date()} (incluye Coca Codo {od.get('Coca Codo', np.nan):.0f} MWh)")
m = pd.read_csv(D / "cenace_mensual_tecnologia.csv").pivot_table(index="mes", columns="tecnologia", values="GWh")
m.index = pd.PeriodIndex(m.index, freq="M"); nd = m.index.days_in_month
md = m.div(nd, axis=0) * 1000  # MWh/día
csr_m = g[["MAZAR", "MOLINO", "SOPLADORA"]].sum(axis=1).resample("MS").mean()
csr_m.index = csr_m.index.to_period("M")
resto_m = (md.hidroelectrica - csr_m).dropna()
resto_m = resto_m[resto_m.index >= pd.Period("2023-01", "M")]
resto_mes = resto_m.groupby(resto_m.index.month)
sup("resto_hidro_mensual_hist", f"{resto_m.index.min()}–{resto_m.index.max()}", "MWh/día", "DATO",
    "CENACE indicadores (hidro mensual) − CELEC SUR (Mazar+Molino+Sopladora)", "P10/P85 por mes calendario con 3–4 años: P10≈mínimo (2024)")

TERM_MAX = sup("termica_max_disponible", float(md.termica.max()), "MWh/día", "SUPUESTO",
               "CENACE indicadores (máximo mensual observado: " + str(md.termica.idxmax()) + ")",
               "No hay serie pública de potencia térmica DISPONIBLE; se usa la energía térmica media diaria máxima lograda (nov-2024). Nominal SNI térmica BNEE jul-2026 = 2436 MW (MCI 1155 + turbogas 837 + turbovapor 445).")
term_act = sup("termica_actual", float(od["TOTAL_termica"]), "MWh/día", "DATO", URL_IO, f"día {f_io.date()}")
IMP = sup("importacion_disponible", 456.554303 * 1000 / 365, "MWh/día", "SUPUESTO", URL_BNEE,
          "Media del año móvil a jul-2026 (456,6 GWh/año, Colombia). Capacidad nominal enlaces 650 MW pero la disponibilidad depende de Colombia/Perú.")
REN = sup("renovable_no_conv", float(mtd.produccion_MWh and ofe[ofe.componente == 'TOTAL_renovable_no_conv'].valor.iloc[-1]), "MWh/día", "DATO", URL_IO, "Eólica+solar+biomasa+biogás, último día")
MSF = sup("minas_san_francisco", float(od.get("Minas San Francisco", 0)), "MWh/día", "DATO (incluido en resto hidro)", URL_IO, "")

# ------------- demanda -------------
base = sup("demanda_base", float(mtd.energia_MWh_dia), "MWh/día", "DATO", URL_IO, f"Media del mes a la fecha (hasta {mtd.fecha.date()}), producción − exportación")
tot = md.total
anios = [a for a in range(2018, 2026) if a not in (2020, 2024)]
fac = []
for a in anios:
    s = tot[tot.index.year == a]
    if len(s) == 12:
        fac.append((s / s.mean()).values)
est = np.mean(fac, axis=0)
sup("estacionalidad_demanda", ";".join(f"{v:.3f}" for v in est), "factor mes 1..12", "ESTIMADO", "CENACE indicadores",
    "Media de (mes/promedio anual) en " + ",".join(map(str, anios)) + " (excluye 2020 pandemia y 2024 cortes)")
oct25 = tot.get(pd.Period(f"{mtd.fecha.year - 1}-{mtd.fecha.month:02d}", "M"))
G = sup("crecimiento_demanda_anual", float(base / oct25 - 1) if oct25 else 0.05, "fracción/año", "ESTIMADO", "CENACE Info Operativa vs indicadores",
        "Mes a la fecha vs mismo mes del año anterior")
m0 = mtd.fecha.month


def demanda(t, d0):
    return base * est[t.month - 1] / est[m0 - 1] * (1 + G) ** ((t - d0).days / 365)


# ------------- umbrales de cota -------------
ZCRIT = sup("cota_critica_mazar", 2115.0, "m s.n.m.", "SUPUESTO (referencia histórica)",
            "https://mazar.ecuanomia.com ; datos CELEC SUR 2023–2024",
            "Umbral PRINCIPAL de cortes: en 2023 y 2024, al cruzar ~2115 m CELEC redujo el turbinado de Mazar y siguieron los racionamientos. No es una cota oficial.")
QCAP = sup("turbinado_bajo_cota_critica", 35.0, "m3/s", "SUPUESTO",
           "https://mazar.ecuanomia.com (mismo supuesto) ; operación observada 2023–2024",
           "Bajo 2115 m el turbinado de Mazar se limita a 35 m³/s (como hizo CELEC en 2023–2024). Menos turbinado = menos energía en Paute.")

# ------------- simulación -------------
hoy = datetime.now(TZ).date()
z0 = float(hist.z.loc[ult]); d0 = ult + timedelta(days=1)
RANGO = f"{hist.index.min().year}–{hist.index.max().year}"
esc_def = {
    "actual": dict(nombre="Caudal actual", desc=f"Afluente Mazar = media últimos {N} d ({q_act:.1f} m³/s); resto hidro = nivel actual"),
    "seco": dict(nombre="Seco (P10)", desc=f"Afluente Mazar = percentil 10 histórico {RANGO} (±15 d); resto hidro = P10 mensual"),
    "estiaje_2024": dict(nombre="Réplica estiaje 2024", desc="Afluentes del mismo día de 2024 y resto hidro del mismo mes de 2024"),
    "normal": dict(nombre="Normal (P50)", desc=f"Afluente Mazar = mediana histórica {RANGO} (±15 d); resto hidro = mediana mensual"),
    "humedo": dict(nombre="Húmedo (P85)", desc=f"Afluente Mazar = percentil 85 (±15 d); resto hidro = P85 mensual"),
}
PCT = {"seco": 10, "normal": 50, "humedo": 85}


def fecha_de(d):
    return (hoy + timedelta(days=d)).isoformat() if d is not None else None


rows, res = [], {}
for k, e in esc_def.items():
    z = z0; dias_c = dias_a = dias_b = None
    for i in range(HORIZ):
        t = d0 + timedelta(days=i)
        dd = t.dayofyear
        if k == "actual":
            qin, qi, resto = q_act, qi_act, resto_act
        elif k in PCT:
            qin, qi = clim(hist.qin, PCT[k], dd), clim(hist.qint, PCT[k], dd)
            resto = float(resto_mes.quantile(PCT[k] / 100).get(t.month, resto_act))
        else:
            t24 = pd.Timestamp(2024 if t.month >= d0.month else 2025, t.month, min(t.day, 28))
            r = hist.loc[t24] if t24 in hist.index else hist.iloc[0]
            qin, qi = float(r.qin), float(r.qint)
            p = pd.Period(t24, "M"); resto = float(resto_m.get(p, resto_act))
        if k != "actual":  # transición gradual desde el estado actual (SUPUESTO: 14 días)
            w = min(i / TRANS, 1.0)
            qin = q_act * (1 - w) + qin * w; qi = qi_act * (1 - w) + qi * w; resto = resto_act * (1 - w) + resto * w
        A, c = area(z)
        qt = qt_pol if z > ZCRIT else min(qt_pol, QCAP)       # bajo 2115 m: turbinado limitado a 35 m³/s (SUPUESTO)
        if z <= ZMIN + 0.05:
            qt = min(qt, qin)                                   # en la mínima solo se turbina lo que entra
        Hh = max(z - 1985.0, 100)
        z = min(z + (qin - qt) * 86400 / 1e6 / A + c, ZMAX)
        if z < ZMIN:
            z = ZMIN; qt = min(qt, qin)
        cuenta = t.date() >= hoy
        if cuenta and dias_c is None and z <= ZCRIT:
            dias_c = (t.date() - hoy).days
        if cuenta and dias_a is None and z <= ZMIN + 0.05:
            dias_a = (t.date() - hoy).days
        Emaz = min(qt * 9.81 * Hh * ETA * 24 / 1000, CAP_MAZ)
        Ems = min(k_ms * (qt + qi), CAP_MS)
        oferta_hidro = Emaz + Ems + resto
        ofer_max = oferta_hidro + TERM_MAX + IMP + REN
        dem_t = demanda(t, d0)
        margen = ofer_max - dem_t
        if dias_b is None and margen < 0 and cuenta:
            dias_b = (t.date() - hoy).days
        rows.append(dict(escenario=k, fecha=t.date().isoformat(), cota_mazar=round(z, 2), afluente_mazar_m3s=round(qin, 1), turbinado_mazar_m3s=round(qt, 1),
                         E_paute_MWh=round(Emaz + Ems), E_resto_hidro_MWh=round(resto), termica_max_MWh=round(TERM_MAX), import_MWh=round(IMP), renov_MWh=round(REN),
                         oferta_max_MWh=round(ofer_max), demanda_MWh=round(dem_t), margen_MWh=round(margen),
                         termica_requerida_MWh=round(max(dem_t - oferta_hidro - IMP - REN, 0))))
    res[k] = dict(**e, dias_2115=dias_c, fecha_2115=fecha_de(dias_c), dias_mazar_min=dias_a, fecha_mazar_min=fecha_de(dias_a),
                  dias_deficit=dias_b, fecha_deficit=fecha_de(dias_b))
pr = pd.DataFrame(rows); pr.to_csv(OUT / "proyeccion_escenarios.csv", index=False)

# chequeo de punta (potencia), solo informativo
pmax = dem[dem.granularidad.isin(["diaria", "dia_demanda_max_historica"])].demanda_max_MW.max()
# tendencia empírica de la cota (independiente del modelo)
w = hist.z.loc[ult - timedelta(days=13): ult]
pend = float(np.polyfit(np.arange(len(w)), w.values, 1)[0])
dias_tend = int((z0 - ZMIN) / -pend) if pend < 0 else None
dias_tend_c = int((z0 - ZCRIT) / -pend) if pend < 0 and z0 > ZCRIT else None

# ------------- probabilidad de apagones (modelo logístico tipo Ecuanomía) -------------
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))
import modelo_probabilidad as mp
try:
    PROB = mp.calcular(hist, pr, hoy)
except Exception as exc:  # noqa: BLE001
    PROB = {"error": str(exc)}
    print("AVISO: modelo de probabilidad falló:", exc)
if "coeficientes" in PROB:
    sup("prob_apagones_etiquetas", "; ".join(f"{x['inicio']}→{x['fin']}" for x in PROB["periodos_apagon"]), "periodos", "DATO (prensa)",
        "El Universo / Expreso (ver modelo/logit_coeficientes.json)", "Días con apagones/racionamientos generalizados usados para etiquetar 2022–2026 (etiqueta = ese día o en los 30 siguientes)")
    sup("prob_apagones_modelo", "logit(cota, ln q7, ln exp30)", "-", "ESTIMADO",
        "modelo/logit_coeficientes.json", f"Regresión logística ajustada con {PROB['n_entrenamiento']} días ({PROB['n_positivos']} positivos) hasta {PROB['ajuste_hasta']}; mismo diseño que Ecuanomía. Solo 3 crisis: orientativo.")

# ------------- KPI -------------
UMBR = dict(verde=">60 días", amarillo="30–60 días", rojo="<30 días")


def sem(d):
    if d is None: return "verde"
    return "rojo" if d < 30 else ("amarillo" if d <= 60 else "verde")


kpi_esc = "actual"
ra = res[kpi_esc]
kd, f_kd = ra["dias_2115"], ra["fecha_2115"]
REF_ECU = dict(fuente="Ecuanomía, https://mazar.ecuanomia.com", fecha_estimacion="2026-10-06",
               texto="Ecuanomía estimó el 6 de octubre de 2026: escenario normal, Mazar en 2115 m en 23 días (29 de octubre); escenario seco en 16 días (22 de octubre); probabilidad de apagones 21 %.",
               normal=dict(dias=23, fecha="2026-10-29"), seco=dict(dias=16, fecha="2026-10-22"), prob_apagones=0.21)
kpi = dict(
    titulo="Días estimados hasta que Mazar llegue a la cota crítica (2115 m s.n.m.)",
    rotulo="Estimación propia, no oficial", generado=datetime.now(TZ).isoformat(timespec="minutes"),
    escenario_kpi=kpi_esc, dias=kd, fecha=f_kd, tipo_plazo_principal="mazar_cota_critica_2115", cota_critica=ZCRIT,
    dias_2115=kd, fecha_2115=f_kd,
    dias_mazar_min=ra["dias_mazar_min"], fecha_mazar_min=ra["fecha_mazar_min"],
    dias_deficit=ra["dias_deficit"], fecha_deficit=ra["fecha_deficit"],
    semaforo=sem(kd), regla_semaforo="Color según los días hasta que Mazar llegue a 2115 m (escenario caudal actual). Verde >60 d, amarillo 30–60 d, rojo <30 d.",
    semaforo_prudente=sem(res["seco"]["dias_2115"]), horizonte_dias=HORIZ, umbrales=UMBR,
    dias_reserva=dict(descripcion="Días de reserva antes de que los apagones sean probables",
                      dias_hasta_2115=kd, fecha_2115=f_kd,
                      primer_dia_prob_mayor_50=PROB.get("primer_dia_mayor_50") if isinstance(PROB, dict) else None),
    probabilidad_apagones=PROB,
    estado_actual=dict(fecha_hidro=ult.date().isoformat(), cota_mazar=round(z0, 2), cota_critica=ZCRIT, cota_min=ZMIN, cota_max=ZMAX,
                       volumen_util_restante_hm3=round(float(sum(area(zz)[0] for zz in np.arange(ZMIN, z0, 1.0))), 1),
                       volumen_sobre_2115_hm3=round(float(sum(area(zz)[0] for zz in np.arange(ZCRIT, z0, 1.0))), 1) if z0 > ZCRIT else 0.0,
                       afluente_mazar_dia_m3s=round(float(hist.qin.loc[ult]), 1),
                       afluente_mazar_7d_m3s=round(float(hist.qin.loc[ult - timedelta(days=6): ult].mean()), 1),
                       afluente_mazar_14d_m3s=round(q_act, 1), turbinado_mazar_14d_m3s=round(qt_pol, 1),
                       tendencia_cota_m_dia_14d=round(pend, 3), dias_a_min_por_tendencia=dias_tend, dias_a_2115_por_tendencia=dias_tend_c,
                       fecha_cenace=f_io.date().isoformat(), demanda_base_MWh_dia=round(base), termica_actual_MWh_dia=round(term_act),
                       termica_max_supuesta_MWh_dia=round(TERM_MAX), holgura_termica_MWh_dia=round(TERM_MAX - term_act),
                       demanda_punta_max_MW=pmax),
    escenarios=res, referencia_externa=REF_ECU, supuestos=SUP,
    fuentes=[URL_CSR, URL_MAZ, URL_IO, URL_BNEE, "CENACE indicadores XLSX (energía mensual por tecnología)", "https://mazar.ecuanomia.com (referencia y supuestos 2115 m / 35 m³/s)"],
    limitaciones=["Balance diario de ENERGÍA; no modela restricciones de punta, transmisión ni mantenimientos.",
                  "2115 m es un umbral de referencia histórica (2023–2024), no una cota oficial; la mínima técnica es 2098 m.",
                  "Bajo 2115 m se supone turbinado de 35 m³/s; el operador real puede decidir otra cosa.",
                  "Térmica disponible real (operativa) no es pública: se usa el máximo mensual logrado (SUPUESTO).",
                  "Coca Codo y demás hidro de filo de agua: solo energía diaria CENACE (sin caudal público); escenarios por percentiles mensuales.",
                  "CENACE Info Operativa no publica histórico diario; la serie diaria se acumula desde 2026-10-07 con cada corrida.",
                  "Turbinado de Mazar sobre 2115 m = política reciente (14 d); el operador puede ahorrar agua (alarga días) o turbinar más (acorta)."])
(D / "kpi_deficit.json").write_text(json.dumps(kpi, ensure_ascii=False, indent=1, default=str))
pd.DataFrame(SUP).to_csv(OUT / "supuestos.csv", index=False)

# ------------- historial (upsert por fecha de corrida: idempotente) -------------
hp = D / "kpi_historial.csv"
fila = dict(fecha_corrida=hoy.isoformat(), semaforo=kpi["semaforo"], semaforo_prudente=kpi["semaforo_prudente"],
            dias_2115_actual=kd, fecha_2115_actual=f_kd, dias_2115_seco=res["seco"]["dias_2115"], fecha_2115_seco=res["seco"]["fecha_2115"],
            dias_mazar_min_actual=ra["dias_mazar_min"], dias_deficit_actual=ra["dias_deficit"], fecha_deficit_actual=ra["fecha_deficit"],
            dias_deficit_seco=res["seco"]["dias_deficit"], fecha_deficit_seco=res["seco"]["fecha_deficit"],
            prob_apagones=PROB.get("prob_hoy") if isinstance(PROB, dict) else None,
            cota_mazar=round(z0, 2), fecha_hidro=ult.date().isoformat(), umbral_principal=ZCRIT)
old = pd.read_csv(hp) if hp.exists() else pd.DataFrame()
if len(old) and "umbral_principal" not in old.columns:
    old["umbral_principal"] = ZMIN   # filas anteriores: el KPI usaba 2098 m / déficit
    old = old.rename(columns={"dias_actual": "dias_deficit_actual", "fecha_actual": "fecha_deficit_actual", "dias_seco": "dias_deficit_seco", "fecha_seco": "fecha_deficit_seco"})
if len(old):  # upsert por (fecha_corrida, umbral_principal): se conserva la fila antigua con umbral 2098 del mismo día
    old = old[~((old.fecha_corrida.astype(str) == hoy.isoformat()) & (old.umbral_principal.astype(float) == ZCRIT))]
hist_kpi = pd.concat([old, pd.DataFrame([fila])], ignore_index=True)
hist_kpi.to_csv(hp, index=False)

print(json.dumps({k: {kk: v[kk] for kk in ("dias_2115", "fecha_2115", "dias_mazar_min", "fecha_mazar_min", "dias_deficit", "fecha_deficit")} for k, v in res.items()}, indent=1))
print(json.dumps(kpi["estado_actual"], indent=1, default=str)); print("KPI 2115:", kd, f_kd, kpi["semaforo"], "prudente", kpi["semaforo_prudente"])
if isinstance(PROB, dict) and "prob_hoy" in PROB:
    print("Prob apagones hoy:", PROB["prob_hoy"], "primer >50%:", PROB["primer_dia_mayor_50"], "validación:", PROB["validacion_ecuanomia"])


# ------------- componente HTML autocontenido -------------
COL = {"verde": "#1a9850", "amarillo": "#f2b01e", "rojo": "#d73027"}
def fmt(d, f, txt="no se alcanza"):
    if d is None: return f"{txt} en {HORIZ} d"
    from datetime import date as _d
    ff = _d.fromisoformat(f); return f"{d} d · {ff.day:02d}/{ff.month:02d}/{ff.year}"
def svg_cota():
    W, H, L, B = 640, 220, 46, 24
    cols = {"actual": "#333", "seco": "#d73027", "estiaje_2024": "#fc8d59", "normal": "#91bfdb", "humedo": "#4575b4"}
    pr2 = pr[pd.to_datetime(pr.fecha) <= pd.Timestamp(hoy) + pd.Timedelta(days=180)]
    n = pr2.groupby("escenario").size().max()
    def X(i): return L + i * (W - L - 10) / max(n - 1, 1)
    def Y(z): return 10 + (ZMAX - z) * (H - B - 10) / (ZMAX - ZMIN)
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Proyección cota Mazar">']
    for zz in (ZMIN, 2110, 2120, 2130, 2140, ZMAX):
        out.append(f'<line x1="{L}" x2="{W-10}" y1="{Y(zz):.1f}" y2="{Y(zz):.1f}" stroke="#ddd"/><text x="{L-4}" y="{Y(zz)+4:.1f}" font-size="10" text-anchor="end">{zz:.0f}</text>')
    out.append(f'<line x1="{L}" x2="{W-10}" y1="{Y(ZCRIT):.1f}" y2="{Y(ZCRIT):.1f}" stroke="#d73027" stroke-width="1.5"/><text x="{W-12}" y="{Y(ZCRIT)-4:.1f}" font-size="10" text-anchor="end" fill="#d73027">cota crítica {ZCRIT:.0f}</text>')
    out.append(f'<line x1="{L}" x2="{W-10}" y1="{Y(ZMIN):.1f}" y2="{Y(ZMIN):.1f}" stroke="#7a0000" stroke-dasharray="4 3"/><text x="{W-12}" y="{Y(ZMIN)-4:.1f}" font-size="10" text-anchor="end" fill="#7a0000">mínima operativa {ZMIN:.0f}</text>')
    for k, c in cols.items():
        q = pr2[pr2.escenario == k].reset_index(drop=True)
        pts = " ".join(f"{X(i):.1f},{Y(z):.1f}" for i, z in enumerate(q.cota_mazar))
        out.append(f'<polyline fill="none" stroke="{c}" stroke-width="2" points="{pts}"/>')
    for i in range(0, n, 30):
        f = pd.to_datetime(pr2.fecha.iloc[i]); out.append(f'<text x="{X(i):.1f}" y="{H-6}" font-size="10" text-anchor="middle">{f.day:02d}/{f.month:02d}</text>')
    out.append("</svg>")
    leg = " ".join(f'<span style="color:{c}">■</span> {esc_def[k]["nombre"]}' for k, c in cols.items())
    return "".join(out) + f'<div class="leg">{leg}</div>'
def svg_prob():
    if not isinstance(PROB, dict) or "prob_hoy" not in PROB: return "<p class='s'>Modelo de probabilidad no disponible hoy.</p>"
    pp = pd.read_csv(OUT / "probabilidad_apagones.csv")
    W, H, L, B = 640, 180, 40, 24
    cols = {"seco": "#d73027", "normal": "#91bfdb", "humedo": "#4575b4", "actual": "#333"}
    n = pp.groupby("escenario").size().max()
    def X(i): return L + i * (W - L - 10) / max(n - 1, 1)
    def Y(p): return 10 + (1 - p) * (H - B - 10)
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Probabilidad de apagones">']
    for p in (0, .25, .5, .75, 1):
        out.append(f'<line x1="{L}" x2="{W-10}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" stroke="{"#d73027" if p == .5 else "#ddd"}"/><text x="{L-4}" y="{Y(p)+4:.1f}" font-size="10" text-anchor="end">{int(p*100)}%</text>')
    for k, c in cols.items():
        q = pp[pp.escenario == k].reset_index(drop=True)
        if q.empty: continue
        pts = " ".join(f"{X(i):.1f},{Y(p):.1f}" for i, p in enumerate(q.prob_apagon))
        out.append(f'<polyline fill="none" stroke="{c}" stroke-width="2" points="{pts}"/>')
    q0 = pp[pp.escenario == "seco"].reset_index(drop=True)
    for i in range(0, len(q0), 7):
        f = pd.to_datetime(q0.fecha.iloc[i]); out.append(f'<text x="{X(i):.1f}" y="{H-6}" font-size="10" text-anchor="middle">{f.day:02d}/{f.month:02d}</text>')
    out.append("</svg>")
    leg = " ".join(f'<span style="color:{c}">■</span> {esc_def[k]["nombre"]}' for k, c in cols.items())
    return "".join(out) + f'<div class="leg">{leg}</div>'
filas = "".join(f"<tr><td>{v['nombre']}</td><td><b>{fmt(v['dias_2115'], v['fecha_2115'])}</b></td><td>{fmt(v['dias_mazar_min'], v['fecha_mazar_min'])}</td><td>{fmt(v['dias_deficit'], v['fecha_deficit'], 'sin déficit')}</td><td class='s'>{v['desc']}</td></tr>" for v in res.values())
sups = "".join(f"<li><b>{x['tipo']}</b> · {x['clave']}: {x['valor'] if not isinstance(x['valor'], float) else f'{x[chr(118)+chr(97)+chr(108)+chr(111)+chr(114)]:,.1f}'} {x['unidad']} — {x['nota']} <span class='s'>[{x['fuente']}]</span></li>" for x in SUP)
ea = kpi["estado_actual"]; c = COL[kpi["semaforo"]]
big = "—" if kd is None else f"{kd}"
p50 = PROB.get("primer_dia_mayor_50", {}) if isinstance(PROB, dict) else {}
def f50(e):
    v = p50.get(e) if p50 else None
    return "no supera 50 % en 45 d" if not v else fmt(v["dias"], v["fecha"])
prob_txt = (f"{PROB['prob_hoy']*100:.0f} %" if isinstance(PROB, dict) and "prob_hoy" in PROB else "—")
val = PROB.get("validacion_ecuanomia", {}) if isinstance(PROB, dict) else {}
html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KPI días hasta cota crítica de Mazar</title><style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:16px;color:#222;background:#fafafa}}
.card{{background:#fff;border-radius:12px;box-shadow:0 1px 4px #0002;padding:18px;max-width:900px;margin:auto}}
.top{{display:flex;gap:18px;align-items:center;flex-wrap:wrap}} .sem{{width:64px;height:64px;border-radius:50%;background:{c};box-shadow:0 0 0 6px {c}33}}
.big{{font-size:56px;font-weight:800;line-height:1}} .lbl{{font-size:13px;color:#555}} .tag{{display:inline-block;background:#fff3cd;border:1px solid #f2b01e;color:#7a5800;border-radius:6px;padding:2px 8px;font-size:12px;font-weight:600}}
table{{border-collapse:collapse;width:100%;margin-top:12px;font-size:14px}} td,th{{border-bottom:1px solid #eee;padding:6px;text-align:left;vertical-align:top}} .s{{color:#666;font-size:12px}}
.chips span{{display:inline-block;margin:4px 6px 0 0;padding:3px 8px;border-radius:12px;background:#f0f0f0;font-size:12px}} details{{margin-top:12px}} .leg{{font-size:12px;color:#444}}
.ref{{margin-top:12px;padding:8px 10px;border-left:4px solid #4575b4;background:#f3f7fb;font-size:13px}}
</style></head><body><div class="card">
<span class="tag">Estimación propia, no oficial</span>
<h2 style="margin:8px 0">{kpi['titulo']}</h2>
<div class="top"><div class="sem" title="{kpi['semaforo']}"></div>
<div><div class="big">{big}<span style="font-size:22px"> {'días' if kd is not None else ''}</span></div>
<div class="lbl">Escenario «{ra['nombre']}» · Mazar en <b>{ZCRIT:.0f} m s.n.m.</b> (cota crítica) · fecha estimada: <b>{f_kd or '—'}</b></div>
<div class="lbl">Secundarios: mínima operativa {ZMIN:.0f} m en <b>{fmt(ra['dias_mazar_min'], ra['fecha_mazar_min'])}</b> · oferta &lt; demanda en <b>{fmt(ra['dias_deficit'], ra['fecha_deficit'], 'sin déficit')}</b></div>
<div class="lbl">Semáforo: <b>{kpi['semaforo'].upper()}</b> · {kpi['regla_semaforo']} · Escenario seco: <b>{kpi['semaforo_prudente'].upper()}</b></div>
<div class="lbl">Probabilidad de apagones (hoy, modelo logístico): <b>{prob_txt}</b> · primer día &gt;50 %: seco <b>{f50('seco')}</b>, normal <b>{f50('normal')}</b>, húmedo <b>{f50('humedo')}</b></div></div></div>
<div class="chips"><span>Cota Mazar {ea['cota_mazar']} m ({ea['fecha_hidro']})</span><span>Volumen sobre 2115 m ≈ {ea['volumen_sobre_2115_hm3']} hm³ (estimado)</span><span>Afluente día {ea['afluente_mazar_dia_m3s']} · 7 d {ea['afluente_mazar_7d_m3s']} · 14 d {ea['afluente_mazar_14d_m3s']} m³/s</span><span>Turbinado 14 d {ea['turbinado_mazar_14d_m3s']} m³/s (35 bajo 2115 m)</span><span>Tendencia cota {ea['tendencia_cota_m_dia_14d']} m/día</span><span>Demanda {ea['demanda_base_MWh_dia']:,} MWh/día</span><span>Térmica {ea['termica_actual_MWh_dia']:,} de ~{ea['termica_max_supuesta_MWh_dia']:,} MWh/día (SUPUESTO máx.)</span></div>
<table><tr><th>Escenario</th><th>Mazar en 2115 m</th><th>Mazar en 2098 m</th><th>Oferta &lt; demanda</th><th>Supuesto</th></tr>{filas}</table>
<h4 style="margin:14px 0 4px">Cota de Mazar proyectada (180 días)</h4>{svg_cota()}
<h4 style="margin:14px 0 4px">Probabilidad de apagones generalizados (45 días)</h4>{svg_prob()}
<p class="s">Validación 6-oct-2026: modelo propio {val.get('prob_modelo_propio','—')} · coeficientes de Ecuanomía con nuestros datos {val.get('prob_coef_ecuanomia_con_nuestros_datos','—')} · publicado por Ecuanomía {val.get('prob_publicada_ecuanomia','—')}.</p>
<div class="ref"><b>Referencia externa:</b> {REF_ECU['texto']} <span class="s">[{REF_ECU['fuente']}]</span></div>
<details><summary><b>Supuestos y fuentes</b></summary><ul>{sups}</ul><p class="s">Limitaciones: {' '.join(kpi['limitaciones'])} {' '.join(PROB.get('limitaciones', [])) if isinstance(PROB, dict) else ''}</p></details>
<p class="s">Generado {kpi['generado']} (hora Ecuador, UTC−5). Datos preliminares SCADA CENACE/CELEC SUR. No es un pronóstico oficial de CENACE ni del Ministerio.</p>
</div></body></html>"""
(D / "kpi_deficit.html").write_text(html)
print("HTML ->", D / "kpi_deficit.html")
