# Checklist de verificación — tablero energía v2 (generado 7-oct-2026 21:18 UTC-5)

Fuente de cada cifra: archivos de `/workspace/ecu/dashboard/`. EN = `estado_nacional.json`; KPI = `kpi_deficit.json`; PA = `modelo/probabilidad_apagones.csv`; PE = `modelo/proyeccion_escenarios.csv`.
Marcar ✔ si la cifra aparece en el tablero con su fecha.

## Fechas
- [ ] Hidrología al **6-oct-2026** — KPI `estado_actual.fecha_hidro`
- [ ] Día operativo CENACE **6-oct-2026** — EN `fecha_dia_operativo`
- [ ] Generado **7-oct-2026 21:18** — KPI/EN `generado`
- [ ] Rótulo «Estimación propia, no oficial» — KPI `rotulo`

## 1) Estado general (6-oct-2026)
| Cifra | Fuente |
|---|---|
| Hidráulica 77.991 MWh · 75,0 % | EN `generacion_MWh.hidraulica` (75.02) / `estado_nacional_diario.csv` |
| Térmica 25.358 MWh · 24,4 % | EN `generacion_MWh.termica` (24.39) |
| Líquidos 22.541 MWh | EN `termica.detalle.combustibles_liquidos_MCI_turbovapor` |
| Gas natural 2.816 MWh | EN `termica.detalle.gas_natural` |
| RNC 567 MWh · 0,55 % | EN `renovable_no_convencional` |
| Eólica 227 / solar 24 / biomasa 274 / biogás 43 MWh (ESTIMADO) | EN `desglose_RNC_estimado_dia_MWh.valores` (suma 568 por redondeo) |
| 40 % / 4,3 % / 48,3 % / 7,5 % (jul-2026) | EN `desglose_RNC_estimado_dia_MWh.mes_GWh.*.pct_de_RNC` |
| Importación 51 / exportación 79 MWh | EN `importacion`, `exportacion` |
| Producción total 103.966 MWh | EN `produccion_total_incl_importacion` |
| Demanda 103.887 MWh | EN `demanda.energia_MWh` |
| Punta 5.268 MW 19:30; mínima 3.465 MW | EN `demanda.max_MW` 5268.38, `hora_max`, `min_MW` 3465.26 |
| Punta histórica 5.635 MW (15-jul-2026) | `demanda_sni.csv` fila `dia_demanda_max_historica`; KPI `estado_actual.demanda_punta_max_MW` |
| Renovable total con hidro 75,6 % | EN `RES.renovables.renovable_total_incl_hidro_pct` 75.56 |
| Piso estatal diario 57 % (59.251 MWh), 8 centrales | EN `estatal_vs_privada.diario` (56.99) |
| CELEC EP 2025: 28.040 GWh = 84 %; resto 16 % | EN `estatal_vs_privada.anual_CELEC_EP_2025` |

## 2) RES (6-oct-2026)
| Cifra | Fuente |
|---|---|
| Margen nominal 53,1 % | EN `RES.reserva.calculo_hoy.margen_reserva_nominal_pct` |
| Con interconexiones 65,4 % (650 MW) | EN `...margen_reserva_nominal_con_importacion_pct`, `importacion_nominal_MW` |
| Potencia nominal SNI 8.064,7 MW | EN `...potencia_nominal_SNI_MW` (BNEE jul-2026) |
| CENACE 10 % con 90 % de probabilidad | EN `RES.reserva.definiciones[2]` (Res. ARCONEL 004/25) |
| Texto «techo teórico» | EN `...calculo_hoy.advertencia` |

## 3) Días de reserva
| Cifra | Fuente |
|---|---|
| 31 días → 7-nov-2026 (2.115 m, caudal actual) | KPI `dias`, `fecha`, `dias_reserva.dias_hasta_2115` |
| >50 % desde 19-oct (12 d), caudal actual | KPI `dias_reserva.primer_dia_prob_mayor_50.actual`; PA primer `prob_apagon`>0,5 |
| Semáforo AMARILLO; reglas >60 / 30–60 / <30 | KPI `semaforo`, `umbrales` |
| Escenario seco ROJO, 20 d · 27-oct | KPI `semaforo_prudente`, `escenarios.seco.dias_2115` |

