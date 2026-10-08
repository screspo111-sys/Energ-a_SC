#!/usr/bin/env python3
"""Estado nacional del último día operativo publicado por CENACE + capacidad/propiedad (ARCONEL, CELEC) + «RES».

Fuentes (todas públicas):
  - CENACE Información Operativa (HTML con Plotly embebido; pestaña diaria = último día validado, SCADA preliminar).
    Se reprocesan TODOS los HTML archivados en raw/cenace_infoop/ (los descarga actualizar_demanda.py).
  - CENACE indicadores (cenace_mensual_tecnologia.csv): desglose mensual eólica/solar/biomasa/biogás.
  - ARCONEL BNEE julio 2026 (raw/BNEE_julio_2026.xls): potencia nominal por tecnología, producción año móvil.
  - ARCONEL Estadística del Sector Eléctrico 2025 (marzo 2026): producción y potencia por TIPO de empresa.
  - CELEC EP, Rendición de cuentas 2025: energía neta de CELEC EP y su aporte a la demanda nacional.
Salidas: estado_nacional.json, estado_nacional_diario.csv (upsert por fecha; idempotente).
"""
from __future__ import annotations
import json, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import cenace_infoop as ci

TZ = ZoneInfo("America/Guayaquil")
ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "dashboard"
RAW = D / "raw" / "cenace_infoop"
URL_BNEE = "https://arconel.gob.ec/wp-content/uploads/downloads/2026/10/BNEE_julio_2026.xls"
URL_EST = "https://arconel.gob.ec/wp-content/uploads/downloads/2026/03/Estadistica2025.pdf"
URL_CELEC_RC = "https://www.celec.gob.ec/transelectric/wp-content/uploads/2026/05/RD2025-convertido.pdf"
URL_DESP = "https://arconel.gob.ec/wp-content/uploads/downloads/2025/01/ProcedimientosDespacho.pdf"
URL_RES004 = "https://arconel.gob.ec/wp-content/uploads/downloads/2025/05/Resolucion-nro.-ARCONEL-004-25.pdf"
URL_RDE = "https://arconel.gob.ec/wp-content/uploads/downloads/2024/08/Reg-ARCERNNR-001-24.pdf"
CELEC_PLANTAS = ["Coca Codo", "Paute", "Sopladora", "Mazar", "Minas San Francisco", "Agoyán", "San Francisco", "Delsitanisagua"]


def diario_de_html(p: Path):
    r = ci.parse(p.read_text(encoding="utf-8", errors="ignore"))
    d = r.get("diaria")
    if not d or not d.get("fecha"):
        return None
    pl = d.get("plantas", {})
    celec = sum(pl.get(k, 0) for k in CELEC_PLANTAS)
    term_mci_tv = pl.get("Térmica"); gas = pl.get("Gas Natural")
    return dict(fecha=d["fecha"].isoformat(), hidraulica_MWh=d["hidraulica"], termica_MWh=d["termica"],
                termica_combustibles_liquidos_MWh=term_mci_tv, termica_gas_natural_MWh=gas,
                renovable_no_convencional_MWh=d["renovable_no_conv"], importacion_MWh=d["importacion"], exportacion_MWh=d["exportacion"],
                produccion_total_MWh=d["produccion_total"], demanda_energia_MWh=d["produccion_total"] - d["exportacion"],
                demanda_max_MW=d.get("demanda_max_MW"), hora_demanda_max=d.get("hora_max"), demanda_min_MW=d.get("demanda_min_MW"),
                hidro_CELEC_identificada_MWh=celec, otras_hidro_MWh=pl.get("Otras Hidro"),
                consultado=datetime.strptime(p.stem, "%Y%m%d_%H%M").replace(tzinfo=TZ).isoformat(), fuente=ci.URL)


def _bnee_path() -> Path | None:
    raw = ROOT / "raw"
    cands = sorted(raw.glob("BNEE_*.xls")) + sorted(raw.glob("BNEE_*.xlsx"))
    return cands[-1] if cands else None


