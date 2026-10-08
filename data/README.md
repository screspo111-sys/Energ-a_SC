# Ecuador — generación unificada

Última actualización (local America/Guayaquil): **2026-10-08 02:36:21 -05**

## Archivos

- `data/generacion_unificada.csv` — dataset unificado (CSV)
- `data/generacion_unificada.parquet` — mismo contenido (Parquet)
- `data/collect_meta.json` — metadatos de la corrida
- `../raw/` — descargas crudas (indicadores.xlsx, BNEE_*.xls, etc.)

## Esquema

Columnas: fecha_hora_local, fecha_hora_utc, granularidad, ambito, codigo_planta, nombre_planta, tecnologia, empresa_uunn, sistema, metrica, valor, unidad, fuente, url_origen, calidad, extra_json

## Fuentes

1. **CELEC SUR ORDS** — energía horaria (MWh) plantas Mazar, Molino, Sopladora, Minas San Francisco y agregado SUR.
2. **CENACE indicadores.xlsx** — GWh mensuales por tecnología + anuales.
3. **ARCONEL BNEE** — último balance XLS (año móvil / potencia de corte).
4. **CENACE Info Operativa** — opcional; solo snapshot de página (series Plotly no parseadas por defecto).

## Rangos y conteos de esta corrida

```json
{
  "CELEC_SUR_ORDS": {
    "n_rows": 1690,
    "requests_ok": 75,
    "requests_total": 75,
    "fecha_min": "2026-09-24T01:00:00-05:00",
    "fecha_max": "2026-10-08T02:00:00-05:00",
    "failures": [],
    "plants": [
      "MAZAR",
      "MOLINO",
      "SOPLADORA",
      "MSF",
      "CELEC_SUR"
    ],
    "days": 14
  },
  "CENACE_indicadores": {
    "fuente": "CENACE_indicadores",
    "url": "https://www.cenace.gob.ec/wp-content/plugins/ez-addons/data/indicadores.xlsx",
    "path": "/home/runner/work/Energ-a_SC/Energ-a_SC/raw/indicadores.xlsx",
    "ok": true,
    "errors": [],
    "n_rows": 1444,
    "fecha_min": "2010-01-01T00:00:00-05:00",
    "fecha_max": "2026-07-01T00:00:00-05:00"
  },
  "ARCONEL_BNEE": {
    "fuente": "ARCONEL_BNEE",
    "url": "https://arconel.gob.ec/wp-content/uploads/downloads/2026/10/BNEE_julio_2026.xls",
    "path": "/home/runner/work/Energ-a_SC/Energ-a_SC/raw/BNEE_julio_2026.xls",
    "page": "https://arconel.gob.ec/balance-nacional-de-energia-electrica/",
    "ok": true,
    "errors": [],
    "titulo": "Balance Nacional de Energía Eléctrica (BNEE) - Año móvil con corte a julio 2026 (1)",
    "corte": "julio_2026",
    "n_rows": 70
  },
  "CENACE_InfoOperativa": {
    "fuente": "CENACE_InfoOperativa",
    "url": "https://www.cenace.gob.ec/info-operativa/InformacionOperativa.htm",
    "ok": true,
    "skipped_full_parse": true,
    "reason": "Page is Plotly-embedded (binary y/customdata); no stable public tabular API. Skipped numeric ingest; HTML snapshot optional.",
    "errors": [],
    "http_status": 200,
    "bytes": 266657,
    "sha256": "824b10a05b2341dffffa5638a64693454ab8a9455a1bfed4de3767b97940b086",
    "fetched_at_local": "2026-10-08T02:36:21-05:00",
    "n_rows": 1
  }
}
```

Total filas unificadas: **5371**

## Refresh diario

```bash
python scripts/collect_all.py --days 30
```

Opciones útiles: `--days 7`, `--no-today`, `--skip-celec`, `--skip-info-op`.
Para guardar HTML de Info Operativa: `ECU_SCRAPE_INFO_OP=1`.

## Notas

- Zona horaria: America/Guayaquil (UTC-5).
- CELEC usa certificado TLS no confiable en algunos entornos; el collector desactiva la verificación SSL solo para ese host.
- Timestamps CELEC: campo `loctimestamp` con sufijo Z interpretado como UTC (fin de hora); ver `extra_json`.
- No se inventan valores; ceros reportados por la API se conservan; `valueedit` null (horas futuras) se omite.
- Info Operativa CENACE: solo snapshot; series Plotly no se parsean (ver `cenace_info_operativa.py`).
