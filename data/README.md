# Ecuador — generación unificada

Última actualización (local America/Guayaquil): **2026-10-21 09:58:04 -05**

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
    "n_rows": 1452,
    "requests_ok": 63,
    "requests_total": 75,
    "fecha_min": "2026-10-07T01:00:00-05:00",
    "fecha_max": "2026-10-21T09:00:00-05:00",
    "failures": [
      {
        "plant": "CELEC_SUR",
        "day": "2026-10-10",
        "url": "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=10/10/2026%2000%3A00%3A00",
        "ok": false,
        "n": 0,
        "error": "CELEC fetch failed after 3 tries: https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=10/10/2026%2000%3A00%3A00 (HTTP Error 503: )"
      },
      {
        "plant": "CELEC_SUR",
        "day": "2026-10-11",
        "url": "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=11/10/2026%2000%3A00%3A00",
        "ok": false,
        "n": 0,
        "error": "CELEC fetch failed after 3 tries: https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=11/10/2026%2000%3A00%3A00 (HTTP Error 503: )"
      },
      {
        "plant": "CELEC_SUR",
        "day": "2026-10-12",
        "url": "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=12/10/2026%2000%3A00%3A00",
        "ok": false,
        "n": 0,
        "error": "CELEC fetch failed after 3 tries: https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=12/10/2026%2000%3A00%3A00 (The read operation timed out)"
      },
      {
        "plant": "CELEC_SUR",
        "day": "2026-10-13",
        "url": "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=13/10/2026%2000%3A00%3A00",
        "ok": false,
        "n": 0,
        "error": "CELEC fetch failed after 3 tries: https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=13/10/2026%2000%3A00%3A00 (<urlopen error timed out>)"
      },
      {
        "plant": "CELEC_SUR",
        "day": "2026-10-14",
        "url": "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=14/10/2026%2000%3A00%3A00",
        "ok": false,
        "n": 0,
        "error": "CELEC fetch failed after 3 tries: https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=14/10/2026%2000%3A00%3A00 (HTTP Error 404: )"
      },
      {
        "plant": "CELEC_SUR",
        "day": "2026-10-15",
        "url": "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=15/10/2026%2000%3A00%3A00",
        "ok": false,
        "n": 0,
        "error": "CELEC fetch failed after 3 tries: https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=15/10/2026%2000%3A00%3A00 (HTTP Error 404: )"
      },
      {
        "plant": "CELEC_SUR",
        "day": "2026-10-16",
        "url": "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=16/10/2026%2000%3A00%3A00",
        "ok": false,
        "n": 0,
        "error": "CELEC fetch failed after 3 tries: https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=16/10/2026%2000%3A00%3A00 (HTTP Error 404: )"
      },
      {
        "plant": "CELEC_SUR",
        "day": "2026-10-17",
        "url": "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=17/10/2026%2000%3A00%3A00",
        "ok": false,
        "n": 0,
        "error": "CELEC fetch failed after 3 tries: https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=17/10/2026%2000%3A00%3A00 (HTTP Error 404: )"
      },
      {
        "plant": "CELEC_SUR",
        "day": "2026-10-18",
        "url": "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=18/10/2026%2000%3A00%3A00",
        "ok": false,
        "n": 0,
        "error": "CELEC fetch failed after 3 tries: https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=18/10/2026%2000%3A00%3A00 (HTTP Error 404: )"
      },
      {
        "plant": "CELEC_SUR",
        "day": "2026-10-19",
        "url": "https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=19/10/2026%2000%3A00%3A00",
        "ok": false,
        "n": 0,
        "error": "CELEC fetch failed after 3 tries: https://generacioncsr.celec.gob.ec:8443/ords/csr/sardomcsr/csrEnerDia?fecha=19/10/2026%2000%3A00%3A00 (HTTP Error 404: )"
      }
    ],
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
    "bytes": 266623,
    "sha256": "f9022f3f516ee62d1dafe279953141645ea1e371c23178232c2329a09dd40801",
    "fetched_at_local": "2026-10-21T09:58:04-05:00",
    "n_rows": 1
  }
}
```

Total filas unificadas: **7283**

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
