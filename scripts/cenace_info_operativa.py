"""Optional CENACE Info Operativa snapshot.

The page https://www.cenace.gob.ec/info-operativa/InformacionOperativa.htm embeds
Plotly charts with binary float payloads (no simple JSON/CSV API). Full decoding
is brittle across layout changes, so by default we only save a lightweight
provenance note + HTML snapshot checksum. Set ECU_SCRAPE_INFO_OP=1 to also keep
the raw HTML under raw/.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
import urllib3

from schema import TZ_LOCAL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://www.cenace.gob.ec/info-operativa/InformacionOperativa.htm"
_LOCAL = ZoneInfo(TZ_LOCAL)


def collect(raw_dir: Path) -> tuple[list[dict], dict[str, Any]]:
    meta: dict[str, Any] = {
        "fuente": "CENACE_InfoOperativa",
        "url": URL,
        "ok": False,
        "skipped_full_parse": True,
        "reason": (
            "Page is Plotly-embedded (binary y/customdata); no stable public tabular API. "
            "Skipped numeric ingest; HTML snapshot optional."
        ),
        "errors": [],
    }
    rows: list[dict] = []
    try:
        r = requests.get(URL, timeout=60, verify=False, allow_redirects=True)
        r.raise_for_status()
        content = r.content
        meta["ok"] = True
        meta["http_status"] = r.status_code
        meta["bytes"] = len(content)
        meta["sha256"] = hashlib.sha256(content).hexdigest()
        meta["fetched_at_local"] = datetime.now(_LOCAL).isoformat(timespec="seconds")
        if os.environ.get("ECU_SCRAPE_INFO_OP", "0") == "1":
            raw_dir.mkdir(parents=True, exist_ok=True)
            dest = raw_dir / "InformacionOperativa.htm"
            dest.write_bytes(content)
            meta["path"] = str(dest)
        # Provenance-only row (no invented generation numbers)
        now_local = datetime.now(_LOCAL)
        now_utc = now_local.astimezone(timezone.utc)
        rows.append(
            {
                "fecha_hora_local": now_local.replace(microsecond=0).isoformat(timespec="seconds"),
                "fecha_hora_utc": now_utc.replace(microsecond=0).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "granularidad": "snapshot",
                "ambito": "nacional",
                "codigo_planta": None,
                "nombre_planta": None,
                "tecnologia": None,
                "empresa_uunn": None,
                "sistema": "SNI",
                "metrica": "page_snapshot_bytes",
                "valor": float(len(content)),
                "unidad": "bytes",
                "fuente": "CENACE_InfoOperativa",
                "url_origen": URL,
                "calidad": "snapshot_only_no_series",
                "extra_json": json.dumps(
                    {
                        "sha256": meta["sha256"],
                        "nota": meta["reason"],
                        "plotly_embedded": True,
                    },
                    ensure_ascii=False,
                ),
            }
        )
        meta["n_rows"] = len(rows)
    except Exception as exc:  # noqa: BLE001
        meta["errors"].append(str(exc))
    return rows, meta
