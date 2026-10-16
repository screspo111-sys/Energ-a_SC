# Ecuador — generación unificada

Última actualización (local America/Guayaquil): **2026-10-16 04:48:17 -05**

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
    "n_rows": 1706,
    "requests_ok": 75,
    "requests_total": 75,
    "fecha_min": "2026-10-02T01:00:00-05:00",
    "fecha_max": "2026-10-16T07:00:00-05:00",
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
    "ok": false,
    "error": "HTTPSConnectionPool(host='arconel.gob.ec', port=443): Read timed out. (read timeout=60)"
  },
  "CENACE_InfoOperativa": {
    "fuente": "CENACE_InfoOperativa",
    "url": "https://www.cenace.gob.ec/info-operativa/InformacionOperativa.htm",
    "ok": true,
    "skipped_full_parse": true,
    "reason": "Page is Plotly-embedded (binary y/customdata); no stable public tabular API. Skipped numeric ingest; HTML snapshot optional.",
    "errors": [],
    "http_status": 200,
    "bytes": 266660,
    "sha256": "7717c97efeb568964fb597d16fed8c70c0e2a4a5eca21a6a95589acd453e8aaa",
    "fetched_at_local": "2026-10-16T04:48:16-05:00",
    "n_rows": 1
  }
}
```

Total filas unificadas: **6541**

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
