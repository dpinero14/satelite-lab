"""Arma docs/index.html con las figuras del notebook y los números de las series, para GitHub Pages.

Lee data/processed/serie_<ruta>.csv, calcula el índice anual de la RN 152 y el de las cuatro
rutas en el último año, y escribe una página estática. Corre después del notebook.
"""

import html
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from slab import DATA_PROC, DOCS, RUTAS  # noqa: E402
from slab.counts import by_period, series  # noqa: E402
from slab.roads import tmda_2016_near  # noqa: E402

BG, INK, MUTED, RULE, ACENTO, AZUL = "#0e1b25", "#f2f2f2", "#8fa3b0", "#22333f", "#f2b134", "#26c6da"


def n(v, d=1):
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tabla(df: pd.DataFrame, cols: list[tuple[str, str, str]]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for _, h, _ in cols)
    filas = []
    for _, r in df.iterrows():
        celdas = []
        for c, _, f in cols:
            v = r[c]
            s = "–" if pd.isna(v) else (f"{int(v)}" if f == "int" else (n(float(v), int(f[1])) if f.startswith("f") else html.escape(str(v))))
            celdas.append(f"<td>{s}</td>")
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(filas)}</tbody></table>"


def main() -> None:
    s152 = series(pd.read_csv(DATA_PROC / "serie_152.csv").to_dict("records"))
    anual = by_period(s152, "YS", min_km=20)
    anual.index = anual.index.year
    filas = []
    for r, c in RUTAS.items():
        p = DATA_PROC / f"serie_{r}.csv"
        if not p.exists():
            continue
        sr = series(pd.read_csv(p).to_dict("records"))
        sr = sr[(sr["fecha"] >= "2025-09-01") & (sr["km"] >= 20)]
        if len(sr) == 0:
            continue
        t = tmda_2016_near(r, c["lon"], c["lat"])
        nn, km = sr["n"].sum(), sr["km"].sum()
        filas.append({"nombre": c["nombre"], "pasadas": len(sr), "km": km, "n": nn, "por_100km": 100 * nn / km, "error_100km": 100 * np.sqrt(max(nn, 1)) / km,
                      "pct_pos": 100 * sr["n_pos"].sum() / max(nn, 1), "tmda": t["tmda_2016"]})
    comp = pd.DataFrame(filas).sort_values("tmda", ascending=False)
    a0 = anual.loc[anual.index <= 2018]; a1 = anual.loc[anual.index >= 2024]
    r0 = 100 * a0["n"].sum() / a0["km"].sum(); r1 = 100 * a1["n"].sum() / a1["km"].sum()
    anual_html = tabla(anual.reset_index().rename(columns={"fecha": "anio"}), [("anio", "año", "s"), ("pasadas", "pasadas", "int"), ("km", "km recorridos", "f0"), ("n", "vehículos", "int"),
                                                                              ("por_100km", "por 100 km", "f1"), ("error_100km", "± error", "f1"), ("pct_pos", "% hacia Neuquén", "f0")])
    comp_html = tabla(comp, [("nombre", "ruta", "s"), ("pasadas", "pasadas", "int"), ("km", "km", "f0"), ("n", "vehículos", "int"), ("por_100km", "por 100 km", "f1"),
                             ("error_100km", "± error", "f1"), ("tmda", "TMDA 2016", "f0")])
    page = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>El satélite cuenta camiones</title>
