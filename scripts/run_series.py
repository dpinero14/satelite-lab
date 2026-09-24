"""Corre el detector sobre una ruta en todas las pasadas de un rango de fechas y guarda una fila por pasada.

    python scripts/run_series.py 152 2017-01-01 2026-09-23 --por-mes 3

Toma las escenas de días hábiles con menos de 5 % de nubes, como mucho `--por-mes` por mes
(las de menos nubes), recorre el tramo de la ruta definido en `slab.RUTAS`, y agrega a
`data/processed/serie_<ruta>.csv` lo que cuenta en cada pasada. Es reanudable: las escenas
ya procesadas se saltean. Las detecciones de cada pasada van a `data/processed/detecciones_<ruta>.csv`.
"""

import argparse
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from slab import DATA_PROC, RUTAS  # noqa: E402
from slab.counts import density  # noqa: E402
from slab.detect import detect  # noqa: E402
from slab.roads import along, fetch_routes, route_line  # noqa: E402
from slab.scenes import scene_crs_bounds, search, strip, valid_km, weekdays  # noqa: E402

warnings.filterwarnings("ignore")


def run_scene(item, routes, rtn: str, lon: float, lat: float, km_from: float, km_to: float, paso_km: float = 10.0, half: int = 4):
    """Recorre el tramo de la ruta en una escena; devuelve (detecciones, km válidos)."""
    crs, bounds = scene_crs_bounds(item)
    line = route_line(routes, rtn, crs, bounds)
    d0 = along(line, lon, lat, crs)
    dets, km = [], 0.0
    for start in np.arange(km_from * 1000, km_to * 1000, paso_km * 1000):
        a, b = d0 + start, d0 + start + paso_km * 1000
        if a < 0 or a >= line.length:
            continue
        s = None
        for intento in range(3):          # la lectura remota falla a veces (DNS, corte): se reintenta con espera
            try:
                s = strip(item, line, a, b, half=half)
                break
            except ValueError:
                break
            except Exception:
                time.sleep(5 * (intento + 1))
        if s is None:
            continue
        kv = valid_km(s)
        if kv < 1.0:
            continue
        km += kv
        d = detect(s)
        d["km_tramo"] = start / 1000 + d["along_m"] / 1000
        dets.append(d)
    det = pd.concat(dets, ignore_index=True) if dets else pd.DataFrame()
    return det, km


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("ruta")
    p.add_argument("desde")
    p.add_argument("hasta")
    p.add_argument("--por-mes", type=int, default=3)
    p.add_argument("--nubes", type=float, default=5.0)
    p.add_argument("--fin-de-semana", action="store_true", help="incluir sábados y domingos")
    args = p.parse_args()
    cfg = RUTAS[args.ruta]
    routes = fetch_routes(tuple(RUTAS))
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    out = DATA_PROC / f"serie_{args.ruta}.csv"
    out_det = DATA_PROC / f"detecciones_{args.ruta}.csv"
    hechas = set(pd.read_csv(out)["escena"]) if out.exists() else set()
    esc = search(cfg["lon"], cfg["lat"], args.desde, args.hasta, max_cloud=args.nubes)
    if not args.fin_de_semana:
        esc = weekdays(esc)
    esc["mes"] = pd.to_datetime(esc["fecha"]).dt.to_period("M")
    esc = esc.sort_values(["mes", "nubes"]).groupby("mes").head(args.por_mes).sort_values("fecha")
    print(f"{cfg['nombre']}: {len(esc)} pasadas entre {args.desde} y {args.hasta}, {len(hechas)} ya hechas", flush=True)
    for _, e in esc.iterrows():
        if e["id"] in hechas:
            continue
        t0 = time.time()
        try:
            det, km = run_scene(e["item"], routes, args.ruta, cfg["lon"], cfg["lat"], *cfg["km"], half=cfg.get("half", 4))
        except Exception as ex:      # una escena rota no frena la serie
            print(f"  {e['fecha']} {e['id']}: error {type(ex).__name__}: {str(ex)[:80]}", flush=True)
            continue
        fila = {"escena": e["id"], "fecha": str(e["fecha"]), "dia": e["nombre_dia"], "hora_utc": e["hora_utc"], "nubes": e["nubes"], **density(det, km)}
        pd.DataFrame([fila]).to_csv(out, mode="a", header=not out.exists(), index=False)
        if len(det):
            det.assign(escena=e["id"], fecha=str(e["fecha"])).to_csv(out_det, mode="a", header=not out_det.exists(), index=False)
        print(f"  {e['fecha']} {e['nombre_dia']} nubes {e['nubes']:.1f}: {fila['n']} en {km:.0f} km ({fila['por_100km']:.1f}/100 km; +{fila['n_pos']} -{fila['n_neg']}) [{time.time() - t0:.0f} s]", flush=True)


if __name__ == "__main__":
    main()
