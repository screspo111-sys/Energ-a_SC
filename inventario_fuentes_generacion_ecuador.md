# Inventario de fuentes públicas — Generación eléctrica Ecuador

Fecha de relevamiento: 5 oct 2026 (hora Ecuador / UTC-5).  
Alcance: fuentes oficiales `.gob.ec` (y portales afiliados CENACE/CELEC/ARCONEL/INAMHI).  
**No se inventan cifras de generación**; solo se documenta qué publica cada fuente, formatos y cobertura.

---

## Resumen ejecutivo

| Prioridad | Fuente | Nivel | Frecuencia útil | Formato scrapeable | Login |
|-----------|--------|-------|-----------------|--------------------|-------|
| **A** | CELEC SUR — gráficas de producción | Planta (4 hidro) + cascada | Horaria / diaria / mensual / anual / multianual | **API ORDS JSON** + CSV UI | No |
| **A** | CENACE — Información Operativa | Nacional + principales hidro | Casi tiempo real (SCADA preliminar) | HTML embebido (Plotly) | No |
| **A** | CENACE — Indicadores (energía neta) | Nacional por tecnología | Mensual (archivo XLSX) | **XLSX público** | No |
| **A** | ARCONEL — BNEE | Nacional por tecnología | Mensual (lag ~n+2) | **XLS** | No |
| **B** | ARCONEL — Estadística anual | Nacional / provincial / parque | Anual | PDF | No |
| **B** | CENACE — Biblioteca (informes) | Nacional / mix | Mensual / anual | PDF | No |
| **C** | SIMEM / SisdatBI / BOSNINET | Mercado / bitácora | Operativo | Portales | **Sí** |
| **C** | INAMHI | Hidrología (caudal) | Variable | Visor / anuarios PDF | No |
| **Gap** | CELEC Coca Codo / otras UU.NN. | — | — | **Sin dashboard público** comparable a CELEC SUR | — |
| **Gap** | Generación solar/eólica por planta en tiempo real | — | — | No hallado en sitios oficiales abiertos | — |

---

## 1. CELEC EP — Unidad de Negocio CELEC SUR

| Campo | Detalle |
|-------|---------|
| **Nombre oficial** | Corporación Eléctrica del Ecuador CELEC EP — Unidad de Negocio CELEC SUR |
| **UI** | https://generacioncsr.celec.gob.ec/graficasproduccion/ |
| **Página institucional** | https://www.celec.gob.ec/celecsur/produccion-en-linea-detalle/ |
| **API (sin login, HTTPS :8443)** | Base: `https://generacioncsr.celec.gob.ec:8443/ords/csr/` |

### Centrales / cobertura

Cascada Paute + Minas San Francisco (capacidad instalada citada en la página CELEC SUR: **2027 MW**):

| Código en API | Central | Endpoints energía |
|---------------|---------|-------------------|
| `sardommaz` / Maz | **Mazar** | `.../sardommaz/mazEnerDia\|Mes\|Anio\|Anios` |
| `sardommol` / Mol | **Molino** (complejo Paute) | `.../sardommol/molEnerDia\|Mes\|Anio\|Anios` |
| `sardomsop` / Sop | **Sopladora** | `.../sardomsop/sopEnerDia\|Mes\|Anio\|Anios` |
| `sardommsf` / Msf | **Minas San Francisco** | `.../sardommsf/msfEnerDia\|Mes\|Anio\|Anios` |
| `sardomcsr` / Csr | **Agregado CELEC SUR** + caudal cuenca Paute | `.../sardomcsr/csrEnerDia\|Mes\|Anio\|Anios` y `csrCaudCuen*` |

**No incluye** Coca Codo Sinclair, Agoyán, térmica, eólica ni solar.

### Métricas (UI + API)

- **Energía (MWh)** — series por periodo (eje Y etiquetado “Energía(MWh)” en el JS de la app).
- **Unidades en línea** (conteo).
- **Hidrología**: caudal (m³/s), cota (m.s.n.m.) por central; caudal cuenca Paute.
- Periodos UI: **Diaria / Mensual / Anual / Multianual**; tipos **Producción** e **Hidrología**.
- Resolución observada en API diaria: **24 puntos horarios** (`loctimestamp` + `valueedit`).
- Histórico multianual de energía agregada CSR: series anuales desde ~1983 (endpoint `csrEnerAnios`).

### Formatos / descarga

- Botón **“Descargar CSV”** en la UI (AngularCsv; columnas dinámicas: `Fecha`, `UnidadesMaz|Mol|Sop|Msf`, `Caudal*`, `Cota*`, `CaudalCuencaPaute`, etc.).
- **API ORDS JSON** pública (probado sin autenticación), ejemplo:  
  `GET .../sardommaz/mazEnerDia?fecha=01/09/2026%2000:00:00`  
  → `{"items":[{"loctimestamp":"...","valueedit":...}, ...]}`
