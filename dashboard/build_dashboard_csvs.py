#!/usr/bin/env python3
"""Build compact dashboard CSVs for CELEC SUR energy dashboard.

Does NOT replace data/generacion_unificada.csv. Paths are relative to the repo root.
"""
from __future__ import annotations

import argparse
import csv
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard"
RAW = OUT / "raw"
UNIFICADA = ROOT / "data" / "generacion_unificada.csv"
BASE = "https://generacioncsr.celec.gob.ec:8443/ords/csr"
TZ = ZoneInfo("America/Guayaquil")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# MRIDs from Angular bundle main*.js (graficasproduccion)
SERIES = [
    # central, metrica, mrid
    ("MAZAR", "caudal_m3s", 30538),
    ("MAZAR", "cota_msnm", 30031),
    ("MOLINO", "caudal_m3s", 24811),  # UI label "Caudal Amaluza"
    ("MOLINO", "cota_msnm", 24019),  # UI label "Cota Amaluza"
    ("SOPLADORA", "caudal_m3s", 90537),
    ("SOPLADORA", "cota_msnm", 90919),
    ("MSF", "caudal_m3s", 650538),
    ("MSF", "cota_msnm", 650919),
    ("CUENCA_PAUTE", "caudal_m3s", 24812),
]

PLANTS_ENER = [
    ("MAZAR", "sardommaz", "maz"),
    ("MOLINO", "sardommol", "mol"),
    ("SOPLADORA", "sardomsop", "sop"),
    ("MSF", "sardommsf", "msf"),
    ("CELEC_SUR", "sardomcsr", "csr"),
]


def fetch_json(url: str, retries: int = 3) -> dict:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json", "User-Agent": "ecu-dashboard/1.0"}
            )
            with urllib.request.urlopen(req, context=CTX, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url} ({last})")


def local_date_from_locts(loctimestamp: str) -> date:
    """CELEC returns ...T05:00:00Z for a calendar-day stamp (local midnight Ecuador)."""
    raw = loctimestamp.strip()
    if raw.endswith("Z"):
        utc = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        utc = datetime.fromisoformat(raw)
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=timezone.utc)
    return utc.astimezone(TZ).date()


def month_params(y: int, m: int) -> dict:
    last = monthrange(y, m)[1]
    if m == 12:
        fi = f"{y}-12-01T05:00:00.000Z"
        ff = f"{y+1}-01-01T04:59:59.000Z"
    else:
        fi = f"{y}-{m:02d}-01T05:00:00.000Z"
        ff = f"{y}-{m+1:02d}-01T04:59:59.000Z"
    return {
        "fechaInicio": fi,
        "fechaFin": ff,
        "fecha": f"01/{m:02d}/{y} 00:00:00",
    }


def fetch_mes_avg(mrid: int, y: int, m: int) -> list[dict]:
    p = month_params(y, m)
    p["mrid"] = str(mrid)
    url = f"{BASE}/sardomcsr/pointValuesMesAvg?" + urllib.parse.urlencode(p)
    data = fetch_json(url)
    return data.get("items") or []


def fetch_ener_mes(plant_path: str, prefix: str, y: int, m: int) -> tuple[list[dict], str]:
    fecha = f"01/{m:02d}/{y} 00:00:00"
    url = f"{BASE}/{plant_path}/{prefix}EnerMes?fecha=" + urllib.parse.quote(fecha)
    data = fetch_json(url)
    return data.get("items") or [], url


