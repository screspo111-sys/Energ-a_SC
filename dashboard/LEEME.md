# Dashboard CELEC SUR — datos compactos

En este repositorio la raíz del proyecto es la carpeta del repo (los scripts ya no usan `/workspace/ecu`). La página pública se arma con `dashboard/scripts/build_pagina.py` y se cifra antes de GitHub Pages.



Generado: **2026-10-05 ~00:49 America/Guayaquil (UTC-5)**. CSV regenerados de nuevo 2026-10-06 ~08:49 por la rutina diaria (los hallazgos de abajo son de la corrida de las 00:49).  
Carpeta: `/workspace/ecu/dashboard/`.  
No se modificó `generacion_unificada.csv` ni `collect_all.py`. Script reproducible: `build_dashboard_csvs.py`.

## Archivos CSV (para subir a claude.ai)

| Archivo | Tamaño | Filas | Rango | Columnas / unidades |
|---------|--------|------:|-------|---------------------|
| `generacion_diaria_celec_sur.csv` | ~196 KB | 6865 | 2023-01-01 → 2026-10-04 | `fecha`, `planta`, `energia_MWh` |
| `generacion_horaria_30d.csv` | ~152 KB | 3600 | 2026-09-05 01:00 → 2026-10-05 00:00 (local) | `fecha_hora`, `planta`, `MWh` |
| `hidrologia_celec_sur.csv` | ~0,7 MB | ~16 000 | 2022-01-01 → ayer (dinámico) | `fecha`, `central`, `metrica`, `valor`, `origen` (`CELEC_promedio_diario` o `calculado_de_horarios`) |
| `cenace_mensual_tecnologia.csv` | ~18 KB | 721 | 2018-01 → 2026-07 | `mes`, `tecnologia`, `GWh` |
| `referencias.csv` | ~4 KB | 24 | — | capacidades, cotas min/max, mrid, fuentes |

Plantas en generación: `MAZAR`, `MOLINO`, `SOPLADORA`, `MSF`, `CELEC_SUR` (agregado).  
Centrales en hidrología: las mismas cuatro + `CUENCA_PAUTE` (solo `caudal_m3s`).  
Métricas hidro: `caudal_m3s` (m³/s, promedio diario) y `cota_msnm` (m s.n.m., promedio diario).  
**MOLINO** en hidrología corresponde al embalse **Amaluza** (etiquetas UI “Caudal/Cota Amaluza”).

---

## Fuentes y endpoints exactos

### CELEC SUR ORDS (sin login)

Base: `https://generacioncsr.celec.gob.ec:8443/ords/csr/`

**Energía diaria (histórico):**  
`GET .../{sardommaz|sardommol|sardomsop|sardommsf|sardomcsr}/{maz|mol|sop|msf|csr}EnerMes?fecha=01/MM/YYYY 00:00:00`  
→ ítems `loctimestamp` + `valueedit` (MWh/día). Usado para `generacion_diaria_celec_sur.csv` (2023-01 → 2026-10).

**Energía horaria (30 d):** desde `/workspace/ecu/data/generacion_unificada.csv` (colector previo `*EnerDia`).  
Ejemplo: `.../sardommaz/mazEnerDia?fecha=05/09/2026%2000:00:00`.

**Hidrología (promedio diario):**  
`GET .../sardomcsr/pointValuesMesAvg?mrid={MRID}&fechaInicio=...&fechaFin=...&fecha=01/MM/YYYY 00:00:00`  

