"""Unified Ecuador electricity generation schema."""

from __future__ import annotations

COLUMNS = [
    "fecha_hora_local",
    "fecha_hora_utc",
    "granularidad",
    "ambito",
    "codigo_planta",
    "nombre_planta",
    "tecnologia",
    "empresa_uunn",
    "sistema",
    "metrica",
    "valor",
    "unidad",
    "fuente",
    "url_origen",
    "calidad",
    "extra_json",
]

TZ_LOCAL = "America/Guayaquil"
