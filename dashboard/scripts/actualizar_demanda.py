#!/usr/bin/env python3
"""Actualiza demanda SNI y oferta diaria por central desde CENACE Información Operativa.

Idempotente: archiva el HTML del día (raw/cenace_infoop/AAAAMMDD_HHMM.html), hace
upsert por (fecha, granularidad) en demanda_sni.csv y por (fecha, componente) en
oferta_sni_diaria.csv. Re-procesa todos los HTML archivados (así reconstruye la
serie diaria aunque falle un día). Además agrega el histórico MENSUAL de CENACE
(cenace_mensual_tecnologia.csv, indicadores XLSX) como demanda proxy.

Uso:  python dashboard/scripts/actualizar_demanda.py [--no-download]
"""
from __future__ import annotations
import argparse, calendar, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd, requests, urllib3

sys.path.insert(0, str(Path(__file__).parent))
import cenace_infoop as ci

urllib3.disable_warnings()
TZ = ZoneInfo("America/Guayaquil")
DASH = Path(__file__).resolve().parents[1]
RAW = DASH / "raw" / "cenace_infoop"
URL_IND = "https://www.cenace.gob.ec/ (XLSX público de indicadores: energía neta por tecnología; ver scripts/cenace_indicadores.py)"


def descargar():
    RAW.mkdir(parents=True, exist_ok=True)
    r = requests.get(ci.URL, timeout=90, verify=False, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    p = RAW / (datetime.now(TZ).strftime("%Y%m%d_%H%M") + ".html")
    p.write_bytes(r.content)
    return p


def filas_de_html(p: Path):
    h = p.read_text(encoding="utf-8", errors="ignore")
    r = ci.parse(h)
    ts = datetime.strptime(p.stem, "%Y%m%d_%H%M").replace(tzinfo=TZ).isoformat()
    dem, ofe = [], []
    d = r.get("diaria")
    if d and d.get("fecha"):
        f = d["fecha"].isoformat()
        dem.append(dict(fecha=f, granularidad="diaria", energia_MWh_dia=d["produccion_total"] - d.get("exportacion", 0),
                        produccion_MWh=d["produccion_total"], exportacion_MWh=d.get("exportacion"),
                        importacion_MWh=d.get("importacion"), demanda_max_MW=d.get("demanda_max_MW"),
                        hora_demanda_max=d.get("hora_max"), demanda_min_MW=d.get("demanda_min_MW"),
                        n_dias=1, fuente="CENACE Información Operativa (pestaña diaria, SCADA preliminar)",
                        url=ci.URL, consultado=ts))
        comp = dict(d["plantas"]); comp.update({"TOTAL_hidraulica": d["hidraulica"], "TOTAL_termica": d["termica"],
                    "TOTAL_renovable_no_conv": d["renovable_no_conv"], "importacion": d["importacion"],
                    "exportacion": d["exportacion"], "produccion_total": d["produccion_total"]})
        if d.get("termica_max_MW") is not None:
            comp["termica_max_MW_media_hora"] = d["termica_max_MW"]
        for k, v in comp.items():
            ofe.append(dict(fecha=f, componente=k, valor=v, unidad="MW" if k.endswith("_MW_media_hora") else "MWh",
                            fuente="CENACE Información Operativa (diaria)", url=ci.URL, consultado=ts))
    m = r.get("mensual")
    if m and m.get("dias") and d and d.get("fecha"):
        f0 = d["fecha"].replace(day=1)
        fin = f0.replace(day=m["dias"])
        dem.append(dict(fecha=fin.isoformat(), granularidad="mes_a_la_fecha",
                        energia_MWh_dia=(m["produccion_total"] - m.get("exportacion", 0)) / m["dias"],
                        produccion_MWh=m["produccion_total"], exportacion_MWh=m.get("exportacion"),
                        importacion_MWh=m.get("importacion"), demanda_max_MW=m.get("demanda_max_MW"),
                        hora_demanda_max=m.get("hora_max"), demanda_min_MW=None, n_dias=m["dias"],
                        fuente=f"CENACE Información Operativa (acumulado mensual {m['fecha_texto']}); demanda_max_MW = día de demanda máxima mensual {r.get('dia_dem_max_mensual')}",
                        url=ci.URL, consultado=ts))
    a = r.get("anual")
    if a and r.get("dia_dem_max_historica"):
        dem.append(dict(fecha=r["dia_dem_max_historica"].isoformat(), granularidad="dia_demanda_max_historica",
                        energia_MWh_dia=a["demanda_media_MW"] * 24, produccion_MWh=None, exportacion_MWh=None,
                        importacion_MWh=None, demanda_max_MW=a.get("demanda_max_MW"), hora_demanda_max=a.get("hora_max"),
                        demanda_min_MW=a.get("demanda_min_MW"), n_dias=1,
                        fuente="CENACE Información Operativa (curva del día de demanda máxima histórica; energía = media de 48 medias horas x 24)",
                        url=ci.URL, consultado=ts))
    return dem, ofe


def mensual_historico():
    p = DASH / "cenace_mensual_tecnologia.csv"
    if not p.exists():
        return []
    t = pd.read_csv(p)
    t = t[t.tecnologia == "total"]
    out = []
    for _, row in t.iterrows():
        y, mo = map(int, row.mes.split("-"))
        nd = calendar.monthrange(y, mo)[1]
        out.append(dict(fecha=f"{y:04d}-{mo:02d}-01", granularidad="mensual", energia_MWh_dia=row.GWh * 1000 / nd,
                        produccion_MWh=row.GWh * 1000, exportacion_MWh=None, importacion_MWh=None,
                        demanda_max_MW=None, hora_demanda_max=None, demanda_min_MW=None, n_dias=nd,
                        fuente="CENACE indicadores: energía neta producida total (sin importaciones) - proxy de demanda",
                        url=URL_IND, consultado=None))
    return out


def upsert(path, rows, keys):
    new = pd.DataFrame(rows)
    if path.exists() and len(new):
        old = pd.read_csv(path)
        new = pd.concat([old, new]).drop_duplicates(keys, keep="last")
    elif path.exists():
        new = pd.read_csv(path)
    new = new.drop_duplicates(keys, keep="last").sort_values(keys)
    new.to_csv(path, index=False)
    return new


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    if not a.no_download:
        try:
            print("descargado", descargar())
        except Exception as e:  # sigue con lo archivado
            print("AVISO: no se pudo descargar CENACE Info Operativa:", e)
    dem, ofe = mensual_historico(), []
    for p in sorted(RAW.glob("*.html")):
        try:
            d, o = filas_de_html(p); dem += d; ofe += o
        except Exception as e:
            print("AVISO: no se pudo parsear", p.name, e)
    D = upsert(DASH / "demanda_sni.csv", dem, ["granularidad", "fecha"])
    O = upsert(DASH / "oferta_sni_diaria.csv", ofe, ["fecha", "componente"])
    print("demanda_sni.csv", len(D), "filas;", D.groupby("granularidad").fecha.agg(["min", "max", "count"]).to_string())
    print("oferta_sni_diaria.csv", len(O), "filas")


if __name__ == "__main__":
    main()
