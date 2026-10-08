#!/usr/bin/env python3
"""Arma site/index.html (una sola página, en español) con los datos embebidos.

La página en claro no se publica: el flujo de GitHub Actions la cifra antes
de subirla a Pages. Aquí no hay contraseña.
"""
from __future__ import annotations

import html
import json
import math
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DASH = ROOT / "dashboard"
SITE = ROOT / "site"
TZ = ZoneInfo("America/Guayaquil")
MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()
COLORES = {
    "actual": "#1a2332",
    "seco": "#d23b3b",
    "estiaje_2024": "#e07a3d",
    "normal": "#3d7ea6",
    "humedo": "#1e8f4e",
}
ORDEN = ["actual", "seco", "estiaje_2024", "normal", "humedo"]
PLANTAS = [
    ("MAZAR", "Mazar"),
    ("MOLINO", "Molino (Amaluza)"),
    ("SOPLADORA", "Sopladora"),
    ("MSF", "Minas San Francisco"),
]


def num(x, dec=0):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if math.isnan(v) or math.isinf(v):
        return "—"
    s = f"{v:,.{dec}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def pct(x, dec=1):
    return f"{num(x, dec)} %"


def fecha(iso):
    if iso is None or iso == "" or str(iso) in {"None", "null", "NaT"}:
        return None
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None
    return f"{d.day}-{MESES[d.month - 1]}-{d.year}"


def plazo(dias, iso, vacio="no llega en 365 días"):
    if dias is None or (isinstance(dias, float) and math.isnan(dias)):
        return vacio
    try:
        n = int(dias)
    except (TypeError, ValueError):
        return vacio
    f = fecha(iso)
    return f"{n} días · {f}" if f else f"{n} días"


def e(s):
    return html.escape("" if s is None else str(s), quote=True)


def sem_color(nombre):
    return {"verde": "#1e8f4e", "amarillo": "#d89b09", "rojo": "#d23b3b"}.get((nombre or "").lower(), "#888")


def sem_palabra(nombre):
    return {"verde": "Verde", "amarillo": "Amarillo", "rojo": "Rojo"}.get((nombre or "").lower(), "Sin dato")


def cargar_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def serie_maza(dias=90):
    h = pd.read_csv(DASH / "hidrologia_celec_sur.csv", parse_dates=["fecha"])
    piv = h.pivot_table(index="fecha", columns=["central", "metrica"], values="valor")
    g = pd.read_csv(DASH / "generacion_diaria_celec_sur.csv", parse_dates=["fecha"])
    gener = g.pivot_table(index="fecha", columns="planta", values="energia_MWh")
    idx = piv.index
    if len(idx) > dias:
        idx = idx[-dias:]
    filas = []
    for f in idx:
        def val(central, metrica):
            try:
                v = piv.loc[f, (central, metrica)]
            except KeyError:
                return None
            if isinstance(v, pd.Series):
                v = v.dropna()
                v = v.iloc[-1] if len(v) else None
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return None
            return float(v)

        z, q = val("MAZAR", "cota_msnm"), val("MAZAR", "caudal_m3s")
        za = val("MOLINO", "cota_msnm")
        try:
            energia = float(gener.loc[f, "MAZAR"]) if f in gener.index else None
        except (KeyError, TypeError, ValueError):
            energia = None
        qt = None
        if energia is not None and z is not None and za is not None and (z - za) >= 20:
            qt = energia / 24 * 1e6 / (1000 * 9.81 * (z - za) * 0.90)
        caudales = {c: val(c, "caudal_m3s") for c, _ in PLANTAS}
        filas.append({"fecha": f.date().isoformat(), "cota": z, "afluente": q, "turbinado": qt, "caudales": caudales})
    return filas


