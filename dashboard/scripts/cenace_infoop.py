"""Parser de CENACE 'Información Operativa' (HTML con gráficos Plotly en base64).

Fuente: https://www.cenace.gob.ec/info-operativa/InformacionOperativa.htm
(datos preliminares SCADA, sujetos a revisión, según la propia página).
La página solo muestra: tiempo real (día en curso, parcial), el día operativo
más reciente validado (normalmente D-2), acumulado mensual y anual, y las curvas
de los días de demanda máxima mensual e histórica. NO publica histórico diario,
por eso el script archiva cada HTML y acumula la serie día a día.
"""
from __future__ import annotations
import base64, json, re, unicodedata
from datetime import date
import numpy as np

URL = "https://www.cenace.gob.ec/info-operativa/InformacionOperativa.htm"
MESES = {m: i + 1 for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}


def _strip(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def _num(s):
    return float(s.replace("\u00a0", "").replace(" ", "").replace(",", "."))


def _fecha(txt):
    m = re.search(r"(\d{1,2}) de ([a-zA-Záéíóú]+) de (\d{4})", txt)
    return date(int(m.group(3)), MESES[_strip(m.group(2))], int(m.group(1))) if m else None


def _figs(h):
    D = json.JSONDecoder()
    out = []
    def dec(v):
        if isinstance(v, dict) and "bdata" in v:
            return np.frombuffer(base64.b64decode(v["bdata"]), dtype=v["dtype"]).tolist()
        return v
    for m in re.finditer(r'Plotly\.newPlot\(\s*"([^"]+)",\s*', h):
        tr, _ = D.raw_decode(h, m.end())
        out.append([{"name": (t.get("name") or "").strip(), "type": t.get("type"),
                     "x": dec(t.get("x")), "y": dec(t.get("y")),
                     "labels": t.get("labels"), "values": dec(t.get("values"))} for t in tr])
    return out


def _text_lines(h):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = t.replace("&#10;", " ")
    return [l.strip() for l in t.split("\n") if l.strip()]


def parse(h: str) -> dict:
    lines = _text_lines(h)
    figs = _figs(h)
    # grupos: cada sección empieza con un pie 'Composición Energética'
    groups, cur = [], None
    for f in figs:
        if f and f[0]["type"] == "pie" and f[0]["name"] == "Composición Energética":
            cur = [f]; groups.append(cur)
        elif cur is not None:
            cur.append(f)
    heads = [("tiempo_real", "PRODUCCIÓN EN TIEMPO REAL"), ("diaria", "INFORMACIÓN OPERATIVA DIARIA"),
             ("mensual", "INFORMACIÓN OPERATIVA MENSUAL"), ("anual", "INFORMACIÓN OPERATIVA ANUAL")]
    res = {}
    for k, (key, head) in enumerate(heads):
        idx = [i for i, l in enumerate(lines) if l == head]
        if not idx:
            continue
        i = idx[-1]
        sec = {"fecha_texto": lines[i + 1], "fecha": _fecha(lines[i + 1])}
        unidad = "GWh" if "(GWh)" in " ".join(lines[i:i + 5]) else "MWh"
        sec["unidad"] = unidad
        for lab, nk in [("PRODUCCIÓN TOTAL", "produccion_total"), ("EXPORTACIÓN", "exportacion"),
                        ("IMPORTACIÓN", "importacion"), ("HIDRÁULICA", "hidraulica"),
                        ("TÉRMICA", "termica"), ("R. NO CONVENCIONAL", "renovable_no_conv")]:
            for j in range(i, min(i + 30, len(lines) - 1)):
                if lines[j] == lab:
                    sec[nk] = _num(lines[j + 1]); break
        g = groups[k] if k < len(groups) else []
        plantas = {}
        curva = {}
        for f in g[1:]:
            for t in f:
                if t["type"] == "bar" and t["y"] and len(t["y"]) == 1:
                    plantas[t["name"]] = float(t["y"][0])
                if t["type"] == "scatter" and t["x"] and len(t["x"]) == 48:
                    curva[t["name"]] = t["y"]; xs = t["x"]
        sec["plantas"] = plantas
        if "DEMANDA NACIONAL" in curva:
            y = np.array(curva["DEMANDA NACIONAL"], dtype=float)
            ok = ~np.isnan(y)
            sec["curva_n_puntos"] = int(ok.sum())
            if ok.sum():
                sec["demanda_max_MW"] = float(np.nanmax(y))
                sec["demanda_min_MW"] = float(np.nanmin(y))
                sec["demanda_media_MW"] = float(np.nanmean(y))
                sec["hora_max"] = xs[int(np.nanargmax(y))]
            if "Térmica" in curva:
                sec["termica_max_MW"] = float(np.nanmax(np.array(curva["Térmica"], dtype=float)))
        res[key] = sec
    for l in lines:
        if l.startswith("Demanda máxima mensual:"):
            res["dia_dem_max_mensual"] = _fecha(l)
        if l.startswith("Demanda máxima histórica:"):
            res["dia_dem_max_historica"] = _fecha(l)
    # días en el acumulado mensual: "(hasta el día 05)"
    if "mensual" in res:
        m = re.search(r"hasta el d[ií]a (\d+)", res["mensual"]["fecha_texto"])
        res["mensual"]["dias"] = int(m.group(1)) if m else None
    return res
