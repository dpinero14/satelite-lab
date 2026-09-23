"""Buscar escenas Sentinel-2 y leer la ruta enderezada.

Las escenas se buscan en el catálogo STAC abierto de AWS por punto, fechas y nubosidad; cada
banda es un GeoTIFF en la nube que se lee por ventana, sin bajar la escena entera. La ruta se
"endereza": se muestrea cada 10 m a lo largo de la línea del IGN y ±half píxeles a lo ancho,
y queda una franja (a lo largo x a lo ancho) por banda. En esa franja un vehículo que se
mueve por la ruta se corre a lo largo, que es la única dirección que importa.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pystac_client
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import LineString

from . import COLLECTION, PIXEL_M, STAC

DIAS = ("lun", "mar", "mie", "jue", "vie", "sab", "dom")
BANDAS = ("blue", "green", "red")
# clases de la máscara SCL de Sentinel-2 que invalidan el píxel: sombra de nube, nubes y nieve
SCL_INVALIDAS = (3, 8, 9, 10, 11)


def catalog():
    return pystac_client.Client.open(STAC)


def search(lon: float, lat: float, start: str, end: str, max_cloud: float = 5.0, collection: str = COLLECTION, max_items: int = 1000) -> pd.DataFrame:
    """Escenas sobre el punto entre `start` y `end` (ISO) con menos de `max_cloud` % de nubes, una por fecha (la menos nublada).

    Columnas: id, fecha, dia (0 = lunes), nombre_dia, hora_utc, nubes, item.
    """
    # el catálogo devuelve las más recientes primero y corta en max_items: se busca año por año para no perder las viejas
    a0, a1 = int(start[:4]), int(end[:4])
    rows = []
    cat = catalog()
    for anio in range(a0, a1 + 1):
        d0 = start if anio == a0 else f"{anio}-01-01"
        d1 = end if anio == a1 else f"{anio}-12-31"
        s = cat.search(collections=[collection], intersects={"type": "Point", "coordinates": [lon, lat]}, datetime=f"{d0}/{d1}",
                       query={"eo:cloud_cover": {"lt": max_cloud}}, max_items=max_items)
        for it in s.items():
            rows.append({"id": it.id, "fecha": it.datetime.date(), "dia": it.datetime.weekday(), "nombre_dia": DIAS[it.datetime.weekday()],
                         "hora_utc": it.datetime.strftime("%H:%M"), "nubes": float(it.properties.get("eo:cloud_cover", np.nan)), "item": it})
    df = pd.DataFrame(rows, columns=["id", "fecha", "dia", "nombre_dia", "hora_utc", "nubes", "item"])
    if len(df) == 0:
        return df
    return df.sort_values(["fecha", "nubes"]).drop_duplicates("fecha").reset_index(drop=True)


def weekdays(df: pd.DataFrame) -> pd.DataFrame:
    """Solo lunes a viernes: el tránsito de camiones cae el fin de semana y las pasadas rotan por los días."""
    return df[df["dia"] < 5].reset_index(drop=True)


def scene_crs_bounds(item):
    with rasterio.open(item.assets["red"].href) as ds:
        return ds.crs, tuple(ds.bounds)


def strip(item, line: LineString, d_from: float, d_to: float, half: int = 4, step: float = PIXEL_M, margin: float = 30.0, with_scl: bool = True) -> dict:
    """La ruta enderezada entre `d_from` y `d_to` (m a lo largo de `line`, en el CRS de la escena).

    Devuelve un dict con `blue`, `green`, `red` (n_along x n_across, NaN fuera de la escena),
    `valid` (bool, píxel útil: dentro de la escena y sin nube), `along` (m desde d_from) y
    `x`, `y` (coordenadas del eje). La fila central del ancho es el eje de la ruta.
    """
    d_to = min(d_to, line.length)
    ds_ = np.arange(d_from, d_to, step)
    if len(ds_) < 3:
        raise ValueError("tramo demasiado corto")
    pts = np.array([[line.interpolate(d).x, line.interpolate(d).y] for d in ds_])
    tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9
    norm = np.stack([-tang[:, 1], tang[:, 0]], 1)
    offs = np.arange(-half, half + 1) * step
    sample = pts[:, None, :] + norm[:, None, :] * offs[None, :, None]        # (n, across, 2)
    x0, x1 = sample[..., 0].min() - margin, sample[..., 0].max() + margin
    y0, y1 = sample[..., 1].min() - margin, sample[..., 1].max() + margin
    out = {"along": ds_ - d_from, "x": pts[:, 0], "y": pts[:, 1]}
    valid = None
    for k in BANDAS:
        with rasterio.open(item.assets[k].href) as ds:
            w = from_bounds(x0, y0, x1, y1, ds.transform).round_offsets().round_lengths()
            a = ds.read(1, window=w).astype(np.float64)
            T = ds.window_transform(w)
        cols = np.round((sample[..., 0] - T.c) / T.a).astype(int)
        rows = np.round((sample[..., 1] - T.f) / T.e).astype(int)
        ok = (rows >= 0) & (rows < a.shape[0]) & (cols >= 0) & (cols < a.shape[1])
        s = np.full(rows.shape, np.nan)
        s[ok] = a[rows[ok], cols[ok]]
        s[s <= 0] = np.nan
        out[k] = s
        valid = ~np.isnan(s) if valid is None else valid & ~np.isnan(s)
    if with_scl and "scl" in item.assets:
        with rasterio.open(item.assets["scl"].href) as ds:
            w = from_bounds(x0, y0, x1, y1, ds.transform).round_offsets().round_lengths()
            a = ds.read(1, window=w)
            T = ds.window_transform(w)
        cols = np.round((sample[..., 0] - T.c) / T.a).astype(int)
        rows = np.round((sample[..., 1] - T.f) / T.e).astype(int)
        ok = (rows >= 0) & (rows < a.shape[0]) & (cols >= 0) & (cols < a.shape[1])
        scl = np.zeros(rows.shape, dtype=int)
        scl[ok] = a[rows[ok], cols[ok]]
        valid &= ~np.isin(scl, SCL_INVALIDAS)
        out["scl"] = scl
    out["valid"] = valid
    return out


def valid_km(s: dict, step: float = PIXEL_M) -> float:
    """Kilómetros de franja con el eje válido (dentro de la escena y sin nube)."""
    centro = s["valid"][:, s["valid"].shape[1] // 2]
    return float(centro.sum() * step / 1000.0)


__all__ = ["DIAS", "BANDAS", "SCL_INVALIDAS", "catalog", "search", "weekdays", "scene_crs_bounds", "strip", "valid_km"]
