"""CELEC SUR ORDS hourly energy collector (public, no login)."""

from __future__ import annotations

import json
import ssl
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from schema import TZ_LOCAL

BASE = "https://generacioncsr.celec.gob.ec:8443/ords/csr"

PLANTS = [
    {
        "path": "sardommaz",
        "prefix": "maz",
        "codigo_planta": "MAZAR",
        "nombre_planta": "Mazar",
        "tecnologia": "hidroelectrica",
        "empresa_uunn": "CELEC EP - Hidropaute",
        "ambito": "planta",
    },
    {
        "path": "sardommol",
        "prefix": "mol",
        "codigo_planta": "MOLINO",
        "nombre_planta": "Molino",
        "tecnologia": "hidroelectrica",
        "empresa_uunn": "CELEC EP - Hidropaute",
        "ambito": "planta",
    },
    {
        "path": "sardomsop",
        "prefix": "sop",
        "codigo_planta": "SOPLADORA",
        "nombre_planta": "Sopladora",
        "tecnologia": "hidroelectrica",
        "empresa_uunn": "CELEC EP - Hidropaute",
        "ambito": "planta",
    },
    {
        "path": "sardommsf",
        "prefix": "msf",
        "codigo_planta": "MSF",
        "nombre_planta": "Minas San Francisco",
        "tecnologia": "hidroelectrica",
        "empresa_uunn": "CELEC EP - Enerjubones",
        "ambito": "planta",
    },
    {
        "path": "sardomcsr",
        "prefix": "csr",
        "codigo_planta": "CELEC_SUR",
        "nombre_planta": "CELEC SUR agregado",
        "tecnologia": "hidroelectrica",
        "empresa_uunn": "CELEC EP - SUR",
        "ambito": "sistema",
    },
]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_LOCAL = ZoneInfo(TZ_LOCAL)


def _fetch_json(url: str, retries: int = 3) -> dict[str, Any]:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"Accept": "application/json", "User-Agent": "ecu-gen-collector/1.0"})
            with urlopen(req, context=_SSL_CTX, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"CELEC fetch failed after {retries} tries: {url} ({last_err})")


def build_url(plant_path: str, prefix: str, day: date) -> str:
    fecha = day.strftime("%d/%m/%Y") + " 00:00:00"
    return f"{BASE}/{plant_path}/{prefix}EnerDia?fecha={quote(fecha)}"


def parse_timestamp(loctimestamp: str) -> tuple[datetime, datetime]:
    """Parse CELEC loctimestamp.

    Values are returned with a trailing Z and span 06:00Z..05:00Z next day for a
    local calendar day (America/Guayaquil). Interpreting Z as true UTC yields
    local end-of-hour stamps 01:00..00:00 next day for that fecha parameter.
    """
    raw = loctimestamp.strip()
    if raw.endswith("Z"):
        utc = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    else:
        utc = datetime.fromisoformat(raw)
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=timezone.utc)
        else:
            utc = utc.astimezone(timezone.utc)
    local = utc.astimezone(_LOCAL)
    return local, utc


def collect_day(plant: dict[str, Any], day: date, prefer_complete: bool) -> tuple[list[dict], dict]:
    url = build_url(plant["path"], plant["prefix"], day)
    meta = {"plant": plant["codigo_planta"], "day": day.isoformat(), "url": url, "ok": False, "n": 0, "error": None}
    try:
        payload = _fetch_json(url)
    except Exception as exc:  # noqa: BLE001
        meta["error"] = str(exc)
        return [], meta

    items = payload.get("items") or []
    meta["ok"] = True
    meta["n"] = len(items)
    meta["n_null_value"] = sum(1 for i in items if i.get("valueedit") is None)
    today = date.today()
    rows: list[dict] = []
    for item in items:
        ts = item.get("loctimestamp")
        val = item.get("valueedit")
        # Do not invent numbers: skip null valueedit (common for future hours / empty today).
        if ts is None or val is None:
            continue
        local, utc = parse_timestamp(str(ts))
        calidad = "observado"
        if day == today:
            calidad = "parcial_hoy"
        elif prefer_complete and day == today - timedelta(days=1):
            calidad = "completo_d1"
        rows.append(
            {
                "fecha_hora_local": local.isoformat(timespec="seconds"),
                "fecha_hora_utc": utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "granularidad": "hora",
                "ambito": plant["ambito"],
                "codigo_planta": plant["codigo_planta"],
                "nombre_planta": plant["nombre_planta"],
                "tecnologia": plant["tecnologia"],
                "empresa_uunn": plant["empresa_uunn"],
                "sistema": "CELEC_SUR / SNI",
                "metrica": "energia_horaria",
                "valor": float(val),
                "unidad": "MWh",
                "fuente": "CELEC_SUR_ORDS",
                "url_origen": url,
                "calidad": calidad,
                "extra_json": json.dumps(
                    {
                        "loctimestamp_raw": ts,
                        "endpoint": f"{plant['path']}/{plant['prefix']}EnerDia",
                        "fecha_param": day.strftime("%d/%m/%Y"),
                        "nota_timestamp": "Z tratado como UTC; para fecha=D cubre ~01:00 local D a 00:00 local D+1 (fin de hora)",
                    },
                    ensure_ascii=False,
                ),
            }
        )
    return rows, meta


def collect(days: int = 30, include_today: bool = True) -> tuple[list[dict], list[dict]]:
    """Pull hourly energy for each plant over the last `days` complete days (+ today optional)."""
    today = date.today()
    # Prefer D-1 fully; include today as partial if requested.
    day_list = [today - timedelta(days=i) for i in range(1, days + 1)]
    if include_today:
        day_list = [today] + day_list
    # oldest first for readability
    day_list = sorted(set(day_list))

    all_rows: list[dict] = []
    reports: list[dict] = []
    for plant in PLANTS:
        for day in day_list:
            rows, meta = collect_day(plant, day, prefer_complete=True)
            all_rows.extend(rows)
            reports.append(meta)
            time.sleep(0.15)  # be polite to ORDS
    return all_rows, reports