- Series puntuales: `.../sardomcsr/pointValues?mrid=...&fechaInicio=...&fechaFin=...&fecha=...` (mriids embebidos en el bundle Angular, p. ej. unidades/caudal/cota por central).
- Login: **no** requerido para UI ni endpoints de datos observados.

### Actualización

Casi continua / horaria para el día operativo; valores futuros o horas aún no cerradas pueden venir `null`. Datos preliminares de operación (no son el balance oficial ARCONEL).

---

## 2. CENACE — Operador Nacional de Electricidad

| Campo | Detalle |
|-------|---------|
| **Nombre oficial** | Operador Nacional de Electricidad — CENACE |
| **Sitio** | https://www.cenace.gob.ec |

### 2.1 Información Operativa (tablero público)

| Campo | Detalle |
|-------|---------|
| **URL** | http://www.cenace.gob.ec/info-operativa/InformacionOperativa.htm |
| **Login** | No |
| **Formato** | HTML estático con gráficos **Plotly** embebidos (sin API REST documentada; hay que parsear el HTML o los `script` Plotly) |
| **Frecuencia** | Vista de **producción y demanda en tiempo real** + acumulados **diario / mensual / anual** (datos **preliminares SCADA**, sujetos a revisión) |

**Métricas (nacionales):**

- Producción energética (MWh o GWh según ventana): total, hidráulica, térmica, renovable no convencional, exportación, importación.
- Curva de generación (MW) por tecnología (Hidráulica / Renovable / Térmica / Imp-Exp).
- Demanda SNI y por empresa de distribución (MW).

**Detalle hidro (barras, no todas las centrales del país):** en la ventana diaria observada aparecen, entre otras, etiquetas: **Coca Codo, Paute, Sopladora, San Francisco, Delsitanisagua, Minas San Francisco** (+ “Otras Hidro” / Agoyán / Mazar en ventanas acumuladas).  
**Otra generación:** Térmica, Gas Natural, Renovable (agregado).

**Descarga:** no hay CSV/API oficial en esta página; scraping del HTML/Plotly o captura periódica.

### 2.2 Energía neta por tipo de tecnología (indicadores)

| Campo | Detalle |
|-------|---------|
| **Página** | https://www.cenace.gob.ec/energia-neta-producida-por-las-centrales-de-generacion-gwh/ |
| **Archivo** | https://www.cenace.gob.ec/wp-content/plugins/ez-addons/data/indicadores.xlsx |
| **Login** | No |
| **Formato** | **XLSX** (hojas `datos`, `produccion`) |

**Contenido verificado:**

- Hoja `datos`: columnas `Año`, `Mes`, `Biogás`, `Biomasa`, `Eólica`, `Fotovoltaica`, `Hidroeléctrica`, `Térmica`, `TOTAL` (GWh mensuales; serie desde **2010** hasta meses disponibles de 2026).
- Hoja `produccion`: anuales de producción / demanda interna / exportación Col-Perú.

**Cobertura:** nacional por **tecnología**, no por planta.

### 2.3 SIMEM — Sistema de Información del Mercado Eléctrico

| Campo | Detalle |
|-------|---------|
| **Info** | https://www.cenace.gob.ec/sistema-de-informacion-del-mercado-electrico-simem/ |
| **Portal** | https://simem.cenace.gob.ec/pmis-web |
| **Login** | **Sí** — certificado digital / credenciales (trámite CENACE-012; contacto `simemconsulta@cenace.gob.ec`) |
| **Público** | No; orientado a participantes mayoristas y entidades homologadas |

Útil para generación/transacciones comerciales a nivel agente, pero **fuera del alcance “open data” inmediato**.

### 2.4 BOSNINET — Bitácora operativa SNI

| Campo | Detalle |
|-------|---------|
| **Página** | https://www.cenace.gob.ec/sistema-bitacora-operativa-del-sistema-nacional-interconectado-bosninet/ |
| **App** | http://sirio.cenace.gob.ec/bitacoraweb |
| **Login** | Esperable (sistema operativo interno); no verificado como open data |

### 2.5 Biblioteca / informes

| Campo | Detalle |
|-------|---------|
| **URL** | https://www.cenace.gob.ec/biblioteca/ |
| **Formatos** | PDF vía download-monitor |
| **Contenido relevante** | Informes Anuales, Informes Ejecutivos de Gestión Mensual, Informe Operativo Anual, formularios de declaración de parámetros de generación |

Buenos para validación histórica y metodologías; malos para series horarias automatizadas.

### 2.6 Otros servicios CENACE (comercial / medición)