def bnee():
    path = _bnee_path()
    if path is None:
        prev = D / "estado_nacional.json"
        if prev.exists():
            old = json.loads(prev.read_text(encoding="utf-8"))
            cap = (old.get("capacidad_instalada_BNEE") or {}).get("por_tecnologia")
            if cap:
                print("AVISO: sin XLS de BNEE; se reutiliza la capacidad del JSON anterior")
                return cap
        raise FileNotFoundError("No hay raw/BNEE_*.xls ni capacidad previa en estado_nacional.json")
    df = pd.read_excel(path, header=None)
    out = {}
    for i in range(6, 20):
        name = df.iloc[i, 2] if isinstance(df.iloc[i, 2], str) else df.iloc[i, 1]
        if not isinstance(name, str): continue
        out[name.strip()] = dict(potencia_nominal_total_MW=round(float(df.iloc[i, 3]), 2), potencia_nominal_SNI_MW=round(float(df.iloc[i, 6]), 2),
                                 produccion_anio_movil_GWh=round(float(df.iloc[i, 9]), 1), produccion_anio_movil_SNI_GWh=round(float(df.iloc[i, 12]), 1))
    return out


def main():
    filas = [f for p in sorted(RAW.glob("*.html")) if (f := diario_de_html(p))]
    if not filas:
        sys.exit("Sin HTML de CENACE archivados")
    ser = pd.DataFrame(filas).drop_duplicates("fecha", keep="last")
    pth = D / "estado_nacional_diario.csv"
    if pth.exists():
        ser = pd.concat([pd.read_csv(pth), ser]).drop_duplicates("fecha", keep="last")
    ser = ser.sort_values("fecha"); ser.to_csv(pth, index=False)
    u = ser.iloc[-1].to_dict()
    prod = u["produccion_total_MWh"]
    pct = lambda v: round(100 * v / prod, 2) if prod else None

    # desglose RNC: último mes CENACE indicadores (no hay desglose diario público)
    m = pd.read_csv(D / "cenace_mensual_tecnologia.csv")
    ult_mes = m.mes.max(); mm = m[m.mes == ult_mes].set_index("tecnologia").GWh
    rnc_keys = [k for k in ("eolica", "fotovoltaica", "biomasa", "biogas") if k in mm.index]
    rnc_tot = float(sum(mm[k] for k in rnc_keys))
    rnc_mes = {k: dict(GWh=round(float(mm[k]), 2), pct_de_RNC=round(100 * float(mm[k]) / rnc_tot, 1) if rnc_tot else None) for k in rnc_keys}
    rnc_dia_est = {k: round(u["renovable_no_convencional_MWh"] * v["pct_de_RNC"] / 100) for k, v in rnc_mes.items()} if rnc_tot else {}

    cap = bnee()
    nom_sni = cap.get("Nacional (Renovable + No Renovable)", {}).get("potencia_nominal_SNI_MW")
    imp_cap = cap.get("Importación", {}).get("potencia_nominal_SNI_MW")
    pmax = u.get("demanda_max_MW")
    margen = round(100 * (nom_sni - pmax) / pmax, 1) if nom_sni and pmax else None
    margen_imp = round(100 * (nom_sni + imp_cap - pmax) / pmax, 1) if nom_sni and pmax and imp_cap else None

    est = dict(
        rotulo="Datos públicos; SCADA preliminar de CENACE (sujeto a revisión)",
        generado=datetime.now(TZ).isoformat(timespec="minutes"),
        fecha_dia_operativo=u["fecha"], fuente_diaria=ci.URL, consultado=u["consultado"],
        generacion_MWh=dict(
            hidraulica=dict(MWh=u["hidraulica_MWh"], pct=pct(u["hidraulica_MWh"])),
            termica=dict(MWh=u["termica_MWh"], pct=pct(u["termica_MWh"]),
                         detalle=dict(combustibles_liquidos_MCI_turbovapor=u["termica_combustibles_liquidos_MWh"], gas_natural=u["termica_gas_natural_MWh"])),
            renovable_no_convencional=dict(MWh=u["renovable_no_convencional_MWh"], pct=pct(u["renovable_no_convencional_MWh"]),
                                           nota="CENACE publica a diario solo el total RNC (eólica+solar+biomasa+biogás)."),
            desglose_RNC_estimado_dia_MWh=dict(valores=rnc_dia_est, metodo=f"Total RNC del día × participación de cada tecnología en {ult_mes} (CENACE indicadores). ESTIMADO, no dato diario.",
                                               mes_referencia=ult_mes, mes_GWh=rnc_mes),
            importacion=u["importacion_MWh"], exportacion=u["exportacion_MWh"], produccion_total_incl_importacion=prod),
        demanda=dict(energia_MWh=u["demanda_energia_MWh"], definicion="Producción total (incluye importación) − exportación",
                     max_MW=pmax, hora_max=u.get("hora_demanda_max"), min_MW=u.get("demanda_min_MW")),
        estatal_vs_privada=dict(
            diario=dict(hidro_CELEC_identificada_MWh=u["hidro_CELEC_identificada_MWh"], pct_produccion=pct(u["hidro_CELEC_identificada_MWh"]),
                        centrales=CELEC_PLANTAS,
                        nota="Piso, no total: suma de las centrales hidro de CELEC EP que CENACE nombra en su reporte diario. «Otras hidro», térmica y RNC mezclan CELEC y privadas; CENACE no publica la propiedad a diario."),
            anual_CELEC_EP_2025=dict(energia_neta_GWh=28040.0, aporte_demanda_nacional_pct=84.0, resto_pct=16.0,
                                     nota="El 16 % restante (complemento) incluye generadoras privadas y mixtas, autogeneradoras, distribuidoras e importaciones; no es solo «privadas».",
                                     fuente=URL_CELEC_RC, fecha="año 2025"),
            ARCONEL_por_tipo_de_empresa_2025=dict(
                nota="ARCONEL clasifica por TIPO de empresa (generadora/autogeneradora/distribuidora), no por propiedad pública/privada.",
                produccion_SNI_pct=dict(generadoras=89.97, autogeneradoras=7.76, distribuidoras=2.26),
                potencia_nominal_MW=dict(generadoras=7413.91, autogeneradoras=1826.72, distribuidoras=208.20, total=9448.83),
                potencia_efectiva_MW=dict(generadoras=7192.79, autogeneradoras=1490.67, distribuidoras=195.92, total=8879.39),
                fuente=URL_EST + " (tablas 21–23 y sección 2.5.1)", fecha="año 2025")),
        capacidad_instalada_BNEE=dict(fecha="julio 2026 (potencia nominal mensual; producción = año móvil ago-2025–jul-2026)", fuente=URL_BNEE, por_tecnologia=cap),
        RES=dict(
            respuesta_corta="En la normativa ecuatoriana no existe una sigla oficial «RES». Lo que CENACE y ARCONEL usan es «reserva» (margen de reserva, reserva rodante, reserva fría) y, para renovables, «renovable no convencional» (RNC/ERNC). Si «RES» se refiere a la reserva de generación, sí aplica a Ecuador.",
            reserva=dict(
                definiciones=[
                    dict(termino="Margen de reserva", texto="Mínimo = el mayor valor entre la unidad más grande del sistema y la importación comprometida, más la reserva fría establecida. CENACE programa mantenimientos para que la reserva supere este margen en las horas de demanda máxima.", fuente=URL_DESP + " (Regulación CONELEC 006/00, num. 4.3.3)"),
                    dict(termino="Reserva rodante", texto="Capacidad disponible de las unidades sincronizadas menos la demanda (incluidas pérdidas de transmisión).", fuente=URL_RDE),
                    dict(termino="Criterio de planificación", texto="CENACE pide mantener reservas del 10 % con 90 % de probabilidad de excedencia; para el estiaje sep-2025–mar-2026 estimó que faltaban 430 MW firmes para cumplirlo.", fuente=URL_RES004)],
                calculo_hoy=dict(
                    fecha=u["fecha"], demanda_max_MW=pmax, potencia_nominal_SNI_MW=nom_sni, importacion_nominal_MW=imp_cap,
                    margen_reserva_nominal_pct=margen, margen_reserva_nominal_con_importacion_pct=margen_imp,
                    formula="(potencia nominal SNI − demanda máxima del día) / demanda máxima del día",
                    advertencia="Es un TECHO teórico: CENACE no publica la potencia DISPONIBLE diaria. La disponible real es menor por mantenimientos, térmicas indisponibles y, sobre todo, por falta de agua en las hidroeléctricas. No equivale a la reserva operativa de CENACE.")),
            renovables=dict(texto="CENACE llama «R. no convencional» a eólica, solar, biomasa y biogás; la hidroeléctrica también es renovable pero se reporta aparte.",
                            hoy_MWh=u["renovable_no_convencional_MWh"], hoy_pct=pct(u["renovable_no_convencional_MWh"]),
                            renovable_total_incl_hidro_pct=pct(u["hidraulica_MWh"] + u["renovable_no_convencional_MWh"]), fuente=ci.URL)),
    )
    (D / "estado_nacional.json").write_text(json.dumps(est, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: est[k] for k in ("fecha_dia_operativo", "generacion_MWh", "demanda")}, ensure_ascii=False, indent=1, default=str))
    print("margen nominal", margen, margen_imp)


if __name__ == "__main__":
    main()