<meta name="description" content="Vehículos en movimiento sobre rutas argentinas contados con Sentinel-2 y el desfase entre bandas, 2017 a 2026.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono&display=swap">
<style>
:root{{--bg:{BG};--ink:{INK};--muted:{MUTED};--rule:{RULE};--acento:{ACENTO};--azul:{AZUL};--panel:#15242f}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"IBM Plex Sans",system-ui,sans-serif;line-height:1.5}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}
h1{{font-size:2rem;margin:0 0 4px;letter-spacing:-.01em}}
h2{{font-size:1.25rem;margin:40px 0 8px;color:var(--acento)}}
p,li{{max-width:68ch}}
.sub{{color:var(--muted);margin:0 0 24px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:20px 0}}
.kpi{{background:var(--panel);border-radius:8px;padding:14px 16px}}
.kpi b{{display:block;font-size:1.7rem;font-variant-numeric:tabular-nums;color:var(--acento)}}
.kpi span{{color:var(--muted);font-size:.9rem}}
figure{{margin:16px 0}} figure img{{width:100%;height:auto;border-radius:6px}} figcaption{{color:var(--muted);font-size:.85rem}}
.tabla{{overflow-x:auto;margin:12px 0}} table{{border-collapse:collapse;width:100%;font-size:.88rem;font-variant-numeric:tabular-nums}}
th,td{{padding:6px 10px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}} th:first-child,td:first-child{{text-align:left}}
th{{color:var(--muted);font-weight:600}}
a{{color:var(--azul)}}
.nota{{color:var(--muted);font-size:.9rem}}
footer{{margin-top:48px;color:var(--muted);font-size:.85rem;border-top:1px solid var(--rule);padding-top:16px}}
</style>
</head>
<body>
<main>
<h1>El satélite cuenta camiones</h1>
<p class="sub">Sentinel-2 toma el azul, el verde y el rojo con un segundo de diferencia. Un vehículo en movimiento queda como un arcoíris de tres píxeles sobre la ruta; este laboratorio los cuenta. Actualizado el {date.today():%d/%m/%Y}.</p>

<div class="kpis">
  <div class="kpi"><b>1,005 s</b><span>entre la toma del azul y la del rojo: 22 m a 80 km/h, dos píxeles</span></div>
  <div class="kpi"><b>{n(r1)}</b><span>vehículos en movimiento por 100 km en la RN 152 en 2024-2026, contra {n(r0)} en 2017-2018</span></div>
  <div class="kpi"><b>{int(s152['n'].sum())}</b><span>vehículos contados en {int(s152['km'].sum()):,} km de pasadas sobre la ruta de la arena</span></div>
  <div class="kpi"><b>{len(comp)}</b><span>rutas comparadas con el conteo de Vialidad en el último año</span></div>
</div>

<h2>Un vehículo, tres bandas</h2>
<figure><img src="figures/arcoiris.png" alt="Un vehículo visto por las tres bandas con un segundo de diferencia"><figcaption>El azul se toma primero; el verde y el rojo, después. El corrimiento da la velocidad y el signo, el sentido.</figcaption></figure>
<figure><img src="figures/ruta_enderezada.png" alt="La RN 152 enderezada con sus detecciones"><figcaption>La ruta enderezada: arriba en color real, abajo la anomalía de cada banda respecto del fondo de la propia ruta.</figcaption></figure>

<h2>La ruta de la arena, 2017 a 2026</h2>
<figure><img src="figures/serie_rn152.png" alt="Serie anual del índice en la RN 152"></figure>
<div class="tabla">{anual_html}</div>
<figure><img src="figures/arena_vs_satelite.png" alt="El índice del satélite contra la arena bombeada"><figcaption>La arena bombeada en Vaca Muerta según el registro de fractura, contra lo que ve el satélite en la RN 152.</figcaption></figure>

<h2>Cuatro rutas contra Vialidad</h2>
<figure><img src="figures/rutas_vs_vialidad.png" alt="Cuatro rutas: satélite y TMDA"></figure>
<div class="tabla">{comp_html}</div>
<p class="nota">El satélite ve una muestra de los vehículos (los que contrastan con la ruta y van a más de 54 km/h), no el total, y esa muestra no es proporcional al tránsito: el índice sirve para comparar rutas y años con el mismo método, no para contar camiones por día.</p>

<h2>Cómo</h2>
<ul>
  <li>Eje de la ruta: red vial nacional del IGN. Imágenes: Sentinel-2 L2A (Copernicus) leídas por ventana desde el catálogo abierto de AWS, sin cuenta.</li>
  <li>Detector propio: ruta enderezada, fondo por mediana móvil, corrimiento azul→rojo por correlación cruzada, verde en el medio, dos o tres píxeles.</li>
  <li>Pasadas de días hábiles con menos de 5 % de nubes, dos por mes; máscara de nubes por píxel.</li>
  <li>Código, tests y notebook: <a href="https://github.com/dpinero14/satelite-lab">github.com/dpinero14/satelite-lab</a>.</li>
</ul>

<footer>satelite-lab · Sur Analytics · Sentinel-2 (Copernicus, vía Element 84 / AWS Open Data) · IGN · Vialidad Nacional · método de referencia: Fisser et al. 2022.</footer>
</main>
</body>
</html>
"""
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    print(f"página: {DOCS / 'index.html'}; RN 152 2017-2018 {r0:.1f} vs 2024-2026 {r1:.1f} por 100 km; rutas comparadas {len(comp)}")


if __name__ == "__main__":
    main()
