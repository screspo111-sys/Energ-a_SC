#!/usr/bin/env python3
"""Rutina del tablero. Una fuente caída no aborta el resto ni borra la historia.

Escribe dashboard/frescura.json con el resultado de cada paso. La página se
arma al final con los CSV/JSON que hayan quedado (nuevos o anteriores).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DASH = ROOT / "dashboard"
PY = sys.executable
TZ = ZoneInfo("America/Guayaquil")


def _run(cmd: list[str]) -> tuple[bool, str]:
    print(">>", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, text=True)
    ok = proc.returncode == 0
    if not ok:
        print(f"AVISO: falló ({proc.returncode}): {' '.join(cmd)}", flush=True)
    return ok, "" if ok else f"código {proc.returncode}"


def main() -> int:
    sin_red = "--sin-red" in sys.argv
    (DASH / "raw").mkdir(parents=True, exist_ok=True)
    (ROOT / "raw").mkdir(parents=True, exist_ok=True)
    alcance_path = DASH / "raw" / "fuentes_alcance.json"
    fuentes: dict[str, dict] = {}

    if sin_red:
        print("Modo sin red: no se consultan CELEC, CENACE ni ARCONEL.")
        for nombre in ("CELEC_SUR", "CENACE_info_operativa", "CENACE_indicadores", "ARCONEL_BNEE"):
            fuentes[nombre] = {"ok": False, "detalle": "omitido (--sin-red); se usan los datos ya guardados"}
    else:
        _run([PY, str(ROOT / "scripts" / "comprobar_fuentes.py")])
        alcance = json.loads(alcance_path.read_text(encoding="utf-8")) if alcance_path.exists() else {}

        def viva(nombre: str) -> bool:
            return bool((alcance.get(nombre) or {}).get("ok"))

        if viva("CELEC_SUR"):
            ok, err = _run([PY, str(ROOT / "scripts" / "collect_all.py"), "--days", "14"])
            fuentes["CELEC_SUR_unificada"] = {"ok": ok, "detalle": "colector unificado, ventana de 14 días" if ok else err}
            ok, err = _run([PY, str(DASH / "build_dashboard_csvs.py"), "--recent-months", "2"])
            fuentes["CELEC_SUR"] = {"ok": ok, "detalle": "hidrología y energía diaria (2 meses, fusionados)" if ok else err}
        else:
            fuentes["CELEC_SUR"] = {
                "ok": False,
                "detalle": "el puerto 8443 de CELEC SUR no respondió; se conserva la hidrología guardada",
            }
            print("AVISO: se omite la descarga CELEC y se usan los CSV anteriores.")

        saltos = []
        cmd = [PY, str(ROOT / "scripts" / "collect_all.py"), "--days", "2"]
        if not viva("CELEC_SUR"):
            cmd.append("--skip-celec")
        if not viva("CENACE_indicadores"):
            cmd.append("--skip-cenace")
            saltos.append("indicadores")
        if not viva("ARCONEL_BNEE"):
            cmd.append("--skip-bnee")
            saltos.append("BNEE")
        if not viva("CENACE_info_operativa"):
            cmd.append("--skip-info-op")
        # El bloque CELEC de arriba ya actualizó la unificada si hubo red. Aquí solo
        # se completan CENACE y ARCONEL cuando CELEC no se consultó en el primer paso.
        if not viva("CELEC_SUR") and any(viva(n) for n in ("CENACE_indicadores", "ARCONEL_BNEE")):
            ok, err = _run(cmd)
            fuentes["CENACE_indicadores"] = {
                "ok": ok and viva("CENACE_indicadores"),
                "detalle": "indicadores.xlsx" if ok else err,
            }
            fuentes["ARCONEL_BNEE"] = {
                "ok": ok and viva("ARCONEL_BNEE"),
                "detalle": "página BNEE" if ok else err,
            }
        else:
            if viva("CELEC_SUR"):
                # collect_all del primer paso ya intentó CENACE y BNEE.
                fuentes.setdefault("CENACE_indicadores", {"ok": viva("CENACE_indicadores"), "detalle": "incluido en el colector unificado"})
                fuentes.setdefault("ARCONEL_BNEE", {"ok": viva("ARCONEL_BNEE"), "detalle": "incluido en el colector unificado"})
            else:
                fuentes["CENACE_indicadores"] = {"ok": False, "detalle": "no respondió; se conserva el mensual guardado"}
                fuentes["ARCONEL_BNEE"] = {"ok": False, "detalle": "no respondió; se conserva la capacidad guardada"}

        if viva("CENACE_info_operativa"):
            ok, err = _run([PY, str(DASH / "scripts" / "actualizar_demanda.py")])
            fuentes["CENACE_info_operativa"] = {"ok": ok, "detalle": "Información Operativa" if ok else err}
        else:
            _run([PY, str(DASH / "scripts" / "actualizar_demanda.py"), "--no-download"])
            fuentes["CENACE_info_operativa"] = {
                "ok": False,
                "detalle": "CENACE no respondió; se conserva la demanda y la oferta ya archivadas",
            }

    ok, err = _run([PY, str(DASH / "scripts" / "estado_nacional.py")])
    fuentes["estado_nacional"] = {"ok": ok, "detalle": "último día CENACE guardado" if ok else err + "; queda el JSON anterior"}
    ok, err = _run([PY, str(DASH / "scripts" / "modelo_deficit.py")])
    fuentes["modelo"] = {"ok": ok, "detalle": "días a 2.115 m y probabilidad" if ok else err + "; queda el KPI anterior"}

    frescura = {
        "generado": datetime.now(TZ).isoformat(timespec="minutes"),
        "fuentes": fuentes,
    }
    (DASH / "frescura.json").write_text(json.dumps(frescura, ensure_ascii=False, indent=2), encoding="utf-8")
    ok, err = _run([PY, str(DASH / "scripts" / "build_pagina.py")])
    if not ok:
        print("ERROR: no se pudo armar la página.", file=sys.stderr)
        return 1
    caidas = [k for k, v in fuentes.items() if not v.get("ok")]
    if caidas:
        print("Fuentes con aviso (la página igual se armó):", ", ".join(caidas))
    else:
        print("Todas las fuentes respondieron.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
