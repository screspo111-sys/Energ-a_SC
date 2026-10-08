#!/usr/bin/env python3
"""Sale 0 si vale la pena un commit de historia; 1 si solo cambió la hora de corrida."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def show(path: str) -> str | None:
    proc = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        return None
    return proc.stdout


def firma_kpi(texto: str | None) -> dict | None:
    if not texto:
        return None
    data = json.loads(texto)
    ea = data.get("estado_actual") or {}
    prob = data.get("probabilidad_apagones") or {}
    return {
        "dias": data.get("dias"),
        "fecha": data.get("fecha"),
        "semaforo": data.get("semaforo"),
        "fecha_hidro": ea.get("fecha_hidro"),
        "cota": ea.get("cota_mazar"),
        "prob": prob.get("prob_hoy") if isinstance(prob, dict) else None,
    }


def firma_estado(texto: str | None):
    if not texto:
        return None
    data = json.loads(texto)
    return data.get("fecha_dia_operativo")


def main() -> int:
    pares = [
        ("dashboard/kpi_deficit.json", firma_kpi),
        ("dashboard/estado_nacional.json", firma_estado),
    ]
    for rel, firma in pares:
        anterior = firma(show(rel))
        actual = firma((ROOT / rel).read_text(encoding="utf-8"))
        if anterior != actual:
            print(f"historia nueva en {rel}")
            return 0
    for rel in (
        "dashboard/hidrologia_celec_sur.csv",
        "dashboard/generacion_diaria_celec_sur.csv",
        "dashboard/demanda_sni.csv",
        "dashboard/oferta_sni_diaria.csv",
        "data/generacion_unificada.csv",
    ):
        viejo = show(rel)
        nuevo = (ROOT / rel).read_text(encoding="utf-8") if (ROOT / rel).exists() else None
        if viejo != nuevo:
            print(f"historia nueva en {rel}")
            return 0
    print("sin cambios de fondo")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
