"""ARCONEL BNEE — latest Balance Nacional XLS (public)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import urllib3

from schema import TZ_LOCAL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PAGE_URL = "https://arconel.gob.ec/balance-nacional-de-energia-electrica/"
_LOCAL = ZoneInfo(TZ_LOCAL)

MES_ES = {
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


def find_latest_bnee_url(session: requests.Session | None = None) -> str:
    sess = session or requests.Session()
    r = sess.get(PAGE_URL, timeout=60, verify=False)
    r.raise_for_status()
    # Prefer .xls / .xlsx download links mentioning BNEE
    hrefs = re.findall(r'href="([^"]+BNEE[^"]+\.xls[x]?)"', r.text, flags=re.I)
    hrefs += re.findall(r"href='([^']+BNEE[^']+\.xls[x]?)'", r.text, flags=re.I)
    if not hrefs:
        hrefs = re.findall(r'href="([^"]+\.xls[x]?)"', r.text, flags=re.I)
    # unique preserve order
    seen = set()
    urls = []
    for h in hrefs:
        u = urljoin(PAGE_URL, h)
        if u not in seen and "BNEE" in u.upper():
            seen.add(u)
            urls.append(u)
    if not urls:
        raise RuntimeError("No BNEE .xls link found on ARCONEL page")
    return urls[0]


def download_latest(raw_dir: Path) -> tuple[Path, str]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    url = find_latest_bnee_url()
    name = url.rstrip("/").split("/")[-1]
    dest = raw_dir / name
    r = requests.get(url, timeout=90, verify=False)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest, url


def _parse_cutoff(title: str) -> tuple[int | None, int | None, str | None]:
    """Extract month/year from titles like '... corte a julio 2026' or filename BNEE_julio_2026.xls."""
    m = re.search(r"corte a\s+([a-záéíóú]+)\s+(\d{4})", title, re.I)
    if not m:
        m = re.search(r"BNEE[_\s-]*([a-záéíóú]+)[_\s-]*(\d{4})", title, re.I)
    if not m:
        return None, None, None
    mes = m.group(1).lower().replace("é", "e").replace("á", "a").replace("í", "i").replace("ó", "o").replace("ú", "u")
    # normalize septiembre variants already ok
    month = MES_ES.get(mes)
    year = int(m.group(2))
    return year, month, f"{mes}_{year}"


def collect(raw_dir: Path) -> tuple[list[dict], dict[str, Any]]:
    path, url = download_latest(raw_dir)
    meta: dict[str, Any] = {"fuente": "ARCONEL_BNEE", "url": url, "path": str(path), "page": PAGE_URL, "ok": True, "errors": []}
    rows: list[dict] = []

    try:
        xl = pd.ExcelFile(path)
        sheet = xl.sheet_names[0]
        df = pd.read_excel(path, sheet_name=sheet, header=None)
    except Exception as exc:  # noqa: BLE001
        meta["ok"] = False
        meta["errors"].append(str(exc))
        return rows, meta

    title = str(df.iloc[0, 1]) if df.shape[1] > 1 else str(path.name)
    year, month, label = _parse_cutoff(title + " " + path.name)
    meta["titulo"] = title
    meta["corte"] = label
    if year and month:
        stamp_local = datetime(year, month, 1, 0, 0, 0, tzinfo=_LOCAL)
    else:
        stamp_local = datetime.now(_LOCAL).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stamp_utc = stamp_local.astimezone(timezone.utc)

    # Rows 6..19-ish hold categories; col2=subtech, col1=group, col3=MW total, col9=GWh prod total, col12=GWh SNI
    for i in range(6, min(30, len(df))):
        group = df.iloc[i, 1]
        sub = df.iloc[i, 2]
        if pd.isna(group) and pd.isna(sub):
            continue
        group_s = None if pd.isna(group) else str(group).strip()
        sub_s = None if pd.isna(sub) else str(sub).strip()
        if group_s and group_s.lower().startswith("notas"):
            break
        if sub_s and sub_s.lower().startswith("notas"):
            break

        tech = (sub_s or group_s or "").lower()
        tech = (
            tech.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace(" ", "_")
        )

        metrics = [
            (3, "potencia_nominal_total", "MW"),
            (6, "potencia_nominal_sni", "MW"),
            (9, "produccion_total_anio_movil", "GWh"),
            (12, "produccion_sni_anio_movil", "GWh"),
            (15, "entregada_servicio_publico", "GWh"),
        ]
        for col, metrica, unidad in metrics:
            if col >= df.shape[1]:
                continue
            val = df.iloc[i, col]
            if pd.isna(val):
                continue
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "fecha_hora_local": stamp_local.isoformat(timespec="seconds"),
                    "fecha_hora_utc": stamp_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
                    "granularidad": "anio_movil",
                    "ambito": "nacional",
                    "codigo_planta": None,
                    "nombre_planta": None,
                    "tecnologia": tech or None,
                    "empresa_uunn": None,
                    "sistema": "nacional",
                    "metrica": metrica,
                    "valor": fval,
                    "unidad": unidad,
                    "fuente": "ARCONEL_BNEE",
                    "url_origen": url,
                    "calidad": "oficial_bnee",
                    "extra_json": json.dumps(
                        {
                            "grupo": group_s,
                            "subtecnologia": sub_s,
                            "hoja": sheet,
                            "fila": int(i),
                            "corte": label,
                            "titulo": title,
                            "nota": "Potencia nominal = mes de corte; energía = año móvil hasta el corte (ver notas BNEE)",
                        },
                        ensure_ascii=False,
                    ),
                }
            )

    meta["n_rows"] = len(rows)
    return rows, meta