- SIMEC, Redespacho, SAMWEB: servicios a participantes; no inventariados como descarga abierta de generación.

---

## 3. ARCONEL (ex ARCERNNR / Control Eléctrico)

| Campo | Detalle |
|-------|---------|
| **Nombre oficial** | Agencia de Regulación y Control de Electricidad — ARCONEL |
| **Hub estadístico** | https://arconel.gob.ec/estadistica-del-sector-electrico/ |
| **Espejo histórico** | https://controlelectrico.gob.ec/… |

### 3.1 Balance Nacional de Energía Eléctrica (BNEE)

| Campo | Detalle |
|-------|---------|
| **URL** | https://arconel.gob.ec/balance-nacional-de-energia-electrica/ |
| **Ejemplo archivo** | https://arconel.gob.ec/wp-content/uploads/downloads/2026/10/BNEE_julio_2026.xls |
| **Login** | No |
| **Formato** | **XLS** (nacional) |
| **Frecuencia** | Mensual; publicación típica desde el **día 20 del mes n+2** (documentado en la página) |

**Métricas (agregado nacional / SNI):** potencia nominal y efectiva (MW); producción e importaciones (GWh) por: Hidráulica, Eólica, Fotovoltaica, Biomasa, Biogás, MCI, Turbogas, Turbovapor; importación Col/Perú; bloques de energía entregada / disponible / facturada.

**No es serie por central.**

### 3.2 Estadística Anual y Multianual del Sector Eléctrico

| Campo | Detalle |
|-------|---------|
| **Publicaciones** | https://arconel.gob.ec/publicaciones-estadistica-del-sector-electrico-2/ |
| **Ejemplo PDF 2025** | https://arconel.gob.ec/wp-content/uploads/downloads/2026/03/Estadistica2025.pdf |
| **Login** | No |
| **Formato** | PDF (tablas de capacidad, generación, distribución, etc.) |
| **Frecuencia** | Anual |

Incluye capítulos de generación (potencia por fuente, provincia, empresas; centrales nuevas del año). Fuente de **referencia oficial** del parque, no de operación horaria.

### 3.3 SisdatBI / Bases de datos

| Campo | Detalle |
|-------|---------|
| **SisdatBI** | https://sisdatbi.arconel.gob.ec/ — **registro / login** (`sisdat.soporte@controlelectrico…`) |
| **reportes.arconel.gob.ec** | En el relevamiento: **504 Gateway Timeout** (no usable al momento) |
| **Power BI pérdidas** | Enlace público embebido desde el hub de estadísticas (pérdidas de energía) |

### 3.4 Datos Abiertos Ecuador (catálogo)

Históricamente hay datasets (BNEE, producción parque generador, capacidad SNI) en https://www.datosabiertos.gob.ec/group/ener — varios con **corte antiguo (≈2021)**; preferir ARCONEL/CENACE actuales para series vivas.

---

## 4. Ministerio de Ambiente y Energía / planificación

| Campo | Detalle |
|-------|---------|
| **PME** | Plan Maestro de Electricidad (p. ej. PME 2023–2032 y actualizaciones) — https://www.ambienteyenergia.gob.ec/plan-maestro-de-electricidad/ |
| **Rol** | Planificación / expansión, no operación diaria |
| **Estadística 2025** | Presentada vía Ministerio + ARCONEL (instrumento anual; ver PDF ARCONEL) |

Útil como contexto de capacidad y proyectos; **no** como feed de generación horaria.

---

## 5. Otras unidades CELEC / operadores

| Unidad / tema | ¿Dashboard público de producción? | Notas |
|---------------|-----------------------------------|-------|
| **CELEC SUR** (Mazar, Molino, Sopladora, Minas SF) | **Sí** — ver §1 | Única UI CELEC con API ORDS abierta hallada |
| **Coca Codo Sinclair / Manduriacu** | **No** hallado equivalente | Sitio https://www.celec.gob.ec/cocacodo/ (ficha técnica); generación aparece en tablero CENACE agregado |
| **Hidropaute** (nombre histórico) | Absorbido en CELEC SUR / cascada Paute | Datos vía §1 |
| **Hidroagoyán, Termoesmeraldas, Termogas Machala, etc.** | Sin portal “producción en línea” público equivalente | Solo menciones institucionales / CENACE agregado |
| **Operadores solares / eólicos** | Sin portales oficiales de generación horaria por planta encontrados | Totales mensuales en CENACE `indicadores.xlsx` y BNEE |

---

## 6. INAMHI (hidrología de apoyo)

