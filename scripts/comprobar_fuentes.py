#!/usr/bin/env python3
"""Comprueba si CELEC SUR, CENACE y ARCONEL responden. Siempre termina en 0.

No descarga el histórico: una petición corta por fuente, con tiempo límite,
para que el tablero decida si consulta o si se queda con los últimos datos.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "raw" / "fuentes_alcance.json"
CTX = ssl._create_unverified_context()
TIMEOUT = 12

FUENTES = [
    (
        "CELEC_SUR",
        "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardommaz/mazEnerDia?fecha=01/10/2026%2000:00:00",
    ),
    (
        "CENACE_info_operativa",
        "https://www.cenace.gob.ec/info-operativa/InformacionOperativa.htm",
    ),
    (
        "CENACE_indicadores",
        "https://www.cenace.gob.ec/wp-content/plugins/ez-addons/data/indicadores.xlsx",
    ),
    (
        "ARCONEL_BNEE",
        "https://arconel.gob.ec/balance-nacional-de-energia-electrica/",
    ),
]


def probar(url: str) -> dict:
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ecu-dashboard/1.0", "Accept": "*/*"})
        with urllib.request.urlopen(req, context=CTX, timeout=TIMEOUT) as resp:
            resp.read(64)
            return {
                "ok": 200 <= resp.status < 400,
                "status": resp.status,
                "ms": int((time.perf_counter() - t0) * 1000),
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "ms": int((time.perf_counter() - t0) * 1000),
        }


def main() -> int:
    informe = {nombre: probar(url) | {"url": url} for nombre, url in FUENTES}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    for nombre, info in informe.items():
        if info.get("ok"):
            print(f"ALCANZA  {nombre}  HTTP {info.get('status')}  {info['ms']} ms")
        else:
            print(f"NO ALCANZA  {nombre}  {info.get('error', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