def svg_lineas(series, hlines=None, altura=188, dec=1):
    """series: [{nombre, color, puntos: [(fecha, valor)]}]"""
    puntos = [(d, y) for s in series for d, y in s["puntos"] if y is not None]
    if len(puntos) < 2:
        return "<p class='muted'>No hay suficientes días para el gráfico.</p>"
    ys = [y for _, y in puntos]
    if hlines:
        ys += [h["y"] for h in hlines]
    ymin, ymax = min(ys), max(ys)
    if ymin == ymax:
        ymin -= 1
        ymax += 1
    pad = (ymax - ymin) * 0.1
    ymin -= pad
    ymax += pad
    W, H, L, R, T, B = 640, altura, 52, 8, 14, 26
    fechas = []
    for s in series:
        for d, y in s["puntos"]:
            if y is not None and d not in fechas:
                fechas.append(d)
    fechas.sort()
    pos = {d: i for i, d in enumerate(fechas)}
    n = max(len(fechas) - 1, 1)

    def X(i):
        return L + i * (W - L - R) / n

    def Y(y):
        return T + (ymax - y) * (H - T - B) / (ymax - ymin)

    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img">']
    for tick in (ymin + pad, (ymin + ymax) / 2, ymax - pad):
        out.append(
            f'<line x1="{L}" x2="{W - R}" y1="{Y(tick):.1f}" y2="{Y(tick):.1f}" stroke="#e7e1d4"/>'
            f'<text x="{L - 6}" y="{Y(tick) + 3:.1f}" font-size="11" text-anchor="end" fill="#5e6a78">{e(num(tick, dec))}</text>'
        )
    for hln in hlines or []:
        out.append(
            f'<line x1="{L}" x2="{W - R}" y1="{Y(hln["y"]):.1f}" y2="{Y(hln["y"]):.1f}" stroke="{hln["color"]}" stroke-dasharray="4 3"/>'
            f'<text x="{W - R}" y="{Y(hln["y"]) - 3:.1f}" font-size="11" text-anchor="end" fill="{hln["color"]}">{e(hln["texto"])}</text>'
        )
    for s in series:
        pts = " ".join(f"{X(pos[d]):.1f},{Y(y):.1f}" for d, y in s["puntos"] if y is not None and d in pos)
        if pts:
            out.append(f'<polyline fill="none" stroke="{s["color"]}" stroke-width="2.4" stroke-linejoin="round" points="{pts}"/>')
    for i, frac in enumerate((0, 0.5, 1)):
        j = min(int(round(frac * (len(fechas) - 1))), len(fechas) - 1)
        ancla = "start" if i == 0 else ("end" if i == 2 else "middle")
        out.append(
            f'<text x="{X(j):.1f}" y="{H - 6}" font-size="11" text-anchor="{ancla}" fill="#5e6a78">{e(fecha(fechas[j]))}</text>'
        )
    out.append("</svg>")
    leyenda = " ".join(
        f'<span class="ley"><i style="background:{s["color"]}"></i>{e(s["nombre"])}</span>' for s in series
    )
    return "".join(out) + f'<div class="leyenda">{leyenda}</div>'


def lamparas(activo):
    partes = []
    for nombre in ("verde", "amarillo", "rojo"):
        encendida = " on" if nombre == (activo or "").lower() else ""
        partes.append(f'<span class="lampara {nombre}{encendida}" title="{sem_palabra(nombre)}"></span>')
    return f'<div class="semaforo" aria-label="Semáforo {sem_palabra(activo)}">{"".join(partes)}</div>'