MRIDs (extraídos del bundle Angular `main*.js` de https://generacioncsr.celec.gob.ec/graficasproduccion/ ):

| Serie | mrid |
|-------|------|
| Mazar caudal | 30538 |
| Mazar cota | 30031 |
| Molino/Amaluza caudal | 24811 |
| Molino/Amaluza cota | 24019 |
| Sopladora caudal | 90537 |
| Sopladora cota | 90919 |
| MSF caudal | 650538 |
| MSF cota | 650919 |
| Cuenca Paute caudal | 24812 |

También existe `csrCaudCuenMesAvg` (sin mrid) para caudal cuenca; los valores coinciden con mrid 24812.

**Horaria puntual (no empaquetada en CSV largo):**  
`.../sardomcsr/pointValues?mrid=...&fechaInicio=...&fechaFin=...&fecha=...` (24 puntos/día).

UI: https://generacioncsr.celec.gob.ec/graficasproduccion/

### CENACE indicadores

`cenace_mensual_tecnologia.csv` proviene de `generacion_unificada.csv` / fuente `CENACE_indicadores`, metrica `energia_mensual`, filtrado desde 2018.  
Origen típico: XLSX público de indicadores CENACE (energía neta por tecnología). Tecnologías: `hidroelectrica`, `termica`, `eolica`, `fotovoltaica`, `biomasa`, `biogas`, `total`.

### Referencias de capacidad / cotas

Ver `referencias.csv`. Resumen:

- CELEC SUR total **2027 MW** — https://www.celec.gob.ec/celecsur/produccion-en-linea-detalle/
- Mazar **170**, Molino **1100**, Sopladora **487**, MSF **270** MW — home/fichas CELEC SUR
- Cota operación Mazar **2098–2153** m s.n.m. — ficha Mazar + título UI
- Cotas UI Amaluza 1975–1991; Sopladora 1312–1318; MSF 783.33–792.86

---

## Hoy 5-oct-2026: sin valores aún

Consulta a `*EnerDia?fecha=05/10/2026 00:00:00` y `pointValues` (cota Mazar) el 2026-10-05 ~00:48 local: **24 ítems, todos `valueedit: null`** en las cinco plantas y en cota.  
Último día completo con datos: **2026-10-04**.

El sello `2026-10-05T00:00:00-05:00` en la serie horaria es el **último intervalo del día operativo 4-oct** (la API para `fecha=D` cubre ~01:00 local D → 00:00 local D+1), no generación del calendario 5-oct.

---

## Huecos y limitaciones

1. **Sin demanda SNI** en CSV: CENACE Info Operativa es HTML/Plotly sin API REST; no se inventó. Queda documentado en `referencias.csv`.
2. **Hidrología = promedio diario** (`pointValuesMesAvg`), no horaria. Para horaria usar `pointValues` día a día (más pesado).
3. **Sopladora `caudal_m3s`:** 11 días sin valor en 2023–2024 (p. ej. 2023-01-02, 2024-10-30/31, varios en nov-2024). Cotas y resto de series completas en el rango.
4. **`generacion_diaria`** usa solo `*EnerMes` (no suma de horarias) para evitar el artefacto del sello 00:00 del día siguiente.
5. Datos CELEC SUR = operación preliminar SCADA de las 4 hidro + agregado; **no** es el balance oficial ARCONEL ni incluye Coca Codo / térmica / eólica nacional.
6. CENACE mensual corta en **2026-07** (último mes en el dataset unificado).
7. Tamaño hidro ~444 KB (ideal &lt;300 KB no alcanzado sin recortar historia 2023+; sigue &lt;1 MB).

---

## Hallazgos objetivos (basados en los CSV)

1. **Caudal cuenca Paute (promedio diario):** último valor **96,25 m³/s** el 2026-10-04. Media sep-2026 ≈ **83,5 m³/s**, frente a sep-2024 ≈ **40,7** y sep-2023 ≈ **54,2**. Media 2023-01→2026-10 ≈ **111 m³/s**. Sep-2024 fue claramente más seco que sep-2026.

2. **Cota Mazar:** **2132,0 m s.n.m.** el 2026-10-04 (rango de operación 2098–2153). Hace 30 días (2026-09-04) estaba en **2146,0** → descenso de **~14 m** en un mes. En la sequía 2024 el mínimo de oct-2024 llegó a **~2111** (más bajo que el nivel actual).

3. **Mazar en cero (ventana horaria 30 d):** **96 de 720** horas con `MWh == 0` (13,3 %). Concentración fuerte: **23 h el 2026-10-03** y **24 h el 2026-10-04** (día completo en 0). Coincide con `energia_MWh == 0` diaria esos dos días. Otros tramos en 0: madrugadas del 19–20, 22, 27 y 30-sep-2026.

4. **Participación térmica nacional (CENACE):** media 2018–2023 ≈ **11,4 %** del total; media **2024 ≈ 23,9 %**. Pico **nov-2024: 53,7 %** térmica (998 GWh térmicos vs 798 GWh hidro). Jul-2026: térmica **477,9 GWh** / **14,2 %** del total (por encima del promedio 2018–2023, lejos del pico de sequía).

5. **Energía diaria agregada CELEC_SUR:** media sep-2026 ≈ **31 081 MWh/día** vs sep-2024 ≈ **20 515** y oct-2024 ≈ **11 322** (mes más crítico del dataset en esa cascada). Sep-2025 ya había recuperado (~29 961). Oct-2026 (días 1–4) media parcial ≈ **16 709** MWh/día, bajando respecto a septiembre.

6. **Mazar energía diaria:** media sep-2026 ≈ **2830 MWh/día** (min 1002); sep-2024 ≈ **1817**; oct-2024 ≈ **704** (con varios ceros). Pese al descenso de cota reciente, la producción de sep-2026 está por encima de la de la sequía 2024.

7. **MSF:** hidrología caudal y cota disponibles en todo el rango 2023–2026 (mrid 650538 / 650919). Energía media sep–oct 2026 ≈ **1316 MWh/día**; Molino ≈ **15 991**; Sopladora ≈ **8687**.

8. **Capacidad instalada citada:** 170+1100+487+270 = **2027 MW** (coherente con el texto institucional CELEC SUR). No se halló serie pública compacta de demanda SNI para empaquetar aquí.

---

## Cómo regenerar

```bash
/workspace/ecu/.venv/bin/python /workspace/ecu/dashboard/build_dashboard_csvs.py
```

Metadatos de recolección: `raw/hidro_meta.json`, `raw/ener_meta.json`, `raw/build_summary.json`.

---

## KPI «Días estimados hasta posible déficit / cortes» (añadido 2026-10-07) — ESTIMACIÓN PROPIA, NO OFICIAL

Rutina diaria (un solo comando): `bash /workspace/ecu/dashboard/scripts/actualizar_tablero_energia.sh`

| Archivo | Contenido |
|---|---|
| `demanda_sni.csv` | demanda SNI: `mensual` 2018-01→2026-07 (CENACE indicadores, proxy = producción neta total), `diaria` y `mes_a_la_fecha` desde CENACE Info Operativa (se acumula con cada corrida), día de demanda máxima histórica |
| `oferta_sni_diaria.csv` | MWh/día por central (Coca Codo, Paute, Sopladora, Mazar, Agoyán, San Francisco, Delsitanisagua, MSF, Otras hidro, Térmica, Gas natural, Renovable, importación, exportación) — CENACE Info Operativa |
| `raw/cenace_infoop/*.html` | HTML archivado de cada consulta (fuente reprocesable) |
| `modelo/curva_mazar_empirica.csv` | área/volumen útil de Mazar por tramo de 5 m, estimada de datos (no hay curva oficial pública) |
| `modelo/proyeccion_escenarios.csv` | simulación diaria 365 d por escenario |
| `modelo/supuestos.csv` | cada parámetro: DATO / ESTIMADO / SUPUESTO + fuente |
| `kpi_deficit.json` / `kpi_deficit.html` | KPI para el tablero (JSON para integrar en el artifact; HTML autocontenido) |

Scripts: `scripts/cenace_infoop.py` (parser Plotly base64), `scripts/actualizar_demanda.py`, `scripts/modelo_deficit.py`, `scripts/actualizar_tablero_energia.sh`.
Semáforo (hasta 2026-10-07 por la mañana): menor entre déficit y Mazar en 2098 m. **Reemplazado el 2026-10-07 por la noche: ver sección siguiente (umbral 2115 m).**


---

## Cambios del 2026-10-07 (noche) — colector, umbral 2115 m, probabilidad de apagones, estado nacional

### 1. Colector de hidrología (por qué se quedaba en el 4-oct)
- **Causa:** `build_dashboard_csvs.py` tenía las fechas fijas (`today = 2026-10-05`, `hist_end = 2026-10-04`). CELEC sí publicaba los promedios diarios del 5 y 6-oct en `pointValuesMesAvg`; simplemente no se pedían.
- **Arreglo:** `today` = fecha local actual y `hist_end` = ayer (último día completo; el día en curso es parcial y no entra al CSV). Historia desde **2022-01-01** (la necesita el modelo de probabilidad).
- **Respaldo horario:** para los últimos 15 días, cada serie sin promedio diario publicado se calcula como promedio de las lecturas horarias de `.../sardomcsr/pointValues` (mínimo 18 horas con valor) y se marca `origen = calculado_de_horarios`. Si CELEC no tiene datos, el día queda vacío y se registra `sin_datos_CELEC` en `raw/hidro_meta.json` / `raw/build_summary.json` (`hidro_fallback`). No se rellena nada.
  - Prueba 6-oct (Mazar): promedio horario 2131,78 m y 31,82 m³/s frente al publicado 2131,75 m y 31,66 m³/s (la diferencia viene de que el promedio CELEC usa datos sub-horarios).
- `hidrologia_ultima_lectura.json`: última lectura horaria (día en curso) de cota/caudal de Mazar y caudal de la cuenca; informativo.
- **Cuadre con Ecuanomía:** su «caudal 40,4 m³/s» es la **media móvil de 7 días** del afluente (nuestro valor del 6-oct: 40,4); sus caudales diarios son idénticos a los de CELEC. Su cota del 6-oct (2131,27–2131,3) parece ser la lectura de cierre del día (lectura horaria de las 23:00: 2131,32); el promedio diario de CELEC es 2131,75.

### 2. Modelo de déficit (`scripts/modelo_deficit.py`)
- **Umbral principal = 2115 m s.n.m. (cota crítica, SUPUESTO por referencia histórica):** en 2023–2024, al cruzar ~2115 m CELEC redujo el turbinado de Mazar y vinieron los racionamientos. **KPI = días/fecha hasta 2115 m en el escenario de caudal actual.**
- Secundarios: días hasta **2098 m** (mínima operativa, ficha CELEC) y días hasta **oferta < demanda**.
- **Bajo 2115 m el turbinado se limita a 35 m³/s** (mismo supuesto que Ecuanomía). Consecuencia: con afluente > 35 m³/s la cota se estabiliza cerca de 2115 m y puede no llegar nunca a 2098 m; a cambio, Paute produce menos energía y el déficit llega antes.
- Escenarios: caudal actual, seco (P10), réplica estiaje 2024, **normal (P50, nuevo)**, húmedo (P85). Cada uno con días/fecha a 2115, a 2098 y a déficit.
- Semáforo con los días a 2115 m: verde >60, amarillo 30–60, rojo <30. `semaforo_prudente` = mismo criterio en el escenario seco.
- Rótulo «Estimación propia, no oficial» en JSON y HTML. Nota de referencia: *Ecuanomía (https://mazar.ecuanomia.com) estimó el 6-oct-2026, escenario normal, 2115 m en 23 días (29-oct); seco en 16 días (22-oct); probabilidad de apagones 21 %.*
- `kpi_historial.csv`: ahora lo escribe el modelo (upsert por `fecha_corrida`, idempotente). Columna `umbral_principal` (2098 en filas antiguas, 2115 desde hoy).

### 3. Probabilidad de apagones (`scripts/modelo_probabilidad.py`, llamado desde el modelo)
- Etiqueta diaria 2022–2026: 1 si hubo apagones/racionamientos generalizados ese día o en los 30 siguientes. Periodos (fuentes de prensa en el código y en `modelo/logit_coeficientes.json`): 27-oct→15-dic-2023, 16-abr→30-abr-2024, 23-sep→19-dic-2024.
- Regresión logística (IRLS en numpy) con: cota de Mazar, ln(afluente media 7 d), ln(mediana histórica del afluente de los 30 días siguientes para la época, ±7 días). Se excluyen los últimos 30 días del ajuste (etiqueta aún desconocida).
- Proyección diaria de 45 días por escenario (seco, normal, húmedo y actual) usando la cota simulada → `modelo/probabilidad_apagones.csv`. Primer día con probabilidad > 50 % en `kpi_deficit.json → probabilidad_apagones.primer_dia_mayor_50` y `dias_reserva`.
- Validación contra Ecuanomía (21 % el 6-oct): se reporta nuestra probabilidad y la que dan los coeficientes publicados por Ecuanomía (su `data.json`) aplicados a nuestros datos.
- Limitación fuerte: solo 3 crisis para aprender; métricas dentro de muestra.

### 4. Estado nacional (`scripts/estado_nacional.py`)
- `estado_nacional.json` (último día operativo de CENACE) y `estado_nacional_diario.csv` (serie, upsert por fecha).
- Generación por tecnología (hidráulica, térmica con detalle líquidos/gas natural, renovable no convencional), importación, exportación, demanda (energía, máxima y mínima).
- CENACE publica a diario solo el total RNC; el desglose eólica/solar/biomasa/biogás del día es ESTIMADO con la participación del último mes de CENACE indicadores (rotulado).
- Estatal vs privada: no hay dato diario. Se da (a) piso diario = centrales hidro de CELEC EP nombradas por CENACE; (b) CELEC EP 2025: 28 040 GWh netos = 84 % de la demanda nacional (Rendición de cuentas CELEC EP 2025); (c) ARCONEL 2025 por tipo de empresa (generadora/autogeneradora/distribuidora; no es público/privado).
- Capacidad instalada por tecnología: BNEE julio 2026.
- «RES»: no es sigla oficial en Ecuador. Se documenta «margen de reserva» (Regulación CONELEC 006/00), «reserva rodante» (Regulación ARCERNNR 001/24) y el criterio de CENACE de reservas del 10 % con 90 % de probabilidad (Resolución ARCONEL 004/25), más «renovable no convencional». Margen de reserva **nominal** = (potencia nominal SNI − demanda máxima del día) / demanda máxima: es un techo, porque CENACE no publica la potencia disponible.

### Rutina
`bash /workspace/ecu/dashboard/scripts/actualizar_tablero_energia.sh` → CELEC SUR → CENACE → estado nacional → modelo. Log acumulado en `raw/ultima_corrida.log`.