| Campo | Detalle |
|-------|---------|
| **Anuarios hidrológicos** | https://servicios.inamhi.gob.ec/anuarios-hidrologicos/ |
| **Visor** | https://inamhi.gob.ec/info/ |
| **Login** | No para contenido público |
| **Relevancia** | Caudales / niveles de ríos (insumo hidro); **no** es generación eléctrica |
| **Formatos** | Visor web, PDF anuarios, boletines |

Complementa CELEC SUR (cota/caudal) y el análisis de Coca Codo (filo de agua), pero no sustituye MWh.

---

## 7. Duplicación y vacíos

### Traslapes (mismo fenómeno, distinta autoridad/calidad)

1. **Energía hidro CELEC SUR** aparece en API CELEC (planta) y, a nivel agregado, en CENACE operativa / indicadores / BNEE.
2. **Matriz por tecnología (GWh)** se solapa entre CENACE `indicadores.xlsx` y ARCONEL BNEE / Estadística anual — conviene marcar `fuente` y usar ARCONEL como **oficial de balance**, CENACE como **operativo/preliminar**.
3. **Coca Codo** solo aparece de forma agregada en CENACE (no hay serie horaria oficial CELEC CCS pública comparable a SUR).

### Gaps críticos para un dataset “todas las plantas”

- Sin feed abierto **planta a planta** nacional en tiempo real (salvo 4 hidro CELEC SUR).
- Térmicas y REN no convencionales: solo agregados nacionales.
- SIMEM/SisdatBI podrían llenar el gap **con credenciales**, no open data.
- `reportes.arconel.gob.ec` inaccesible al momento del relevamiento.

---

## 8. Forma sugerida de dataset unificado

Tabla larga (una fila = una observación), lista para Parquet/CSV:

```text
fecha_hora_local     # America/Guayaquil, ISO-8601
fecha_hora_utc       # ISO-8601 Z
granularidad         # hora | dia | mes | anio
ambito               # planta | tecnologia | nacional | empresa_distribucion
codigo_planta        # nullable; catálogo propio (ej. CELEC_MAZAR, CCS, …)
nombre_planta        # nullable
tecnologia           # hidro | termica_mci | turbogas | turbovapor | eolica | fv | biomasa | biogas | mix | desconocida
empresa_uunn         # CELEC_SUR | CELEC_CCS | CENACE_AGREGADO | ARCONEL_BNEE | …
sistema              # SNI | aislado | NA
metrica              # energia_mwh | potencia_mw | caudal_m3s | cota_msnm | unidades_en_linea | demanda_mw | ...
valor                # float
unidad               # MWh | MW | m3/s | msnm | GWh | ...
fuente               # celec_sur_ords | cenace_info_op | cenace_indicadores | arconel_bnee | ...
url_origen           # string
calidad              # preliminar_scada | oficial_balance | declarado
extra_json           # mrid, periodo_ui, notas
```

**Catálogo mínimo de plantas** (tabla aparte): `codigo_planta`, nombre, tecnología, potencia_efectiva_mw (desde Estadística ARCONEL), lat/lon si hay, uunn, activo.

**Reglas:**

- No mezclar MWh horarios CELEC con GWh mensuales BNEE sin convertir y etiquetar `granularidad` + `calidad`.
- Preferir suma de plantas CELEC SUR solo para esas cuatro; el resto del país desde CENACE/ARCONEL agregados hasta tener SIMEM u otra fuente planta.

---

## 9. Próximo paso recomendado (recolección)

**Empezar por el path de menor fricción y mayor valor horario:**

1. **Colector CELEC SUR (API ORDS)**  
   - Script diario que, para cada `{maz,mol,sop,msf,csr}` y cada `*EnerDia`, pida `fecha=DD/MM/YYYY 00:00:00` del día D-1 (y opcionalmente el día en curso).  
   - Persistir JSON → normalizar a la forma unificada (`metrica=energia_mwh`, `granularidad=hora`).  
   - Añadir caudales/cotas vía `pointValues` + mriids del bundle.  
   - Respetar rate limits; un solo proceso cron.

2. **Snapshot CENACE Información Operativa**  
   - Descargar HTML 1–4 veces/día; parsear totales nacionales y barras de principales hidro; guardar raw HTML + filas unificadas (`calidad=preliminar_scada`).

3. **Pull mensual de archivos oficiales**  
   - `indicadores.xlsx` (CENACE) y último `BNEE_*.xls` (ARCONEL) → filas `granularidad=mes`, `ambito=tecnologia|nacional`, `calidad=oficial_balance` para BNEE.

4. **Después (si se necesita planta-completa)**  
   - Evaluar solicitud de acceso SIMEM / SisdatBI (proceso formal, no scraping).  
   - Monitorear si CELEC publica dashboards para CCS u otras UU.NN.

**No priorizar** scraping de PDFs de biblioteca/estadística anual salvo para enriquecer el catálogo de plantas y validar totales anuales.