## 4) Probabilidad
| Cifra | Fuente |
|---|---|
| Hoy 19 % (dato 6-oct) | KPI `probabilidad_apagones.prob_hoy` 0.187 |
| Ecuanomía 21 % (6-oct) | KPI `validacion_ecuanomia.prob_publicada_ecuanomia` |
| Coef. Ecuanomía con nuestros datos 15,5 % | KPI `prob_coef_ecuanomia_con_nuestros_datos` |
| >50 %: seco 15-oct (8 d), normal 17-oct (10 d), actual 19-oct (12 d), húmedo nunca | KPI `primer_dia_mayor_50` |
| Máximos 45 d: seco 100 %, normal 98,6 %, actual 95,2 %, húmedo 23,5 % | KPI `prob_max_45d` |
| Curva 7-oct→20-nov cada 3 días (tabla del prompt) | PA, `prob_apagon` por `escenario`/`fecha` (redondeo a entero) |
| Estiaje 2024 sin curva | PA solo tiene seco/normal/humedo/actual |

## 5) Mazar (6-oct-2026)
| Cifra | Fuente |
|---|---|
| Cota 2.131,75 m | KPI `estado_actual.cota_mazar`; hidrologia_celec_sur.csv 2131.754 |
| Rango 2.098–2.153 m | KPI `cota_min`, `cota_max`; referencias.csv |
| Entra 31,7 (día) / 40,4 (7 d) / 40,8 (14 d) m³/s | KPI `afluente_mazar_dia_m3s`, `_7d_`, `_14d_` |
| Turbinado 68,5 m³/s (14 d, estimado) | KPI `turbinado_mazar_14d_m3s`; supuestos.csv `turbinado_mazar_politica` |
| Tendencia −0,44 m/día (14 d) | KPI `tendencia_cota_m_dia_14d` −0.437 |
| 92,8 hm³ sobre 2.115; 168,5 hm³ útil | KPI `volumen_sobre_2115_hm3`, `volumen_util_restante_hm3` |
| 2.115 m principal; 35 m³/s bajo 2.115 | supuestos.csv `cota_critica_mazar`, `turbinado_bajo_cota_critica` |
| 2.098 m secundario | supuestos.csv `cota_min_operativa_mazar` |

Tabla de escenarios — KPI `escenarios.*` (re-verificada contra PE: primer día cota ≤ 2115 / ≤ 2098 / margen_MWh < 0):
| Escenario | 2.115 m | 2.098 m | Déficit |
|---|---|---|---|
| Seco (P10) | 20 d · 27-oct | 49 d · 25-nov | 7 d · 14-oct |
| Normal (P50) | 26 d · 2-nov | no llega (mín. 2.104 m) | 12 d · 19-oct |
| Caudal actual | 31 d · 7-nov | no llega (mín. 2.114,4 m) | 32 d · 8-nov |
| Estiaje 2024 | 22 d · 29-oct | 57 d · 3-dic | 7 d · 14-oct |
| Húmedo (P85) | no llega | no llega | sin déficit |

## 6) Supuestos / límites / Ecuanomía
- [ ] 3 crisis: 27-oct→15-dic-2023, 16→30-abr-2024, 23-sep→19-dic-2024 — `modelo/logit_coeficientes.json periodos_apagon`
- [ ] Térmica disponible supuesta 33.270 MWh/día (nov-2024); actual 25.358; holgura 7.912 — KPI `estado_actual`, supuestos.csv `termica_max_disponible`
- [ ] Ecuanomía 6-oct: normal 23 d (29-oct), seco 16 d (22-oct), 21 % — KPI `referencia_externa`
- [ ] Nuestro: normal 26 d (2-nov), seco 20 d (27-oct), 19 %
- [ ] Link https://mazar.ecuanomia.com

## Valores viejos PROHIBIDOS (deben desaparecer)
- `145 d · 01/03/2027` (déficit caudal actual viejo; kpi_historial.csv fila 1: 145, 2027-03-01)
- `49 d · 25/11/2026` como «caudal actual → mínimo» (kpi_historial.csv fila 1 `dias_mazar_min_actual` 49)
- `−0,59 m/día`, «baja 0,59 m por día → 49 días»
- `57 días` (versión anterior al cambio a 49)
- `8 d · 15/10/2026` como déficit seco (ahora 7 d · 14-oct); `29 d · 05/11/2026`; `9 d · 16/10/2026`; `33 d · 09/11/2026`
- `Semáforo al 4 oct 2026`, `Vigilancia · 1 punto de 8`, `2132 m s.n.m.`, `109 %`, `81,9 frente a 74,8 m³/s`, `61,8 %`, `62 % de su rango`, `14,2 %` térmica jul-2026
- Umbral principal 2.098 m (ahora es 2.115 m)

### Coincidencias VÁLIDAS (no confundir con valores viejos)
- `49 d · 25-nov` = seco hasta 2.098 m · `57 d · 3-dic` = estiaje 2024 hasta 2.098 m
- `8 d · 15-oct` = primer día >50 % escenario seco
- `57 %` = piso estatal diario
