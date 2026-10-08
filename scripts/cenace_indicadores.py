"""CENACE indicadores.xlsx — monthly GWh by technology (public)."""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import urllib3

from schema import TZ_LOCAL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://www.cenace.gob.ec/wp-content/plugins/ez-addons/data/indicadores.xlsx"

MES_MAP = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

TECH_COLS = {
    "Biogás": "biogas",
    "Biomasa": "biomasa",
    "Eólica": "eolica",
    "Fotovoltaica": "fotovoltaica",
    "Hidroeléctrica": "hidroelectrica",
    "Térmica": "termica",
    "TOTAL": "total",
}

_LOCAL = ZoneInfo(TZ_LOCAL)


def download(raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / "indicadores.xlsx"
    r = requests.get(URL, timeout=60, verify=False)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def _month_start_end(year: int, month: int) -> tuple[datetime, datetime]:
    start_local = datetime(year, month, 1, 0, 0, 0, tzinfo=_LOCAL)
    last = monthrange(year, month)[1]
    # represent monthly value at month start; end exclusive noted in extra
    return start_local, datetime(year, month, last, 23, 59, 59, tzinfo=_LOCAL)


def collect(raw_dir: Path) -> tuple[list[dict], dict[str, Any]]:
    path = download(raw_dir)
    meta: dict[str, Any] = {"fuente": "CENACE_indicadores", "url": URL, "path": str(path), "ok": True, "errors": []}
    rows: list[dict] = []
    try:
        df = pd.read_excel(path, sheet_name="datos")
    except Exception as exc:  # noqa: BLE001
        meta["ok"] = False
        meta["errors"].append(str(exc))
        return rows, meta

    # normalize headers
    df.columns = [str(c).strip() for c in df.columns]
    if "Año" not in df.columns or "Mes" not in df.columns:
        meta["ok"] = False
        meta["errors"].append(f"Unexpected columns: {list(df.columns)}")
        return rows, meta

    for _, rec in df.iterrows():
        try:
            year = int(rec["Año"])
            mes_name = str(rec["Mes"]).strip().lower()
            month = MES_MAP.get(mes_name)
            if not month:
                continue
        except Exception:
            continue
        start_local, end_local = _month_start_end(year, month)
        start_utc = start_local.astimezone(timezone.utc)
        for col_es, tech in TECH_COLS.items():
            if col_es not in df.columns:
                continue
            val = rec[col_es]
            if pd.isna(val):
                continue
            rows.append(
                {
                    "fecha_hora_local": start_local.isoformat(timespec="seconds"),
                    "fecha_hora_utc": start_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
                    "granularidad": "mes",
                    "ambito": "nacional",
                    "codigo_planta": None,
                    "nombre_planta": None,
                    "tecnologia": tech,
                    "empresa_uunn": None,
                    "sistema": "SNI",
                    "metrica": "energia_mensual",
                    "valor": float(val),
                    "unidad": "GWh",
                    "fuente": "CENACE_indicadores",
                    "url_origen": URL,
                    "calidad": "oficial_mensual",
                    "extra_json": json.dumps(
                        {
                            "mes": mes_name,
                            "anio": year,
                            "periodo_local_fin": end_local.isoformat(timespec="seconds"),
                            "columna_origen": col_es,
                            "hoja": "datos",
                        },
                        ensure_ascii=False,
                    ),
                }
            )

    # Annual sheet produccion (optional annual totals)
    try:
        dfp = pd.read_excel(path, sheet_name="produccion")
        dfp.columns = [str(c).strip() for c in dfp.columns]
        for _, rec in dfp.iterrows():
            if pd.isna(rec.get("Año")):
                continue
            year = int(rec["Año"])
            start_local = datetime(year, 1, 1, 0, 0, 0, tzinfo=_LOCAL)
            start_utc = start_local.astimezone(timezone.utc)
            mapping = {
                "Producción": ("energia_anual", "total"),
                "Generación Demanda Interna": ("energia_anual_demanda_interna", "total"),
                "Exportación Colombia y Perú": ("energia_anual_exportacion", "exportacion"),
            }
            for col, (metrica, tech) in mapping.items():
                if col not in dfp.columns or pd.isna(rec.get(col)):
                    continue
                comentario = rec.get("Comentario")
                rows.append(
                    {
                        "fecha_hora_local": start_local.isoformat(timespec="seconds"),
                        "fecha_hora_utc": start_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
                        "granularidad": "anio",
                        "ambito": "nacional",
                        "codigo_planta": None,
                        "nombre_planta": None,
                        "tecnologia": tech,
                        "empresa_uunn": None,
                        "sistema": "SNI",
                        "metrica": metrica,
                        "valor": float(rec[col]),
                        "unidad": "GWh",
                        "fuente": "CENACE_indicadores",
                        "url_origen": URL,
                        "calidad": "oficial_anual",
                        "extra_json": json.dumps(
                            {
                                "anio": year,
                                "columna_origen": col,
                                "hoja": "produccion",
                                "comentario": None if pd.isna(comentario) else str(comentario),
                            },
                            ensure_ascii=False,
                        ),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        meta["errors"].append(f"produccion sheet: {exc}")

    meta["n_rows"] = len(rows)
    if rows:
        fechas = [r["fecha_hora_local"] for r in rows]
        meta["fecha_min"] = min(fechas)
        meta["fecha_max"] = max(fechas)
    return rows, meta
