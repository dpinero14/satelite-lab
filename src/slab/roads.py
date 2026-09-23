"""La geometría de la ruta: la red vial nacional del IGN, una línea por ruta, y la posición a lo largo.

El detector trabaja sobre una franja angosta alrededor de la ruta, así que necesita el eje
con precisión de un píxel (10 m). La capa `ign:vial_nacional` del Instituto Geográfico Nacional
(WFS abierto) trae la red completa con el número de ruta en `rtn`; sobre la RN 152 quedó a
menos de un píxel del asfalto en las escenas probadas. Se baja una vez y se cachea.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import requests
from pyproj import Transformer
from shapely.geometry import LineString, Point, box
from shapely.ops import linemerge, unary_union

from . import CRS_GEO, DATA_RAW

IGN_WFS = "https://wms.ign.gob.ar/geoserver/ows"
LAYER = "ign:vial_nacional"


def fetch_routes(rtns: tuple[str, ...], path: Path = DATA_RAW / "ign_rutas.geojson", timeout: int = 300) -> gpd.GeoDataFrame:
    """Los tramos del IGN de las rutas pedidas (números como '152'), cacheados en `path`."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        cql = "rtn IN (" + ",".join(f"'{r}'" for r in rtns) + ")"
        r = requests.get(IGN_WFS, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": LAYER,
                                           "outputFormat": "application/json", "CQL_FILTER": cql},
                         timeout=timeout, headers={"User-Agent": "satelite-lab/0.1 (+https://github.com/dpinero14)"})
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    g = gpd.read_file(path)
    return g[g["rtn"].astype(str).isin([str(x) for x in rtns])].reset_index(drop=True)


def route_line(routes: gpd.GeoDataFrame, rtn: str, crs, bounds: tuple[float, float, float, float] | None = None) -> LineString:
    """Una sola línea de la ruta en el sistema `crs` (el de la escena), recortada al rectángulo `bounds` si se da.

    Los tramos del IGN se unen; si quedan varios pedazos (cortes, desvíos), se usa el más largo.
    """
    g = routes[routes["rtn"].astype(str) == str(rtn)].to_crs(crs)
    if bounds is not None:
        g = g[g.intersects(box(*bounds))]
    if len(g) == 0:
        raise ValueError(f"la RN {rtn} no cruza la escena")
    u = unary_union(g.geometry)
    line = u if u.geom_type == "LineString" else linemerge(u)
    if line.geom_type != "LineString":
        line = max(line.geoms, key=lambda p: p.length)
    return line


def along(line: LineString, lon: float, lat: float, crs) -> float:
    """Distancia a lo largo de la línea (m) del punto de la ruta más cercano a (lon, lat)."""
    tr = Transformer.from_crs(CRS_GEO, crs, always_xy=True)
    x, y = tr.transform(lon, lat)
    return float(line.project(Point(x, y)))


__all__ = ["IGN_WFS", "LAYER", "fetch_routes", "route_line", "along"]


def tmda_2016_near(rtn: str, lon: float, lat: float, path: Path = DATA_RAW / "tmda_2016.geojson") -> dict:
    """El tramo del TMDA 2016 de Vialidad de la ruta `rtn` más cercano al punto: descripción, km inicio y fin, vehículos por día."""
    import pandas as pd

    g = gpd.read_file(path)
    g = g[g["ruta"].astype(str).str.lstrip("0") == str(rtn).lstrip("0")].copy()
    g["t"] = pd.to_numeric(g["tmda2016"], errors="coerce")
    g = g[g["t"] > 1].to_crs("EPSG:5346")
    p = gpd.GeoSeries([Point(lon, lat)], crs=CRS_GEO).to_crs("EPSG:5346").iloc[0]
    g["dist_km"] = g.geometry.distance(p) / 1000
    r = g.sort_values("dist_km").iloc[0]
    return {"ruta": r["nom_mapa"], "tramo": r["descripcio"], "km_inicio": float(r["inicio"]), "km_fin": float(r["fin"]), "tmda_2016": float(r["t"]), "dist_km": float(r["dist_km"])}


__all__ += ["tmda_2016_near"]