def render(kpi, est, filas, prob, frescura):
    ahora = datetime.now(TZ)
    sello = f"{ahora.day} {MESES[ahora.month - 1]} {ahora.year} {ahora.hour:02d}:{ahora.minute:02d}"
    ea = kpi.get("estado_actual") or {}
    sem = (kpi.get("semaforo") or "").lower()
    sem_p = (kpi.get("semaforo_prudente") or "").lower()
    prob_b = kpi.get("probabilidad_apagones") or {}
    if isinstance(prob_b, dict) and "prob_hoy" not in prob_b:
        prob_b = {}
    dias = kpi.get("dias")
    g = (est.get("generacion_MWh") or {})
    hidro = (g.get("hidraulica") or {})
    term = (g.get("termica") or {})
    rnc = (g.get("renovable_no_convencional") or {})
    desg = ((g.get("desglose_RNC_estimado_dia_MWh") or {}).get("valores") or {})
    dem = est.get("demanda") or {}
    ev = est.get("estatal_vs_privada") or {}
    diario = ev.get("diario") or {}
    anual = ev.get("anual_CELEC_EP_2025") or {}
    reserva = (((est.get("RES") or {}).get("reserva") or {}).get("calculo_hoy") or {})
    escenarios = kpi.get("escenarios") or {}
    seco = escenarios.get("seco") or {}
    p50 = (prob_b.get("primer_dia_mayor_50") or {}).get("actual") if prob_b else None
    fecha_hidro = ea.get("fecha_hidro")
    fecha_cenace = est.get("fecha_dia_operativo")
    hoy = ahora.date()
    edad_h = (hoy - date.fromisoformat(fecha_hidro)).days if fecha_hidro else None

    avisos = []
    for nombre, info in (frescura.get("fuentes") or {}).items():
        if not info.get("ok"):
            avisos.append(info.get("detalle") or nombre)
    if edad_h is not None and edad_h > 2:
        avisos.append(f"La hidrología de Mazar es del {fecha(fecha_hidro)} ({edad_h} días).")
    banner = ""
    if avisos:
        # únicos, cortos
        vistos = []
        for a in avisos:
            if a and a not in vistos:
                vistos.append(a)
        items = "".join(f"<li>{e(a)}</li>" for a in vistos[:6])
        banner = (
            "<div class='aviso'><b>Hay fuentes que no respondieron en esta corrida.</b> "
            "Se muestra el último dato guardado, con su fecha."
            f"<ul>{items}</ul></div>"
        )

    def tarjeta_esc(clave):
        esc = escenarios.get(clave) or {}
        nombre = esc.get("nombre") or clave
        cls = "esc"
        if clave == "actual":
            cls += " actual"
        if clave == "seco":
            cls += " seco"
        d2115 = plazo(esc.get("dias_2115"), esc.get("fecha_2115"))
        d2098 = plazo(esc.get("dias_mazar_min"), esc.get("fecha_mazar_min"))
        ddef = plazo(esc.get("dias_deficit"), esc.get("fecha_deficit"), "sin déficit en 365 días")
        return (
            f"<article class='{cls}'><h3>{e(nombre)}</h3>"
            f"<p class='cuando'>Hasta 2.115 m: <b>{e(d2115)}</b></p>"
            f"<p>Hasta 2.098 m: {e(d2098)}</p>"
            f"<p>Oferta menor que la demanda: {e(ddef)}</p>"
            f"<p class='nota'>{e(esc.get('desc') or '')}</p></article>"
        )

    def barra(etiqueta, valor, ancho, clase, nota=""):
        w = 0 if ancho is None else max(0, min(100, float(ancho)))
        extra = f"<small>{e(nota)}</small>" if nota else ""
        return (
            f"<div class='fila'><div class='etiq'><span>{e(etiqueta)}</span><b>{e(valor)}</b></div>"
            f"{extra}<div class='pista'><div class='lleno {clase}' style='width:{w:.1f}%'></div></div></div>"
        )

    rnc_vals = desg or {}
    rnc_txt = (
        f"eólica {num(rnc_vals.get('eolica'), 0)} · solar {num(rnc_vals.get('fotovoltaica'), 0)} · "
        f"biomasa {num(rnc_vals.get('biomasa'), 0)} · biogás {num(rnc_vals.get('biogas'), 0)} MWh"
    )
    mes_ref = (g.get("desglose_RNC_estimado_dia_MWh") or {}).get("mes_referencia") or ""

    hist_cota = [{"nombre": "Cota", "color": "#0f6f6a", "puntos": [(r["fecha"], r["cota"]) for r in filas]}]
    hist_q = [{"nombre": "Afluente", "color": "#3d7ea6", "puntos": [(r["fecha"], r["afluente"]) for r in filas]}]
    hist_t = [{"nombre": "Turbinado estimado", "color": "#1a2332", "puntos": [(r["fecha"], r["turbinado"]) for r in filas]}]
    series_q = []
    paleta_p = ["#0f6f6a", "#3d7ea6", "#e07a3d", "#1a2332"]
    for (cod, nombre), color in zip(PLANTAS, paleta_p):
        series_q.append({"nombre": nombre, "color": color, "puntos": [(r["fecha"], (r["caudales"] or {}).get(cod)) for r in filas]})

    proy = []
    if not prob.empty and "escenario" in prob.columns:
        for clave in ("seco", "normal", "humedo", "actual"):
            q = prob[prob.escenario == clave]
            proy.append({
                "nombre": {"seco": "Seco", "normal": "Normal", "humedo": "Húmedo", "actual": "Actual"}.get(clave, clave),
                "color": COLORES.get(clave, "#333"),
                "puntos": [(f, float(p) * 100) for f, p in zip(q.fecha.astype(str), q.prob_apagon.astype(float))],
            })

    ultimo = filas[-1] if filas else {}
    caudales_html = []
    for cod, nombre in PLANTAS:
        v = (ultimo.get("caudales") or {}).get(cod)
        caudales_html.append(
            f"<div class='mini'><span>{e(nombre)}</span><b>{e(num(v, 1))} <small>m³/s</small></b>"
            f"<small>último día de la serie, {e(fecha(ultimo.get('fecha')))}</small></div>"
        )

    prob_hoy = pct_entero(prob_b.get("prob_hoy")) if prob_b else "—"
    primer = "no supera 50 % en 45 días"
    if isinstance(p50, dict) and p50.get("fecha"):
        primer = f"{int(p50['dias'])} días · {fecha(p50['fecha'])}"
    otros = []
    for clave, etiqueta in (("seco", "seco"), ("normal", "normal"), ("humedo", "húmedo"), ("actual", "caudal actual")):
        bloque = (prob_b.get("primer_dia_mayor_50") or {}).get(clave) if prob_b else None
        if bloque is None and clave == "humedo":
            otros.append(f"{etiqueta}: no supera 50 % en 45 días")
        elif isinstance(bloque, dict):
            otros.append(f"{etiqueta}: {int(bloque['dias'])} días · {fecha(bloque['fecha'])}")

    margen = reserva.get("margen_reserva_nominal_pct")
    margen_imp = reserva.get("margen_reserva_nominal_con_importacion_pct")
    pico = dem.get("max_MW")
    hora_pico = dem.get("hora_max") or ""

    datos = {
        "kpi": {k: kpi.get(k) for k in (
            "dias", "fecha", "semaforo", "semaforo_prudente", "escenarios", "estado_actual",
            "probabilidad_apagones", "dias_reserva", "rotulo", "generado", "regla_semaforo",
        )},
        "estado": {
            "fecha_dia_operativo": fecha_cenace,
            "generacion_MWh": g,
            "demanda": dem,
            "estatal_vs_privada": ev,
            "RES": est.get("RES"),
            "generado": est.get("generado"),
        },
        "serie_reciente": filas,
    }
    blob = json.dumps(datos, ensure_ascii=False, default=str).replace("<", "\\u003c")

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Electricidad en Ecuador</title>
<style>
:root {{
  --bg:#f6f3ec; --ink:#1a2332; --muted:#5e6a78; --card:#fff; --line:#e7e1d4;
  --verde:#1e8f4e; --ambar:#d89b09; --rojo:#d23b3b; --teal:#0f6f6a;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; line-height:1.45; }}
.wrap {{ max-width:42rem; margin:0 auto; padding:18px 14px 56px; }}
header h1 {{ font-size:1.45rem; line-height:1.2; margin:8px 0 4px; }}
.sello {{ color:var(--muted); font-size:.92rem; margin:0; }}
.rotulo {{ display:inline-block; background:#fff7e0; color:#7a5b00; border:1px solid #ead48a; border-radius:999px; padding:2px 10px; font-size:.78rem; font-weight:700; }}
.aviso {{ background:#fff4f2; border:1px solid #f0c2bc; border-radius:14px; padding:12px 14px; margin:14px 0; font-size:.92rem; }}
.aviso ul {{ margin:8px 0 0; padding-left:18px; }}
.card {{ background:var(--card); border-radius:18px; padding:16px; margin:12px 0; box-shadow:0 1px 2px #0000000d; }}
h2 {{ font-size:1.05rem; margin:0 0 8px; }}
h3 {{ font-size:.95rem; margin:14px 0 4px; }}
.muted, .nota, small {{ color:var(--muted); }}
.nota, small {{ font-size:.82rem; }}
.hero {{ display:flex; gap:14px; align-items:center; }}
.semaforo {{ display:flex; flex-direction:column; gap:6px; background:#1a2332; padding:8px; border-radius:16px; }}
.lampara {{ width:18px; height:18px; border-radius:50%; background:#3a4454; display:block; }}
.lampara.on.verde {{ background:var(--verde); box-shadow:0 0 0 4px #1e8f4e33; }}
.lampara.on.amarillo {{ background:var(--ambar); box-shadow:0 0 0 4px #d89b0933; }}
.lampara.on.rojo {{ background:var(--rojo); box-shadow:0 0 0 4px #d23b3b33; }}
.palabra {{ font-weight:800; letter-spacing:.04em; text-transform:uppercase; font-size:.95rem; }}
.grande {{ font-size:3.1rem; font-weight:800; letter-spacing:-.03em; line-height:.95; margin:6px 0; }}
.grande span {{ font-size:1.2rem; font-weight:650; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
.mini {{ background:#f7f5f0; border-radius:12px; padding:10px 12px; }}
.mini b {{ display:block; font-size:1.25rem; }}
.esc {{ border-left:4px solid var(--line); padding:8px 0 8px 10px; margin:8px 0; }}
.esc.actual {{ border-left-color:var(--ink); background:#f7f5f0; border-radius:0 12px 12px 0; padding:10px; }}
.esc.seco {{ border-left-color:var(--rojo); }}
.cuando {{ margin:2px 0; }}
.fila {{ margin:10px 0; }}
.etiq {{ display:flex; justify-content:space-between; gap:8px; font-size:.92rem; }}
.pista {{ height:8px; background:#efeae0; border-radius:99px; overflow:hidden; margin-top:4px; }}
.lleno {{ height:100%; border-radius:99px; }}
.lleno.hidro {{ background:#3d7ea6; }}
.lleno.termica {{ background:#e07a3d; }}
.lleno.rnc {{ background:#1e8f4e; }}
.lleno.estado {{ background:var(--teal); }}
.leyenda {{ display:flex; flex-wrap:wrap; gap:8px 12px; font-size:.78rem; color:var(--muted); margin-top:4px; }}
.ley i {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; }}
details {{ margin-top:8px; }}
summary {{ cursor:pointer; font-weight:650; }}
a {{ color:var(--teal); }}
@media (max-width:520px) {{
  .grid {{ grid-template-columns:1fr; }}
  .grande {{ font-size:2.7rem; }}
}}
</style>
</head>
<body>
<div class="wrap">
<header>
<span class="rotulo">Estimación propia, no oficial</span>
<h1>Electricidad en Ecuador</h1>
<p class="sello">Actualizado: {e(sello)} (Ecuador, UTC−5)</p>
<p class="sello">Hidrología al {e(fecha(fecha_hidro) or "—")} · día operativo de CENACE {e(fecha(fecha_cenace) or "—")}</p>
</header>
{banner}

<section class="card">
<div class="hero">
{lamparas(sem)}
<div>
<div class="palabra" style="color:{sem_color(sem)}">{e(sem_palabra(sem))}</div>
<p class="nota" style="margin:4px 0 0">El color mide los días hasta que Mazar baje a 2.115 m con el caudal de ahora. Verde: más de 60 días. Amarillo: 30 a 60. Rojo: menos de 30.</p>
</div>
</div>
</section>

<section class="card">
<h2>Días hasta la cota de los cortes</h2>
<div class="grande">{e(num(dias, 0))} <span>días</span></div>
<p>Con el caudal actual, Mazar llega a <b>2.115 m</b> el <b>{e(fecha(kpi.get("fecha")) or "—")}</b>.</p>
<p class="nota">2.115 m es el umbral principal: en 2023 y 2024, al cruzarlo, CELEC bajó el turbinado y vinieron los racionamientos. No es una cota oficial.</p>
<p>Referencia secundaria, mínima operativa <b>2.098 m</b>: {e(plazo(kpi.get("dias_mazar_min"), kpi.get("fecha_mazar_min")))}.</p>
<p class="nota">Si el tiempo fuera el del escenario seco, el semáforo pasaría a <b style="color:{sem_color(sem_p)}">{e(sem_palabra(sem_p))}</b> ({e(plazo(seco.get("dias_2115"), seco.get("fecha_2115")))}).</p>
</section>

<section class="card">
<h2>Días de reserva antes de cortes probables</h2>
<div class="grid">
<div class="mini"><span>Umbral físico, 2.115 m</span><b>{e(num(dias, 0))} días</b><small>cuándo el embalse llega a la cota en la que antes hubo cortes</small></div>
<div class="mini"><span>El modelo pasa de 50 %</span><b>{e(primer)}</b><small>compara la cota y los caudales de hoy con las semanas previas a apagones pasados</small></div>
</div>
<p class="nota">El modelo estadístico se adelanta al embalse: reacciona a caudales bajos y a la época seca antes de que el agua baje hasta 2.115 m. Son dos relojes distintos.</p>
</section>

<section class="card">
<h2>Probabilidad de apagones hoy</h2>
<div class="grande">{e(prob_hoy)}</div>
<p>Modelo logístico propio, con la cota y el caudal del {e(fecha(prob_b.get("fecha_dato")) or fecha(fecha_hidro) or "—")}.</p>
<p>Primer día por encima de 50 %, caudal actual: <b>{e(primer)}</b>.</p>
<p class="nota">{e(" · ".join(otros))}</p>
{svg_lineas(proy, [{"y": 50, "color": "#d23b3b", "texto": "50 %"}], dec=0) if proy else ""}
<p class="nota">El escenario de estiaje 2024 no tiene curva de probabilidad. El modelo se entrenó con solo tres crisis; es una orientación, no un pronóstico oficial.</p>
</section>

<section class="card">
<h2>Escenarios</h2>
<p class="nota">Qué pasa con Mazar si el caudal de las próximas semanas se parece al de ahora, a un año seco, al estiaje de 2024, a un año normal o a un año húmedo.</p>
{"".join(tarjeta_esc(k) for k in ORDEN)}
</section>

<section class="card">
<h2>Mazar, últimos {len(filas)} días</h2>
<div class="grid">
<div class="mini"><span>Cota</span><b>{e(num(ea.get("cota_mazar"), 2))} <small>m</small></b><small>rango de operación 2.098–2.153</small></div>
<div class="mini"><span>Entra</span><b>{e(num(ea.get("afluente_mazar_dia_m3s"), 1))} <small>m³/s</small></b><small>media 7 días {e(num(ea.get("afluente_mazar_7d_m3s"), 1))} · 14 días {e(num(ea.get("afluente_mazar_14d_m3s"), 1))}</small></div>
<div class="mini"><span>Turbinado</span><b>{e(num(ea.get("turbinado_mazar_14d_m3s"), 1))} <small>m³/s</small></b><small>media 14 días, estimada a partir de la energía</small></div>
<div class="mini"><span>Tendencia de la cota</span><b>{e(num(ea.get("tendencia_cota_m_dia_14d"), 2))} <small>m/día</small></b><small>últimos 14 días</small></div>
</div>
<h3>Cota</h3>
{svg_lineas(hist_cota, [
    {"y": 2115, "color": "#d23b3b", "texto": "2.115"},
    {"y": 2098, "color": "#7a1f1f", "texto": "2.098"},
], dec=0)}
<h3>Afluente</h3>
{svg_lineas(hist_q, dec=0)}
<h3>Turbinado estimado</h3>
{svg_lineas(hist_t, dec=0)}
<p class="nota">El turbinado del gráfico sale de la energía diaria y del salto entre Mazar y Amaluza (eficiencia supuesta 0,90). Bajo 2.115 m el modelo supone que el turbinado se limita a 35 m³/s.</p>
</section>

<section class="card">
<h2>Caudal por central de CELEC SUR</h2>
<p class="nota">Promedio diario publicado por CELEC SUR, en m³/s. Molino corresponde al embalse Amaluza.</p>
<div class="grid">{"".join(caudales_html)}</div>
{svg_lineas(series_q, dec=0)}
</section>

<section class="card">
<h2>Generación del último día completo</h2>
<p class="nota">CENACE, día operativo {e(fecha(fecha_cenace) or "—")}. Cifras preliminares de SCADA.</p>
{barra("Hidráulica", f"{num(hidro.get('MWh'), 0)} MWh · {pct(hidro.get('pct'))}", hidro.get("pct"), "hidro")}
{barra("Térmica", f"{num(term.get('MWh'), 0)} MWh · {pct(term.get('pct'))}", term.get("pct"), "termica",
       f"líquidos {num((term.get('detalle') or {}).get('combustibles_liquidos_MCI_turbovapor'), 0)} · gas natural {num((term.get('detalle') or {}).get('gas_natural'), 0)} MWh")}
{barra("Renovable no convencional", f"{num(rnc.get('MWh'), 0)} MWh · {pct(rnc.get('pct'), 2)}", rnc.get("pct"), "rnc",
       "eólica y solar son estimadas")}
<p class="nota">Reparto del día, estimado con la participación de {e(mes_ref)} porque CENACE solo publica el total diario: {e(rnc_txt)}. Eólica y solar van marcadas como estimación, igual que biomasa y biogás.</p>
<div class="grid">
<div class="mini"><span>Importación</span><b>{e(num(g.get("importacion"), 0))} <small>MWh</small></b></div>
<div class="mini"><span>Exportación</span><b>{e(num(g.get("exportacion"), 0))} <small>MWh</small></b></div>
<div class="mini"><span>Demanda de energía</span><b>{e(num(dem.get("energia_MWh"), 0))} <small>MWh</small></b><small>producción, incluida la importación, menos la exportación</small></div>
<div class="mini"><span>Punta del día</span><b>{e(num(pico, 0))} <small>MW</small></b><small>{e(hora_pico)} · mínima {e(num(dem.get("min_MW"), 0))} MW</small></div>
</div>
</section>

<section class="card">
<h2>Parte estatal y parte privada</h2>
<div class="grid">
<div class="mini"><span>Piso de CELEC, ese día</span><b>{e(pct(diario.get("pct_produccion"), 0))}</b><small>{e(num(diario.get("hidro_CELEC_identificada_MWh"), 0))} MWh de las hidroeléctricas que CENACE nombra como CELEC</small></div>
<div class="mini"><span>CELEC EP en 2025</span><b>{e(pct(anual.get("aporte_demanda_nacional_pct"), 0))}</b><small>{e(num(anual.get("energia_neta_GWh"), 0))} GWh netos, el {e(pct(anual.get("resto_pct"), 0))} restante no es solo privado</small></div>
</div>
{barra("Piso estatal del día", pct(diario.get("pct_produccion"), 0), diario.get("pct_produccion"), "estado")}
<p class="nota">{e(diario.get("nota") or "")} {e(anual.get("nota") or "")}</p>
</section>

<section class="card">
<h2>Margen de reserva</h2>
<div class="grande">{e(pct(margen))}</div>
<p>Ecuador no usa la sigla «RES». Lo equivalente es el <b>margen de reserva</b>: cuánta potencia nominal sobra por encima de la demanda máxima. CENACE planifica con reservas del 10 % (90 % de probabilidad).</p>
<p class="nota">Fórmula del {e(fecha(reserva.get("fecha")) or fecha(fecha_cenace) or "—")}: (potencia nominal del sistema, {e(num(reserva.get("potencia_nominal_SNI_MW"), 1))} MW − punta {e(num(pico, 0))} MW) / punta. Con las interconexiones ({e(num(reserva.get("importacion_nominal_MW"), 0))} MW) el margen sube a {e(pct(margen_imp))}.</p>
<p class="nota">{e(reserva.get("advertencia") or "Es un techo teórico: usa la potencia instalada, no la que de verdad está disponible.")}</p>
</section>

<section class="card">
<h2>Cómo leer esta página</h2>
<p>Mire primero el semáforo y los días hasta 2.115 m. Después, la probabilidad de hoy. La lista de escenarios dice qué cambiaría si llueve más o menos. Los gráficos de Mazar muestran si el embalse ya viene bajando.</p>
<details>
<summary>Supuestos y límites</summary>
<ul>
<li>Estimación propia, no oficial. No es un parte de CENACE ni del Ministerio.</li>
<li>2.115 m es una referencia histórica. 2.098 m es la mínima operativa de la ficha de CELEC.</li>
<li>Bajo 2.115 m el modelo supone 35 m³/s de turbinado. El operador puede decidir otra cosa.</li>
<li>La probabilidad se aprendió con tres crisis (oct–dic 2023, abril 2024 y sep–dic 2024).</li>
<li>El balance es de energía diaria: no incluye la hora pico, la transmisión ni los mantenimientos.</li>
<li>La térmica disponible de verdad no se publica cada día. El margen de reserva es un techo.</li>
</ul>
<p class="nota">Fuentes públicas: CELEC SUR (generacioncsr.celec.gob.ec), CENACE Información Operativa e indicadores, ARCONEL BNEE.</p>
</details>
</section>
</div>
<script type="application/json" id="datos-tablero">{blob}</script>
</body>
</html>
"""


def pct_entero(p):
    if p is None:
        return "—"
    return f"{int(round(float(p) * 100))} %"


def assert_coherente(pagina, kpi, est):
    if "Estimación propia, no oficial" not in pagina:
        raise SystemExit("falta el rótulo")
    if "Actualizado:" not in pagina or "UTC−5" not in pagina:
        raise SystemExit("falta la fecha de actualización")
    dias = kpi.get("dias")
    if dias is not None and f"{int(dias)}" not in pagina:
        raise SystemExit("la página no muestra los días hasta 2.115 m")
    sem = (kpi.get("semaforo") or "").lower()
    if sem and sem_palabra(sem) not in pagina:
        raise SystemExit("falta el semáforo")
    margen = (((est.get("RES") or {}).get("reserva") or {}).get("calculo_hoy") or {}).get("margen_reserva_nominal_pct")
    if margen is not None and pct(margen) not in pagina:
        raise SystemExit("falta el margen de reserva")
    prob = (kpi.get("probabilidad_apagones") or {}).get("prob_hoy")
    if isinstance(prob, float) and pct_entero(prob) not in pagina:
        raise SystemExit("falta la probabilidad de hoy")
    for clave in ORDEN:
        nombre = ((kpi.get("escenarios") or {}).get(clave) or {}).get("nombre")
        if nombre and nombre not in pagina:
            raise SystemExit(f"falta el escenario {nombre}")


def main() -> int:
    kpi = cargar_json(DASH / "kpi_deficit.json", {})
    est = cargar_json(DASH / "estado_nacional.json", {})
    if not kpi or not est:
        raise SystemExit("Faltan kpi_deficit.json o estado_nacional.json; no se arma una página vacía.")
    filas = serie_maza(90)
    prob_path = DASH / "modelo" / "probabilidad_apagones.csv"
    prob = pd.read_csv(prob_path) if prob_path.exists() else pd.DataFrame()
    frescura = cargar_json(DASH / "frescura.json", {})
    pagina = render(kpi, est, filas, prob, frescura)
    assert_coherente(pagina, kpi, est)
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(pagina, encoding="utf-8")
    print(f"site/index.html ({len(pagina)} caracteres)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