def month_iter(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1


def collect_hidrologia(start: date, end: date) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    meta: list[dict] = []
    for central, metrica, mrid in SERIES:
        for y, m in month_iter(start, end):
            url = f"{BASE}/sardomcsr/pointValuesMesAvg?mrid={mrid}&..."
            try:
                items = fetch_mes_avg(mrid, y, m)
                n_kept = 0
                for it in items:
                    val = it.get("valueedit")
                    ts = it.get("loctimestamp")
                    if val is None or ts is None:
                        continue
                    d = local_date_from_locts(str(ts))
                    if d < start or d > end:
                        continue
                    rows.append(
                        {
                            "fecha": d.isoformat(),
                            "central": central,
                            "metrica": metrica,
                            "valor": float(val),
                        }
                    )
                    n_kept += 1
                meta.append(
                    {
                        "central": central,
                        "metrica": metrica,
                        "mrid": mrid,
                        "ym": f"{y}-{m:02d}",
                        "n_items": len(items),
                        "n_kept": n_kept,
                        "ok": True,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                meta.append(
                    {
                        "central": central,
                        "metrica": metrica,
                        "mrid": mrid,
                        "ym": f"{y}-{m:02d}",
                        "ok": False,
                        "error": str(exc),
                    }
                )
            time.sleep(0.12)
    return rows, meta



ORIGEN_DIARIO = "CELEC_promedio_diario"          # pointValuesMesAvg (publicado por CELEC)
ORIGEN_HORARIO = "calculado_de_horarios"          # promedio propio de pointValues horarios
FALLBACK_DIAS = 15        # ventana reciente revisada para huecos del promedio diario
MIN_HORAS_VALIDAS = 18    # mínimo de horas con valor para aceptar un promedio calculado


def point_values_url(mrid: int, d: date) -> str:
    """pointValues horario del día local d (CELEC: 00:00 local = 05:00Z)."""
    s = datetime(d.year, d.month, d.day, 5, tzinfo=timezone.utc)
    e = s + timedelta(days=1) - timedelta(seconds=1)
    p = {
        "mrid": str(mrid),
        "fechaInicio": s.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "fechaFin": e.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "fecha": d.strftime("%d/%m/%Y 00:00:00"),
    }
    return f"{BASE}/sardomcsr/pointValues?" + urllib.parse.urlencode(p)


def fetch_point_values(mrid: int, d: date) -> list[tuple[datetime, float]]:
    """Lecturas horarias no nulas cuyo sello local cae en el día d."""
    items = fetch_json(point_values_url(mrid, d)).get("items") or []
    out = []
    for it in items:
        v, ts = it.get("valueedit"), it.get("loctimestamp")
        if v is None or ts is None:
            continue
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(TZ)
        if t.date() == d:
            out.append((t, float(v)))
    return sorted(out)


def fallback_horario(daily_rows: list[dict], end: date, n_dias: int) -> tuple[list[dict], list[dict]]:
    """Para cada serie y cada día de los últimos n_dias (hasta end) SIN promedio diario publicado,
    calcula el promedio de las lecturas horarias (pointValues). No inventa: si hay menos de
    MIN_HORAS_VALIDAS horas con valor, deja el día vacío y lo registra como 'sin_datos_CELEC'."""
    have = {(r["fecha"], r["central"], r["metrica"]) for r in daily_rows}
    rows, meta = [], []
    for central, metrica, mrid in SERIES:
        for i in range(n_dias):
            d = end - timedelta(days=i)
            if (d.isoformat(), central, metrica) in have:
                continue
            try:
                pts = fetch_point_values(mrid, d)
            except Exception as exc:  # noqa: BLE001
                meta.append({"fecha": d.isoformat(), "central": central, "metrica": metrica, "estado": "error", "error": str(exc)})
                continue
            if len(pts) >= MIN_HORAS_VALIDAS:
                val = sum(v for _, v in pts) / len(pts)
                rows.append({"fecha": d.isoformat(), "central": central, "metrica": metrica, "valor": val, "origen": ORIGEN_HORARIO})
                meta.append({"fecha": d.isoformat(), "central": central, "metrica": metrica, "estado": ORIGEN_HORARIO, "n_horas": len(pts)})
            else:
                meta.append({"fecha": d.isoformat(), "central": central, "metrica": metrica, "estado": "sin_datos_CELEC", "n_horas": len(pts)})
            time.sleep(0.1)
    return rows, meta


def write_ultima_lectura(today: date) -> None:
    """Última lectura horaria (día en curso o anterior) de Mazar y cuenca Paute -> hidrologia_ultima_lectura.json.
    Informativo: NO entra al CSV diario porque el día en curso está incompleto."""
    out = {"generado": datetime.now(TZ).isoformat(timespec="minutes"), "nota": "Lecturas horarias SCADA CELEC SUR (pointValues); día en curso parcial", "series": {}}
    for central, metrica, mrid in SERIES:
        if central not in ("MAZAR", "CUENCA_PAUTE"):
            continue
        try:
            pts = []
            for d in (today, today - timedelta(days=1)):
                pts = fetch_point_values(mrid, d)
                if pts:
                    break
            if pts:
                t, v = pts[-1]
                rec = {"fecha_hora_local": t.isoformat(), "valor": round(v, 3),
                       "promedio_horas_disponibles": round(sum(x for _, x in pts) / len(pts), 3), "n_horas": len(pts)}
                ayer = today - timedelta(days=1)
                pa = pts if t.date() == ayer else fetch_point_values(mrid, ayer)
                if pa:  # lectura de cierre del último día completo (Ecuanomía usa este valor como «cota del día»)
                    rec["cierre_ultimo_dia_completo"] = {"fecha_hora_local": pa[-1][0].isoformat(), "valor": round(pa[-1][1], 3)}
                out["series"][f"{central}_{metrica}"] = rec
        except Exception as exc:  # noqa: BLE001
            out["series"][f"{central}_{metrica}"] = {"error": str(exc)}
    prev_path = OUT / "hidrologia_ultima_lectura.json"
    useful = [s for s in out["series"].values() if "valor" in s]
    if not useful and prev_path.exists():
        print("AVISO: sin lecturas horarias nuevas; se conserva hidrologia_ultima_lectura.json")
        return
    prev_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def collect_ener_diaria_api(start: date, end: date) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    meta: list[dict] = []
    for planta, path, prefix in PLANTS_ENER:
        for y, m in month_iter(start, end):
            try:
                items, url = fetch_ener_mes(path, prefix, y, m)
                n_kept = 0
                for it in items:
                    val = it.get("valueedit")
                    ts = it.get("loctimestamp")
                    if val is None or ts is None:
                        continue
                    d = local_date_from_locts(str(ts))
                    if d < start or d > end:
                        continue
                    rows.append(
                        {
                            "fecha": d.isoformat(),
                            "planta": planta,
                            "energia_MWh": float(val),
                            "fuente": "CELEC_SUR_ORDS_EnerMes",
                            "url_origen": url,
                        }
                    )
                    n_kept += 1
                meta.append(
                    {
                        "planta": planta,
                        "ym": f"{y}-{m:02d}",
                        "n_items": len(items),
                        "n_kept": n_kept,
                        "ok": True,
                        "url": url,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                meta.append({"planta": planta, "ym": f"{y}-{m:02d}", "ok": False, "error": str(exc)})
            time.sleep(0.12)
    return rows, meta


def build_from_unificada():
    df = pd.read_csv(UNIFICADA)

    # Hourly 30d CELEC
    celec = df[(df["fuente"] == "CELEC_SUR_ORDS") & (df["metrica"] == "energia_horaria")].copy()
    celec["fecha_hora"] = pd.to_datetime(celec["fecha_hora_local"], utc=False)
    horaria = celec[["fecha_hora", "codigo_planta", "valor"]].rename(
        columns={"codigo_planta": "planta", "valor": "MWh"}
    )
    horaria["fecha_hora"] = horaria["fecha_hora"].dt.strftime("%Y-%m-%dT%H:%M:%S%z").str.replace(
        r"(\d{2})(\d{2})$", r"\1:\2", regex=True
    )
    # Fix offset format: pandas may give -0500
    horaria = horaria.sort_values(["fecha_hora", "planta"])

    # Daily sum from hourly (same window as unificada)
    tmp = celec.copy()
    tmp["fecha"] = pd.to_datetime(tmp["fecha_hora_local"]).dt.date.astype(str)
    # For end-of-day stamps at 00:00 next day belonging to previous operating day?
    # Existing collector: local stamps ~01:00 D .. 00:00 D+1 for fecha=D.
    # Sum by calendar date of the local timestamp is OK for dashboard; note in LEEME.
    diaria_h = (
        tmp.groupby(["fecha", "codigo_planta"], as_index=False)["valor"]
        .sum()
        .rename(columns={"codigo_planta": "planta", "valor": "energia_MWh"})
    )
    diaria_h["fuente"] = "suma_horaria_CELEC_SUR_ORDS"

    # CENACE mensual desde 2018
    cen = df[(df["fuente"] == "CENACE_indicadores") & (df["metrica"] == "energia_mensual")].copy()
    cen["mes"] = pd.to_datetime(cen["fecha_hora_local"]).dt.strftime("%Y-%m")
    cen = cen[cen["mes"] >= "2018-01"]
    cenace = (
        cen[["mes", "tecnologia", "valor"]]
        .rename(columns={"valor": "GWh"})
        .sort_values(["mes", "tecnologia"])
    )

    return horaria, diaria_h, cenace, celec


def write_csv(path: Path, rows: list[dict] | pd.DataFrame, fieldnames: list[str] | None = None):
    empty = (isinstance(rows, pd.DataFrame) and rows.empty) or (not isinstance(rows, pd.DataFrame) and not rows)
    if empty and path.exists() and path.stat().st_size > 80:
        print(f"AVISO: no se vacía {path.name}; se conserva el archivo anterior")
        return
    if isinstance(rows, pd.DataFrame):
        rows.to_csv(path, index=False)
        return
    if not rows:
        path.write_text(",".join(fieldnames or []) + "\n", encoding="utf-8")
        return
    fn = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fn, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _read_dicts(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size < 20:
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _merge(old: list[dict], new: list[dict], keys: list[str]) -> list[dict]:
    """Las filas nuevas pisan la misma clave; lo que no vino en esta corrida se conserva."""
    by: dict[tuple, dict] = {}
    for r in old:
        by[tuple(str(r.get(k, "")) for k in keys)] = r
    for r in new:
        by[tuple(str(r.get(k, "")) for k in keys)] = r
    return list(by.values())


def _month_start_back(today: date, n_months: int) -> date:
    y, m = today.year, today.month
    for _ in range(max(n_months, 1) - 1):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return date(y, m, 1)


def main():
    ap = argparse.ArgumentParser(description="CSV del tablero CELEC SUR")
    ap.add_argument(
        "--recent-months",
        type=int,
        default=0,
        help="Si es >0, solo consulta esos meses y los fusiona con el CSV histórico. 0 = desde 2022.",
    )
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)

    # Fechas dinámicas (antes estaban fijas en 2026-10-05 / 2026-10-04 y por eso la hidrología
    # quedaba congelada en el 4-oct aunque CELEC ya publicaba días nuevos).
    today = datetime.now(TZ).date()
    hist_start = date(2022, 1, 1)  # desde 2022: lo necesita el modelo de probabilidad de apagones (etiquetas 2022–2026)
    hist_end = today - timedelta(days=1)  # último día calendario COMPLETO; el día en curso es parcial
    fetch_start = _month_start_back(today, args.recent_months) if args.recent_months else hist_start
    if fetch_start < hist_start:
        fetch_start = hist_start

    print("Building from unificada...")
    try:
        horaria, diaria_h, cenace, celec_raw = build_from_unificada()
    except Exception as exc:  # noqa: BLE001
        print("AVISO: no se pudo leer generacion_unificada.csv:", exc)
        horaria = pd.DataFrame()
        diaria_h = pd.DataFrame(columns=["fecha", "planta", "energia_MWh", "fuente"])
        cenace = pd.DataFrame()
        celec_raw = pd.DataFrame()
    if not horaria.empty:
        write_csv(OUT / "generacion_horaria_30d.csv", horaria)
    else:
        print("AVISO: sin generación horaria nueva; se conserva generacion_horaria_30d.csv")
    if not cenace.empty:
        write_csv(OUT / "cenace_mensual_tecnologia.csv", cenace)
    else:
        print("AVISO: sin CENACE mensual nuevo; se conserva cenace_mensual_tecnologia.csv")

    print(f"Collecting hydrology daily {fetch_start}..{hist_end}...")
    hidro_rows, hidro_meta = collect_hidrologia(fetch_start, hist_end)
    for r in hidro_rows:
        r["origen"] = ORIGEN_DIARIO
    # Respaldo: días recientes sin promedio diario publicado -> promedio de datos horarios (pointValues)
    fb_rows, fb_meta = fallback_horario(hidro_rows, hist_end, FALLBACK_DIAS)
    hidro_rows.extend(fb_rows)
    hidro_meta.append({"fallback_horario": fb_meta})
    write_ultima_lectura(today)
    # dedupe, luego fusionar con la historia ya guardada (una corrida parcial no la borra)
    seen = set()
    hidro_new = []
    for r in hidro_rows:
        k = (r["fecha"], r["central"], r["metrica"])
        if k in seen:
            continue
        seen.add(k)
        hidro_new.append(r)
    hidro_ok = sum(1 for m in hidro_meta if isinstance(m, dict) and m.get("ok") is True)
    old_hidro = _read_dicts(OUT / "hidrologia_celec_sur.csv")
    if hidro_ok == 0 and not fb_rows and old_hidro:
        print("AVISO: CELEC hidrología no respondió; se conserva hidrologia_celec_sur.csv")
        hidro_dedup = old_hidro
    else:
        hidro_dedup = _merge(old_hidro, hidro_new, ["fecha", "central", "metrica"])
    hidro_dedup.sort(key=lambda r: (str(r["fecha"]), str(r["central"]), str(r["metrica"])))
    write_csv(
        OUT / "hidrologia_celec_sur.csv",
        hidro_dedup,
        ["fecha", "central", "metrica", "valor", "origen"],
    )
    (RAW / "hidro_meta.json").write_text(json.dumps(hidro_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Collecting energy daily EnerMes {fetch_start}..{hist_end}...")
    ener_rows, ener_meta = collect_ener_diaria_api(fetch_start, hist_end)
    (RAW / "ener_meta.json").write_text(json.dumps(ener_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    ener_ok = sum(1 for m in ener_meta if m.get("ok"))

    # Merge: prefer EnerMes API for history; for overlapping recent days, EnerMes is authoritative daily total
    # Also keep sum of hourly for days only in unificada if API missing
    by_key = {}
    if not diaria_h.empty:
        diaria_h = diaria_h[diaria_h["fecha"] <= hist_end.isoformat()]  # sin el día en curso (parcial)
        for r in diaria_h.to_dict("records"):
            by_key[(r["fecha"], r["planta"])] = {
                "fecha": r["fecha"],
                "planta": r["planta"],
                "energia_MWh": float(r["energia_MWh"]),
                "fuente": r["fuente"],
            }
    for r in ener_rows:
        by_key[(r["fecha"], r["planta"])] = {
            "fecha": r["fecha"],
            "planta": r["planta"],
            "energia_MWh": float(r["energia_MWh"]),
            "fuente": "CELEC_SUR_ORDS_EnerMes",
        }
    diaria_new = [{"fecha": r["fecha"], "planta": r["planta"], "energia_MWh": r["energia_MWh"]} for r in by_key.values()]
    old_diaria = _read_dicts(OUT / "generacion_diaria_celec_sur.csv")
    if ener_ok == 0 and not diaria_new and old_diaria:
        print("AVISO: CELEC energía diaria no respondió; se conserva generacion_diaria_celec_sur.csv")
        diaria_out = old_diaria
    else:
        diaria_out = _merge(old_diaria, diaria_new, ["fecha", "planta"])
    diaria_out.sort(key=lambda r: (str(r["fecha"]), str(r["planta"])))
    write_csv(OUT / "generacion_diaria_celec_sur.csv", diaria_out, ["fecha", "planta", "energia_MWh"])
    # Keep provenance sidecar (solo lo recién armado; raw/ no se publica)
    if by_key:
        write_csv(
            RAW / "generacion_diaria_con_fuente.csv",
            sorted(by_key.values(), key=lambda r: (r["fecha"], r["planta"])),
            ["fecha", "planta", "energia_MWh", "fuente"],
        )

    # referencias.csv — only sourced values
    refs = [
        {
            "clave": "capacidad_instalada_CELEC_SUR_MW",
            "valor": "2027",
            "unidad": "MW",
            "fuente": "https://www.celec.gob.ec/celecsur/produccion-en-linea-detalle/",
            "nota": "Texto institucional: Mazar+Molino+Sopladora+MSF suman 2027 MW",
        },
        {
            "clave": "capacidad_instalada_MAZAR_MW",
            "valor": "170",
            "unidad": "MW",
            "fuente": "https://www.celec.gob.ec/celecsur/",
            "nota": "Banner home CELEC SUR: GENERACIÓN 170 MW (Central Paute MAZAR)",
        },
        {
            "clave": "capacidad_instalada_MOLINO_MW",
            "valor": "1100",
            "unidad": "MW",
            "fuente": "https://www.celec.gob.ec/celecsur/",
            "nota": "Banner home CELEC SUR: GENERACIÓN 1100 MW (Central Paute MOLINO)",
        },
        {
            "clave": "capacidad_instalada_SOPLADORA_MW",
            "valor": "487",
            "unidad": "MW",
            "fuente": "https://www.celec.gob.ec/celecsur/informacion-tecnica/central-hidroelectrica-paute-sopladora/",
            "nota": "Ficha técnica: potencia de la Central es 487 MW",
        },
        {
            "clave": "capacidad_instalada_MSF_MW",
            "valor": "270",
            "unidad": "MW",
            "fuente": "https://www.celec.gob.ec/celecsur/informacion-tecnica/central-hidroelectrica-minas-san-francisco/",
            "nota": "Ficha técnica: potencia instalada de 270 MW",
        },
        {
            "clave": "cota_operacion_MAZAR_min_msnm",
            "valor": "2098",
            "unidad": "m s.n.m.",
            "fuente": "https://www.celec.gob.ec/celecsur/informacion-tecnica/central-hidroelectrica-paute-mazar/",
            "nota": "Cota mínima de operación 2.098 msnm; UI graficasproduccion título Cota Mazar min:2098",
        },
        {
            "clave": "cota_operacion_MAZAR_max_msnm",
            "valor": "2153",
            "unidad": "m s.n.m.",
            "fuente": "https://www.celec.gob.ec/celecsur/informacion-tecnica/central-hidroelectrica-paute-mazar/",
            "nota": "Cota máxima de operación 2.153 msnm; UI título max:2153",
        },
        {
            "clave": "cota_AMALUZA_MOLINO_min_msnm_UI",
            "valor": "1975",
            "unidad": "m s.n.m.",
            "fuente": "https://generacioncsr.celec.gob.ec/graficasproduccion/ (bundle main.js título Cota Amaluza)",
            "nota": "UI: min:1975 max:1991; ficha Molino menciona nivel máximo normal 1991 m.s.n.m.",
        },
        {
            "clave": "cota_AMALUZA_MOLINO_max_msnm",
            "valor": "1991",
            "unidad": "m s.n.m.",
            "fuente": "https://www.celec.gob.ec/celecsur/informacion-tecnica/central-hidroelectrica-paute-molino/",
            "nota": "Nivel máximo normal 1.991 m.s.n.m.; UI max:1991",
        },
        {
            "clave": "cota_SOPLADORA_min_msnm_UI",
            "valor": "1312",
            "unidad": "m s.n.m.",
            "fuente": "https://generacioncsr.celec.gob.ec/graficasproduccion/ (bundle main.js título Cota Sopladora)",
            "nota": "UI: min:1312 max:1318",
        },
        {
            "clave": "cota_SOPLADORA_max_msnm_UI",
            "valor": "1318",
            "unidad": "m s.n.m.",
            "fuente": "https://generacioncsr.celec.gob.ec/graficasproduccion/ (bundle main.js título Cota Sopladora)",
            "nota": "UI: min:1312 max:1318; ficha menciona Máximo maximorum cámara 1318,14",
        },
        {
            "clave": "cota_MSF_min_msnm_UI",
            "valor": "783.33",
            "unidad": "m s.n.m.",
            "fuente": "https://generacioncsr.celec.gob.ec/graficasproduccion/ (bundle main.js título Cota Minas San Francisco)",
            "nota": "UI: min:783.33 max:792.86",
        },
        {
            "clave": "cota_MSF_max_msnm_UI",
            "valor": "792.86",
            "unidad": "m s.n.m.",
            "fuente": "https://generacioncsr.celec.gob.ec/graficasproduccion/ (bundle main.js título Cota Minas San Francisco)",
            "nota": "UI: min:783.33 max:792.86",
        },
        {
            "clave": "mrid_caudal_MAZAR",
            "valor": "30538",
            "unidad": "mrid",
            "fuente": f"{BASE}/sardomcsr/pointValues",
            "nota": "Embebido en Angular bundle; endpoint pointValuesMesAvg",
        },
        {
            "clave": "mrid_cota_MAZAR",
            "valor": "30031",
            "unidad": "mrid",
            "fuente": f"{BASE}/sardomcsr/pointValues",
            "nota": "Embebido en Angular bundle",
        },
        {
            "clave": "mrid_caudal_MOLINO_Amaluza",
            "valor": "24811",
            "unidad": "mrid",
            "fuente": f"{BASE}/sardomcsr/pointValues",
            "nota": "UI etiqueta Caudal Amaluza",
        },
        {
            "clave": "mrid_cota_MOLINO_Amaluza",
            "valor": "24019",
            "unidad": "mrid",
            "fuente": f"{BASE}/sardomcsr/pointValues",
            "nota": "UI etiqueta Cota Amaluza",
        },
        {
            "clave": "mrid_caudal_SOPLADORA",
            "valor": "90537",
            "unidad": "mrid",
            "fuente": f"{BASE}/sardomcsr/pointValues",
            "nota": "",
        },
        {
            "clave": "mrid_cota_SOPLADORA",
            "valor": "90919",
            "unidad": "mrid",
            "fuente": f"{BASE}/sardomcsr/pointValues",
            "nota": "",
        },
        {
            "clave": "mrid_caudal_MSF",
            "valor": "650538",
            "unidad": "mrid",
            "fuente": f"{BASE}/sardomcsr/pointValues",
            "nota": "",
        },
        {
            "clave": "mrid_cota_MSF",
            "valor": "650919",
            "unidad": "mrid",
            "fuente": f"{BASE}/sardomcsr/pointValues",
            "nota": "",
        },
        {
            "clave": "mrid_caudal_CUENCA_PAUTE",
            "valor": "24812",
            "unidad": "mrid",
            "fuente": f"{BASE}/sardomcsr/pointValues",
            "nota": "También csrCaudCuenMesAvg (sin mrid) para promedio cuenca",
        },
        {
            "clave": "demanda_SNI_serie_compacta",
            "valor": "",
            "unidad": "",
            "fuente": "http://www.cenace.gob.ec/info-operativa/InformacionOperativa.htm",
            "nota": "NO incluida: CENACE Info Operativa es HTML/Plotly sin API REST; no hay serie de demanda en generacion_unificada.csv aparte de snapshot. No inventada.",
        },
        {
            "clave": "BNEE_potencia_nominal_sni_hidraulica_MW_julio_2026",
            "valor": "5370.65801",
            "unidad": "MW",
            "fuente": "https://arconel.gob.ec/wp-content/uploads/downloads/2026/10/BNEE_julio_2026.xls",
            "nota": "Desde generacion_unificada.csv / ARCONEL BNEE corte julio 2026",
        },
    ]
    write_csv(
        OUT / "referencias.csv",
        refs,
        ["clave", "valor", "unidad", "fuente", "nota"],
    )

    # Probe today status
    today_status = {}
    for planta, path, prefix in PLANTS_ENER:
        url = f"{BASE}/{path}/{prefix}EnerDia?fecha=" + urllib.parse.quote(today.strftime("%d/%m/%Y 00:00:00"))
        try:
            data = fetch_json(url)
            items = data.get("items") or []
            nn = sum(1 for i in items if i.get("valueedit") is not None)
            today_status[planta] = {"n": len(items), "nonnull": nn, "url": url}
        except Exception as exc:  # noqa: BLE001
            today_status[planta] = {"error": str(exc)}
        time.sleep(0.1)
    # Mazar cota today
    url = point_values_url(30031, today)
    try:
        data = fetch_json(url)
        items = data.get("items") or []
        today_status["MAZAR_cota_horaria"] = {
            "n": len(items),
            "nonnull": sum(1 for i in items if i.get("valueedit") is not None),
            "url": url,
        }
    except Exception as exc:  # noqa: BLE001
        today_status["MAZAR_cota_horaria"] = {"error": str(exc)}

    summary = {
        "built_at_local": datetime.now(TZ).isoformat(timespec="seconds"),
        "hist_start": hist_start.isoformat(),
        "fetch_start": fetch_start.isoformat(),
        "hist_end": hist_end.isoformat(),
        "hidro_meses_ok": hidro_ok,
        "energia_meses_ok": ener_ok,
        "today": today.isoformat(),
        "today_status": today_status,
        "n_hidro": len(hidro_dedup),
        "hidro_ultima_fecha": max(r["fecha"] for r in hidro_dedup) if hidro_dedup else None,
        "hidro_dias_calculados_de_horarios": sorted({r["fecha"] for r in hidro_dedup if r.get("origen") == ORIGEN_HORARIO}),
        "hidro_fallback": fb_meta,
        "n_diaria": len(diaria_out),
        "n_horaria": len(horaria),
        "n_cenace": len(cenace),
        "files": {p.name: p.stat().st_size for p in OUT.glob("*.csv")},
    }
    (RAW / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    # Si CELEC no respondió, el CSV anterior sigue en su sitio, pero la corrida no fue fresca.
    if hidro_ok == 0 and ener_ok == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
