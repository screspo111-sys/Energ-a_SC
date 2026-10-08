#!/usr/bin/env python3
"""Refresh unified Ecuador electricity generation dataset from public sources.

Usage:
  python scripts/collect_all.py
  python scripts/collect_all.py --days 30
  python scripts/collect_all.py --skip-celec

Refresh:
  python scripts/collect_all.py --days 30
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from schema import COLUMNS, TZ_LOCAL  # noqa: E402
import arconel_bnee  # noqa: E402
import celec_sur  # noqa: E402
import cenace_indicadores  # noqa: E402
import cenace_info_operativa  # noqa: E402


def _write_readme(data_dir: Path, summary: dict) -> None:
    lines = [
        "# Ecuador — generación unificada",
        "",
        f"Última actualización (local {TZ_LOCAL}): **{summary['updated_at_local']}**",
        "",
        "## Archivos",
        "",
        f"- `{summary['csv']}` — dataset unificado (CSV)",
        f"- `{summary['parquet']}` — mismo contenido (Parquet)",
        f"- `{summary['meta_json']}` — metadatos de la corrida",
        "- `../raw/` — descargas crudas (indicadores.xlsx, BNEE_*.xls, etc.)",
        "",
        "## Esquema",
        "",
        "Columnas: " + ", ".join(COLUMNS),
        "",
        "## Fuentes",
        "",
        "1. **CELEC SUR ORDS** — energía horaria (MWh) plantas Mazar, Molino, Sopladora, Minas San Francisco y agregado SUR.",
        "2. **CENACE indicadores.xlsx** — GWh mensuales por tecnología + anuales.",
        "3. **ARCONEL BNEE** — último balance XLS (año móvil / potencia de corte).",
        "4. **CENACE Info Operativa** — opcional; solo snapshot de página (series Plotly no parseadas por defecto).",
        "",
        "## Rangos y conteos de esta corrida",
        "",
        "```json",
        json.dumps(summary.get("sources", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        f"Total filas unificadas: **{summary.get('n_rows', 0)}**",
        "",
        "## Refresh diario",
        "",
        "```bash",
        "python scripts/collect_all.py --days 30",
        "```",
        "",
        "Opciones útiles: `--days 7`, `--no-today`, `--skip-celec`, `--skip-info-op`.",
        "Para guardar HTML de Info Operativa: `ECU_SCRAPE_INFO_OP=1`.",
        "",
        "## Notas",
        "",
        "- Zona horaria: America/Guayaquil (UTC-5).",
        "- CELEC usa certificado TLS no confiable en algunos entornos; el collector desactiva la verificación SSL solo para ese host.",
        "- Timestamps CELEC: campo `loctimestamp` con sufijo Z interpretado como UTC (fin de hora); ver `extra_json`.",
        "- No se inventan valores; ceros reportados por la API se conservan; `valueedit` null (horas futuras) se omite.",
        "- Info Operativa CENACE: solo snapshot; series Plotly no se parsean (ver `cenace_info_operativa.py`).",
        "",
    ]
    (data_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Ecuador generation data")
    parser.add_argument("--days", type=int, default=30, help="CELEC history days (complete days ending D-1)")
    parser.add_argument("--no-today", action="store_true", help="Do not pull CELEC partial today")
    parser.add_argument("--skip-celec", action="store_true")
    parser.add_argument("--skip-cenace", action="store_true")
    parser.add_argument("--skip-bnee", action="store_true")
    parser.add_argument("--skip-info-op", action="store_true")
    args = parser.parse_args()

    data_dir = ROOT / "data"
    raw_dir = ROOT / "raw"
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    sources: dict = {}
    failures: list[str] = []

    if not args.skip_celec:
        print(f"[CELEC] pulling {args.days} days (+today={not args.no_today})...")
        try:
            rows, reports = celec_sur.collect(days=args.days, include_today=not args.no_today)
            all_rows.extend(rows)
            ok = sum(1 for r in reports if r.get("ok"))
            fail = [r for r in reports if not r.get("ok")]
            fechas = [r["fecha_hora_local"] for r in rows] if rows else []
            sources["CELEC_SUR_ORDS"] = {
                "n_rows": len(rows),
                "requests_ok": ok,
                "requests_total": len(reports),
                "fecha_min": min(fechas) if fechas else None,
                "fecha_max": max(fechas) if fechas else None,
                "failures": fail[:10],
                "plants": [p["codigo_planta"] for p in celec_sur.PLANTS],
                "days": args.days,
            }
            if fail:
                failures.append(f"CELEC: {len(fail)} request failures")
            print(f"  -> {len(rows)} rows, {ok}/{len(reports)} requests OK")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"CELEC fatal: {exc}")
            sources["CELEC_SUR_ORDS"] = {"ok": False, "error": str(exc)}
            print(f"  !! {exc}")

    if not args.skip_cenace:
        print("[CENACE] indicadores.xlsx...")
        try:
            rows, meta = cenace_indicadores.collect(raw_dir)
            all_rows.extend(rows)
            sources["CENACE_indicadores"] = meta
            print(f"  -> {len(rows)} rows")
            if not meta.get("ok"):
                failures.append("CENACE indicadores failed")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"CENACE fatal: {exc}")
            sources["CENACE_indicadores"] = {"ok": False, "error": str(exc)}
            print(f"  !! {exc}")

    if not args.skip_bnee:
        print("[ARCONEL] BNEE latest XLS...")
        try:
            rows, meta = arconel_bnee.collect(raw_dir)
            all_rows.extend(rows)
            sources["ARCONEL_BNEE"] = meta
            print(f"  -> {len(rows)} rows ({meta.get('corte')})")
            if not meta.get("ok"):
                failures.append("ARCONEL BNEE failed")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"ARCONEL fatal: {exc}")
            sources["ARCONEL_BNEE"] = {"ok": False, "error": str(exc)}
            print(f"  !! {exc}")

    if not args.skip_info_op:
        print("[CENACE] Info Operativa snapshot (no series parse)...")
        try:
            rows, meta = cenace_info_operativa.collect(raw_dir)
            all_rows.extend(rows)
            sources["CENACE_InfoOperativa"] = meta
            print(f"  -> snapshot ok={meta.get('ok')} rows={len(rows)}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"InfoOperativa: {exc}")
            sources["CENACE_InfoOperativa"] = {"ok": False, "error": str(exc)}
            print(f"  !! {exc}")

    csv_path = data_dir / "generacion_unificada.csv"
    parquet_path = data_dir / "generacion_unificada.parquet"
    meta_path = data_dir / "collect_meta.json"
    keys = ["fuente", "fecha_hora_utc", "codigo_planta", "metrica", "tecnologia", "granularidad"]
    new = pd.DataFrame(all_rows, columns=COLUMNS)
    if csv_path.exists() and csv_path.stat().st_size > 0:
        prev = pd.read_csv(csv_path)
    else:
        prev = pd.DataFrame(columns=COLUMNS)
    # Una fuente caída no borra su historia: solo se insertan filas de fuentes que respondieron.
    if new.empty:
        df = prev
        if not df.empty:
            print("AVISO: esta corrida no trajo filas nuevas; se conserva generacion_unificada.csv")
    elif prev.empty:
        df = new
    else:
        df = pd.concat([prev, new], ignore_index=True)
        df = df.drop_duplicates(keys, keep="last")
    if not df.empty:
        df = df.sort_values(
            by=["fuente", "fecha_hora_utc", "codigo_planta", "metrica", "tecnologia"],
            kind="mergesort",
        ).reset_index(drop=True)
    if df.empty and csv_path.exists() and csv_path.stat().st_size > 0:
        print("AVISO: no se vacía generacion_unificada.csv")
    else:
        df.to_csv(csv_path, index=False)
        try:
            df.to_parquet(parquet_path, index=False)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"parquet write: {exc}")

    updated = datetime.now(ZoneInfo(TZ_LOCAL)).strftime("%Y-%m-%d %H:%M:%S %Z")
    summary = {
        "updated_at_local": updated,
        "n_rows": int(len(df)),
        "csv": "data/generacion_unificada.csv",
        "parquet": "data/generacion_unificada.parquet",
        "meta_json": "data/collect_meta.json",
        "sources": sources,
        "failures": failures,
        "columns": COLUMNS,
    }
    meta_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_readme(data_dir, summary)

    print("\n=== DONE ===")
    print(f"rows={len(df)} csv={csv_path} parquet={parquet_path}")
    if failures:
        print("failures:", failures)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
